# -*- coding: utf-8 -*-
"""多模型路由器：根据任务类型（简单/复杂）选择不同规模的 LM Studio 模型。

LM Studio 一次可加载多个模型，本路由器按任务复杂度路由：
  - 简单任务（需求解析）→ 小模型（gemma-3-e4b / qwen3.5-9b 等）
  - 复杂任务（代码生成/修复）→ 大模型（qwen3-coder-30b / gpt-oss-20b 等）

使用方式：
    router = ModelRouter()
    model_id = router.select_model("code_generation")
    info = router.get_model_info(model_id)
"""

import os
import warnings
from typing import Any, Optional

import httpx

from app.utils.log_util import logger


# 统一 LLM HTTP 请求超时（秒），可通过环境变量 LLM_REQUEST_TIMEOUT_MS 覆盖
# 默认 180000ms = 180s，与 local_llm_client 保持一致
_LLM_TIMEOUT_SEC: float = float(os.environ.get("LLM_REQUEST_TIMEOUT_MS", "180000")) / 1000.0


def _resolve_local_llm_base_url(default: str = "http://localhost:11434/v1") -> str:
    """读取本地 LLM 服务地址，优先 LOCAL_LLM_BASE_URL，回退到已弃用的 LMSTUDIO_BASE_URL。"""
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


# 任务类型 → 模型规模偏好
# 简单任务用 small，复杂任务用 large
_TASK_COMPLEXITY: dict[str, str] = {
    "requirement_parse": "small",
    "contract_generation": "small",
    "code_generation": "large",
    "code_repair": "large",
    "report_writing": "small",
    "default": "small",
}

# 各规模的首选 / 备用模型候选列表（按优先级降序）
# 候选 ID 同时兼容 LM Studio 实际 ID（如 "qwen/qwen3.5-9b"）和简写形式
_MODEL_CANDIDATES: dict[str, list[str]] = {
    "small": [
        "gemma-3-e4b",
        "gemma-4-e4b",
        "qwen3.5-9b",
        "qwen/qwen3.5-9b",
        "qwen2.5-7b-instruct",
        "qwen/qwen2.5-7b-instruct",
    ],
    "large": [
        "qwen3-coder-30b",
        "qwen3.6-27b",
        "gpt-oss-20b",
        "qwen2.5-coder-32b-instruct",
        "qwen/qwen3.5-9b",
    ],
}


class ModelRouter:
    """多模型路由器：根据任务复杂度选择 LM Studio 中已加载的模型。

    通过 LM Studio OpenAI 兼容 API（/v1/models）查询已加载模型，
    按任务类型偏好匹配首选模型，未加载时直接抛出异常。
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        """初始化模型路由器。

        Args:
            base_url: 本地 LLM API 地址，默认从环境变量 LOCAL_LLM_BASE_URL 读取
                （旧名 LMSTUDIO_BASE_URL 仍兼容，会触发 DeprecationWarning）。
            timeout: 单次模型调用超时阈值（秒），仅用于记录耗时告警。
        """
        self.base_url = base_url or _resolve_local_llm_base_url()
        self.timeout = timeout
        # 模型调用耗时记录：{model_id: last_latency_seconds}
        self._latency: dict[str, float] = {}
        # 当前手动选择的模型（API /api/models/select 可设置）
        self._manual_selection: Optional[str] = None

    # ------------------------------------------------------------------ #
    # 公共 API
    # ------------------------------------------------------------------ #

    def select_model(self, task_type: str) -> str:
        """根据任务类型选择模型 ID。

        选择策略：
          1. 若已通过 set_manual_selection 手动指定，直接返回该模型
          2. 否则按 task_type → 复杂度 → 候选模型列表 → 选中首选模型
          3. 首选模型未加载时抛出 RuntimeError

        Args:
            task_type: 任务类型，如 requirement_parse / code_generation。

        Returns:
            模型 ID 字符串。

        Raises:
            RuntimeError: 首选模型未加载或 LM Studio 无可用模型。
        """
        # 1. 手动选择优先
        if self._manual_selection:
            logger.info(f"ModelRouter:使用手动选择的模型 {self._manual_selection}")
            return self._manual_selection

        # 2. 按任务复杂度匹配
        complexity = _TASK_COMPLEXITY.get(task_type, _TASK_COMPLEXITY["default"])
        candidates = _MODEL_CANDIDATES.get(complexity, _MODEL_CANDIDATES["small"])

        loaded_models = self.list_available_models()
        loaded_ids = {m["id"] for m in loaded_models}

        # 3. 使用候选列表中的首选模型
        if candidates:
            preferred = candidates[0]
            if preferred in loaded_ids:
                logger.info(
                    f"ModelRouter:任务 {task_type} (complexity={complexity}) "
                    f"选中已加载模型 {preferred}"
                )
                return preferred
            raise RuntimeError(
                f"ModelRouter:推荐模型 {preferred} 未加载 (task={task_type})"
            )

        raise RuntimeError(
            f"ModelRouter:无可用候选模型 (task={task_type})"
        )

    def get_model_info(self, model_id: str) -> dict[str, Any]:
        """获取模型信息（名称、大小、是否已加载）。

        Args:
            model_id: 模型 ID。

        Returns:
            dict：含 id / loaded / size / type / context_length / last_latency。
        """
        loaded_models = self.list_available_models()
        for m in loaded_models:
            if m["id"] == model_id:
                info = {
                    "id": m["id"],
                    "loaded": True,
                    "size": m.get("size", "unknown"),
                    "type": m.get("type", "unknown"),
                    "context_length": m.get("context_length", "unknown"),
                    "last_latency": self._latency.get(model_id),
                }
                return info

        # 未加载的模型仍返回基本信息
        return {
            "id": model_id,
            "loaded": False,
            "size": "unknown",
            "type": "unknown",
            "context_length": "unknown",
            "last_latency": self._latency.get(model_id),
        }

    def list_available_models(self) -> list[dict[str, Any]]:
        """列出 LM Studio 中所有已加载的模型。

        Returns:
            模型信息列表，每项含 id / size / type / context_length 等字段。
            LM Studio 不可用时返回空列表。
        """
        try:
            resp = httpx.get(f"{self.base_url}/models", timeout=5)
            if resp.status_code != 200:
                logger.warning(f"ModelRouter:LM Studio /models 返回 {resp.status_code}")
                return []
            data = resp.json()
            models: list[dict[str, Any]] = []
            for m in data.get("data", []):
                models.append(
                    {
                        "id": m.get("id", ""),
                        "size": m.get("size", m.get("size_gb", "unknown")),
                        "type": m.get("type", "llm"),
                        "context_length": m.get(
                            "context_length",
                            m.get("max_context_length", "unknown"),
                        ),
                    }
                )
            return models
        except Exception as e:
            logger.warning(f"ModelRouter:获取模型列表失败: {e}")
            return []

    def record_latency(self, model_id: str, latency: float) -> None:
        """记录模型调用耗时。

        Args:
            model_id: 模型 ID。
            latency: 本次调用耗时（秒）。
        """
        self._latency[model_id] = latency
        if latency > self.timeout:
            logger.warning(
                f"ModelRouter:模型 {model_id} 耗时 {latency:.1f}s "
                f"超过阈值 {self.timeout}s"
            )

    def set_manual_selection(self, model_id: Optional[str]) -> None:
        """手动指定模型（None 表示清除手动选择，恢复自动路由）。

        Args:
            model_id: 模型 ID，传 None 清除。
        """
        self._manual_selection = model_id
        if model_id:
            logger.info(f"ModelRouter:已手动选择模型 {model_id}")
        else:
            logger.info("ModelRouter:已清除手动选择，恢复自动路由")


# 全局单例
_model_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """获取 ModelRouter 单例。"""
    global _model_router
    if _model_router is None:
        _model_router = ModelRouter()
    return _model_router


def reset_model_router() -> None:
    """重置 ModelRouter 单例（仅供测试使用，强制下次重新创建）。"""
    global _model_router
    _model_router = None
