"""Cppcheck 扫描 Stage。"""

from __future__ import annotations

from typing import Any

from skyforge_engine.core.protocols import StageResult
from skyforge_engine.core.stages._utils import (
    _flush_collected_logs,
    _make_sync_log_collector,
    _normalize_hook,
)


class CppcheckStage:
    """Cppcheck MISRA-C 扫描。"""

    def __init__(self, language: str = "c") -> None:
        self._language = language

    @property
    def name(self) -> str:
        return "cppcheck"

    @property
    def description(self) -> str:
        return "Cppcheck MISRA-C 扫描"

    async def execute(
        self, artifact: dict[str, Any], context: dict[str, Any] | None = None
    ) -> StageResult:
        from skyforge_engine.tools.cppcheck_scanner import scan_multi

        context = context or {}
        hook = _normalize_hook(context.get("log_hook"))
        code = artifact.get("code", "")

        await hook("SYSTEM", "info", "启动 Cppcheck MISRA-C 扫描")
        sync_cb, pending_logs = _make_sync_log_collector()
        cppcheck_result = scan_multi(code, language=self._language, log_callback=sync_cb)
        await _flush_collected_logs(hook, pending_logs)
        level = "success" if not cppcheck_result else "warn"
        await hook(
            "SYSTEM",
            level,
            f"Cppcheck 扫描完成 violations={len(cppcheck_result)}",
        )
        artifact["cppcheck_result"] = cppcheck_result
        return StageResult(artifact=artifact, status="success")
