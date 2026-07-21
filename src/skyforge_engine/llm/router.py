"""LLM 模式路由器。

根据 SKYFORGE_LLM_MODE 环境变量路由到对应客户端。
严格分离 Mock/API/Local 三种模式，不做任何降级。
"""

import os
from enum import Enum
from typing import Optional

from skyforge_engine.llm.mock_client import MockClient
from skyforge_engine.llm.api_client import APIClient
from skyforge_engine.llm.local_client import LocalClient
from skyforge_engine.utils.log_util import logger


class LLMMode(Enum):
    """LLM 后端运行模式。"""

    MOCK = "mock"
    API = "api"
    LOCAL = "local"


class LLMBackendUnavailableError(RuntimeError):
    """当前 LLM 后端不可用异常。"""

    def __init__(self, backend: str, message: str):
        super().__init__(message)
        self.backend = backend
        self.message = message


class LLMRouter:
    """LLM 模式路由器。

    根据配置的模式返回对应客户端实例，不做任何降级处理。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
            cls._instance._mode = None
        return cls._instance

    def get_mode(self) -> LLMMode:
        """获取当前配置的 LLM 模式。

        每次调用都重新读取环境变量，确保模式切换立即生效。
        """
        raw = os.environ.get("SKYFORGE_LLM_MODE", "mock").strip().lower()
        try:
            return LLMMode(raw)
        except ValueError:
            logger.warning(f"无效的 LLM 模式: {raw}，默认使用 mock")
            return LLMMode.MOCK

    def get_client(self) -> Optional[MockClient | APIClient | LocalClient]:
        """获取当前模式对应的 LLM 客户端。

        根据 SKYFORGE_LLM_MODE 返回：
        - mock: MockClient
        - api: APIClient
        - local: LocalClient

        不做任何降级，若后端不可用，客户端的 is_available() 将返回 False，
        调用 chat() 时会直接抛出异常。

        每次调用都检查模式是否改变，若改变则重新创建客户端。
        """
        mode = self.get_mode()

        if self._client is None or (hasattr(self, '_last_mode') and self._last_mode != mode):
            logger.info(f"初始化 LLM 客户端，模式: {mode.value}")

            match mode:
                case LLMMode.MOCK:
                    self._client = MockClient()
                case LLMMode.API:
                    self._client = APIClient()
                case LLMMode.LOCAL:
                    provider = os.environ.get("SKYFORGE_LOCAL_PROVIDER", "ollama")
                    self._client = LocalClient(provider=provider)

            self._last_mode = mode

        return self._client

    def reset(self):
        """重置路由器状态。"""
        self._client = None
        self._mode = None


def get_current_mode() -> LLMMode:
    """获取当前 LLM 模式。"""
    return LLMRouter().get_mode()


def get_client() -> Optional[MockClient | APIClient | LocalClient]:
    """获取当前模式的 LLM 客户端。"""
    return LLMRouter().get_client()


def require_mode(expected: LLMMode) -> None:
    """模式守卫：要求当前模式必须等于 expected。"""
    current = get_current_mode()
    if current != expected:
        raise LLMBackendUnavailableError(
            backend=current.value,
            message=f"当前 LLM 模式为 {current.value.upper()}，"
                    f"但此操作要求 {expected.value.upper()} 模式。",
        )


__all__ = [
    "LLMMode",
    "LLMBackendUnavailableError",
    "LLMRouter",
    "get_current_mode",
    "get_client",
    "require_mode",
]
