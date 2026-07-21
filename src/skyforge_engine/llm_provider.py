# -*- coding: utf-8 -*-
"""LLM 客户端 Provider — L0 依赖反转接口。

设计动机
--------
L0 (skyforge_engine) 通过 provider 模式反转依赖：
- L0 仅定义 ``LLMClientProtocol``（最小接口）+ ``set_llm_client_provider`` 注入点
- L0 模块统一调用 ``get_llm_client()`` 获取客户端
- L3 启动时（``studio/app/core/llm/__init__.py`` 加载时）调用
  ``set_llm_client_provider(get_local_llm_client)`` 注入自己的实现

本模块使用新的分层架构：
- Mock/API/Local 三种模式严格分离
- 通过 LLMRouter 根据 SKYFORGE_LLM_MODE 路由到对应客户端
- 不做任何降级，后端不可用时直接抛出异常
"""

from __future__ import annotations

from typing import Callable, Optional, Protocol, runtime_checkable

from skyforge_engine.llm.router import get_client


@runtime_checkable
class LLMClientProtocol(Protocol):
    """LLM 客户端最小接口（duck typing）。"""

    def is_available(self, force_recheck: bool = ...) -> bool: ...

    def chat(
        self,
        prompt: str,
        system_prompt: str = ...,
        temperature: float = ...,
        max_tokens: int = ...,
    ) -> str: ...

    async def chat_async(
        self,
        prompt: str,
        system_prompt: str = ...,
        temperature: float = ...,
        max_tokens: int = ...,
    ) -> str: ...

    def get_available_models(self) -> list[str]: ...


LLMClientProvider = Callable[[], Optional[LLMClientProtocol]]


def _default_provider() -> Optional[LLMClientProtocol]:
    """默认 provider：使用 LLMRouter 获取客户端。

    根据 SKYFORGE_LLM_MODE 环境变量路由到对应客户端。
    """
    return get_client()


_provider: LLMClientProvider = _default_provider


def set_llm_client_provider(provider: LLMClientProvider) -> None:
    """注入 LLM 客户端 provider（由 L3 启动时调用）。"""
    global _provider
    _provider = provider


def get_llm_client() -> Optional[LLMClientProtocol]:
    """获取 LLM 客户端（通过当前 provider）。"""
    return _provider()


get_lmstudio_client = get_llm_client


__all__ = [
    "LLMClientProtocol",
    "LLMClientProvider",
    "set_llm_client_provider",
    "get_llm_client",
    "get_lmstudio_client",
]
