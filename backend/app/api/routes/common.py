"""基础路由模块，提供健康检查等通用接口。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
async def health_check():
    """健康检查接口。"""
    return {"status": "ok", "service": "SkyForge"}
