"""组件组合验证路由（DO-178C 6.5 可组合性）。

POST /api/compose 组合两个组件
POST /api/check-compatibility 单独检查契约兼容性
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.composable import check_compatibility, compose, simulate_composition
from app.utils.log_util import logger

router = APIRouter()


class ComponentSpec(BaseModel):
    """单个组件规格（代码 + 契约）。"""

    code: str
    contract: str


class ComposeRequest(BaseModel):
    """组件组合接口请求体。"""

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


@router.post("/api/compose")
async def compose_components(req: ComposeRequest) -> dict[str, Any]:
    """组件组合接口（DO-178C 6.5 可组合性验证）。

    接收两个组件（代码 + 契约）和连接方式，返回组合后的代码、契约和兼容性检查结果。
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
    """契约兼容性检查接口（DO-178C 6.5）。"""
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
