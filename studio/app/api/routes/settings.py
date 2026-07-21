"""LLM 配置管理路由模块。

提供 LLM 配置的读取、保存、测试接口，供前端 Web 端动态修改 LLM 连接参数。
GET  /api/llm/config  读取当前 LLM 配置（API Key 脱敏）
PUT  /api/llm/config  保存 LLM 配置（写入环境变量与 settings）
POST /api/llm/test    测试 LLM 连接（直接使用 httpx，不依赖 UnifiedLLMClient）
"""

import os
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Literal, Optional

import httpx
from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel, field_validator

from app.core.auth import require_write_access

from app.core.llm.local_llm_client import get_local_llm_client as get_lmstudio_client
from skyforge_engine.config import settings

router = APIRouter(prefix="/api")


# ============================================================================ #
# Pydantic 模型
# ============================================================================ #


class LLMConfigRequest(BaseModel):
    """LLM 配置请求体（PUT 保存 / POST 测试 共用）。"""

    mode: Literal["mock", "api", "local"] = "mock"
    provider: Optional[str] = None  # "openai" | "anthropic" | None
    apiKey: str = ""
    baseUrl: str = "http://localhost:11434/v1"
    model: Optional[str] = None
    remember: bool = True

    @field_validator("apiKey", "baseUrl", "model", "provider")
    @classmethod
    def reject_control_characters(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and any(char in value for char in ("\r", "\n", "\x00")):
            raise ValueError("configuration values cannot contain control characters")
        return value

    @field_validator("baseUrl")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        if not value:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("baseUrl must be an absolute http(s) URL")
        return value.rstrip("/")


class LLMConfigResponse(BaseModel):
    """LLM 配置响应体（GET 返回，API Key 脱敏）。"""

    mode: str
    provider: Optional[str] = None
    apiKey: str = ""
    baseUrl: str = ""
    model: Optional[str] = None
    remember: bool = False


class LLMTestResponse(BaseModel):
    """LLM 连接测试响应体。"""

    ok: bool
    latency_ms: int
    message: str
    model: Optional[str] = None
    models: Optional[list[str]] = None  # 完整模型 ID 列表


# ============================================================================ #
# 辅助函数
# ============================================================================ #


def _mask_api_key(key: Optional[str]) -> str:
    """对 API Key 脱敏：保留前 3 字符 + **** + 后 4 字符；长度 ≤ 8 时返回 ****。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}****{key[-4:]}"


def _is_masked_api_key(key: str) -> bool:
    return "****" in key


_REPO_ROOT = Path(__file__).resolve().parents[4]
_PERSISTED_ENV = _REPO_ROOT / "config" / ".env"
_PERSISTED_KEYS = {
    "SKYFORGE_LLM_MODE",
    "SKYFORGE_LLM_PROVIDER",
    "LOCAL_LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_API_KEY",
    "USE_LLM",
}


def _has_persisted_config() -> bool:
    if not _PERSISTED_ENV.exists():
        return False
    for line in _PERSISTED_ENV.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Z][A-Z0-9_]*)=", line)
        if match and match.group(1) in _PERSISTED_KEYS:
            return True
    return False


def _persist_config(values: dict[str, str | None]) -> None:
    """Atomically update only managed LLM keys in the ignored local env file."""
    _PERSISTED_ENV.parent.mkdir(parents=True, exist_ok=True)
    lines = (
        _PERSISTED_ENV.read_text(encoding="utf-8").splitlines()
        if _PERSISTED_ENV.exists()
        else []
    )
    managed = set(values)
    seen: set[str] = set()
    rendered: list[str] = []
    for line in lines:
        match = re.match(r"^([A-Z][A-Z0-9_]*)=", line)
        if match and match.group(1) in managed:
            key = match.group(1)
            if values[key] is not None:
                rendered.append(f"{key}={json.dumps(values[key], ensure_ascii=False)}")
            seen.add(key)
        else:
            rendered.append(line)
    if rendered and rendered[-1] != "":
        rendered.append("")
    for key, value in values.items():
        if key not in seen and value is not None:
            rendered.append(f"{key}={json.dumps(value, ensure_ascii=False)}")
    temp_path = _PERSISTED_ENV.with_suffix(".tmp")
    temp_path.write_text("\n".join(rendered).rstrip() + "\n", encoding="utf-8")
    temp_path.replace(_PERSISTED_ENV)


def _sync_agent_configs(api_key: str, base_url: str, model: str) -> None:
    """将配置同步写入 4 个 Agent 子配置字段（简化：所有 Agent 共用相同配置）。

    覆盖 REQ_PARSER / CON_GEN / CODE_GEN / REPAIR 四组 Agent 的
    API_KEY / BASE_URL / MODEL 字段。
    """
    agent_prefixes = ["REQ_PARSER", "CON_GEN", "CODE_GEN", "REPAIR"]
    for prefix in agent_prefixes:
        if api_key:
            env_key = f"{prefix}_API_KEY"
            os.environ[env_key] = api_key
            setattr(settings, f"{prefix}_API_KEY", api_key)
        if base_url:
            env_base = f"{prefix}_BASE_URL"
            os.environ[env_base] = base_url
            setattr(settings, f"{prefix}_BASE_URL", base_url)
        if model:
            env_model = f"{prefix}_MODEL"
            os.environ[env_model] = model
            setattr(settings, f"{prefix}_MODEL", model)


# ============================================================================ #
# 端点 1：GET /api/llm/config  读取当前 LLM 配置
# ============================================================================ #


@router.get("/llm/config")
async def get_llm_config() -> dict[str, Any]:
    """读取当前 LLM 配置（API Key 脱敏返回）。"""
    # mode / provider 从环境变量读取（默认 mock）
    mode = settings.SKYFORGE_LLM_MODE
    provider = settings.SKYFORGE_LLM_PROVIDER

    # API Key 优先从 settings 读取，回退到环境变量
    api_key = settings.LLM_API_KEY or os.environ.get("LLM_API_KEY")
    # base_url 优先 LOCAL_LLM_BASE_URL，回退到 settings.LMSTUDIO_BASE_URL（旧名，skyforge_engine.config 仍保留）
    base_url = (
        settings.LOCAL_LLM_BASE_URL
        or os.environ.get("LOCAL_LLM_BASE_URL")
        or settings.LMSTUDIO_BASE_URL
    )
    model = settings.LLM_MODEL

    logger.debug(f"读取 LLM 配置: mode={mode}, provider={provider}, baseUrl={base_url}")
    return {
        "mode": mode,
        "provider": provider,
        "apiKey": _mask_api_key(api_key),
        "baseUrl": base_url,
        "model": model,
        "remember": _has_persisted_config(),
    }


# ============================================================================ #
# 端点 2：PUT /api/llm/config  保存 LLM 配置
# ============================================================================ #


@router.put("/llm/config")
async def put_llm_config(
    req: LLMConfigRequest,
    _user: str = Depends(require_write_access),
) -> dict[str, Any]:
    """保存 LLM 配置：写入环境变量与 settings，并同步 4 个 Agent 子配置。"""
    # 1. mode / provider 写入环境变量
    os.environ["SKYFORGE_LLM_MODE"] = req.mode
    settings.SKYFORGE_LLM_MODE = req.mode
    if req.provider is not None:
        os.environ["SKYFORGE_LLM_PROVIDER"] = req.provider
        settings.SKYFORGE_LLM_PROVIDER = req.provider

    # 2. apiKey 非空才更新（空字符串表示不修改）
    submitted_key = req.apiKey or ""
    current_key = settings.LLM_API_KEY or os.environ.get("LLM_API_KEY") or ""
    api_key = (
        current_key
        if not submitted_key or _is_masked_api_key(submitted_key)
        else submitted_key
    )
    if api_key:
        os.environ["LLM_API_KEY"] = api_key
        settings.LLM_API_KEY = api_key

    # 3. baseUrl 写入环境变量与 settings
    #    主名 LOCAL_LLM_BASE_URL（新），同时保留 LMSTUDIO_BASE_URL 一版本兼容
    base_url = req.baseUrl or ""
    if base_url:
        os.environ["LOCAL_LLM_BASE_URL"] = base_url
        os.environ["LMSTUDIO_BASE_URL"] = base_url  # 兼容旧名（一版本后移除）
        settings.LMSTUDIO_BASE_URL = base_url
        settings.LOCAL_LLM_BASE_URL = base_url

    # 4. model 非空才更新
    model = req.model or ""
    if model:
        os.environ["LLM_MODEL"] = model
        settings.LLM_MODEL = model

    # 5. 同步 4 个 Agent 子配置（简化：所有 Agent 共用相同配置）
    _sync_agent_configs(api_key, base_url, model)

    if req.remember:
        persisted = {
            "SKYFORGE_LLM_MODE": req.mode,
            "SKYFORGE_LLM_PROVIDER": req.provider or "",
            "LOCAL_LLM_BASE_URL": base_url,
            "LLM_MODEL": model,
            "USE_LLM": "false" if req.mode == "mock" else "true",
        }
        if api_key:
            persisted["LLM_API_KEY"] = api_key
        _persist_config(persisted)
    else:
        _persist_config(
            {
                "SKYFORGE_LLM_MODE": None,
                "SKYFORGE_LLM_PROVIDER": None,
                "LOCAL_LLM_BASE_URL": None,
                "LLM_MODEL": None,
                "LLM_API_KEY": None,
                "USE_LLM": None,
            }
        )

    # 6. 调用 UnifiedLLMClient 单例的 apply_config（若存在），否则降级到 os.environ 生效
    client = get_lmstudio_client()
    apply_config = getattr(client, "apply_config", None)
    if callable(apply_config):
        try:
            apply_config(req.mode, req.provider, api_key, base_url, model)
        except Exception as e:
            logger.warning(f"client.apply_config 调用失败: {e}")
    else:
        logger.warning(
            "UnifiedLLMClient 未实现 apply_config 方法，"
            "配置已写入 os.environ，下次 _resolve_backend 时生效"
        )

    logger.info(
        "LLM 配置已保存 | mode={} | provider={} | model={} | remembered={}",
        req.mode,
        req.provider or "-",
        model or "auto",
        req.remember,
    )
    return {
        "ok": True,
        "message": "配置已保存",
        "apiKey": _mask_api_key(api_key),
    }


# ============================================================================ #
# 端点 3：POST /api/llm/test  测试 LLM 连接
# ============================================================================ #


@router.post("/llm/test")
async def test_llm_config(
    req: LLMConfigRequest,
    _user: str = Depends(require_write_access),
) -> dict[str, Any]:
    """测试 LLM 连接（直接使用 httpx，避免循环依赖 UnifiedLLMClient）。"""
    # mock 模式无需测试
    if req.mode == "mock":
        return {
            "ok": True,
            "latency_ms": 0,
            "message": "Mock 模式无需测试",
            "model": None,
            "models": None,
        }

    base_url = (req.baseUrl or "").rstrip("/")
    submitted_key = req.apiKey or ""
    api_key = (
        settings.LLM_API_KEY or os.environ.get("LLM_API_KEY") or ""
        if not submitted_key or _is_masked_api_key(submitted_key)
        else submitted_key
    )
    model = req.model
    # api 模式超时 10s，local 模式超时 5s
    timeout = 10.0 if req.mode == "api" else 5.0

    start = time.time()
    try:
        if req.mode == "api" and req.provider != "anthropic":
            # OpenAI 兼容接口：GET {baseUrl}/models
            async with httpx.AsyncClient(timeout=timeout) as http:
                resp = await http.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
            data = resp.json().get("data", [])
            models = [item["id"] for item in data if "id" in item]
            first_model = models[0] if models else None
            latency = int((time.time() - start) * 1000)
            logger.info(
                f"LLM 测试成功 (openai): latency={latency}ms, "
                f"models_count={len(models)}"
            )
            return {
                "ok": True,
                "latency_ms": latency,
                "message": "连接成功",
                "model": first_model,
                "models": models,
            }

        if req.mode == "api" and req.provider == "anthropic":
            # Anthropic 接口：POST {baseUrl}/v1/messages
            url = f"{base_url}/v1/messages"
            payload = {
                "model": model or "claude-3-5-sonnet-20241022",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
            }
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            async with httpx.AsyncClient(timeout=timeout) as http:
                resp = await http.post(url, json=payload, headers=headers)
                resp.raise_for_status()
            latency = int((time.time() - start) * 1000)
            # Anthropic 成功时不返回 model 字段；Anthropic API 不提供 list models 接口
            logger.info(f"LLM 测试成功 (anthropic): latency={latency}ms")
            return {
                "ok": True,
                "latency_ms": latency,
                "message": "连接成功",
                "model": None,
                "models": None,
            }

        if req.mode == "local":
            # 本地模式：GET {baseUrl}/models，无鉴权
            async with httpx.AsyncClient(timeout=timeout) as http:
                resp = await http.get(f"{base_url}/models")
                resp.raise_for_status()
            data = resp.json().get("data", [])
            models = [item["id"] for item in data if "id" in item]
            first_model = models[0] if models else None
            latency = int((time.time() - start) * 1000)
            logger.info(
                f"LLM 测试成功 (local): latency={latency}ms, "
                f"models_count={len(models)}"
            )
            return {
                "ok": True,
                "latency_ms": latency,
                "message": "连接成功",
                "model": first_model,
                "models": models,
            }

        # 未知 mode/provider 组合
        latency = int((time.time() - start) * 1000)
        return {
            "ok": False,
            "latency_ms": latency,
            "message": f"不支持的配置组合: mode={req.mode}, provider={req.provider}",
            "model": None,
            "models": None,
        }

    except httpx.ConnectError as e:
        latency = int((time.time() - start) * 1000)
        logger.warning(f"LLM 测试连接失败 (ConnectError): {e}")
        return {
            "ok": False,
            "latency_ms": latency,
            "message": f"连接被拒绝: {e}",
            "model": None,
            "models": None,
        }
    except httpx.TimeoutException:
        latency = int((time.time() - start) * 1000)
        logger.warning(f"LLM 测试连接超时 ({timeout}s)")
        return {
            "ok": False,
            "latency_ms": latency,
            "message": f"请求超时（{int(timeout)}s）",
            "model": None,
            "models": None,
        }
    except httpx.HTTPStatusError as e:
        latency = int((time.time() - start) * 1000)
        status = e.response.status_code
        reason = e.response.reason_phrase or ""
        logger.warning(f"LLM 测试返回 HTTP 错误: {status} {reason}")
        return {
            "ok": False,
            "latency_ms": latency,
            "message": f"HTTP {status} {reason}".strip(),
            "model": None,
            "models": None,
        }
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        logger.warning(f"LLM 测试失败 (未知异常): {e}")
        return {
            "ok": False,
            "latency_ms": latency,
            "message": f"测试失败: {e}",
            "model": None,
            "models": None,
        }
