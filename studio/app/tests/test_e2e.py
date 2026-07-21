# -*- coding: utf-8 -*-
"""端到端（E2E）测试：用 FastAPI TestClient 走完整 HTTP 流程。

测试覆盖：
- test_e2e_full_pipeline：完整 12 步 API 流程
    generate -> simulate -> report -> report/download
    -> compose -> check-compatibility -> fault-types -> llm/status
    -> models -> hil/pending -> upload-scade
- test_e2e_fault_injection_all_types：5 类故障注入（bias/signal_loss/noise/stuck/step）
"""

import io
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

# ---- 在导入 app 之前设置环境变量，避免触发真实 LM Studio 调用 ----
os.environ["USE_LLM"] = "false"
os.environ["LOCAL_LLM_BASE_URL"] = "http://localhost:9999/v1"
os.environ["HIL_ENABLED"] = "false"

from app.main import app  # noqa: E402
from app.core.llm import local_llm_client as lmstudio_module  # noqa: E402
from app.core.llm.model_router import reset_model_router  # noqa: E402
from app.core.hil.hil_manager import reset_hil_manager  # noqa: E402


# ====================================================================== #
# 测试常量
# ====================================================================== #

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
        """完整 12 步 API 流程：generate -> simulate ->
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

        # 2. POST /api/simulate —— 故障注入仿真
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
        self.assertGreaterEqual(len(fault_type_list), 5, "应至少有 5 类故障")
        types = {item["type"] for item in fault_type_list}
        expected = {"bias", "signal_loss", "noise", "stuck", "step"}
        self.assertTrue(
            expected.issubset(types),
            f"故障类型集合不完整, 期望: {expected}, 实际: {types}",
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


class TestE2EMultiLanguage(unittest.TestCase):
    """多语言代码生成端到端测试：C / C++ / Python 三种语言全流程。"""

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

    def test_e2e_generate_c_language(self) -> None:
        """POST /api/generate language='c' -> 生成 C 代码。"""
        resp = self.client.post(
            "/api/generate",
            json={"requirement": "实现一个低通滤波器", "language": "c"},
        )
        self.assertEqual(resp.status_code, 200, f"generate c 失败: {resp.text}")
        gen = resp.json()
        self.assertFalse(gen.get("aborted", False))
        code = gen["code"]
        self.assertIsInstance(code, str)
        self.assertGreater(len(code), 0, "C 代码不应为空")
        # C 代码应包含 C 语法特征
        self.assertTrue(
            any(kw in code for kw in ("int ", "double ", "float ", "void ", "static ", "return ")),
            f"C 代码应含 C 关键字: {code[:200]}",
        )

    def test_e2e_generate_cpp_language(self) -> None:
        """POST /api/generate language='cpp' -> 生成 C++ 代码。"""
        resp = self.client.post(
            "/api/generate",
            json={"requirement": "实现一个低通滤波器", "language": "cpp"},
        )
        self.assertEqual(resp.status_code, 200, f"generate cpp 失败: {resp.text}")
        gen = resp.json()
        self.assertFalse(gen.get("aborted", False))
        code = gen["code"]
        self.assertIsInstance(code, str)
        self.assertGreater(len(code), 0, "C++ 代码不应为空")
        # C++ 代码应包含 C++ 语法特征
        self.assertTrue(
            any(kw in code for kw in ("class ", "std::", "template", "namespace", "#include", "auto ")),
            f"C++ 代码应含 C++ 关键字: {code[:200]}",
        )

    def test_e2e_generate_python_language(self) -> None:
        """POST /api/generate language='python' -> 生成 Python 代码。"""
        resp = self.client.post(
            "/api/generate",
            json={"requirement": "实现一个低通滤波器", "language": "python"},
        )
        self.assertEqual(resp.status_code, 200, f"generate python 失败: {resp.text}")
        gen = resp.json()
        self.assertFalse(gen.get("aborted", False))
        code = gen["code"]
        self.assertIsInstance(code, str)
        self.assertGreater(len(code), 0, "Python 代码不应为空")
        # Python 代码应包含 Python 语法特征
        self.assertTrue(
            any(kw in code for kw in ("def ", "class ", "import ", "return ", "self.", "elif ")),
            f"Python 代码应含 Python 关键字: {code[:200]}",
        )

    def test_e2e_generate_all_languages_produce_contract(self) -> None:
        """三种语言生成都应产出非空契约。"""
        for lang in ("c", "cpp", "python"):
            with self.subTest(language=lang):
                resp = self.client.post(
                    "/api/generate",
                    json={"requirement": "实现一个低通滤波器", "language": lang},
                )
                self.assertEqual(resp.status_code, 200, f"generate {lang} 失败")
                gen = resp.json()
                contract = gen["contract"]
                self.assertIsInstance(contract, str)
                self.assertGreater(len(contract), 0, f"{lang} 契约不应为空")
                self.assertIn("component:", contract, f"{lang} 契约应含 component 字段")

    def test_e2e_generate_all_languages_produce_violations(self) -> None:
        """三种语言生成都应产出 cppcheck_result 列表（可能为空）。"""
        for lang in ("c", "cpp", "python"):
            with self.subTest(language=lang):
                resp = self.client.post(
                    "/api/generate",
                    json={"requirement": "实现一个低通滤波器", "language": lang},
                )
                self.assertEqual(resp.status_code, 200, f"generate {lang} 失败")
                gen = resp.json()
                self.assertIn("cppcheck_result", gen)
                self.assertIsInstance(gen["cppcheck_result"], list)

    def test_e2e_generate_default_language_is_c(self) -> None:
        """不传 language 参数时默认使用 C。"""
        resp = self.client.post(
            "/api/generate",
            json={"requirement": "实现一个低通滤波器"},
        )
        self.assertEqual(resp.status_code, 200, f"generate default 失败: {resp.text}")
        gen = resp.json()
        code = gen["code"]
        # 默认应生成 C 代码
        self.assertTrue(
            any(kw in code for kw in ("int ", "double ", "float ", "void ", "static ", "return ")),
            f"默认语言应为 C: {code[:200]}",
        )


class TestE2EStrictMode(unittest.TestCase):
    """严格模式端到端测试：验证删除优雅降级后的行为。"""

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

    def test_e2e_mock_mode_pipeline_completes(self) -> None:
        """mock 模式下完整流水线通过，返回非空代码和契约。"""
        with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "mock"}):
            resp = self.client.post(
                "/api/generate",
                json={"requirement": "实现一个低通滤波器"},
            )
        self.assertEqual(resp.status_code, 200, f"generate 失败: {resp.text}")
        gen = resp.json()
        self.assertFalse(gen.get("aborted", False), "流水线不应被中止")
        self.assertIsInstance(gen["code"], str)
        self.assertGreater(len(gen["code"]), 0, "生成的代码不应为空")
        self.assertIsInstance(gen["contract"], str)
        self.assertGreater(len(gen["contract"]), 0, "生成的契约不应为空")

    def test_e2e_api_mode_raises_when_backend_unavailable(self) -> None:
        """api 模式下 LLM 后端不可用时直接报错，不再降级。"""
        with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "api"}):
            with patch(
                "skyforge_engine.pipeline.run_pipeline",
                side_effect=RuntimeError("LLM 后端不可用"),
            ):
                resp = self.client.post(
                    "/api/generate",
                    json={"requirement": "实现一个低通滤波器"},
                )
        # generate 路由捕获异常后返回 200 但带有 error/aborted 标记
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("error", data)
        self.assertTrue(data.get("aborted", False), "应标记为 aborted")
        self.assertIn("LLM 后端不可用", data["error"])

    def test_e2e_local_mode_raises_when_ollama_down(self) -> None:
        """local 模式下 Ollama 未启动时直接报错，不再降级。"""
        with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "local"}):
            with patch(
                "skyforge_engine.pipeline.run_pipeline",
                side_effect=RuntimeError("Ollama 未启动"),
            ):
                resp = self.client.post(
                    "/api/generate",
                    json={"requirement": "实现一个低通滤波器"},
                )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("error", data)
        self.assertTrue(data.get("aborted", False), "应标记为 aborted")
        self.assertIn("Ollama 未启动", data["error"])


if __name__ == "__main__":
    unittest.main()
