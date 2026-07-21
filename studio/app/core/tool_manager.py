"""外部工具管理器。

检测和管理 SkyForge 所需的外部工具，确保工具缺失时明确报错而非降级。
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

from app.utils.log_util import logger


@dataclass
class ToolInfo:
    """外部工具信息。

    Attributes:
        name: 工具名称（可执行文件）。
        min_version: 最低版本要求。
        description: 用途描述。
        install_hint: 安装提示信息。
        found: 是否已在系统 PATH 中找到。
        version: 实际检测到的版本字符串（未找到时为空）。
    """

    name: str
    min_version: str
    description: str
    install_hint: str = ""
    found: bool = False
    version: str = ""


# SkyForge 核心外部工具清单
TOOLS_REQUIREMENTS: list[ToolInfo] = [
    ToolInfo(name="cbmc", min_version="6.0", description="形式化验证", install_hint="→ https://github.com/diffblue/cbmc/releases"),
    ToolInfo(name="z3", min_version="4.12", description="SMT约束求解", install_hint="→ pip install z3-solver"),
    ToolInfo(name="semgrep", min_version="1.60", description="静态分析", install_hint="→ pip install semgrep"),
    ToolInfo(name="gcc", min_version="14.0", description="代码编译", install_hint=""),
    ToolInfo(name="lcov", min_version="2.0", description="覆盖率收集", install_hint="→ choco install lcov (Windows) / apt install lcov (Linux)"),
]


def _extract_version(text: str) -> Optional[str]:
    """从文本中提取类似 ``1.2.3`` 的版本号。"""
    match = re.search(r"(\d+(?:\.\d+){0,2})", text)
    return match.group(1) if match else None


def _version_tuple(version: str | None) -> tuple[int, ...]:
    """将版本号字符串转换为可比较的元组。"""
    if version is None:
        return ()
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def check_tool_available(name: str, min_version: str) -> Optional[str]:
    """检查单个外部工具是否可用并满足最低版本。

    使用 ``shutil.which`` 在 ``PATH`` 中查找可执行文件；
    若存在，则运行 ``tool --version`` 获取版本输出，
    使用正则提取版本号并与 *min_version* 比较。

    对于 ``z3``，额外检测 Python ``z3-solver`` 包的导入可用性。

    Args:
        name: 可执行文件名称。
        min_version: 最低版本要求（如 ``6.0``）。

    Returns:
        工具版本字符串（首行），若未找到或版本不足则返回 ``None``。
    """
    # z3 特殊处理：优先检测 Python 包，其次检测命令行二进制
    if name == "z3":
        try:
            import importlib.metadata as _meta
            ver = _meta.version("z3-solver")
            if ver and _version_tuple(ver) >= _version_tuple(min_version):
                return ver
        except Exception:
            pass
        # 也检查 z3 模块
        try:
            import z3 as _z3  # noqa: F401
            try:
                ver = _z3.get_version_string()
                if ver and _version_tuple(ver) >= _version_tuple(min_version):
                    return ver
            except Exception:
                pass
        except ImportError:
            pass

    tool_path = shutil.which(name)
    if tool_path is None:
        return None

    try:
        # Windows 上 .cmd/.bat 需要通过 shell=True 才能由 subprocess 执行
        use_shell = platform.system() == "Windows" and tool_path.lower().endswith((".cmd", ".bat"))
        result = subprocess.run(
            [name, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            shell=use_shell,
        )
        version_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    except Exception:
        version_line = ""

    actual = _extract_version(version_line)
    if actual is None:
        # 能找到但无法解析版本时，保守地视为可用
        return version_line or "unknown"

    if _version_tuple(actual) < _version_tuple(min_version):
        return None

    return actual


def check_all_tools() -> list[ToolInfo]:
    """检查 ``TOOLS_REQUIREMENTS`` 中所有工具的状态。

    Returns:
        包含检测结果的 ``ToolInfo`` 列表（原地更新后返回新列表副本）。
    """
    results: list[ToolInfo] = []
    for req in TOOLS_REQUIREMENTS:
        version = check_tool_available(req.name, req.min_version)
        found = version is not None
        results.append(
            ToolInfo(
                name=req.name,
                min_version=req.min_version,
                description=req.description,
                install_hint=req.install_hint,
                found=found,
                version=version or "",
            )
        )
    return results


def check_tools_on_startup() -> list[ToolInfo]:
    """启动时检查所有外部工具并记录日志。

    对缺失或版本不足的工具打印 ``warning`` 日志，
    便于运维人员快速定位环境缺失问题。

    Returns:
        检测结果列表。
    """
    results = check_all_tools()
    for info in results:
        if not info.found:
            hint = f" {info.install_hint}" if info.install_hint else ""
            logger.warning(
                f"外部工具缺失: {info.name} (需要 >= {info.min_version}) — {info.description}{hint}"
            )
        else:
            logger.info(
                f"外部工具就绪: {info.name}={info.version} (要求 >= {info.min_version})"
            )
    return results


def add_tools_to_path() -> None:
    """将 SkyForge 本地工具目录添加到 ``PATH``。

    优先查找用户级本地目录中的离线安装包，避免全局污染：

    - Windows: ``%LOCALAPPDATA%\\SkyForge\\tools\\bin``
    - Linux/macOS: ``~/.local/share/skyforge/tools/bin``

    若目录存在，则插入到 ``PATH`` 最前，使本地版本优先于系统版本。
    """
    system = platform.system()
    if system == "Windows":
        local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        local_bin = os.path.join(local_appdata, "SkyForge", "tools", "bin")
    else:
        local_bin = os.path.expanduser("~/.local/share/skyforge/tools/bin")

    if os.path.isdir(local_bin):
        current_path = os.environ.get("PATH", "")
        if local_bin not in current_path.split(os.pathsep):
            os.environ["PATH"] = local_bin + os.pathsep + current_path
            logger.info(f"已将本地工具目录加入 PATH: {local_bin}")
    else:
        logger.debug(f"本地工具目录不存在，跳过: {local_bin}")
