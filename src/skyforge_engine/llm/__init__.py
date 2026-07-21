"""LLM 客户端模块。

严格分离 Mock/API/Local 三种模式，通过路由器统一访问。

使用方式：
    from skyforge_engine.llm import get_client, get_current_mode, require_mode

    client = get_client()
    response = client.chat(prompt, system_prompt)
"""

from skyforge_engine.llm.protocols import LLMClientProtocol
from skyforge_engine.llm.mock_client import MockClient
from skyforge_engine.llm.api_client import APIClient
from skyforge_engine.llm.local_client import LocalClient
from skyforge_engine.llm.router import (
    LLMMode,
    LLMBackendUnavailableError,
    LLMRouter,
    get_current_mode,
    get_client,
    require_mode,
)

__all__ = [
    "LLMClientProtocol",
    "MockClient",
    "APIClient",
    "LocalClient",
    "LLMMode",
    "LLMBackendUnavailableError",
    "LLMRouter",
    "get_current_mode",
    "get_client",
    "require_mode",
]
