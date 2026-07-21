"""引擎层自清理工具：轻量级临时文件清理，不依赖 FastAPI。

提供：
- safe_tempdir: 带异常安全清理的临时目录上下文管理器（替代裸 mkdtemp）
- safe_tempfile: 带异常安全清理的临时文件上下文管理器
- cleanup_stale_tempdirs: 清理系统临时目录中残留的 skyforge_* 目录

所有使用 tempfile.mkdtemp / NamedTemporaryFile(delete=False) 的地方
都应改用本模块，确保异常时也能清理。
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from skyforge_engine.utils.log_util import logger


_PREFIXES = (
    "skyforge_cppcheck_",
    "skyforge_contract_",
    "skyforge_digital_twin_",
    "skyforge_cbmc_",
    "skyforge_gcov_",
    "skyforge_",
)

_registered_dirs: list[str] = []
_atexit_registered = False


def _ensure_atexit() -> None:
    global _atexit_registered
    if not _atexit_registered:
        atexit.register(_cleanup_registered)
        _atexit_registered = True


def _cleanup_registered() -> None:
    """退出时清理所有已注册的临时目录。"""
    for d in _registered_dirs:
        try:
            if os.path.exists(d):
                shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass


@contextmanager
def safe_tempdir(prefix: str = "skyforge_") -> Generator[str, None, None]:
    """安全临时目录上下文管理器。

    相比 tempfile.TemporaryDirectory，额外保证：
    1. 即使 with 块内发生任何异常也会清理
    2. 注册到 atexit，万一上下文未正常退出也兜底清理

    Args:
        prefix: 目录名前缀，建议 skyforge_xxx_ 便于识别

    Yields:
        临时目录路径
    """
    tmpdir = tempfile.mkdtemp(prefix=prefix)
    _ensure_atexit()
    _registered_dirs.append(tmpdir)
    try:
        yield tmpdir
    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        finally:
            if tmpdir in _registered_dirs:
                _registered_dirs.remove(tmpdir)


@contextmanager
def safe_tempfile(
    mode: str = "w",
    suffix: str = "",
    prefix: str = "skyforge_",
    encoding: Optional[str] = "utf-8",
) -> Generator[tuple[str, object], None, None]:
    """安全临时文件上下文管理器。

    返回 (文件路径, 文件对象)，退出时自动删除。

    Args:
        mode: 打开模式
        suffix: 文件名后缀
        prefix: 文件名前缀
        encoding: 编码

    Yields:
        (文件路径, 文件对象)
    """

    tmpdir_ctx = safe_tempdir(prefix=prefix)
    tmpdir = next(tmpdir_ctx.__iter__())
    try:
        filepath = os.path.join(tmpdir, f"tmp{suffix}")
        f = open(filepath, mode, encoding=encoding) if "b" not in mode else open(filepath, mode)
        try:
            yield filepath, f
        finally:
            try:
                f.close()
            except Exception:
                pass
    finally:
        try:
            tmpdir_ctx.__exit__(None, None, None)
        except Exception:
            pass


def cleanup_stale_tempdirs(min_age_seconds: int = 3600) -> int:
    """清理系统临时目录下残留的 skyforge_* 目录。

    通常在服务启动时调用一次，清理上次崩溃遗留的临时文件。
    默认只清理至少 1 小时以前创建/修改的目录，避免删除当前测试或
    运行中的编译产物。

    Returns:
        清理的目录数量
    """
    sys_tmp = Path(tempfile.gettempdir())
    count = 0
    cutoff = time.time() - min_age_seconds
    try:
        for entry in sys_tmp.iterdir():
            if not entry.is_dir():
                continue
            name = entry.name
            if not any(name.startswith(p) for p in _PREFIXES):
                continue
            if str(entry) in _registered_dirs:
                continue
            try:
                newest = max(entry.stat().st_mtime, entry.stat().st_ctime)
            except OSError:
                continue
            if newest > cutoff:
                continue
            try:
                shutil.rmtree(entry, ignore_errors=True)
                count += 1
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"cleanup_stale_tempdirs: 扫描失败: {e}")

    if count > 0:
        logger.info(f"cleanup_stale_tempdirs: 清理了 {count} 个残留临时目录")
    return count
