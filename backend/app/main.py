"""SkyForge (天锻) 应用入口，配置 FastAPI 应用和中间件。"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import os
from app.api.routes import common as common_router
from app.api.routes import task_ws as ws_router
from app.api.routes import generate as ws_streaming_router
from app.api.routes import pipeline as pipeline_router
from app.api.routes import reports as reports_router
from app.api.routes import composition as composition_router
from app.api.routes import hil as hil_router
from app.api.routes import models as models_router
from app.config.setting import settings
from app.utils.log_util import logger
from fastapi.staticfiles import StaticFiles
from app.utils.cli import get_ascii_banner, center_cli_str


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(get_ascii_banner())
    logger.info("Starting SkyForge")

    PROJECT_FOLDER = "./project"
    os.makedirs(PROJECT_FOLDER, exist_ok=True)

    yield
    logger.info("Stopping SkyForge")


app = FastAPI(
    title="SkyForge",
    description="SkyForge (天锻) - AI智能体驱动的机载软件轻量化开发工具",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(common_router.router)
app.include_router(ws_router.router)
app.include_router(ws_streaming_router.router)
app.include_router(pipeline_router.router)
app.include_router(reports_router.router)
app.include_router(composition_router.router)
app.include_router(hil_router.router)
app.include_router(models_router.router)


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

app.mount(
    "/static",
    StaticFiles(directory="project/work_dir"),
    name="static",
)
