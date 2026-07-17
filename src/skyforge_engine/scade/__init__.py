# SkyForge Engine: scade

"""SCADE 集成模块。

提供 Lustre 语言解析、分析和转换功能。
支持完整的 Lustre 语义，包括：
- 数据类型（int, real, bool, array, struct）
- 操作符（算术、逻辑、比较、时序）
- 节点定义（node, function, package）
- 方程（equations）
- 断言（assertions）
"""

from .lustre_parser import parse_glustre
from .lustre_ast import (
    LustreProgram, Variable, Equation, ParsedLustre,
    ast_to_parsed_lustre,
)

__all__ = [
    'parse_glustre',
    'LustreProgram',
    'Variable',
    'Equation',
    'ParsedLustre',
    'ast_to_parsed_lustre',
]
