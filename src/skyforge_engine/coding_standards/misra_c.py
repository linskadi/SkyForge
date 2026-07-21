"""MISRA-C:2012 编码标准注册。

注册规则数据、红线规则、修复函数、Mock扫描模式到编码标准注册表。
"""

from skyforge_engine.coding_standards.base import CodingStandard, get_registry
from skyforge_engine.utils.log_util import logger


def _register() -> None:
    from skyforge_engine.agents.misra_fixes import FIXERS

    standard = CodingStandard(
        standard_id="misra_c_2012",
        name="MISRA-C:2012",
        languages=["c"],
        version="2012",
        rule_data_file="skyforge_engine/rag/data/misra_rules.txt",
        red_line_rules=[
            "Rule 21.3",
            "Rule 21.6",
            "Rule 8.1",
            "Rule 8.7",
            "Rule 17.7",
            "Rule 1.3",
            "Rule 20.4",
            "Rule 8.4",
            "Rule 9.1",
            "Dir 4.1",
        ],
        agent_default_queries={
            "requirement_parser": ["需求", "可追溯性", "需求分析"],
            "contract_generator": ["契约", "前置条件", "后置条件", "断言"],
            "code_generator": ["函数声明", "类型声明", "命名规范", "static"],
            "code_repairer": ["隐式转换", "动态内存", "未初始化", "返回值"],
        },
        agent_display_names={
            "requirement_parser": "需求解析 Agent",
            "contract_generator": "契约生成 Agent",
            "code_generator": "代码生成 Agent",
            "code_repairer": "代码修复 Agent",
        },
        rule_prefix_category={
            "1": "environment",
            "2": "unused_code",
            "3": "comments",
            "4": "lexical",
            "5": "identifier",
            "6": "type",
            "7": "constant",
            "8": "declaration",
            "9": "declaration",
            "10": "expression",
            "11": "expression",
            "12": "expression",
            "13": "expression",
            "14": "control",
            "15": "control",
            "16": "control",
            "17": "declaration",
            "18": "type",
            "19": "expression",
            "20": "preprocessor",
            "21": "std_library",
            "22": "std_library",
        },
        keyword_category_map=[
            (["动态内存", "malloc", "free", "memory", "内存分配", "堆", "heap"], "memory"),
            (["类型", "typedef", "struct", "union", "enum", "bit-field", "位域", "指针"], "type"),
            (["switch", "if", "while", "for", "goto", "循环", "跳转", "分支"], "control"),
            (["表达式", "运算符", "转换", "隐式", "explicit", "cast", "副作用"], "expression"),
            (["声明", "定义", "函数", "原型", "标识符", "作用域", "参数"], "declaration"),
            (["预处理", "宏", "#define", "#include", "预编译", "macro"], "preprocessor"),
            (["标准库", "stdlib", "stdio", "string", "math", "errno", "FILE"], "std_library"),
        ],
        fixers=FIXERS,
        mock_scan_patterns=[
            {
                "pattern": r"\b(malloc|calloc|realloc)\s*\(",
                "rule_id": "misra-c2012-20.4",
                "severity": "error",
                "message": "动态内存分配不被允许（Rule 20.4）",
            },
            {
                "pattern": r"^(void|int|double|float|char|short|long|unsigned)\s+\w+\s*=\s*.+;",
                "rule_id": "misra-c2012-8.7",
                "severity": "style",
                "message": "外部变量应定义为 static（Rule 8.7）",
                "exclude_starts": ["static", "extern"],
            },
            {
                "pattern": r"^(\w+)\s*\(([^)]*)\)\s*;\s*$",
                "rule_id": "misra-c2012-17.7",
                "severity": "style",
                "message": "函数返回值未被使用（Rule 17.7）",
                "exclude_names": ["if", "while", "for", "switch", "return", "sizeof"],
                "exclude_contains": ["= ", "{"],
            },
            {
                "pattern": r"^(void|int|double|float|char|short|long|unsigned)\s+\w+\s*\([^)]*\)\s*\{",
                "rule_id": "misra-c2012-8.1",
                "severity": "style",
                "message": "函数需要类型声明/原型（Rule 8.1）",
            },
            {
                "pattern": r"\(\w+\s*\*\)\s*\w+",
                "rule_id": "misra-c2012-11.3",
                "severity": "error",
                "message": "不同类型指针间转换需要显式强制类型转换（Rule 11.3）",
            },
            {
                "pattern": r"\w+\s*\+\s*\w+\s*<<\s*\w+",
                "rule_id": "misra-c2012-12.1",
                "severity": "style",
                "message": "运算符优先级需要括号明确（Rule 12.1）",
            },
            {
                "pattern": r"\w+\s*\|\s*\w+\s*\&\s*\w+",
                "rule_id": "misra-c2012-12.1",
                "severity": "style",
                "message": "运算符优先级需要括号明确（Rule 12.1）",
            },
            {
                "pattern": r"\b(printf|fprintf|scanf|fscanf)\s*\(",
                "rule_id": "misra-c2012-21.6",
                "severity": "error",
                "message": "标准库 I/O 函数在嵌入式系统中不允许使用（Rule 21.6）",
            },
        ],
        priority=100,
    )

    get_registry().register(standard)
    logger.info("MISRA-C:2012 编码标准已注册")


_register()
