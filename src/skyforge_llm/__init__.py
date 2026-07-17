"""SkyForge LLM — LLM 抽象与安全封装层。

Provider 适配: OpenAI · Anthropic · Qwen · DeepSeek · 智谱 · Moonshot · 通用 OpenAI 兼容
安全封装:   输入净化 + 输出校验 + 审计日志 + Prompt 加固
本地 LLM:   接口预留，当前不开发（个人 PC 本地 LLM 性能不足）

依赖: skyforge-engine + httpx + openai + anthropic
默认: USE_LLM=true，使用真实 LLM 推理
降级: LM Studio 不可用时自动降级为 Mock 模式（关键词匹配+模板拼接）
"""

from skyforge_llm.client import LMStudioClient, UnifiedLLMClient, get_lmstudio_client
from skyforge_llm.parser import safe_parse_llm_json

__version__ = "0.4.0"
__all__ = ["LMStudioClient", "UnifiedLLMClient", "get_lmstudio_client", "safe_parse_llm_json"]
