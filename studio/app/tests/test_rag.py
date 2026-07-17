"""RAG 知识库（MISRA-C 规则检索引擎）测试。

测试覆盖：
- test_search_by_keyword：关键词检索
- test_get_rule_by_id：精确查找
- test_get_all_rules：全量规则
- test_get_rules_by_category：分类检索
- test_enhance_prompt：RAG 增强 prompt
- test_build_misra_context：构建上下文
- test_categorize：规则分类
"""

import os
import unittest

from app.rag.misra_searcher import MisraRuleSearcher
from app.rag.rag_enhancer import RagEnhancer, enhance_prompt, build_misra_context
from app.rag.rule_parser import (
    MisraRule,
    parse_misra_rules,
    categorize_rule,
)


# misra_rules.txt 路径
_RULES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "rag",
    "data",
    "misra_rules.txt",
)
_RULES_PATH = os.path.abspath(_RULES_PATH)


def _has_rules_file() -> bool:
    """检查 misra_rules.txt 是否存在。"""
    return os.path.exists(_RULES_PATH)


@unittest.skipUnless(_has_rules_file(), "misra_rules.txt 不存在")
class TestRuleParser(unittest.TestCase):
    """规则解析器测试。"""

    def test_categorize_type(self) -> None:
        """类型相关规则应分类到 type。"""
        category = categorize_rule("Rule 6.1 Bit-fields shall only be declared", "")
        self.assertEqual(category, "type")

    def test_categorize_memory(self) -> None:
        """动态内存相关规则应分类到 memory。"""
        category = categorize_rule(
            "Rule 21.3 不得使用 malloc free 进行动态内存分配",
            "动态内存分配 malloc free",
        )
        self.assertEqual(category, "memory")

    def test_categorize_control(self) -> None:
        """控制流相关规则应分类到 control。"""
        category = categorize_rule("Rule 14.4 if 语句控制表达式", "")
        self.assertEqual(category, "control")

    def test_categorize_expression(self) -> None:
        """表达式相关规则应分类到 expression。"""
        category = categorize_rule("Rule 10.1 隐式转换", "")
        self.assertEqual(category, "expression")

    def test_categorize_preprocessor(self) -> None:
        """预处理相关规则应分类到 preprocessor。"""
        category = categorize_rule("Rule 20.1 #include 指令", "")
        self.assertEqual(category, "preprocessor")

    def test_categorize_std_library(self) -> None:
        """标准库相关规则应分类到 std_library。"""
        category = categorize_rule("Rule 21.6 不得使用标准库 stdio 函数", "")
        self.assertEqual(category, "std_library")

    def test_categorize_default(self) -> None:
        """无明确特征的规则应 fallback 到 declaration。"""
        category = categorize_rule("未知规则内容", "")
        self.assertEqual(category, "declaration")

    def test_parse_misra_rules_count(self) -> None:
        """解析出的规则总数应合理（≥ 100）。"""
        with open(_RULES_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        rules = parse_misra_rules(content)
        self.assertGreaterEqual(
            len(rules), 100, f"仅解析出 {len(rules)} 条规则，期望 ≥ 100"
        )

    def test_parse_misra_rules_structure(self) -> None:
        """解析出的规则应包含必要字段。"""
        with open(_RULES_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        rules = parse_misra_rules(content)
        # 抽查前 5 条
        for rule in rules[:5]:
            self.assertIsInstance(rule, MisraRule)
            self.assertTrue(rule.rule_id)
            self.assertTrue(rule.title)
            self.assertIn(
                rule.category,
                [
                    "type",
                    "memory",
                    "control",
                    "expression",
                    "declaration",
                    "preprocessor",
                    "std_library",
                    "environment",
                    "unused_code",
                    "comments",
                    "lexical",
                    "identifier",
                    "constant",
                    "other",
                ],
            )

    def test_parse_misra_rules_contains_rule_8_1(self) -> None:
        """应能解析出 Rule 8.1。"""
        with open(_RULES_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        rules = parse_misra_rules(content)
        rule_ids = [r.rule_id for r in rules]
        self.assertIn("Rule 8.1", rule_ids)

    def test_parse_misra_rules_contains_dir_4_1(self) -> None:
        """应能解析出 Dir 4.1。"""
        with open(_RULES_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        rules = parse_misra_rules(content)
        rule_ids = [r.rule_id for r in rules]
        self.assertIn("Dir 4.1", rule_ids)


@unittest.skipUnless(_has_rules_file(), "misra_rules.txt 不存在")
class TestMisraRuleSearcher(unittest.TestCase):
    """MISRA 规则检索引擎测试。"""

    @classmethod
    def setUpClass(cls) -> None:
        """测试类初始化：创建 searcher 实例（避免重复 IO）。"""
        cls.searcher = MisraRuleSearcher(_RULES_PATH)

    def test_get_all_rules(self) -> None:
        """全量规则应非空且数量 ≥ 100。"""
        rules = self.searcher.get_all_rules()
        self.assertGreaterEqual(len(rules), 100, f"仅 {len(rules)} 条规则")
        # 验证规则 ID 唯一
        rule_ids = [r.rule_id for r in rules]
        self.assertEqual(len(rule_ids), len(set(rule_ids)), "规则 ID 有重复")

    def test_get_rule_by_id(self) -> None:
        """按规则 ID 精确查找 Rule 8.1。"""
        rule = self.searcher.get_rule("Rule 8.1")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_id, "Rule 8.1")
        self.assertTrue(rule.title)

    def test_get_rule_by_id_dir(self) -> None:
        """按规则 ID 精确查找 Dir 4.1。"""
        rule = self.searcher.get_rule("Dir 4.1")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_id, "Dir 4.1")

    def test_get_rule_by_id_case_insensitive(self) -> None:
        """规则 ID 大小写不敏感。"""
        rule = self.searcher.get_rule("rule 8.1")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_id, "Rule 8.1")

    def test_get_rule_by_id_with_prefix(self) -> None:
        """支持带前缀的规则 ID（如 MISRA-C:2012-Rule-8.1）。"""
        rule = self.searcher.get_rule("MISRA-C:2012-Rule-8.1")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_id, "Rule 8.1")

    def test_get_rule_by_number_only(self) -> None:
        """仅规则号也能匹配。"""
        rule = self.searcher.get_rule("8.1")
        self.assertIsNotNone(rule)
        self.assertTrue(rule.rule_id.endswith("8.1"))

    def test_get_rule_not_found(self) -> None:
        """不存在的规则 ID 应返回 None。"""
        rule = self.searcher.get_rule("Rule 99.99")
        self.assertIsNone(rule)

    def test_search_by_keyword_chinese(self) -> None:
        """中文关键词检索：动态内存应能找到相关规则。"""
        results = self.searcher.search("动态内存", top_k=5)
        self.assertGreater(len(results), 0, "未找到动态内存相关规则")
        # 至少有一条规则与内存相关
        rule_texts = [
            (r.rule_id + " " + r.title + " " + r.description).lower() for r in results
        ]
        has_memory = any(
            "memory" in text or "malloc" in text or "内存" in text
            for text in rule_texts
        )
        self.assertTrue(has_memory, f"动态内存检索结果未包含内存规则: {rule_texts}")

    def test_search_by_keyword_function_decl(self) -> None:
        """中文关键词检索：函数声明应能找到 Rule 8.x 相关规则。"""
        results = self.searcher.search("函数声明", top_k=5)
        self.assertGreater(len(results), 0)
        # 期望结果中包含 Rule 8.x（声明和定义章节）
        rule_ids = [r.rule_id for r in results]
        has_rule_8 = any("Rule 8." in rid for rid in rule_ids)
        self.assertTrue(
            has_rule_8,
            f"函数声明检索结果未包含 Rule 8.x: {rule_ids}",
        )

    def test_search_by_keyword_implicit_conversion(self) -> None:
        """中文关键词检索：隐式转换应能找到 Rule 10.x 相关规则。"""
        results = self.searcher.search("隐式转换", top_k=5)
        self.assertGreater(len(results), 0)
        rule_ids = [r.rule_id for r in results]
        has_rule_10 = any("Rule 10." in rid for rid in rule_ids)
        self.assertTrue(
            has_rule_10,
            f"隐式转换检索结果未包含 Rule 10.x: {rule_ids}",
        )

    def test_search_by_rule_id(self) -> None:
        """规则 ID 检索：'Rule 8.1' 应能命中 Rule 8.1。"""
        results = self.searcher.search("Rule 8.1", top_k=5)
        self.assertGreater(len(results), 0)
        rule_ids = [r.rule_id for r in results]
        self.assertIn("Rule 8.1", rule_ids)

    def test_search_by_english_keyword(self) -> None:
        """英文关键词检索：malloc 应能找到内存相关规则。"""
        results = self.searcher.search("malloc", top_k=5)
        self.assertGreater(len(results), 0)

    def test_search_top_k_limit(self) -> None:
        """top_k 限制应生效。"""
        results = self.searcher.search("类型", top_k=3)
        self.assertLessEqual(len(results), 3)

    def test_search_empty_query(self) -> None:
        """空查询应返回空列表。"""
        self.assertEqual(self.searcher.search("", top_k=5), [])
        self.assertEqual(self.searcher.search("   ", top_k=5), [])

    def test_get_rules_by_category_type(self) -> None:
        """按 type 分类检索应返回 type 类规则。"""
        rules = self.searcher.get_rules_by_category("type")
        self.assertGreater(len(rules), 0, "type 分类下应有规则")
        for rule in rules:
            self.assertEqual(rule.category, "type")

    def test_get_rules_by_category_memory(self) -> None:
        """按 memory 分类检索应返回 memory 类规则。"""
        rules = self.searcher.get_rules_by_category("memory")
        # memory 分类可能为空（如果规则都被归到 std_library），
        # 但至少应该能调用成功
        for rule in rules:
            self.assertEqual(rule.category, "memory")

    def test_get_rules_by_category_control(self) -> None:
        """按 control 分类检索应返回 control 类规则。"""
        rules = self.searcher.get_rules_by_category("control")
        self.assertGreater(len(rules), 0, "control 分类下应有规则")
        for rule in rules:
            self.assertEqual(rule.category, "control")

    def test_get_rules_by_category_unknown(self) -> None:
        """未知分类应返回空列表。"""
        rules = self.searcher.get_rules_by_category("unknown_category")
        self.assertEqual(rules, [])

    def test_get_categories_summary(self) -> None:
        """分类统计应返回非空字典。"""
        summary = self.searcher.get_categories_summary()
        self.assertIsInstance(summary, dict)
        self.assertGreater(len(summary), 0)
        # 总和应等于规则总数
        total = sum(summary.values())
        self.assertEqual(total, len(self.searcher.get_all_rules()))

    def test_get_severity_summary(self) -> None:
        """严重程度统计应返回非空字典。"""
        summary = self.searcher.get_severity_summary()
        self.assertIsInstance(summary, dict)
        self.assertGreater(len(summary), 0)

    def test_searcher_singleton(self) -> None:
        """get_instance 应返回同一个实例。"""
        s1 = MisraRuleSearcher.get_instance()
        s2 = MisraRuleSearcher.get_instance()
        self.assertIs(s1, s2)


@unittest.skipUnless(_has_rules_file(), "misra_rules.txt 不存在")
class TestRagEnhancer(unittest.TestCase):
    """RAG 增强器测试。"""

    @classmethod
    def setUpClass(cls) -> None:
        """测试类初始化。"""
        cls.searcher = MisraRuleSearcher(_RULES_PATH)
        # 创建一个 RAG 启用的 enhancer 用于测试
        cls.enhancer = RagEnhancer(cls.searcher)
        cls.enhancer.set_enabled(True)

    def test_enhance_prompt_code_generator(self) -> None:
        """代码生成 Agent 的 enhance_prompt 应返回非空上下文。"""
        result = self.enhancer.enhance_prompt("code_generator", "实现一个低通滤波器")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)
        # 应包含 MISRA 规则上下文标记
        self.assertIn("MISRA", result)
        # 应包含静态红线规则中的至少一条
        self.assertIn("Rule", result)

    def test_enhance_prompt_code_repairer(self) -> None:
        """代码修复 Agent 的 enhance_prompt 应返回非空上下文。"""
        result = self.enhancer.enhance_prompt("code_repairer", "修复 Rule 8.1 违规")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)
        self.assertIn("MISRA", result)

    def test_enhance_prompt_unknown_agent(self) -> None:
        """未知 Agent 名称也应能返回上下文（仅基于任务文本检索）。"""
        result = self.enhancer.enhance_prompt("unknown_agent", "函数声明 类型")
        self.assertIsInstance(result, str)
        # 至少应该能检索到一些规则
        if len(result) > 0:
            self.assertIn("MISRA", result)

    def test_enhance_prompt_disabled(self) -> None:
        """RAG 未启用时应返回空字符串。"""
        enhancer = RagEnhancer(self.searcher)
        enhancer.set_enabled(False)
        result = enhancer.enhance_prompt("code_generator", "实现一个函数")
        self.assertEqual(result, "")

    def test_enhance_prompt_empty_task(self) -> None:
        """空任务应仍能返回上下文（使用默认关键词）。"""
        result = self.enhancer.enhance_prompt("code_generator", "")
        self.assertIsInstance(result, str)
        # 应至少包含静态红线规则
        if len(result) > 0:
            self.assertIn("MISRA", result)

    def test_build_misra_context_with_valid_ids(self) -> None:
        """build_misra_context 用有效规则 ID 应构建上下文。"""
        result = self.enhancer.build_misra_context(["Rule 8.1", "Rule 21.3"])
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)
        self.assertIn("Rule 8.1", result)
        self.assertIn("Rule 21.3", result)

    def test_build_misra_context_with_invalid_ids(self) -> None:
        """build_misra_context 用无效规则 ID 应仍能返回上下文（含静态红线规则）。"""
        result = self.enhancer.build_misra_context(["Rule 99.99"])
        self.assertIsInstance(result, str)
        # 应至少包含静态红线规则
        self.assertGreater(len(result), 0)
        self.assertIn("MISRA", result)

    def test_build_misra_context_empty_ids(self) -> None:
        """build_misra_context 用空列表应返回空字符串。"""
        result = self.enhancer.build_misra_context([])
        self.assertEqual(result, "")

    def test_build_misra_context_disabled(self) -> None:
        """RAG 未启用时 build_misra_context 应返回空字符串。"""
        enhancer = RagEnhancer(self.searcher)
        enhancer.set_enabled(False)
        result = enhancer.build_misra_context(["Rule 8.1"])
        self.assertEqual(result, "")

    def test_build_misra_context_dedup(self) -> None:
        """build_misra_context 应去重（重复规则 ID 只出现一次）。"""
        result = self.enhancer.build_misra_context(
            ["Rule 8.1", "Rule 8.1", "Rule 21.3"]
        )
        self.assertIsInstance(result, str)
        # Rule 8.1 标题应只出现一次（在动态检索规则区）
        # 静态红线规则和动态检索规则中可能出现 Rule 8.1 一次
        # 但通过 seen_ids 去重，应只在静态红线区出现一次
        # 验证：标题不应出现两次以上
        count = result.count("### Rule 8.1")
        self.assertLessEqual(count, 1, f"Rule 8.1 出现 {count} 次，应去重为 1 次")

    def test_module_level_enhance_prompt(self) -> None:
        """模块级 enhance_prompt 函数应可调用。"""
        # 注意：模块级函数使用全局单例，RAG_ENABLED 默认为 false，
        # 因此返回空字符串是预期行为
        result = enhance_prompt("code_generator", "函数声明")
        self.assertIsInstance(result, str)

    def test_module_level_build_misra_context(self) -> None:
        """模块级 build_misra_context 函数应可调用。"""
        # 同上，RAG_ENABLED 默认为 false
        result = build_misra_context(["Rule 8.1"])
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
