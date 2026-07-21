"""模型选择与编码规则检索路由。

GET  /api/models 列出可用模型
POST /api/models/select 手动选择模型
GET  /api/llm/status 查询本地 LLM 状态
GET  /api/misra/search 搜索 MISRA-C 规则（向后兼容）
GET  /api/misra/categories 获取规则分类统计
GET  /api/misra/rules 列出规则
GET  /api/rules/standards 列出所有可用规则集
GET  /api/rules/search 搜索指定规则集的规则（支持 standard_id 参数）
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.auth import require_write_access

from app.core.llm.local_llm_client import get_local_llm_client as get_lmstudio_client
from app.core.llm.model_router import get_model_router
from app.rag.misra_searcher import (
    MisraRuleSearcher,
    get_searcher,
    get_standards,
)
from app.utils.log_util import logger

router = APIRouter()


# ============================================================================ #
# 多模型路由 API
# ============================================================================ #


class ModelSelectRequest(BaseModel):
    """手动选择模型请求体。"""

    model_id: str


@router.get("/api/models")
async def list_models() -> dict[str, Any]:
    """列出 LM Studio 中所有可用模型。"""
    router_ = get_model_router()
    models = router_.list_available_models()
    return {
        "models": models,
        "selected": router_._manual_selection,
    }


@router.post("/api/models/select")
async def select_model(
    req: ModelSelectRequest,
    _user: str = Depends(require_write_access),
) -> dict[str, Any]:
    """手动选择模型。传空字符串可恢复自动路由。"""
    router_ = get_model_router()
    model_id = req.model_id or None
    router_.set_manual_selection(model_id)
    info = router_.get_model_info(req.model_id)
    logger.info(f"/api/models/select 设置为 {req.model_id}, loaded={info['loaded']}")
    return {
        "model_id": req.model_id,
        "model_info": info,
    }


# ============================================================================ #
# LLM 状态 API
# ============================================================================ #


@router.get("/api/llm/status")
async def llm_status() -> dict[str, Any]:
    """查询 LLM 状态（Local / LM Studio / Mock）。"""
    client = get_lmstudio_client()
    return {
        "available": client.is_available(),
        "models": client.get_available_models(),
        "use_llm": client.use_llm,
        "active_backend": client.get_active_backend(),
    }


# ============================================================================ #
# MISRA-C 规则检索 API（RAG 知识库）
# ============================================================================ #


@router.get("/api/misra/search")
async def misra_search(
    q: str = Query(..., description="搜索关键词"),
    top_k: int = Query(5, ge=1, le=50, description="返回最多 top_k 条规则"),
) -> dict[str, Any]:
    """搜索 MISRA-C 规则。支持中文/英文关键词、规则 ID。"""
    searcher = MisraRuleSearcher.get_instance()
    results = searcher.search(q, top_k=top_k)
    return {
        "query": q,
        "top_k": top_k,
        "count": len(results),
        "rules": [r.to_dict() for r in results],
    }


@router.get("/api/misra/categories")
async def misra_categories() -> dict[str, Any]:
    """获取 MISRA-C 规则分类统计。"""
    searcher = MisraRuleSearcher.get_instance()
    all_rules = searcher.get_all_rules()
    cat_summary = searcher.get_categories_summary()
    sev_summary = searcher.get_severity_summary()
    categories = [
        {"category": cat, "count": count}
        for cat, count in sorted(cat_summary.items(), key=lambda x: x[1], reverse=True)
    ]
    severity = [
        {"severity": sev, "count": count}
        for sev, count in sorted(sev_summary.items(), key=lambda x: x[1], reverse=True)
    ]
    return {
        "total": len(all_rules),
        "categories": categories,
        "severity": severity,
    }


@router.get("/api/misra/rules")
async def misra_list_rules(
    category: str | None = Query(None, description="按分类过滤"),
    limit: int = Query(0, ge=0, le=500, description="限制返回数量，0=全部"),
) -> dict[str, Any]:
    """列出 MISRA-C 规则。"""
    searcher = MisraRuleSearcher.get_instance()
    if category:
        rules = searcher.get_rules_by_category(category)
    else:
        rules = searcher.get_all_rules()
    if limit > 0:
        rules = rules[:limit]
    return {
        "total": len(searcher.get_all_rules()),
        "count": len(rules),
        "rules": [r.to_dict() for r in rules],
    }


# ============================================================================ #
# 多规则集 API（支持 MISRA-C / MISRA-C++ / Python 军工规范）
# ============================================================================ #


@router.get("/api/rules/standards")
async def list_rule_standards() -> dict[str, Any]:
    """列出所有可用的规则集。

    返回格式：
        {
            "standards": [
                {"id": "misra_c_2012", "name": "MISRA-C:2012", "language": "c", "version": "2012"},
                {"id": "jsf_av_cpp", "name": "MISRA-C++ / JSF AV C++", "language": "cpp", "version": "2023"},
                {"id": "python_safety", "name": "Python 军工软件编程规范", "language": "python", "version": "2023"}
            ]
        }
    """
    return {"standards": get_standards()}


@router.get("/api/rules/search")
async def rules_search(
    q: str = Query(..., description="搜索关键词"),
    standard_id: str = Query(
        "misra_c_2012",
        description="规则集 ID：misra_c_2012 / jsf_av_cpp / python_safety",
    ),
    top_k: int = Query(5, ge=1, le=50, description="返回最多 top_k 条规则"),
) -> dict[str, Any]:
    """搜索指定规则集的规则。

    支持的 standard_id：
    - misra_c_2012：MISRA-C:2012（C 语言）
    - jsf_av_cpp：MISRA-C++/JSF AV C++/CERT C++（C++ 语言）
    - python_safety：Python 军工软件编程规范（Python 语言）

    支持中文/英文关键词、规则 ID（如 "Rule 8.1" / "Rule P-01" / "Rule JSF-001"）。
    """
    searcher = get_searcher(standard_id)
    results = searcher.search(q, top_k=top_k)
    return {
        "query": q,
        "standard_id": standard_id,
        "top_k": top_k,
        "count": len(results),
        "rules": [r.to_dict() for r in results],
    }
