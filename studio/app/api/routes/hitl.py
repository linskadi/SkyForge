"""HITL 人工审查（Human-in-the-Loop）路由。

注意：与 HIL（Hardware-in-the-Loop 硬件在环，studio/app/digital_twin/）
无关。本文件实现的是"人在回路"的人工审批流程；为兼容现有调用方，
URL 路径沿用旧名 /api/hil/*（保持外部接口稳定）。

端点：
GET  /api/hil/status  获取 HITL 启用状态（轻量端点）
GET  /api/hil/pending 获取待审批请求
POST /api/hil/toggle  运行时切换 HITL 启用状态
POST /api/hil/approve 批准审批
POST /api/hil/reject  拒绝审批
GET  /api/hil/history 获取审批历史
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import require_write_access

from app.core.hil.hil_manager import get_hil_manager
from app.utils.log_util import logger

router = APIRouter()


class HITLApprovalRequest(BaseModel):
    """HITL 人工审查操作请求体。"""

    request_id: str
    comments: str = ""
    reviewer: str = "reviewer"


class HITLToggleRequest(BaseModel):
    """HITL 启用状态切换请求体。"""

    enabled: bool


@router.get("/api/hil/status")
async def get_hitl_status() -> dict[str, bool]:
    """获取 HITL 启用状态（轻量端点，不返回待审批列表）。

    Task 11: 独立端点，避免 getHITLStatus 获取完整列表仅取 enabled 字段。
    """
    mgr = get_hil_manager()
    return {"enabled": mgr.enabled}


@router.get("/api/hil/pending")
async def hitl_pending() -> dict[str, Any]:
    """获取所有待审批请求。"""
    manager = get_hil_manager()
    return {
        "pending": manager.get_pending_approvals(),
        "enabled": manager.enabled,
    }


@router.post("/api/hil/toggle")
async def hitl_toggle(
    req: HITLToggleRequest,
    _user: str = Depends(require_write_access),
) -> dict[str, Any]:
    """运行时切换 HITL 启用状态。

    默认禁用（HITL_ENABLED=false）。开启后，pipeline 在需求/契约/代码
    评审检查点会暂停等待人工审批（5 分钟超时自动批准）。
    """
    manager = get_hil_manager()
    manager.set_enabled(req.enabled)
    logger.info(f"/api/hil/toggle enabled={req.enabled}")
    return {"enabled": manager.enabled}


@router.post("/api/hil/approve")
async def hitl_approve(
    req: HITLApprovalRequest,
    _user: str = Depends(require_write_access),
) -> dict[str, Any]:
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
async def hitl_reject(
    req: HITLApprovalRequest,
    _user: str = Depends(require_write_access),
) -> dict[str, Any]:
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
async def hitl_history() -> dict[str, Any]:
    """获取所有已完成的审批历史。"""
    manager = get_hil_manager()
    history = manager.get_history()
    return {
        "history": history,
        "count": len(history),
    }
