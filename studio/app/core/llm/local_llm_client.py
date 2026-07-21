# -*- coding: utf-8 -*-
"""L3 LLM 客户端：转发到 L1 skyforge_llm.client。

历史上 L3 有独立的 local_llm_client 实现（与 L1 src/skyforge_llm/client.py 重复），
2026-07 重构后统一使用 L1 实现作为唯一来源。本文件保留 import 路径兼容性，
避免破坏既有 `from app.core.llm.local_llm_client import ...` 引用。

注意：
- LMStudioClient / UnifiedLLMClient 类定义直接复用 L1，不再维护副本
- 测试代码通过 `lmstudio_module._unified_client = None` 重置单例，因此本模块
  保留自己的 _unified_client 状态，并覆写 get_lmstudio_client / get_local_llm_client
  以使用本模块的单例（与 L1 单例解耦，避免互相污染）
"""

from typing import Optional

from skyforge_llm.client import LMStudioClient, UnifiedLLMClient  # noqa: F401

__all__ = [
    "LMStudioClient",
    "UnifiedLLMClient",
    "get_lmstudio_client",
    "get_local_llm_client",
]


# 本模块独立维护的单例（测试通过 lmstudio_module._unified_client = None 重置）
_unified_client: Optional[UnifiedLLMClient] = None


def get_lmstudio_client() -> UnifiedLLMClient:
    """获取统一 LLM 客户端单例（向后兼容历史命名）。

    返回 UnifiedLLMClient，接口与 LMStudioClient 完全兼容，
    自动回退：本地 GGUF → 本地 LLM → Mock。
    """
    global _unified_client
    if _unified_client is None:
        _unified_client = UnifiedLLMClient()
    return _unified_client


# 向后兼容别名（历史命名，逐步迁移到 get_local_llm_client）
get_local_llm_client = get_lmstudio_client
