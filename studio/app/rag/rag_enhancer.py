"""RAG 增强 Agent prompt 构建器：根据任务检索相关 MISRA 规则注入到 Agent prompt。

参考文档：
- 1.6.4 节 MISRA-C 上下文注入策略（静态红线规则 + 动态检索规则 + 去重）
- 第 3 章 RAG 系统设计

策略：
- 静态红线规则：每次必注入的高优先级规则（如 Rule 21.3 禁动态内存、Rule 8.1 类型声明）。
- 动态检索规则：根据 Agent 任务类型检索的 top-K 规则。
- 去重：rule_id 集合去重，避免重复注入。
"""

from typing import Optional

from app.config.setting import settings
from app.rag.misra_searcher import MisraRuleSearcher
from app.rag.rule_parser import MisraRule
from app.utils.log_util import logger


# 静态红线规则 ID 列表（每次必注入）
# 参考 1.6.4 节：航空软件不可妥协的核心规则
_RED_LINE_RULE_IDS: list[str] = [
    "Rule 21.3",  # 不得使用 malloc/free（动态内存）
    "Rule 21.6",  # 不得使用标准库输入/输出函数
    "Rule 8.1",  # 类型应明确指定
    "Rule 8.7",  # 内部链接对象应使用 static
    "Rule 17.7",  # 函数返回值必须被使用
    "Rule 1.3",  # 避免未定义行为
    "Rule 20.4",  # 不得使用动态内存分配宏
    "Rule 8.4",  # 外部链接对象需可见声明
    "Rule 9.1",  # 自动变量使用前必须初始化
    "Dir 4.1",  # 运行时故障必须最小化
]

# Agent 名称 → 默认检索查询关键词
_AGENT_DEFAULT_QUERIES: dict[str, list[str]] = {
    "requirement_parser": ["需求", "可追溯性", "需求分析"],
    "contract_generator": ["契约", "前置条件", "后置条件", "断言"],
    "code_generator": ["函数声明", "类型声明", "命名规范", "static"],
    "code_repairer": ["隐式转换", "动态内存", "未初始化", "返回值"],
}

# Agent 名称 → 中文友好名
_AGENT_DISPLAY_NAMES: dict[str, str] = {
    "requirement_parser": "需求解析 Agent",
    "contract_generator": "契约生成 Agent",
    "code_generator": "代码生成 Agent",
    "code_repairer": "代码修复 Agent",
}


def _format_rule_for_context(rule: MisraRule) -> str:
    """将单条 MisraRule 格式化为上下文文本片段。

    Args:
        rule: MisraRule 实例。

    Returns:
        格式化后的文本（含规则 ID、标题、严重程度、描述、示例预览）。
    """
    lines = [f"### {rule.rule_id} ({rule.severity or '未知'})"]
    if rule.title:
        lines.append(f"**标题**: {rule.title}")
    if rule.description:
        # 描述截断（避免过长）
        desc = rule.description
        if len(desc) > 500:
            desc = desc[:500] + "..."
        lines.append(f"**描述**: {desc}")
    if rule.examples:
        # 仅保留前 1 个示例，且截断
        first_example = rule.examples[0]
        if len(first_example) > 300:
            first_example = first_example[:300] + "..."
        lines.append("**示例**:")
        lines.append("```c")
        lines.append(first_example)
        lines.append("```")
    return "\n".join(lines)


class RagEnhancer:
    """RAG 增强器：根据任务和 Agent 类型构建 MISRA-C 上下文。

    使用方法：
        enhancer = RagEnhancer()
        enhanced = enhancer.enhance_prompt("code_generator", "实现一个低通滤波器")
        context = enhancer.build_misra_context(["Rule 8.1", "Rule 21.3"])
    """

    def __init__(self, searcher: Optional[MisraRuleSearcher] = None) -> None:
        """初始化 RAG 增强器。

        Args:
            searcher: 可选的 MisraRuleSearcher 实例（不传则使用单例）。
        """
        self._searcher = searcher or MisraRuleSearcher.get_instance()
        self._enabled: bool = bool(getattr(settings, "RAG_ENABLED", False))
        self._top_k: int = int(getattr(settings, "RAG_TOP_K", 5))

    @property
    def enabled(self) -> bool:
        """RAG 是否启用。"""
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """运行时切换 RAG 启用状态。"""
        self._enabled = enabled
        logger.info(f"RagEnhancer:RAG 已{'启用' if enabled else '禁用'}")

    def enhance_prompt(self, agent_name: str, task: str) -> str:
        """根据任务检索相关 MISRA 规则，注入到 Agent prompt。

        Args:
            agent_name: Agent 名称（如 "code_generator" / "code_repairer"）。
            task: Agent 当前任务描述。

        Returns:
            注入 MISRA 规则上下文后的增强 prompt 字符串。
            若 RAG 未启用或无相关规则，返回空字符串。
        """
        if not self._enabled:
            logger.debug("RagEnhancer:RAG 未启用，跳过增强")
            return ""
        if not self._searcher.get_all_rules():
            logger.warning("RagEnhancer:无可用规则，跳过增强")
            return ""

        agent_display = _AGENT_DISPLAY_NAMES.get(agent_name, agent_name)
        # 1) 获取该 Agent 默认查询关键词
        default_queries = _AGENT_DEFAULT_QUERIES.get(agent_name, [])
        # 2) 将任务本身作为查询
        task_query = task.strip() if task else ""

        # 3) 动态检索：用任务关键词 + 默认关键词检索
        dynamic_rules: list[MisraRule] = []
        seen_ids: set[str] = set()

        # 先用任务文本检索
        if task_query:
            results = self._searcher.search(task_query, top_k=self._top_k)
            for rule in results:
                if rule.rule_id not in seen_ids:
                    seen_ids.add(rule.rule_id)
                    dynamic_rules.append(rule)

        # 再用默认关键词补充检索
        for query in default_queries:
            if len(dynamic_rules) >= self._top_k:
                break
            results = self._searcher.search(query, top_k=max(2, self._top_k // 2))
            for rule in results:
                if rule.rule_id not in seen_ids:
                    seen_ids.add(rule.rule_id)
                    dynamic_rules.append(rule)
                    if len(dynamic_rules) >= self._top_k:
                        break

        # 4) 静态红线规则
        red_line_rules: list[MisraRule] = []
        for rule_id in _RED_LINE_RULE_IDS:
            rule = self._searcher.get_rule(rule_id)
            if rule and rule.rule_id not in seen_ids:
                seen_ids.add(rule.rule_id)
                red_line_rules.append(rule)

        if not dynamic_rules and not red_line_rules:
            return ""

        # 5) 构建上下文文本
        return self._build_context_text(
            agent_name=agent_name,
            agent_display=agent_display,
            task=task_query,
            red_line_rules=red_line_rules,
            dynamic_rules=dynamic_rules,
        )

    def build_misra_context(self, rule_ids: list[str]) -> str:
        """构建指定规则 ID 集合的 MISRA 上下文。

        参考 1.6.4 节：静态红线规则 + 动态检索规则 + 去重。
        本方法接收一组规则 ID，返回格式化的上下文文本。
        若 RAG 未启用，返回空字符串。

        Args:
            rule_ids: 规则 ID 列表（如 ["Rule 8.1", "Rule 21.3"]）。

        Returns:
            格式化的 MISRA 规则上下文文本。
        """
        if not self._enabled:
            logger.debug("RagEnhancer:RAG 未启用，跳过构建上下文")
            return ""
        if not rule_ids:
            return ""
        if not self._searcher.get_all_rules():
            logger.warning("RagEnhancer:无可用规则，跳过构建上下文")
            return ""

        # 1) 静态红线规则（去重）
        seen_ids: set[str] = set()
        red_line_rules: list[MisraRule] = []
        for rule_id in _RED_LINE_RULE_IDS:
            rule = self._searcher.get_rule(rule_id)
            if rule and rule.rule_id not in seen_ids:
                seen_ids.add(rule.rule_id)
                red_line_rules.append(rule)

        # 2) 动态指定规则（去重）
        dynamic_rules: list[MisraRule] = []
        for rule_id in rule_ids:
            # 标准化输入
            rule = self._searcher.get_rule(rule_id)
            if rule and rule.rule_id not in seen_ids:
                seen_ids.add(rule.rule_id)
                dynamic_rules.append(rule)

        if not red_line_rules and not dynamic_rules:
            return ""

        # 3) 构建上下文文本
        return self._build_context_text(
            agent_name="custom",
            agent_display="自定义",
            task="",
            red_line_rules=red_line_rules,
            dynamic_rules=dynamic_rules,
        )

    def _build_context_text(
        self,
        agent_name: str,
        agent_display: str,
        task: str,
        red_line_rules: list[MisraRule],
        dynamic_rules: list[MisraRule],
    ) -> str:
        """构建最终的上下文文本。

        结构：
        === MISRA-C 规则上下文（{Agent 名称}） ===
        ## 静态红线规则（必须遵守）
        ...
        ## 动态检索规则（与任务相关）
        ...
        ## 任务描述
        {task}
        === 上下文结束 ===
        """
        lines = [
            f"=== MISRA-C 规则上下文（{agent_display}）===",
        ]
        if red_line_rules:
            lines.append("## 静态红线规则（必须遵守，不可妥协）")
            for rule in red_line_rules:
                lines.append(_format_rule_for_context(rule))
                lines.append("")
        if dynamic_rules:
            lines.append("## 动态检索规则（与当前任务相关）")
            for rule in dynamic_rules:
                lines.append(_format_rule_for_context(rule))
                lines.append("")
        if task:
            lines.append("## 任务描述")
            lines.append(task)
            lines.append("")
        lines.append("=== 上下文结束 ===")
        lines.append(
            "提示：在执行任务时，请严格遵守上述 MISRA-C 规则。"
            "每处代码改动应标注对应规则 ID（如 [MISRA-Rule-8.1]）以保持追溯链。"
        )
        return "\n".join(lines)


# ============================================================================
# 模块级便捷函数（参考文档 1.6.4 节）
# ============================================================================

# 全局单例（懒加载）
_global_enhancer: Optional[RagEnhancer] = None


def _get_enhancer() -> RagEnhancer:
    """获取全局 RagEnhancer 单例。"""
    global _global_enhancer
    if _global_enhancer is None:
        _global_enhancer = RagEnhancer()
    return _global_enhancer


def enhance_prompt(agent_name: str, task: str) -> str:
    """模块级便捷函数：根据任务检索相关 MISRA 规则，注入到 Agent prompt。

    Args:
        agent_name: Agent 名称。
        task: 任务描述。

    Returns:
        增强 prompt 字符串。若 RAG 未启用返回空字符串。
    """
    return _get_enhancer().enhance_prompt(agent_name, task)


def build_misra_context(rule_ids: list[str]) -> str:
    """模块级便捷函数：构建指定规则 ID 集合的 MISRA 上下文。

    Args:
        rule_ids: 规则 ID 列表。

    Returns:
        上下文文本字符串。
    """
    return _get_enhancer().build_misra_context(rule_ids)
