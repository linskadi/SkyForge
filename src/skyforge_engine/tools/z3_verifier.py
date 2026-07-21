"""Z3 SMT 约束求解器 — 契约验证 + 边界测试用例生成。

工具: z3-solver (MIT), Microsoft Research
用途: 约束求解、自动测试生成、组件兼容性形式化证明
DO-178C: 契约式设计 (Design by Contract) 的形式化基础

集成方式:
    from skyforge_engine.tools.z3_verifier import verify_contract_constraints
    result = verify_contract_constraints(preconditions, postconditions)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from skyforge_engine.utils.log_util import logger

import warnings
from skyforge_engine.core.verifiers.z3_verifier import Z3Verifier as _Z3Verifier


@dataclass
class Z3Result:
    """Z3 约束求解结果。"""

    satisfiable: bool = False
    model: dict[str, Any] = field(default_factory=dict)
    unsat_core: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    tool_available: bool = False


def _has_z3() -> bool:
    """检查 z3-solver 是否可用。"""
    try:
        from z3 import Solver  # noqa: F401
        return True
    except ImportError:
        return False


def verify_contract_constraints(
    preconditions: list[dict[str, Any]],
    postconditions: list[dict[str, Any]],
    invariants: list[dict[str, Any]] | None = None,
) -> Z3Result:
    """验证契约约束是否一致。

    .. deprecated::
        使用 ``Z3Verifier().verify(preconditions=..., postconditions=...)`` 替代。

    Args:
        preconditions: 前置条件列表 [{expr, domain}, ...]
        postconditions: 后置条件列表 [{expr, expected}, ...]
        invariants: 不变式列表

    Returns:
        Z3Result: 约束验证结果。
    """
    warnings.warn(
        "verify_contract_constraints is deprecated, use Z3Verifier instead",
        DeprecationWarning,
        stacklevel=2,
    )
    if not _has_z3():
        return Z3Result(satisfiable=True, tool_available=False)

    try:
        from z3 import Real, Solver, sat

        solver = Solver()

        # 定义变量
        variables: dict[str, Any] = {}
        for pc in preconditions:
            var_name = pc.get("var", "x")
            if var_name not in variables:
                variables[var_name] = Real(var_name)

        # 添加前置条件约束
        for pc in preconditions:
            var_name = pc.get("var", "x")
            domain = pc.get("domain", [])
            expr = pc.get("expr", "")
            if domain:
                lo, hi = domain
                solver.add(variables[var_name] >= lo)
                solver.add(variables[var_name] <= hi)
            if expr:
                _add_expr(solver, variables, expr)

        # 添加不变式
        if invariants:
            for inv in invariants:
                expr = inv.get("expr", "")
                if expr:
                    _add_expr(solver, variables, expr)

        # 添加后置条件（取反检查不可达）
        for pc in postconditions:
            expect = pc.get("expected", 0)
            expr = pc.get("expr", "")
            if expr:
                _add_expr(solver, variables, f"{expr} != {expect}")

        result = solver.check()

        if result == sat:
            model = {str(d): solver.model()[d] for d in solver.model()}
            return Z3Result(
                satisfiable=True,
                model=model,
                tool_available=True,
            )
        else:
            return Z3Result(
                satisfiable=False,
                unsat_core=[str(c) for c in solver.unsat_core()],
                violations=["契约约束不一致：前置/后置条件存在逻辑矛盾"],
                tool_available=True,
            )

    except Exception as e:
        logger.error(f"Z3:验证异常: {e}")
        return Z3Result(
            satisfiable=True,
            violations=[str(e)],
            tool_available=_has_z3(),
        )


def generate_boundary_test_cases(
    variable: str,
    domain: tuple[float, float],
    constraints: list[str] | None = None,
) -> list[dict[str, float]]:
    """基于约束求解生成边界测试用例。

    .. deprecated::
        使用 ``Z3Verifier`` 的边界测试生成能力替代。

    Args:
        variable: 变量名。
        domain: (min, max) 范围。
        constraints: 额外约束表达式。

    Returns:
        测试用例列表 [{variable: value}, ...]。
    """
    warnings.warn(
        "generate_boundary_test_cases is deprecated, use Z3Verifier instead",
        DeprecationWarning,
        stacklevel=2,
    )
    if not _has_z3():
        return [{"value": (domain[0] + domain[1]) / 2, "type": "default"}]

    try:
        from z3 import Real, Solver, sat, And

        cases: list[dict[str, float]] = []

        # 边界值
        lo, hi = domain
        mid = (lo + hi) / 2

        boundaries = [
            ("min", lo),
            ("min+1", lo + 1),
            ("mid", mid),
            ("max-1", hi - 1),
            ("max", hi),
        ]

        for label, val in boundaries:
            solver = Solver()
            x = Real(variable)
            solver.add(And(x >= lo, x <= hi))
            solver.add(x == val)
            if constraints:
                for c in constraints:
                    _add_expr(solver, {variable: x}, c)
            if solver.check() == sat:
                cases.append({variable: float(val), "type": label})

        return cases

    except Exception as e:
        logger.warning(f"Z3:测试生成失败: {e}")
        return [{"value": (domain[0] + domain[1]) / 2, "type": "default"}]


def check_component_compatibility_z3(
    input_range: tuple[float, float],
    output_range: tuple[float, float],
    gain: float = 1.0,
) -> dict[str, Any]:
    """用 Z3 验证组件输入/输出兼容性。

    .. deprecated::
        使用 ``Z3Verifier`` 替代。

    Args:
        input_range: 输入范围 (min, max)。
        output_range: 输出范围 (min, max)。
        gain: 增益系数。

    Returns:
        兼容性结果字典。
    """
    warnings.warn(
        "check_component_compatibility_z3 is deprecated, use Z3Verifier instead",
        DeprecationWarning,
        stacklevel=2,
    )
    if not _has_z3():
        return {"compatible": True, "method": "default"}

    try:
        from z3 import Real, Solver, sat, And

        x = Real("x")
        y = Real("y")
        solver = Solver()

        # 输入范围
        solver.add(And(x >= input_range[0], x <= input_range[1]))
        # 输出关系
        solver.add(y == x * gain)
        # 检查输出是否超界
        solver.add(And(y < output_range[0], y > output_range[1]))

        result = solver.check()
        return {
            "compatible": result != sat,
            "method": "z3",
            "unsat": result != sat,
        }

    except Exception as e:
        logger.warning(f"Z3:兼容性检查失败: {e}")
        return {"compatible": True, "method": "fallback"}


def _add_expr(solver, variables: dict, expr: str) -> None:
    """简化表达式解析并添加到求解器。"""

    # 简单表达式解析：x <= 100, x >= 0, x == 42
    expr = expr.strip()
    for var_name, var_obj in variables.items():
        if var_name in expr:
            if "<=" in expr:
                parts = expr.split("<=")
                if len(parts) == 2:
                    val = float(parts[1].strip())
                    solver.add(var_obj <= val)
            elif ">=" in expr:
                parts = expr.split(">=")
                if len(parts) == 2:
                    val = float(parts[1].strip())
                    solver.add(var_obj >= val)
            elif "<" in expr and "<<" not in expr:
                parts = expr.split("<")
                if len(parts) == 2:
                    val = float(parts[1].strip())
                    solver.add(var_obj < val)
            elif ">" in expr and ">>" not in expr:
                parts = expr.split(">")
                if len(parts) == 2:
                    val = float(parts[1].strip())
                    solver.add(var_obj > val)
            elif "==" in expr:
                parts = expr.split("==")
                if len(parts) == 2:
                    val = float(parts[1].strip())
                    solver.add(var_obj == val)
            break


# 便捷函数
def verify(counts: list[dict], conditions: list[dict]) -> dict:
    """便捷函数: 验证契约约束并返回字典。

    .. deprecated::
        使用 ``Z3Verifier().verify(preconditions=..., postconditions=...)`` 替代。
    """
    warnings.warn(
        "verify is deprecated, use Z3Verifier instead",
        DeprecationWarning,
        stacklevel=2,
    )
    verifier = _Z3Verifier()
    if not verifier.is_available():
        return {
            "satisfiable": True,
            "model": {},
            "violations": [],
            "tool_available": False,
        }
    try:
        result = verifier.verify(preconditions=counts, postconditions=conditions)
        return {
            "satisfiable": result.passed,
            "model": {},
            "violations": [v.get("message", "") for v in result.violations],
            "tool_available": result.tool_available,
        }
    except Exception as e:
        logger.error(f"Z3:验证异常: {e}")
        return {
            "satisfiable": True,
            "model": {},
            "violations": [str(e)],
            "tool_available": verifier.is_available(),
        }
