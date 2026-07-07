"""Pipeline 编排路由：生成、上传 SCADE、修复、契约校验、仿真、故障类型。

POST /api/generate 触发完整 Agent 流水线
POST /api/upload-scade 上传 G-Lustre 文件
POST /api/repair 单独触发修复闭环
POST /api/check-contract 单独触发契约校验
POST /api/simulate 单独触发数字孪生仿真
GET  /api/fault-types 返回故障类型描述
"""

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel

from app.core.composable import simulate_composition
from app.core.digital_twin.fault_injector import FaultInjector
from app.core.digital_twin.simulation_engine import SimulationEngine
from app.core.pipeline import repair_loop, run_full_pipeline
from app.core.scade.lustre_parser import parse_glustre
from app.core.scade.lustre_to_requirement import convert, convert_to_contract
from app.core.tools.contract_checker import check as contract_check
from app.utils.log_util import logger

router = APIRouter()


class GenerateRequest(BaseModel):
    """生成接口请求体。支持 requirement 和/或 scade_file。"""

    requirement: str = ""
    scade_file: str = ""


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
    """数字孪生仿真接口请求体。"""

    code: str
    contract: str = ""
    fault_type: str | None = None
    fault_params: dict[str, Any] | None = None
    steps: int = 200


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


@router.post("/api/repair")
async def repair(req: RepairRequest) -> dict[str, Any]:
    """单独触发修复闭环：输入 C 代码，返回修复后代码 + 修复历史。"""
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
    """单独触发契约校验：输入 C 代码 + 契约 YAML，返回校验结果 + 断言插桩代码。"""
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
