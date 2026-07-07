# -*- coding: utf-8 -*-
"""LM Studio 轻量级客户端，提供 OpenAI 兼容 API 调用。

直接用 httpx 调用 LM Studio Local Server（localhost:1234/v1），
不依赖重型组件。

使用方式：
    client = LMStudioClient()
    if client.is_available():
        response = client.chat("你好")
    else:
        response = "LM Studio 不可用，使用 Mock"
"""

import os
import json
import httpx
from typing import Optional
from app.utils.log_util import logger


class LMStudioClient:
    """LM Studio 轻量级客户端。

    通过 OpenAI 兼容 API 调用 LM Studio Local Server。
    支持 USE_LLM 开关控制是否使用真实 LLM。
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        use_llm: Optional[bool] = None,
        timeout: int = 300,
    ):
        """初始化 LM Studio 客户端。

        Args:
            base_url: LM Studio API 地址，默认从环境变量读取
            model: 模型 ID，默认从环境变量读取
            use_llm: 是否使用真实 LLM，默认从环境变量 USE_LLM 读取
            timeout: 请求超时时间（秒），LM Studio 首次推理可能较慢
        """
        self.base_url = base_url or os.getenv(
            "LMSTUDIO_BASE_URL", "http://localhost:1234/v1"
        )
        self.model = model or os.getenv("LMSTUDIO_MODEL", "google/gemma-4-e4b")
        self.use_llm = (
            use_llm
            if use_llm is not None
            else (os.getenv("USE_LLM", "false").lower() == "true")
        )
        self.timeout = timeout
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """检查 LM Studio 是否可用（server 已启动 + 至少一个模型已加载）。

        Returns:
            True 如果 LM Studio 可用且 USE_LLM=true
        """
        if not self.use_llm:
            return False
        if self._available is not None:
            return self._available
        try:
            resp = httpx.get(f"{self.base_url}/models", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id", "") for m in data.get("data", [])]
                self._available = len(models) > 0
                if self._available:
                    logger.info(f"LM Studio 可用，已加载模型: {models}")
                else:
                    logger.warning("LM Studio 运行中但无模型加载")
            else:
                self._available = False
                logger.warning(f"LM Studio 返回 {resp.status_code}")
        except Exception as e:
            self._available = False
            logger.warning(f"LM Studio 不可用: {e}")
        return self._available

    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """同步调用 LM Studio 生成回复。

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Returns:
            LLM 生成的文本，如果不可用则返回空字符串
        """
        if not self.is_available():
            return ""

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                logger.info(
                    f"LM Studio 响应: model={self.model} "
                    f"tokens={data.get('usage', {}).get('total_tokens', '?')}"
                )
                return content
            else:
                logger.error(f"LM Studio 返回 {resp.status_code}: {resp.text[:200]}")
                return ""
        except Exception as e:
            logger.error(f"LM Studio 调用失败: {e}")
            return ""

    async def chat_async(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """异步调用 LM Studio 生成回复。

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Returns:
            LLM 生成的文本
        """
        if not self.is_available():
            return ""

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.error(f"LM Studio 返回 {resp.status_code}")
                return ""
        except Exception as e:
            logger.error(f"LM Studio 异步调用失败: {e}")
            return ""

    async def chat_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        """流式调用 LM Studio，逐 token 生成（用于 Patch 4 打字机效果）。

        Yields:
            每个 token 的文本片段
        """
        if not self.is_available():
            return

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": True,
                    },
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"LM Studio 流式调用失败: {e}")

    def get_available_models(self) -> list[str]:
        """获取 LM Studio 中已加载的模型列表。

        Returns:
            模型 ID 列表
        """
        try:
            resp = httpx.get(f"{self.base_url}/models", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("id", "") for m in data.get("data", [])]
        except Exception:
            pass
        return []


# 全局单例
_lmstudio_client: Optional[LMStudioClient] = None


def get_lmstudio_client() -> LMStudioClient:
    """获取 LM Studio 客户端单例。"""
    global _lmstudio_client
    if _lmstudio_client is None:
        _lmstudio_client = LMStudioClient()
    return _lmstudio_client
