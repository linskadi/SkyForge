"""SkyForge (天锻) 应用入口，配置 FastAPI 应用和中间件。"""

from fastapi import FastAPI, Request, APIRouter
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import atexit
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
# HITL 人工审查（Human-in-the-Loop）路由。
# 模块名已从 hil 重命名为 hitl；URL 路径 /api/hil/* 保持不变以避免破坏现有调用方。
from app.api.routes import hitl as hitl_router
from app.api.routes import models as models_router
from app.api.routes import settings as settings_router
from app.api.routes import dashboard as dashboard_router
from app.api.routes import tasks_v1 as tasks_v1_router
from app.config.setting import settings
from app.core.llm.local_llm_client import get_lmstudio_client
from skyforge_engine.utils.log_util import logger
from skyforge_engine.utils.cleanup_util import cleanup_stale_tempdirs
from fastapi.staticfiles import StaticFiles
from app.utils.cli import get_ascii_banner
from app.utils.cleanup_manager import get_cleanup_manager
from app.core.streaming import get_stream_manager
from app.core.tool_manager import check_tools_on_startup, add_tools_to_path
from app.services.redis_manager import redis_manager
# 导入 TaskHistory 模型，确保 Base.metadata.create_all 能感知到该表
from app.models import task_history as _task_history_model  # noqa: F401
from app.models import task as _task_model  # noqa: F401
from app.repositories import task_repo
from app.db import Base, SessionLocal, engine


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
    logger.info("SkyForge 后端启动 | env={} | pid={}", settings.ENV, os.getpid())

    # 将本地工具目录加入 PATH，随后检查外部工具可用性
    try:
        add_tools_to_path()
        check_tools_on_startup()
    except Exception as e:
        logger.warning(f"外部工具检查失败: {e}")

    PROJECT_FOLDER = "./project"
    os.makedirs(PROJECT_FOLDER, exist_ok=True)

    # 初始化数据库：自动建表
    try:
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            legacy = task_repo.migrate_legacy_history(db)
            interrupted = task_repo.mark_running_interrupted(db)
        logger.info(
            f"数据库初始化完成（迁移 {legacy} 个 legacy 摘要，恢复 {interrupted} 个中断任务）"
        )
    except Exception as e:
        logger.warning(f"数据库初始化失败（Dashboard 持久化将不可用）: {e}")

    # 只应用用户明确选择的后端。默认 mock 不再扫描 llama.cpp、Ollama 或
    # LM Studio，避免无关依赖警告和启动阶段 502/超时。云 API 永不自动预热，
    # 防止无意消耗余额；本地模型可通过 SKYFORGE_LLM_WARMUP 显式开启预热。
    client = get_lmstudio_client()
    llm_mode = settings.SKYFORGE_LLM_MODE
    llm_provider = settings.SKYFORGE_LLM_PROVIDER
    llm_base_url = settings.LOCAL_LLM_BASE_URL or settings.LMSTUDIO_BASE_URL
    client.apply_config(
        llm_mode,
        llm_provider,
        settings.LLM_API_KEY,
        llm_base_url,
        settings.LLM_MODEL,
    )
    logger.info(
        "LLM 配置已加载 | mode={} | provider={} | model={} | key_configured={}",
        llm_mode,
        llm_provider or "-",
        settings.LLM_MODEL or "auto",
        bool(settings.LLM_API_KEY),
    )
    if (
        llm_mode == "local"
        and settings.SKYFORGE_LLM_WARMUP
        and client.is_available()
    ):
        asyncio.create_task(_warmup_llm(client))

    # 启动自清理管理器：清理崩溃残留 + 后台定期清理
    try:
        stale_count = cleanup_stale_tempdirs()
        if stale_count > 0:
            logger.info(f"启动清理：移除 {stale_count} 个残留临时目录")
        cleanup_mgr = get_cleanup_manager()
        cleanup_mgr.start()
    except Exception as e:
        logger.warning(f"自清理管理器启动失败: {e}")

    yield
    logger.info("SkyForge 后端停止")

    # 停止自清理管理器
    try:
        cleanup_mgr = get_cleanup_manager()
        cleanup_mgr.stop()
    except Exception as e:
        logger.warning(f"自清理管理器停止失败: {e}")

    # 关闭 StreamManager（清理残留 WebSocket 连接）
    try:
        await get_stream_manager().close()
    except Exception as e:
        logger.warning(f"StreamManager 关闭失败: {e}")

    # 关闭 Redis pubsub 连接（RedisManager 持有消息发布/订阅客户端）
    try:
        await redis_manager.close()
        logger.info("Redis 连接已关闭")
    except Exception as e:
        logger.warning(f"Redis 连接关闭失败: {e}")

    # 关闭数据库引擎连接池
    try:
        engine.dispose()
        logger.info("数据库引擎已释放")
    except Exception as e:
        logger.warning(f"数据库引擎释放失败: {e}")


def _atexit_close_redis() -> None:
    """进程退出兜底：关闭 Redis pubsub 连接。

    lifespan shutdown 是主清理路径；当进程被信号终止或 lifespan 未正常
    完成时，atexit 钩子作为兜底尝试关闭 Redis 客户端，避免连接泄漏。
    """
    try:
        if redis_manager._client is None:
            return
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        if loop is not None and not loop.is_closed() and not loop.is_running():
            loop.run_until_complete(redis_manager.close())
        elif loop is not None and loop.is_running():
            # loop 仍在运行（罕见）：调度任务，不等待
            asyncio.ensure_future(redis_manager.close())
        else:
            # 无可用 loop：新建一次性 loop
            asyncio.run(redis_manager.close())
    except Exception as e:
        logger.debug(f"atexit 关闭 Redis 失败（可忽略）: {e}")


atexit.register(_atexit_close_redis)


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
app.include_router(hitl_router.router)
app.include_router(models_router.router)
app.include_router(settings_router.router)
app.include_router(dashboard_router.router)
app.include_router(tasks_v1_router.router)


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
_cors_origins = [
    o.strip()
    for o in settings.CORS_ALLOW_ORIGINS.split(",")
    if o.strip() and o.strip() != "*"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["Content-Disposition"],
)

os.makedirs("project/work_dir", exist_ok=True)
app.mount(
    "/static",
    StaticFiles(directory="project/work_dir"),
    name="static",
)
