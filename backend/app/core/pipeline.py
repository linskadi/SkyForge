"""Agent 编排器：串联需求解析→契约生成→代码生成→Cppcheck 扫描→修复闭环→数字孪生仿真，
并支持流式推送 hook（Patch 4 已接通 WebSocket）。

HIL 集成：在关键检查点（需求评审 / 契约评审 / 代码评审）调用
HILManager.request_approval，等待人工确认后再进入下一阶段。
HIL_ENABLED=false 时自动跳过。

Patch 4 更新：
- log_hook 签名改为 (agent_name, level, message) -> None | Awaitable[None]
- agent_name 与前端 AgentTerminal.vue 的 AgentType 对齐：
  REQ-Parser / CON-Gen / CODE-Gen / REPAIR / SYSTEM / TERMINAL
- level 与前端 LogLevel 对齐：info / success / warn / error
- LM Studio 可用时通过 chat_stream 生成 Agent 思考叙述并推送
- cppcheck/gcc 终端命令和输出通过 log_callback 推送
"""

import inspect
import json
from dataclasses import asdict
from typing import Any, Awaitable, Callable, Union

from app.core.agents.code_generator_agent import CodeGeneratorAgent
from app.core.agents.code_repairer_agent import CodeRepairerAgent
from app.core.agents.contract_generator_agent import ContractGeneratorAgent
from app.core.agents.requirement_parser_agent import RequirementParserAgent
from app.core.digital_twin.simulation_engine import SimulationEngine
from app.core.hil.hil_manager import get_hil_manager
from app.core.llm.lmstudio_client import get_lmstudio_client
from app.core.tools.contract_checker import CheckResult, check as contract_check
from app.core.tools.cppcheck_scanner import Violation, scan as cppcheck_scan
from app.utils.log_util import logger

# 流式推送 hook 类型（Patch 4 已接通 WebSocket）
# 签名：(agent_name: str, level: str, message: str) -> None | Awaitable[None]
# - agent_name：REQ-Parser / CON-Gen / CODE-Gen / REPAIR / SYSTEM / TERMINAL
#   （与前端 AgentTerminal.vue 的 AgentType 对齐）
# - level：info / success / warn / error（与前端 LogLevel 对齐）
# - message：推送的思考内容或终端输出
LogHook = Callable[[str, str, str], Union[None, Awaitable[None]]]

# 归一化后的 async hook 类型
AsyncLogHook = Callable[[str, str, str], Awaitable[None]]


async def _default_hook(agent_name: str, level: str, message: str) -> None:
    """默认日志 hook：输出到 logger。"""
    logger.info(f"[Pipeline] {agent_name}[{level}]: {message}")


def _normalize_hook(log_hook: LogHook | None) -> AsyncLogHook:
    """归一化 hook 为 async 形式，兼容 sync / async / None。

    Args:
        log_hook: 调用方传入的 hook，可为 sync / async / None。

    Returns:
        统一的 async hook，签名为 (agent_name, level, message) -> Awaitable[None]。
    """
    if log_hook is None:
        return _default_hook
    if inspect.iscoroutinefunction(log_hook):
        return log_hook

    # sync hook：包装为 async
    async def _wrapper(agent_name: str, level: str, message: str) -> None:
        log_hook(agent_name, level, message)

    return _wrapper


def _make_sync_log_collector() -> tuple[
    Callable[[str, str, str], None], list[tuple[str, str, str]]
]:
    """创建一个同步 log_callback，收集消息供后续异步推送。

    用于把 sync 的 cppcheck_scan / VirtualMCU.compile/run 终端日志
    收集起来，待 sync 调用返回后再通过 async hook 推送到 WebSocket。

    Returns:
        (callback, messages)：callback 是同步回调，messages 是收集到的
        (agent, level, message) 元组列表。
    """
    messages: list[tuple[str, str, str]] = []

    def callback(agent: str, level: str, message: str) -> None:
        messages.append((agent, level, message))

    return callback, messages


async def _flush_collected_logs(
    hook: AsyncLogHook, messages: list[tuple[str, str, str]]
) -> None:
    """将收集到的同步日志通过 async hook 推送。"""
    for agent, level, msg in messages:
        await hook(agent, level, msg)


async def _push_agent_thought(
    hook: AsyncLogHook, agent_name: str, context_desc: str
) -> None:
    """推送一条 Agent 思考消息。

    LM Studio 可用时通过 chat_stream 生成简短叙述（流式生成、整条推送），
    不可用时推送 fallback 静态消息（保证 WebSocket 有内容可推）。

    Args:
        hook: 已归一化的 async hook。
        agent_name: 前端 AgentType 名称。
        context_desc: 上下文描述（fallback 文案 / LLM prompt）。
    """
    client = get_lmstudio_client()
    if client.is_available():
        try:
            thought = ""
            async for token in client.chat_stream(
                prompt=(
                    "你是航空软件工程 Agent。用一句话（不超过 50 字）"
                    f"简述你即将执行的任务：{context_desc}"
                ),
                max_tokens=80,
            ):
                thought += token
            thought = thought.strip() or context_desc
            await hook(agent_name, "info", thought)
            return
        except Exception as e:
            logger.warning(f"Pipeline:LLM 流式思考生成失败，降级为静态文案: {e}")
    await hook(agent_name, "info", context_desc)


async def _log_llm_status(hook: AsyncLogHook) -> None:
    """记录 LM Studio 状态（使用真实 LLM 还是 Mock）。

    Args:
        hook: 已归一化的 async hook。
    """
    client = get_lmstudio_client()
    if client.is_available():
        models = client.get_available_models()
        await hook(
            "SYSTEM",
            "info",
            f"LM Studio 可用，已加载模型: {models}（将使用真实 LLM 推理）",
        )
        logger.info(f"[Pipeline] 使用真实 LLM，已加载模型: {models}")
    else:
        await hook(
            "SYSTEM",
            "info",
            "LM Studio 不可用或 USE_LLM=false，使用 Mock 模式",
        )
        logger.info("[Pipeline] 使用 Mock 模式（LM Studio 不可用或 USE_LLM=false）")


async def _run_hil_checkpoint(
    checkpoint: str,
    content: str,
    hook: AsyncLogHook,
    timeout: int = 300,
) -> dict[str, Any]:
    """在 HIL 检查点请求人工审批，返回审批结果字典。

    HIL_ENABLED=false 时直接返回 approved=True（status=skipped）。

    Args:
        checkpoint: 检查点名称（requirement_review / contract_review / code_review）。
        content: 待审批内容（需求 JSON / 契约 YAML / 代码字符串）。
        hook: 已归一化的 async hook。
        timeout: 审批超时时间（秒）。

    Returns:
        审批结果字典：{approved, comments, reviewer, timestamp, status, ...}
    """
    manager = get_hil_manager()
    await hook("SYSTEM", "info", f"{checkpoint}:等待人工审批")
    result = await manager.request_approval(
        checkpoint=checkpoint,
        content=content,
        timeout=timeout,
    )
    status_str = result.get("status", "approved")
    approved = result.get("approved", False)
    level = "success" if approved else "error"
    await hook(
        "SYSTEM",
        level,
        f"{checkpoint}:审批完成 status={status_str} approved={approved}",
    )
    return result


async def run_pipeline(
    requirement: str = None,
    scade_file: str = None,
    log_hook: LogHook | None = None,
) -> dict[str, Any]:
    """编排 3 个 Agent + Cppcheck 扫描，返回完整产物。

    支持两种输入：
    - requirement：自然语言需求字符串
    - scade_file：G-Lustre 文件内容（字符串）

    输入合并规则：
    - 同时有 requirement 和 scade_file：将 SCADE 转换的需求与原需求合并
    - 只有 scade_file：用转换后的需求作为输入
    - 只有 requirement：直接使用 requirement
    - 两者都为空：抛出 ValueError

    HIL 集成：在需求解析后、契约生成后、代码生成后分别调用 HIL 检查点
    （requirement_review / contract_review / code_review），等待人工确认。
    HIL_ENABLED=false 时跳过审批。

    Args:
        requirement: 自然语言需求字符串（可选）。
        scade_file: G-Lustre 文件内容字符串（可选）。
        log_hook: 流式推送回调 (agent_name, level, message)，
            支持 sync / async / None。

    Returns:
        包含 requirement / contract / code / cppcheck_result /
        hil_approvals 的字典。若提供 scade_file，额外包含
        scade_parsed / scade_contract 字段。
    """
    hook = _normalize_hook(log_hook)
    hil_approvals: dict[str, dict[str, Any]] = {}

    # 记录 LM Studio 状态（使用真实 LLM 还是 Mock）
    await _log_llm_status(hook)

    # ---- 处理 SCADE 输入（G-Lustre → 需求 + 契约）----
    scade_parsed = None
    scade_contract: str | None = None
    scade_requirement: str | None = None
    if scade_file:
        await hook("SYSTEM", "info", "开始解析 SCADE G-Lustre 文件")
        from app.core.scade.lustre_parser import parse_glustre
        from app.core.scade.lustre_to_requirement import (
            convert as scade_convert,
        )
        from app.core.scade.lustre_to_requirement import (
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

    # ---- Agent 1：需求解析 ----
    await _push_agent_thought(
        hook,
        "REQ-Parser",
        "需求解析 Agent 启动：解析自然语言需求并生成结构化需求标签",
    )
    parser = RequirementParserAgent()
    req_json = await parser.run(final_requirement)
    await hook(
        "REQ-Parser",
        "success",
        f"需求解析完成 req_id={req_json['req_id']}",
    )

    # ---- HIL 检查点 1：需求评审 ----
    hil_approvals["requirement_review"] = await _run_hil_checkpoint(
        checkpoint="requirement_review",
        content=json.dumps(req_json, ensure_ascii=False, indent=2),
        hook=hook,
    )
    if not hil_approvals["requirement_review"].get("approved", False):
        await hook("SYSTEM", "error", "需求评审未通过，流水线终止")
        return {
            "requirement": req_json,
            "contract": "",
            "code": "",
            "cppcheck_result": [],
            "hil_approvals": hil_approvals,
            "aborted": True,
            "abort_reason": "requirement_review rejected",
        }

    # ---- Agent 2：契约生成 ----
    # Agent 依据合并后的需求生成契约；SCADE 转换的契约作为独立字段返回（scade_contract）
    await _push_agent_thought(
        hook,
        "CON-Gen",
        "契约生成 Agent 启动：依据需求生成 DO-178C 契约 YAML",
    )
    contract_agent = ContractGeneratorAgent()
    contract = await contract_agent.run(req_json)
    await hook("CON-Gen", "success", "契约生成完成")

    # ---- HIL 检查点 2：契约评审 ----
    hil_approvals["contract_review"] = await _run_hil_checkpoint(
        checkpoint="contract_review",
        content=contract,
        hook=hook,
    )
    if not hil_approvals["contract_review"].get("approved", False):
        await hook("SYSTEM", "error", "契约评审未通过，流水线终止")
        return {
            "requirement": req_json,
            "contract": contract,
            "code": "",
            "cppcheck_result": [],
            "hil_approvals": hil_approvals,
            "aborted": True,
            "abort_reason": "contract_review rejected",
        }

    # ---- Agent 3：代码生成 ----
    await _push_agent_thought(
        hook,
        "CODE-Gen",
        "代码生成 Agent 启动：依据需求和契约生成 MISRA-C 合规代码",
    )
    code_agent = CodeGeneratorAgent()
    code = await code_agent.run(req_json, contract)
    await hook("CODE-Gen", "success", "C 代码生成完成")

    # ---- HIL 检查点 3：代码评审 ----
    hil_approvals["code_review"] = await _run_hil_checkpoint(
        checkpoint="code_review",
        content=code,
        hook=hook,
    )
    if not hil_approvals["code_review"].get("approved", False):
        await hook("SYSTEM", "error", "代码评审未通过，流水线终止")
        return {
            "requirement": req_json,
            "contract": contract,
            "code": code,
            "cppcheck_result": [],
            "hil_approvals": hil_approvals,
            "aborted": True,
            "abort_reason": "code_review rejected",
        }

    # ---- Patch 1：Cppcheck 查改解耦（仅扫描，修复在 Patch 1 后续触发）----
    await hook("SYSTEM", "info", "启动 Cppcheck MISRA-C 扫描")
    sync_cb, pending_logs = _make_sync_log_collector()
    cppcheck_result = cppcheck_scan(code, log_callback=sync_cb)
    await _flush_collected_logs(hook, pending_logs)
    level = "success" if not cppcheck_result else "warn"
    await hook(
        "SYSTEM",
        level,
        f"Cppcheck 扫描完成 violations={len(cppcheck_result)}",
    )

    result: dict[str, Any] = {
        "requirement": req_json,
        "contract": contract,
        "code": code,
        "cppcheck_result": cppcheck_result,
        "hil_approvals": hil_approvals,
    }
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


async def repair_loop(
    code: str,
    contract: str = "",
    max_iterations: int = 3,
    req_id: str = "REQ-001",
    log_hook: LogHook | None = None,
) -> dict[str, Any]:
    """修复闭环编排（Day 2）：扫描→修复→契约校验，最多 max_iterations 轮。

    流程：
      1. 调 cppcheck_scanner.scan(code) 得违规列表
      2. 若无违规 → 跳出循环
      3. 调 code_repairer_agent.repair(code, violations) 得修复代码
      4. 调 contract_checker.check(修复代码, contract) 验证契约仍满足
      5. code = 修复代码，回到步骤 1（最多 max_iterations 轮）

    Args:
        code: 待修复的 C 代码字符串。
        contract: .contract YAML 文本（用于契约校验，可为空字符串跳过校验）。
        max_iterations: 最大修复轮次（默认 3）。
        req_id: 关联的 [REQ-xxx] 追溯 Tag。
        log_hook: 流式推送回调 (agent_name, level, message)，
            支持 sync / async / None。

    Returns:
        dict：{final_code, repair_history, final_violations, contract_check_result}
    """
    hook = _normalize_hook(log_hook)
    repairer = CodeRepairerAgent()
    current_code = code
    repair_history: list[dict[str, Any]] = []
    final_violations: list[Violation] = []
    contract_check_result: CheckResult | None = None

    await hook("REPAIR", "info", f"修复闭环启动 max_iterations={max_iterations}")

    for iteration in range(1, max_iterations + 1):
        # 步骤 1：扫描
        await hook("REPAIR", "info", f"第 {iteration} 轮：扫描违规")
        sync_cb, pending_logs = _make_sync_log_collector()
        violations = cppcheck_scan(current_code, log_callback=sync_cb)
        await _flush_collected_logs(hook, pending_logs)
        final_violations = violations

        # 步骤 2：若无违规 → 跳出循环
        if not violations:
            await hook("REPAIR", "success", f"第 {iteration} 轮：无违规，跳出循环")
            break

        await hook(
            "REPAIR",
            "warn",
            f"第 {iteration} 轮：检出 {len(violations)} 条违规",
        )

        # 步骤 3：修复
        await _push_agent_thought(
            hook,
            "REPAIR",
            f"第 {iteration} 轮修复 Agent 启动：针对 {len(violations)} 条 MISRA 违规进行修复",
        )
        repair_result = await repairer.repair(current_code, violations, req_id=req_id)
        await hook(
            "REPAIR",
            "success",
            f"第 {iteration} 轮：修复完成 actions={len(repair_result.actions)}",
        )

        # 步骤 4：契约校验（若提供契约）
        if contract:
            await hook("SYSTEM", "info", f"第 {iteration} 轮：契约校验")
            contract_check_result = contract_check(
                repair_result.code, contract, cid="CON-001"
            )
            level = "success" if contract_check_result.passed else "error"
            await hook(
                "SYSTEM",
                level,
                f"第 {iteration} 轮：契约校验完成 passed={contract_check_result.passed}",
            )
        else:
            contract_check_result = None

        # 步骤 5：记录历史 + 更新 code
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

    # 最终再扫描一次，得到最终违规列表
    sync_cb, pending_logs = _make_sync_log_collector()
    final_violations = cppcheck_scan(current_code, log_callback=sync_cb)
    await _flush_collected_logs(hook, pending_logs)
    await hook(
        "REPAIR",
        "success",
        f"修复闭环完成 iterations={len(repair_history)} "
        f"final_violations={len(final_violations)}",
    )

    return {
        "final_code": current_code,
        "repair_history": repair_history,
        "final_violations": [asdict(v) for v in final_violations],
        "contract_check_result": (
            _check_result_to_dict(contract_check_result)
            if contract_check_result
            else None
        ),
    }


def _check_result_to_dict(result: CheckResult) -> dict[str, Any]:
    """将 CheckResult 转为可序列化字典（供 API 返回）。"""
    return {
        "passed": result.passed,
        "preconditions": [asdict(item) for item in result.preconditions],
        "postconditions": [asdict(item) for item in result.postconditions],
        "invariants": [asdict(item) for item in result.invariants],
        "fault_handling": [asdict(item) for item in result.fault_handling],
        "assert_code": result.assert_code,
        "violations": result.violations,
    }


async def run_full_pipeline(
    requirement: str = None,
    scade_file: str = None,
    log_hook: LogHook | None = None,
    simulate: bool = True,
) -> dict[str, Any]:
    """完整流水线（Day 3）：3 个 Agent + Cppcheck 扫描 + 修复闭环 + 数字孪生仿真。

    在 run_pipeline + repair_loop 之后增加仿真步骤：
      1. run_pipeline(requirement, scade_file) 生成需求/契约/代码/cppcheck 结果
      2. repair_loop(code, contract) 修复违规 + 契约校验
      3. SimulationEngine.run_simulation(final_code, contract) 数字孪生仿真

    支持两种输入（至少其一）：
    - requirement：自然语言需求
    - scade_file：G-Lustre 文件内容

    Args:
        requirement: 自然语言需求字符串（可选）。
        scade_file: G-Lustre 文件内容字符串（可选）。
        log_hook: 流式推送回调 (agent_name, level, message)，
            支持 sync / async / None。
        simulate: 是否执行数字孪生仿真（默认 True，可关闭以加速）。

    Returns:
        完整流水线产物字典，包含：
        - requirement / contract / code / cppcheck_result
        - repair_history / final_violations / contract_check_result
        - simulation_result（SimulationResult.to_dict()，simulate=False 时为 None）
        - hil_approvals（HIL 各检查点审批结果）
        - aborted（HIL 拒绝时为 True，标识流水线被中止）
        - scade_parsed / scade_contract（提供 scade_file 时返回）
    """
    hook = _normalize_hook(log_hook)

    # 记录 LM Studio 状态（使用真实 LLM 还是 Mock）
    await _log_llm_status(hook)

    # ---- 阶段 1：3 个 Agent + Cppcheck 扫描（含 HIL 检查点）----
    await hook("SYSTEM", "info", "阶段 1：需求 → 契约 → 代码 → Cppcheck 扫描")
    pipeline_result = await run_pipeline(
        requirement=requirement, scade_file=scade_file, log_hook=hook
    )

    # 若 HIL 拒绝导致流水线中止，直接返回（不进入修复 / 仿真阶段）
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
            engine = SimulationEngine()
            sim = engine.run_simulation(
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
    }
    # 透传 SCADE 解析结果（若 run_pipeline 阶段解析过）
    if "scade_parsed" in pipeline_result:
        full_result["scade_parsed"] = pipeline_result["scade_parsed"]
        full_result["scade_contract"] = pipeline_result.get("scade_contract")
    return full_result
