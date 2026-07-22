"""API LLM 客户端。

纯 API 实现，支持 OpenAI/Anthropic 兼容接口。
不做任何降级，后端不可用时直接抛出异常。
"""

import asyncio
import json
import os
import time
from typing import Any, Dict, Optional

import httpx

from skyforge_engine.utils.log_util import logger


class APIClient:
    """API LLM 客户端。

    通过 HTTP API 调用远程 LLM 服务（OpenAI/Anthropic 兼容）。
    后端不可用时直接抛出异常，不做任何降级。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_type: str = "openai",
        max_retries: int = 3,
        timeout: int = 180,
    ):
        self.api_key = (
            api_key
            or os.environ.get("SKYFORGE_API_KEY")
            or os.environ.get("LLM_API_KEY")
        )
        self.base_url = (
            base_url
            or os.environ.get("SKYFORGE_API_BASE_URL")
            or os.environ.get("LOCAL_LLM_BASE_URL")
            or os.environ.get("LMSTUDIO_BASE_URL")
        )
        self.model = (
            model
            or os.environ.get("SKYFORGE_API_MODEL")
            or os.environ.get("LLM_MODEL")
            or "gpt-4o-mini"
        )
        self.api_type = api_type.lower()
        self.max_retries = max_retries
        self.timeout = timeout
        self._available: Optional[bool] = None
        self._client = None
        self._async_client = None

    def _ensure_client(self):
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)

    def _ensure_async_client(self):
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self.timeout)

    def _build_request(self, prompt: str, system_prompt: str, **kwargs) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        if kwargs.get("stop"):
            request["stop"] = kwargs["stop"]

        return request

    def _endpoint(self, path: str) -> str:
        base_url = (self.base_url or "").rstrip("/")
        prefix = base_url if base_url.endswith("/v1") else f"{base_url}/v1"
        return f"{prefix}/{path.lstrip('/')}"

    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: Optional[list[str]] = None,
    ) -> str:
        self._ensure_client()

        if not self.api_key:
            raise ValueError("API Key 未配置，请设置 LLM_API_KEY 或 SKYFORGE_API_KEY 环境变量")
        if not self.base_url:
            raise ValueError("API Base URL 未配置，请设置 LOCAL_LLM_BASE_URL 或 SKYFORGE_API_BASE_URL 环境变量")

        request = self._build_request(prompt, system_prompt, temperature=temperature, max_tokens=max_tokens, stop=stop)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        for attempt in range(self.max_retries):
            try:
                response = self._client.post(
                    self._endpoint("chat/completions"),
                    headers=headers,
                    json=request,
                )
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"].get("content", "")
                finish_reason = result["choices"][0].get("finish_reason", "")
                usage = result.get("usage", {})
                # 推理模型（如 deepseek-v4-flash）可能 content 为空但 reasoning_content 有值
                if not content:
                    reasoning = result["choices"][0]["message"].get("reasoning_content", "")
                    if reasoning:
                        logger.warning(f"APIClient.chat: content 为空，使用 reasoning_content ({len(reasoning)} chars) 作为 fallback")
                        content = reasoning
                logger.info(f"APIClient.chat: generated {len(content)} chars, finish_reason={finish_reason}, usage={usage}")
                if finish_reason == "length":
                    logger.warning(f"APIClient.chat: response truncated due to max_tokens limit! Consider increasing max_tokens.")
                return content
            except Exception as e:
                logger.error(f"APIClient.chat attempt {attempt + 1}/{self.max_retries} failed: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

        return ""

    async def chat_async(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: Optional[list[str]] = None,
    ) -> str:
        self._ensure_async_client()

        if not self.api_key:
            raise ValueError("API Key 未配置，请设置 LLM_API_KEY 或 SKYFORGE_API_KEY 环境变量")
        if not self.base_url:
            raise ValueError("API Base URL 未配置，请设置 LOCAL_LLM_BASE_URL 或 SKYFORGE_API_BASE_URL 环境变量")

        request = self._build_request(prompt, system_prompt, temperature=temperature, max_tokens=max_tokens, stop=stop)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        for attempt in range(self.max_retries):
            try:
                response = await self._async_client.post(
                    self._endpoint("chat/completions"),
                    headers=headers,
                    json=request,
                )
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"].get("content", "")
                finish_reason = result["choices"][0].get("finish_reason", "")
                usage = result.get("usage", {})
                # 推理模型（如 deepseek-v4-flash）可能 content 为空但 reasoning_content 有值
                if not content:
                    reasoning = result["choices"][0]["message"].get("reasoning_content", "")
                    if reasoning:
                        logger.warning(f"APIClient.chat_async: content 为空，使用 reasoning_content ({len(reasoning)} chars) 作为 fallback")
                        content = reasoning
                logger.info(f"APIClient.chat_async: generated {len(content)} chars, finish_reason={finish_reason}, usage={usage}")
                if finish_reason == "length":
                    logger.warning(f"APIClient.chat_async: response truncated due to max_tokens limit! Consider increasing max_tokens.")
                return content
            except Exception as e:
                logger.error(f"APIClient.chat_async attempt {attempt + 1}/{self.max_retries} failed: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

        return ""

    def chat_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Any:
        self._ensure_client()

        if not self.api_key:
            raise ValueError("API Key 未配置，请设置 LLM_API_KEY 或 SKYFORGE_API_KEY 环境变量")
        if not self.base_url:
            raise ValueError("API Base URL 未配置，请设置 LOCAL_LLM_BASE_URL 或 SKYFORGE_API_BASE_URL 环境变量")

        request_body = self._build_request(prompt, system_prompt, temperature=temperature, max_tokens=max_tokens)
        request_body["stream"] = True
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        # httpx.Client.post() 不接受 stream 参数，需用 Client.send() + stream=True
        req = httpx.Request(
            "POST",
            self._endpoint("chat/completions"),
            headers=headers,
            json=request_body,
        )
        response = self._client.send(req, stream=True)
        response.raise_for_status()

        def stream():
            try:
                for line in response.iter_lines():
                    if line:
                        if isinstance(line, bytes):
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
            finally:
                response.close()

        return stream()

    def is_available(self, force_recheck: bool = False) -> bool:
        if force_recheck or self._available is None:
            try:
                self._ensure_client()
                if not self.api_key or not self.base_url:
                    self._available = False
                    return False

                headers = {"Authorization": f"Bearer {self.api_key}"}
                response = self._client.get(
                    self._endpoint("models"),
                    headers=headers,
                    timeout=5,
                )
                self._available = response.status_code == 200
            except Exception:
                self._available = False

        return self._available

    def get_available_models(self) -> list[str]:
        try:
            self._ensure_client()
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = self._client.get(
                self._endpoint("models"),
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            return [model["id"] for model in result.get("data", [])]
        except Exception as e:
            logger.error(f"APIClient.get_available_models failed: {str(e)}")
            return []
