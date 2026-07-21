"""Z3 SMT 求解器验证器 —— VerifierProtocol 实现."""

from __future__ import annotations

import time
from typing import Any

from skyforge_engine.core.protocols import ToolNotFoundError, VerificationResult
from skyforge_engine.utils.log_util import logger


class Z3Verifier:
    """Z3 SMT 约束求解器验证器."""

    @property
    def tool_name(self) -> str:
        return "z3"

    def is_available(self) -> bool:
        try:
            from z3 import Solver  # noqa: F401
            return True
        except ImportError:
            return False

    def verify(self, code: str = "", contract: str | None = None, **kwargs: Any) -> VerificationResult:
        """执行 Z3 约束验证.

        Args:
            code: 待验证代码（当前实现中主要用于兼容性，核心约束来自 kwargs）。
            contract: 可选契约文本。
            **kwargs: 支持 preconditions, postconditions, invariants。

        Returns:
            VerificationResult: 验证结果。

        Raises:
            ToolNotFoundError: Z3 不可用时抛出。
        """
        if not self.is_available():
            raise ToolNotFoundError(self.tool_name)

        preconditions = kwargs.get("preconditions", [])
        postconditions = kwargs.get("postconditions", [])
        invariants = kwargs.get("invariants", [])

        start = time.time()
        try:
            from z3 import Real, Solver, sat

            solver = Solver()
            variables: dict[str, Any] = {}

            for pc in preconditions:
                var_name = pc.get("var", "x")
                if var_name not in variables:
                    variables[var_name] = Real(var_name)

            for pc in preconditions:
                var_name = pc.get("var", "x")
                domain = pc.get("domain", [])
                expr = pc.get("expr", "")
                if domain:
                    lo, hi = domain
                    solver.add(variables[var_name] >= lo)
                    solver.add(variables[var_name] <= hi)
                if expr:
                    self._add_expr(solver, variables, expr)

            if invariants:
                for inv in invariants:
                    expr = inv.get("expr", "")
                    if expr:
                        self._add_expr(solver, variables, expr)

            for pc in postconditions:
                expect = pc.get("expected", 0)
                expr = pc.get("expr", "")
                if expr:
                    self._add_expr(solver, variables, f"{expr} != {expect}")

            result = solver.check()
            elapsed = (time.time() - start) * 1000

            if result == sat:
                model = {str(d): solver.model()[d] for d in solver.model()}
                return VerificationResult(
                    passed=True,
                    tool_name=self.tool_name,
                    tool_available=True,
                    output=f"模型: {model}",
                    duration_ms=elapsed,
                )
            else:
                violations = ["契约约束不一致：前置/后置条件存在逻辑矛盾"]
                if hasattr(solver, "unsat_core"):
                    violations.extend([str(c) for c in solver.unsat_core()])
                return VerificationResult(
                    passed=False,
                    tool_name=self.tool_name,
                    tool_available=True,
                    violations=[{"message": v} for v in violations],
                    output="约束不可满足",
                    duration_ms=elapsed,
                )

        except Exception as e:
            logger.error(f"Z3:验证异常: {e}")
            raise

    def _add_expr(self, solver, variables: dict, expr: str) -> None:
        """简化表达式解析并添加到求解器."""
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
