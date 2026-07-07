"""通用路由模块，提供健康检查等接口。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
async def health_check():
    """健康检查接口。"""
    return {"status": "ok", "service": "AirborneAI"}


@router.get("/api/hello")
async def hello_world():
    """Hello World 接口。"""
    return {"message": "Hello from AirborneAI"}
