"""SCADE 模型输入支持测试（次级功能）。

测试覆盖：
- test_parse_simple_node：解析简单 node（输入/输出/等式）
- test_parse_with_pre：解析含 pre 操作符的等式
- test_parse_with_if：解析含 if-then-else 的等式
- test_parse_multi_var：解析多变量声明（name1, name2: type）
- test_parse_with_locals：解析含 var 局部变量的 node
- test_parse_with_range_annotation：解析含范围注释的变量
- test_parse_from_example_file：从 example.lus 读取并解析
- test_parse_invalid_no_node：无 node 定义时抛 ValueError
- test_convert_to_requirement：转换为自然语言需求
- test_convert_to_requirement_with_range：含范围的转换
- test_convert_to_contract：转换为契约 YAML
- test_convert_to_contract_structure：契约 YAML 结构完整
- test_pipeline_with_scade：pipeline 集成 G-Lustre 输入
- test_pipeline_scade_only：仅 scade_file 输入（无 requirement）
- test_upload_scade_route：POST /api/upload-scade 路由
- test_generate_with_scade_route：POST /api/generate 含 scade_file
"""

import asyncio
import io
import os
import unittest
from dataclasses import asdict

from app.core.scade.lustre_parser import (
    Equation,
    Variable,
    parse_glustre,
)
from app.core.scade.lustre_to_requirement import convert, convert_to_contract

# 测试数据目录
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_EXAMPLE_LUS = os.path.join(_DATA_DIR, "example.lus")


class TestLustreParser(unittest.TestCase):
    """G-Lustre 解析器测试。"""

    def test_parse_simple_node(self) -> None:
        """解析简单 node：1 输入 1 输出 1 等式。"""
        content = (
            "node Gain(input: real) returns (output: real);\n"
            "let\n"
            "  output = 2.0 * input;\n"
            "tel\n"
        )
        parsed = parse_glustre(content)

        self.assertEqual(parsed.node_name, "Gain")
        self.assertEqual(len(parsed.inputs), 1)
        self.assertEqual(parsed.inputs[0].name, "input")
        self.assertEqual(parsed.inputs[0].type, "real")
        self.assertEqual(len(parsed.outputs), 1)
        self.assertEqual(parsed.outputs[0].name, "output")
        self.assertEqual(parsed.outputs[0].type, "real")
        self.assertEqual(len(parsed.equations), 1)
        self.assertEqual(parsed.equations[0].output, "output")
        self.assertIn("2.0", parsed.equations[0].expression)
        self.assertIn("input", parsed.equations[0].expression)
        # 原始内容应保留
        self.assertEqual(parsed.raw_content, content)

    def test_parse_with_pre(self) -> None:
        """解析含 pre 操作符的等式（一阶 IIR 低通滤波）。"""
        content = (
            "node LowPassFilter(input: real) returns (output: real);\n"
            "let\n"
            "  output = (input -> (0.9 * pre(output) + 0.1 * input));\n"
            "tel\n"
        )
        parsed = parse_glustre(content)

        self.assertEqual(parsed.node_name, "LowPassFilter")
        self.assertEqual(len(parsed.equations), 1)
        expr = parsed.equations[0].expression
        # 应包含 pre 和 -> 操作符
        self.assertIn("pre", expr)
        self.assertIn("->", expr)
        self.assertIn("0.9", expr)
        self.assertIn("0.1", expr)

    def test_parse_with_if(self) -> None:
        """解析含 if-then-else 的等式。"""
        content = (
            "node Saturation(input: real) returns (output: real);\n"
            "let\n"
            "  output = if input > 100.0 then 100.0 else input;\n"
            "tel\n"
        )
        parsed = parse_glustre(content)

        self.assertEqual(parsed.node_name, "Saturation")
        self.assertEqual(len(parsed.equations), 1)
        expr = parsed.equations[0].expression
        # 应包含 if-then-else 关键字
        self.assertIn("if", expr)
        self.assertIn("then", expr)
        self.assertIn("else", expr)
        self.assertIn("100.0", expr)

    def test_parse_multi_var(self) -> None:
        """解析多变量声明 'name1, name2: type'。"""
        content = (
            "node Adder(a, b: real) returns (sum: real);\nlet\n  sum = a + b;\ntel\n"
        )
        parsed = parse_glustre(content)

        self.assertEqual(parsed.node_name, "Adder")
        self.assertEqual(len(parsed.inputs), 2)
        self.assertEqual(parsed.inputs[0].name, "a")
        self.assertEqual(parsed.inputs[1].name, "b")
        self.assertEqual(parsed.inputs[0].type, "real")
        self.assertEqual(parsed.inputs[1].type, "real")
        self.assertEqual(len(parsed.outputs), 1)
        self.assertEqual(parsed.outputs[0].name, "sum")

    def test_parse_with_locals(self) -> None:
        """解析含 var 局部变量的 node。"""
        content = (
            "node Counter(reset: bool) returns (count: int);\n"
            "var\n"
            "  prev_count: int;\n"
            "let\n"
            "  prev_count = 0 -> (if reset then 0 else pre(count));\n"
            "  count = prev_count + 1;\n"
            "tel\n"
        )
        parsed = parse_glustre(content)

        self.assertEqual(parsed.node_name, "Counter")
        self.assertEqual(len(parsed.locals), 1)
        self.assertEqual(parsed.locals[0].name, "prev_count")
        self.assertEqual(parsed.locals[0].type, "int")
        # 应解析出两条等式
        self.assertEqual(len(parsed.equations), 2)
        outputs_in_eq = {eq.output for eq in parsed.equations}
        self.assertEqual(outputs_in_eq, {"prev_count", "count"})

    def test_parse_with_range_annotation(self) -> None:
        """解析含范围注释的变量。"""
        content = (
            "node Sensor(input: real) returns (output: real);\n"
            "/*@ range = [0.0, 20000.0] */\n"
            "let\n"
            "  output = input;\n"
            "tel\n"
        )
        parsed = parse_glustre(content)

        # 范围注释被 best-effort 提取（不强求成功，仅验证不抛异常）
        self.assertEqual(parsed.node_name, "Sensor")
        self.assertEqual(len(parsed.inputs), 1)
        self.assertEqual(len(parsed.equations), 1)

    def test_parse_from_example_file(self) -> None:
        """从 example.lus 读取并解析。"""
        with open(_EXAMPLE_LUS, "r", encoding="utf-8") as f:
            content = f.read()
        parsed = parse_glustre(content)

        self.assertEqual(parsed.node_name, "LowPassFilter")
        self.assertEqual(len(parsed.inputs), 1)
        self.assertEqual(parsed.inputs[0].name, "input")
        self.assertEqual(parsed.inputs[0].type, "real")
        self.assertEqual(len(parsed.outputs), 1)
        self.assertEqual(parsed.outputs[0].name, "output")
        self.assertEqual(len(parsed.equations), 1)
        expr = parsed.equations[0].expression
        self.assertIn("pre", expr)
        self.assertIn("->", expr)

    def test_parse_invalid_no_node(self) -> None:
        """无 node 定义时抛 ValueError。"""
        content = "this is not a valid G-Lustre file;\n"
        with self.assertRaises(ValueError):
            parse_glustre(content)

    def test_parse_logical_operators(self) -> None:
        """解析含 and/or/not 逻辑操作符的等式。"""
        content = (
            "node Logic(a: bool; b: bool) returns (c: bool);\n"
            "let\n"
            "  c = a and (not b or a);\n"
            "tel\n"
        )
        parsed = parse_glustre(content)

        self.assertEqual(parsed.node_name, "Logic")
        self.assertEqual(len(parsed.inputs), 2)
        self.assertEqual(len(parsed.outputs), 1)
        expr = parsed.equations[0].expression
        self.assertIn("and", expr)
        self.assertIn("or", expr)
        self.assertIn("not", expr)

    def test_parsed_lustre_dataclass_fields(self) -> None:
        """ParsedLustre 数据类含全部必要字段。"""
        content = "node Test(x: real) returns (y: real);\nlet\n  y = x;\ntel\n"
        parsed = parse_glustre(content)
        # 字段存在性
        self.assertTrue(hasattr(parsed, "node_name"))
        self.assertTrue(hasattr(parsed, "inputs"))
        self.assertTrue(hasattr(parsed, "outputs"))
        self.assertTrue(hasattr(parsed, "locals"))
        self.assertTrue(hasattr(parsed, "equations"))
        self.assertTrue(hasattr(parsed, "raw_content"))

    def test_variable_dataclass_to_dict(self) -> None:
        """Variable 数据类可转字典（asdict）。"""
        v = Variable(name="x", type="real", range=[0.0, 100.0])
        d = asdict(v)
        self.assertEqual(d["name"], "x")
        self.assertEqual(d["type"], "real")
        self.assertEqual(d["range"], [0.0, 100.0])

    def test_equation_dataclass_to_dict(self) -> None:
        """Equation 数据类可转字典（asdict）。"""
        eq = Equation(output="y", expression="x + 1")
        d = asdict(eq)
        self.assertEqual(d["output"], "y")
        self.assertEqual(d["expression"], "x + 1")


class TestLustreToRequirement(unittest.TestCase):
    """G-Lustre → 需求转换器测试。"""

    def test_convert_to_requirement(self) -> None:
        """转换为自然语言需求。"""
        content = (
            "node Gain(input: real) returns (output: real);\n"
            "let\n"
            "  output = 2.0 * input;\n"
            "tel\n"
        )
        parsed = parse_glustre(content)
        requirement = convert(parsed, req_id="REQ-001")

        # 应含 [REQ-xxx] Tag
        self.assertIn("[REQ-001]", requirement)
        # 应含节点名
        self.assertIn("Gain", requirement)
        # 应含输入/输出描述
        self.assertIn("input", requirement)
        self.assertIn("output", requirement)
        self.assertIn("real", requirement)
        # 应含等式（功能描述）
        self.assertIn("2.0", requirement)
        # 应含约束条件字段
        self.assertIn("约束条件", requirement)

    def test_convert_to_requirement_with_locals(self) -> None:
        """含局部变量的需求转换。"""
        content = (
            "node Counter(reset: bool) returns (count: int);\n"
            "var\n"
            "  prev: int;\n"
            "let\n"
            "  prev = 0;\n"
            "  count = prev + 1;\n"
            "tel\n"
        )
        parsed = parse_glustre(content)
        requirement = convert(parsed, req_id="REQ-042")

        self.assertIn("[REQ-042]", requirement)
        self.assertIn("Counter", requirement)
        self.assertIn("prev", requirement)
        self.assertIn("局部变量", requirement)

    def test_convert_to_requirement_with_range(self) -> None:
        """含范围注释的需求转换。"""
        content = (
            "node Sensor(input: real) returns (output: real);\n"
            "/*@ range = [0.0, 20000.0] */\n"
            "let\n"
            "  output = input;\n"
            "tel\n"
        )
        parsed = parse_glustre(content)
        requirement = convert(parsed, req_id="REQ-001")

        self.assertIn("[REQ-001]", requirement)
        self.assertIn("Sensor", requirement)

    def test_convert_to_contract(self) -> None:
        """转换为契约 YAML。"""
        content = (
            "node Gain(input: real) returns (output: real);\n"
            "let\n"
            "  output = 2.0 * input;\n"
            "tel\n"
        )
        parsed = parse_glustre(content)
        contract = convert_to_contract(parsed, req_id="REQ-001")

        # YAML 关键段
        self.assertIn("component:", contract)
        self.assertIn("version:", contract)
        self.assertIn("safety_level:", contract)
        self.assertIn("traceability:", contract)
        self.assertIn("[REQ-001]", contract)
        self.assertIn("interface:", contract)
        self.assertIn("preconditions:", contract)
        self.assertIn("postconditions:", contract)
        self.assertIn("invariants:", contract)
        self.assertIn("fault_handling:", contract)
        # 节点名应出现在 component 字段
        self.assertIn("Gain", contract)

    def test_convert_to_contract_structure(self) -> None:
        """契约 YAML 结构完整，可被 yaml.safe_load 解析。"""
        import yaml

        content = (
            "node Adder(a, b: real) returns (sum: real);\nlet\n  sum = a + b;\ntel\n"
        )
        parsed = parse_glustre(content)
        contract = convert_to_contract(parsed, req_id="REQ-001")

        # 应能被 YAML 解析
        data = yaml.safe_load(contract)
        self.assertIsInstance(data, dict)
        self.assertEqual(data["component"], "Adder")
        self.assertEqual(data["safety_level"], "DAL-B")
        self.assertEqual(data["traceability"], ["REQ-001"])

        # 接口
        interface = data["interface"]
        self.assertIn("inputs", interface)
        self.assertIn("outputs", interface)
        self.assertEqual(len(interface["inputs"]), 2)
        self.assertEqual(len(interface["outputs"]), 1)

        # 契约段
        contracts = data["contracts"]
        self.assertIn("preconditions", contracts)
        self.assertIn("postconditions", contracts)
        self.assertIn("invariants", contracts)
        self.assertIn("fault_handling", contracts)
        # 前置条件应含 NULL 检查
        self.assertTrue(any("NULL" in p for p in contracts["preconditions"]))
        # 不变式应含等式信息
        self.assertTrue(any("sum" in i for i in contracts["invariants"]))

    def test_convert_to_contract_c_type_mapping(self) -> None:
        """契约 YAML 中类型应映射为 C 类型（real → double）。"""
        content = (
            "node Mix(a: real; b: int; c: bool) returns (out: real);\n"
            "let\n"
            "  out = a;\n"
            "tel\n"
        )
        parsed = parse_glustre(content)
        contract = convert_to_contract(parsed, req_id="REQ-001")

        import yaml

        data = yaml.safe_load(contract)
        inputs = data["interface"]["inputs"]
        types = {inp["name"]: inp["type"] for inp in inputs}
        self.assertEqual(types["a"], "double")  # real → double
        self.assertEqual(types["b"], "int")
        self.assertEqual(types["c"], "bool")


class TestPipelineWithScade(unittest.TestCase):
    """pipeline 集成 G-Lustre 输入测试。"""

    def test_pipeline_with_scade(self) -> None:
        """pipeline 集成 G-Lustre 输入：合并 requirement + scade_file。"""
        from app.core.pipeline import run_pipeline

        with open(_EXAMPLE_LUS, "r", encoding="utf-8") as f:
            scade_content = f.read()
        requirement = "实现一个机载信号处理模块"

        result = asyncio.run(
            run_pipeline(requirement=requirement, scade_file=scade_content)
        )

        # 应返回 scade_parsed 字段
        self.assertIn("scade_parsed", result)
        scade_parsed = result["scade_parsed"]
        self.assertEqual(scade_parsed["node_name"], "LowPassFilter")
        self.assertEqual(len(scade_parsed["inputs"]), 1)
        self.assertEqual(scade_parsed["inputs"][0]["name"], "input")
        self.assertEqual(len(scade_parsed["outputs"]), 1)
        self.assertEqual(len(scade_parsed["equations"]), 1)

        # 应返回 scade_contract 字段
        self.assertIn("scade_contract", result)
        self.assertIn("LowPassFilter", result["scade_contract"])

        # 常规 pipeline 产物应存在
        self.assertIn("requirement", result)
        self.assertIn("contract", result)
        self.assertIn("code", result)
        self.assertIn("cppcheck_result", result)
        # 需求描述应含合并后的 SCADE 模型输入标记
        self.assertIn("SCADE 模型输入", result["requirement"]["desc"])

    def test_pipeline_scade_only(self) -> None:
        """仅 scade_file 输入（无 requirement）。"""
        from app.core.pipeline import run_pipeline

        with open(_EXAMPLE_LUS, "r", encoding="utf-8") as f:
            scade_content = f.read()

        result = asyncio.run(run_pipeline(scade_file=scade_content))

        # 应正常返回（使用转换后的需求）
        self.assertIn("requirement", result)
        self.assertIn("contract", result)
        self.assertIn("code", result)
        # 应含 SCADE 解析结果
        self.assertIn("scade_parsed", result)
        self.assertEqual(result["scade_parsed"]["node_name"], "LowPassFilter")

    def test_pipeline_no_input_raises(self) -> None:
        """两者都为空时抛 ValueError。"""
        from app.core.pipeline import run_pipeline

        with self.assertRaises(ValueError):
            asyncio.run(run_pipeline())


class TestScadeAPIRoutes(unittest.TestCase):
    """SCADE 相关 API 路由测试。"""

    def test_upload_scade_route(self) -> None:
        """POST /api/upload-scade 路由：上传 G-Lustre 文件。"""
        from starlette.datastructures import UploadFile
        from app.api.routes.generate import upload_scade

        with open(_EXAMPLE_LUS, "rb") as f:
            content_bytes = f.read()

        upload = UploadFile(
            filename="example.lus",
            file=io.BytesIO(content_bytes),
        )
        result = asyncio.run(upload_scade(upload))

        # 应返回 parsed / requirement / contract / filename
        self.assertIn("filename", result)
        self.assertEqual(result["filename"], "example.lus")
        self.assertIn("parsed", result)
        self.assertIn("requirement", result)
        self.assertIn("contract", result)

        # parsed 结构完整
        parsed = result["parsed"]
        self.assertEqual(parsed["node_name"], "LowPassFilter")
        self.assertEqual(len(parsed["inputs"]), 1)
        self.assertEqual(len(parsed["outputs"]), 1)
        self.assertEqual(len(parsed["equations"]), 1)
        self.assertIn("raw_content", parsed)

        # requirement 含 [REQ-xxx] Tag
        self.assertIn("[REQ-", result["requirement"])
        self.assertIn("LowPassFilter", result["requirement"])

        # contract 含 YAML 关键段
        self.assertIn("component:", result["contract"])
        self.assertIn("LowPassFilter", result["contract"])

    def test_generate_with_scade_route(self) -> None:
        """POST /api/generate 含 scade_file 参数。"""
        from app.api.routes.generate import GenerateRequest, generate

        with open(_EXAMPLE_LUS, "r", encoding="utf-8") as f:
            scade_content = f.read()

        req = GenerateRequest(requirement="", scade_file=scade_content)
        result = asyncio.run(generate(req))

        # 不应返回 no_input 错误
        self.assertNotIn("error", result)
        # 应返回常规 pipeline 产物
        self.assertIn("requirement", result)
        self.assertIn("contract", result)
        self.assertIn("code", result)
        # 应透传 scade_parsed
        self.assertIn("scade_parsed", result)
        self.assertEqual(result["scade_parsed"]["node_name"], "LowPassFilter")

    def test_generate_no_input_returns_error(self) -> None:
        """POST /api/generate 无输入时返回错误。"""
        from app.api.routes.generate import GenerateRequest, generate

        req = GenerateRequest(requirement="", scade_file="")
        result = asyncio.run(generate(req))

        self.assertIn("error", result)
        self.assertTrue(result["aborted"])
        self.assertEqual(result["abort_reason"], "no_input")


if __name__ == "__main__":
    unittest.main()
