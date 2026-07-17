# -*- coding: utf-8 -*-
"""LM Studio 轻量级客户端：本地开发用，httpx 直连 LM Studio。

何时使用此类（vs LLM 类）：
- 单轮 prompt 调用、无需历史管理 → 用 LMStudioClient
- 需要多轮对话、工具调用、Redis 流式推送 → 用 LLM（通过 LLMFactory 创建）

Pipeline 的 4 个 Agent 均使用本客户端（get_lmstudio_client() 单例）：
- RequirementParserAgent: 需求解析
- ContractGeneratorAgent: 契约生成
- CodeGeneratorAgent: 代码生成
- CodeRepairerAgent: 代码修复

直接用 httpx 调用 LM Studio Local Server（localhost:1234/v1），
不依赖重型组件。

使用方式：
    client = get_lmstudio_client()
    if client.is_available():
        response = client.chat("你好")
    else:
        response = "LM Studio 不可用，使用 Mock"
"""

import os
import json
import time
import httpx
from typing import Optional, AsyncGenerator
from skyforge_engine.utils.log_util import logger
from skyforge_llm.cache import get_llm_cache


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
        timeout: int = 900,
    ):
        """初始化 LM Studio 客户端。

        Args:
            base_url: LM Studio API 地址，默认从环境变量读取
            model: 模型 ID，默认从环境变量读取
            use_llm: 是否使用真实 LLM，默认从环境变量 USE_LLM 读取
            timeout: 请求超时时间（秒），LM Studio 首次推理可能较慢，默认900秒（15分钟）
        """
        self.base_url = base_url or os.getenv(
            "LMSTUDIO_BASE_URL", "http://localhost:1234/v1"
        )
        self.model = model or os.getenv("LMSTUDIO_MODEL", "google/gemma-4-e4b")
        self.use_llm = (
            use_llm
            if use_llm is not None
            else (os.getenv("USE_LLM", "true").lower() == "true")
        )
        self.timeout = timeout
        self._available: Optional[bool] = None
        self._last_check: float = 0.0
        self._cache_ttl: int = 60  # 缓存有效期（秒）
        # 连接池复用：单例 AsyncClient + 同步 Client
        self._async_client: Optional[httpx.AsyncClient] = None
        self._sync_client: Optional[httpx.Client] = None

    def _get_sync_client(self) -> httpx.Client:
        """获取或创建同步 HTTP 客户端（连接池复用）。"""
        if self._sync_client is None or self._sync_client.is_closed:
            self._sync_client = httpx.Client(
                timeout=self.timeout,
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                    keepalive_expiry=30,
                ),
            )
        return self._sync_client

    def _get_async_client(self) -> httpx.AsyncClient:
        """获取或创建异步 HTTP 客户端（连接池复用）。"""
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                    keepalive_expiry=30,
                ),
            )
        return self._async_client

    def is_available(self, force_recheck: bool = False) -> bool:
        """检查 LM Studio 是否可用（server 已启动 + 至少一个模型已加载）。

        使用 TTL 缓存，避免频繁请求。默认每 60 秒重新检查一次。

        Args:
            force_recheck: 强制重新检查，忽略缓存

        Returns:
            True 如果 LM Studio 可用且 USE_LLM=true
        """
        if not self.use_llm:
            return False

        # TTL 缓存：未过期且非强制刷新时直接返回缓存值
        if not force_recheck and self._available is not None:
            if time.time() - self._last_check < self._cache_ttl:
                return self._available

        # 执行实际检查
        try:
            client = self._get_sync_client()
            resp = client.get(f"{self.base_url}/models")
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

        # 更新检查时间戳
        self._last_check = time.time()
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
            client = self._get_sync_client()
            resp = client.post(
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
            client = self._get_async_client()
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
            client = self._get_async_client()
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
            client = self._get_sync_client()
            resp = client.get(f"{self.base_url}/models")
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("id", "") for m in data.get("data", [])]
        except Exception:
            pass
        return []

    async def close(self):
        """关闭 HTTP 客户端。"""
        if self._async_client and not self._async_client.is_closed:
            await self._async_client.aclose()
        if self._sync_client and not self._sync_client.is_closed:
            self._sync_client.close()


# ---------------------------------------------------------------------------
# 统一 LLM 客户端：Local → LMStudio → Mock 自动回退链
# ---------------------------------------------------------------------------


class UnifiedLLMClient:
    """统一 LLM 客户端，自动回退：本地 GGUF → LM Studio → Mock。

    接口与 LMStudioClient 完全兼容（is_available / chat / chat_async / chat_stream），
    Agent 无需修改代码即可享受多后端支持。
    """

    def __init__(self):
        self._local = None
        self._lmstudio: Optional[LMStudioClient] = None
        self._active_backend: str = "none"

    def _get_local(self):
        """延迟加载本地 LLM 客户端。"""
        if self._local is None:
            try:
                from skyforge_llm.local_client import get_local_llm_client

                self._local = get_local_llm_client()
            except Exception:
                pass
        return self._local

    def _get_lmstudio(self) -> LMStudioClient:
        """获取 LM Studio 客户端。"""
        if self._lmstudio is None:
            self._lmstudio = LMStudioClient()
        return self._lmstudio

    def _resolve_backend(self) -> str:
        """解析当前可用的后端，优先级：Local > LMStudio > mock。

        Returns:
            "local" | "lmstudio" | "mock"
        """
        # 1. 尝试本地 GGUF
        local = self._get_local()
        if local and local.is_available():
            return "local"

        # 2. 尝试 LM Studio
        lmstudio = self._get_lmstudio()
        if lmstudio.is_available():
            return "lmstudio"

        return "mock"

    def is_available(self, force_recheck: bool = False) -> bool:
        """检查是否有任何 LLM 后端可用（Local 或 LMStudio）。"""
        backend = self._resolve_backend()
        self._active_backend = backend
        return backend != "mock"

    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """同步调用，自动选择后端。"""
        backend = self._resolve_backend()
        self._active_backend = backend

        # 缓存：仅对非 mock 后端（真实 LLM）生效，Mock 自身已很快
        cache = get_llm_cache()
        use_cache = backend != "mock" and cache.is_enabled()
        key = cache.make_key(prompt, system_prompt) if use_cache else None
        if use_cache:
            cached = cache.get(key)  # type: ignore[arg-type]
            if cached is not None:
                return cached

        if backend == "local":
            logger.info("[UnifiedLLM] 使用本地 GGUF 模型")
            result = self._local.generate(
                prompt, system_prompt, temperature, max_tokens
            )
        elif backend == "lmstudio":
            logger.info("[UnifiedLLM] 使用 LM Studio")
            result = self._get_lmstudio().chat(
                prompt, system_prompt, temperature, max_tokens
            )
        else:
            logger.info("[UnifiedLLM] 无可用 LLM 后端，返回 Mock")
            return ""

        # 推理成功且有内容时写缓存
        if use_cache and result:
            cache.set(key, result)  # type: ignore[arg-type]
        return result

    async def chat_async(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> str:
        """异步调用，自动选择后端。"""
        backend = self._resolve_backend()
        self._active_backend = backend

        # 缓存：仅对非 mock 后端（真实 LLM）生效，Mock 自身已很快
        cache = get_llm_cache()
        use_cache = backend != "mock" and cache.is_enabled()
        key = cache.make_key(prompt, system_prompt) if use_cache else None
        if use_cache:
            cached = cache.get(key)  # type: ignore[arg-type]
            if cached is not None:
                return cached

        if backend == "local":
            logger.info("[UnifiedLLM] 使用本地 GGUF 模型（异步）")
            result = await self._local.generate_async(
                prompt, system_prompt, temperature, max_tokens
            )
        elif backend == "lmstudio":
            logger.info("[UnifiedLLM] 使用 LM Studio（异步）")
            result = await self._get_lmstudio().chat_async(
                prompt, system_prompt, temperature, max_tokens
            )
        else:
            logger.info("[UnifiedLLM] 无可用 LLM 后端，返回 Mock")
            return ""

        # 推理成功且有内容时写缓存
        if use_cache and result:
            cache.set(key, result)  # type: ignore[arg-type]
        return result

    async def chat_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """流式调用，自动选择后端。"""
        backend = self._resolve_backend()
        self._active_backend = backend

        if backend == "local":
            logger.info("[UnifiedLLM] 使用本地 GGUF 模型（流式）")
            async for chunk in self._local.generate_stream(
                prompt, system_prompt, temperature, max_tokens
            ):
                yield chunk
        elif backend == "lmstudio":
            logger.info("[UnifiedLLM] 使用 LM Studio（流式）")
            async for chunk in self._get_lmstudio().chat_stream(
                prompt, system_prompt, temperature, max_tokens
            ):
                yield chunk
        else:
            logger.info("[UnifiedLLM] 无可用 LLM 后端，流式返回空")
            return

    def get_active_backend(self) -> str:
        """返回当前激活的后端名称。"""
        return self._active_backend

    def get_status(self) -> dict:
        """获取所有后端的状态信息。"""
        local = self._get_local()
        lmstudio = self._get_lmstudio()
        return {
            "active_backend": self._active_backend,
            "local_llm": {
                "available": local.is_available() if local else False,
                "model": str(local._ensure_model()) if local else None,
            },
            "lmstudio": {
                "available": lmstudio.is_available(),
                "base_url": lmstudio.base_url,
                "model": lmstudio.model,
            },
        }

    def get_available_models(self) -> list[str]:
        """获取当前后端可用模型列表（兼容旧接口）。"""
        backend = self._resolve_backend()
        if backend == "lmstudio":
            return self._get_lmstudio().get_available_models()
        elif backend == "local":
            local = self._get_local()
            if local and local.is_available():
                return [str(local._ensure_model())]
        return []

    @property
    def use_llm(self) -> bool:
        """兼容旧接口：检查 USE_LLM 开关。"""
        return os.getenv("USE_LLM", "true").lower() == "true"

    @use_llm.setter
    def use_llm(self, value: bool):
        """兼容旧接口：设置 USE_LLM 开关。"""
        os.environ["USE_LLM"] = "true" if value else "false"
        # 重置 LM Studio 客户端的缓存
        lmstudio = self._get_lmstudio()
        lmstudio.use_llm = value
        lmstudio._available = None

    async def close(self):
        """关闭所有后端连接。"""
        lmstudio = self._get_lmstudio()
        await lmstudio.close()


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_unified_client: Optional[UnifiedLLMClient] = None


def get_lmstudio_client() -> UnifiedLLMClient:
    """获取统一 LLM 客户端单例（向后兼容，Agent 无需修改）。

    返回 UnifiedLLMClient，接口与 LMStudioClient 完全兼容，
    自动回退：本地 GGUF → LM Studio → Mock。
    """
    global _unified_client
    if _unified_client is None:
        _unified_client = UnifiedLLMClient()
    return _unified_client
