"""基础路由模块，提供健康检查等通用接口。"""

import time
from fastapi import APIRouter

router = APIRouter()

_start_time = time.time()


@router.get("/api/health")
async def health_check():
    """健康检查接口（Docker HEALTHCHECK 依赖此端点）。

    返回服务状态、运行时长和 LLM 后端状态。
    """
    from app.core.llm.lmstudio_client import get_lmstudio_client

    client = get_lmstudio_client()
    llm_status = client.get_status()

    return {
        "status": "ok",
        "service": "SkyForge",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "llm": llm_status,
    }
