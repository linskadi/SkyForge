"""基础路由模块，提供健康检查、统计等通用接口。"""

import shutil
import time
from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
_start_time = time.time()


@router.get("/api/health")
@limiter.limit("30/minute")
async def health_check(request: Request):
    """健康检查接口（Docker HEALTHCHECK 依赖此端点）。

    返回服务状态、运行时长、各组件状态。
    """
    from app.core.llm.lmstudio_client import get_lmstudio_client
    from app.services.redis_manager import redis_manager

    client = get_lmstudio_client()
    llm_status = client.get_status()

    gcc_available = shutil.which("gcc") is not None

    redis_ok = False
    try:
        redis_ok = await redis_manager.ping()
    except Exception:
        pass

    overall = "ok"
    if not gcc_available:
        overall = "degraded"

    return {
        "status": overall,
        "service": "SkyForge",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "llm": llm_status,
        "gcc": gcc_available,
        "redis": redis_ok,
    }


@router.get("/api/stats")
@limiter.limit("10/minute")
async def system_stats(request: Request):
    """系统运行统计。"""
    return {
        "uptime_seconds": round(time.time() - _start_time, 1),
        "service": "SkyForge",
        "version": "1.0.0",
    }
