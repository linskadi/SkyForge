"""MISRA-C 规则检索引擎：基于关键词匹配的轻量级检索，不依赖 ChromaDB / embedding。

设计目标：
- 离线可用：仅用 Python 标准库（re / collections）实现。
- 检索语义：
  - 支持 "Rule 8.1" / "Dir 4.1" 等规则 ID 直接命中。
  - 支持 "函数声明"、"动态内存"、"隐式转换" 等中文关键词命中。
  - 支持 "malloc"、"static"、"goto" 等英文/代码关键词命中。
- 排序策略：基于 TF-IDF 思想的简化打分（关键词频次 + 字段权重 + 规则 ID 加分）。

参考文档：1.6.4 节 MISRA-C 上下文注入策略、第 3 章 RAG 系统设计。
"""

import os
import re
import math
from collections import Counter
from typing import Optional

from skyforge_engine.rag.rule_parser import MisraRule, parse_misra_rules
from skyforge_engine.utils.log_util import logger


# misra_rules.txt 默认路径
_DEFAULT_RULES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "misra_rules.txt"
)

# 字段权重（标题命中权重最高，其次描述，最后示例）
_FIELD_WEIGHTS = {
    "rule_id": 8.0,
    "title": 4.0,
    "description": 2.0,
    "examples": 1.0,
    "severity": 1.5,
}

# 严重程度权重（强制 > 要求 > 建议）
_SEVERITY_WEIGHTS = {
    "强制": 1.5,
    "要求": 1.0,
    "建议": 0.8,
}

# 中文停用词（避免高频通用词干扰检索）
_STOP_WORDS = {
    "的",
    "了",
    "和",
    "与",
    "或",
    "在",
    "中",
    "为",
    "是",
    "及",
    "等",
    "应",
    "应当",
    "应该",
    "不得",
    "不应",
    "必须",
    "可以",
    "the",
    "a",
    "an",
    "is",
    "are",
    "shall",
    "should",
    "must",
    "be",
    "to",
    "of",
    "in",
    "and",
    "or",
    "not",
    "for",
    "with",
}


def _tokenize(query: str) -> list[str]:
    """将查询切分为关键词列表。

    切分策略：
    - 提取中英文/数字 token（连续字母/数字/中文作为一个 token）
    - 中文 token 进一步切分为 2 字 bigram（避免短语无法匹配）
    - 规则 ID 形如 "Rule 8.1" / "Dir 4.1" / "8.1" 单独保留
    - 转小写
    - 去除停用词

    Args:
        query: 用户查询字符串。

    Returns:
        关键词 token 列表（去重）。
    """
    if not query:
        return []
    # 先匹配规则 ID 形如 "Rule 8.1" / "Dir 4.1"
    rule_id_tokens = re.findall(r"(?:rule|dir)\s*\d+\.\d+", query, re.IGNORECASE)
    # 移除已匹配的部分
    cleaned = re.sub(r"(?:rule|dir)\s*\d+\.\d+", " ", query, flags=re.IGNORECASE)
    # 再匹配单独的 "8.1" 数字编号
    number_tokens = re.findall(r"\d+\.\d+", cleaned)
    cleaned = re.sub(r"\d+\.\d+", " ", cleaned)
    # 匹配中文/英文/数字 token
    word_tokens = re.findall(r"[\u4e00-\u9fa5]+|[a-zA-Z_]+|\d+", cleaned)

    tokens: list[str] = []
    for tok in rule_id_tokens:
        # 规范化为 "rule 8.1" 形式
        normalized = re.sub(r"\s+", " ", tok.strip().lower())
        tokens.append(normalized)
    for tok in number_tokens:
        tokens.append(tok.strip())
    for tok in word_tokens:
        normalized = tok.strip().lower()
        if not normalized or normalized in _STOP_WORDS:
            continue
        # 单字符英文停用词过滤
        if len(normalized) == 1 and normalized.isalpha():
            continue
        tokens.append(normalized)
        # 中文 token 进一步切分为 2 字 bigram
        # 这样 "函数声明" 会被切成 "函数", "数声", "声明"
        # 便于匹配规则文本中分散的关键词
        if len(normalized) >= 3 and re.match(r"^[\u4e00-\u9fa5]+$", normalized):
            for i in range(len(normalized) - 1):
                bigram = normalized[i : i + 2]
                if bigram not in _STOP_WORDS:
                    tokens.append(bigram)

    # 去重保序
    seen: set[str] = set()
    unique: list[str] = []
    for tok in tokens:
        if tok not in seen:
            seen.add(tok)
            unique.append(tok)
    return unique


def _build_field_text(rule: MisraRule) -> dict[str, str]:
    """构建各字段的可检索文本（小写）。"""
    return {
        "rule_id": rule.rule_id.lower(),
        "title": rule.title.lower(),
        "description": (rule.description or "").lower(),
        "examples": "\n".join(rule.examples).lower(),
        "severity": (rule.severity or "").lower(),
    }


def _compute_idf(rules: list[MisraRule]) -> dict[str, float]:
    """计算所有 token 的逆文档频率 IDF。

    IDF(token) = log(N / (1 + df(token)))
    其中 N 是规则总数，df(token) 是包含该 token 的规则数。

    Args:
        rules: MisraRule 列表。

    Returns:
        {token: idf_value} 字典。
    """
    n = len(rules)
    if n == 0:
        return {}
    df: Counter = Counter()
    for rule in rules:
        fields = _build_field_text(rule)
        # 合并所有字段的 token
        all_text = " ".join(fields.values())
        tokens = set(_tokenize(all_text))
        for tok in tokens:
            df[tok] += 1
    idf: dict[str, float] = {}
    for tok, freq in df.items():
        idf[tok] = math.log((n + 1) / (1 + freq)) + 1.0
    return idf


def _score_rule(
    rule: MisraRule, query_tokens: list[str], idf: dict[str, float]
) -> float:
    """对单条规则与查询关键词的相关性打分。

    打分公式：sum(token_score * field_weight * idf) + severity_weight + rule_id_bonus

    Args:
        rule: 待评分的规则。
        query_tokens: 查询关键词列表。
        idf: token → IDF 字典。

    Returns:
        相关性得分（越高越相关）。
    """
    if not query_tokens:
        return 0.0
    fields = _build_field_text(rule)
    score = 0.0
    for token in query_tokens:
        token_idf = idf.get(token, 1.0)
        # 在每个字段中查找 token 出现次数
        for field_name, weight in _FIELD_WEIGHTS.items():
            text = fields.get(field_name, "")
            if not text:
                continue
            # 计算出现次数
            count = text.count(token)
            if count > 0:
                # 使用 1 + log(count) 平滑高频命中
                token_score = 1.0 + math.log(count)
                score += token_score * weight * token_idf

        # 规则 ID 精确命中额外加分（如查询 "8.1" 命中 "rule 8.1"）
        rule_id_lower = rule.rule_id.lower()
        if token in rule_id_lower:
            # 全词匹配检查：避免 "8.1" 命中 "18.1"
            # 简单处理：token 前后是非数字字符或边界
            pattern = rf"(?<![0-9]){re.escape(token)}(?![0-9])"
            if re.search(pattern, rule_id_lower):
                score += 10.0 * token_idf

    # 严重程度加权
    sev_weight = _SEVERITY_WEIGHTS.get(rule.severity, 1.0)
    score *= sev_weight

    return score


class MisraRuleSearcher:
    """MISRA-C 规则检索引擎（轻量级，无外部依赖）。

    使用方法：
        searcher = MisraRuleSearcher()
        results = searcher.search("函数声明", top_k=5)
        rule = searcher.get_rule("Rule 8.1")
        all_rules = searcher.get_all_rules()
        type_rules = searcher.get_rules_by_category("type")
    """

    _instance: Optional["MisraRuleSearcher"] = None
    _rules: list[MisraRule]
    _rules_by_id: dict[str, MisraRule]
    _idf: dict[str, float]

    def __init__(self, rules_path: Optional[str] = None) -> None:
        """初始化检索引擎，加载并解析 misra_rules.txt。

        Args:
            rules_path: misra_rules.txt 路径。默认使用模块内 data 目录下的文件。
        """
        path = rules_path or _DEFAULT_RULES_PATH
        if not os.path.exists(path):
            logger.error(f"MisraRuleSearcher:规则文件不存在: {path}")
            self._rules = []
            self._rules_by_id = {}
            self._idf = {}
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self._rules = parse_misra_rules(content)
            self._rules_by_id = {r.rule_id: r for r in self._rules}
            self._idf = _compute_idf(self._rules)
            logger.info(f"MisraRuleSearcher:加载 {len(self._rules)} 条规则 from {path}")
        except Exception as e:
            logger.error(f"MisraRuleSearcher:加载规则失败: {e}")
            self._rules = []
            self._rules_by_id = {}
            self._idf = {}

    @classmethod
    def get_instance(cls) -> "MisraRuleSearcher":
        """获取单例实例（避免重复 IO）。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def search(self, query: str, top_k: int = 5) -> list[MisraRule]:
        """关键词检索 MISRA-C 规则。

        支持的查询示例：
        - "Rule 8.1"：直接匹配规则 ID
        - "函数声明"：中文关键词匹配
        - "动态内存" / "malloc"：动态内存相关规则
        - "隐式转换"：表达式相关规则

        Args:
            query: 查询字符串。
            top_k: 返回最多 top_k 条规则。

        Returns:
            相关性排序后的 MisraRule 列表（最多 top_k 条）。
        """
        if not self._rules:
            return []
        if not query or not query.strip():
            return []
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        # 对所有规则打分
        scored = [
            (rule, _score_rule(rule, query_tokens, self._idf)) for rule in self._rules
        ]
        # 过滤得分为 0 的，按分数降序排序
        relevant = [(r, s) for r, s in scored if s > 0]
        relevant.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in relevant[: max(0, top_k)]]

    def get_rule(self, rule_id: str) -> Optional[MisraRule]:
        """按规则 ID 精确查找。

        支持的输入格式：
        - "Rule 8.1" / "Dir 4.1"（标准格式）
        - "rule 8.1" / "RULE 8.1"（大小写不敏感）
        - "8.1"（仅规则号，会自动匹配 Rule/Dir）
        - "MISRA-C:2012-Rule-8.1"（带前缀的格式）

        Args:
            rule_id: 规则 ID。

        Returns:
            MisraRule 或 None（未找到时）。
        """
        if not rule_id:
            return None
        # 标准化：去除前缀，保留 "Rule X.Y" / "Dir X.Y" 形式
        normalized = self._normalize_rule_id(rule_id)
        if normalized in self._rules_by_id:
            return self._rules_by_id[normalized]
        # 尝试仅用规则号匹配（先 Rule 后 Dir）
        number_match = re.search(r"(\d+\.\d+)", rule_id)
        if number_match:
            number = number_match.group(1)
            for prefix in ("Rule", "Dir"):
                key = f"{prefix} {number}"
                if key in self._rules_by_id:
                    return self._rules_by_id[key]
        return None

    @staticmethod
    def _normalize_rule_id(rule_id: str) -> str:
        """将各种规则 ID 格式标准化为 'Rule X.Y' / 'Dir X.Y'。"""
        # 提取规则类型和编号
        m = re.search(r"(rule|dir)", rule_id, re.IGNORECASE)
        number_m = re.search(r"(\d+\.\d+)", rule_id)
        if m and number_m:
            return f"{m.group(1).capitalize()} {number_m.group(1)}"
        return rule_id.strip()

    def get_all_rules(self) -> list[MisraRule]:
        """返回所有 MISRA-C 规则（按 ID 排序）。"""
        return list(self._rules)

    def get_rules_by_category(self, category: str) -> list[MisraRule]:
        """按分类检索规则。

        Args:
            category: 分类名称（type/memory/control/expression/declaration/
                preprocessor/std_library/identifier/comments/lexical/
                environment/unused_code/constant/other）。

        Returns:
            该分类下的所有规则。
        """
        if not category:
            return []
        category_lower = category.lower().strip()
        return [r for r in self._rules if r.category == category_lower]

    def get_categories_summary(self) -> dict[str, int]:
        """返回各分类的规则数量统计。"""
        summary: Counter = Counter()
        for rule in self._rules:
            summary[rule.category] += 1
        return dict(summary)

    def get_severity_summary(self) -> dict[str, int]:
        """返回各严重程度的规则数量统计。"""
        summary: Counter = Counter()
        for rule in self._rules:
            summary[rule.severity or "未知"] += 1
        return dict(summary)

    def __len__(self) -> int:
        return len(self._rules)

    def __repr__(self) -> str:
        return f"<MisraRuleSearcher rules={len(self._rules)}>"
