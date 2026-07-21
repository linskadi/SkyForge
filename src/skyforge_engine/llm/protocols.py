"""LLM 客户端统一协议。

定义三种模式（Mock/API/Local）的统一接口，所有客户端实现必须满足此协议。
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class LLMClientProtocol(Protocol):
    """LLM 客户端统一协议。

    所有模式的客户端必须实现此协议，确保调用方可以透明切换后端。

    方法约定：
    - chat: 同步生成文本
    - chat_async: 异步生成文本
    - chat_stream: 流式生成文本
    - is_available: 检查客户端是否可用
    - get_available_models: 返回可用模型列表
    """

    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: Optional[list[str]] = None,
    ) -> str:
        """同步生成文本。"""
        ...

    async def chat_async(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: Optional[list[str]] = None,
    ) -> str:
        """异步生成文本。"""
        ...

    def chat_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Any:
        """流式生成文本。"""
        ...

    def is_available(self, force_recheck: bool = False) -> bool:
        """检查客户端是否可用。"""
        ...

    def get_available_models(self) -> list[str]:
        """返回可用模型列表。"""
        ...
