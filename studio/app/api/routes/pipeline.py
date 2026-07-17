"""Pipeline 编排路由：生成、上传 SCADE、修复、契约校验、仿真、故障类型。

POST /api/generate 触发完整 Agent 流水线
POST /api/upload-scade 上传 G-Lustre 文件
POST /api/repair 单独触发修复闭环
POST /api/check-contract 单独触发契约校验
POST /api/simulate 单独触发数字孪生仿真
POST /api/verify 对契约执行形式化验证（Z3 + CBMC）
GET  /api/fault-types 返回故障类型描述
"""

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel

from skyforge_engine.digital_twin.fault_injector import FaultInjector
from skyforge_engine.digital_twin.simulation_engine import SimulationEngine
from skyforge_engine.pipeline import repair_loop, run_full_pipeline
from skyforge_engine.scade.lustre_parser import parse_glustre
from skyforge_engine.scade.lustre_to_requirement import convert, convert_to_contract
from skyforge_engine.tools.contract_checker import check as contract_check
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
        f"/api/repair 收到代码 {len(req.code)} 字符，"
        f"max_iterations={req.max_iterations}"
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


@router.post("/api/verify")
async def verify(req: VerifyRequest) -> dict[str, Any]:
    """对契约执行形式化验证（Z3 SMT + CBMC 有界模型检查）。

    Mock 模式（Z3/CBMC 均不可用）下，所有检查项自动降级为 skipped，
    保证接口始终可用。

    Returns:
        {
            "status": "passed|failed|skipped",
            "summary": {total, passed, failed, skipped},
            "checks": [{name, status, duration_ms, counter_example, tool}],
            "total_duration_ms": int,
            "tool": "Z3|CBMC|Z3+CBMC|Mock"
        }
    """
    from pathlib import Path

    from skyforge_engine.tools.contract_formal_verifier import verify_contract

    # 解析契约文本：优先 contract，其次 contract_path
    contract_text = req.contract
    if not contract_text and req.contract_path:
        path = Path(req.contract_path)
        if not path.exists():
            logger.warning(f"/api/verify 契约文件不存在: {req.contract_path}")
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

    # 调用底层 verify_contract（Mock 模式下自动降级）
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
