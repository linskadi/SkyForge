"""MISRA-C++ / JSF AV C++ / CERT C++ 编码标准注册。

注册规则数据、红线规则、Mock扫描模式到编码标准注册表。
"""

from skyforge_engine.coding_standards.base import CodingStandard, get_registry
from skyforge_engine.utils.log_util import logger


def _register() -> None:
    from skyforge_engine.agents.misra_cpp_fixes import CPP_FIXERS

    standard = CodingStandard(
        standard_id="jsf_av_cpp",
        name="MISRA-C++/JSF AV C++/CERT C++",
        languages=["cpp"],
        version="1.0",
        rule_data_file="skyforge_engine/rag/data/misra_cpp_rules.txt",
        red_line_rules=[
            "Rule 18-4-1",
            "Rule 3-1-1",
            "Rule 5-2-1",
            "Rule 6-6-1",
            "Rule 12-1-2",
        ],
        agent_default_queries={
            "requirement_parser": ["需求", "可追溯性", "需求分析"],
            "contract_generator": ["契约", "前置条件", "后置条件", "断言"],
            "code_generator": ["类设计", "继承", "模板", "命名空间", "RAII"],
            "code_repairer": ["类型安全", "资源泄漏", "空指针", "异常安全"],
        },
        agent_display_names={
            "requirement_parser": "需求解析 Agent",
            "contract_generator": "契约生成 Agent",
            "code_generator": "代码生成 Agent",
            "code_repairer": "代码修复 Agent",
        },
        rule_prefix_category={},
        keyword_category_map=[
            (["继承", "虚函数", "多态", "override", "纯虚"], "class_design"),
            (["模板", "template", "泛型", "特化"], "templates"),
            (["异常", "exception", "try", "catch", "throw", "noexcept"], "exceptions"),
            (["内存", "new", "delete", "智能指针", "unique_ptr", "shared_ptr"], "memory"),
            (["类型安全", "static_cast", "dynamic_cast", "reinterpret_cast", "const_cast"], "type_safety"),
            (["命名空间", "namespace", "using", "ADL"], "namespaces"),
            (["RAII", "资源", "文件", "锁", "mutex"], "resource_management"),
        ],
        fixers=CPP_FIXERS,
        mock_scan_patterns=[
            {
                "pattern": r"\bnew\s+\w+[\[\(]",
                "rule_id": "jsf-av-cpp-18-4-1",
                "severity": "error",
                "message": "禁止使用 new/delete，应使用智能指针（Rule 18-4-1）",
            },
            {
                "pattern": r"\bdelete\s+",
                "rule_id": "jsf-av-cpp-18-4-1",
                "severity": "error",
                "message": "禁止使用 new/delete，应使用智能指针（Rule 18-4-1）",
            },
            {
                "pattern": r"\bmalloc\s*\(",
                "rule_id": "jsf-av-cpp-18-4-1",
                "severity": "error",
                "message": "禁止使用 malloc/free（Rule 18-4-1）",
            },
            {
                "pattern": r"\bgoto\s+",
                "rule_id": "jsf-av-cpp-6-6-1",
                "severity": "error",
                "message": "禁止使用 goto（Rule 6-6-1）",
            },
        ],
        priority=50,
    )

    get_registry().register(standard)
    logger.info("MISRA-C++/JSF AV C++ 编码标准已注册")


_register()
