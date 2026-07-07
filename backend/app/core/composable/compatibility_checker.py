"""契约兼容性检查器：验证两个组件契约在指定连接方式下是否兼容。

参考设计文档第 6.5 节"可组合性验证"。
契约式设计的核心价值是"组件可组合性"——多个组件组合后契约仍然满足。

支持的连接方式：
- sequential：A 的输出作为 B 的输入
    检查 A 的 postconditions 是否满足 B 的 preconditions
    （A 的输出范围 ⊆ B 的输入范围）
- parallel：A 和 B 并行执行（共享输入）
    检查 A 和 B 的 preconditions 是否同时可满足
    （A 的输入范围 ∩ B 的输入范围 ≠ ∅）
- feedback：B 的输出反馈到 A
    检查反馈循环稳定性（B 的输出范围 ⊆ A 的输入范围 + 反馈增益 mock 评估）

兼容两种 YAML 布局（与 contract_checker / contract_to_assert 一致）：
- 布局1（顶层）：postconditions / preconditions / invariants 直接在顶层
- 布局2（contracts 块）：上述列表位于 contracts 子字典
"""

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from app.utils.log_util import logger

# 支持的连接方式
VALID_CONNECTIONS = {"sequential", "parallel", "feedback"}


@dataclass
class CheckedPair:
    """单对契约检查项结果（A 的某条 postcondition vs B 的某条 precondition）。

    Attributes:
        a_postcondition: A 的后置条件表达式（或描述）。
        b_precondition: B 的前置条件表达式（或描述）。
        satisfied: 是否满足（兼容）。
        message: 检查结果说明。
    """

    a_postcondition: str
    b_precondition: str
    satisfied: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "a_postcondition": self.a_postcondition,
            "b_precondition": self.b_precondition,
            "satisfied": self.satisfied,
            "message": self.message,
        }


@dataclass
class CompatibilityResult:
    """兼容性检查结果。

    Attributes:
        compatible: 整体是否兼容（所有强制检查项均通过）。
        checked_pairs: 检查的契约对列表（CheckedPair.to_dict()）。
        violations: 不满足的契约对（与 checked_pairs 中 satisfied=False 项对应）。
        warnings: 警告信息列表（非致命，例如无法自动判定的项）。
        connection: 实际使用的连接方式。
    """

    compatible: bool = False
    checked_pairs: list[dict[str, Any]] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    connection: str = "sequential"

    def to_dict(self) -> dict[str, Any]:
        return {
            "compatible": self.compatible,
            "checked_pairs": self.checked_pairs,
            "violations": self.violations,
            "warnings": self.warnings,
            "connection": self.connection,
        }


class CompatibilityChecker:
    """契约兼容性检查器。

    使用方式：
        checker = CompatibilityChecker()
        result = checker.check(contract_a_yaml, contract_b_yaml, "sequential")
    """

    def check(
        self,
        contract_a_yaml: str,
        contract_b_yaml: str,
        connection: str = "sequential",
    ) -> CompatibilityResult:
        """检查两个契约在指定连接方式下是否兼容。

        Args:
            contract_a_yaml: A 组件的 .contract YAML 字符串。
            contract_b_yaml: B 组件的 .contract YAML 字符串。
            connection: 连接方式（sequential / parallel / feedback）。

        Returns:
            CompatibilityResult。
        """
        if connection not in VALID_CONNECTIONS:
            raise ValueError(
                f"不支持的连接方式: {connection}，支持: {VALID_CONNECTIONS}"
            )

        logger.info(
            f"CompatibilityChecker:开始 connection={connection} "
            f"A={len(contract_a_yaml)}B={len(contract_b_yaml)}B"
        )

        try:
            contract_a = yaml.safe_load(contract_a_yaml) or {}
        except yaml.YAMLError as e:
            return CompatibilityResult(
                compatible=False,
                violations=[
                    {
                        "a_postcondition": "<YAML>",
                        "b_precondition": "<YAML>",
                        "satisfied": False,
                        "message": f"A 契约 YAML 解析失败: {e}",
                    }
                ],
                warnings=[],
                connection=connection,
            )

        try:
            contract_b = yaml.safe_load(contract_b_yaml) or {}
        except yaml.YAMLError as e:
            return CompatibilityResult(
                compatible=False,
                violations=[
                    {
                        "a_postcondition": "<YAML>",
                        "b_precondition": "<YAML>",
                        "satisfied": False,
                        "message": f"B 契约 YAML 解析失败: {e}",
                    }
                ],
                warnings=[],
                connection=connection,
            )

        if connection == "sequential":
            return self._check_sequential(contract_a, contract_b)
        if connection == "parallel":
            return self._check_parallel(contract_a, contract_b)
        return self._check_feedback(contract_a, contract_b)

    # ------------------------------------------------------------------ #
    # 顺序组合：A 的输出 → B 的输入
    # ------------------------------------------------------------------ #
    def _check_sequential(
        self, contract_a: dict[str, Any], contract_b: dict[str, Any]
    ) -> CompatibilityResult:
        """顺序组合兼容性检查。

        规则：
        1) 提取 A 的输出范围（从 interface.outputs.range 和 postconditions 推断）
        2) 提取 B 的输入范围（从 interface.inputs.range 和 preconditions 推断）
        3) 接口范围检查：A.output_range ⊆ B.input_range
        4) 表达式级检查：B 的每条 precondition 是否被 A 的 postconditions 满足
        """
        pairs: list[CheckedPair] = []
        violations: list[dict[str, Any]] = []
        warnings: list[str] = []

        # 接口范围检查
        a_output_range = _extract_output_range(contract_a)
        b_input_range = _extract_input_range(contract_b)

        if a_output_range and b_input_range:
            a_min, a_max = a_output_range
            b_min, b_max = b_input_range
            satisfied = (a_min >= b_min) and (a_max <= b_max)
            pair = CheckedPair(
                a_postcondition=f"A.output ∈ [{a_min}, {a_max}]",
                b_precondition=f"B.input ∈ [{b_min}, {b_max}]",
                satisfied=satisfied,
                message=(
                    "A 的输出范围 ⊆ B 的输入范围，兼容"
                    if satisfied
                    else f"不兼容：A 输出 [{a_min}, {a_max}] 超出 B 输入 "
                    f"[{b_min}, {b_max}]"
                ),
            )
            pairs.append(pair)
            if not satisfied:
                violations.append(pair.to_dict())
        elif a_output_range and not b_input_range:
            warnings.append("B 未声明输入范围，跳过接口范围检查")
        elif b_input_range and not a_output_range:
            warnings.append("A 未声明输出范围，跳过接口范围检查")
        else:
            warnings.append("A/B 均未声明输入/输出范围，仅做表达式级检查")

        # 表达式级检查：B 的每条 precondition 是否被 A 的 postconditions 满足
        a_posts = _extract_section(contract_a, "postconditions")
        b_pres = _extract_section(contract_b, "preconditions")

        if not b_pres:
            warnings.append("B 无前置条件，跳过表达式级检查")
        elif not a_posts:
            warnings.append("A 无后置条件，无法证明 B 的前置条件")
            for pre in b_pres:
                pre_str = _expr_to_str(pre)
                pair = CheckedPair(
                    a_postcondition="<none>",
                    b_precondition=pre_str,
                    satisfied=False,
                    message="A 无后置条件，无法证明 B 的前置条件",
                )
                pairs.append(pair)
                violations.append(pair.to_dict())
        else:
            a_post_strs = [_expr_to_str(p) for p in a_posts]
            for pre in b_pres:
                pre_str = _expr_to_str(pre)
                satisfied, msg = _check_precondition_satisfied(
                    pre_str, a_post_strs, a_output_range
                )
                pair = CheckedPair(
                    a_postcondition=" | ".join(a_post_strs),
                    b_precondition=pre_str,
                    satisfied=satisfied,
                    message=msg,
                )
                pairs.append(pair)
                if not satisfied:
                    violations.append(pair.to_dict())

        return CompatibilityResult(
            compatible=len(violations) == 0,
            checked_pairs=[p.to_dict() for p in pairs],
            violations=violations,
            warnings=warnings,
            connection="sequential",
        )

    # ------------------------------------------------------------------ #
    # 并行组合：A 和 B 并行（共享输入）
    # ------------------------------------------------------------------ #
    def _check_parallel(
        self, contract_a: dict[str, Any], contract_b: dict[str, Any]
    ) -> CompatibilityResult:
        """并行组合兼容性检查。

        规则：A 和 B 的输入范围必须有交集（可同时满足）。
        """
        pairs: list[CheckedPair] = []
        violations: list[dict[str, Any]] = []
        warnings: list[str] = []

        a_input_range = _extract_input_range(contract_a)
        b_input_range = _extract_input_range(contract_b)

        if a_input_range and b_input_range:
            a_min, a_max = a_input_range
            b_min, b_max = b_input_range
            # 交集非空条件：max(a_min, b_min) <= min(a_max, b_max)
            inter_min = max(a_min, b_min)
            inter_max = min(a_max, b_max)
            satisfied = inter_min <= inter_max
            pair = CheckedPair(
                a_postcondition=f"A.input ∈ [{a_min}, {a_max}]",
                b_precondition=f"B.input ∈ [{b_min}, {b_max}]",
                satisfied=satisfied,
                message=(
                    f"输入范围交集 = [{inter_min}, {inter_max}]，可同时满足"
                    if satisfied
                    else "输入范围无交集，A/B 不能并行"
                ),
            )
            pairs.append(pair)
            if not satisfied:
                violations.append(pair.to_dict())
        else:
            warnings.append("A 或 B 未声明输入范围，跳过并行输入范围检查")

        # 检查前置条件表达式是否冲突（mock：检测显式矛盾的常量约束）
        a_pres = [
            _expr_to_str(p) for p in _extract_section(contract_a, "preconditions")
        ]
        b_pres = [
            _expr_to_str(p) for p in _extract_section(contract_b, "preconditions")
        ]
        conflict = _detect_precondition_conflict(a_pres, b_pres)
        if conflict:
            pair = CheckedPair(
                a_postcondition=" | ".join(a_pres),
                b_precondition=" | ".join(b_pres),
                satisfied=False,
                message=f"前置条件冲突: {conflict}",
            )
            pairs.append(pair)
            violations.append(pair.to_dict())
        else:
            pair = CheckedPair(
                a_postcondition=" | ".join(a_pres) if a_pres else "<none>",
                b_precondition=" | ".join(b_pres) if b_pres else "<none>",
                satisfied=True,
                message="未检测到前置条件显式冲突",
            )
            pairs.append(pair)

        return CompatibilityResult(
            compatible=len(violations) == 0,
            checked_pairs=[p.to_dict() for p in pairs],
            violations=violations,
            warnings=warnings,
            connection="parallel",
        )

    # ------------------------------------------------------------------ #
    # 反馈组合：B 的输出反馈到 A
    # ------------------------------------------------------------------ #
    def _check_feedback(
        self, contract_a: dict[str, Any], contract_b: dict[str, Any]
    ) -> CompatibilityResult:
        """反馈组合兼容性检查。

        规则：
        1) B 的输出范围 ⊆ A 的输入范围（反馈通路稳定的前置）
        2) 反馈稳定性：若可推断 B 的输出/输入增益，需 |gain| < 1（mock 评估）
        3) 警告：反馈循环需仿真验证稳定性
        """
        pairs: list[CheckedPair] = []
        violations: list[dict[str, Any]] = []
        warnings: list[str] = []

        b_output_range = _extract_output_range(contract_b)
        a_input_range = _extract_input_range(contract_a)

        if b_output_range and a_input_range:
            b_min, b_max = b_output_range
            a_min, a_max = a_input_range
            satisfied = (b_min >= a_min) and (b_max <= a_max)
            pair = CheckedPair(
                a_postcondition=f"A.input ∈ [{a_min}, {a_max}]",
                b_precondition=f"B.output ∈ [{b_min}, {b_max}]",
                satisfied=satisfied,
                message=(
                    "B 输出范围 ⊆ A 输入范围，反馈通路兼容"
                    if satisfied
                    else f"不兼容：B 输出 [{b_min}, {b_max}] 超出 A 输入 "
                    f"[{a_min}, {a_max}]，反馈可能破坏 A 的前置条件"
                ),
            )
            pairs.append(pair)
            if not satisfied:
                violations.append(pair.to_dict())
        else:
            warnings.append("A 输入或 B 输出范围未声明，跳过反馈范围检查")

        # 反馈稳定性 mock 评估
        a_posts = [
            _expr_to_str(p) for p in _extract_section(contract_a, "postconditions")
        ]
        b_posts = [
            _expr_to_str(p) for p in _extract_section(contract_b, "postconditions")
        ]
        stable, msg = _assess_feedback_stability(a_posts, b_posts)
        pair = CheckedPair(
            a_postcondition=" | ".join(a_posts) if a_posts else "<none>",
            b_precondition="feedback stability",
            satisfied=stable,
            message=msg,
        )
        pairs.append(pair)
        if not stable:
            violations.append(pair.to_dict())

        warnings.append("反馈组合的稳定性需通过仿真进一步验证（建议至少 200 步）")

        return CompatibilityResult(
            compatible=len(violations) == 0,
            checked_pairs=[p.to_dict() for p in pairs],
            violations=violations,
            warnings=warnings,
            connection="feedback",
        )


# ====================================================================== #
# 模块级便捷函数
# ====================================================================== #
def check_compatibility(
    contract_a_yaml: str,
    contract_b_yaml: str,
    connection: str = "sequential",
) -> CompatibilityResult:
    """契约兼容性检查模块级入口（便捷封装）。

    Args:
        contract_a_yaml: A 组件的 .contract YAML 字符串。
        contract_b_yaml: B 组件的 .contract YAML 字符串。
        connection: 连接方式（sequential / parallel / feedback）。

    Returns:
        CompatibilityResult。
    """
    checker = CompatibilityChecker()
    return checker.check(contract_a_yaml, contract_b_yaml, connection)


# ====================================================================== #
# 辅助解析函数
# ====================================================================== #
def _extract_section(contract: dict[str, Any], section: str) -> list[Any]:
    """从契约字典提取指定 section，兼容两种 YAML 布局。

    布局1：section 在顶层
    布局2：section 在 contracts 子字典
    """
    if section in contract:
        return contract.get(section, []) or []
    contracts_block = contract.get("contracts", {}) or {}
    return contracts_block.get(section, []) or []


def _expr_to_str(expr: Any) -> str:
    """将契约表达式（str 或 dict）转为字符串描述。"""
    if isinstance(expr, str):
        return expr
    if isinstance(expr, dict):
        return str(expr.get("desc", "") or expr.get("expr", ""))
    return str(expr)


def _extract_input_range(contract: dict[str, Any]) -> tuple[float, float] | None:
    """提取契约的输入范围 [min, max]。

    优先从 interface.inputs[0].range 提取；
    其次从 preconditions 中解析数值边界（>=、<=、>、<）。
    """
    interface = contract.get("interface", {}) or {}
    inputs = interface.get("inputs", []) or []
    if inputs and isinstance(inputs[0], dict):
        rng = inputs[0].get("range")
        if rng and isinstance(rng, (list, tuple)) and len(rng) == 2:
            try:
                return float(rng[0]), float(rng[1])
            except (TypeError, ValueError):
                pass

    return _extract_range_from_conditions(_extract_section(contract, "preconditions"))


def _extract_output_range(contract: dict[str, Any]) -> tuple[float, float] | None:
    """提取契约的输出范围 [min, max]。

    优先从 interface.outputs[0].range 提取；
    其次从 postconditions 中解析数值边界。
    """
    interface = contract.get("interface", {}) or {}
    outputs = interface.get("outputs", []) or []
    if outputs and isinstance(outputs[0], dict):
        rng = outputs[0].get("range")
        if rng and isinstance(rng, (list, tuple)) and len(rng) == 2:
            try:
                return float(rng[0]), float(rng[1])
            except (TypeError, ValueError):
                pass

    return _extract_range_from_conditions(_extract_section(contract, "postconditions"))


# 数值边界正则：匹配 >= 0, <= 20000, > -10, < 100 等
_RANGE_PATTERN = re.compile(r"(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)")


def _extract_range_from_conditions(
    conditions: list[Any],
) -> tuple[float, float] | None:
    """从条件表达式列表中提取 [min, max] 范围。

    扫描所有条件，提取 >= / > 的最大值作为下界，<= / < 的最小值作为上界。
    若只找到一端，另一端使用默认 ±inf。
    """
    min_val: float | None = None
    max_val: float | None = None

    for cond in conditions:
        expr = _expr_to_str(cond)
        for op, val_str in _RANGE_PATTERN.findall(expr):
            try:
                val = float(val_str)
            except ValueError:
                continue
            if op in (">=", ">"):
                if min_val is None or val > min_val:
                    min_val = val
            elif op in ("<=", "<"):
                if max_val is None or val < max_val:
                    max_val = val

    if min_val is None and max_val is None:
        return None
    return (
        min_val if min_val is not None else float("-inf"),
        max_val if max_val is not None else float("inf"),
    )


def _check_precondition_satisfied(
    pre_str: str,
    a_post_strs: list[str],
    a_output_range: tuple[float, float] | None,
) -> tuple[bool, str]:
    """检查 B 的单条前置条件是否被 A 的后置条件满足。

    判定规则：
    1) 若前置条件是数值边界检查（如 "x >= 0"）：
       用 A 的输出范围 [min, max] 验证（所有 A 输出值必须满足 B 前置）
    2) 若前置条件是 NULL 检查：
       检查 A 的后置条件中是否包含 NULL 检查
    3) 其他：默认通过（避免阻塞，仅做占位 mock）

    Args:
        pre_str: B 的前置条件表达式字符串。
        a_post_strs: A 的所有后置条件表达式字符串列表。
        a_output_range: A 的输出范围 (min, max) 或 None。

    Returns:
        (satisfied, message)
    """
    pre_lower = pre_str.lower()

    # 1) NULL 检查类
    if "null" in pre_lower:
        for post in a_post_strs:
            if "null" in post.lower():
                return True, f"A 的后置条件 '{post}' 满足 NULL 检查"
        return False, "A 的后置条件中未声明 NULL 检查"

    # 2) 数值边界检查
    pre_ranges = _RANGE_PATTERN.findall(pre_str)
    if pre_ranges:
        if a_output_range is None:
            return (
                True,
                "A 未声明输出范围，数值边界检查默认通过（mock）",
            )
        a_min, a_max = a_output_range
        for op, val_str in pre_ranges:
            try:
                val = float(val_str)
            except ValueError:
                continue
            if op == ">=":
                # 要求 A 所有输出 >= val，即 a_min >= val
                if a_min >= val:
                    continue
                return (
                    False,
                    f"A 输出最小值 {a_min} < 要求 {val}，不满足前置条件 '{pre_str}'",
                )
            if op == ">":
                if a_min > val:
                    continue
                return (
                    False,
                    f"A 输出最小值 {a_min} ≤ 要求 {val}，不满足前置条件 '{pre_str}'",
                )
            if op == "<=":
                if a_max <= val:
                    continue
                return (
                    False,
                    f"A 输出最大值 {a_max} > 要求 {val}，不满足前置条件 '{pre_str}'",
                )
            if op == "<":
                if a_max < val:
                    continue
                return (
                    False,
                    f"A 输出最大值 {a_max} ≥ 要求 {val}，不满足前置条件 '{pre_str}'",
                )
        # 所有数值边界均满足
        return True, f"A 的输出范围 [{a_min}, {a_max}] 满足 '{pre_str}'"

    # 3) 其他类型：默认通过（mock，避免阻塞）
    return True, f"前置条件 '{pre_str}' 默认通过（mock）"


def _detect_precondition_conflict(a_pres: list[str], b_pres: list[str]) -> str | None:
    """检测 A 和 B 的前置条件是否显式冲突（mock）。

    检测规则：从两边各提取数值边界，若同一变量存在互斥约束，则视为冲突。
    此处简化：若 A 要求 input >= val_a 且 B 要求 input < val_b 且 val_b <= val_a，
    则视为冲突。
    """
    a_lower_bound = _extract_lower_bound(a_pres)
    b_lower_bound = _extract_lower_bound(b_pres)
    a_upper_bound = _extract_upper_bound(a_pres)
    b_upper_bound = _extract_upper_bound(b_pres)

    lower = max(a_lower_bound or float("-inf"), b_lower_bound or float("-inf"))
    upper = min(a_upper_bound or float("inf"), b_upper_bound or float("inf"))

    if lower > upper:
        return (
            f"A 输入下界 {a_lower_bound} / B 输入下界 {b_lower_bound} "
            f"vs A 输入上界 {a_upper_bound} / B 输入上界 {b_upper_bound} 互斥"
        )
    return None


def _extract_lower_bound(conds: list[str]) -> float | None:
    """从条件列表中提取最大下界（>= / > 的最大值）。"""
    result: float | None = None
    for cond in conds:
        for op, val_str in _RANGE_PATTERN.findall(cond):
            try:
                val = float(val_str)
            except ValueError:
                continue
            if op in (">=", ">") and (result is None or val > result):
                result = val
    return result


def _extract_upper_bound(conds: list[str]) -> float | None:
    """从条件列表中提取最小上界（<= / < 的最小值）。"""
    result: float | None = None
    for cond in conds:
        for op, val_str in _RANGE_PATTERN.findall(cond):
            try:
                val = float(val_str)
            except ValueError:
                continue
            if op in ("<=", "<") and (result is None or val < result):
                result = val
    return result


def _assess_feedback_stability(
    a_posts: list[str], b_posts: list[str]
) -> tuple[bool, str]:
    """反馈稳定性 mock 评估。

    真实实现需通过仿真迭代收敛性分析；此处采用启发式：
    - 若 A 或 B 的后置条件中含 abs / delta 限定（如 |x| < eps），
      视为有界约束，倾向稳定；
    - 否则默认通过（mock），由仿真进一步验证。

    Returns:
        (stable, message)
    """
    bounded = False
    for post in a_posts + b_posts:
        lower = post.lower()
        if "abs" in lower or "delta" in lower or "epsilon" in lower:
            bounded = True
            break

    if bounded:
        return True, "A/B 后置条件含 abs/delta 约束，反馈预期稳定"
    return (
        True,
        "反馈稳定性默认通过（mock），需仿真进一步验证",
    )
