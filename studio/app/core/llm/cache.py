# -*- coding: utf-8 -*-
"""LLM 响应缓存层：对相同 prompt + system_prompt 的非流式调用做进程级缓存。

设计要点（对应设计文档 14.7.4 优化建议第 1 条）：
- 以 prompt + system_prompt 的 SHA256 为 key
- 内存字典存储（进程级缓存），TTL 可配（默认 3600s）
- 线程安全（threading.Lock）
- 仅在 LLMCache.enabled 为 True 时生效
- 缓存命中/未命中记录 loguru 日志

适用场景：需求解析、契约生成等幂等的非流式 LLM 调用。
流式调用（chat_stream）不缓存；Mock 模式（USE_LLM=false）下缓存不生效。
"""

import hashlib
import threading
import time
from typing import Optional

from app.config.setting import settings
from app.utils.log_util import logger


class LLMCache:
    """LLM 响应缓存，进程级内存字典 + TTL + 线程安全。"""

    def __init__(self, ttl: int = 3600, enabled: bool = True) -> None:
        """初始化缓存。

        Args:
            ttl: 缓存有效期（秒），默认 3600s。
            enabled: 是否启用缓存，默认 True。
        """
        self._ttl: int = ttl
        self._enabled: bool = enabled
        # key -> (value, expire_at_timestamp)
        self._store: dict[str, tuple[str, float]] = {}
        self._lock: threading.Lock = threading.Lock()

    def is_enabled(self) -> bool:
        """返回缓存是否启用。"""
        return self._enabled

    def make_key(self, prompt: str, system_prompt: str = "") -> str:
        """根据 prompt + system_prompt 生成 SHA256 缓存 key。

        Args:
            prompt: 用户提示词。
            system_prompt: 系统提示词。

        Returns:
            SHA256 十六进制摘要字符串。
        """
        # 用 \x00 分隔避免 prompt/system_prompt 拼接歧义
        raw = f"{system_prompt}\x00{prompt}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[str]:
        """查询缓存。

        命中且未过期时返回缓存值；未命中或已过期返回 None。
        命中/未命中均记录 loguru 日志。

        Args:
            key: 缓存 key（由 make_key 生成）。

        Returns:
            缓存的 LLM 响应文本，或 None。
        """
        if not self._enabled:
            return None

        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                logger.info(f"[LLMCache] 未命中 key={key[:16]}...")
                return None
            value, expire_at = entry
            now = time.time()
            if now > expire_at:
                # 已过期，惰性清理
                self._store.pop(key, None)
                logger.info(f"[LLMCache] 过期清理 key={key[:16]}...")
                return None
            logger.info(f"[LLMCache] 命中 key={key[:16]}...")
            return value

    def set(self, key: str, value: str) -> None:
        """写入缓存。

        Args:
            key: 缓存 key（由 make_key 生成）。
            value: LLM 响应文本。
        """
        if not self._enabled:
            return

        expire_at = time.time() + self._ttl
        with self._lock:
            self._store[key] = (value, expire_at)
            logger.info(
                f"[LLMCache] 写入 key={key[:16]}... ttl={self._ttl}s "
                f"size={len(self._store)}"
            )


# ---------------------------------------------------------------------------
# 全局单例（进程级缓存）
# ---------------------------------------------------------------------------

_llm_cache: Optional[LLMCache] = None
_singleton_lock = threading.Lock()


def get_llm_cache() -> LLMCache:
    """获取 LLM 响应缓存单例。

    从 settings 读取 LLM_CACHE_ENABLED / LLM_CACHE_TTL 初始化。
    """
    global _llm_cache
    if _llm_cache is None:
        with _singleton_lock:
            if _llm_cache is None:
                _llm_cache = LLMCache(
                    ttl=settings.LLM_CACHE_TTL,
                    enabled=settings.LLM_CACHE_ENABLED,
                )
    return _llm_cache
