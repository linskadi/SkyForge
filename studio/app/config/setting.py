"""应用配置模块 — 统一使用 skyforge_engine.config 的 settings 单例。"""

# Re-export from skyforge_engine.config to avoid duplicate settings objects
from skyforge_engine.config import settings, Settings, ApiType, parse_cors

__all__ = ["settings", "Settings", "ApiType", "parse_cors"]
