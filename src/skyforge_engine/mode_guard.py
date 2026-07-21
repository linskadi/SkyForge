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
    import shutil
    import subprocess
    import re

    tool_path = shutil.which(tool_name)
    if tool_path is None:
        raise ToolNotFoundError(tool_name, f"未在 PATH 中找到工具: {tool_name}")

    version_info = tool_path
    try:
        result = subprocess.run(
            [tool_name, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            version_info = result.stdout.strip().splitlines()[0]
    except Exception:
        pass

    if min_version is not None:
        match = re.search(r"(\d+(?:\.\d+){0,2})", version_info)
        if match:
            actual = match.group(1)
            actual_tuple = tuple(int(p) for p in actual.split(".") if p.isdigit())
            min_tuple = tuple(int(p) for p in min_version.split(".") if p.isdigit())
            if actual_tuple < min_tuple:
                raise ToolNotFoundError(
                    tool_name,
                    f"工具 {tool_name} 版本 {actual} 低于最低要求 {min_version}"
                )

    return version_info


class ToolNotFoundError(RuntimeError):
    """所需外部工具缺失异常（兼容层）。"""
    pass


__all__ = [
    "LLMMode",
    "LLMBackendUnavailableError",
    "ToolNotFoundError",
    "get_current_mode",
    "require_mode",
    "require_tool",
]
