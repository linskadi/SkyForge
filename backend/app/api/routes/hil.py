"""人机协作（HIL）路由：审批流程管理。

GET  /api/hil/pending 获取待审批请求
POST /api/hil/approve 批准审批
POST /api/hil/reject 拒绝审批
GET  /api/hil/history 获取审批历史
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.hil.hil_manager import get_hil_manager
from app.utils.log_util import logger

router = APIRouter()


class HilApprovalRequest(BaseModel):
    """HIL 审批操作请求体。"""

    request_id: str
    comments: str = ""
    reviewer: str = "reviewer"


@router.get("/api/hil/pending")
async def hil_pending() -> dict[str, Any]:
    """获取所有待审批请求。"""
    manager = get_hil_manager()
    return {
        "pending": manager.get_pending_approvals(),
        "enabled": manager.enabled,
    }


@router.post("/api/hil/approve")
async def hil_approve(req: HilApprovalRequest) -> dict[str, Any]:
    """批准指定审批请求。"""
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
    """拒绝指定审批请求。"""
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
    """获取所有已完成的审批历史。"""
    manager = get_hil_manager()
    history = manager.get_history()
    return {
        "history": history,
        "count": len(history),
    }
