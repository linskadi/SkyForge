"""Local LLM 客户端。

纯本地实现，支持 Ollama 和 LM Studio。
不做任何降级，后端不可用时直接抛出异常。
"""

import json
import os
from typing import Any, Optional

import httpx

from skyforge_engine.utils.log_util import logger


class LocalClient:
    """Local LLM 客户端。

    通过本地 LLM 服务（Ollama 或 LM Studio）进行推理。
    后端不可用时直接抛出异常，不做任何降级。
    """

    def __init__(
        self,
        provider: str = "ollama",
        base_url: Optional[str] = None,
        model: str = "qwen3:8b",
        timeout: int = 300,
    ):
        self.provider = provider.lower()
        self.base_url = base_url or self._detect_base_url(provider)
        self.model = model
        self.timeout = timeout
        self._available: Optional[bool] = None
        self._client = None
        self._async_client = None

    def _detect_base_url(self, provider: str) -> str:
        if provider == "ollama":
            return os.environ.get("SKYFORGE_OLLAMA_URL", "http://localhost:11434")
        elif provider == "lmstudio":
            return os.environ.get("SKYFORGE_LMSTUDIO_URL", "http://localhost:1234")
        else:
            return os.environ.get("SKYFORGE_LOCAL_URL", "http://localhost:11434")

    def _ensure_client(self):
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)

    def _ensure_async_client(self):
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self.timeout)

    def _build_request(self, prompt: str, system_prompt: str, **kwargs) -> dict:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "stream": False,
        }

        if kwargs.get("stop"):
            request["stop"] = kwargs["stop"]

        return request

    def _build_stream_request(self, prompt: str, system_prompt: str, **kwargs) -> dict:
        request = self._build_request(prompt, system_prompt, **kwargs)
        request["stream"] = True
        return request

    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: Optional[list[str]] = None,
    ) -> str:
        self._ensure_client()

        if not self.is_available():
            raise RuntimeError(
                f"本地 LLM 服务不可用，请检查 {self.provider} 是否已启动。"
                f"预期地址: {self.base_url}"
            )

        request = self._build_request(prompt, system_prompt, temperature=temperature, max_tokens=max_tokens, stop=stop)

        try:
            response = self._client.post(
                f"{self.base_url.rstrip('/')}/v1/chat/completions",
                json=request,
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"].get("content", "")
            logger.info(f"LocalClient.chat: generated {len(content)} chars")
            return content
        except Exception as e:
            logger.error(f"LocalClient.chat failed: {str(e)}")
            raise

    async def chat_async(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: Optional[list[str]] = None,
    ) -> str:
        self._ensure_async_client()

        if not self.is_available():
            raise RuntimeError(
                f"本地 LLM 服务不可用，请检查 {self.provider} 是否已启动。"
                f"预期地址: {self.base_url}"
            )

        request = self._build_request(prompt, system_prompt, temperature=temperature, max_tokens=max_tokens, stop=stop)

        try:
            response = await self._async_client.post(
                f"{self.base_url.rstrip('/')}/v1/chat/completions",
                json=request,
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"].get("content", "")
            logger.info(f"LocalClient.chat_async: generated {len(content)} chars")
            return content
        except Exception as e:
            logger.error(f"LocalClient.chat_async failed: {str(e)}")
            raise

    def chat_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Any:
        self._ensure_client()

        if not self.is_available():
            raise RuntimeError(
                f"本地 LLM 服务不可用，请检查 {self.provider} 是否已启动。"
                f"预期地址: {self.base_url}"
            )

        request = self._build_stream_request(prompt, system_prompt, temperature=temperature, max_tokens=max_tokens)

        try:
            response = self._client.post(
                f"{self.base_url.rstrip('/')}/v1/chat/completions",
                json=request,
                stream=True,
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"LocalClient.chat_stream failed: {str(e)}")
            raise

        def stream():
            for line in response.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            content = chunk["choices"][0]["delta"].get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        return stream()

    def is_available(self, force_recheck: bool = False) -> bool:
        if force_recheck or self._available is None:
            try:
                self._ensure_client()
                response = self._client.get(
                    f"{self.base_url.rstrip('/')}/api/tags",
                    timeout=5,
                )
                self._available = response.status_code == 200
                if self._available:
                    logger.info(f"Local LLM ({self.provider}) 可用: {self.base_url}")
            except Exception as e:
                self._available = False
                logger.warning(f"Local LLM ({self.provider}) 不可用: {str(e)}")

        return self._available

    def get_available_models(self) -> list[str]:
        try:
            self._ensure_client()
            response = self._client.get(
                f"{self.base_url.rstrip('/')}/api/tags",
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            if self.provider == "ollama":
                return [model["name"] for model in result.get("models", [])]
            else:
                return [model.get("name", "") for model in result.get("models", [])]
        except Exception as e:
            logger.error(f"LocalClient.get_available_models failed: {str(e)}")
            return []
