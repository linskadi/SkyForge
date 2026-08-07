"""形式化验证 Stage。"""

from __future__ import annotations

from typing import Any

from skyforge_engine.core.protocols import StageResult
from skyforge_engine.core.stages._utils import _normalize_hook
from skyforge_engine.utils.log_util import logger


class FormalVerificationStage:
    """契约形式化验证 (Z3 + CBMC)。"""

    @property
    def name(self) -> str:
        return "formal_verification"

    @property
    def description(self) -> str:
        return "契约形式化验证 (Z3 + CBMC)"

    async def execute(
        self, artifact: dict[str, Any], context: dict[str, Any] | None = None
    ) -> StageResult:
        context = context or {}
        hook = _normalize_hook(context.get("log_hook"))
        contract = artifact.get("contract", "")

        try:
            from skyforge_engine.core.verifiers import ContractVerifier

            verifier = ContractVerifier()
            formal_result = verifier.verify(code="", contract=contract)
            artifact["formal_verification"] = {
                "passed": formal_result.passed,
                "tool_available": formal_result.tool_available,
                "violations": formal_result.violations,
                "output": formal_result.output,
                "duration_ms": formal_result.duration_ms,
            }
            if not formal_result.passed:
                await hook(
                    "SYSTEM",
                    "warn",
                    f"契约形式化验证发现 {len(formal_result.violations)} 处逻辑矛盾，"
                    "建议审查契约条件",
                )
            else:
                await hook(
                    "SYSTEM",
                    "info",
                    f"契约形式化验证通过 "
                    f"(tool_available={formal_result.tool_available})",
                )
        except ImportError:
            await hook("SYSTEM", "info", "契约形式化验证跳过 (模块未安装)")
            artifact["formal_verification"] = None
        except Exception as e:
            logger.warning(f"Pipeline:契约形式化验证异常: {e}")
            artifact["formal_verification"] = None

        return StageResult(artifact=artifact, status="success")
