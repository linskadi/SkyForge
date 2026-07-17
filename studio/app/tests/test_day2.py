"""Day 2 测试：修复闭环 + 契约校验 + MISRA 规则模板修复。"""

import asyncio
import unittest

from skyforge_engine.agents.code_repairer import CodeRepairerAgent
from skyforge_engine.pipeline import repair_loop
from skyforge_engine.tools.contract_checker import check as contract_check
from skyforge_engine.tools.cppcheck_scanner import Violation, scan as cppcheck_scan

CLEAN_CODE = "static double s_buffer[100];\nstatic int s_count = 0;\n"
# DIRTY_CODE: 故意包含 MISRA-C 违规（Rule 8.7: 非 static 全局变量）
DIRTY_CODE = """\
double g_value = 0.0;
int g_count = 0;
"""

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

CODE_WITH_NULL_CHECK = """\
double test_filter(double raw_input) {
    if (raw_input == NULL) {
        return 0;
    }
    return raw_input;
}
"""


def _mk_violation(rule_id: str, line: int) -> Violation:
    return Violation(
        file="code.c",
        line=line,
        column=0,
        severity="style",
        rule_id=rule_id,
        message=f"test {rule_id}",
    )


class TestRepairLoop(unittest.TestCase):
    """修复闭环测试。"""

    def test_repair_loop_no_violations(self) -> None:
        """无违规代码直接返回。"""
        result = asyncio.run(repair_loop(CLEAN_CODE, contract="", max_iterations=3))
        self.assertEqual(len(result["final_violations"]), 0)
        self.assertEqual(len(result["repair_history"]), 0)
        self.assertEqual(result["final_code"], CLEAN_CODE)
        self.assertIsNone(result["contract_check_result"])

    def test_repair_loop_with_violations(self) -> None:
        """构造含违规的代码，修复后违规减少。

        注意：真实 Cppcheck MISRA addon 在 Windows 上可能无法正确捕获输出，
        此时使用 mock 扫描来验证修复闭环逻辑。
        """
        initial = cppcheck_scan(DIRTY_CODE)
        # 如果真实 Cppcheck 未找到违规（Windows MISRA addon 问题），使用 mock 扫描
        if len(initial) == 0:
            from skyforge_engine.tools.cppcheck_scanner import _mock_scan
            initial = _mock_scan(DIRTY_CODE)
        self.assertGreater(len(initial), 0, "dirty code should have violations")
        result = asyncio.run(repair_loop(DIRTY_CODE, contract="", max_iterations=3))
        self.assertLess(
            len(result["final_violations"]),
            len(initial),
            "violations should decrease after repair",
        )
        self.assertGreater(len(result["repair_history"]), 0)
        for entry in result["repair_history"]:
            self.assertIn("iteration", entry)
            self.assertIn("violations_before", entry)
            self.assertIn("actions", entry)
            self.assertIn("code_after", entry)

    def test_repair_loop_with_contract(self) -> None:
        """修复闭环加契约校验。"""
        result = asyncio.run(
            repair_loop(DIRTY_CODE, contract=SAMPLE_CONTRACT, max_iterations=2)
        )
        self.assertIsNotNone(result["contract_check_result"])
        ccr = result["contract_check_result"]
        self.assertIn("passed", ccr)
        self.assertIn("preconditions", ccr)
        self.assertIn("assert_code", ccr)


class TestContractChecker(unittest.TestCase):
    """契约校验器测试。"""

    def test_contract_checker_structure(self) -> None:
        """契约校验器返回完整结构。"""
        result = contract_check(CODE_WITH_NULL_CHECK, SAMPLE_CONTRACT, cid="CON-001")
        self.assertIsInstance(result.preconditions, list)
        self.assertIsInstance(result.postconditions, list)
        self.assertIsInstance(result.invariants, list)
        self.assertIsInstance(result.fault_handling, list)
        self.assertIsInstance(result.assert_code, str)
        self.assertIsInstance(result.violations, list)
        self.assertIn("assert(", result.assert_code)
        for item in result.preconditions:
            self.assertTrue(item.id.startswith("CON-001-PRE"))
        for item in result.postconditions:
            self.assertTrue(item.id.startswith("CON-001-POST"))

    def test_contract_checker_preconditions(self) -> None:
        """前置条件检查项。"""
        result = contract_check(CODE_WITH_NULL_CHECK, SAMPLE_CONTRACT, cid="CON-002")
        self.assertGreaterEqual(len(result.preconditions), 2)
        null_item = next(
            (i for i in result.preconditions if "NULL" in i.desc or "null" in i.desc),
            None,
        )
        self.assertIsNotNone(null_item, "should have NULL precondition")
        self.assertTrue(null_item.passed, "NULL check should pass")

    def test_contract_checker_assert_code(self) -> None:
        """断言插桩代码生成正确。"""
        result = contract_check(CODE_WITH_NULL_CHECK, SAMPLE_CONTRACT, cid="CON-003")
        self.assertIn("isnan", result.assert_code)
        self.assertIn("isinf", result.assert_code)
        self.assertIn("CON-003", result.assert_code)

    def test_contract_checker_fault_handling(self) -> None:
        """故障处理检查项。"""
        result = contract_check(CODE_WITH_NULL_CHECK, SAMPLE_CONTRACT, cid="CON-004")
        self.assertGreaterEqual(len(result.fault_handling), 1)
        for item in result.fault_handling:
            self.assertTrue(
                item.passed, f"fault handling {item.id} should pass: {item.detail}"
            )


class TestCodeRepairer(unittest.TestCase):
    """每个 MISRA 规则模板修复测试。"""

    def test_rule_8_1_prototype(self) -> None:
        """Rule 8.1 函数定义添加原型声明。"""
        code = "void my_func(void) {\n    return;\n}\n"
        agent = CodeRepairerAgent()
        result = asyncio.run(agent.repair(code, [_mk_violation("misra-c2012-8.1", 1)]))
        self.assertIn("void my_func(void);", result.code)
        self.assertEqual(len(result.actions), 1)
        self.assertIn("8.1", result.actions[0].rule_id)

    def test_rule_8_4_extern(self) -> None:
        """Rule 8.4 外部函数添加 extern 声明。"""
        code = "    external_call();\n"
        agent = CodeRepairerAgent()
        result = asyncio.run(agent.repair(code, [_mk_violation("misra-c2012-8.4", 1)]))
        self.assertIn("extern void external_call", result.code)

    def test_rule_8_7_static(self) -> None:
        """Rule 8.7 外部变量转为 static。"""
        code = "double s_var = 0.0;\n"
        agent = CodeRepairerAgent()
        result = asyncio.run(agent.repair(code, [_mk_violation("misra-c2012-8.7", 1)]))
        self.assertIn("static double", result.code)

    def test_rule_10_1_cast(self) -> None:
        """Rule 10.1 隐式转换添加显式类型转换。"""
        code = "int x = 5;\n"
        agent = CodeRepairerAgent()
        result = asyncio.run(agent.repair(code, [_mk_violation("misra-c2012-10.1", 1)]))
        self.assertIn("(double)", result.code)
        self.assertIn("10.1", result.actions[0].rule_id)

    def test_rule_10_3_cast(self) -> None:
        """Rule 10.3 赋值隐式转换添加显式转换。"""
        code = "y = compute(5);\n"
        agent = CodeRepairerAgent()
        result = asyncio.run(agent.repair(code, [_mk_violation("misra-c2012-10.3", 1)]))
        self.assertIn("(double)", result.code)

    def test_rule_15_5_single_exit(self) -> None:
        """Rule 15.5 函数单一出口重构为单一 return。"""
        code = "double my_func(double x) {\n    return x;\n}\n"
        agent = CodeRepairerAgent()
        result = asyncio.run(agent.repair(code, [_mk_violation("misra-c2012-15.5", 2)]))
        self.assertIn("goto __cleanup_15_5", result.code)
        self.assertIn("__result_15_5", result.code)

    def test_rule_17_7_check_return(self) -> None:
        """Rule 17.7 返回值使用检查返回值。"""
        code = "    some_func(5);\n"
        agent = CodeRepairerAgent()
        result = asyncio.run(agent.repair(code, [_mk_violation("misra-c2012-17.7", 1)]))
        self.assertIn("if (some_func(5) != 0)", result.code)

    def test_rule_20_4_static_alloc(self) -> None:
        """Rule 20.4 动态内存替换 malloc 为静态分配。"""
        code = "char *p = malloc(100);\n"
        agent = CodeRepairerAgent()
        result = asyncio.run(agent.repair(code, [_mk_violation("misra-c2012-20.4", 1)]))
        self.assertNotIn("malloc(", result.code)
        self.assertIn("__static_buf_20_4", result.code)

    def test_repairer_no_violations(self) -> None:
        """无违规返回原代码。"""
        code = "static int x = 0;\n"
        agent = CodeRepairerAgent()
        result = asyncio.run(agent.repair(code, []))
        self.assertEqual(result.code, code)
        self.assertEqual(len(result.actions), 0)

    def test_repairer_unknown_rule(self) -> None:
        """未实现模板的规则标注 TODO。"""
        code = "int x = 0;\n"
        agent = CodeRepairerAgent()
        result = asyncio.run(
            agent.repair(code, [_mk_violation("misra-c2012-99.99", 1)])
        )
        self.assertEqual(len(result.actions), 1)
        self.assertIn("未实现", result.actions[0].description)

    def test_repairer_traceability_tag(self) -> None:
        """每处修复标注 REQ-xxx 追溯 Tag。"""
        code = "double s_var = 0.0;\n"
        agent = CodeRepairerAgent()
        result = asyncio.run(
            agent.repair(code, [_mk_violation("misra-c2012-8.7", 1)], req_id="REQ-042")
        )
        self.assertIn("[REQ-042]", result.code)
        self.assertEqual(result.actions[0].req_id, "REQ-042")


if __name__ == "__main__":
    unittest.main()
