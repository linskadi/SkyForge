"""组件组合器：把两个 C 组件按指定连接方式拼接为单一组件。

参考设计文档第 6.5 节"可组合性验证"。
契约式设计的一个关键价值是"组件可组合性"——多个组件组合后，契约仍然满足。

工作流：
  1. 调用 CompatibilityChecker 检查 A/B 契约在指定连接方式下是否兼容
  2. 重命名 A/B 代码中的 filter 函数为 filter_a / filter_b
  3. 拼接 A/B 代码 + 生成 wrapper filter 函数
  4. 合并 A/B 契约为组合契约
  5. 返回 CompositionResult

支持的连接方式：
- sequential：A 的输出作为 B 的输入
- parallel：A 和 B 并行执行（共享输入）
- feedback：B 的输出反馈到 A
"""

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from app.core.composable.compatibility_checker import (
    CompatibilityChecker,
    CompatibilityResult,
)
from app.utils.log_util import logger

# 支持的连接方式
VALID_CONNECTIONS = {"sequential", "parallel", "feedback"}

# 匹配 C 函数定义：double filter(double xxx)
_FILTER_DEF_PATTERN = re.compile(r"\b(double\s+filter\s*\(\s*double\s+\w+\s*\)\s*\{)")


@dataclass
class CompositionResult:
    """组件组合结果。

    Attributes:
        composed_code: 组合后的 C 代码字符串（含单一 double filter(double) 入口）。
        composed_contract: 组合后的 .contract YAML 字符串。
        compatibility_check: 兼容性检查结果字典（CompatibilityResult.to_dict()）。
        warnings: 警告信息列表。
        connection: 实际使用的连接方式。
    """

    composed_code: str = ""
    composed_contract: str = ""
    compatibility_check: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    connection: str = "sequential"

    def to_dict(self) -> dict[str, Any]:
        return {
            "composed_code": self.composed_code,
            "composed_contract": self.composed_contract,
            "compatibility_check": self.compatibility_check,
            "warnings": self.warnings,
            "connection": self.connection,
        }


class ComponentCombinator:
    """组件组合器：拼接 A/B 代码 + 合并契约 + 兼容性检查。

    使用方式：
        combinator = ComponentCombinator()
        result = combinator.compose(
            component_a_code, component_a_contract,
            component_b_code, component_b_contract,
            connection="sequential",
        )
    """

    def __init__(self) -> None:
        self.checker = CompatibilityChecker()

    def compose(
        self,
        component_a_code: str,
        component_a_contract: str,
        component_b_code: str,
        component_b_contract: str,
        connection: str = "sequential",
    ) -> CompositionResult:
        """组合两个组件。

        Args:
            component_a_code: A 组件的 C 代码字符串（必须含 double filter(double) 函数）。
            component_a_contract: A 组件的 .contract YAML 字符串。
            component_b_code: B 组件的 C 代码字符串（必须含 double filter(double) 函数）。
            component_b_contract: B 组件的 .contract YAML 字符串。
            connection: 连接方式（sequential / parallel / feedback）。

        Returns:
            CompositionResult：包含组合后代码、契约、兼容性检查结果。
        """
        if connection not in VALID_CONNECTIONS:
            raise ValueError(
                f"不支持的连接方式: {connection}，支持: {VALID_CONNECTIONS}"
            )

        logger.info(
            f"ComponentCombinator:开始 connection={connection} "
            f"A_code={len(component_a_code)}B "
            f"B_code={len(component_b_code)}B"
        )

        warnings: list[str] = []

        # 1) 兼容性检查
        compat_result: CompatibilityResult = self.checker.check(
            component_a_contract, component_b_contract, connection
        )
        warnings.extend(compat_result.warnings)
        if not compat_result.compatible:
            warnings.append(
                "兼容性检查未通过，组合可能不安全；"
                "请查看 compatibility_check.violations"
            )

        # 2) 解析契约
        try:
            contract_a = yaml.safe_load(component_a_contract) or {}
        except yaml.YAMLError:
            contract_a = {}
            warnings.append("A 契约 YAML 解析失败，组合契约为最小化版本")
        try:
            contract_b = yaml.safe_load(component_b_contract) or {}
        except yaml.YAMLError:
            contract_b = {}
            warnings.append("B 契约 YAML 解析失败，组合契约为最小化版本")

        # 3) 生成组合后的 C 代码
        composed_code = self._generate_composed_code(
            component_a_code, component_b_code, connection
        )

        # 4) 生成组合后的契约
        composed_contract = self._generate_composed_contract(
            contract_a, contract_b, connection
        )

        logger.info(
            f"ComponentCombinator:完成 composed_code={len(composed_code)}B "
            f"compat={compat_result.compatible}"
        )

        return CompositionResult(
            composed_code=composed_code,
            composed_contract=composed_contract,
            compatibility_check=compat_result.to_dict(),
            warnings=warnings,
            connection=connection,
        )

    # ------------------------------------------------------------------ #
    # C 代码组合
    # ------------------------------------------------------------------ #
    def _generate_composed_code(
        self,
        code_a: str,
        code_b: str,
        connection: str,
    ) -> str:
        """生成组合后的 C 代码。

        策略：
        1. 把 A 的 filter 函数重命名为 filter_a
        2. 把 B 的 filter 函数重命名为 filter_b
        3. 新增 double filter(double input) wrapper，按 connection 调用两者
        """
        # 重命名 A/B 代码中的 filter 函数定义
        renamed_a = _rename_filter_def(code_a, "filter_a")
        renamed_b = _rename_filter_def(code_b, "filter_b")

        # 生成 wrapper
        if connection == "sequential":
            wrapper = _SEQUENTIAL_WRAPPER
        elif connection == "parallel":
            wrapper = _PARALLEL_WRAPPER
        else:  # feedback
            wrapper = _FEEDBACK_WRAPPER

        header = (
            "/* === 组合 C 代码（由 ComponentCombinator 自动生成）===\n"
            f" * 连接方式: {connection}\n"
            " * DO-178C 6.5 组件可组合性验证\n"
            " */\n\n"
        )

        return (
            header
            + "/* ===== 组件 A ===== */\n"
            + renamed_a
            + "\n\n"
            + "/* ===== 组件 B ===== */\n"
            + renamed_b
            + "\n\n"
            + "/* ===== 组合 wrapper ===== */\n"
            + wrapper
        )

    # ------------------------------------------------------------------ #
    # 契约组合
    # ------------------------------------------------------------------ #
    def _generate_composed_contract(
        self,
        contract_a: dict[str, Any],
        contract_b: dict[str, Any],
        connection: str,
    ) -> str:
        """生成组合后的契约 YAML。

        合并规则：
        - sequential：pre = A.pre, post = B.post, inv = A.inv + B.inv, fh = A.fh + B.fh
        - parallel：pre = A.pre + B.pre, post = A.post + B.post, ...
        - feedback：pre = A.pre, post = A.post + 反馈稳定性约束, ...
        """
        a_pre = _extract_section(contract_a, "preconditions")
        a_post = _extract_section(contract_a, "postconditions")
        a_inv = _extract_section(contract_a, "invariants")
        a_fh = _extract_section(contract_a, "fault_handling")

        b_pre = _extract_section(contract_b, "preconditions")
        b_post = _extract_section(contract_b, "postconditions")
        b_inv = _extract_section(contract_b, "invariants")
        b_fh = _extract_section(contract_b, "fault_handling")

        a_interface = contract_a.get("interface", {}) or {}
        b_interface = contract_b.get("interface", {}) or {}

        if connection == "sequential":
            # 组合后输入 = A 的输入；组合后输出 = B 的输出
            composed_pre = list(a_pre)
            composed_post = list(b_post)
            composed_inv = list(a_inv) + list(b_inv)
            composed_fh = list(a_fh) + list(b_fh)
            composed_interface = {
                "inputs": a_interface.get("inputs", []) or [],
                "outputs": b_interface.get("outputs", []) or [],
            }
        elif connection == "parallel":
            # 组合后输入 = A/B 共享；组合后输出 = A/B 合并
            composed_pre = list(a_pre) + list(b_pre)
            composed_post = list(a_post) + list(b_post)
            composed_inv = list(a_inv) + list(b_inv)
            composed_fh = list(a_fh) + list(b_fh)
            composed_interface = {
                "inputs": a_interface.get("inputs", []) or [],
                "outputs": (a_interface.get("outputs", []) or [])
                + (b_interface.get("outputs", []) or []),
            }
        else:  # feedback
            # 反馈：组合后输入 = A 的输入；组合后输出 = A 的输出
            # 反馈稳定性约束作为额外后置条件
            composed_pre = list(a_pre)
            composed_post = list(a_post) + [
                "feedback_loop_stable: |B_output| bounded (验证)"
            ]
            composed_inv = list(a_inv) + list(b_inv)
            composed_fh = list(a_fh) + list(b_fh)
            composed_interface = {
                "inputs": a_interface.get("inputs", []) or [],
                "outputs": a_interface.get("outputs", []) or [],
            }

        composed = {
            "component": f"composed_{connection}",
            "version": "1.0.0",
            "safety_level": contract_a.get("safety_level", "DAL-B"),
            "traceability": list(contract_a.get("traceability", []))
            + [f"B:{t}" for t in contract_b.get("traceability", []) or []],
            "interface": composed_interface,
            "contracts": {
                "preconditions": composed_pre,
                "postconditions": composed_post,
                "invariants": composed_inv,
                "fault_handling": composed_fh,
            },
        }
        return yaml.safe_dump(composed, allow_unicode=True, sort_keys=False)


# ====================================================================== #
# 模块级便捷函数
# ====================================================================== #
def compose(
    component_a_code: str,
    component_a_contract: str,
    component_b_code: str,
    component_b_contract: str,
    connection: str = "sequential",
) -> CompositionResult:
    """组件组合模块级入口（便捷封装）。

    Args:
        component_a_code: A 组件的 C 代码字符串。
        component_a_contract: A 组件的 .contract YAML 字符串。
        component_b_code: B 组件的 C 代码字符串。
        component_b_contract: B 组件的 .contract YAML 字符串。
        connection: 连接方式（sequential / parallel / feedback）。

    Returns:
        CompositionResult。
    """
    combinator = ComponentCombinator()
    return combinator.compose(
        component_a_code,
        component_a_contract,
        component_b_code,
        component_b_contract,
        connection,
    )


# ====================================================================== #
# 内部辅助函数
# ====================================================================== #
def _rename_filter_def(code: str, new_name: str) -> str:
    """把 C 代码中的 `double filter(double ...)` 函数定义重命名。

    替换 `double filter(` → `double <new_name>(`，仅替换第一个匹配（避免误伤）。
    若代码中没有 filter 定义，原样返回。
    """
    pattern = re.compile(r"\bdouble\s+filter\s*\(")
    # 仅替换第一个匹配
    new_code, n = pattern.subn(f"double {new_name}(", code, count=1)
    if n == 0:
        # 没有 filter 函数定义，原样返回（VirtualMCU 会自动补一个）
        return code
    return new_code


def _extract_section(contract: dict[str, Any], section: str) -> list[Any]:
    """从契约字典提取指定 section，兼容两种 YAML 布局。"""
    if section in contract:
        return contract.get(section, []) or []
    contracts_block = contract.get("contracts", {}) or {}
    return contracts_block.get(section, []) or []


# ====================================================================== #
# wrapper C 代码模板
# ====================================================================== #
_SEQUENTIAL_WRAPPER = """\
/* 顺序组合：A 的输出 → B 的输入 */
double filter(double input) {
    double intermediate = filter_a(input);
    return filter_b(intermediate);
}
"""

_PARALLEL_WRAPPER = """\
/* 并行组合：A 和 B 共享输入，输出取平均 */
double filter(double input) {
    double out_a = filter_a(input);
    double out_b = filter_b(input);
    return (out_a + out_b) / 2.0;
}
"""

_FEEDBACK_WRAPPER = """\
/* 反馈组合：B 的输出反馈到 A（单步反馈，需仿真验证稳定性）*/
double filter(double input) {
    /* 第 1 轮：A 处理原始输入 */
    double a_out = filter_a(input);
    /* 第 2 轮：A 处理输入 + B 的反馈 */
    double feedback = filter_b(a_out);
    double a_out_final = filter_a(input + feedback);
    return a_out_final;
}
"""
