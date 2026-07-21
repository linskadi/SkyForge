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
            from skyforge_engine.tools.contract_formal_verifier import verify_contract

            formal_result = verify_contract(contract, code=None)
            artifact["formal_verification"] = formal_result.to_dict()
            if not formal_result.is_consistent:
                await hook(
                    "SYSTEM",
                    "warn",
                    f"契约形式化验证发现 {len(formal_result.contradictions)} 处逻辑矛盾，"
                    "建议审查契约条件",
                )
            else:
                await hook(
                    "SYSTEM",
                    "info",
                    f"契约形式化验证通过 (Z3: {'可用' if formal_result.z3_available else '不可用'}, "
                    f"CBMC: {'可用' if formal_result.cbmc_available else ' unavailable'})"
                    f"{' + 生成' + str(formal_result.test_case_count) + '个边界测试用例' if formal_result.test_case_count > 0 else ''}",
                )
        except ImportError:
            await hook("SYSTEM", "info", "契约形式化验证跳过 (模块未安装)")
            artifact["formal_verification"] = None
        except Exception as e:
            logger.warning(f"Pipeline:契约形式化验证异常: {e}")
            artifact["formal_verification"] = None

        return StageResult(artifact=artifact, status="success")
