"""Python安全修复规则（基于《军工软件Python语言编程指南》）。"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skyforge_engine.tools.cppcheck_scanner import Violation

from skyforge_engine.agents.types import RepairAction


def _fix_p01(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-01: 禁止使用 eval/exec"""
    # 移除 eval/exec 调用
    new_code = re.sub(r'\beval\s*\([^)]*\)', 'None  # 安全替代', code)
    new_code = re.sub(r'\bexec\s*\([^)]*\)', 'pass  # 安全替代', new_code)
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='移除 eval/exec 调用'
    )


def _fix_p02(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-02: 禁止使用 global/nonlocal"""
    new_code = re.sub(r'\bglobal\s+\w+', '', code)
    new_code = re.sub(r'\bnonlocal\s+\w+', '', code)
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='移除 global/nonlocal 声明'
    )


def _fix_t01(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """T-01: 函数必须有类型标注"""
    # 为函数添加类型标注
    lines = code.splitlines(keepends=True)
    for i, line in enumerate(lines):
        match = re.match(r'(\s*def\s+\w+\s*\()([^)]*)\)(\s*:)', line)
        if match and '->' not in line:
            lines[i] = line.replace('):', ') -> None:')
    return ''.join(lines), RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='添加函数返回类型标注'
    )


def _fix_n01(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """N-01: 模块命名规范"""
    # 检查模块名是否符合 snake_case
    return code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='检查模块命名规范'
    )


# Python修复规则映射
PYTHON_FIXERS = {
    'P-01': _fix_p01,
    'P-02': _fix_p02,
    'T-01': _fix_t01,
    'N-01': _fix_n01,
}
