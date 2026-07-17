"""SkyForge (天锻) 应用入口，配置 FastAPI 应用和中间件。"""

from fastapi import FastAPI, Request, APIRouter
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import asyncio
import os
from app.api.routes import common as common_router
# Redis 可选 — 不可用时跳过 WebSocket 任务消息路由
try:
    from app.api.routes import task_ws as ws_router
except ImportError:
    from types import SimpleNamespace
    ws_router = SimpleNamespace(router=APIRouter())
from app.api.routes import generate as ws_streaming_router
from app.api.routes import pipeline as pipeline_router
from app.api.routes import reports as reports_router
from app.api.routes import composition as composition_router
from app.api.routes import hil as hil_router
from app.api.routes import models as models_router
from app.config.setting import settings
from skyforge_llm.client import get_lmstudio_client
from skyforge_engine.utils.log_util import logger
from fastapi.staticfiles import StaticFiles
from app.utils.cli import get_ascii_banner


# Rate limiter
limiter = Limiter(key_func=get_remote_address)


async def _warmup_llm(client) -> None:
    """模型预热：发送简短 prompt 触发首次推理，完成 KV-Cache 预热。

    后台异步执行，失败仅记录警告日志，不影响服务启动。
    """
    try:
        response = await client.chat_async("hello", max_tokens=16)
        if response:
            logger.info("LLM 模型预热完成（KV-Cache 已就绪）")
        else:
            logger.warning("LLM 模型预热未返回内容，可能后端不可用")
    except Exception as e:
        logger.warning(f"LLM 模型预热失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(get_ascii_banner())
    logger.info("Starting SkyForge")

    PROJECT_FOLDER = "./project"
    os.makedirs(PROJECT_FOLDER, exist_ok=True)

    # 模型预热：USE_LLM=true 且 LLM 可用时，异步发送简短 prompt 触发 KV-Cache 预热
    if settings.USE_LLM:
        client = get_lmstudio_client()
        if client.is_available():
            asyncio.create_task(_warmup_llm(client))

    yield
    logger.info("Stopping SkyForge")


app = FastAPI(
    title="SkyForge",
    description="SkyForge (天锻) - AI智能体驱动的机载软件轻量化开发工具",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security middleware: add security headers
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

app.include_router(common_router.router)
app.include_router(ws_router.router)
app.include_router(ws_streaming_router.router)
app.include_router(pipeline_router.router)
app.include_router(reports_router.router)
app.include_router(composition_router.router)
app.include_router(hil_router.router)
app.include_router(models_router.router)


@app.get("/", include_in_schema=False)
async def root():
    """根路径：返回 API 导航信息，避免直接访问后端时 404。"""
    return {
        "name": "SkyForge 天锻",
        "description": "AI 智能体驱动的机载软件轻量化开发工具",
        "frontend": "http://localhost:5173",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/api/health",
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """favicon：返回 204 避免浏览器请求时 404 报错。"""
    return JSONResponse(status_code=204, content=None)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# 跨域 CORS（从 settings 读取，支持多环境配置）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

os.makedirs("project/work_dir", exist_ok=True)
app.mount(
    "/static",
    StaticFiles(directory="project/work_dir"),
    name="static",
)
