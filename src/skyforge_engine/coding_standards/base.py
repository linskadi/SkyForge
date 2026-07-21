"""编码标准基类与注册表。

设计原则：
- DO-178C 过程标准固定，编码标准可插拔
- 每个编码标准封装为一个 CodingStandard 实例
- 通过 CodingStandardRegistry 统一管理注册、查询、迭代
- 支持按语言、标准ID、规则ID 多维查询
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from skyforge_engine.utils.log_util import logger


@dataclass
class CodingStandard:
    """编码标准定义。

    Attributes:
        standard_id: 唯一标识符，如 "misra_c_2012"、"jsf_av_cpp"、"python_safety"
        name: 人类可读名称
        languages: 支持的语言列表，如 ["c"]、["cpp"]、["python"]
        version: 标准版本号
        rule_data_file: 规则数据文件路径（相对或绝对）
        rule_parser: 规则解析函数，接收文件内容返回规则列表
        red_line_rules: 每次必须注入的红线规则 ID 列表
        agent_default_queries: Agent 名称 → 默认检索查询关键词
        agent_display_names: Agent 名称 → 中文友好名
        rule_prefix_category: 规则号前缀 → 分类映射
        keyword_category_map: 关键词 → 分类映射列表
        fixers: 规则 ID → 修复函数映射
        mock_scan_patterns: Mock 扫描的正则模式列表
        priority: 优先级（数字越大优先级越高，同语言多标准时取最高优先级）
    """

    standard_id: str
    name: str
    languages: list[str]
    version: str = "1.0"
    rule_data_file: str = ""
    rule_parser: Callable[..., Any] | None = None
    red_line_rules: list[str] = field(default_factory=list)
    agent_default_queries: dict[str, list[str]] = field(default_factory=dict)
    agent_display_names: dict[str, str] = field(default_factory=dict)
    rule_prefix_category: dict[str, str] = field(default_factory=dict)
    keyword_category_map: list[tuple[list[str], str]] = field(default_factory=list)
    fixers: dict[str, Callable[..., Any]] = field(default_factory=dict)
    mock_scan_patterns: list[dict[str, Any]] = field(default_factory=list)
    priority: int = 0

    def load_rules(self) -> str:
        """加载规则数据文件内容。"""
        if not self.rule_data_file:
            return ""
        if os.path.isabs(self.rule_data_file):
            path = self.rule_data_file
        else:
            path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                self.rule_data_file,
            )
        if not os.path.exists(path):
            logger.warning(
                f"CodingStandard[{self.standard_id}]:规则文件不存在: {path}"
            )
            return ""
        with open(path, encoding="utf-8") as f:
            return f.read()

    def get_fixer(self, rule_id: str) -> Callable[..., Any] | None:
        """获取指定规则的修复函数。"""
        return self.fixers.get(rule_id)


class CodingStandardRegistry:
    """编码标准注册表。

    全局单例，管理所有已注册的编码标准。
    支持按语言、标准ID、规则ID 多维查询。
    """

    def __init__(self) -> None:
        self._standards: dict[str, CodingStandard] = {}
        self._loaded = False

    def register(self, standard: CodingStandard) -> None:
        """注册一个编码标准。"""
        if standard.standard_id in self._standards:
            logger.warning(
                f"编码标准 {standard.standard_id} 已注册，将被覆盖"
            )
        self._standards[standard.standard_id] = standard
        logger.info(
            f"编码标准已注册: {standard.standard_id} ({standard.name}) "
            f"语言={standard.languages} 版本={standard.version}"
        )

    def unregister(self, standard_id: str) -> None:
        """注销一个编码标准。"""
        if standard_id in self._standards:
            del self._standards[standard_id]
            logger.info(f"编码标准已注销: {standard_id}")

    def get(self, standard_id: str) -> CodingStandard | None:
        """按标准ID获取。"""
        self._ensure_loaded()
        return self._standards.get(standard_id)

    def get_for_language(self, language: str) -> list[CodingStandard]:
        """按语言获取所有适用的标准（按优先级降序排列）。"""
        self._ensure_loaded()
        result = [
            s for s in self._standards.values() if language in s.languages
        ]
        result.sort(key=lambda s: s.priority, reverse=True)
        return result

    def get_all(self) -> list[CodingStandard]:
        """获取所有已注册标准。"""
        self._ensure_loaded()
        return list(self._standards.values())

    def get_red_line_rules(self, language: str) -> list[str]:
        """获取指定语言的所有红线规则（合并同语言所有标准）。"""
        self._ensure_loaded()
        rules: list[str] = []
        for std in self.get_for_language(language):
            rules.extend(std.red_line_rules)
        return list(dict.fromkeys(rules))

    def get_agent_queries(self, language: str, agent_name: str) -> list[str]:
        """获取指定语言和Agent的默认检索查询。"""
        self._ensure_loaded()
        for std in self.get_for_language(language):
            if agent_name in std.agent_default_queries:
                return std.agent_default_queries[agent_name]
        return []

    def get_agent_display_name(self, language: str, agent_name: str) -> str:
        """获取Agent的中文友好名。"""
        self._ensure_loaded()
        for std in self.get_for_language(language):
            if agent_name in std.agent_display_names:
                return std.agent_display_names[agent_name]
        return agent_name

    def get_fixers(self, language: str) -> dict[str, Callable[..., Any]]:
        """获取指定语言的所有修复函数（合并同语言所有标准）。"""
        self._ensure_loaded()
        fixers: dict[str, Callable[..., Any]] = {}
        for std in self.get_for_language(language):
            fixers.update(std.fixers)
        return fixers

    def get_rule_prefix_category(self, language: str) -> dict[str, str]:
        """获取指定语言的规则号前缀→分类映射。"""
        self._ensure_loaded()
        result: dict[str, str] = {}
        for std in self.get_for_language(language):
            result.update(std.rule_prefix_category)
        return result

    def get_keyword_category_map(
        self, language: str
    ) -> list[tuple[list[str], str]]:
        """获取指定语言的关键词→分类映射。"""
        self._ensure_loaded()
        result: list[tuple[list[str], str]] = []
        for std in self.get_for_language(language):
            result.extend(std.keyword_category_map)
        return result

    def get_mock_scan_patterns(
        self, language: str
    ) -> list[dict[str, Any]]:
        """获取指定语言的 Mock 扫描模式。"""
        self._ensure_loaded()
        patterns: list[dict[str, Any]] = []
        for std in self.get_for_language(language):
            patterns.extend(std.mock_scan_patterns)
        return patterns

    def _ensure_loaded(self) -> None:
        """确保内置标准已自动加载。"""
        if not self._loaded:
            self._loaded = True
            self._load_builtin_standards()

    def _load_builtin_standards(self) -> None:
        """自动加载内置编码标准模块。"""
        builtins = [
            "skyforge_engine.coding_standards.misra_c",
            "skyforge_engine.coding_standards.misra_cpp",
            "skyforge_engine.coding_standards.python_safety",
        ]
        for module_name in builtins:
            try:
                importlib.import_module(module_name)
            except ImportError:
                logger.debug(
                    f"内置编码标准模块加载跳过: {module_name} (可选依赖)"
                )
            except Exception as e:
                logger.warning(
                    f"内置编码标准模块加载失败: {module_name}: {e}"
                )


_registry: CodingStandardRegistry | None = None


def get_registry() -> CodingStandardRegistry:
    """获取全局编码标准注册表单例。"""
    global _registry
    if _registry is None:
        _registry = CodingStandardRegistry()
    return _registry
