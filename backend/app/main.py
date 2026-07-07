"""SkyForge (天锻) 应用入口，配置 FastAPI 应用和中间件。"""

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import os
from app.routers import ws_router, common_router, files_router
from app.api.routes import generate as ws_streaming_router
from app.api.routes import pipeline as pipeline_router
from app.api.routes import reports as reports_router
from app.api.routes import composition as composition_router
from app.api.routes import hil as hil_router
from app.api.routes import models as models_router
from app.utils.log_util import logger
from fastapi.staticfiles import StaticFiles
from app.utils.cli import get_ascii_banner, center_cli_str


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(get_ascii_banner())
    print(center_cli_str("SkyForge (天锻): 机载软件安全合规 AI 中台"))
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

app.include_router(ws_router.router)
app.include_router(common_router.router)
app.include_router(files_router.router)
app.include_router(ws_streaming_router.router)
app.include_router(pipeline_router.router)
app.include_router(reports_router.router)
app.include_router(composition_router.router)
app.include_router(hil_router.router)
app.include_router(models_router.router)


# 跨域 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # 暴露所有响应头
)

app.mount(
    "/static",  # 这是访问时的前缀
    StaticFiles(directory="project/work_dir"),  # 这是本地文件夹路径
    name="static",
)
