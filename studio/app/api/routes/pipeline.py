"""Pipeline 编排路由：生成、上传 SCADE、仿真、故障类型。

POST /api/generate 触发完整 Agent 流水线
POST /api/upload-scade 上传 G-Lustre 文件
POST /api/simulate 单独触发数字孪生仿真
POST /api/verify 对契约执行形式化验证（Z3 + CBMC）
GET  /api/fault-types 返回故障类型描述
"""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.llm.mode_guard import require_tool, ToolNotFoundError

from skyforge_engine.digital_twin.fault_injector import FaultInjector
from skyforge_engine.digital_twin.simulation_engine import SimulationEngine
from skyforge_engine.scade.lustre_parser import parse_glustre
from skyforge_engine.scade.lustre_to_requirement import convert, convert_to_contract
from app.services.task_service import get_task_service
from app.utils.log_util import logger

router = APIRouter()


class GenerateRequest(BaseModel):
    """生成接口请求体。支持 requirement 和/或 scade_file。"""

    requirement: str = ""
    scade_file: str = ""
    language: str = "c"  # 目标语言: c, cpp, python


class SimulateRequest(BaseModel):
    """数字孪生仿真接口请求体。"""

    code: str
    contract: str = ""
    fault_type: str | None = None
    fault_params: dict[str, Any] | None = None
    steps: int = 200


class VerifyRequest(BaseModel):
    """形式化验证接口请求体。

    支持两种契约输入方式：
    - contract: 契约文本（YAML 或 JSON 字符串）
    - contract_path: 契约文件路径（服务端读取，优先级低于 contract）

    可选 code: C 代码文本（提供后启用 CBMC 有界模型检查）
    """

    contract: str | None = None
    contract_path: str | None = None
    code: str | None = None


@router.post("/api/generate")
async def generate(req: GenerateRequest) -> dict[str, Any]:
    """接收自然语言需求（和/或 SCADE G-Lustre），编排完整流水线返回产物。

    HIL 集成：在需求/契约/代码评审检查点暂停等待人工审批
    （HIL_ENABLED=false 时自动跳过）。
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
    service = get_task_service()
    created = await service.create(
        requirement=req.requirement or f"SCADE input ({len(req.scade_file)} bytes)",
        scade_file=req.scade_file or None,
        language=req.language,
        profile_id="local",
        idempotency_key=f"legacy-http-{uuid4().hex}",
    )
    detail = await service.wait(created["id"])
    if detail is None:
        return {"error": "task disappeared", "aborted": True}
    # Task 13: 使用 .get() 避免 KeyError
    result = detail.get("result") or {}
    if not result and detail.get("status") in ("error", "cancelled", "timeout"):
        # 失败任务直接返回错误信息
        return {
            "error": detail.get("error", "task failed"),
            "status": detail.get("status"),
            "aborted": True,
            "task_id": created["id"],
        }

    response: dict[str, Any] = {
        "requirement": result.get("requirement"),
        "contract": result.get("contract"),
        "code": result.get("final_code"),
        "cppcheck_result": result.get("cppcheck_result", []),
        "repair_history": result.get("repair_history", []),
        "final_violations": result.get("final_violations", []),
        "contract_check_result": result.get("contract_check_result", {}),
        "simulation_result": result.get("simulation_result"),
        "coverage_result": result.get("coverage_result") or {},
        "hil_approvals": result.get("hil_approvals", {}),
        "aborted": result.get("aborted", False),
        "abort_reason": result.get("abort_reason"),
        "task_id": created["id"],
        "provenance": detail.get("provenance"),
    }
    if "scade_parsed" in result:
        response["scade_parsed"] = result["scade_parsed"]
        response["scade_contract"] = result.get("scade_contract")
    return response


@router.post("/api/upload-scade")
async def upload_scade(file: UploadFile) -> dict[str, Any]:
    """上传 G-Lustre 文件，解析并返回结构化结果。"""
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


@router.post("/api/simulate")
async def simulate(req: SimulateRequest) -> dict[str, Any]:
    """单独触发数字孪生仿真。"""
    logger.info(
        f"/api/simulate 收到代码 {len(req.code)} 字符, "
        f"fault_type={req.fault_type} steps={req.steps}"
    )
    engine = SimulationEngine()
    result = await engine.run_simulation_async(
        code=req.code,
        contract_yaml=req.contract,
        fault_type=req.fault_type,
        fault_params=req.fault_params,
        steps=req.steps,
    )
    return result.to_dict()


@router.get("/api/fault-types")
async def fault_types() -> dict[str, Any]:
    """返回 5 类故障的描述和默认参数。"""
    injector = FaultInjector()
    return {"fault_types": injector.get_fault_types()}


@router.post("/api/verify")
async def verify(req: VerifyRequest) -> dict[str, Any]:
    """对契约执行形式化验证（Z3 SMT + CBMC 有界模型检查）。

    Returns:
        {
            "status": "passed|failed|skipped",
            "summary": {total, passed, failed, skipped},
            "checks": [{name, status, duration_ms, counter_example, tool}],
            "total_duration_ms": int,
            "tool": "Z3|CBMC|Z3+CBMC"
        }
    """

    from skyforge_engine.tools.contract_formal_verifier import verify_contract

    # 解析契约文本：优先 contract，其次 contract_path
    contract_text = req.contract
    if not contract_text and req.contract_path:
        from app.utils.common_utils import safe_resolve_workdir
        try:
            path = safe_resolve_workdir(req.contract_path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"illegal contract_path: {exc}")
        if not path.exists():
            logger.warning(f"/api/verify 契约文件不存在: {path}")
            return {
                "status": "skipped",
                "summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
                "checks": [],
                "total_duration_ms": 0,
                "tool": "Mock",
                "error": f"contract file not found: {req.contract_path}",
            }
        contract_text = path.read_text(encoding="utf-8")

    if not contract_text:
        logger.warning("/api/verify 未提供契约数据")
        return {
            "status": "skipped",
            "summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
            "checks": [],
            "total_duration_ms": 0,
            "tool": "Mock",
            "error": "no contract provided",
        }

    logger.info(
        f"/api/verify 收到契约 ({len(contract_text)} 字符), "
        f"code={'provided' if req.code else 'none'}"
    )

    # 检查工具可用性
    missing_tools = []
    try:
        require_tool("z3")
    except ToolNotFoundError:
        missing_tools.append("z3")
    try:
        require_tool("cbmc")
    except ToolNotFoundError:
        missing_tools.append("cbmc")

    if len(missing_tools) == 2:
        return JSONResponse(
            status_code=503,
            content={
                "error": "形式化验证工具未安装",
                "missing_tools": missing_tools,
            },
        )

    # 调用底层 verify_contract
    verification = verify_contract(contract_text, code=req.code)

    # 转换为结构化 checks 列表（与 CLI 共用语义，但格式独立以避免循环依赖）
    checks = _build_verification_checks_api(verification)

    passed = sum(1 for c in checks if c["status"] == "passed")
    failed = sum(1 for c in checks if c["status"] == "failed")
    skipped = sum(1 for c in checks if c["status"] == "skipped")
    total = len(checks)
    overall = "failed" if failed > 0 else ("passed" if passed > 0 else "skipped")
    total_duration_ms = sum(c["duration_ms"] for c in checks)

    # 工具标签
    tools = []
    if verification.z3_available:
        tools.append("Z3")
    if verification.cbmc_available:
        tools.append("CBMC")
    tool_label = "+".join(tools) if tools else "Mock"

    return {
        "status": overall,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        },
        "checks": checks,
        "total_duration_ms": total_duration_ms,
        "tool": tool_label,
    }


def _build_verification_checks_api(verification) -> list[dict[str, Any]]:
    """将 VerificationResult 转换为 API 响应的 checks 列表。

    与 CLI 的 _build_verification_checks 保持语义一致，但独立实现
    以避免 cli.py 与 API 路由的循环依赖。
    """
    checks: list[dict[str, Any]] = []

    # Check 1: Z3 约束一致性
    if verification.z3_available:
        counter_example = None
        status = "passed"
        if not verification.is_consistent:
            status = "failed"
            counter_example = (
                "; ".join(verification.contradictions)
                if verification.contradictions
                else "约束不可同时满足"
            )
        checks.append({
            "name": "Constraint consistency",
            "tool": "Z3",
            "status": status,
            "duration_ms": int(verification.z3_solver_time_ms or 0),
            "counter_example": counter_example,
        })
    else:
        checks.append({
            "name": "Constraint consistency",
            "tool": "Z3",
            "status": "skipped",
            "duration_ms": 0,
            "counter_example": "Z3 不可用（pip install z3-solver 启用）",
        })

    # Check 2: Z3 边界测试用例生成
    if verification.z3_available:
        if verification.test_case_count > 0:
            status = "passed"
            counter_example = None
        elif not verification.is_consistent:
            status = "skipped"
            counter_example = "契约不一致，跳过测试用例生成"
        else:
            status = "skipped"
            counter_example = "无可解析的数值边界条件"
        checks.append({
            "name": "Boundary test case generation",
            "tool": "Z3",
            "status": status,
            "duration_ms": 0,
            "counter_example": counter_example,
        })
    else:
        checks.append({
            "name": "Boundary test case generation",
            "tool": "Z3",
            "status": "skipped",
            "duration_ms": 0,
            "counter_example": "Z3 不可用",
        })

    # Check 3: CBMC 有界模型检查
    if verification.cbmc_available:
        if verification.cbmc_verified:
            status = "passed"
            counter_example = None
        else:
            status = "failed"
            counter_example = (
                verification.cbmc_output[:500]
                if verification.cbmc_output
                else "CBMC 验证未通过"
            )
        checks.append({
            "name": "Bounded model checking",
            "tool": "CBMC",
            "status": status,
            "duration_ms": int(verification.cbmc_time_ms or 0),
            "counter_example": counter_example,
        })
    else:
        checks.append({
            "name": "Bounded model checking",
            "tool": "CBMC",
            "status": "skipped",
            "duration_ms": 0,
            "counter_example": "CBMC 不可用（requires CBMC）",
        })

    return checks
