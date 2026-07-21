# -*- coding: utf-8 -*-
"""L3 LLM 模块入口 — 注册 L3 单例为 L0 LLM 客户端 provider。

历史上下文：L0 (skyforge_engine) 曾通过 ``try: from studio.app.core.llm...``
反向 import L3 的 ``local_llm_client`` 单例。2026-07 L0→L3 反向依赖修复后，
L0 改为通过 ``skyforge_engine.llm_provider.set_llm_client_provider`` 注入点接收
L3 实现。本模块在 L3 包加载时注册 L3 的 ``get_local_llm_client``，使：

- L0 Agent 通过 ``get_llm_client()`` 拿到的就是 L3 单例
- L3 测试通过 ``lmstudio_module._unified_client = None`` 重置单例的既有套路依然
  生效（provider 每次调用都读取 L3 单例的最新状态）
- L0 独立运行（无 L3）时回退到 L1 ``skyforge_llm.client``（见 llm_provider.py）
"""

from app.core.llm.local_llm_client import (
    LMStudioClient,
    UnifiedLLMClient,
    get_local_llm_client,
    get_lmstudio_client,
)
from skyforge_engine.llm_provider import set_llm_client_provider

# 注册 L3 单例为 L0 LLM 客户端 provider（覆盖 L0 默认的 L1 回退实现）
set_llm_client_provider(get_local_llm_client)

__all__ = [
    "LMStudioClient",
    "UnifiedLLMClient",
    "get_lmstudio_client",
    "get_local_llm_client",
]
