# -*- coding: utf-8 -*-
"""本地 LLM 轻量级客户端：本地开发用，httpx 直连本地 LLM 服务（如 LM Studio）。

何时使用此类（vs LLM 类）：
- 单轮 prompt 调用、无需历史管理 → 用 LMStudioClient
- 需要多轮对话、工具调用、Redis 流式推送 → 用 LLM（通过 LLMFactory 创建）

Pipeline 的 4 个 Agent 均使用本客户端（get_lmstudio_client() 单例，等价于 get_local_llm_client）：
- RequirementParserAgent: 需求解析
- ContractGeneratorAgent: 契约生成
- CodeGeneratorAgent: 代码生成
- CodeRepairerAgent: 代码修复

直接用 httpx 调用本地 LLM 服务（如 LM Studio Local Server，localhost:1234/v1），
不依赖重型组件。

使用方式：
    client = get_lmstudio_client()
    if client.is_available():
        response = client.chat("你好")
    else:
        response = "本地 LLM 不可用，使用 Mock"
"""

import os
import json
import time
import warnings
import httpx
from typing import Optional, AsyncGenerator
from skyforge_engine.utils.log_util import logger
from skyforge_llm.cache import get_llm_cache


# LLM 请求超时（秒）—— 可通过环境变量 LLM_REQUEST_TIMEOUT_MS（毫秒）覆盖。
# 默认 180000ms = 180s，与 studio/app/core/llm/model_router.py 中的默认值保持一致。
# 历史硬编码 60.0s 在本地大模型首次推理（含模型加载）时容易超时。
_LLM_TIMEOUT_SEC = float(os.environ.get("LLM_REQUEST_TIMEOUT_MS", "180000")) / 1000.0


def _resolve_local_llm_base_url(default: str = "http://localhost:11434/v1") -> str:
    """读取本地 LLM 服务地址，优先 LOCAL_LLM_BASE_URL，回退到已弃用的 LMSTUDIO_BASE_URL。

    Args:
        default: 两个环境变量都未设置时的默认值。

    Returns:
        本地 LLM API 地址。
    """
    new_url = os.environ.get("LOCAL_LLM_BASE_URL")
    if new_url:
        return new_url
    legacy_url = os.environ.get("LMSTUDIO_BASE_URL")
    if legacy_url:
        warnings.warn(
            "LMSTUDIO_BASE_URL 已弃用，请改用 LOCAL_LLM_BASE_URL",
            DeprecationWarning,
            stacklevel=2,
        )
        return legacy_url
    return default


class LMStudioClient:
    """本地 LLM 轻量级客户端（类名保留为历史命名）。

    通过 OpenAI 兼容 API 调用本地 LLM 服务（如 LM Studio Local Server）。
    支持 USE_LLM 开关控制是否使用真实 LLM。
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        use_llm: Optional[bool] = None,
        timeout: int = 900,
    ):
        """初始化本地 LLM 客户端。

        Args:
            base_url: 本地 LLM API 地址，默认从环境变量读取
            model: 模型 ID，默认从环境变量读取
            use_llm: 是否使用真实 LLM，默认从环境变量 USE_LLM 读取
            timeout: 请求超时时间（秒），本地 LLM 首次推理可能较慢，默认900秒（15分钟）
        """
        self.base_url = base_url or _resolve_local_llm_base_url()
        self.model = model or os.getenv("LLM_MODEL") or os.getenv("LMSTUDIO_MODEL", "qwen3:8b")
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
        """检查本地 LLM 是否可用（server 已启动 + 至少一个模型已加载）。

        使用 TTL 缓存，避免频繁请求。默认每 60 秒重新检查一次。

        Args:
            force_recheck: 强制重新检查，忽略缓存

        Returns:
            True 如果本地 LLM 可用且 USE_LLM=true
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
                    logger.info(f"本地 LLM 可用，已加载模型: {models}")
                else:
                    logger.warning("本地 LLM 服务运行中但无模型加载")
            else:
                self._available = False
                logger.warning(f"本地 LLM 服务返回 {resp.status_code}")
        except Exception as e:
            self._available = False
            logger.warning(f"本地 LLM 服务不可用: {e}")

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
        """同步调用本地 LLM 生成回复。

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
                    f"本地 LLM 响应: model={self.model} "
                    f"tokens={data.get('usage', {}).get('total_tokens', '?')}"
                )
                return content
            else:
                logger.error(f"本地 LLM 服务返回 {resp.status_code}: {resp.text[:200]}")
                return ""
        except Exception as e:
            logger.error(f"本地 LLM 调用失败: {e}")
            return ""

    async def chat_async(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """异步调用本地 LLM 生成回复。

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
                logger.error(f"本地 LLM 服务返回 {resp.status_code}")
                return ""
        except Exception as e:
            logger.error(f"本地 LLM 异步调用失败: {e}")
            return ""

    async def chat_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        """流式调用本地 LLM，逐 token 生成（用于 Patch 4 打字机效果）。

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
            logger.error(f"本地 LLM 流式调用失败: {e}")

    def get_available_models(self) -> list[str]:
        """获取本地 LLM 中已加载的模型列表。

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
# 统一 LLM 客户端：Local → 本地 LLM → Mock 自动回退链
# ---------------------------------------------------------------------------


class UnifiedLLMClient:
    """统一 LLM 客户端，自动回退：本地 GGUF → 本地 LLM → Mock。

    接口与 LMStudioClient 完全兼容（is_available / chat / chat_async / chat_stream），
    Agent 无需修改代码即可享受多后端支持。
    """

    def __init__(self):
        self._local = None
        self._lmstudio: Optional[LMStudioClient] = None
        self._active_backend: str = "none"
        # 异步 HTTP 客户端（真正异步 LLM 调用时使用）
        self._async_client: Optional[httpx.AsyncClient] = None
        # 运行时配置覆盖（由 settings 路由层调用 apply_config 设置）
        self._override_mode: Optional[str] = None  # "mock" / "api" / "local" / None
        self._override_provider: Optional[str] = None  # "openai" / "anthropic" / None
        self._override_api_key: Optional[str] = None
        self._override_base_url: Optional[str] = None
        self._override_model: Optional[str] = None
        # 探测缓存（避免每次 is_available 都发起 HTTP 请求）
        self._override_available: Optional[bool] = None
        self._override_last_check: float = 0.0
        self._override_cache_ttl: int = 60  # 60 秒缓存

    def apply_config(
        self,
        mode: str,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """运行时切换 LLM 后端配置（无需重启服务）。

        参数:
            mode: "mock" / "api" / "local"
            provider: "openai" / "anthropic"（仅 mode="api" 时有效）
            api_key: API 密钥（mode="api" 时必填）
            base_url: 服务地址（mode="local" 或 "api" 时必填）
            model: 模型 ID（可选，留空则自动选择）
        """
        self._override_mode = mode
        self._override_provider = provider
        self._override_api_key = api_key
        self._override_base_url = base_url
        self._override_model = model
        # 强制重新解析后端
        self._active_backend = self._resolve_backend()
        # 重置探测缓存，下次 is_available 会重新探测
        self._override_available = None
        self._override_last_check = 0.0
        # 更新 use_llm 状态
        if mode == "mock":
            self.use_llm = False
        else:
            self.use_llm = True
        logger.info(
            f"UnifiedLLMClient 配置已切换: mode={mode}, provider={provider}, "
            f"base_url={base_url}, model={model}"
        )

    def _get_local(self):
        """延迟加载本地 LLM 客户端。"""
        if self._local is None:
            try:
                from skyforge_llm.local import get_local_llm_client

                self._local = get_local_llm_client()
            except Exception:
                pass
        return self._local

    def _get_lmstudio(self) -> LMStudioClient:
        """获取本地 LLM 客户端（字段名保留为历史命名）。"""
        if self._lmstudio is None:
            self._lmstudio = LMStudioClient(
                base_url=self._override_base_url,
                model=self._override_model,
                use_llm=self._override_mode != "mock",
            )
        elif self._override_mode == "local":
            if self._override_base_url:
                self._lmstudio.base_url = self._override_base_url
            self._lmstudio.model = (
                self._override_model
                or os.getenv("LLM_MODEL")
                or os.getenv("LMSTUDIO_MODEL", "qwen3:8b")
            )
            self._lmstudio.use_llm = True
            self._lmstudio._available = None
        return self._lmstudio

    def _get_async_client(self) -> httpx.AsyncClient:
        """获取或创建异步 HTTP 客户端（连接池复用）。"""
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                timeout=_LLM_TIMEOUT_SEC,
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                    keepalive_expiry=30,
                ),
            )
        return self._async_client

    def _resolve_backend(self) -> str:
        """解析当前可用的后端，优先级：override > Local > 本地 LLM > mock。

        Returns:
            "mock" | "api-openai" | "api-anthropic" | "lmstudio" | "local"
        """
        # 优先使用 override 配置
        if self._override_mode == "mock":
            return "mock"
        if self._override_mode == "api":
            if self._override_provider == "anthropic":
                return "api-anthropic"
            return "api-openai"
        if self._override_mode == "local":
            # 本地模式仍走 lmstudio 路径，但使用 override 的 base_url
            return "lmstudio"

        # 以下是原有探测逻辑（fallback）
        # 1. 尝试本地 GGUF
        local = self._get_local()
        if local and local.is_available():
            return "local"

        # 2. 尝试本地 LLM（OpenAI 兼容协议，如 LM Studio / Ollama）
        lmstudio = self._get_lmstudio()
        if lmstudio.is_available():
            return "lmstudio"

        return "mock"

    def is_available(self, force_recheck: bool = False) -> bool:
        """检查是否有任何 LLM 后端可用（Local / 本地 LLM / API）。

        override 模式下真实探测服务可达性，避免与下游 chat_async 的
        LMStudioClient.is_available() 状态分裂。
        """
        # TTL 缓存：未过期且非强制刷新时直接返回缓存值
        if not force_recheck and self._override_available is not None:
            if time.time() - self._override_last_check < self._override_cache_ttl:
                return self._override_available

        backend = self._resolve_backend()
        self._active_backend = backend

        if backend == "mock":
            self._override_available = False
        elif backend == "lmstudio":
            # local 模式：真实探测本地 LLM（LMStudio/Ollama）服务可达性
            lmstudio = self._get_lmstudio()
            self._override_available = lmstudio.is_available(force_recheck=True)
        elif backend == "local":
            # fallback 模式：_resolve_backend 已验证 local 可用
            local = self._get_local()
            self._override_available = bool(local and local.is_available())
        elif backend == "api-openai":
            # api 模式 + openai：GET /models with auth
            self._override_available = self._ping_openai()
        elif backend == "api-anthropic":
            # api 模式 + anthropic：POST /v1/messages max_tokens=1
            self._override_available = self._ping_anthropic()
        else:
            self._override_available = False

        self._override_last_check = time.time()
        return self._override_available

    def _ping_openai(self) -> bool:
        """探测 OpenAI 兼容 API 可达性（GET /models）。"""
        try:
            base_url = self._override_base_url or _resolve_local_llm_base_url()
            api_key = self._override_api_key or os.environ.get("LLM_API_KEY", "")
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{base_url}/models", headers=headers)
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"OpenAI ping 失败: {e}")
            return False

    def _ping_anthropic(self) -> bool:
        """探测 Anthropic API 可达性（POST /v1/messages max_tokens=1）。"""
        try:
            base_url = self._override_base_url or "https://api.anthropic.com"
            api_key = self._override_api_key or os.environ.get("LLM_API_KEY", "")
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": self._override_model or "claude-3-5-sonnet-20241022",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
            }
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    f"{base_url}/v1/messages", json=payload, headers=headers
                )
                # 200 或 400（参数错误）都说明 API 可达且鉴权通过
                return resp.status_code in (200, 400)
        except Exception as e:
            logger.warning(f"Anthropic ping 失败: {e}")
            return False

    def _audit_call(
        self,
        backend: str,
        prompt: str,
        result: str,
        start_time: float,
        cached: bool,
    ) -> None:
        """记录 LLM 调用审计日志（延迟 import 避免循环依赖）。

        受 settings.SECURITY_AUDIT_ENABLED 开关控制；审计失败不影响主流程。
        """
        try:
            from skyforge_engine.config import settings
            from skyforge_llm.security.auditor import get_auditor, LLMCallRecord

            if settings.SECURITY_AUDIT_ENABLED:
                auditor = get_auditor()
                if backend == "lmstudio":
                    model = self._get_lmstudio().model
                elif backend == "local" and self._local:
                    model = str(self._local._ensure_model())
                else:
                    model = ""
                record = LLMCallRecord(
                    provider=backend,
                    model=model,
                    input_hash=auditor.compute_hash(prompt),
                    input_len=len(prompt),
                    output_len=len(result) if result else 0,
                    duration_ms=(time.time() - start_time) * 1000,
                    cached=cached,
                )
                auditor.log(record)
        except Exception as e:
            logger.warning(f"审计日志记录失败: {e}")

    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """同步调用，自动选择后端。"""
        start_time = time.time()
        backend = self._resolve_backend()
        self._active_backend = backend

        # 缓存：仅对非 mock 后端（真实 LLM）生效，Mock 自身已很快
        cache = get_llm_cache()
        use_cache = backend != "mock" and cache.is_enabled()
        key = cache.make_key(prompt, system_prompt) if use_cache else None
        cached = False
        if use_cache:
            cached_value = cache.get(key)  # type: ignore[arg-type]
            if cached_value is not None:
                cached = True
                self._audit_call(backend, prompt, cached_value, start_time, cached)
                return cached_value

        if backend == "local":
            logger.info("[UnifiedLLM] 使用本地 GGUF 模型")
            result = self._local.generate(
                prompt, system_prompt, temperature, max_tokens
            )
        elif backend == "lmstudio":
            logger.info("[UnifiedLLM] 使用本地 LLM")
            result = self._get_lmstudio().chat(
                prompt, system_prompt, temperature, max_tokens
            )
        elif backend == "api-openai":
            # 调用 OpenAI 兼容 API
            logger.info("[UnifiedLLM] 使用 OpenAI 兼容 API")
            result = self._chat_openai_compat(
                prompt, system_prompt, temperature, max_tokens
            )
        elif backend == "api-anthropic":
            # 调用 Anthropic API
            logger.info("[UnifiedLLM] 使用 Anthropic API")
            result = self._chat_anthropic(
                prompt, system_prompt, temperature, max_tokens
            )
        else:
            logger.info("[UnifiedLLM] 无可用 LLM 后端，返回 Mock")
            result = ""

        # 推理成功且有内容时写缓存
        if use_cache and result:
            cache.set(key, result)  # type: ignore[arg-type]
        self._audit_call(backend, prompt, result, start_time, cached)
        return result

    async def chat_async(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """异步调用，自动选择后端。"""
        start_time = time.time()
        backend = self._resolve_backend()
        self._active_backend = backend

        # 缓存：仅对非 mock 后端（真实 LLM）生效，Mock 自身已很快
        cache = get_llm_cache()
        use_cache = backend != "mock" and cache.is_enabled()
        key = cache.make_key(prompt, system_prompt) if use_cache else None
        cached = False
        if use_cache:
            cached_value = cache.get(key)  # type: ignore[arg-type]
            if cached_value is not None:
                cached = True
                self._audit_call(backend, prompt, cached_value, start_time, cached)
                return cached_value

        if backend == "local":
            logger.info("[UnifiedLLM] 使用本地 GGUF 模型（异步）")
            result = await self._local.generate_async(
                prompt, system_prompt, temperature, max_tokens
            )
        elif backend == "lmstudio":
            logger.info("[UnifiedLLM] 使用本地 LLM（异步）")
            result = await self._get_lmstudio().chat_async(
                prompt, system_prompt, temperature, max_tokens
            )
        elif backend == "api-openai":
            # 调用 OpenAI 兼容 API（真正异步，避免阻塞事件循环）
            logger.info("[UnifiedLLM] 使用 OpenAI 兼容 API（异步）")
            result = await self._chat_openai_compat_async(
                prompt, system_prompt, temperature, max_tokens
            )
        elif backend == "api-anthropic":
            # 调用 Anthropic API（真正异步，避免阻塞事件循环）
            logger.info("[UnifiedLLM] 使用 Anthropic API（异步）")
            result = await self._chat_anthropic_async(
                prompt, system_prompt, temperature, max_tokens
            )
        else:
            logger.info("[UnifiedLLM] 无可用 LLM 后端，返回 Mock")
            result = ""

        # 推理成功且有内容时写缓存
        if use_cache and result:
            cache.set(key, result)  # type: ignore[arg-type]
        self._audit_call(backend, prompt, result, start_time, cached)
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
            logger.info("[UnifiedLLM] 使用本地 LLM（流式）")
            async for chunk in self._get_lmstudio().chat_stream(
                prompt, system_prompt, temperature, max_tokens
            ):
                yield chunk
        elif backend == "api-openai":
            # OpenAI 兼容 API 流式：底层 helper 不支持流式，作为单块返回
            # 真正异步调用，避免阻塞事件循环
            logger.info("[UnifiedLLM] 使用 OpenAI 兼容 API（流式，单块）")
            chunk = await self._chat_openai_compat_async(
                prompt, system_prompt, temperature, max_tokens
            )
            if chunk:
                yield chunk
        elif backend == "api-anthropic":
            # Anthropic API 流式：底层 helper 不支持流式，作为单块返回
            # 真正异步调用，避免阻塞事件循环
            logger.info("[UnifiedLLM] 使用 Anthropic API（流式，单块）")
            chunk = await self._chat_anthropic_async(
                prompt, system_prompt, temperature, max_tokens
            )
            if chunk:
                yield chunk
        else:
            logger.info("[UnifiedLLM] 无可用 LLM 后端，流式返回空")
            return

    def _chat_openai_compat(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """调用 OpenAI 兼容 API（含本地 LLM 如 LM Studio / Ollama）。"""
        base_url = self._override_base_url or _resolve_local_llm_base_url()
        api_key = self._override_api_key or os.environ.get("LLM_API_KEY", "")
        model = self._override_model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=_LLM_TIMEOUT_SEC)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"OpenAI 兼容 API 调用失败: {e}")
            return ""

    def _chat_anthropic(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """调用 Anthropic API。"""
        base_url = self._override_base_url or "https://api.anthropic.com"
        api_key = self._override_api_key or os.environ.get("LLM_API_KEY", "")
        model = self._override_model or "claude-3-5-sonnet-20241022"
        url = f"{base_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=_LLM_TIMEOUT_SEC)
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]
        except Exception as e:
            logger.warning(f"Anthropic API 调用失败: {e}")
            return ""

    async def _chat_openai_compat_async(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """异步调用 OpenAI 兼容 API（含本地 LLM 如 LM Studio / Ollama）。

        使用 ``httpx.AsyncClient`` 真正异步发起请求，避免阻塞事件循环。
        请求参数与同步版本完全一致。
        """
        base_url = self._override_base_url or _resolve_local_llm_base_url()
        api_key = self._override_api_key or os.environ.get("LLM_API_KEY", "")
        model = self._override_model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            client = self._get_async_client()
            resp = await client.post(url, json=payload, headers=headers, timeout=_LLM_TIMEOUT_SEC)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"OpenAI 兼容 API 异步调用失败: {e}")
            return ""

    async def _chat_anthropic_async(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """异步调用 Anthropic API。

        使用 ``httpx.AsyncClient`` 真正异步发起请求，避免阻塞事件循环。
        """
        base_url = self._override_base_url or "https://api.anthropic.com"
        api_key = self._override_api_key or os.environ.get("LLM_API_KEY", "")
        model = self._override_model or "claude-3-5-sonnet-20241022"
        url = f"{base_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        try:
            client = self._get_async_client()
            resp = await client.post(url, json=payload, headers=headers, timeout=_LLM_TIMEOUT_SEC)
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]
        except Exception as e:
            logger.warning(f"Anthropic API 异步调用失败: {e}")
            return ""

    def get_active_backend(self) -> str:
        """返回当前激活的后端名称。"""
        return self._active_backend

    def get_status(self) -> dict:
        """获取所有后端的状态信息。

        override 模式下跳过 local 探测，避免触发 llama-cpp-python /
        huggingface_hub 的 ImportError 日志噪声（这两个是可选重型依赖）。
        """
        # override 模式：用户已明确指定后端，无需探测本地 GGUF
        if self._override_mode is not None:
            return {
                "active_backend": self._active_backend,
                "display_backend": (
                    self._override_provider
                    if self._override_mode == "api"
                    else self._override_mode
                ),
                "override_mode": self._override_mode,
                "override_provider": self._override_provider,
                "override_base_url": self._override_base_url,
                "override_model": self._override_model,
                "connection": {
                    "configured": self._override_mode == "mock" or bool(self._override_base_url),
                    "mode": self._override_mode,
                    "provider": self._override_provider,
                    "base_url": self._override_base_url or "",
                    "model": self._override_model,
                },
                "local_llm": {"available": False, "model": None},
                "lmstudio": {
                    "available": self._override_mode == "local",
                    "base_url": (self._override_base_url or "") if self._override_mode == "local" else "",
                    "model": self._override_model if self._override_mode == "local" else None,
                },
            }

        # 非 override 模式：保留原行为，仅在 local 可用时才 _ensure_model
        local = self._get_local()
        lmstudio = self._get_lmstudio()
        local_available = local.is_available() if local else False
        return {
            "active_backend": self._active_backend,
            "local_llm": {
                "available": local_available,
                "model": (
                    str(local._ensure_model())
                    if (local and local_available)
                    else None
                ),
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
        # 重置本地 LLM 客户端的缓存
        lmstudio = self._get_lmstudio()
        lmstudio.use_llm = value
        lmstudio._available = None

    async def close(self):
        """关闭所有后端连接。"""
        if self._async_client and not self._async_client.is_closed:
            await self._async_client.aclose()
            self._async_client = None
        lmstudio = self._get_lmstudio()
        await lmstudio.close()


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_unified_client: Optional[UnifiedLLMClient] = None


def get_lmstudio_client() -> UnifiedLLMClient:
    """获取统一 LLM 客户端单例（向后兼容，Agent 无需修改）。

    返回 UnifiedLLMClient，接口与 LMStudioClient 完全兼容，
    自动回退：本地 GGUF → 本地 LLM → Mock。
    """
    global _unified_client
    if _unified_client is None:
        _unified_client = UnifiedLLMClient()
    return _unified_client


# 向后兼容别名（历史命名，逐步迁移到 get_local_llm_client）
get_local_llm_client = get_lmstudio_client
