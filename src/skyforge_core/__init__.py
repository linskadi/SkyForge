"""SkyForge Core CLI — AI驱动的机载软件轻量化开发工具。

依赖: skyforge-engine + skyforge-llm
用法: skyforge generate -r requirements.txt -o output/
"""

from skyforge_engine import run_pipeline, run_full_pipeline

__version__ = "0.4.0"
