# -*- coding: utf-8 -*-
"""LLM 输出 JSON 兜底解析器（参考设计文档第 1.6.5 节）。

本地 LLM（如 Qwen2）偶发输出自然语言前缀、Markdown 包裹或非法转义，
导致 json.loads 失败。本模块提供三级降级解析，确保解析成功率 > 99%。

三级降级策略：
  1. 直接 json.loads
  2. 剥离 Markdown 代码块包裹（```json ... ```）
  3. 正则提取首个完整花括号块后再 json.loads

解析失败时返回 None（便于上层优雅降级为 mock，不抛异常）。
"""

import json
import re
from typing import Optional

from app.utils.log_util import logger


def safe_parse_llm_json(text: str) -> Optional[dict]:
    """三级降级解析 LLM 输出的 JSON。

    Args:
        text: LLM 输出的原始文本。

    Returns:
        解析成功返回 dict，失败返回 None。
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # 一级：直接解析
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # 二级：剥离 Markdown 代码块包裹（```json ... ``` 或 ``` ... ```）
    stripped = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        text,
        flags=re.MULTILINE,
    ).strip()
    try:
        result = json.loads(stripped)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # 三级：正则提取首个完整花括号块
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    logger.warning(
        f"safe_parse_llm_json: 三级解析均失败，文本前 200 字符: {text[:200]}"
    )
    return None
