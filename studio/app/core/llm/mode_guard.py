"""LLM 模式守卫模块（兼容层）。

已迁移到 skyforge_engine.llm.router 模块，本文件仅保留向后兼容。

新代码应使用：
    from skyforge_engine.llm import get_current_mode, require_mode, LLMMode
"""

from skyforge_engine.llm.router import (
    LLMMode,
    LLMBackendUnavailableError,
    get_current_mode,
    require_mode,
)

def require_tool(tool_name: str, min_version: str | None = None) -> str:
    """检查外部工具是否可用（已迁移到 tool_manager）。"""
    from app.core.tool_manager import check_tool_available
    result = check_tool_available(tool_name, min_version)
    if result is None:
        raise ToolNotFoundError(tool_name, f"未在 PATH 中找到工具: {tool_name}")
    return result


class ToolNotFoundError(RuntimeError):
    """所需外部工具缺失异常（兼容层）。"""

    def __init__(self, tool_name: str, message: str = ""):
        super().__init__(message or f"Tool '{tool_name}' not found")
        self.tool_name = tool_name
        self.message = message


__all__ = [
    "LLMMode",
    "LLMBackendUnavailableError",
    "ToolNotFoundError",
    "get_current_mode",
    "require_mode",
    "require_tool",
]
