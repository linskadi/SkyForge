"""基础路由模块，提供健康检查、清理等通用接口。"""

import shutil
import time
from fastapi import APIRouter, Depends, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.auth import require_write_access
from app.utils.log_util import logger

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
_start_time = time.time()


@router.get("/api/health")
@limiter.limit("30/minute")
async def health_check(request: Request):
    """健康检查接口（Docker HEALTHCHECK 依赖此端点）。

    返回服务状态、运行时长、各组件状态。任何组件状态查询失败时该字段返回
    "error"，整体 status 为 "ok" 当且仅当所有组件正常，端点始终返回 200（避免 Docker
    HEALTHCHECK 误判容器不可用）。
    """
    # LLM 状态（失败时返回 "error"）
    llm_status = "error"
    try:
        from app.core.llm.local_llm_client import get_local_llm_client as get_lmstudio_client
        client = get_lmstudio_client()
        llm_status = client.get_status()
    except Exception as e:
        logger.warning(f"/api/health: LLM 状态查询失败: {e}")

    # GCC 可用性（失败时返回 "error"）
    gcc_available = "error"
    try:
        gcc_available = shutil.which("gcc") is not None
    except Exception as e:
        logger.warning(f"/api/health: GCC 探测失败: {e}")

    # Redis 可用性（失败时返回 "error"）
    redis_available = "error"
    try:
        from app.services.redis_manager import redis_manager
        redis_available = await redis_manager.ping()
    except Exception as e:
        logger.warning(f"/api/health: Redis 状态查询失败: {e}")

    # 综合状态：所有组件正常时才为 "ok"
    overall = (
        "ok"
        if (llm_status and llm_status != "error" and gcc_available is True and redis_available is True)
        else "error"
    )

    return {
        "status": overall,
        "service": "SkyForge",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "llm": llm_status,
        "gcc": gcc_available,
        "redis": redis_available,
    }


@router.get("/api/cleanup/status")
@limiter.limit("10/minute")
async def cleanup_status(request: Request):
    """获取自清理管理器状态。"""
    try:
        from app.utils.cleanup_manager import get_cleanup_manager
        mgr = get_cleanup_manager()
        return mgr.get_status()
    except Exception as e:
        logger.error(f"/api/cleanup/status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/cleanup/run")
@limiter.limit("5/minute")
async def cleanup_run(request: Request, _user: str = Depends(require_write_access)):
    """手动触发完整清理（工作目录 + 日志 + 证据包 + 临时目录）。"""
    try:
        from app.utils.cleanup_manager import get_cleanup_manager
        mgr = get_cleanup_manager()
        stats = mgr.run_full_cleanup()
        logger.info(f"手动清理完成：释放 {stats.total_freed_bytes / 1024 / 1024:.2f} MB")
        return stats.to_dict()
    except Exception as e:
        logger.error(f"/api/cleanup/run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/cleanup/temp")
@limiter.limit("10/minute")
async def cleanup_temp(request: Request, _user: str = Depends(require_write_access)):
    """仅清理系统临时目录下的 skyforge_* 残留。"""
    try:
        from app.utils.cleanup_manager import get_cleanup_manager
        mgr = get_cleanup_manager()
        stats = mgr.cleanup_temp_dirs()
        return stats.to_dict()
    except Exception as e:
        logger.error(f"/api/cleanup/temp: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/cleanup/workdir/{task_id}")
@limiter.limit("10/minute")
async def cleanup_task_workdir(request: Request, task_id: str, _user: str = Depends(require_write_access)):
    """清理指定任务的工作目录。"""
    from app.utils.common_utils import ensure_safe_task_id
    try:
        safe_id = ensure_safe_task_id(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        from app.utils.cleanup_manager import get_cleanup_manager
        mgr = get_cleanup_manager()
        success = mgr.cleanup_task_dir(safe_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"任务目录不存在: {safe_id}")
        return {"success": True, "task_id": safe_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/api/cleanup/workdir/{safe_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
