"""Studio 日志兼容入口；统一复用 engine 的单一 Loguru 配置。"""

from skyforge_engine.utils.log_util import LoggerInitializer, logger

__all__ = ["LoggerInitializer", "logger"]
