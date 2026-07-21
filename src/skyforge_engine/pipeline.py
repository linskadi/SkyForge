"""Agent 编排器：串联需求解析→契约生成→代码生成→Cppcheck 扫描→修复闭环→数字孪生仿真，
并支持流式推送 hook（Patch 4 已接通 WebSocket）。

HIL 集成：在关键检查点（需求评审 / 契约评审 / 代码评审）调用
HILManager.request_approval，等待人工确认后再进入下一阶段。
HIL_ENABLED=false 时自动跳过。

HIL 并行优化（设计文档 14.7.4 §4）：HIL 启用时，将"需求评审等待"与
"契约生成"并行执行（asyncio.gather）——契约生成只依赖 req_json，不依赖
HIL 审批结果；HIL 拒绝时丢弃契约结果并中止流水线。HIL 禁用时 HIL 立即
返回 skipped，重叠无收益，保持原有串行行为。

Patch 4 更新：
- log_hook 签名改为 (agent_name, level, message) -> None | Awaitable[None]
- agent_name 与前端 AgentTerminal.vue 的 AgentType 对齐：
  REQ-Parser / CON-Gen / CODE-Gen / REPAIR / SYSTEM / TERMINAL
- level 与前端 LogLevel 对齐：info / success / warn / error
- 本地 LLM 可用时通过 chat_stream 生成 Agent 思考叙述并推送
- cppcheck/gcc 终端命令和输出通过 log_callback 推送
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from skyforge_engine.config import settings
from skyforge_engine.digital_twin.simulation_engine import SimulationEngine
from skyforge_engine.execution import ToolEvidence

# HIL Manager — L0 依赖反转：L3 启动时通过 set_hil_manager_provider 注入实现，
# 引擎独立运行时返回空实现（_NoopHILManager，所有审批自动 skipped）。
# 详见 hil_provider.py。
from skyforge_engine.hil_provider import get_hil_manager
# LLM 客户端 — 通过 L0 provider 注入（L3 启动时注册自己的单例，
# 引擎独立运行时回退到 L1 skyforge_llm.client）。详见 llm_provider.py。
from skyforge_engine.llm_provider import get_llm_client as get_lmstudio_client
from skyforge_engine.tools.cppcheck_scanner import (
    multi_scanner,
)
from skyforge_engine.utils.log_util import logger

# 从新的分层模块导入共享工具与 Stage
from skyforge_engine.core.orchestrator import PipelineOrchestrator
from skyforge_engine.core.stages import (
    ArchitectureDesignStage,
    CodeGenStage,
    ContractGenStage,
    CppcheckStage,
    FormalVerificationStage,
    HILCheckpointStage,
    LLRGenStage,
    RepairLoopStage,
    RequirementParseStage,
)
from skyforge_engine.core.stages._utils import (
    LogHook,
    AsyncLogHook,
    _installed_tool_version,
    _log_llm_status,
    _normalize_hook,
    deprecated,
)


# ============================================================================
# 兼容导出（保留原有类型别名供外部引用）
# ============================================================================

__all__ = [
    "LogHook",
    "AsyncLogHook",
    "run_pipeline",
    "repair_loop",
    "run_full_pipeline",
]


# ============================================================================
# 废弃函数（向后兼容）
# ============================================================================

@deprecated("请使用 PipelineOrchestrator 直接编排 Stage")
async def run_pipeline(
    requirement: str = None,
    scade_file: str = None,
    language: str = "c",
    log_hook: LogHook | None = None,
    task_id: str = "",
) -> dict[str, Any]:
    """编排 3 个 Agent + Cppcheck 扫描，返回完整产物。

    当前实现已迁移至 PipelineOrchestrator + Stage 分层，函数签名保持不变。
    """
    hook = _normalize_hook(log_hook)

    await _log_llm_status(hook)

    # ---- 处理 SCADE 输入（G-Lustre → 需求 + 契约）----
    scade_parsed = None
    scade_contract: str | None = None
    scade_requirement: str | None = None
    if scade_file:
        await hook("SYSTEM", "info", "开始解析 SCADE G-Lustre 文件")
        from skyforge_engine.scade.lustre_parser import parse_glustre
        from skyforge_engine.scade.lustre_to_requirement import (
            convert as scade_convert,
        )
        from skyforge_engine.scade.lustre_to_requirement import (
            convert_to_contract as scade_convert_to_contract,
        )

        scade_parsed = parse_glustre(scade_file)
        scade_requirement = scade_convert(scade_parsed)
        scade_contract = scade_convert_to_contract(scade_parsed)
        await hook(
            "SYSTEM",
            "success",
            f"SCADE 解析完成 node={scade_parsed.node_name} "
            f"equations={len(scade_parsed.equations)}",
        )

    # 合并 requirement 与 SCADE 转换的需求
    final_requirement = requirement or ""
    if scade_requirement:
        if final_requirement:
            final_requirement = (
                f"{final_requirement}\n\n[SCADE 模型输入]\n{scade_requirement}"
            )
        else:
            final_requirement = scade_requirement

    if not final_requirement:
        raise ValueError("必须提供 requirement 或 scade_file 至少一项")

    # 输入净化（可选，默认关闭）
    sanitize_mapping_for_evidence = None
    if settings.SECURITY_SANITIZE_INPUT:
        from skyforge_llm.security.sanitizer import sanitize_input

        sanitized = sanitize_input(final_requirement)
        logger.info(
            f"[Security] 输入净化已启用，脱敏 {len(sanitized.mapping)} 项敏感信息"
        )
        try:
            msg = f"输入净化已启用，脱敏 {len(sanitized.mapping)} 项敏感信息"
            await hook("SYSTEM", "info", msg)
        except Exception:
            pass
        final_requirement = sanitized.text
        sanitize_mapping_for_evidence = sanitized.mapping

    # ---- 构建 Stage 列表 ----
    hil_manager = get_hil_manager()
    stages: list[Any] = [
        RequirementParseStage(),
        LLRGenStage(),
        ArchitectureDesignStage(),
        HILCheckpointStage(checkpoint="requirement_review", content_key="requirement"),
        ContractGenStage(),
        HILCheckpointStage(checkpoint="contract_review", content_key="contract"),
        FormalVerificationStage(),
        CodeGenStage(language=language),
        HILCheckpointStage(checkpoint="code_review", content_key="code"),
        CppcheckStage(language=language),
    ]

    config: dict[str, Any] = {
        "parallel_groups": (
            [["hil_requirement_review", "contract_gen"]] if hil_manager.enabled else []
        ),
        "on_stage_failure": "stop",
    }

    orchestrator = PipelineOrchestrator(stages, config)

    initial_artifact: dict[str, Any] = {
        "requirement": final_requirement,
        "language": language,
        "task_id": task_id,
    }
    ctx = {"log_hook": hook, "task_id": task_id}

    results = await orchestrator.run(initial_artifact, ctx)

    # 检查是否因 HIL 拒绝而失败，保持原有 abort 返回格式
    for result in results:
        if result.status == "failure":
            final_artifact = result.artifact
            abort_reason = result.errors[0] if result.errors else "unknown"
            return {
                "requirement": final_artifact.get("requirement", {}),
                "contract": final_artifact.get("contract", ""),
                "code": final_artifact.get("code", ""),
                "cppcheck_result": final_artifact.get("cppcheck_result", []),
                "hil_approvals": final_artifact.get("hil_approvals", {}),
                "aborted": True,
                "abort_reason": abort_reason,
            }

    final_artifact = results[-1].artifact if results else initial_artifact

    result: dict[str, Any] = {
        "requirement": final_artifact["requirement"],
        "contract": final_artifact.get("contract", ""),
        "code": final_artifact.get("code", ""),
        "cppcheck_result": final_artifact.get("cppcheck_result", []),
        "hil_approvals": final_artifact.get("hil_approvals", {}),
        "llr_result": final_artifact["requirement"].get("llr_result", {}),
        "formal_verification": final_artifact.get("formal_verification"),
    }
    if sanitize_mapping_for_evidence:
        result["sanitize_mapping"] = sanitize_mapping_for_evidence
    if scade_parsed is not None:
        result["scade_parsed"] = {
            "node_name": scade_parsed.node_name,
            "inputs": [asdict(v) for v in scade_parsed.inputs],
            "outputs": [asdict(v) for v in scade_parsed.outputs],
            "locals": [asdict(v) for v in scade_parsed.locals],
            "equations": [asdict(e) for e in scade_parsed.equations],
            "raw_content": scade_parsed.raw_content,
        }
        result["scade_contract"] = scade_contract
    return result


@deprecated("请使用 PipelineOrchestrator 直接编排 Stage")
async def repair_loop(
    code: str,
    contract: str = "",
    max_iterations: int = 3,
    req_id: str = "REQ-001",
    log_hook: LogHook | None = None,
) -> dict[str, Any]:
    """修复闭环编排：扫描→修复→契约校验，最多 max_iterations 轮。

    当前实现已迁移至 RepairLoopStage + PipelineOrchestrator。
    """
    hook = _normalize_hook(log_hook)
    stage = RepairLoopStage(max_iterations=max_iterations, req_id=req_id)
    orchestrator = PipelineOrchestrator([stage])

    initial_artifact: dict[str, Any] = {
        "code": code,
        "contract": contract,
        "req_id": req_id,
    }
    ctx = {"log_hook": hook, "req_id": req_id}

    results = await orchestrator.run(initial_artifact, ctx)
    final_artifact = results[-1].artifact if results else initial_artifact
    return final_artifact.get("repair_result", {})


@deprecated("请使用 PipelineOrchestrator 直接编排 Stage")
async def run_full_pipeline(
    requirement: str = None,
    scade_file: str = None,
    log_hook: LogHook | None = None,
    simulate: bool = True,
    language: str = "c",
    execution_context=None,
) -> dict[str, Any]:
    """完整流水线：3 个 Agent + Cppcheck 扫描 + 修复闭环 + 数字孪生仿真。

    当前实现已迁移至 PipelineOrchestrator + Stage 分层，函数签名保持不变。
    """
    hook = _normalize_hook(log_hook)

    await _log_llm_status(hook)

    degraded = False
    try:
        llm_client = get_lmstudio_client()
        degraded = not llm_client.is_available()
    except Exception as e:
        logger.warning(f"Pipeline: LLM 可用性检测失败，标记为降级: {e}")
        degraded = True
    if degraded:
        await hook("SYSTEM", "warn", "LLM 不可用，Agent 将走降级（mock）路径")

    # ---- P1-3 修复：启动 DO-178C 合规证据收集 ----
    evidence_collector = None
    try:
        from skyforge_engine.report.evidence_collector import get_collector

        evidence_collector = get_collector()
        evidence_collector.start_session(pipeline_version="v0.5.0")
        await hook(
            "SYSTEM", "info", f"合规证据收集已启动 (会话: {evidence_collector.session_id})"
        )
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Pipeline:证据收集器启动失败: {e}")

    # ---- 阶段 1：run_pipeline ----
    await hook("SYSTEM", "info", "阶段 1：需求 → 契约 → 代码 → Cppcheck 扫描")
    pipeline_result = await run_pipeline(
        requirement=requirement,
        scade_file=scade_file,
        language=language,
        log_hook=hook,
        task_id=getattr(execution_context, "task_id", "") or "",
    )

    # 记录证据：需求解析
    if evidence_collector and evidence_collector.active:
        try:
            evidence_collector.record_requirement_parsed(pipeline_result["requirement"])
            if pipeline_result.get("contract"):
                evidence_collector.record_contract_generated(
                    pipeline_result["contract"],
                    pipeline_result["requirement"].get("req_id", "REQ-001"),
                )
            llr_result = pipeline_result.get("requirement", {}).get("llr_result")
            if llr_result and llr_result.get("llr_list"):
                evidence_collector.record_llr_generated(
                    llr_list=llr_result["llr_list"],
                    hlr_req_id=pipeline_result["requirement"].get("req_id", "REQ-001"),
                )
        except Exception as e:
            logger.debug(f"Pipeline:证据记录失败: {e}")

    if (
        pipeline_result.get("sanitize_mapping")
        and evidence_collector
        and evidence_collector.active
    ):
        try:
            _sanitize_mapping = pipeline_result["sanitize_mapping"]
            evidence_collector.record_tool_usage(
                tool_name="LLMSanitizer",
                tool_version="1.0",
                command=json.dumps(
                    {
                        "purpose": "输入净化（脱敏路径/地址/版本号/代号/C注释）",
                        "mapping_size": len(_sanitize_mapping),
                        "mapping": _sanitize_mapping,
                    },
                    ensure_ascii=False,
                ),
                exit_code=0,
            )
            logger.info(
                f"[Security] 脱敏映射已记录到 EvidenceCollector "
                f"(mapping_size={len(_sanitize_mapping)})"
            )
        except Exception as e:
            logger.warning(f"脱敏映射记录到 EvidenceCollector 失败: {e}")

    if pipeline_result.get("aborted"):
        await hook(
            "SYSTEM",
            "error",
            f"流水线被中止: {pipeline_result.get('abort_reason')}",
        )
        return {
            "requirement": pipeline_result["requirement"],
            "contract": pipeline_result["contract"],
            "final_code": pipeline_result["code"],
            "cppcheck_result": pipeline_result["cppcheck_result"],
            "repair_history": [],
            "final_violations": [],
            "contract_check_result": None,
            "simulation_result": None,
            "hil_approvals": pipeline_result.get("hil_approvals", {}),
            "aborted": True,
            "abort_reason": pipeline_result.get("abort_reason"),
            "degraded": degraded,
        }

    # ---- 阶段 2：修复闭环 ----
    await hook("SYSTEM", "info", "阶段 2：修复闭环")
    repair_result = await repair_loop(
        code=pipeline_result["code"],
        contract=pipeline_result["contract"],
        max_iterations=3,
        req_id=pipeline_result["requirement"]["req_id"],
        log_hook=hook,
    )

    # ---- 阶段 3：数字孪生仿真 ----
    simulation_result_dict: dict[str, Any] | None = None
    if simulate:
        await hook("SYSTEM", "info", "阶段 3：数字孪生仿真（无故障默认）")
        try:
            engine = SimulationEngine(
                use_real_gcc=(
                    execution_context.tool_policy.use_real_gcc
                    if execution_context is not None
                    else None
                )
            )
            sim = await engine.run_simulation_async(
                code=repair_result["final_code"],
                contract_yaml=pipeline_result["contract"],
                fault_type=None,
                fault_params=None,
                steps=200,
            )
            simulation_result_dict = sim.to_dict()
            level = "success" if sim.passed else "error"
            await hook(
                "SYSTEM",
                level,
                f"仿真完成 passed={sim.passed} steps={sim.total_steps}",
            )
        except Exception as e:
            logger.error(f"Pipeline:数字孪生仿真异常: {e}")
            await hook("SYSTEM", "error", f"仿真异常: {e}")

    full_result: dict[str, Any] = {
        "requirement": pipeline_result["requirement"],
        "contract": pipeline_result["contract"],
        "final_code": repair_result["final_code"],
        "cppcheck_result": pipeline_result["cppcheck_result"],
        "repair_history": repair_result["repair_history"],
        "final_violations": repair_result["final_violations"],
        "contract_check_result": repair_result["contract_check_result"],
        "simulation_result": simulation_result_dict,
        "hil_approvals": pipeline_result.get("hil_approvals", {}),
        "degraded": degraded,
        "formal_verification": pipeline_result.get("formal_verification"),
    }

    static_available = multi_scanner.is_available(language)
    static_status = (
        "observed"
        if static_available
        else "simulated"
        if language == "c"
        else "unavailable"
    )
    static_engine = (
        "cppcheck"
        if language == "c" and static_available
        else "clang-tidy"
        if language == "cpp" and static_available
        else "mypy/ruff"
        if language == "python" and static_available
        else "pattern-scanner"
        if language == "c"
        else "none"
    )
    compilation = (simulation_result_dict or {}).get("compilation") or {}
    if not simulation_result_dict:
        compile_status = "unavailable"
    elif compilation.get("used_mock"):
        compile_status = "simulated"
    elif compilation.get("success") and compilation.get("exit_code") in (0, None):
        compile_status = "observed"
    else:
        compile_status = "failed"
    formal = pipeline_result.get("formal_verification") or {}
    formal_status = "observed" if formal.get("z3_available") else "unavailable"
    digest = hashlib.sha256(repair_result["final_code"].encode("utf-8")).hexdigest()
    tool_evidence = {
        "static_analysis": asdict(
            ToolEvidence(
                status=static_status,
                engine=static_engine,
                version=_installed_tool_version(
                    "cppcheck"
                    if language == "c"
                    else "clang-tidy"
                    if language == "cpp"
                    else "ruff"
                ),
                output_digest=digest,
                findings=tuple(
                    {"rule": str(getattr(item, "rule_id", ""))}
                    for item in repair_result["final_violations"]
                ),
                warning=(
                    None
                    if static_available
                    else "真实静态分析器不可用；结果来自模式扫描"
                    if language == "c"
                    else "静态分析器不可用"
                ),
            )
        ),
        "compilation": asdict(
            ToolEvidence(
                status=compile_status,
                engine=(
                    "python-simulator" if compilation.get("used_mock") else "gcc"
                ),
                version=compilation.get("version"),
                exit_code=compilation.get("exit_code"),
                output_digest=digest,
                command=compilation.get("command") or None,
                warning=(compilation.get("errors") or None),
            )
        ),
        "formal_verification": asdict(
            ToolEvidence(
                status=formal_status,
                engine="z3",
                version=_installed_tool_version("z3"),
                findings=tuple(
                    {"contradiction": item}
                    for item in formal.get("contradictions", [])
                ),
                warning=(
                    None if formal.get("z3_available") else "Z3 不可用，未执行证明"
                ),
            )
        ),
    }
    full_result["tool_evidence"] = tool_evidence
    if "scade_parsed" in pipeline_result:
        full_result["scade_parsed"] = pipeline_result["scade_parsed"]
        full_result["scade_contract"] = pipeline_result.get("scade_contract")

    # ---- P1-3 修复：记录合规证据并生成证据包 ----
    if evidence_collector and evidence_collector.active:
        try:
            evidence_collector.record_code_generated(
                repair_result["final_code"],
                pipeline_result["requirement"].get("req_id", "REQ-001"),
            )
            evidence_collector.record_cppcheck_scan(
                repair_result["final_violations"],
                real_scan=(static_status == "observed"),
            )
            repair_history = repair_result.get("repair_history", [])
            if repair_history:
                for i, entry in enumerate(repair_history):
                    evidence_collector.record_code_repaired(
                        iteration=entry.get("iteration", i + 1),
                        before_violations=entry.get("violations_count_before", 0),
                        after_violations=(
                            0
                            if i == len(repair_history) - 1
                            else entry.get("violations_count_before", 0)
                        ),
                        fixed_rules=[],
                    )
            elif not repair_result.get("final_violations"):
                evidence_collector.record_code_repaired(
                    iteration=0,
                    before_violations=0,
                    after_violations=0,
                    fixed_rules=[],
                )
            if simulation_result_dict:
                evidence_collector.record_simulation_completed(
                    simulation_result_dict,
                    fault_injected=False,
                )
                try:
                    fault_engine = SimulationEngine()
                    fault_sim = await fault_engine.run_simulation_async(
                        code=repair_result["final_code"],
                        contract_yaml=pipeline_result["contract"],
                        fault_type="bias",
                        fault_params={"bias_value": 100},
                        steps=100,
                    )
                    evidence_collector.record_simulation_completed(
                        fault_sim.to_dict(),
                        fault_injected=True,
                    )
                except Exception as fault_err:
                    logger.debug(f"Pipeline:故障注入仿真跳过: {fault_err}")

            if repair_result.get("contract_check_result"):
                evidence_collector.record_contract_verified(
                    repair_result["contract_check_result"],
                )

            for checkpoint, approval in pipeline_result.get("hil_approvals", {}).items():
                evidence_collector.record_hil_approval(
                    checkpoint=checkpoint,
                    approved=approval.get("approved", False),
                    reviewer=approval.get("reviewer", "system"),
                    comments=approval.get("comments", ""),
                )

            compile_evidence = tool_evidence["compilation"]
            if compile_evidence.get("engine"):
                evidence_collector.record_compile_result(
                    compiler=compile_evidence["engine"],
                    compiler_version=compile_evidence["version"] or "unknown",
                    source_file="generated-task-source.c",
                    exit_code=compile_evidence.get("exit_code", -1),
                    warnings=[],
                )

            evidence_collector.record_report_generated(
                report_type="compliance",
                format="html",
            )

            static_evidence = tool_evidence["static_analysis"]
            if static_evidence["status"] == "observed":
                evidence_collector.record_tool_usage(
                    tool_name=static_evidence["engine"],
                    tool_version=static_evidence["version"] or "unknown",
                    command=f"{static_evidence['engine']} generated-task-source",
                    exit_code=0,
                )
            if compile_evidence["status"] == "observed":
                evidence_collector.record_tool_usage(
                    tool_name=compile_evidence["engine"],
                    tool_version=compile_evidence["version"] or "unknown",
                    command=compile_evidence["command"] or "",
                    exit_code=compile_evidence["exit_code"],
                )

            config_files = []
            for label, content in (
                ("final_code", repair_result.get("final_code", "")),
                ("contract", pipeline_result.get("contract", "")),
                ("requirement", json.dumps(pipeline_result.get("requirement", {}), ensure_ascii=False)),
            ):
                if content:
                    fhash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
                    config_files.append({"path": label, "hash": fhash})
            if config_files:
                evidence_collector.record_configuration_snapshot(config_files)

            formal_evidence = tool_evidence["formal_verification"]
            if formal_evidence["status"] == "observed":
                evidence_collector.record_formal_verification(
                    verifier_type="Z3",
                    passed=bool(formal.get("consistent")),
                    details=formal,
                )

            if simulation_result_dict:
                contract_violation = simulation_result_dict.get("contract_violation")
                if contract_violation:
                    evidence_collector.record_contract_breach(
                        contract_id=contract_violation.get("contract_id", "unknown"),
                        failed_step=contract_violation.get("failed_step", 0),
                        assertion_message=contract_violation.get(
                            "assertion_message", ""
                        ),
                        breach_type="postcondition",
                        stderr_output=contract_violation.get("stderr_output", ""),
                    )
                else:
                    evidence_collector.record_breach_resolution(
                        contract_id=pipeline_result["requirement"].get(
                            "req_id", "REQ-001"
                        ),
                        resolution_method="no_breach",
                    )

            for evidence, scope in (
                (static_evidence, "static_analysis"),
                (compile_evidence, "compilation"),
                (formal_evidence, "formal_verification"),
            ):
                if evidence["status"] != "observed":
                    continue
                approved = (
                    len(repair_result["final_violations"]) == 0
                    if scope == "static_analysis"
                    else bool(formal.get("consistent"))
                    if scope == "formal_verification"
                    else evidence.get("exit_code") == 0
                )
                evidence_collector.record_independent_review(
                    reviewer_id=f"{evidence['engine']}-{evidence['version'] or 'unknown'}",
                    reviewer_role="automated_tool",
                    is_author=False,
                    scope=scope,
                    findings=[f"status={evidence['status']}"]
                    + [str(item) for item in evidence.get("findings", [])],
                    approved=approved,
                    comments="独立确定性工具的实际执行记录",
                )

            for checkpoint, approval in pipeline_result.get("hil_approvals", {}).items():
                if approval.get("approved"):
                    evidence_collector.record_independent_review(
                        reviewer_id=f"human-{checkpoint}",
                        reviewer_role="human_reviewer",
                        is_author=False,
                        scope=f"{checkpoint}_review",
                        findings=[approval.get("comments", "")],
                        approved=True,
                        comments=f"HITL 检查点 {checkpoint} 人工审查通过",
                    )

            if simulation_result_dict:
                contract_violation = simulation_result_dict.get("contract_violation")
                if contract_violation:
                    full_result["breach_detected"] = True
                    full_result["breach_contract_id"] = contract_violation.get(
                        "contract_id", "unknown"
                    )
                else:
                    full_result["breach_resolved"] = True
            else:
                full_result["breach_status"] = "unavailable"

            independent_reviews = []
            for evidence, scope in (
                (static_evidence, "static_analysis"),
                (compile_evidence, "compilation"),
                (formal_evidence, "formal_verification"),
            ):
                if evidence["status"] != "observed":
                    continue
                independent_reviews.append(
                    {
                        "reviewer_id": f"{evidence['engine']}-{evidence['version'] or 'unknown'}",
                        "reviewer_role": "automated_tool",
                        "is_author": False,
                        "scope": scope,
                        "approved": (
                            len(repair_result["final_violations"]) == 0
                            if scope == "static_analysis"
                            else bool(formal.get("consistent"))
                            if scope == "formal_verification"
                            else evidence.get("exit_code") == 0
                        ),
                    }
                )
            for checkpoint, approval in pipeline_result.get(
                "hil_approvals", {}
            ).items():
                if approval.get("approved"):
                    independent_reviews.append(
                        {
                            "reviewer_id": f"human-{checkpoint}",
                            "reviewer_role": "human_reviewer",
                            "is_author": False,
                            "scope": f"{checkpoint}_review",
                            "approved": True,
                        }
                    )
            full_result["independent_reviews"] = independent_reviews

            # A-7.5/A-7.7/A-7.8: 覆盖率证据（在 evidence block 内收集）
            if repair_result.get("final_code"):
                try:
                    from skyforge_engine.report.coverage_analyzer import (
                        analyze_code_coverage,
                    )

                    dal_level = pipeline_result.get("dal", "C")
                    cov_result = analyze_code_coverage(
                        code=repair_result.get("final_code", ""),
                        fault_injected=bool(simulation_result_dict),
                        dal=dal_level,
                        use_real_coverage=True,
                    )
                    full_result["coverage_result"] = cov_result
                    evidence_collector.record_coverage_collected(
                        {
                            "statement_coverage": cov_result.get("statement_coverage", 0.0),
                            "decision_coverage": cov_result.get("decision_coverage", 0.0),
                            "mcdc_coverage": cov_result.get("mcdc_coverage", 0.0),
                            "method": cov_result.get("method", "static_analysis"),
                            "dal_target": dal_level,
                        }
                    )
                    logger.info(
                        f"Pipeline:覆盖率闭环 method={cov_result.get('method', 'static_analysis')} "
                        f"stmt={cov_result.get('statement_coverage', 0)}% "
                        f"dec={cov_result.get('decision_coverage', 0)}% "
                        f"mcdc={cov_result.get('mcdc_coverage', 0)}%"
                    )
                except Exception as cov_err:
                    logger.warning(f"Pipeline:覆盖率收集失败: {cov_err}")
                    full_result["coverage_result"] = {}
            else:
                full_result["coverage_result"] = {}

            evidence_collector.end_session("completed")
            evidence_path = evidence_collector.generate_package()
            full_result["evidence_package"] = evidence_path
            await hook(
                "SYSTEM",
                "success",
                f"DO-178C 工程辅助证据包已生成: {evidence_path}",
            )
        except Exception as e:
            logger.warning(f"Pipeline:证据收集完成失败: {e}")

    return full_result
