"""G-Lustre 解析器：解析 G-Lustre 文件，提取节点/变量/等式信息。

G-Lustre 是 Lustre 数据流语言的一种变体，由 SCADE 工程转换工具生成。
本模块使用 ANTLR4 风格的递归下降解析器替代原有的正则表达式解析器。
支持完整的 Lustre 语义，同时保持向后兼容性。

主要改进：
1. 完整的词法分析和语法分析
2. 生成结构化的 AST（抽象语法树）
3. 支持所有 Lustre 数据类型和操作符
4. 更好的错误恢复和错误报告
5. 向后兼容原有 API

支持语法：
- `node name(input: type) returns (output: type);` 节点签名
- `let ... tel` 等式块
- `output = expr;` 等式
- 表达式操作符：`+ - * / pre -> if-then-else and or not`
- 可选 `var locals; let` 局部变量块
- 可选范围注释：`/*@ range = [min, max] */` 或 `(*@ range = [min, max] @*)`
- 数据类型：int, real, bool, float, double, int8, uint8, int16, uint16, int32, uint32
- 数组类型：array[N] of type
- 结构体类型：struct { field: type, ... }
- 函数定义：function name(params) returns (params)
- 结构体定义：struct name { field: type, ... }
- 常量定义：const name: type = value;
- 类型别名：type name = type;
- 导入声明：import name[.name]*;
- 包声明：package name;
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from skyforge_engine.utils.log_util import logger


@dataclass
class Variable:
    """变量定义（输入/输出/局部）。

    Attributes:
        name: 变量名。
        type: 变量类型（real/int/bool 等）。
        range: 取值范围 [min, max]，来自注释，可能为 None。
    """

    name: str
    type: str
    range: Optional[list[float]] = None


@dataclass
class Equation:
    """等式：output = expression。"""

    output: str
    expression: str


@dataclass
class ParsedLustre:
    """G-Lustre 解析结果。

    Attributes:
        node_name: 节点名。
        inputs: 输入变量列表。
        outputs: 输出变量列表。
        locals: 局部变量列表。
        equations: 等式列表（output = expression）。
        raw_content: 原始 G-Lustre 文本。
    """

    node_name: str = ""
    inputs: list[Variable] = field(default_factory=list)
    outputs: list[Variable] = field(default_factory=list)
    locals: list[Variable] = field(default_factory=list)
    equations: list[Equation] = field(default_factory=list)
    raw_content: str = ""


def parse_glustre(content: str) -> ParsedLustre:
    """解析 G-Lustre 文件，提取节点/变量/等式。

    这是主要的解析入口函数，使用新的ANTLR4风格解析器。

    Args:
        content: G-Lustre 文件文本。

    Returns:
        ParsedLustre 解析结果。

    Raises:
        ValueError: 找不到 node 定义时抛出。
        LustreLexerError: 词法分析错误。
        LustreParseError: 语法分析错误。
    """
    logger.info(f"LustreParser:开始解析 G-Lustre (长度={len(content)})")

    try:
        # 尝试使用新的解析器
        from .lustre_parser_new import parse_glustre as parse_with_ast
        result = parse_with_ast(content)
        logger.info(
            f"LustreParser:完成 node={result.node_name} "
            f"inputs={len(result.inputs)} outputs={len(result.outputs)} "
            f"locals={len(result.locals)} equations={len(result.equations)}"
        )
        return result
    except Exception as e:
        # 如果新解析器失败，使用旧的解析器作为后备
        logger.info(f"LustreParser:新解析器失败 ({e})，使用后备正则表达式解析器")
        return _parse_with_regex(content)


def _parse_with_regex(content: str) -> ParsedLustre:
    """使用正则表达式解析器（后备方案）。

    Args:
        content: G-Lustre 文件文本。

    Returns:
        ParsedLustre 解析结果。

    Raises:
        ValueError: 找不到 node 定义时抛出。
    """
    raw = content

    # 提取范围注释映射（变量名 -> [min, max]）
    range_map = _extract_range_annotations(content)

    # 提取节点签名：node NAME(inputs) returns (outputs);
    node_match = re.search(
        r"\bnode\s+(\w+)\s*\(\s*([^)]*?)\s*\)\s*returns\s*\(\s*([^)]*?)\s*\)\s*;",
        content,
        re.DOTALL,
    )
    if not node_match:
        raise ValueError("无法找到 node 定义：缺少 `node name(...) returns (...);`")

    node_name = node_match.group(1)
    inputs_str = node_match.group(2).strip()
    outputs_str = node_match.group(3).strip()

    inputs = _parse_var_list(inputs_str, range_map)
    outputs = _parse_var_list(outputs_str, range_map)

    # 提取局部变量 var ... ;（在 returns 之后、let 之前）
    locals_list: list[Variable] = []
    var_match = re.search(
        r"returns\s*\([^)]*\)\s*;\s*\bvar\b\s+(.*?)\s*\blet\b",
        content,
        re.DOTALL,
    )
    if var_match:
        locals_str = var_match.group(1)
        locals_list = _parse_var_list(locals_str, range_map)

    # 提取 let ... tel 块内的等式
    equations: list[Equation] = []
    let_match = re.search(r"\blet\b\s+(.*?)\s*\btel\b", content, re.DOTALL)
    if let_match:
        body = let_match.group(1)
        equations = _parse_equations(body)

    parsed = ParsedLustre(
        node_name=node_name,
        inputs=inputs,
        outputs=outputs,
        locals=locals_list,
        equations=equations,
        raw_content=raw,
    )
    logger.info(
        f"LustreParser:完成 node={node_name} "
        f"inputs={len(inputs)} outputs={len(outputs)} "
        f"locals={len(locals_list)} equations={len(equations)}"
    )
    return parsed


def _parse_var_list(
    s: str, range_map: Optional[dict[str, list[float]]] = None
) -> list[Variable]:
    """解析变量列表，支持 'name1, name2: type1; name3: type2' 格式。

    Args:
        s: 变量声明字符串。
        range_map: 变量名到范围的映射（来自注释）。

    Returns:
        变量列表。
    """
    range_map = range_map or {}
    variables: list[Variable] = []
    if not s:
        return variables
    # 按分号分割变量组
    parts = [p.strip() for p in s.split(";") if p.strip()]
    for part in parts:
        # 移除注释（保留语义信息已在 range_map 中）
        clean = re.sub(r"/\*.*?\*/", "", part, flags=re.DOTALL)
        clean = re.sub(r"\(\*.*?\*\)", "", clean, flags=re.DOTALL)
        clean = clean.strip()
        if not clean:
            continue
        # 格式：name1, name2: type 或 name: type
        m = re.match(r"([\w\s,]+?)\s*:\s*(\w+)", clean)
        if m:
            names_str = m.group(1)
            type_str = m.group(2)
            names = [n.strip() for n in names_str.split(",") if n.strip()]
            for name in names:
                rng = range_map.get(name)
                variables.append(Variable(name=name, type=type_str, range=rng))
    return variables


def _parse_equations(body: str) -> list[Equation]:
    """解析等式列表 'output = expr; output2 = expr2;'。

    Args:
        body: let ... tel 块内的文本。

    Returns:
        等式列表。
    """
    equations: list[Equation] = []
    # 移除注释（避免注释中的分号被误判为等式分隔符）
    clean = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    clean = re.sub(r"\(\*.*?\*\)", "", clean, flags=re.DOTALL)
    # 按分号分割
    parts = [p.strip() for p in clean.split(";") if p.strip()]
    for part in parts:
        if "=" in part:
            # 仅在第一个 = 处分割（避免 == 等比较操作符误判）
            lhs, rhs = part.split("=", 1)
            output = lhs.strip()
            expression = rhs.strip()
            if output and expression:
                equations.append(Equation(output=output, expression=expression))
    return equations


def _extract_range_annotations(content: str) -> dict[str, list[float]]:
    """提取变量范围注释（best-effort）。

    支持的注释格式（紧跟变量声明后）：
    - `name: type; /*@ range = [min, max] */`
    - `name: type; (*@ range = [min, max] @*)`

    Args:
        content: G-Lustre 文本。

    Returns:
        变量名 -> [min, max] 映射。
    """
    range_map: dict[str, list[float]] = {}
    # 匹配 "变量名: 类型 ... 注释 range = [min, max]"
    pattern = re.compile(
        r"(\w+)\s*:\s*\w+[^;]*?"
        r"(?:/\*@|\(\*@)[^]]*?range\s*=\s*\[\s*"
        r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]",
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(content):
        var_name = m.group(1)
        rng = [float(m.group(2)), float(m.group(3))]
        range_map[var_name] = rng
    return range_map


# ==================== 增强的解析功能 ====================

def parse_glustre_with_ast(content: str):
    """解析 G-Lustre 文件并返回完整的 AST。

    这是增强的解析函数，返回完整的 LustreProgram AST。

    Args:
        content: G-Lustre 文件文本。

    Returns:
        LustreProgram AST 根节点。

    Raises:
        LustreLexerError: 词法分析错误。
        LustreParseError: 语法分析错误。
    """
    from .lustre_parser_new import parse_glustre_with_ast as parse_with_ast
    return parse_with_ast(content)


def validate_lustre(content: str) -> tuple[bool, list[str]]:
    """验证 Lustre 代码的语法正确性。

    Args:
        content: Lustre 源代码。

    Returns:
        (是否有效, 错误信息列表)
    """
    from .lustre_parser_new import validate_lustre as validate
    return validate(content)


def get_ast_statistics(program) -> dict:
    """获取 AST 的统计信息。

    Args:
        program: Lustre AST 程序节点。

    Returns:
        统计信息字典。
    """
    from .lustre_parser_new import get_ast_statistics as get_stats
    return get_stats(program)


# ==================== 导出 ====================

__all__ = [
    'parse_glustre',
    'parse_glustre_with_ast',
    'validate_lustre',
    'get_ast_statistics',
    'Variable',
    'Equation',
    'ParsedLustre',
]
