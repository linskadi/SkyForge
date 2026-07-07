"""DO-178C 合规报告生成器测试（次级功能）。

测试覆盖：
- test_generate_report_has_7_sections：HTML 报告含 7 个章节
- test_generate_report_contains_badges：[REQ-xxx] [CON-xxx] [TST-xxx] Tag 彩色 Badge
- test_generate_report_contains_pre_code：代码用 <pre><code> 标签包裹
- test_traceability_matrix：追溯矩阵构建
- test_traceability_matrix_bidirectional：双向追溯（多 REQ / CON）
- test_do178_objectives：12 项目标检查
- test_do178_objectives_status_values：状态值合法
- test_report_endpoint：POST /api/report 路由
- test_report_download_endpoint：GET /api/report/download 路由
"""

import unittest

from app.core.report import (
    TraceEntry,
    build_matrix,
    check_objectives,
    generate_report,
)


# ---- 测试 fixture：构造一份与 /api/generate 返回结构一致的 pipeline_result ----

SAMPLE_PIPELINE_RESULT: dict = {
    "requirement": {
        "req_id": "REQ-001",
        "desc": "实现一个机载低通滤波器，截止频率10Hz，采样率100Hz",
        "type": "filter",
        "module_name": "lowpass_filter_10hz",
        "safety_level": "DAL-B",
        "params": {
            "cutoff_hz": 10.0,
            "sample_rate_hz": 100.0,
            "range_min": 0.0,
            "range_max": 20000.0,
        },
        "constraints": ["WCET <= 1ms", "禁止动态内存（MISRA Rule-21.3）"],
    },
    "contract": (
        "component: lowpass_filter_10hz\n"
        "version: 1.2.0\n"
        "safety_level: DAL-B\n"
        "traceability: [REQ-001]\n"
        "\n"
        "interface:\n"
        "  inputs:\n"
        "    - name: raw_input\n"
        "      type: double\n"
        "      range: [0, 20000]\n"
        "  outputs:\n"
        "    - name: filtered_output\n"
        "      type: double\n"
        "\n"
        "contracts:\n"
        "  preconditions:\n"
        '    - "raw_input != NULL"\n'
        '    - "raw_input >= 0"\n'
        "  postconditions:\n"
        '    - "filtered_output >= 0"\n'
        '    - "filtered_output <= 20000"\n'
        "  invariants:\n"
        '    - "sample_rate == 100Hz"\n'
        "  fault_handling:\n"
        '    - "if raw_input == 0: set fault_detected = true"\n'
    ),
    "final_code": (
        "/* [REQ-001] [MISRA-Rule-8.13] 机载信号滤波器实现 */\n"
        '#include "lowpass_filter_10hz.h"\n'
        "#include <math.h>\n"
        "\n"
        "/* [REQ-001] [MISRA-Rule-8.9] 模块内部状态 */\n"
        "static double s_prev_output = 0.0;\n"
        "static int    s_initialized = 0;\n"
        "\n"
        "/* [REQ-001] [MISRA-Rule-15.7] 一阶 IIR 低通滤波 */\n"
        "double lowpass_filter_10hz_apply(double raw_input) {\n"
        "    double filtered_output;\n"
        "    if (0 == s_initialized) {\n"
        "        lowpass_filter_10hz_init();\n"
        "    }\n"
        "    filtered_output = 0.015466 * raw_input + 0.984534 * s_prev_output;\n"
        "    s_prev_output = filtered_output;\n"
        "    return filtered_output;\n"
        "}\n"
    ),
    "cppcheck_result": [
        {
            "file": "code.c",
            "line": 7,
            "column": 0,
            "severity": "style",
            "rule_id": "misra-c2012-8.7",
            "message": "外部变量应定义为 static（Rule 8.7）",
        },
        {
            "file": "code.c",
            "line": 12,
            "column": 0,
            "severity": "style",
            "rule_id": "misra-c2012-17.7",
            "message": "函数返回值未被使用（Rule 17.7）",
        },
    ],
    "repair_history": [
        {
            "iteration": 1,
            "violations_before": [
                {
                    "file": "code.c",
                    "line": 7,
                    "column": 0,
                    "severity": "style",
                    "rule_id": "misra-c2012-8.7",
                    "message": "外部变量应定义为 static",
                }
            ],
            "violations_count_before": 1,
            "actions": [
                {
                    "rule_id": "misra-c2012-8.7",
                    "req_id": "REQ-001",
                    "description": "外部变量转为 static",
                }
            ],
            "actions_count": 1,
            "code_after": "/* 修复后 */\n",
            "contract_passed": True,
        },
    ],
    "final_violations": [],
    "contract_check_result": {
        "passed": True,
        "preconditions": [
            {
                "id": "CON-001-PRE-000",
                "desc": "raw_input != NULL",
                "passed": True,
                "detail": "代码中检测到 NULL 检查",
            },
            {
                "id": "CON-001-PRE-001",
                "desc": "raw_input >= 0",
                "passed": True,
                "detail": "范围检查默认通过（mock）",
            },
        ],
        "postconditions": [
            {
                "id": "CON-001-POST-000",
                "desc": "filtered_output >= 0",
                "passed": True,
                "detail": "范围检查默认通过（mock）",
            },
            {
                "id": "CON-001-POST-001",
                "desc": "filtered_output <= 20000",
                "passed": True,
                "detail": "范围检查默认通过（mock）",
            },
        ],
        "invariants": [
            {
                "id": "CON-001-INV-000",
                "desc": "sample_rate == 100Hz",
                "passed": True,
                "detail": "invariant 默认通过（mock）",
            }
        ],
        "fault_handling": [
            {
                "id": "CON-001-FH-000",
                "desc": "if raw_input == 0: set fault_detected = true",
                "passed": True,
                "detail": "命中关键词 ['0 ==']，视为已处理",
            }
        ],
        "assert_code": (
            "/* 自动生成的契约断言 */\n"
            "static void __check_contract_step_CON_001(double output) {\n"
            '    assert(output >= 0 && "[CON-001-POST-000] 违反后置条件");\n'
            "    assert(!isnan(output));\n"
            "}\n"
        ),
        "violations": [],
    },
    "simulation_result": {
        "passed": True,
        "total_steps": 200,
        "fault_type": "bias",
        "fault_params": {"bias_value": 50.0},
        "input_waveform": [0.0, 1.0, 2.0, 3.0, 4.0] + [5.0] * 195,
        "output_waveform": [0.0, 0.5, 1.5, 2.5, 3.5] + [5.0] * 195,
        "contract_violation": None,
        "statistics": {
            "input_min": 0.0,
            "input_max": 5.0,
            "input_mean": 4.85,
            "output_min": 0.0,
            "output_max": 5.0,
            "output_mean": 4.85,
            "duration_ms": 12.34,
        },
        "compilation": {
            "success": True,
            "errors": "",
            "used_mock": False,
        },
        "terminal_log": "[1/6] 生成正常传感器数据...\n[6/6] 仿真结果: PASSED",
    },
}


class TestGenerateReport(unittest.TestCase):
    """报告生成器测试。"""

    def setUp(self) -> None:
        self.html = generate_report(SAMPLE_PIPELINE_RESULT)

    def test_generate_report_returns_html_string(self) -> None:
        """generate_report 返回非空 HTML 字符串。"""
        self.assertIsInstance(self.html, str)
        self.assertGreater(len(self.html), 1000)
        self.assertTrue(self.html.startswith("<!DOCTYPE html>"))
        self.assertIn("</html>", self.html)

    def test_generate_report_has_7_sections(self) -> None:
        """HTML 含 7 个章节：封面、追溯矩阵、契约验证、MISRA、仿真、目标符合性、签名页。"""
        # 1) 封面（含项目名 + 日期 + 版本号 + 生成时间）
        self.assertIn("DO-178C 合规报告", self.html)
        self.assertIn("lowpass_filter_10hz", self.html)  # 项目名
        self.assertIn("1.2.0", self.html)  # 版本号（来自契约 YAML）
        self.assertIn("DAL-B", self.html)  # 安全等级
        # 含日期（YYYY-MM-DD）和时间（HH:MM:SS）

        self.assertRegex(self.html, r"\d{4}-\d{2}-\d{2}")
        self.assertRegex(self.html, r"\d{2}:\d{2}:\d{2}")

        # 2) 需求追溯矩阵（章节标题为"1. 需求追溯矩阵"）
        self.assertIn("需求追溯矩阵", self.html)

        # 3) 契约验证结果
        self.assertIn("契约验证结果", self.html)
        self.assertIn("前置条件", self.html)
        self.assertIn("后置条件", self.html)
        self.assertIn("不变式", self.html)
        self.assertIn("故障处理", self.html)

        # 4) MISRA-C 合规摘要
        self.assertIn("MISRA-C 合规摘要", self.html)
        self.assertIn("修复历史", self.html)

        # 5) 数字孪生仿真结果
        self.assertIn("数字孪生仿真结果", self.html)
        self.assertIn("故障注入结果", self.html)
        self.assertIn("契约违约情况", self.html)

        # 6) DO-178C 目标符合性表
        self.assertIn("DO-178C 目标符合性表", self.html)
        self.assertIn("OBJ-1", self.html)
        self.assertIn("OBJ-12", self.html)

        # 7) 签名页
        self.assertIn("签名页", self.html)
        self.assertIn("开发者", self.html)
        self.assertIn("审核者", self.html)
        self.assertIn("批准者", self.html)

    def test_generate_report_contains_badges(self) -> None:
        """报告含彩色 Badge：[REQ-xxx] [CON-xxx] [TST-xxx] [MISRA-Rule-x.x]。"""
        # CSS 类
        self.assertIn("badge-req", self.html)
        self.assertIn("badge-con", self.html)
        self.assertIn("badge-tst", self.html)
        self.assertIn("badge-misra", self.html)
        # 实际 Tag
        self.assertIn("REQ-001", self.html)
        self.assertIn("CON-001", self.html)
        self.assertIn("TST-001", self.html)
        self.assertIn("MISRA-Rule", self.html)

    def test_generate_report_contains_pre_code(self) -> None:
        """代码用 <pre><code> 标签包裹。"""
        self.assertIn("<pre><code>", self.html)
        # 应该包含契约断言插桩代码
        self.assertIn("__check_contract_step_CON_001", self.html)
        # 应该包含最终 C 代码
        self.assertIn("lowpass_filter_10hz_apply", self.html)

    def test_generate_report_contains_internal_css(self) -> None:
        """HTML 含内嵌 CSS（不依赖外部库）。"""
        self.assertIn("<style>", self.html)
        self.assertIn("@media print", self.html)
        self.assertIn("font-family", self.html)

    def test_generate_report_objectives_summary(self) -> None:
        """目标符合性表含满足/部分满足/未满足的统计卡片。"""
        self.assertIn("满足", self.html)
        self.assertIn("部分满足", self.html)
        self.assertIn("未满足", self.html)


class TestTraceabilityMatrix(unittest.TestCase):
    """追溯矩阵构建器测试。"""

    def setUp(self) -> None:
        self.matrix = build_matrix(SAMPLE_PIPELINE_RESULT)

    def test_traceability_matrix_returns_list(self) -> None:
        """build_matrix 返回 list[TraceEntry]。"""
        self.assertIsInstance(self.matrix, list)
        self.assertGreater(len(self.matrix), 0)
        for entry in self.matrix:
            self.assertIsInstance(entry, TraceEntry)

    def test_traceability_matrix_has_req_entry(self) -> None:
        """追溯矩阵至少含 REQ-001 一行。"""
        req_ids = {e.req_id for e in self.matrix}
        self.assertIn("REQ-001", req_ids)

    def test_traceability_matrix_links_req_to_con(self) -> None:
        """REQ-001 通过契约 YAML traceability 字段反查到 CON-001。"""
        entry = next(e for e in self.matrix if e.req_id == "REQ-001")
        self.assertEqual(entry.contract_id, "CON-001")

    def test_traceability_matrix_links_req_to_code_line(self) -> None:
        """REQ-001 链接到代码中含 [REQ-001] 注释的行号。"""
        entry = next(e for e in self.matrix if e.req_id == "REQ-001")
        self.assertGreater(entry.code_line, 0)
        self.assertIn("REQ-001", entry.code_snippet)
        # 应当含 MISRA-Rule 标记
        self.assertIn("MISRA-Rule", entry.code_snippet)

    def test_traceability_matrix_links_req_to_test(self) -> None:
        """REQ-001 链接到由契约校验项合成的 TST-xxx。"""
        entry = next(e for e in self.matrix if e.req_id == "REQ-001")
        self.assertTrue(entry.test_id.startswith("TST-"))
        self.assertIn(entry.test_result, ("通过", "失败"))

    def test_traceability_matrix_to_dict(self) -> None:
        """TraceEntry.to_dict 返回完整字段。"""
        d = self.matrix[0].to_dict()
        for key in (
            "req_id",
            "req_desc",
            "contract_id",
            "code_line",
            "code_snippet",
            "test_id",
            "test_result",
        ):
            self.assertIn(key, d)

    def test_traceability_matrix_handles_missing_fields(self) -> None:
        """pipeline_result 缺失部分字段时仍能构建（不抛异常）。"""
        minimal = {
            "requirement": {"req_id": "REQ-042", "desc": "test"},
            "contract": "traceability: [REQ-042]\n",
            "final_code": "/* [REQ-042] hello */\nint x = 0;\n",
        }
        matrix = build_matrix(minimal)
        self.assertEqual(len(matrix), 1)
        entry = matrix[0]
        self.assertEqual(entry.req_id, "REQ-042")
        self.assertEqual(entry.contract_id, "CON-001")  # 默认
        self.assertGreater(entry.code_line, 0)
        # 无 contract_check_result / simulation_result → test_id 为空
        self.assertEqual(entry.test_id, "")
        self.assertEqual(entry.test_result, "")

    def test_traceability_matrix_handles_structured_reqs(self) -> None:
        """pipeline_result[structured_reqs] 列表也能正确解析。"""
        data = {
            "structured_reqs": [
                {"req_id": "REQ-101", "desc": "需求 A"},
                {"req_id": "REQ-102", "desc": "需求 B"},
            ],
            "contract": "traceability: [REQ-101, REQ-102]\n",
            "final_code": (
                "/* [REQ-101] code A */\n"
                "int a = 0;\n"
                "/* [REQ-102] code B */\n"
                "int b = 0;\n"
            ),
        }
        matrix = build_matrix(data)
        self.assertEqual(len(matrix), 2)
        req_ids = {e.req_id for e in matrix}
        self.assertEqual(req_ids, {"REQ-101", "REQ-102"})


class TestDO178Objectives(unittest.TestCase):
    """DO-178C 目标符合性检查测试。"""

    def setUp(self) -> None:
        self.objectives = check_objectives(SAMPLE_PIPELINE_RESULT)

    def test_do178_objectives_returns_list(self) -> None:
        """check_objectives 返回 list[ObjectiveResult]，至少 10 项。"""
        self.assertIsInstance(self.objectives, list)
        self.assertGreaterEqual(len(self.objectives), 10)

    def test_do178_objectives_has_obj_1_to_obj_10(self) -> None:
        """至少含 OBJ-1 ~ OBJ-10。"""
        obj_ids = {o.obj_id for o in self.objectives}
        for i in range(1, 11):
            self.assertIn(f"OBJ-{i}", obj_ids)

    def test_do178_objectives_status_values(self) -> None:
        """每项目标 status ∈ {满足, 部分满足, 未满足}。"""
        for obj in self.objectives:
            self.assertIn(obj.status, ("满足", "部分满足", "未满足"))
            self.assertIsInstance(obj.name, str)
            self.assertIsInstance(obj.description, str)
            self.assertIsInstance(obj.evidence, str)

    def test_do178_objectives_passes_for_good_pipeline(self) -> None:
        """SAMPLE_PIPELINE_RESULT 是良好流水线产物，应大部分满足。"""
        passed = sum(1 for o in self.objectives if o.status == "满足")
        self.assertGreater(passed, 5, f"应有 >5 项目标满足，实际 {passed}")

    def test_do178_objectives_obj1_traceability(self) -> None:
        """OBJ-1 需求可追溯性检查存在。"""
        obj1 = next(o for o in self.objectives if o.obj_id == "OBJ-1")
        self.assertEqual(obj1.name, "需求可追溯性")
        self.assertIn("追溯矩阵", obj1.evidence)

    def test_do178_objectives_obj3_misra(self) -> None:
        """OBJ-3 源代码合规性：SAMPLE 中 final_violations=[]，应为满足。"""
        obj3 = next(o for o in self.objectives if o.obj_id == "OBJ-3")
        self.assertEqual(obj3.status, "满足")
        self.assertIn("无 MISRA-C 残留违规", obj3.evidence)

    def test_do178_objectives_obj5_simulation(self) -> None:
        """OBJ-5 仿真测试覆盖：SAMPLE 中 total_steps=200，应为满足。"""
        obj5 = next(o for o in self.objectives if o.obj_id == "OBJ-5")
        self.assertEqual(obj5.status, "满足")
        self.assertIn("200", obj5.evidence)

    def test_do178_objectives_to_dict(self) -> None:
        """ObjectiveResult.to_dict 返回完整字段。"""
        d = self.objectives[0].to_dict()
        for key in ("obj_id", "name", "description", "status", "evidence"):
            self.assertIn(key, d)

    def test_do178_objectives_handles_missing_simulation(self) -> None:
        """pipeline_result 缺失 simulation_result 时相关目标为未满足。"""
        data = {
            "requirement": {"req_id": "REQ-001", "desc": "test"},
            "contract": "traceability: [REQ-001]\nversion: 1.0.0\n",
            "final_code": "/* [REQ-001] */\nint x = 0;\n",
            "final_violations": [],
            "cppcheck_result": [],
            "repair_history": [],
        }
        objectives = check_objectives(data)
        obj5 = next(o for o in objectives if o.obj_id == "OBJ-5")
        self.assertEqual(obj5.status, "未满足")
        obj11 = next(o for o in objectives if o.obj_id == "OBJ-11")
        self.assertEqual(obj11.status, "未满足")


class TestReportAPIRoutes(unittest.TestCase):
    """POST /api/report 与 GET /api/report/download 路由测试。

    直接调用路由函数（绕过 HTTP），验证返回结构。
    """

    def test_report_route_returns_html_and_matrix_and_objectives(self) -> None:
        """POST /api/report 返回 report_html / traceability_matrix / do178_objectives。"""
        import asyncio

        from app.api.routes.generate import ReportRequest, report

        req = ReportRequest(pipeline_result=SAMPLE_PIPELINE_RESULT)
        result = asyncio.run(report(req))

        self.assertIn("report_html", result)
        self.assertIn("traceability_matrix", result)
        self.assertIn("do178_objectives", result)

        self.assertIsInstance(result["report_html"], str)
        self.assertGreater(len(result["report_html"]), 1000)
        self.assertIsInstance(result["traceability_matrix"], list)
        self.assertGreater(len(result["traceability_matrix"]), 0)
        self.assertIsInstance(result["do178_objectives"], list)
        self.assertGreaterEqual(len(result["do178_objectives"]), 10)

        # 验证 traceability_matrix 是 dict 列表（已 to_dict）
        first = result["traceability_matrix"][0]
        self.assertIsInstance(first, dict)
        self.assertIn("req_id", first)

    def test_report_download_route_returns_html_response(self) -> None:
        """GET /api/report/download 返回 text/html Response。"""
        import asyncio

        from app.api.routes.generate import report, report_download, ReportRequest

        # 先 POST 一次填充缓存
        asyncio.run(report(ReportRequest(pipeline_result=SAMPLE_PIPELINE_RESULT)))
        # 再 GET download
        response = asyncio.run(report_download())
        self.assertEqual(response.media_type, "text/html; charset=utf-8")
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertIn("do178c_report.html", response.headers["content-disposition"])
        self.assertIsInstance(response.body, (bytes, bytearray, str))
        # body 应该是 HTML
        body_text = (
            response.body.decode("utf-8")
            if isinstance(response.body, (bytes, bytearray))
            else response.body
        )
        self.assertIn("<html", body_text)
        self.assertIn("DO-178C 合规报告", body_text)

    def test_report_download_route_without_cache_returns_hint(self) -> None:
        """无缓存时 GET /api/report/download 返回提示 HTML（不报错）。"""
        import asyncio

        from app.api.routes import generate as gen_mod
        from app.api.routes.generate import report_download

        # 清空缓存
        gen_mod._last_report_html = None
        gen_mod._last_report_cache = None
        response = asyncio.run(report_download())
        self.assertEqual(response.media_type, "text/html; charset=utf-8")
        body_text = (
            response.body.decode("utf-8")
            if isinstance(response.body, (bytes, bytearray))
            else response.body
        )
        self.assertIn("暂无可下载的报告", body_text)


if __name__ == "__main__":
    unittest.main()
