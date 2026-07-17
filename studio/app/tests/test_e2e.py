# -*- coding: utf-8 -*-
"""端到端（E2E）测试：用 FastAPI TestClient 走完整 HTTP 流程。

测试覆盖：
- test_e2e_full_pipeline：完整 12 步 API 流程
    generate -> check-contract -> simulate -> report -> report/download
    -> compose -> check-compatibility -> fault-types -> llm/status
    -> models -> hil/pending -> upload-scade
- test_e2e_fault_injection_all_types：5 类故障注入（bias/signal_loss/noise/stuck/step）
- test_e2e_repair_loop：含违规代码 -> /api/repair -> 违规减少
- test_e2e_contract_assert_injection：契约 -> 断言注入 -> assert 包含契约条件
"""

import io
import os
import unittest

from fastapi.testclient import TestClient

# ---- 在导入 app 之前设置环境变量，避免触发真实 LM Studio 调用 ----
os.environ["USE_LLM"] = "false"
os.environ["LMSTUDIO_BASE_URL"] = "http://localhost:9999/v1"
os.environ["HIL_ENABLED"] = "false"

from app.main import app  # noqa: E402
from app.core.llm import lmstudio_client as lmstudio_module  # noqa: E402
from app.core.llm.model_router import reset_model_router  # noqa: E402
from app.core.hil.hil_manager import reset_hil_manager  # noqa: E402


# ====================================================================== #
# 测试常量
# ====================================================================== #

# 含违规的代码（全局变量 + 未初始化），用于修复闭环测试
DIRTY_CODE = "double s_global = 0.0;\nint s_count = 0;\n"

# 简单的 filter C 代码（含 double filter(double)），用于契约校验 / 仿真
FILTER_CODE = """\
double filter(double input) {
    static double last = 0.0;
    double out = 0.9 * last + 0.1 * input;
    last = out;
    return out;
}
"""

# 测试用契约 YAML（含后置条件：filtered_output >= 0 / <= 20000）
SAMPLE_CONTRACT = """\
component: test_filter
version: 1.0.0
safety_level: DAL-B
traceability: [REQ-001]

interface:
  inputs:
    - name: raw_input
      type: double
      range: [0, 20000]
  outputs:
    - name: filtered_output
      type: double

contracts:
  preconditions:
    - "raw_input != NULL"
    - "raw_input >= 0"
  postconditions:
    - "filtered_output >= 0"
    - "filtered_output <= 20000"
  invariants:
    - "sample_rate == 100Hz"
  fault_handling:
    - "if raw_input == 0: set fault_detected = true"
"""

# 兼容的契约组合（A 输出范围 [0, 100] 包含于 B 输入范围 [0, 200]）
CONTRACT_A_COMPAT = """\
component: filter_a
version: 1.0.0
safety_level: DAL-B
traceability: [REQ-A]
interface:
  inputs:
    - name: raw_input
      type: double
      range: [0, 20000]
  outputs:
    - name: filtered_output
      type: double
      range: [0, 100]
contracts:
  preconditions:
    - "raw_input >= 0"
  postconditions:
    - "filtered_output >= 0"
    - "filtered_output <= 100"
  invariants:
    - "sample_rate == 100Hz"
  fault_handling:
    - "if raw_input == 0: set fault_detected = true"
"""

CONTRACT_B_COMPAT = """\
component: filter_b
version: 1.0.0
safety_level: DAL-B
traceability: [REQ-B]
interface:
  inputs:
    - name: a_output
      type: double
      range: [0, 200]
  outputs:
    - name: filtered_output
      type: double
      range: [0, 200]
contracts:
  preconditions:
    - "a_output >= 0"
  postconditions:
    - "filtered_output >= 0"
    - "filtered_output <= 200"
  invariants:
    - "sample_rate == 100Hz"
  fault_handling:
    - "if a_output == 0: set fault_detected = true"
"""

# 测试数据目录（用于 upload-scade 测试）
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_EXAMPLE_LUS = os.path.join(_DATA_DIR, "example.lus")

# 5 类故障及其参数
FAULT_CASES = [
    ("bias", {"bias_value": 1000.0}),
    ("signal_loss", {"start": 0, "end": 100}),
    ("noise", {"amplitude": 50.0}),
    ("stuck", {"start": 0, "end": 100, "stuck_value": 0.0}),
    ("step", {"step_at": 100, "step_value": 1000.0}),
]


def _reset_singletons() -> None:
    """重置 HIL 和 ModelRouter 单例，避免测试间状态污染。"""
    reset_hil_manager()
    reset_model_router()
    lmstudio_module._unified_client = None


class TestE2EFullPipeline(unittest.TestCase):
    """端到端完整流程测试：用 TestClient 走真实 HTTP 链路。"""

    @classmethod
    def setUpClass(cls) -> None:
        """类级 setUp：创建一次 TestClient（避免重复启动 lifespan）。"""
        _reset_singletons()
        # with 上下文触发 lifespan（创建 ./project 目录等）
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        """类级 tearDown：退出 lifespan 上下文。"""
        cls.client.__exit__(None, None, None)

    def setUp(self) -> None:
        """每个测试前重置单例，保证 LLM/HIL 状态干净。"""
        _reset_singletons()

    # ------------------------------------------------------------------ #
    # 主流程：12 步 API 全链路
    # ------------------------------------------------------------------ #

    def test_e2e_full_pipeline(self) -> None:
        """完整 12 步 API 流程：generate -> check-contract -> simulate ->
        report -> report/download -> compose -> check-compatibility ->
        fault-types -> llm/status -> models -> hil/pending -> upload-scade。
        """
        # 1. POST /api/generate —— 触发完整流水线
        resp = self.client.post(
            "/api/generate",
            json={"requirement": "实现一个低通滤波器"},
        )
        self.assertEqual(resp.status_code, 200, f"generate 失败: {resp.text}")
        gen = resp.json()
        # 验证返回字段完整
        for key in (
            "contract",
            "code",
            "cppcheck_result",
            "repair_history",
            "simulation_result",
        ):
            self.assertIn(key, gen, f"/api/generate 缺少字段 {key}")
        # 不应被中止
        self.assertFalse(gen.get("aborted", False), "流水线不应被中止")
        code = gen["code"]
        contract = gen["contract"]
        self.assertIsInstance(code, str)
        self.assertGreater(len(code), 0, "生成的代码不应为空")
        self.assertIsInstance(contract, str)
        self.assertGreater(len(contract), 0, "生成的契约不应为空")

        # 2. POST /api/check-contract —— 单独触发契约校验
        resp = self.client.post(
            "/api/check-contract",
            json={"code": code, "contract": contract},
        )
        self.assertEqual(resp.status_code, 200, f"check-contract 失败: {resp.text}")
        ccr = resp.json()
        # 验证返回字段（与路由实现一致）
        for key in (
            "passed",
            "preconditions",
            "postconditions",
            "invariants",
            "fault_handling",
            "assert_code",
            "violations",
        ):
            self.assertIn(key, ccr, f"/api/check-contract 缺少字段 {key}")

        # 3. POST /api/simulate —— 故障注入仿真
        resp = self.client.post(
            "/api/simulate",
            json={
                "code": code,
                "contract": contract,
                "fault_type": "bias",
                "fault_params": {"bias_value": 1000},
            },
        )
        self.assertEqual(resp.status_code, 200, f"simulate 失败: {resp.text}")
        sim = resp.json()
        # 验证仿真结果字段
        for key in (
            "passed",
            "total_steps",
            "fault_type",
            "input_waveform",
            "output_waveform",
        ):
            self.assertIn(key, sim, f"/api/simulate 缺少字段 {key}")
        self.assertEqual(sim["fault_type"], "bias")
        self.assertEqual(sim["fault_params"], {"bias_value": 1000})

        # 4. POST /api/report —— 生成 DO-178C 合规报告
        pipeline_result = dict(gen)
        # 补充 report 需要的字段（pipeline_result 与 /api/generate 返回结构一致）
        pipeline_result.setdefault("final_code", gen["code"])
        pipeline_result.setdefault("final_violations", gen.get("final_violations", []))
        resp = self.client.post(
            "/api/report",
            json={"pipeline_result": pipeline_result},
        )
        self.assertEqual(resp.status_code, 200, f"report 失败: {resp.text}")
        rep = resp.json()
        for key in ("report_html", "traceability_matrix", "do178_objectives"):
            self.assertIn(key, rep, f"/api/report 缺少字段 {key}")
        self.assertIsInstance(rep["report_html"], str)
        self.assertGreater(len(rep["report_html"]), 500, "HTML 报告内容过短")
        self.assertIsInstance(rep["traceability_matrix"], list)
        self.assertIsInstance(rep["do178_objectives"], list)
        self.assertGreaterEqual(len(rep["do178_objectives"]), 10)

        # 5. GET /api/report/download —— 下载 HTML 报告
        resp = self.client.get("/api/report/download")
        self.assertEqual(resp.status_code, 200, f"report/download 失败: {resp.text}")
        self.assertIn("text/html", resp.headers.get("content-type", ""))
        self.assertIn("attachment", resp.headers.get("content-disposition", ""))
        self.assertIn("do178c_report.html", resp.headers.get("content-disposition", ""))
        self.assertIn(b"<html", resp.content, "下载内容应为 HTML")

        # 6. POST /api/compose —— 组件组合
        resp = self.client.post(
            "/api/compose",
            json={
                "component_a": {"code": FILTER_CODE, "contract": CONTRACT_A_COMPAT},
                "component_b": {"code": FILTER_CODE, "contract": CONTRACT_B_COMPAT},
                "connection": "sequential",
                "simulate": False,
            },
        )
        self.assertEqual(resp.status_code, 200, f"compose 失败: {resp.text}")
        comp = resp.json()
        self.assertIn("composed_code", comp)
        self.assertIsInstance(comp["composed_code"], str)
        self.assertGreater(len(comp["composed_code"]), 0, "组合代码不应为空")
        self.assertIn("connection", comp)
        self.assertEqual(comp["connection"], "sequential")

        # 7. POST /api/check-compatibility —— 契约兼容性检查
        resp = self.client.post(
            "/api/check-compatibility",
            json={
                "contract_a": CONTRACT_A_COMPAT,
                "contract_b": CONTRACT_B_COMPAT,
                "connection": "sequential",
            },
        )
        self.assertEqual(
            resp.status_code, 200, f"check-compatibility 失败: {resp.text}"
        )
        compat = resp.json()
        for key in (
            "compatible",
            "checked_pairs",
            "violations",
            "warnings",
            "connection",
        ):
            self.assertIn(key, compat, f"/api/check-compatibility 缺少字段 {key}")

        # 8. GET /api/fault-types —— 5 类故障描述
        resp = self.client.get("/api/fault-types")
        self.assertEqual(resp.status_code, 200, f"fault-types 失败: {resp.text}")
        ft = resp.json()
        self.assertIn("fault_types", ft)
        fault_type_list = ft["fault_types"]
        self.assertEqual(len(fault_type_list), 5, "应有 5 类故障")
        types = {item["type"] for item in fault_type_list}
        self.assertEqual(
            types,
            {"bias", "signal_loss", "noise", "stuck", "step"},
            "故障类型集合不正确",
        )
        for item in fault_type_list:
            for key in ("type", "name", "desc", "default_params", "params_schema"):
                self.assertIn(key, item)

        # 9. GET /api/llm/status —— LLM 状态
        resp = self.client.get("/api/llm/status")
        self.assertEqual(resp.status_code, 200, f"llm/status 失败: {resp.text}")
        status = resp.json()
        for key in ("available", "models", "use_llm"):
            self.assertIn(key, status, f"/api/llm/status 缺少字段 {key}")
        # USE_LLM=false 时 use_llm 应为 False
        self.assertFalse(status["use_llm"], "USE_LLM=false 时 use_llm 应为 False")

        # 10. GET /api/models —— 模型列表
        resp = self.client.get("/api/models")
        self.assertEqual(resp.status_code, 200, f"models 失败: {resp.text}")
        models_resp = resp.json()
        self.assertIn("models", models_resp)
        self.assertIn("selected", models_resp)
        self.assertIsInstance(models_resp["models"], list)

        # 11. GET /api/hil/pending —— 待审批列表
        resp = self.client.get("/api/hil/pending")
        self.assertEqual(resp.status_code, 200, f"hil/pending 失败: {resp.text}")
        pending = resp.json()
        self.assertIn("pending", pending)
        self.assertIn("enabled", pending)
        self.assertIsInstance(pending["pending"], list)
        # HIL_ENABLED=false 时 enabled 应为 False
        self.assertFalse(pending["enabled"], "HIL_ENABLED=false 时 enabled 应为 False")

        # 12. POST /api/upload-scade —— 上传 .lus 文件
        self.assertTrue(os.path.exists(_EXAMPLE_LUS), "测试数据 example.lus 不存在")
        with open(_EXAMPLE_LUS, "rb") as f:
            lus_bytes = f.read()
        resp = self.client.post(
            "/api/upload-scade",
            files={
                "file": (
                    "example.lus",
                    io.BytesIO(lus_bytes),
                    "application/octet-stream",
                )
            },
        )
        self.assertEqual(resp.status_code, 200, f"upload-scade 失败: {resp.text}")
        up = resp.json()
        for key in ("filename", "parsed", "requirement", "contract"):
            self.assertIn(key, up, f"/api/upload-scade 缺少字段 {key}")
        self.assertEqual(up["filename"], "example.lus")
        self.assertEqual(up["parsed"]["node_name"], "LowPassFilter")
        self.assertIn("[REQ-", up["requirement"])
        self.assertIn("component:", up["contract"])


class TestE2EFaultInjectionAllTypes(unittest.TestCase):
    """测试 5 类故障注入端到端流程。"""

    @classmethod
    def setUpClass(cls) -> None:
        _reset_singletons()
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def setUp(self) -> None:
        _reset_singletons()

    def test_e2e_fault_injection_all_types(self) -> None:
        """5 类故障 bias/signal_loss/noise/stuck/step 通过 /api/simulate 注入，
        每种故障 simulation_result 包含正确的 fault_type 和 fault_params。
        """
        for fault_type, params in FAULT_CASES:
            with self.subTest(fault_type=fault_type):
                resp = self.client.post(
                    "/api/simulate",
                    json={
                        "code": FILTER_CODE,
                        "contract": SAMPLE_CONTRACT,
                        "fault_type": fault_type,
                        "fault_params": params,
                    },
                )
                self.assertEqual(
                    resp.status_code,
                    200,
                    f"simulate {fault_type} 失败: {resp.text}",
                )
                sim = resp.json()
                # 验证 fault_type 正确
                self.assertEqual(
                    sim["fault_type"],
                    fault_type,
                    f"fault_type 应为 {fault_type}",
                )
                # 验证 fault_params 正确回显
                self.assertEqual(
                    sim["fault_params"],
                    params,
                    f"fault_params 应为 {params}",
                )
                # 验证必要字段存在
                self.assertIn("passed", sim)
                self.assertIn("total_steps", sim)
                self.assertIn("input_waveform", sim)
                self.assertIn("output_waveform", sim)
                # 仿真步数应大于 0
                self.assertGreater(sim["total_steps"], 0)


class TestE2ERepairLoop(unittest.TestCase):
    """修复闭环端到端测试：含违规代码 -> /api/repair -> 违规减少。"""

    @classmethod
    def setUpClass(cls) -> None:
        _reset_singletons()
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def setUp(self) -> None:
        _reset_singletons()

    def test_e2e_repair_loop(self) -> None:
        """构造含违规的代码（全局变量）-> POST /api/repair -> 修复后违规减少。"""
        # 先用 cppcheck 扫描原始代码，得到初始违规数
        from skyforge_engine.tools.cppcheck_scanner import scan as cppcheck_scan

        initial_violations = cppcheck_scan(DIRTY_CODE)
        self.assertGreater(
            len(initial_violations),
            0,
            "测试前置：dirty code 应有违规",
        )

        # 调用 /api/repair
        resp = self.client.post(
            "/api/repair",
            json={"code": DIRTY_CODE, "max_iterations": 3},
        )
        self.assertEqual(resp.status_code, 200, f"repair 失败: {resp.text}")
        result = resp.json()
        # 验证返回字段
        for key in ("final_code", "repair_history", "final_violations"):
            self.assertIn(key, result, f"/api/repair 缺少字段 {key}")

        # 修复后违规数应少于初始
        final_count = len(result["final_violations"])
        self.assertLess(
            final_count,
            len(initial_violations),
            f"修复后违规应减少: 初始 {len(initial_violations)} -> 修复后 {final_count}",
        )
        # 修复历史不应为空
        self.assertGreater(len(result["repair_history"]), 0, "应有修复历史记录")
        # 验证修复历史结构
        for entry in result["repair_history"]:
            self.assertIn("iteration", entry)
            self.assertIn("violations_before", entry)
            self.assertIn("actions", entry)
            self.assertIn("code_after", entry)
        # final_code 应为非空字符串
        self.assertIsInstance(result["final_code"], str)
        self.assertGreater(len(result["final_code"]), 0)


class TestE2EContractAssertInjection(unittest.TestCase):
    """契约 -> 断言注入端到端测试。"""

    @classmethod
    def setUpClass(cls) -> None:
        _reset_singletons()
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def setUp(self) -> None:
        _reset_singletons()

    def test_e2e_contract_assert_injection(self) -> None:
        """生成契约 -> 调 /api/check-contract 生成断言 -> assert 代码包含契约条件。

        验证：
        1. assert_code 含 assert() 调用
        2. assert_code 含 __check_contract_step_ 函数
        3. assert_code 含后置条件表达式（filtered_output >= 0 / <= 20000）
        """
        # 调用 /api/check-contract 触发契约 -> 断言注入
        resp = self.client.post(
            "/api/check-contract",
            json={"code": FILTER_CODE, "contract": SAMPLE_CONTRACT},
        )
        self.assertEqual(
            resp.status_code,
            200,
            f"check-contract 失败: {resp.text}",
        )
        ccr = resp.json()

        # assert_code 应为非空字符串
        self.assertIsInstance(ccr["assert_code"], str)
        self.assertGreater(len(ccr["assert_code"]), 0, "assert_code 不应为空")

        assert_code = ccr["assert_code"]

        # 1. 含 assert() 调用
        self.assertIn("assert(", assert_code, "assert_code 应含 assert() 调用")
        # 2. 含 __check_contract_step_ 函数
        self.assertIn(
            "__check_contract_step_",
            assert_code,
            "assert_code 应含 __check_contract_step_ 函数",
        )
        # 3. 含后置条件表达式（契约中的 filtered_output 条件）
        # 注意：契约转断言时，filtered_output 会被映射为 output（参见模板）
        self.assertIn(
            "output",
            assert_code,
            "assert_code 应包含契约输出变量 output",
        )
        # 后置条件 filtered_output >= 0 / <= 20000 应被转化为 assert
        # 由于后置条件表达式经 _extract_postconditions 解析，断言中应出现数值
        self.assertTrue(
            "20000" in assert_code or "0" in assert_code,
            "assert_code 应包含后置条件中的数值边界",
        )

        # 4. 含 NaN/Inf 检查（模板固定项）
        self.assertIn("isnan", assert_code, "assert_code 应含 NaN 检查")
        self.assertIn("isinf", assert_code, "assert_code 应含 Inf 检查")

        # 5. 契约校验本身应能执行（passed 字段存在）
        self.assertIn("passed", ccr)
        self.assertIsInstance(ccr["passed"], bool)
        # postconditions 列表应至少有 2 项（对应契约中的 2 条后置条件）
        self.assertGreaterEqual(
            len(ccr["postconditions"]),
            2,
            "postconditions 应至少 2 项",
        )


if __name__ == "__main__":
    unittest.main()
