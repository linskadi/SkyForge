"""组件可组合性验证测试（DO-178C 6.5）。

测试覆盖：
- test_compose_sequential：顺序组合（A 输出 → B 输入）
- test_compose_parallel：并行组合（A/B 共享输入）
- test_compose_feedback：反馈组合（B 输出反馈到 A）
- test_compatibility_check_compatible：兼容的契约组合
- test_compatibility_check_incompatible：不兼容的契约（A 输出超出 B 输入范围）
- test_composition_simulation：组合后仿真验证
"""

import unittest

from app.core.composable import (
    check_compatibility,
    compose,
    simulate_composition,
)

# ====================================================================== #
# 测试用 C 代码
# ====================================================================== #

# 组件 A：低通滤波器，输出范围 [0, 100]
FILTER_A_CODE = """\
double filter(double input) {
    static double last = 0.0;
    double out = 0.9 * last + 0.1 * input;
    if (out < 0.0) out = 0.0;
    if (out > 100.0) out = 100.0;
    last = out;
    return out;
}
"""

# 组件 B：另一低通滤波器，输入范围 [0, 200]，输出范围 [0, 200]
FILTER_B_CODE = """\
double filter(double input) {
    static double last = 0.0;
    double out = 0.5 * last + 0.5 * input;
    if (out < 0.0) out = 0.0;
    if (out > 200.0) out = 200.0;
    last = out;
    return out;
}
"""

# ====================================================================== #
# 测试用契约 YAML
# ====================================================================== #

# A 契约：输出范围 [0, 100]（兼容 B 的输入范围 [0, 200]）
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

# B 契约：输入范围 [0, 200]（与 A 的输出 [0, 100] 兼容）
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
    - name: b_output
      type: double
      range: [0, 200]
contracts:
  preconditions:
    - "a_output >= 0"
    - "a_output <= 200"
  postconditions:
    - "b_output >= 0"
    - "b_output <= 200"
  invariants:
    - "sample_rate == 100Hz"
"""

# A 契约（不兼容版）：输出范围 [0, 20000]（超出 B 的输入范围 [0, 100]）
CONTRACT_A_INCOMPAT = """\
component: filter_a_wide
version: 1.0.0
safety_level: DAL-B
traceability: [REQ-A-WIDE]
interface:
  inputs:
    - name: raw_input
      type: double
      range: [0, 20000]
  outputs:
    - name: filtered_output
      type: double
      range: [0, 20000]
contracts:
  preconditions:
    - "raw_input >= 0"
  postconditions:
    - "filtered_output >= 0"
    - "filtered_output <= 20000"
"""

# B 契约（不兼容版）：输入范围 [0, 100]（A 输出 [0, 20000] 超出）
CONTRACT_B_INCOMPAT = """\
component: filter_b_narrow
version: 1.0.0
safety_level: DAL-B
traceability: [REQ-B-NARROW]
interface:
  inputs:
    - name: a_output
      type: double
      range: [0, 100]
  outputs:
    - name: b_output
      type: double
      range: [0, 100]
contracts:
  preconditions:
    - "a_output >= 0"
    - "a_output <= 100"
  postconditions:
    - "b_output >= 0"
    - "b_output <= 100"
"""


class TestComponentCombinator(unittest.TestCase):
    """组件组合器测试。"""

    def test_compose_sequential(self) -> None:
        """顺序组合：A 的输出作为 B 的输入。"""
        result = compose(
            component_a_code=FILTER_A_CODE,
            component_a_contract=CONTRACT_A_COMPAT,
            component_b_code=FILTER_B_CODE,
            component_b_contract=CONTRACT_B_COMPAT,
            connection="sequential",
        )

        # 1) 组合代码应包含重命名后的 filter_a / filter_b
        self.assertIn("double filter_a(", result.composed_code)
        self.assertIn("double filter_b(", result.composed_code)

        # 2) 组合代码应包含单一 filter 入口（wrapper）
        self.assertIn("double filter(double input)", result.composed_code)

        # 3) 顺序组合 wrapper 应调用 filter_a 然后 filter_b
        self.assertIn("filter_a(input)", result.composed_code)
        self.assertIn("filter_b(intermediate)", result.composed_code)

        # 4) 组合代码应包含连接方式注释
        self.assertIn("sequential", result.composed_code)
        self.assertIn("顺序组合", result.composed_code)

        # 5) 组合契约应包含 B 的后置条件（顺序组合 post = B.post）
        self.assertIn("b_output >= 0", result.composed_contract)
        self.assertIn("b_output <= 200", result.composed_contract)

        # 6) 组合契约应包含 A 的前置条件（顺序组合 pre = A.pre）
        self.assertIn("raw_input >= 0", result.composed_contract)

        # 7) 兼容性检查应通过（A 输出 [0, 100] ⊆ B 输入 [0, 200]）
        compat = result.compatibility_check
        self.assertTrue(
            compat["compatible"],
            f"兼容性检查应通过: {compat.get('violations')}",
        )
        self.assertEqual(compat["connection"], "sequential")
        self.assertGreater(len(compat["checked_pairs"]), 0)

        # 8) to_dict 应返回完整字典
        d = result.to_dict()
        self.assertIn("composed_code", d)
        self.assertIn("composed_contract", d)
        self.assertIn("compatibility_check", d)
        self.assertIn("warnings", d)
        self.assertIn("connection", d)

    def test_compose_parallel(self) -> None:
        """并行组合：A 和 B 共享输入，输出取平均。"""
        result = compose(
            component_a_code=FILTER_A_CODE,
            component_a_contract=CONTRACT_A_COMPAT,
            component_b_code=FILTER_B_CODE,
            component_b_contract=CONTRACT_B_COMPAT,
            connection="parallel",
        )

        # 1) 组合代码应包含 filter_a / filter_b / filter
        self.assertIn("double filter_a(", result.composed_code)
        self.assertIn("double filter_b(", result.composed_code)
        self.assertIn("double filter(double input)", result.composed_code)

        # 2) 并行组合 wrapper 应同时调用 filter_a 和 filter_b，输出取平均
        self.assertIn("out_a = filter_a(input)", result.composed_code)
        self.assertIn("out_b = filter_b(input)", result.composed_code)
        self.assertIn("(out_a + out_b) / 2.0", result.composed_code)

        # 3) 组合代码应包含并行注释
        self.assertIn("并行组合", result.composed_code)

        # 4) 并行组合契约应包含 A 和 B 的前置条件
        self.assertIn("raw_input >= 0", result.composed_contract)
        self.assertIn("a_output >= 0", result.composed_contract)

        # 5) 并行组合契约应包含 A 和 B 的后置条件
        self.assertIn("filtered_output <= 100", result.composed_contract)
        self.assertIn("b_output <= 200", result.composed_contract)

        # 6) 连接方式应为 parallel
        self.assertEqual(result.connection, "parallel")
        self.assertEqual(result.compatibility_check["connection"], "parallel")

    def test_compose_feedback(self) -> None:
        """反馈组合：B 的输出反馈到 A。"""
        result = compose(
            component_a_code=FILTER_A_CODE,
            component_a_contract=CONTRACT_A_COMPAT,
            component_b_code=FILTER_B_CODE,
            component_b_contract=CONTRACT_B_COMPAT,
            connection="feedback",
        )

        # 1) 组合代码应包含 filter_a / filter_b / filter
        self.assertIn("double filter_a(", result.composed_code)
        self.assertIn("double filter_b(", result.composed_code)
        self.assertIn("double filter(double input)", result.composed_code)

        # 2) 反馈组合 wrapper 应包含反馈逻辑
        self.assertIn("feedback", result.composed_code.lower())
        self.assertIn("filter_b(a_out)", result.composed_code)
        self.assertIn("filter_a(input + feedback)", result.composed_code)

        # 3) 组合代码应包含反馈注释
        self.assertIn("反馈组合", result.composed_code)

        # 4) 反馈组合契约应包含 A 的前置条件
        self.assertIn("raw_input >= 0", result.composed_contract)

        # 5) 反馈组合契约应包含反馈稳定性约束（额外后置条件）
        self.assertIn("feedback_loop_stable", result.composed_contract)

        # 6) 连接方式应为 feedback
        self.assertEqual(result.connection, "feedback")
        self.assertEqual(result.compatibility_check["connection"], "feedback")

        # 7) 反馈组合应包含稳定性需仿真验证的警告
        self.assertTrue(
            any("仿真" in w for w in result.warnings),
            f"反馈组合应包含仿真验证警告: {result.warnings}",
        )

    def test_compose_invalid_connection_raises(self) -> None:
        """不支持的连接方式应抛 ValueError。"""
        with self.assertRaises(ValueError):
            compose(
                component_a_code=FILTER_A_CODE,
                component_a_contract=CONTRACT_A_COMPAT,
                component_b_code=FILTER_B_CODE,
                component_b_contract=CONTRACT_B_COMPAT,
                connection="unknown",
            )


class TestCompatibilityChecker(unittest.TestCase):
    """契约兼容性检查器测试。"""

    def test_compatibility_check_compatible(self) -> None:
        """兼容的契约组合：A 输出 [0, 100] ⊆ B 输入 [0, 200]。"""
        result = check_compatibility(
            contract_a_yaml=CONTRACT_A_COMPAT,
            contract_b_yaml=CONTRACT_B_COMPAT,
            connection="sequential",
        )

        # 1) 应判定为兼容
        self.assertTrue(
            result.compatible,
            f"兼容的契约应通过: violations={result.violations}",
        )

        # 2) 应有检查对（接口范围检查 + 表达式级检查）
        self.assertGreater(len(result.checked_pairs), 0)

        # 3) 应无违约
        self.assertEqual(len(result.violations), 0)

        # 4) 每个检查对应包含 a_postcondition / b_precondition / satisfied / message
        for pair in result.checked_pairs:
            self.assertIn("a_postcondition", pair)
            self.assertIn("b_precondition", pair)
            self.assertIn("satisfied", pair)
            self.assertIn("message", pair)
            self.assertTrue(pair["satisfied"], f"检查对应通过: {pair}")

        # 5) 连接方式应为 sequential
        self.assertEqual(result.connection, "sequential")

        # 6) to_dict 应返回完整字典
        d = result.to_dict()
        self.assertIn("compatible", d)
        self.assertIn("checked_pairs", d)
        self.assertIn("violations", d)
        self.assertIn("warnings", d)

    def test_compatibility_check_incompatible(self) -> None:
        """不兼容的契约：A 输出 [0, 20000] 超出 B 输入 [0, 100]。"""
        result = check_compatibility(
            contract_a_yaml=CONTRACT_A_INCOMPAT,
            contract_b_yaml=CONTRACT_B_INCOMPAT,
            connection="sequential",
        )

        # 1) 应判定为不兼容
        self.assertFalse(
            result.compatible,
            "A 输出 [0, 20000] 超出 B 输入 [0, 100]，应不兼容",
        )

        # 2) 应有违约项
        self.assertGreater(len(result.violations), 0)

        # 3) 违约项应包含不满足的检查对
        for violation in result.violations:
            self.assertFalse(violation["satisfied"])
            self.assertTrue(
                "20000" in violation["message"]
                or "100" in violation["message"]
                or "超出" in violation["message"],
                f"违约消息应说明范围超出: {violation['message']}",
            )

        # 4) 至少有一个违约涉及接口范围检查（A 输出 20000 > B 输入 100）
        interface_violations = [
            v
            for v in result.violations
            if "A.output" in v["a_postcondition"] or "B.input" in v["b_precondition"]
        ]
        self.assertGreater(
            len(interface_violations),
            0,
            "应包含接口范围检查违约",
        )

    def test_compatibility_check_parallel(self) -> None:
        """并行兼容性检查：A/B 输入范围应有交集。"""
        result = check_compatibility(
            contract_a_yaml=CONTRACT_A_COMPAT,
            contract_b_yaml=CONTRACT_B_COMPAT,
            connection="parallel",
        )
        # A 输入 [0, 20000] ∩ B 输入 [0, 200] = [0, 200] ≠ ∅，应兼容
        self.assertTrue(result.compatible)
        self.assertEqual(result.connection, "parallel")

    def test_compatibility_check_feedback(self) -> None:
        """反馈兼容性检查：B 输出应 ⊆ A 输入。"""
        result = check_compatibility(
            contract_a_yaml=CONTRACT_A_COMPAT,
            contract_b_yaml=CONTRACT_B_COMPAT,
            connection="feedback",
        )
        # B 输出 [0, 200] ⊆ A 输入 [0, 20000]，反馈通路兼容
        self.assertTrue(result.compatible)
        self.assertEqual(result.connection, "feedback")
        # 反馈组合应包含需仿真验证的警告
        self.assertTrue(
            any("仿真" in w for w in result.warnings),
            f"反馈组合应包含仿真警告: {result.warnings}",
        )

    def test_compatibility_check_invalid_connection_raises(self) -> None:
        """不支持的连接方式应抛 ValueError。"""
        with self.assertRaises(ValueError):
            check_compatibility(
                contract_a_yaml=CONTRACT_A_COMPAT,
                contract_b_yaml=CONTRACT_B_COMPAT,
                connection="unknown",
            )

    def test_compatibility_check_invalid_yaml(self) -> None:
        """非法 YAML 应返回不兼容结果。"""
        result = check_compatibility(
            contract_a_yaml="not: valid: yaml: [",
            contract_b_yaml=CONTRACT_B_COMPAT,
            connection="sequential",
        )
        self.assertFalse(result.compatible)
        self.assertGreater(len(result.violations), 0)


class TestCompositionSimulator(unittest.TestCase):
    """组合仿真验证测试。"""

    def test_composition_simulation(self) -> None:
        """组合后仿真：验证 composed_code + composed_contract 能跑通。"""
        # 先组合
        composition = compose(
            component_a_code=FILTER_A_CODE,
            component_a_contract=CONTRACT_A_COMPAT,
            component_b_code=FILTER_B_CODE,
            component_b_contract=CONTRACT_B_COMPAT,
            connection="sequential",
        )

        # 运行组合仿真
        result = simulate_composition(
            composed_code=composition.composed_code,
            composed_contract=composition.composed_contract,
            steps=50,
        )

        # 1) 仿真步数应匹配
        self.assertEqual(result.total_steps, 50)

        # 2) 输出波形长度应等于步数（mock 模式下必为 50；GCC 模式下若契约满足也为 50）
        self.assertEqual(len(result.output_waveform), 50)

        # 3) 应包含契约满足状态字段
        self.assertIn("contract_satisfied", result.to_dict())
        self.assertIn("violation_location", result.to_dict())

        # 4) 终端日志应包含仿真开始/结束标记
        self.assertIn("仿真", result.terminal_log)

        # 5) 统计信息应包含输入/输出范围
        self.assertIn("input_min", result.statistics)
        self.assertIn("duration_ms", result.statistics)

        # 6) simulation_result 字段应包含完整 SimulationResult
        sim_dict = result.simulation_result
        self.assertIn("passed", sim_dict)
        self.assertIn("compilation", sim_dict)

        # 7) to_dict 应返回完整字典
        d = result.to_dict()
        self.assertIn("passed", d)
        self.assertIn("total_steps", d)
        self.assertIn("contract_satisfied", d)
        self.assertIn("violation_location", d)
        self.assertIn("violation_message", d)
        self.assertIn("output_waveform", d)
        self.assertIn("statistics", d)
        self.assertIn("terminal_log", d)
        self.assertIn("simulation_result", d)

    def test_composition_simulation_parallel(self) -> None:
        """并行组合仿真：验证并行组合代码能跑通。"""
        composition = compose(
            component_a_code=FILTER_A_CODE,
            component_a_contract=CONTRACT_A_COMPAT,
            component_b_code=FILTER_B_CODE,
            component_b_contract=CONTRACT_B_COMPAT,
            connection="parallel",
        )
        result = simulate_composition(
            composed_code=composition.composed_code,
            composed_contract=composition.composed_contract,
            steps=30,
        )
        self.assertEqual(result.total_steps, 30)
        self.assertEqual(len(result.output_waveform), 30)


if __name__ == "__main__":
    unittest.main()
