"""机载软件生成路由：POST /api/generate 触发 Agent 流水线 + 修复闭环 + 数字孪生仿真，
POST /api/repair 单独触发修复，POST /api/check-contract 单独触发契约校验，
POST /api/simulate 单独触发数字孪生仿真，GET /api/fault-types 返回故障类型描述。

POST /api/report 生成 DO-178C 合规报告（HTML），GET /api/report/download 下载 HTML。

POST /api/compose 组合两个组件（DO-178C 6.5 可组合性验证），
POST /api/check-compatibility 单独检查契约兼容性。

GET /api/misra/search 搜索 MISRA-C 规则（RAG 知识库），
GET /api/misra/rule/{rule_id} 获取单条规则详情，
GET /api/misra/categories 获取规则分类统计。

WebSocket /ws/agent-stream 预留（Patch 4 接通）。
"""

from dataclasses import asdict
from datetime import datetime
from typing import Any

from fastapi import (
    APIRouter,
    Query,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel

from app.core.composable import (
    check_compatibility,
    compose,
    simulate_composition,
)
from app.core.digital_twin.fault_injector import FaultInjector
from app.core.digital_twin.simulation_engine import SimulationEngine
from app.core.hil.hil_manager import get_hil_manager
from app.core.llm.lmstudio_client import get_lmstudio_client
from app.core.llm.model_router import get_model_router
from app.core.pipeline import repair_loop, run_full_pipeline
from app.core.report import build_matrix, check_objectives, generate_report
from app.core.scade.lustre_parser import parse_glustre
from app.core.scade.lustre_to_requirement import convert, convert_to_contract
from app.core.streaming import get_stream_manager
from app.core.tools.contract_checker import check as contract_check
from app.rag.misra_searcher import MisraRuleSearcher
from app.utils.log_util import logger

router = APIRouter()


class GenerateRequest(BaseModel):
    """生成接口请求体。

    支持两种输入（至少其一）：
    - requirement：自然语言需求
    - scade_file：G-Lustre 文件内容（字符串）
    """

    requirement: str = ""
    scade_file: str = ""


class LlmSwitchRequest(BaseModel):
    """LLM 开关切换请求体。"""

    use_llm: bool


class ModelSelectRequest(BaseModel):
    """手动选择模型请求体。"""

    model_id: str


class HilApprovalRequest(BaseModel):
    """HIL 审批操作请求体。"""

    request_id: str
    comments: str = ""
    reviewer: str = "reviewer"


class RepairRequest(BaseModel):
    """修复接口请求体。"""

    code: str
    contract: str = ""
    max_iterations: int = 3
    req_id: str = "REQ-001"


class CheckContractRequest(BaseModel):
    """契约校验接口请求体。"""

    code: str
    contract: str
    cid: str = "CON-001"


class SimulateRequest(BaseModel):
    """数字孪生仿真接口请求体（Day 3）。"""

    code: str
    contract: str = ""
    fault_type: str | None = None
    fault_params: dict[str, Any] | None = None
    steps: int = 200


class ReportRequest(BaseModel):
    """DO-178C 合规报告生成接口请求体。

    pipeline_result 为 /api/generate 返回的全流程结果字典，至少包含：
    requirement / contract / code (或 final_code) / cppcheck_result /
    repair_history / final_violations / contract_check_result / simulation_result。
    """

    pipeline_result: dict[str, Any]


class ComponentSpec(BaseModel):
    """单个组件规格（代码 + 契约）。"""

    code: str
    contract: str


class ComposeRequest(BaseModel):
    """组件组合接口请求体（DO-178C 6.5 可组合性验证）。

    connection 支持：
    - sequential：A 的输出作为 B 的输入
    - parallel：A 和 B 并行执行
    - feedback：B 的输出反馈到 A
    """

    component_a: ComponentSpec
    component_b: ComponentSpec
    connection: str = "sequential"
    simulate: bool = True
    steps: int = 200


class CheckCompatibilityRequest(BaseModel):
    """契约兼容性检查接口请求体。"""

    contract_a: str
    contract_b: str
    connection: str = "sequential"


@router.post("/api/generate")
async def generate(req: GenerateRequest) -> dict[str, Any]:
    """接收自然语言需求（和/或 SCADE G-Lustre），编排完整流水线返回产物。

    支持两种输入（至少其一）：
    - requirement：自然语言需求
    - scade_file：G-Lustre 文件内容

    输入合并规则：
    - 同时提供两者：合并需求（原需求 + SCADE 转换需求）
    - 仅 scade_file：用 SCADE 转换后的需求
    - 仅 requirement：直接使用

    HIL 集成：在需求评审 / 契约评审 / 代码评审检查点暂停等待人工审批
    （HIL_ENABLED=false 时自动跳过，hil_approvals 中各项 status=skipped）。

    Args:
        req: 包含 requirement / scade_file 字段的请求体。

    Returns:
        包含 requirement / contract / code / cppcheck_result /
        repair_history / contract_check_result / simulation_result /
        hil_approvals 的字典。若提供 scade_file，额外返回
        scade_parsed / scade_contract 字段。
    """
    if not req.requirement and not req.scade_file:
        return {
            "error": "必须提供 requirement 或 scade_file 至少一项",
            "aborted": True,
            "abort_reason": "no_input",
        }

    req_preview = (
        req.requirement[:50]
        if req.requirement
        else f"<scade_file {len(req.scade_file)}B>"
    )
    logger.info(f"/api/generate 收到输入: {req_preview}...")
    result = await run_full_pipeline(
        requirement=req.requirement or None,
        scade_file=req.scade_file or None,
    )

    response: dict[str, Any] = {
        "requirement": result["requirement"],
        "contract": result["contract"],
        "code": result["final_code"],
        "cppcheck_result": [asdict(v) for v in result["cppcheck_result"]],
        "repair_history": result["repair_history"],
        "final_violations": result["final_violations"],
        "contract_check_result": result["contract_check_result"],
        "simulation_result": result.get("simulation_result"),
        "hil_approvals": result.get("hil_approvals", {}),
        "aborted": result.get("aborted", False),
        "abort_reason": result.get("abort_reason"),
    }
    # 透传 SCADE 解析结果（若提供 scade_file）
    if "scade_parsed" in result:
        response["scade_parsed"] = result["scade_parsed"]
        response["scade_contract"] = result.get("scade_contract")
    return response


@router.post("/api/upload-scade")
async def upload_scade(file: UploadFile) -> dict[str, Any]:
    """上传 G-Lustre 文件，解析并返回结构化结果。

    流程：
      1. 读取上传的 G-Lustre 文件内容
      2. 调 parse_glustre() 解析为 ParsedLustre
      3. 调 convert() 转换为自然语言需求
      4. 调 convert_to_contract() 转换为契约 YAML
      5. 返回 parsed + requirement + contract

    Args:
        file: UploadFile，G-Lustre 文件（.lus / .lustre / .scade）。

    Returns:
        dict：parsed（ParsedLustre 字典）/ requirement / contract / filename。
    """
    filename = file.filename or "unknown.lus"
    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content = content_bytes.decode("gbk", errors="replace")

    logger.info(f"/api/upload-scade 收到文件: {filename} ({len(content)} 字符)")

    parsed = parse_glustre(content)
    requirement = convert(parsed)
    contract = convert_to_contract(parsed)

    return {
        "filename": filename,
        "parsed": {
            "node_name": parsed.node_name,
            "inputs": [asdict(v) for v in parsed.inputs],
            "outputs": [asdict(v) for v in parsed.outputs],
            "locals": [asdict(v) for v in parsed.locals],
            "equations": [asdict(e) for e in parsed.equations],
            "raw_content": parsed.raw_content,
        },
        "requirement": requirement,
        "contract": contract,
    }


@router.post("/api/repair")
async def repair(req: RepairRequest) -> dict[str, Any]:
    """单独触发修复闭环：输入 C 代码，返回修复后代码 + 修复历史。

    Args:
        req: 包含 code / contract(可选) / max_iterations / req_id 的请求体。

    Returns:
        修复闭环结果：final_code / repair_history / final_violations /
        contract_check_result。
    """
    logger.info(
        f"/api/repair 收到代码 {len(req.code)} 字符，max_iterations={req.max_iterations}"
    )
    result = await repair_loop(
        code=req.code,
        contract=req.contract,
        max_iterations=req.max_iterations,
        req_id=req.req_id,
    )
    return result


@router.post("/api/check-contract")
async def check_contract(req: CheckContractRequest) -> dict[str, Any]:
    """单独触发契约校验：输入 C 代码 + 契约 YAML，返回校验结果 + 断言插桩代码。

    Args:
        req: 包含 code / contract / cid 的请求体。

    Returns:
        契约校验结果：passed / preconditions / postconditions / invariants /
        fault_handling / assert_code / violations。
    """
    logger.info(f"/api/check-contract 收到代码 {len(req.code)} 字符, cid={req.cid}")
    result = contract_check(req.code, req.contract, cid=req.cid)
    return {
        "passed": result.passed,
        "preconditions": [asdict(item) for item in result.preconditions],
        "postconditions": [asdict(item) for item in result.postconditions],
        "invariants": [asdict(item) for item in result.invariants],
        "fault_handling": [asdict(item) for item in result.fault_handling],
        "assert_code": result.assert_code,
        "violations": result.violations,
    }


@router.post("/api/simulate")
async def simulate(req: SimulateRequest) -> dict[str, Any]:
    """单独触发数字孪生仿真（Day 3）。

    输入 AI 生成的 C 代码 + 契约 YAML + 可选故障，返回完整仿真结果。

    Args:
        req: 包含 code / contract / fault_type / fault_params / steps 的请求体。

    Returns:
        SimulationResult 字典：passed / total_steps / fault_type /
        input_waveform / output_waveform / contract_violation / statistics /
        compilation / terminal_log。
    """
    logger.info(
        f"/api/simulate 收到代码 {len(req.code)} 字符, "
        f"fault_type={req.fault_type} steps={req.steps}"
    )
    engine = SimulationEngine()
    result = engine.run_simulation(
        code=req.code,
        contract_yaml=req.contract,
        fault_type=req.fault_type,
        fault_params=req.fault_params,
        steps=req.steps,
    )
    return result.to_dict()


@router.post("/api/compose")
async def compose_components(req: ComposeRequest) -> dict[str, Any]:
    """组件组合接口（DO-178C 6.5 可组合性验证）。

    接收两个组件（代码 + 契约）和连接方式，返回：
      - composed_code：组合后的 C 代码
      - composed_contract：组合后的契约 YAML
      - compatibility_check：兼容性检查结果
      - simulation_result：组合后仿真结果（req.simulate=True 时返回）

    Args:
        req: ComposeRequest 请求体。

    Returns:
        dict：composed_code / composed_contract / compatibility_check /
        simulation_result / warnings / connection。
    """
    logger.info(
        f"/api/compose 收到 connection={req.connection} "
        f"A_code={len(req.component_a.code)}B "
        f"B_code={len(req.component_b.code)}B"
    )

    composition = compose(
        component_a_code=req.component_a.code,
        component_a_contract=req.component_a.contract,
        component_b_code=req.component_b.code,
        component_b_contract=req.component_b.contract,
        connection=req.connection,
    )

    response: dict[str, Any] = {
        "composed_code": composition.composed_code,
        "composed_contract": composition.composed_contract,
        "compatibility_check": composition.compatibility_check,
        "warnings": composition.warnings,
        "connection": composition.connection,
    }

    if req.simulate:
        logger.info(f"/api/compose 启动组合仿真 steps={req.steps}")
        sim_result = simulate_composition(
            composed_code=composition.composed_code,
            composed_contract=composition.composed_contract,
            steps=req.steps,
        )
        response["simulation_result"] = sim_result.to_dict()

    return response


@router.post("/api/check-compatibility")
async def check_compat(req: CheckCompatibilityRequest) -> dict[str, Any]:
    """契约兼容性检查接口（DO-178C 6.5）。

    单独检查两个契约在指定连接方式下是否兼容，不进行代码组合或仿真。

    Args:
        req: CheckCompatibilityRequest 请求体。

    Returns:
        dict：compatible / checked_pairs / violations / warnings / connection。
    """
    logger.info(
        f"/api/check-compatibility 收到 connection={req.connection} "
        f"A={len(req.contract_a)}B B={len(req.contract_b)}B"
    )
    result = check_compatibility(
        contract_a_yaml=req.contract_a,
        contract_b_yaml=req.contract_b,
        connection=req.connection,
    )
    return result.to_dict()


@router.get("/api/fault-types")
async def fault_types() -> dict[str, Any]:
    """返回 5 类故障的描述和默认参数（Day 3）。

    Returns:
        {"fault_types": [...]}：每项含 type/name/desc/default_params/params_schema。
    """
    injector = FaultInjector()
    return {"fault_types": injector.get_fault_types()}


@router.get("/api/llm/status")
async def llm_status() -> dict[str, Any]:
    """查询 LM Studio 状态（不重启服务）。

    Returns:
        dict：available（bool）/ models（list[str]）/ use_llm（bool）。
    """
    client = get_lmstudio_client()
    return {
        "available": client.is_available(),
        "models": client.get_available_models(),
        "use_llm": client.use_llm,
    }


@router.post("/api/llm/switch")
async def llm_switch(req: LlmSwitchRequest) -> dict[str, Any]:
    """切换 USE_LLM 开关（不重启服务）。

    Args:
        req: 包含 use_llm 字段的请求体。

    Returns:
        dict：use_llm（切换后的值）/ available（切换后是否可用）。
    """
    client = get_lmstudio_client()
    client.use_llm = req.use_llm
    # 重置可用性缓存，使下次 is_available() 重新探测
    client._available = None
    available = client.is_available()
    logger.info(f"USE_LLM 已切换为 {req.use_llm}，available={available}")
    return {
        "use_llm": client.use_llm,
        "available": available,
    }


@router.post("/api/report")
async def report(req: ReportRequest) -> dict[str, Any]:
    """生成 DO-178C 合规报告（次级功能）。

    接收 /api/generate 返回的 pipeline_result，返回：
      - report_html：完整 HTML 报告（内嵌 CSS，可写入 .html 文件）
      - traceability_matrix：追溯矩阵 [TraceEntry.to_dict()]
      - do178_objectives：DO-178C Level C 12 项目标检查结果

    Args:
        req: 包含 pipeline_result 字段的请求体。

    Returns:
        dict：report_html / traceability_matrix / do178_objectives。
    """
    logger.info(
        f"/api/report 收到 pipeline_result keys={list(req.pipeline_result.keys())}"
    )
    pipeline_result = req.pipeline_result

    # 追溯矩阵
    matrix_entries = build_matrix(pipeline_result)
    traceability_matrix = [e.to_dict() for e in matrix_entries]

    # DO-178C 目标
    obj_results = check_objectives(pipeline_result)
    do178_objectives = [o.to_dict() for o in obj_results]

    # HTML 报告
    report_html = generate_report(pipeline_result)

    # 缓存到模块级变量，供 GET /api/report/download 直接拉取
    global _last_report_cache, _last_report_html
    _last_report_cache = pipeline_result
    _last_report_html = report_html

    return {
        "report_html": report_html,
        "traceability_matrix": traceability_matrix,
        "do178_objectives": do178_objectives,
    }


@router.get("/api/report/download")
async def report_download() -> Response:
    """下载 HTML 报告（返回 text/html）。

    从最近一次 POST /api/report 的缓存中读取 HTML 并返回；
    若缓存为空，则返回一段提示 HTML 引导先调用 POST /api/report。

    Returns:
        Response：Content-Type: text/html; charset=utf-8，attachment 下载。
    """
    global _last_report_html
    if _last_report_html:
        html = _last_report_html
    else:
        html = (
            "<html><body><h1>暂无可下载的报告</h1>"
            "<p>请先调用 <code>POST /api/report</code> 生成报告。</p></body></html>"
        )

    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="do178c_report.html"',
        },
    )


# 模块级缓存：保存最近一次 POST /api/report 的 pipeline_result + 生成的 HTML，
# 供 GET /api/report/download 使用。多实例部署时应替换为 Redis。
_last_report_cache: dict[str, Any] | None = None
_last_report_html: str | None = None


# ============================================================================ #
# 多模型路由 API
# ============================================================================ #


@router.get("/api/models")
async def list_models() -> dict[str, Any]:
    """列出 LM Studio 中所有可用模型（GET /api/models）。

    Returns:
        dict：models（list[dict]）/ selected（当前手动选择的模型 ID，可能为 None）。
    """
    router_ = get_model_router()
    models = router_.list_available_models()
    return {
        "models": models,
        "selected": router_._manual_selection,
    }


@router.post("/api/models/select")
async def select_model(req: ModelSelectRequest) -> dict[str, Any]:
    """手动选择模型（POST /api/models/select）。

    设置后将忽略任务类型自动路由，所有任务都使用该模型。
    传空字符串或调用 /api/models/clear 可恢复自动路由。

    Args:
        req: 包含 model_id 字段的请求体。

    Returns:
        dict：model_id（已设置的模型）/ model_info（模型信息）。
    """
    router_ = get_model_router()
    model_id = req.model_id or None
    router_.set_manual_selection(model_id)
    info = router_.get_model_info(req.model_id)
    logger.info(f"/api/models/select 设置为 {req.model_id}, loaded={info['loaded']}")
    return {
        "model_id": req.model_id,
        "model_info": info,
    }


@router.post("/api/models/clear")
async def clear_model_selection() -> dict[str, Any]:
    """清除手动模型选择，恢复自动路由（POST /api/models/clear）。

    Returns:
        dict：selected（清除后为 None）/ message。
    """
    router_ = get_model_router()
    router_.set_manual_selection(None)
    return {
        "selected": None,
        "message": "已清除手动选择，恢复任务类型自动路由",
    }


# ============================================================================ #
# HIL 人机协作 API
# ============================================================================ #


@router.get("/api/hil/pending")
async def hil_pending() -> dict[str, Any]:
    """获取所有待审批请求（GET /api/hil/pending）。

    Returns:
        dict：pending（list[dict]）/ enabled（HIL 是否启用）。
    """
    manager = get_hil_manager()
    return {
        "pending": manager.get_pending_approvals(),
        "enabled": manager.enabled,
    }


@router.post("/api/hil/approve")
async def hil_approve(req: HilApprovalRequest) -> dict[str, Any]:
    """批准指定审批请求（POST /api/hil/approve）。

    Args:
        req: 包含 request_id / comments(可选) / reviewer(可选) 的请求体。

    Returns:
        dict：审批结果。若 request_id 不存在或已处理，返回 error 字段。
    """
    manager = get_hil_manager()
    result = await manager.approve(
        request_id=req.request_id,
        comments=req.comments,
        reviewer=req.reviewer,
    )
    logger.info(f"/api/hil/approve {req.request_id} approved={result.get('approved')}")
    return result


@router.post("/api/hil/reject")
async def hil_reject(req: HilApprovalRequest) -> dict[str, Any]:
    """拒绝指定审批请求（POST /api/hil/reject）。

    Args:
        req: 包含 request_id / comments(可选) / reviewer(可选) 的请求体。

    Returns:
        dict：审批结果。若 request_id 不存在或已处理，返回 error 字段。
    """
    manager = get_hil_manager()
    result = await manager.reject(
        request_id=req.request_id,
        comments=req.comments,
        reviewer=req.reviewer,
    )
    logger.info(f"/api/hil/reject {req.request_id} approved={result.get('approved')}")
    return result


@router.get("/api/hil/history")
async def hil_history() -> dict[str, Any]:
    """获取所有已完成的审批历史（GET /api/hil/history）。

    Returns:
        dict：history（list[dict]）/ count（历史记录数）。
    """
    manager = get_hil_manager()
    history = manager.get_history()
    return {
        "history": history,
        "count": len(history),
    }


@router.websocket("/ws/agent-stream")
async def agent_stream(websocket: WebSocket) -> None:
    """Agent 流式推送 WebSocket（Patch 4 已接通 pipeline）。

    协议：
    1. 前端连接后发送 JSON：{"requirement": "...", "scade_file": "..."}
    2. 后端运行 run_full_pipeline，通过 log_hook 逐条推送 Agent 思考消息
    3. 流水线完成后推送 {"level": "complete", "result": {...}}
    4. 连接保持，可继续接收下一个生成请求

    消息格式（与前端 AgentTerminal.vue 对齐）：
    {
        "agent": "REQ-Parser" | "CON-Gen" | "CODE-Gen" | "REPAIR" |
                 "SYSTEM" | "TERMINAL",
        "level": "info" | "success" | "warn" | "error" | "complete",
        "thought": "消息内容",
        "time": "ISO 8601 时间戳"
    }

    完成消息额外包含 "result" 字段，携带完整 pipeline 产物。
    """
    await websocket.accept()
    stream_manager = get_stream_manager()
    ws_id = await stream_manager.register(websocket)
    logger.info(f"WebSocket /ws/agent-stream 连接建立 id={ws_id}")

    try:
        while True:
            # 等待前端发送生成请求
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning(f"WebSocket 接收消息异常: {e}")
                break

            if not isinstance(data, dict):
                data = {"requirement": str(data)}

            requirement = data.get("requirement", "") or ""
            scade_file = data.get("scade_file", "") or ""

            if not requirement and not scade_file:
                await websocket.send_json(
                    {
                        "agent": "SYSTEM",
                        "level": "error",
                        "thought": "必须提供 requirement 或 scade_file 至少一项",
                        "time": datetime.now().isoformat(),
                    }
                )
                continue

            req_preview = (
                requirement[:50] if requirement else f"<scade_file {len(scade_file)}B>"
            )
            logger.info(f"WebSocket /ws/agent-stream 收到请求: {req_preview}...")

            # 创建 log_hook，将日志推送到 WebSocket
            async def log_hook(agent_name: str, level: str, message: str) -> None:
                try:
                    await websocket.send_json(
                        {
                            "agent": agent_name,
                            "level": level,
                            "thought": message,
                            "time": datetime.now().isoformat(),
                        }
                    )
                except (WebSocketDisconnect, RuntimeError, ConnectionError):
                    # 连接已断开，忽略推送错误
                    pass

            # 运行 pipeline，传入 log_hook
            try:
                result = await run_full_pipeline(
                    requirement=requirement or None,
                    scade_file=scade_file or None,
                    log_hook=log_hook,
                )
                # 序列化结果：cppcheck_result 为 Violation dataclass 列表，
                # 需转为 dict 才能 JSON 序列化（与 /api/generate 行为一致）
                serializable_result = dict(result)
                if "cppcheck_result" in serializable_result:
                    serializable_result["cppcheck_result"] = [
                        asdict(v) for v in serializable_result["cppcheck_result"]
                    ]
                # 发送最终完成消息
                await websocket.send_json(
                    {
                        "agent": "SYSTEM",
                        "level": "complete",
                        "thought": "全流程完成",
                        "result": serializable_result,
                        "time": datetime.now().isoformat(),
                    }
                )
            except Exception as e:
                logger.error(f"WebSocket pipeline 异常: {e}")
                try:
                    await websocket.send_json(
                        {
                            "agent": "SYSTEM",
                            "level": "error",
                            "thought": f"流水线异常: {e}",
                            "time": datetime.now().isoformat(),
                        }
                    )
                except (WebSocketDisconnect, RuntimeError, ConnectionError):
                    pass
    except WebSocketDisconnect:
        logger.info(f"WebSocket /ws/agent-stream 断开 id={ws_id}")
    except Exception as e:
        logger.error(f"WebSocket /ws/agent-stream 异常: {e}")
    finally:
        await stream_manager.unregister(ws_id)
        logger.info(f"WebSocket /ws/agent-stream 连接清理 id={ws_id}")


# ============================================================================ #
# MISRA-C 规则检索 API（RAG 知识库）
# ============================================================================ #


@router.get("/api/misra/search")
async def misra_search(
    q: str = Query(
        ..., description="搜索关键词，如 'Rule 8.1' / '函数声明' / '动态内存'"
    ),
    top_k: int = Query(5, ge=1, le=50, description="返回最多 top_k 条规则"),
) -> dict[str, Any]:
    """搜索 MISRA-C 规则（GET /api/misra/search）。

    基于关键词匹配检索 MISRA-C:2012 规则。支持中文关键词、英文关键词、
    规则 ID（如 "Rule 8.1"）等多种查询方式。

    Args:
        q: 搜索关键词。
        top_k: 返回最多 top_k 条规则（1-50，默认 5）。

    Returns:
        dict：query / top_k / count / rules（list[dict]）。
    """
    searcher = MisraRuleSearcher.get_instance()
    results = searcher.search(q, top_k=top_k)
    return {
        "query": q,
        "top_k": top_k,
        "count": len(results),
        "rules": [r.to_dict() for r in results],
    }


@router.get("/api/misra/rule/{rule_id}")
async def misra_get_rule(rule_id: str) -> dict[str, Any]:
    """获取单条 MISRA-C 规则详情（GET /api/misra/rule/{rule_id}）。

    支持的 rule_id 格式：
    - "Rule 8.1" / "Dir 4.1"（标准格式，URL 中需 URL-encode 空格为 %20 或 +）
    - "8.1"（仅规则号，自动匹配 Rule 或 Dir）
    - "MISRA-C:2012-Rule-8.1"（带前缀）

    Args:
        rule_id: 规则 ID。

    Returns:
        dict：rule（MisraRule 字典）。若未找到，返回 found=false。
    """
    # URL 解码：FastAPI 自动解码 path 参数，但 + 可能不被解码为空格
    decoded = rule_id.replace("+", " ")
    searcher = MisraRuleSearcher.get_instance()
    rule = searcher.get_rule(decoded)
    if rule is None:
        return {"found": False, "rule_id": decoded, "rule": None}
    return {"found": True, "rule_id": decoded, "rule": rule.to_dict()}


@router.get("/api/misra/categories")
async def misra_categories() -> dict[str, Any]:
    """获取 MISRA-C 规则分类统计（GET /api/misra/categories）。

    Returns:
        dict：total / categories（list[dict]，每项含 category / count）/
        severity（list[dict]，每项含 severity / count）。
    """
    searcher = MisraRuleSearcher.get_instance()
    all_rules = searcher.get_all_rules()
    cat_summary = searcher.get_categories_summary()
    sev_summary = searcher.get_severity_summary()
    categories = [
        {"category": cat, "count": count}
        for cat, count in sorted(cat_summary.items(), key=lambda x: x[1], reverse=True)
    ]
    severity = [
        {"severity": sev, "count": count}
        for sev, count in sorted(sev_summary.items(), key=lambda x: x[1], reverse=True)
    ]
    return {
        "total": len(all_rules),
        "categories": categories,
        "severity": severity,
    }


@router.get("/api/misra/rules")
async def misra_list_rules(
    category: str | None = Query(None, description="按分类过滤"),
    limit: int = Query(0, ge=0, le=500, description="限制返回数量，0 表示全部"),
) -> dict[str, Any]:
    """列出 MISRA-C 规则（GET /api/misra/rules）。

    Args:
        category: 可选分类过滤（如 type/memory/control 等）。
        limit: 限制返回数量，0 表示返回全部（默认 0，最大 500）。

    Returns:
        dict：total / count / rules（list[dict]）。
    """
    searcher = MisraRuleSearcher.get_instance()
    if category:
        rules = searcher.get_rules_by_category(category)
    else:
        rules = searcher.get_all_rules()
    if limit > 0:
        rules = rules[:limit]
    return {
        "total": len(searcher.get_all_rules()),
        "count": len(rules),
        "rules": [r.to_dict() for r in rules],
    }
