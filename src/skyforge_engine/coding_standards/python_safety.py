"""Python 军工软件编程安全规范编码标准注册。

基于《军工软件Python语言编程指南》T/ZASDI 0002-2023。
"""

from skyforge_engine.coding_standards.base import CodingStandard, get_registry
from skyforge_engine.utils.log_util import logger


def _register() -> None:
    from skyforge_engine.agents.python_fixes import PYTHON_FIXERS

    standard = CodingStandard(
        standard_id="python_safety",
        name="军工软件Python编程规范 (T/ZASDI 0002-2023)",
        languages=["python"],
        version="2023",
        rule_data_file="skyforge_engine/rag/data/python_safety_rules.txt",
        red_line_rules=[
            "P-01",
            "P-02",
            "T-01",
        ],
        agent_default_queries={
            "requirement_parser": ["需求", "可追溯性"],
            "contract_generator": ["契约", "类型标注", "前置条件"],
            "code_generator": ["类型标注", "命名规范", "模块结构"],
            "code_repairer": ["类型标注", "eval/exec", "全局变量"],
        },
        agent_display_names={
            "requirement_parser": "需求解析 Agent",
            "contract_generator": "契约生成 Agent",
            "code_generator": "代码生成 Agent",
            "code_repairer": "代码修复 Agent",
        },
        rule_prefix_category={},
        keyword_category_map=[
            (["eval", "exec", "compile", "动态执行"], "security"),
            (["global", "nonlocal", "全局状态"], "encapsulation"),
            (["类型标注", "type hint", "typing", "->"], "typing"),
            (["命名", "snake_case", "CamelCase", "UPPER_CASE"], "naming"),
            (["导入", "import", "from", "__init__"], "module"),
        ],
        fixers=PYTHON_FIXERS,
        mock_scan_patterns=[
            {
                "pattern": r"\beval\s*\(",
                "rule_id": "python-P-01",
                "severity": "error",
                "message": "禁止使用 eval（P-01）",
            },
            {
                "pattern": r"\bexec\s*\(",
                "rule_id": "python-P-01",
                "severity": "error",
                "message": "禁止使用 exec（P-01）",
            },
            {
                "pattern": r"\bglobal\s+\w+",
                "rule_id": "python-P-02",
                "severity": "warning",
                "message": "禁止使用 global 声明（P-02）",
            },
            {
                "pattern": r"\bnonlocal\s+\w+",
                "rule_id": "python-P-02",
                "severity": "warning",
                "message": "禁止使用 nonlocal 声明（P-02）",
            },
        ],
        priority=50,
    )

    get_registry().register(standard)
    logger.info("Python 军工软件编程安全规范已注册")


_register()
