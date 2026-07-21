"""自清理管理器：统一管理项目产生的临时文件、工作目录、日志、缓存等垃圾文件。

功能：
1. 启动时清理：清理残留的系统临时目录下 skyforge_* 目录
2. 退出时清理：atexit 注册，确保进程退出时清理临时文件
3. 定期清理：后台线程按 TTL 清理老旧工作目录 / 日志 / 证据包
4. 手动清理：API 端点触发按需清理
5. 工作目录自动清理：任务完成后可选自动删除工作目录

环境变量：
- CLEANUP_ENABLED=true       是否启用自清理（默认 true）
- CLEANUP_WORK_DIR_TTL=86400 工作目录保留时长（秒），默认 24 小时
- CLEANUP_LOG_TTL=604800     日志文件保留时长（秒），默认 7 天
- CLEANUP_EVIDENCE_TTL=86400 证据包保留时长（秒），默认 24 小时
- CLEANUP_INTERVAL=3600      定期清理间隔（秒），默认 1 小时
- CLEANUP_ON_STARTUP=true    启动时是否清理残留临时文件
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.utils.log_util import logger


@dataclass
class CleanupStats:
    """清理统计信息。"""

    work_dirs_removed: int = 0
    work_dirs_freed_bytes: int = 0
    logs_removed: int = 0
    logs_freed_bytes: int = 0
    evidence_removed: int = 0
    evidence_freed_bytes: int = 0
    temp_dirs_removed: int = 0
    temp_dirs_freed_bytes: int = 0
    pycache_removed: int = 0
    pycache_freed_bytes: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_freed_bytes(self) -> int:
        return (
            self.work_dirs_freed_bytes
            + self.logs_freed_bytes
            + self.evidence_freed_bytes
            + self.temp_dirs_freed_bytes
            + self.pycache_freed_bytes
        )

    def to_dict(self) -> dict:
        return {
            "work_dirs_removed": self.work_dirs_removed,
            "work_dirs_freed_mb": round(self.work_dirs_freed_bytes / 1024 / 1024, 2),
            "logs_removed": self.logs_removed,
            "logs_freed_mb": round(self.logs_freed_bytes / 1024 / 1024, 2),
            "evidence_removed": self.evidence_removed,
            "evidence_freed_mb": round(self.evidence_freed_bytes / 1024 / 1024, 2),
            "temp_dirs_removed": self.temp_dirs_removed,
            "temp_dirs_freed_mb": round(self.temp_dirs_freed_bytes / 1024 / 1024, 2),
            "pycache_removed": self.pycache_removed,
            "pycache_freed_mb": round(self.pycache_freed_bytes / 1024 / 1024, 2),
            "total_freed_mb": round(self.total_freed_bytes / 1024 / 1024, 2),
            "errors": self.errors,
        }


class CleanupManager:
    """自清理管理器单例。"""

    _instance: Optional["CleanupManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.enabled = os.environ.get("CLEANUP_ENABLED", "true").lower() != "false"
        self.work_dir_ttl = int(os.environ.get("CLEANUP_WORK_DIR_TTL", "86400"))
        self.log_ttl = int(os.environ.get("CLEANUP_LOG_TTL", "604800"))
        self.evidence_ttl = int(os.environ.get("CLEANUP_EVIDENCE_TTL", "86400"))
        self.interval = int(os.environ.get("CLEANUP_INTERVAL", "3600"))
        self.on_startup = os.environ.get("CLEANUP_ON_STARTUP", "true").lower() != "false"

        self._base_dir = Path.cwd()
        self._work_dir_root = self._base_dir / "project" / "work_dir"
        self._log_dir = self._base_dir / "logs"
        self._evidence_dir = self._base_dir / "evidence_package"
        self._sys_temp = Path(tempfile.gettempdir())

        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_cleanup_time: float = 0
        self._last_stats = CleanupStats()

        self._registered_temp_dirs: list[str] = []
        self._atexit_registered = False

    @classmethod
    def get_instance(cls) -> "CleanupManager":
        """获取单例。"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def start(self) -> None:
        """启动清理管理器：注册 atexit + 启动后台定期清理线程 + 启动时清理。"""
        if not self.enabled:
            logger.info("CleanupManager:已禁用 (CLEANUP_ENABLED=false)")
            return

        if not self._atexit_registered:
            atexit.register(self._on_exit)
            self._atexit_registered = True
            logger.debug("CleanupManager:已注册 atexit 退出清理")

        startup_freed_bytes = 0
        if self.on_startup:
            logger.debug("CleanupManager:执行启动时清理")
            stats = self.cleanup_temp_dirs()
            stats = self.cleanup_pycache()
            startup_freed_bytes = stats.total_freed_bytes

        if self._scheduler_thread is None or not self._scheduler_thread.is_alive():
            self._stop_event.clear()
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                name="cleanup-scheduler",
                daemon=True,
            )
            self._scheduler_thread.start()
            logger.info(
                "CleanupManager 已启动 | "
                f"interval={self.interval}s | freed={startup_freed_bytes / 1024:.1f}KB"
            )

    def stop(self) -> None:
        """停止后台清理线程。"""
        self._stop_event.set()
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)
        logger.debug("CleanupManager:定期清理线程已停止")

    def _scheduler_loop(self) -> None:
        """后台定期清理循环。"""
        while not self._stop_event.is_set():
            try:
                self._stop_event.wait(self.interval)
                if self._stop_event.is_set():
                    break
                logger.info("CleanupManager:执行定期清理...")
                stats = self.run_full_cleanup()
                self._last_stats = stats
                self._last_cleanup_time = time.time()
                logger.info(
                    f"CleanupManager:定期清理完成，释放 {stats.total_freed_bytes / 1024 / 1024:.2f} MB"
                )
            except Exception as e:
                logger.error(f"CleanupManager:定期清理异常: {e}")

    def _on_exit(self) -> None:
        """进程退出时的清理回调。"""
        try:
            for tmp_dir in self._registered_temp_dirs:
                try:
                    if os.path.exists(tmp_dir):
                        shutil.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass
            self.cleanup_temp_dirs()
        except Exception:
            pass

    def register_temp_dir(self, path: str) -> None:
        """注册一个临时目录，进程退出时自动清理。"""
        self._registered_temp_dirs.append(path)

    # ==================== 各类清理方法 ====================

    def run_full_cleanup(self) -> CleanupStats:
        """执行完整清理：工作目录 + 日志 + 证据包 + 临时目录 + pycache。"""
        stats = CleanupStats()
        self._merge_stats(stats, self.cleanup_work_dirs())
        self._merge_stats(stats, self.cleanup_logs())
        self._merge_stats(stats, self.cleanup_evidence())
        self._merge_stats(stats, self.cleanup_temp_dirs())
        self._merge_stats(stats, self.cleanup_pycache())
        return stats

    @staticmethod
    def _merge_stats(target: CleanupStats, source: CleanupStats) -> None:
        target.work_dirs_removed += source.work_dirs_removed
        target.work_dirs_freed_bytes += source.work_dirs_freed_bytes
        target.logs_removed += source.logs_removed
        target.logs_freed_bytes += source.logs_freed_bytes
        target.evidence_removed += source.evidence_removed
        target.evidence_freed_bytes += source.evidence_freed_bytes
        target.temp_dirs_removed += source.temp_dirs_removed
        target.temp_dirs_freed_bytes += source.temp_dirs_freed_bytes
        target.pycache_removed += source.pycache_removed
        target.pycache_freed_bytes += source.pycache_freed_bytes
        target.errors.extend(source.errors)

    def cleanup_work_dirs(self, ttl_seconds: Optional[int] = None) -> CleanupStats:
        """清理过期的任务工作目录。

        Args:
            ttl_seconds: 保留时长，默认使用配置值

        Returns:
            清理统计
        """
        stats = CleanupStats()
        ttl = ttl_seconds if ttl_seconds is not None else self.work_dir_ttl
        now = time.time()

        if not self._work_dir_root.exists():
            return stats

        try:
            for entry in self._work_dir_root.iterdir():
                if not entry.is_dir():
                    continue
                try:
                    age = now - entry.stat().st_mtime
                    if age > ttl:
                        size = self._dir_size(entry)
                        shutil.rmtree(entry, ignore_errors=True)
                        stats.work_dirs_removed += 1
                        stats.work_dirs_freed_bytes += size
                        logger.debug(f"CleanupManager:清理工作目录 {entry.name} (age={age/3600:.1f}h)")
                except Exception as e:
                    stats.errors.append(f"work_dir {entry.name}: {e}")
        except Exception as e:
            stats.errors.append(f"work_dir root: {e}")

        if stats.work_dirs_removed > 0:
            logger.info(
                f"CleanupManager:清理了 {stats.work_dirs_removed} 个工作目录，"
                f"释放 {stats.work_dirs_freed_bytes / 1024:.1f} KB"
            )
        return stats

    def cleanup_logs(self, ttl_seconds: Optional[int] = None) -> CleanupStats:
        """清理过期的日志文件。

        Args:
            ttl_seconds: 保留时长，默认使用配置值

        Returns:
            清理统计
        """
        stats = CleanupStats()
        ttl = ttl_seconds if ttl_seconds is not None else self.log_ttl
        now = time.time()

        if not self._log_dir.exists():
            return stats

        try:
            for entry in self._log_dir.iterdir():
                if not entry.is_file():
                    continue
                try:
                    age = now - entry.stat().st_mtime
                    if age > ttl:
                        size = entry.stat().st_size
                        entry.unlink()
                        stats.logs_removed += 1
                        stats.logs_freed_bytes += size
                        logger.debug(f"CleanupManager:清理日志 {entry.name} (age={age/3600:.1f}h)")
                except Exception as e:
                    stats.errors.append(f"log {entry.name}: {e}")
        except Exception as e:
            stats.errors.append(f"log dir: {e}")

        if stats.logs_removed > 0:
            logger.info(
                f"CleanupManager:清理了 {stats.logs_removed} 个日志文件，"
                f"释放 {stats.logs_freed_bytes / 1024:.1f} KB"
            )
        return stats

    def cleanup_evidence(self, ttl_seconds: Optional[int] = None) -> CleanupStats:
        """清理过期的证据包。

        Args:
            ttl_seconds: 保留时长，默认使用配置值

        Returns:
            清理统计
        """
        stats = CleanupStats()
        ttl = ttl_seconds if ttl_seconds is not None else self.evidence_ttl
        now = time.time()

        if not self._evidence_dir.exists():
            return stats

        try:
            for entry in self._evidence_dir.iterdir():
                if not entry.is_dir():
                    continue
                try:
                    age = now - entry.stat().st_mtime
                    if age > ttl:
                        size = self._dir_size(entry)
                        shutil.rmtree(entry, ignore_errors=True)
                        stats.evidence_removed += 1
                        stats.evidence_freed_bytes += size
                        logger.debug(f"CleanupManager:清理证据包 {entry.name} (age={age/3600:.1f}h)")
                except Exception as e:
                    stats.errors.append(f"evidence {entry.name}: {e}")
        except Exception as e:
            stats.errors.append(f"evidence dir: {e}")

        if stats.evidence_removed > 0:
            logger.info(
                f"CleanupManager:清理了 {stats.evidence_removed} 个证据包，"
                f"释放 {stats.evidence_freed_bytes / 1024:.1f} KB"
            )
        return stats

    def cleanup_temp_dirs(self) -> CleanupStats:
        """清理系统临时目录下残留的 skyforge_* 临时目录。

        这些是 tempfile.mkdtemp(prefix="skyforge_*") 创建但因崩溃未清理的。

        Returns:
            清理统计
        """
        stats = CleanupStats()
        prefixes = (
            "skyforge_cppcheck_",
            "skyforge_contract_",
            "skyforge_digital_twin_",
            "skyforge_cbmc_",
            "skyforge_gcov_",
            "skyforge_",
        )

        try:
            for entry in self._sys_temp.iterdir():
                if not entry.is_dir():
                    continue
                name = entry.name
                if not any(name.startswith(p) for p in prefixes):
                    continue
                try:
                    size = self._dir_size(entry)
                    shutil.rmtree(entry, ignore_errors=True)
                    stats.temp_dirs_removed += 1
                    stats.temp_dirs_freed_bytes += size
                    logger.debug(f"CleanupManager:清理临时目录 {entry.name}")
                except Exception as e:
                    stats.errors.append(f"temp {entry.name}: {e}")
        except Exception as e:
            stats.errors.append(f"temp dir: {e}")

        if stats.temp_dirs_removed > 0:
            logger.info(
                f"CleanupManager:清理了 {stats.temp_dirs_removed} 个残留临时目录，"
                f"释放 {stats.temp_dirs_freed_bytes / 1024:.1f} KB"
            )
        return stats

    def cleanup_pycache(self) -> CleanupStats:
        """清理项目内 __pycache__ 目录和 .pyc 文件。

        仅在开发/测试环境调用，生产环境不自动清理。
        由 CLEANUP_PYCACHE 环境变量控制，默认 false。

        Returns:
            清理统计
        """
        stats = CleanupStats()
        if os.environ.get("CLEANUP_PYCACHE", "false").lower() != "true":
            return stats

        try:
            for pycache in self._base_dir.rglob("__pycache__"):
                if ".venv" in str(pycache) or "venv" in str(pycache) or "site-packages" in str(pycache):
                    continue
                try:
                    size = self._dir_size(pycache)
                    shutil.rmtree(pycache, ignore_errors=True)
                    stats.pycache_removed += 1
                    stats.pycache_freed_bytes += size
                except Exception as e:
                    stats.errors.append(f"pycache {pycache}: {e}")
            for pgc in self._base_dir.rglob("*.pyc"):
                if ".venv" in str(pgc) or "venv" in str(pgc) or "site-packages" in str(pgc):
                    continue
                try:
                    size = pgc.stat().st_size
                    pgc.unlink()
                    stats.pycache_removed += 1
                    stats.pycache_freed_bytes += size
                except Exception:
                    pass
        except Exception as e:
            stats.errors.append(f"pycache scan: {e}")

        if stats.pycache_removed > 0:
            logger.info(
                f"CleanupManager:清理了 {stats.pycache_removed} 个 pycache，"
                f"释放 {stats.pycache_freed_bytes / 1024:.1f} KB"
            )
        return stats

    def cleanup_task_dir(self, task_id: str) -> bool:
        """立即清理指定任务的工作目录（双重校验路径）。

        Args:
            task_id: 任务 ID

        Returns:
            是否成功清理
        """
        if not task_id:
            return False
        task_dir = (self._work_dir_root / task_id).resolve()
        if not task_dir.is_relative_to(self._work_dir_root.resolve()):
            logger.warning(f"CleanupManager:路径越界: {task_id}")
            return False
        if not task_dir.exists():
            return False
        try:
            size = self._dir_size(task_dir)
            shutil.rmtree(task_dir, ignore_errors=True)
            logger.info(f"CleanupManager:手动清理任务目录 {task_id}，释放 {size / 1024:.1f} KB")
            return True
        except Exception as e:
            logger.error(f"CleanupManager:清理任务目录 {task_id} 失败: {e}")
            return False

    def get_status(self) -> dict:
        """获取清理管理器状态。"""
        return {
            "enabled": self.enabled,
            "work_dir_ttl_hours": round(self.work_dir_ttl / 3600, 1),
            "log_ttl_days": round(self.log_ttl / 86400, 1),
            "evidence_ttl_hours": round(self.evidence_ttl / 3600, 1),
            "interval_hours": round(self.interval / 3600, 1),
            "last_cleanup_time": self._last_cleanup_time,
            "last_stats": self._last_stats.to_dict(),
            "work_dir_count": self._count_dirs(self._work_dir_root),
            "log_count": self._count_files(self._log_dir),
            "evidence_count": self._count_dirs(self._evidence_dir),
        }

    @staticmethod
    def _dir_size(path: Path) -> int:
        """计算目录总大小（字节）。"""
        total = 0
        try:
            for f in path.rglob("*"):
                if f.is_file():
                    try:
                        total += f.stat().st_size
                    except Exception:
                        pass
        except Exception:
            pass
        return total

    @staticmethod
    def _count_dirs(path: Path) -> int:
        """统计目录下的子目录数量。"""
        if not path.exists():
            return 0
        try:
            return sum(1 for e in path.iterdir() if e.is_dir())
        except Exception:
            return 0

    @staticmethod
    def _count_files(path: Path) -> int:
        """统计目录下的文件数量。"""
        if not path.exists():
            return 0
        try:
            return sum(1 for e in path.iterdir() if e.is_file())
        except Exception:
            return 0


def get_cleanup_manager() -> CleanupManager:
    """获取清理管理器单例。"""
    return CleanupManager.get_instance()
