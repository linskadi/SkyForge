"""验证器链 —— 支持组合多个 VerifierProtocol 实现."""

from __future__ import annotations

from typing import Any

from skyforge_engine.core.protocols import ToolNotFoundError, VerificationResult, VerifierProtocol


class VerifierChain:
    """验证器链，支持顺序执行多个验证器.

    Attributes:
        fail_fast: 为 True 时，第一个验证失败或工具不可用即停止/抛出。
    """

    def __init__(self, verifiers: list[VerifierProtocol] | None = None, fail_fast: bool = False):
        self._verifiers = list(verifiers) if verifiers else []
        self.fail_fast = fail_fast

    def add(self, verifier: VerifierProtocol) -> "VerifierChain":
        """向链中添加验证器并返回自身（支持链式调用）。"""
        self._verifiers.append(verifier)
        return self

    def verify_all(self, code: str, contract: str | None = None, **kwargs: Any) -> list[VerificationResult]:
        """顺序执行所有验证器，返回结果列表.

        Args:
            code: 待验证代码。
            contract: 可选契约文本。
            **kwargs: 传递给每个验证器的额外参数。

        Returns:
            各验证器的结果列表。

        Raises:
            ToolNotFoundError: 当 fail_fast=True 且某个验证器不可用时抛出。
        """
        results: list[VerificationResult] = []
        for verifier in self._verifiers:
            try:
                result = verifier.verify(code, contract, **kwargs)
                results.append(result)
                if self.fail_fast and not result.passed:
                    break
            except ToolNotFoundError:
                if self.fail_fast:
                    raise
                results.append(
                    VerificationResult(
                        passed=False,
                        tool_name=verifier.tool_name,
                        tool_available=False,
                        output=f"工具不可用: {verifier.tool_name}",
                    )
                )
        return results

    def verify_any(self, code: str, contract: str | None = None, **kwargs: Any) -> VerificationResult:
        """尝试各验证器，返回第一个通过的验证结果.

        如果所有验证器都失败或不可用，返回一个失败的 VerificationResult。

        Args:
            code: 待验证代码。
            contract: 可选契约文本。
            **kwargs: 传递给每个验证器的额外参数。

        Returns:
            第一个通过的验证结果，或汇总失败结果。
        """
        last_error: Exception | None = None
        for verifier in self._verifiers:
            try:
                result = verifier.verify(code, contract, **kwargs)
                if result.passed:
                    return result
            except ToolNotFoundError as e:
                last_error = e
                continue

        if last_error is not None:
            raise last_error

        return VerificationResult(
            passed=False,
            tool_name="verifier_chain",
            tool_available=True,
            output="所有验证器均未通过",
        )
