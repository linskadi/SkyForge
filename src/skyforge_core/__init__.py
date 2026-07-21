"""SkyForge Core CLI — AI驱动的机载软件轻量化开发工具。

依赖: skyforge-engine + skyforge-llm
用法: skyforge generate -r requirements.txt -o output/
"""

from skyforge_engine import run_full_pipeline as run_full_pipeline
from skyforge_engine import run_pipeline as run_pipeline

__version__ = "0.4.0"

__all__ = ["run_full_pipeline", "run_pipeline"]
