"""修复闭环 Stage。"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from skyforge_engine.core.protocols import StageResult
from skyforge_engine.core.stages._utils import (
    _check_result_to_dict,
    _flush_collected_logs,
    _make_sync_log_collector,
    _normalize_hook,
    _push_agent_thought,
)
from skyforge_engine.utils.log_util import logger


class RepairLoopStage:
    """扫描→修复→契约校验循环。"""

    def __init__(self, max_iterations: int = 3, req_id: str = "REQ-001") -> None:
        self._max_iterations = max_iterations
        self._req_id = req_id

    @property
    def name(self) -> str:
        return "repair_loop"

    @property
    def description(self) -> str:
        return "修复闭环：扫描→修复→契约校验"

    async def execute(
        self, artifact: dict[str, Any], context: dict[str, Any] | None = None
    ) -> StageResult:
        from skyforge_engine.agents.code_repairer import CodeRepairerAgent
        from skyforge_engine.tools.contract_checker import check as contract_check
        from skyforge_engine.tools.cppcheck_scanner import scan_multi as cppcheck_scan

        context = context or {}
        hook = _normalize_hook(context.get("log_hook"))
        code = artifact.get("code", "")
        contract = artifact.get("contract", "")
        language = artifact.get("language", "c")
        req_id = context.get("req_id", self._req_id)

        repairer = CodeRepairerAgent()
        current_code = code
        repair_history: list[dict[str, Any]] = []
        final_violations: list[Any] = []
        contract_check_result: Any = None

        await hook("REPAIR", "info", f"修复闭环启动 max_iterations={self._max_iterations}")

        for iteration in range(1, self._max_iterations + 1):
            await hook("REPAIR", "info", f"第 {iteration} 轮：扫描违规")
            sync_cb, pending_logs = _make_sync_log_collector()
            violations = cppcheck_scan(current_code, language=language, log_callback=sync_cb)
            await _flush_collected_logs(hook, pending_logs)
            final_violations = violations

            if not violations:
                await hook("REPAIR", "success", f"第 {iteration} 轮：无违规，跳出循环")
                break

            await hook(
                "REPAIR",
                "warn",
                f"第 {iteration} 轮：检出 {len(violations)} 条违规",
            )

            await _push_agent_thought(
                hook,
                "REPAIR",
                f"第 {iteration} 轮修复 Agent 启动：针对 "
                f"{len(violations)} 条 MISRA 违规进行修复",
            )
            repair_result = await repairer.repair(current_code, violations, req_id=req_id)
            await hook(
                "REPAIR",
                "success",
                f"第 {iteration} 轮：修复完成 actions={len(repair_result.actions)}",
            )

            # ---- 不退步检测：修复后重新扫描，防止引入新违规 ----
            sync_cb2, pending_logs2 = _make_sync_log_collector()
            post_repair_violations = cppcheck_scan(repair_result.code, language=language, log_callback=sync_cb2)
            await _flush_collected_logs(hook, pending_logs2)
            if len(post_repair_violations) > len(violations) or (
                # 检测引入新规则 ID（例如修复 15.5 时引入 15.1 goto）
                {v.rule_id for v in post_repair_violations} - {v.rule_id for v in violations}
            ):
                introduced = {v.rule_id for v in post_repair_violations} - {v.rule_id for v in violations}
                reason_parts = []
                if len(post_repair_violations) > len(violations):
                    reason_parts.append(f"数量退步（{len(violations)} → {len(post_repair_violations)}）")
                if introduced:
                    reason_parts.append(f"引入新规则 {introduced}")
                await hook(
                    "REPAIR",
                    "warn",
                    f"第 {iteration} 轮：修复后退步（{'，'.join(reason_parts)}），"
                    f"回退到修复前代码并终止修复循环",
                )
                # 回退：使用修复前代码，记录回退事件
                history_entry_degraded: dict[str, Any] = {
                    "iteration": iteration,
                    "violations_before": [asdict(v) for v in violations],
                    "violations_count_before": len(violations),
                    "post_repair_violations": len(post_repair_violations),
                    "actions": [asdict(a) for a in repair_result.actions],
                    "actions_count": len(repair_result.actions),
                    "code_after": repair_result.code,
                    "degraded": True,
                    "reverted": True,
                }
                repair_history.append(history_entry_degraded)
                break
            # ---- 不退步检测结束 ----

            if contract:
                await hook("SYSTEM", "info", f"第 {iteration} 轮：契约校验")
                contract_check_result = contract_check(
                    repair_result.code, contract, cid="CON-001", language=language
                )
                level = "success" if contract_check_result.passed else "error"
                await hook(
                    "SYSTEM",
                    level,
                    f"第 {iteration} 轮：契约校验完成 "
                    f"passed={contract_check_result.passed}",
                )
            else:
                contract_check_result = None

            history_entry: dict[str, Any] = {
                "iteration": iteration,
                "violations_before": [asdict(v) for v in violations],
                "violations_count_before": len(violations),
                "actions": [asdict(a) for a in repair_result.actions],
                "actions_count": len(repair_result.actions),
                "code_after": repair_result.code,
                "contract_passed": (
                    contract_check_result.passed if contract_check_result else None
                ),
            }
            repair_history.append(history_entry)
            current_code = repair_result.code

        sync_cb, pending_logs = _make_sync_log_collector()
        final_violations = cppcheck_scan(current_code, language=language, log_callback=sync_cb)
        await _flush_collected_logs(hook, pending_logs)

        if contract and contract_check_result is None:
            await hook("SYSTEM", "info", "契约校验（最终代码）")
            contract_check_result = contract_check(
                current_code, contract, cid="CON-001", language=language
            )
            level = "success" if contract_check_result.passed else "error"
            await hook(
                "SYSTEM",
                level,
                f"契约校验完成 passed={contract_check_result.passed}",
            )

        await hook(
            "REPAIR",
            "success",
            f"修复闭环完成 iterations={len(repair_history)} "
            f"final_violations={len(final_violations)}",
        )

        post_verification: dict[str, Any] = {}

        try:
            from skyforge_engine.tools.cbmc_verifier import run_cbmc_verification

            # CBMC 仅支持 C/C++，非 C 代码跳过
            cbmc_result = None
            if language in ("c", "cpp"):
                cbmc_result = run_cbmc_verification(current_code, unwind=10)
            else:
                await hook(
                    "SYSTEM",
                    "info",
                    f"CBMC: 跳过（语言={language}，仅支持 C/C++）",
                )
            if cbmc_result and cbmc_result.tool_available:
                post_verification["cbmc"] = {
                    "passed": cbmc_result.passed,
                    "status": cbmc_result.status,
                    "violations": len(cbmc_result.violations),
                    "time_ms": cbmc_result.time_ms,
                }
                await hook(
                    "SYSTEM",
                    "info",
                    f"CBMC: {'PASSED' if cbmc_result.passed else 'FAILED'} ({cbmc_result.time_ms:.0f}ms)",
                )
        except Exception as e:
            logger.debug(f"Pipeline:CBMC skipped: {e}")

        try:
            from skyforge_engine.tools.z3_verifier import verify_contract_constraints

            if contract:
                z3_result = verify_contract_constraints([], [{"expr": contract}])
                if z3_result.tool_available:
                    post_verification["z3"] = {
                        "satisfiable": z3_result.satisfiable,
                        "violations": z3_result.violations,
                    }
        except Exception as e:
            logger.debug(f"Pipeline:Z3 skipped: {e}")

        artifact["repair_result"] = {
            "final_code": current_code,
            "repair_history": repair_history,
            "final_violations": [asdict(v) for v in final_violations],
            "contract_check_result": (
                _check_result_to_dict(contract_check_result)
                if contract_check_result
                else None
            ),
            "post_verification": post_verification,
        }
        return StageResult(artifact=artifact, status="success")
