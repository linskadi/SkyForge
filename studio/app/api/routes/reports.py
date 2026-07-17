"""DO-178C 合规报告路由：生成和下载。

POST /api/report 生成 HTML 报告
GET  /api/report/download 下载 HTML 报告
"""

import time
from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel

from skyforge_engine.report.traceability_matrix import build_matrix
from skyforge_engine.report.do178_objectives import check_objectives
from skyforge_engine.report.report_generator import generate_report
from skyforge_engine.utils.log_util import logger

router = APIRouter()

# Session-scoped report cache: keyed by session ID,
# auto-cleans entries older than 1 hour.
# NOTE: 单实例内存缓存，适用于开发和演示。生产多实例部署应替换为 Redis。
_report_cache: dict[str, dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour
_CACHE_MAX_ENTRIES = 50  # 防止内存无限增长


def _cleanup_report_cache() -> None:
    """Remove cache entries older than TTL and enforce max size."""
    now = time.time()
    expired = [
        k
        for k, v in _report_cache.items()
        if now - v["created_at"] > _CACHE_TTL_SECONDS
    ]
    for k in expired:
        del _report_cache[k]
    # Enforce max entries: remove oldest if over limit
    if len(_report_cache) > _CACHE_MAX_ENTRIES:
        sorted_keys = sorted(
                      _report_cache,
                      key=lambda k: _report_cache[k]["created_at"],
                      )
        for k in sorted_keys[: len(_report_cache) - _CACHE_MAX_ENTRIES]:
            del _report_cache[k]


def _store_report(report_html: str, pipeline_result: dict[str, Any]) -> str:
    """Store report and return a session ID."""
    _cleanup_report_cache()
    session_id = f"report-{int(time.time() * 1000)}"
    _report_cache[session_id] = {
        "html": report_html,
        "pipeline_result": pipeline_result,
        "created_at": time.time(),
    }
    return session_id


def _get_report(session_id: str) -> str | None:
    """Retrieve report HTML by session ID; returns None if expired or missing."""
    _cleanup_report_cache()
    entry = _report_cache.get(session_id)
    if entry is None:
        return None
    if time.time() - entry["created_at"] > _CACHE_TTL_SECONDS:
        del _report_cache[session_id]
        return None
    return entry["html"]


def _get_latest_report() -> str | None:
    """Retrieve the most recent report HTML (backward-compatible helper)."""
    _cleanup_report_cache()
    if not _report_cache:
        return None
    latest_key = max(_report_cache, key=lambda k: _report_cache[k]["created_at"])
    return _report_cache[latest_key]["html"]


class ReportRequest(BaseModel):
    """DO-178C 合规报告生成接口请求体。

    pipeline_result 为 /api/generate 返回的全流程结果字典。
    """

    pipeline_result: dict[str, Any]


@router.post("/api/report")
async def report(req: ReportRequest) -> dict[str, Any]:
    """生成 DO-178C 合规报告（HTML），含追溯矩阵和目标检查。"""
    logger.info(
        f"/api/report 收到 pipeline_result keys={list(req.pipeline_result.keys())}"
    )
    pipeline_result = req.pipeline_result

    matrix_entries = build_matrix(pipeline_result)
    traceability_matrix = [e.to_dict() for e in matrix_entries]

    obj_results = check_objectives(pipeline_result)
    do178_objectives = [o.to_dict() for o in obj_results]

    report_html = generate_report(pipeline_result)

    session_id = _store_report(report_html, pipeline_result)

    return {
        "report_html": report_html,
        "traceability_matrix": traceability_matrix,
        "do178_objectives": do178_objectives,
        "session_id": session_id,
    }


@router.get("/api/report/download")
async def report_download(session_id: str | None = None) -> Response:
    """下载最近一次生成的 HTML 报告。

    Args:
        session_id: Optional session ID from POST /api/report response.
                    Falls back to most recent report if omitted.
    """
    if session_id:
        html = _get_report(session_id)
    else:
        html = _get_latest_report()

    if not html:
        html = (
            "<html><body><h1>暂无可下载的报告</h1>"
            "<p>请先调用 <code>POST /api/report</code> 生成报告。</p></body></html>"
        )

    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="do178c_report.html"',
        },
    )
