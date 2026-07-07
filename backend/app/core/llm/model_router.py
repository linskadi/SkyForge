# -*- coding: utf-8 -*-
"""多模型路由器：根据任务类型（简单/复杂）选择不同规模的 LM Studio 模型。

LM Studio 一次可加载多个模型，本路由器按任务复杂度路由：
  - 简单任务（需求解析）→ 小模型（gemma-3-e4b / qwen3.5-9b 等）
  - 复杂任务（代码生成/修复）→ 大模型（qwen3-coder-30b / gpt-oss-20b 等）
  - 首选模型超时或未加载时自动降级到备用模型

使用方式：
    router = ModelRouter()
    model_id = router.select_model("code_generation")
    info = router.get_model_info(model_id)
"""

import os
from typing import Any, Optional

import httpx

from app.utils.log_util import logger


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
        "qwen/qwen3.5-9b",  # 大模型不可用时退回 9b
    ],
}


class ModelRouter:
    """多模型路由器：根据任务复杂度选择 LM Studio 中已加载的模型。

    通过 LM Studio OpenAI 兼容 API（/v1/models）查询已加载模型，
    按任务类型偏好匹配首选模型，超时/未加载时降级到备用模型。
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        """初始化模型路由器。

        Args:
            base_url: LM Studio API 地址，默认从环境变量 LMSTUDIO_BASE_URL 读取。
            timeout: 单次模型调用超时阈值（秒），超过则触发降级。
        """
        self.base_url = base_url or os.getenv(
            "LMSTUDIO_BASE_URL", "http://localhost:1234/v1"
        )
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
          2. 否则按 task_type → 复杂度 → 候选模型列表 → 匹配已加载模型
          3. 全部候选都未加载时，返回 LM Studio 中第一个可用模型
          4. 若 LM Studio 不可用 / 无模型，返回环境变量 LMSTUDIO_MODEL 默认值

        Args:
            task_type: 任务类型，如 requirement_parse / code_generation。

        Returns:
            模型 ID 字符串。
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

        # 3. 在候选列表中找第一个已加载的
        for candidate in candidates:
            if candidate in loaded_ids:
                logger.info(
                    f"ModelRouter:任务 {task_type} (complexity={complexity}) "
                    f"选中已加载模型 {candidate}"
                )
                return candidate

        # 4. 候选都未加载 → 取 LM Studio 中第一个可用模型
        if loaded_ids:
            fallback = next(iter(loaded_ids))
            logger.warning(
                f"ModelRouter:候选模型均未加载，降级使用 {fallback} (task={task_type})"
            )
            return fallback

        # 5. LM Studio 完全不可用 → 返回环境变量默认
        default_model = os.getenv("LMSTUDIO_MODEL", "qwen/qwen3.5-9b")
        logger.warning(f"ModelRouter:LM Studio 无可用模型，返回默认 {default_model}")
        return default_model

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
        """记录模型调用耗时（用于超时降级决策）。

        Args:
            model_id: 模型 ID。
            latency: 本次调用耗时（秒）。
        """
        self._latency[model_id] = latency
        if latency > self.timeout:
            logger.warning(
                f"ModelRouter:模型 {model_id} 耗时 {latency:.1f}s "
                f"超过阈值 {self.timeout}s，下次将触发降级"
            )

    def select_with_fallback(self, task_type: str) -> str:
        """选择模型并在超时时降级到备用模型。

        若首选模型最近一次调用耗时超过 self.timeout，自动切换到候选列表中的下一个。

        Args:
            task_type: 任务类型。

        Returns:
            模型 ID。
        """
        complexity = _TASK_COMPLEXITY.get(task_type, _TASK_COMPLEXITY["default"])
        candidates = _MODEL_CANDIDATES.get(complexity, _MODEL_CANDIDATES["small"])
        loaded_ids = {m["id"] for m in self.list_available_models()}

        for candidate in candidates:
            if candidate not in loaded_ids:
                continue
            latency = self._latency.get(candidate)
            # 首次调用或未超时 → 直接选用
            if latency is None or latency <= self.timeout:
                return candidate
            logger.info(
                f"ModelRouter:模型 {candidate} 超时(latency={latency:.1f}s)，"
                f"尝试下一个候选"
            )

        # 所有候选都超时或未加载 → 调用 select_model 兜底
        return self.select_model(task_type)

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
