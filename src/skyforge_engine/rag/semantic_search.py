"""MISRA-C 规则语义搜索引擎：基于 sentence-transformers + ChromaDB 的向量化检索。

设计目标：
- 语义理解：将关键词匹配升级为语义相似度搜索，理解查询意图。
- 中英双语：使用 paraphrase-multilingual-MiniLM-L12-v2 模型，支持中英文混合查询。
- 降级兼容：当依赖不可用时，自动降级到关键词匹配（MisraRuleSearcher）。
- 上下文感知：结合规则分类、严重程度等元数据进行推荐。

集成方式：
    from skyforge_engine.rag.semantic_search import SemanticMisraSearcher
    searcher = SemanticMisraSearcher()
    results = searcher.search("动态内存分配的安全替代方案", top_k=5)

参考文档：
- 1.6.4 节 MISRA-C 上下文注入策略
- 第 3 章 RAG 系统设计（语义搜索扩展）
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from skyforge_engine.rag.rule_parser import MisraRule, parse_misra_rules
from skyforge_engine.rag.misra_searcher import MisraRuleSearcher
from skyforge_engine.utils.log_util import logger


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 语义搜索默认配置
_DEFAULT_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_DEFAULT_COLLECTION_NAME = "misra_rules"
_DEFAULT_PERSIST_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "chromadb"
)

# misra_rules.txt 默认路径
_DEFAULT_RULES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "misra_rules.txt"
)

# 中文查询扩展映射：将常见中文意图映射到规则关键词
_QUERY_EXPANSIONS: dict[str, list[str]] = {
    "动态内存": ["malloc", "free", "heap", "内存分配", "动态"],
    "内存泄漏": ["malloc", "free", "内存", "leak"],
    "数组越界": ["数组", "bounds", "index", "越界", "array"],
    "空指针": ["null", "指针", "pointer", "空"],
    "递归": ["recursion", "递归", "recursive", "栈溢出"],
    "未初始化": ["初始化", "initialize", "初始化", "未赋值"],
    "隐式类型转换": ["转换", "cast", "implicit", "类型", "conversion"],
    "goto语句": ["goto", "跳转", "branch"],
    "标准库": ["stdlib", "stdio", "string", "标准库", "library"],
    "宏定义": ["macro", "#define", "预处理", "宏"],
    "函数返回值": ["返回值", "return", "函数", "返回"],
    "声明": ["declaration", "声明", "定义", "prototype"],
    "控制流": ["if", "while", "for", "switch", "控制", "循环"],
}


# ---------------------------------------------------------------------------
# 可选依赖检测
# ---------------------------------------------------------------------------

_HAS_SENTENCE_TRANSFORMERS = False
_HAS_CHROMADB = False

try:
    from sentence_transformers import SentenceTransformer  # noqa: F401

    _HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    pass

try:
    import chromadb  # noqa: F401

    _HAS_CHROMADB = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# 结果数据类
# ---------------------------------------------------------------------------

@dataclass
class SemanticSearchResult:
    """语义搜索结果，包含规则和相关性得分。"""

    rule: MisraRule
    score: float
    match_type: str = "semantic"  # "semantic" | "keyword" | "fallback"

    @property
    def rule_id(self) -> str:
        return self.rule.rule_id

    def __repr__(self) -> str:
        return (
            f"<SemanticSearchResult rule_id={self.rule_id!r} "
            f"score={self.score:.4f} match_type={self.match_type!r}>"
        )


# ---------------------------------------------------------------------------
# 查询预处理
# ---------------------------------------------------------------------------

def _preprocess_query(query: str) -> str:
    """预处理查询：去除冗余字符、规范化空白。"""
    if not query:
        return ""
    query = query.strip()
    # 去除规则 ID 前缀（如 "MISRA-Rule-8.1" → "8.1"）
    query = re.sub(r"(?i)misra[-_]?(?:rule|dir)[-_]?", "", query)
    # 规范化空白
    query = re.sub(r"\s+", " ", query).strip()
    return query


def _expand_query(query: str) -> list[str]:
    """将单个查询扩展为多个语义相关查询。

    对中文查询进行同义扩展，提升召回率。
    返回包含原始查询和扩展查询的列表。
    """
    queries = [query]
    query_lower = query.lower()
    for pattern, expansions in _QUERY_EXPANSIONS.items():
        if pattern in query_lower or any(exp in query_lower for exp in expansions):
            for exp in expansions[:2]:
                if exp.lower() not in query_lower:
                    queries.append(exp)
            break
    return queries[:5]  # 最多 5 个扩展查询


def _build_rule_text(rule: MisraRule) -> str:
    """为单条规则构建向量化文本（包含多语言语义信息）。

    构建策略：
    - 规则 ID + 标题作为核心语义
    - 描述补充上下文
    - 分类标签提供结构化信息
    - 中英文关键词辅助跨语言匹配
    """
    parts = [rule.rule_id, rule.title]
    if rule.description:
        parts.append(rule.description)
    if rule.category:
        parts.append(f"category:{rule.category}")
    if rule.severity:
        parts.append(f"severity:{rule.severity}")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# SemanticMisraSearcher
# ---------------------------------------------------------------------------

class SemanticMisraSearcher:
    """MISRA-C 规则语义搜索引擎。

    支持三级检索策略：
    1. ChromaDB 向量语义搜索（最优）
    2. sentence-transformers + 内存向量搜索（ChromaDB 不可用时）
    3. 降级到关键词匹配 MisraRuleSearcher（依赖完全不可用时）

    使用方法：
        searcher = SemanticMisraSearcher()
        # 语义搜索
        results = searcher.search("动态内存分配的安全替代方案", top_k=5)
        # 精确查找（降级到关键词）
        rule = searcher.get_rule("Rule 21.3")
        # 上下文推荐
        recommendations = searcher.context_recommend("code_repairer", "修复内存泄漏问题")
    """

    def __init__(
        self,
        rules_path: Optional[str] = None,
        model_name: str = _DEFAULT_MODEL_NAME,
        persist_dir: Optional[str] = None,
    ) -> None:
        """初始化语义搜索引擎。

        Args:
            rules_path: misra_rules.txt 路径。
            model_name: sentence-transformers 模型名称。
            persist_dir: ChromaDB 持久化目录。
        """
        self._model_name = model_name
        self._persist_dir = persist_dir or _DEFAULT_PERSIST_DIR
        self._model: Optional["SentenceTransformer"] = None
        self._collection: Optional["chromadb.Collection"] = None
        self._chroma_client: Optional["chromadb.ClientAPI"] = None

        # 加载规则
        rules_path = rules_path or _DEFAULT_RULES_PATH
        self._rules: list[MisraRule] = []
        self._rules_by_id: dict[str, MisraRule] = {}
        self._load_rules(rules_path)

        # 关键词搜索引擎（降级方案）
        self._fallback_searcher: Optional[MisraRuleSearcher] = None

        # 初始化向量引擎
        self._engine_mode = self._init_engine()
        logger.info(
            f"SemanticMisraSearcher:engine_mode={self._engine_mode} "
            f"rules_count={len(self._rules)}"
        )

    def _load_rules(self, path: str) -> None:
        """加载并解析 MISRA 规则文件。"""
        if not os.path.exists(path):
            logger.error(f"SemanticMisraSearcher:规则文件不存在: {path}")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self._rules = parse_misra_rules(content)
            self._rules_by_id = {r.rule_id: r for r in self._rules}
            logger.info(f"SemanticMisraSearcher:加载 {len(self._rules)} 条规则")
        except Exception as e:
            logger.error(f"SemanticMisraSearcher:加载规则失败: {e}")

    def _init_engine(self) -> str:
        """初始化向量搜索引擎，返回引擎模式。

        Returns:
            "chromadb" | "in_memory" | "keyword_only"
        """
        # 尝试 ChromaDB 模式
        if _HAS_SENTENCE_TRANSFORMERS and _HAS_CHROMADB:
            try:
                self._model = SentenceTransformer(self._model_name)
                self._chroma_client = chromadb.PersistentClient(
                    path=self._persist_dir
                )
                self._collection = self._chroma_client.get_or_create_collection(
                    name=_DEFAULT_COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
                # 如果集合为空，进行索引
                if self._collection.count() == 0:
                    self._index_rules()
                return "chromadb"
            except Exception as e:
                logger.warning(
                    f"SemanticMisraSearcher:ChromaDB 初始化失败，降级: {e}"
                )

        # 尝试仅 sentence-transformers 内存模式
        if _HAS_SENTENCE_TRANSFORMERS:
            try:
                self._model = SentenceTransformer(self._model_name)
                self._index_rules_in_memory()
                return "in_memory"
            except Exception as e:
                logger.warning(
                    f"SemanticMisraSearcher:SentenceTransformer 初始化失败: {e}"
                )

        # 降级到关键词搜索
        logger.warning("SemanticMisraSearcher:降级到关键词匹配模式")
        self._fallback_searcher = MisraRuleSearcher()
        return "keyword_only"

    def _index_rules(self) -> None:
        """将所有规则索引到 ChromaDB。"""
        if not self._model or not self._collection or not self._rules:
            return

        batch_size = 64
        for i in range(0, len(self._rules), batch_size):
            batch = self._rules[i : i + batch_size]
            ids = [r.rule_id for r in batch]
            documents = [_build_rule_text(r) for r in batch]
            metadatas = [
                {
                    "category": r.category or "unknown",
                    "severity": r.severity or "unknown",
                    "rule_id": r.rule_id,
                }
                for r in batch
            ]
            embeddings = self._model.encode(documents).tolist()
            self._collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        logger.info(
            f"SemanticMisraSearcher:已索引 {len(self._rules)} 条规则到 ChromaDB"
        )

    def _index_rules_in_memory(self) -> None:
        """将规则索引到内存向量存储（无 ChromaDB 时的备选方案）。"""
        if not self._model or not self._rules:
            return
        documents = [_build_rule_text(r) for r in self._rules]
        self._memory_embeddings = self._model.encode(documents)
        self._memory_rules = list(self._rules)
        logger.info(
            f"SemanticMisraSearcher:已索引 {len(self._rules)} 条规则到内存"
        )

    # -------------------------------------------------------------------
    # 搜索 API
    # -------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        category_filter: Optional[str] = None,
        severity_filter: Optional[str] = None,
    ) -> list[SemanticSearchResult]:
        """语义搜索 MISRA-C 规则。

        Args:
            query: 查询字符串（支持中英文混合）。
            top_k: 返回最多 top_k 条结果。
            category_filter: 可选的分类过滤（如 "memory", "type"）。
            severity_filter: 可选的严重程度过滤（如 "强制", "要求"）。

        Returns:
            按相关性排序的 SemanticSearchResult 列表。
        """
        if not self._rules or not query or not query.strip():
            return []

        query = _preprocess_query(query)
        if not query:
            return []

        # 根据引擎模式选择搜索策略
        if self._engine_mode == "chromadb":
            results = self._search_chromadb(query, top_k * 2)
        elif self._engine_mode == "in_memory":
            results = self._search_in_memory(query, top_k * 2)
        else:
            return self._search_fallback(query, top_k)

        # 应用过滤器
        if category_filter:
            results = [
                r for r in results if r.rule.category == category_filter.lower()
            ]
        if severity_filter:
            results = [
                r for r in results if r.rule.severity == severity_filter
            ]

        # 去重（按 rule_id）
        seen: set[str] = set()
        unique: list[SemanticSearchResult] = []
        for r in results:
            if r.rule_id not in seen:
                seen.add(r.rule_id)
                unique.append(r)

        return unique[:top_k]

    def _search_chromadb(
        self, query: str, n_results: int
    ) -> list[SemanticSearchResult]:
        """ChromaDB 语义搜索。"""
        assert self._model is not None and self._collection is not None

        # 扩展查询
        expanded_queries = _expand_query(query)
        all_results: dict[str, SemanticSearchResult] = {}

        for q in expanded_queries:
            query_embedding = self._model.encode([q]).tolist()
            n = min(n_results, len(self._rules))
            response = self._collection.query(
                query_embeddings=query_embedding,
                n_results=n,
                include=["documents", "metadatas", "distances"],
            )
            if not response["ids"] or not response["ids"][0]:
                continue
            for idx, rule_id in enumerate(response["ids"][0]):
                distance = response["distances"][0][idx]
                # cosine 距离 → 相似度
                similarity = 1.0 - distance
                if rule_id in self._rules_by_id:
                    rule = self._rules_by_id[rule_id]
                    if (
                        rule_id not in all_results
                        or all_results[rule_id].score < similarity
                    ):
                        all_results[rule_id] = SemanticSearchResult(
                            rule=rule,
                            score=similarity,
                            match_type="semantic",
                        )

        results = sorted(all_results.values(), key=lambda x: x.score, reverse=True)
        return results

    def _search_in_memory(
        self, query: str, n_results: int
    ) -> list[SemanticSearchResult]:
        """内存向量搜索（当 ChromaDB 不可用时）。"""
        import numpy as np

        assert self._model is not None

        expanded_queries = _expand_query(query)
        all_results: dict[str, SemanticSearchResult] = {}

        for q in expanded_queries:
            query_embedding = self._model.encode([q])
            # 余弦相似度
            norms = np.linalg.norm(self._memory_embeddings, axis=1)
            query_norm = np.linalg.norm(query_embedding)
            if query_norm == 0:
                continue
            similarities = np.dot(self._memory_embeddings, query_embedding) / (
                norms * query_norm + 1e-10
            )
            top_indices = np.argsort(similarities)[::-1][:n_results]

            for idx in top_indices:
                rule = self._memory_rules[idx]
                score = float(similarities[idx])
                if (
                    rule.rule_id not in all_results
                    or all_results[rule.rule_id].score < score
                ):
                    all_results[rule.rule_id] = SemanticSearchResult(
                        rule=rule,
                        score=score,
                        match_type="semantic",
                    )

        results = sorted(all_results.values(), key=lambda x: x.score, reverse=True)
        return results

    def _search_fallback(
        self, query: str, top_k: int
    ) -> list[SemanticSearchResult]:
        """降级到关键词匹配搜索。"""
        if self._fallback_searcher is None:
            self._fallback_searcher = MisraRuleSearcher()
        keyword_results = self._fallback_searcher.search(query, top_k)
        return [
            SemanticSearchResult(rule=r, score=1.0, match_type="keyword")
            for r in keyword_results
        ]

    # -------------------------------------------------------------------
    # 精确查找
    # -------------------------------------------------------------------

    def get_rule(self, rule_id: str) -> Optional[MisraRule]:
        """按规则 ID 精确查找（兼容 MisraRuleSearcher 接口）。

        Args:
            rule_id: 规则 ID（如 "Rule 8.1", "Dir 4.1"）。

        Returns:
            MisraRule 或 None。
        """
        if not rule_id:
            return None
        # 直接查字典
        if rule_id in self._rules_by_id:
            return self._rules_by_id[rule_id]
        # 标准化后再查
        normalized = MisraRuleSearcher._normalize_rule_id(rule_id)
        if normalized in self._rules_by_id:
            return self._rules_by_id[normalized]
        # 仅用规则号匹配
        number_match = re.search(r"(\d+\.\d+)", rule_id)
        if number_match:
            number = number_match.group(1)
            for prefix in ("Rule", "Dir"):
                key = f"{prefix} {number}"
                if key in self._rules_by_id:
                    return self._rules_by_id[key]
        return None

    def get_all_rules(self) -> list[MisraRule]:
        """返回所有规则（兼容 MisraRuleSearcher 接口）。"""
        return list(self._rules)

    def get_rules_by_category(self, category: str) -> list[MisraRule]:
        """按分类检索规则（兼容 MisraRuleSearcher 接口）。"""
        if not category:
            return []
        return [r for r in self._rules if r.category == category.lower()]

    # -------------------------------------------------------------------
    # 上下文感知推荐
    # -------------------------------------------------------------------

    def context_recommend(
        self,
        agent_name: str,
        task_description: str,
        top_k: int = 5,
    ) -> list[SemanticSearchResult]:
        """根据 Agent 类型和任务描述进行上下文感知的规则推荐。

        结合 Agent 角色语义和任务语义，推荐最相关的 MISRA 规则。

        Args:
            agent_name: Agent 名称（如 "code_repairer", "code_generator"）。
            task_description: 任务描述文本。
            top_k: 返回最多 top_k 条推荐。

        Returns:
            按相关性排序的 SemanticSearchResult 列表。
        """
        if not self._rules or not task_description:
            return []

        # 构建复合查询：Agent 角色 + 任务描述
        agent_role_hints = {
            "requirement_parser": "需求分析 可追溯性 requirement analysis traceability",
            "contract_generator": "契约 前置条件 后置条件 断言 contract precondition postcondition assertion",
            "code_generator": "代码生成 函数声明 类型声明 命名规范 code generation function declaration",
            "code_repairer": "代码修复 隐式转换 未初始化 返回值 内存 code repair implicit conversion uninitialized",
        }
        role_hint = agent_role_hints.get(agent_name, "")
        composite_query = f"{task_description} {role_hint}".strip()

        # 语义搜索
        results = self.search(composite_query, top_k=top_k)

        # 按分类加权（任务相关分类得分提升）
        task_lower = task_description.lower()
        category_boosts: dict[str, float] = {}
        if any(kw in task_lower for kw in ["内存", "malloc", "free", "heap"]):
            category_boosts["memory"] = 1.3
        if any(kw in task_lower for kw in ["类型", "typedef", "struct", "转换"]):
            category_boosts["type"] = 1.2
        if any(kw in task_lower for kw in ["控制", "循环", "switch", "if"]):
            category_boosts["control"] = 1.2
        if any(kw in task_lower for kw in ["函数", "声明", "原型"]):
            category_boosts["declaration"] = 1.2
        if any(kw in task_lower for kw in ["预处理", "宏", "#define"]):
            category_boosts["preprocessor"] = 1.2
        if any(kw in task_lower for kw in ["标准库", "stdlib", "stdio"]):
            category_boosts["std_library"] = 1.2

        for r in results:
            boost = category_boosts.get(r.rule.category, 1.0)
            r.score *= boost

        # 重新排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    # -------------------------------------------------------------------
    # 索引管理
    # -------------------------------------------------------------------

    def rebuild_index(self) -> None:
        """重建向量索引（当规则文件更新后调用）。"""
        if self._engine_mode == "chromadb" and self._collection:
            self._chroma_client.delete_collection(_DEFAULT_COLLECTION_NAME)
            self._collection = self._chroma_client.get_or_create_collection(
                name=_DEFAULT_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            self._index_rules()
            logger.info("SemanticMisraSearcher:ChromaDB 索引已重建")
        elif self._engine_mode == "in_memory":
            self._index_rules_in_memory()
            logger.info("SemanticMisraSearcher:内存索引已重建")

    def get_index_stats(self) -> dict:
        """返回索引统计信息。"""
        stats: dict = {
            "engine_mode": self._engine_mode,
            "total_rules": len(self._rules),
            "model_name": self._model_name,
        }
        if self._engine_mode == "chromadb" and self._collection:
            stats["collection_count"] = self._collection.count()
        elif self._engine_mode == "in_memory":
            stats["memory_indexed"] = len(getattr(self, "_memory_rules", []))
        return stats

    # -------------------------------------------------------------------
    # 魔术方法
    # -------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._rules)

    def __repr__(self) -> str:
        return (
            f"<SemanticMisraSearcher engine_mode={self._engine_mode!r} "
            f"rules={len(self._rules)} model={self._model_name!r}>"
        )
