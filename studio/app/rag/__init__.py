"""MISRA-C RAG 知识库模块。

提供轻量级的 MISRA-C 规则检索能力，基于关键词匹配，不依赖 ChromaDB / embedding。

子模块：
- rule_parser: 解析 misra_rules.txt 为结构化 MisraRule 列表
- misra_searcher: MisraRuleSearcher 检索引擎
- rag_enhancer: RAG 增强 Agent prompt 构建
"""

from app.rag.rule_parser import MisraRule, parse_misra_rules, categorize_rule
from app.rag.misra_searcher import MisraRuleSearcher
from app.rag.rag_enhancer import (
    RagEnhancer,
    enhance_prompt,
    build_misra_context,
)

__all__ = [
    "MisraRule",
    "parse_misra_rules",
    "categorize_rule",
    "MisraRuleSearcher",
    "RagEnhancer",
    "enhance_prompt",
    "build_misra_context",
]
