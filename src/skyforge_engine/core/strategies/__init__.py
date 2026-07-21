"""Agent 策略层。

提供 MockStrategy 和 LLMStrategy，根据 LLM 模式自动选择。
"""

import os

from skyforge_engine.core.strategies.mock_strategy import MockStrategy
from skyforge_engine.core.strategies.llm_strategy import LLMStrategy


def get_strategy_for_mode() -> MockStrategy | LLMStrategy:
    """根据当前 LLM 模式返回对应策略。"""
    mode = os.environ.get("SKYFORGE_LLM_MODE", "mock").strip().lower()
    if mode == "mock":
        return MockStrategy()
    return LLMStrategy()


__all__ = ["MockStrategy", "LLMStrategy", "get_strategy_for_mode"]
