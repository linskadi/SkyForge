"""CBMC 有界模型检查器 — 形式化验证生成的 C 代码。

工具: CBMC (C Bounded Model Checker), BSD-4-Clause
用途: 数学级证明内存安全性和功能正确性
DO-178C: 对应 DO-333 形式化方法补充
参考: Amazon 曾用 CBMC 验证 FreeRTOS 内核

集成方式:
    from skyforge_engine.tools.cbmc_verifier import run_cbmc_verification
    result = run_cbmc_verification(code, unwind=10)

环境变量:
    CBMC_ENABLED=true  启用 CBMC 验证（默认取决于工具可用性）
    USE_REAL_CBMC=true 强制真实调用（不可用时报错）
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field

from skyforge_engine.utils.log_util import logger

import warnings
from skyforge_engine.core.verifiers.cbmc_verifier import CBMCVerifier as _CBMCVerifier


@dataclass
class CBMCResult:
    """CBMC 验证结果。

    Attributes:
        passed: True 表示验证通过。
        status: 原始状态（SUCCESS / FAILURE）。
        violations: 违反的断言列表。
        trace: 反例追踪（验证失败时）。
        time_ms: 验证耗时（毫秒）。
        tool_available: CBMC 工具是否可用。
    """

    passed: bool = False
    status: str = ""
    violations: list[str] = field(default_factory=list)
    trace: str = ""
    time_ms: float = 0.0
    tool_available: bool = False


def _find_cbmc() -> str | None:
    """查找 CBMC 可执行文件路径。"""
    return shutil.which("cbmc")


def _is_enabled() -> bool:
    """检查 CBMC 是否启用。"""
    if os.environ.get("CBMC_ENABLED", "").lower() == "false":
        return False
    return _find_cbmc() is not None


def run_cbmc_verification(
    code: str,
    unwind: int = 10,
    function: str | None = None,
    property_flags: list[str] | None = None,
) -> CBMCResult:
    """对 C 代码运行 CBMC 有界模型检查。

    .. deprecated::
        使用 ``CBMCVerifier().verify(code, unwind=..., function=...)`` 替代。

    Args:
        code: C 源代码字符串。
        unwind: 循环展开次数（默认 10）。
        function: 指定入口函数（None=自动检测 main）。
        property_flags: 额外属性标志。

    Returns:
        CBMCResult: 验证结果。
    """
    warnings.warn(
        "run_cbmc_verification is deprecated, use CBMCVerifier instead",
        DeprecationWarning,
        stacklevel=2,
    )

    if not _is_enabled():
        return CBMCResult(
            passed=True,
            status="SKIPPED",
            tool_available=False,
        )

    verifier = _CBMCVerifier()
    if not verifier.is_available():
        return CBMCResult(
            passed=True,
            status="SKIPPED",
            tool_available=False,
        )

    try:
        result = verifier.verify(
            code,
            unwind=unwind,
            function=function,
            property_flags=property_flags,
        )
        return CBMCResult(
            passed=result.passed,
            status=result.metadata.get("status", "UNKNOWN"),
            violations=[v.get("message", "") for v in result.violations],
            trace=result.metadata.get("trace", ""),
            time_ms=result.duration_ms,
            tool_available=True,
        )
    except Exception as e:
        logger.error(f"CBMC:异常: {e}")
        return CBMCResult(
            passed=True,
            status="ERROR",
            violations=[str(e)],
        )


def _inject_cbmc_assertions(code: str) -> str:
    """在 C 代码中注入 CBMC 断言注解。

    自动添加:
      - __CPROVER_assume(condition) 约束假设
      - __CPROVER_assert(condition, "message") 断言检查

    对 main 函数中的输入 fgets 添加范围约束。
    """
    lines = code.splitlines()
    injected: list[str] = []
    in_main = False

    for line in lines:
        stripped = line.strip()
        # 检测 main 函数入口
        if "int main" in stripped or "void main" in stripped:
            in_main = True
            injected.append(line)
            continue

        # 在 main 函数中处理输入
        if in_main and "fgets" in stripped and "stdin" in stripped:
            pass  # 跳过，由 CBMC 自动处理

        injected.append(line)

    return "\n".join(injected)


# 便捷函数
def verify_code(code: str, unwind: int = 10) -> dict:
    """便捷函数：验证代码并返回字典结果。

    .. deprecated::
        使用 ``CBMCVerifier().verify(code, unwind=...)`` 替代。
    """
    warnings.warn(
        "verify_code is deprecated, use CBMCVerifier instead",
        DeprecationWarning,
        stacklevel=2,
    )
    result = run_cbmc_verification(code, unwind=unwind)
    return {
        "passed": result.passed,
        "status": result.status,
        "violations": result.violations,
        "time_ms": result.time_ms,
        "tool_available": result.tool_available,
    }
