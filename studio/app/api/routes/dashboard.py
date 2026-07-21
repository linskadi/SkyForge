"""Dashboard 聚合统计 API。

提供 Dashboard 页面所需的最近任务、系统状态、合规率趋势、统计指标数据。
"""

import shutil
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.llm.local_llm_client import get_local_llm_client
from app.db import get_db
from app.models.task import Task
from app.repositories import task_history_repo
from app.utils.log_util import logger

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/recent-tasks")
async def get_recent_tasks(
    limit: int = 20, db: Session = Depends(get_db)
) -> list[dict]:
    """返回最近 N 条任务记录。"""
    tasks = task_history_repo.list_recent(db, limit=limit)
    return [
        {
            "id": t.id,
            "requirement": t.requirement,
            "language": t.language,
            "status": t.status,
            "violation_count": t.violation_count,
            "stage_reached": t.stage_reached,
            "duration_ms": t.duration_ms,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]


@router.get("/system-status")
async def get_system_status(db: Session = Depends(get_db)) -> dict:
    """返回系统状态聚合信息：后端 + LLM + 工具链 + 持久化。"""
    # 后端状态（端点能响应即 online）
    backend_status = "online"

    # LLM 状态
    llm_info: dict = {
        "mode": "unknown",
        "provider": None,
        "model": None,
        "available": False,
    }
    try:
        client = get_local_llm_client()
        available = client.is_available()
        status = client.get_status() if hasattr(client, "get_status") else {}
        # 优先读 override 配置（由 /api/settings/llm 写入），降级到 active_backend 推断
        if isinstance(status, dict):
            mode = status.get("override_mode")
            if mode is None:
                # 非 override 模式：根据 active_backend 推断
                active = status.get("active_backend", "none")
                mode = "mock" if active == "none" else "local"
            # model 字段：override 模式下读 override_model，否则读 lmstudio.model
            model_val = status.get("override_model")
            if model_val is None and isinstance(status.get("lmstudio"), dict):
                model_val = status["lmstudio"].get("model")
            llm_info = {
                "mode": mode,
                "provider": status.get("override_provider"),
                "model": model_val,
                "available": bool(available),
            }
    except Exception as e:
        logger.warning(f"Dashboard system-status: LLM 状态查询失败: {e}")

    # 工具链可用性
    # z3：优先检测 Python 包（z3-solver），其次检测命令行二进制
    z3_available = False
    try:
        import z3 as _z3  # noqa: F401
        z3_available = True
    except ImportError:
        z3_available = shutil.which("z3") is not None

    # cbmc：检测命令行二进制 + Windows 默认安装路径
    cbmc_available = shutil.which("cbmc") is not None
    if not cbmc_available and sys.platform == "win32":
        cbmc_default = Path(r"C:\Program Files\cbmc\bin\cbmc.exe")
        cbmc_available = cbmc_default.exists()

    tools = {
        "gcc": shutil.which("gcc") is not None,
        "z3": z3_available,
        "cbmc": cbmc_available,
    }

    # 持久化状态
    persistence: dict = {"db_rows": 0, "tables": {}, "last_write": None}
    try:
        # 确保读取最新提交数据：结束当前事务快照，开启新事务
        db.commit()
        tasks_count = db.execute(select(func.count()).select_from(Task)).scalar() or 0
        history_count = task_history_repo.total_count(db)
        persistence["db_rows"] = tasks_count + history_count
        persistence["tables"] = {"tasks": tasks_count, "task_history": history_count}
        last = task_history_repo.list_recent(db, limit=1)
        if last:
            persistence["last_write"] = (
                last[0].created_at.isoformat() if last[0].created_at else None
            )
    except Exception as e:
        logger.warning(f"Dashboard system-status: 持久化状态查询失败: {e}")

    # 自清理状态
    cleanup: dict = {"enabled": False, "work_dir_count": 0}
    try:
        from app.utils.cleanup_manager import get_cleanup_manager
        mgr = get_cleanup_manager()
        cleanup = mgr.get_status()
    except Exception as e:
        logger.warning(f"Dashboard system-status: 清理状态查询失败: {e}")

    return JSONResponse(
        content={
            "backend": backend_status,
            "llm": llm_info,
            "tools": tools,
            "persistence": persistence,
            "cleanup": cleanup,
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/compliance-trend")
async def get_compliance_trend(
    limit: int = 20, db: Session = Depends(get_db)
) -> list[dict]:
    """返回最近 N 次生成的违规数趋势。按时间正序（旧到新）。"""
    return task_history_repo.compliance_trend(db, limit=limit)


@router.get("/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)) -> dict:
    """返回 Dashboard 顶部统计指标。"""
    today_count = task_history_repo.count_today(db)
    today_done = task_history_repo.count_today_done(db)
    total_count = task_history_repo.total_count(db)

    # 平均合规率：近 20 次生成中违规数为 0 的比例
    recent = task_history_repo.list_recent(db, limit=20)
    if recent:
        zero_violation_count = sum(1 for t in recent if t.violation_count == 0)
        avg_compliance_rate = round(zero_violation_count / len(recent) * 100, 1)
    else:
        avg_compliance_rate = 0.0

    return {
        "today_count": today_count,
        "today_done": today_done,
        "total_count": total_count,
        "avg_compliance_rate": avg_compliance_rate,
    }


@router.get("/tasks/{task_id}")
async def get_task_detail(task_id: str, db: Session = Depends(get_db)) -> dict:
    """返回单条任务详情。"""
    task = task_history_repo.get(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id,
        "requirement": task.requirement,
        "language": task.language,
        "status": task.status,
        "code_hash": task.code_hash,
        "violation_count": task.violation_count,
        "mandatory_count": task.mandatory_count,
        "required_count": task.required_count,
        "advisory_count": task.advisory_count,
        "stage_reached": task.stage_reached,
        "duration_ms": task.duration_ms,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }
