"""模型选择与 MISRA-C 规则检索路由。

GET  /api/models 列出可用模型
POST /api/models/select 手动选择模型
POST /api/models/clear 清除模型选择
GET  /api/llm/status 查询 LM Studio 状态
POST /api/llm/switch 切换 USE_LLM 开关
GET  /api/misra/search 搜索 MISRA-C 规则
GET  /api/misra/rule/{rule_id} 获取单条规则详情
GET  /api/misra/categories 获取规则分类统计
GET  /api/misra/rules 列出规则
"""

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.llm.lmstudio_client import get_lmstudio_client
from app.core.llm.model_router import get_model_router
from app.rag.misra_searcher import MisraRuleSearcher
from app.utils.log_util import logger

router = APIRouter()


# ============================================================================ #
# 多模型路由 API
# ============================================================================ #


class ModelSelectRequest(BaseModel):
    """手动选择模型请求体。"""

    model_id: str


class LlmSwitchRequest(BaseModel):
    """LLM 开关切换请求体。"""

    use_llm: bool


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
async def select_model(req: ModelSelectRequest) -> dict[str, Any]:
    """手动选择模型。传空字符串或调用 /api/models/clear 可恢复自动路由。"""
    router_ = get_model_router()
    model_id = req.model_id or None
    router_.set_manual_selection(model_id)
    info = router_.get_model_info(req.model_id)
    logger.info(f"/api/models/select 设置为 {req.model_id}, loaded={info['loaded']}")
    return {
        "model_id": req.model_id,
        "model_info": info,
    }


@router.post("/api/models/clear")
async def clear_model_selection() -> dict[str, Any]:
    """清除手动模型选择，恢复自动路由。"""
    router_ = get_model_router()
    router_.set_manual_selection(None)
    return {
        "selected": None,
        "message": "已清除手动选择，恢复任务类型自动路由",
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


@router.post("/api/llm/switch")
async def llm_switch(req: LlmSwitchRequest) -> dict[str, Any]:
    """切换 USE_LLM 开关（不重启服务）。"""
    client = get_lmstudio_client()
    client.use_llm = req.use_llm
    available = client.is_available(force_recheck=True)
    logger.info(f"USE_LLM 已切换为 {req.use_llm}，available={available}")
    return {
        "use_llm": client.use_llm,
        "available": available,
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


@router.get("/api/misra/rule/{rule_id}")
async def misra_get_rule(rule_id: str) -> dict[str, Any]:
    """获取单条 MISRA-C 规则详情。"""
    decoded = rule_id.replace("+", " ")
    searcher = MisraRuleSearcher.get_instance()
    rule = searcher.get_rule(decoded)
    if rule is None:
        return {"found": False, "rule_id": decoded, "rule": None}
    return {"found": True, "rule_id": decoded, "rule": rule.to_dict()}


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
