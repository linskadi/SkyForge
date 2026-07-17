"""Lustre AST 节点定义。

定义 Lustre 语言的抽象语法树（AST）节点类型，用于替代正则表达式解析。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# ==================== 枚举类型 ====================

class LustreType(Enum):
    """Lustre 基础数据类型。"""
    INT = auto()
    REAL = auto()
    BOOL = auto()
    FLOAT = auto()
    DOUBLE = auto()
    INT8 = auto()
    UINT8 = auto()
    INT16 = auto()
    UINT16 = auto()
    INT32 = auto()
    UINT32 = auto()
    ARRAY = auto()
    STRUCT = auto()
    NAMED = auto()


class BinOp(Enum):
    """二元运算符。"""
    ADD = '+'
    SUB = '-'
    MUL = '*'
    DIV = '/'
    MOD = 'mod'
    REM = 'rem'
    POW = '^'
    EQ = '='
    NEQ = '<>'
    LT = '<'
    GT = '>'
    LTE = '<='
    GTE = '>='
    AND = 'and'
    OR = 'or'


class UnaryOp(Enum):
    """一元运算符。"""
    NEG = '-'
    PRE = 'pre'
    NOT = 'not'
    ABS = 'abs'


# ==================== AST 节点 ====================

@dataclass
class ASTNode:
    """AST 节点基类。"""
    line: int = 0
    column: int = 0


@dataclass
class TypeNode(ASTNode):
    """类型节点基类。"""
    pass


@dataclass
class NamedTypeNode(TypeNode):
    """命名类型（如用户定义的类型名）。"""
    name: str = ""


@dataclass
class PrimitiveTypeNode(TypeNode):
    """基础类型节点。"""
    type: LustreType = LustreType.INT


@dataclass
class ArrayTypeNode(TypeNode):
    """数组类型节点。"""
    size: int = 0
    element_type: TypeNode = field(default_factory=PrimitiveTypeNode)


@dataclass
class StructTypeNode(TypeNode):
    """结构体类型节点。"""
    fields: list[StructFieldNode] = field(default_factory=list)


@dataclass
class StructFieldNode(ASTNode):
    """结构体字段。"""
    name: str = ""
    type: TypeNode = field(default_factory=PrimitiveTypeNode)


# ==================== 变量声明 ====================

@dataclass
class VariableNode(ASTNode):
    """变量声明节点。"""
    names: list[str] = field(default_factory=list)
    type: TypeNode = field(default_factory=PrimitiveTypeNode)


@dataclass
class ParamNode(ASTNode):
    """参数声明节点。"""
    names: list[str] = field(default_factory=list)
    type: TypeNode = field(default_factory=PrimitiveTypeNode)


# ==================== 表达式 ====================

@dataclass
class ExprNode(ASTNode):
    """表达式节点基类。"""
    pass


@dataclass
class IntLiteralNode(ExprNode):
    """整数字面量。"""
    value: int = 0


@dataclass
class FloatLiteralNode(ExprNode):
    """浮点字面量。"""
    value: float = 0.0


@dataclass
class BoolLiteralNode(ExprNode):
    """布尔字面量。"""
    value: bool = False


@dataclass
class IdentifierNode(ExprNode):
    """标识符节点。"""
    name: str = ""


@dataclass
class BinaryOpNode(ExprNode):
    """二元运算节点。"""
    op: BinOp = BinOp.ADD
    left: ExprNode = field(default_factory=IdentifierNode)
    right: ExprNode = field(default_factory=IdentifierNode)


@dataclass
class UnaryOpNode(ExprNode):
    """一元运算节点。"""
    op: UnaryOp = UnaryOp.NEG
    operand: ExprNode = field(default_factory=IdentifierNode)


@dataclass
class PreNode(ExprNode):
    """前一个值操作符 (pre)。"""
    operand: ExprNode = field(default_factory=IdentifierNode)


@dataclass
class ArrowNode(ExprNode):
    """箭头操作符 (->)，表示初始值。"""
    initial: ExprNode = field(default_factory=IdentifierNode)
    current: ExprNode = field(default_factory=IdentifierNode)


@dataclass
class IfThenElseNode(ExprNode):
    """if-then-else 表达式。"""
    condition: ExprNode = field(default_factory=IdentifierNode)
    then_expr: ExprNode = field(default_factory=IdentifierNode)
    else_expr: ExprNode = field(default_factory=IdentifierNode)


@dataclass
class ArrayLiteralNode(ExprNode):
    """数组字面量。"""
    elements: list[ExprNode] = field(default_factory=list)


@dataclass
class ArrayAccessNode(ExprNode):
    """数组访问。"""
    array: ExprNode = field(default_factory=IdentifierNode)
    index: ExprNode = field(default_factory=IntLiteralNode)


@dataclass
class FieldAccessNode(ExprNode):
    """字段访问。"""
    record: ExprNode = field(default_factory=IdentifierNode)
    field: str = ""


@dataclass
class FunctionCallNode(ExprNode):
    """函数调用。"""
    name: str = ""
    args: list[ExprNode] = field(default_factory=list)


@dataclass
class MergeNode(ExprNode):
    """merge 操作符。"""
    clock: str = ""
    true_expr: ExprNode = field(default_factory=IdentifierNode)
    false_expr: ExprNode = field(default_factory=IdentifierNode)


@dataclass
class FbyNode(ExprNode):
    """fby 操作符（followed by）。"""
    initial: ExprNode = field(default_factory=IdentifierNode)
    count: int = 0


@dataclass
class WhenNode(ExprNode):
    """when 操作符。"""
    expr: ExprNode = field(default_factory=IdentifierNode)
    clock: ExprNode = field(default_factory=IdentifierNode)


@dataclass
class CurrentNode(ExprNode):
    """current 操作符。"""
    operand: ExprNode = field(default_factory=IdentifierNode)


@dataclass
class LastNode(ExprNode):
    """last 操作符。"""
    operand: ExprNode = field(default_factory=IdentifierNode)


@dataclass
class NorNode(ExprNode):
    """nor 操作符。"""
    operands: list[ExprNode] = field(default_factory=list)


@dataclass
class ConversionNode(ExprNode):
    """类型转换函数。"""
    func: str = ""  # bool_to_int, int_to_real, real_to_int
    operand: ExprNode = field(default_factory=IdentifierNode)


# ==================== 语句 ====================

@dataclass
class EquationNode(ASTNode):
    """等式节点。"""
    lhs: list[str] = field(default_factory=list)
    rhs: ExprNode = field(default_factory=IdentifierNode)


@dataclass
class AssertNode(ASTNode):
    """断言节点。"""
    expr: ExprNode = field(default_factory=IdentifierNode)


# ==================== 定义 ====================

@dataclass
class NodeDecl(ASTNode):
    """节点声明。"""
    name: str = ""
    inputs: list[ParamNode] = field(default_factory=list)
    outputs: list[ParamNode] = field(default_factory=list)
    locals: list[VariableNode] = field(default_factory=list)
    equations: list[EquationNode] = field(default_factory=list)


@dataclass
class FunctionDecl(ASTNode):
    """函数声明。"""
    name: str = ""
    inputs: list[ParamNode] = field(default_factory=list)
    outputs: list[ParamNode] = field(default_factory=list)
    locals: list[VariableNode] = field(default_factory=list)
    equations: list[EquationNode] = field(default_factory=list)


@dataclass
class StructDecl(ASTNode):
    """结构体声明。"""
    name: str = ""
    fields: list[StructFieldNode] = field(default_factory=list)


@dataclass
class ConstDecl(ASTNode):
    """常量声明。"""
    name: str = ""
    type: TypeNode = field(default_factory=PrimitiveTypeNode)
    value: ExprNode = field(default_factory=IntLiteralNode)


@dataclass
class TypeAliasDecl(ASTNode):
    """类型别名声明。"""
    name: str = ""
    type: TypeNode = field(default_factory=PrimitiveTypeNode)


@dataclass
class ImportDecl(ASTNode):
    """导入声明。"""
    path: list[str] = field(default_factory=list)


@dataclass
class PackageDecl(ASTNode):
    """包声明。"""
    name: str = ""


# ==================== 程序 ====================

@dataclass
class LustreProgram(ASTNode):
    """Lustre 程序根节点。"""
    packages: list[PackageDecl] = field(default_factory=list)
    imports: list[ImportDecl] = field(default_factory=list)
    declarations: list[ASTNode] = field(default_factory=list)


# ==================== 向后兼容的转换类型 ====================

@dataclass
class Variable:
    """向后兼容的变量定义。

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
    """向后兼容的等式定义。"""
    output: str
    expression: str


@dataclass
class ParsedLustre:
    """向后兼容的解析结果。

    Attributes:
        node_name: 节点名。
        inputs: 输入变量列表。
        outputs: 输出变量列表。
        locals: 局部变量列表。
        equations: 等式列表（output = expression）。
        raw_content: 原始 Lustre 文本。
    """
    node_name: str = ""
    inputs: list[Variable] = field(default_factory=list)
    outputs: list[Variable] = field(default_factory=list)
    locals: list[Variable] = field(default_factory=list)
    equations: list[Equation] = field(default_factory=list)
    raw_content: str = ""


def _type_to_string(type_node: TypeNode) -> str:
    """将类型节点转换为字符串表示。"""
    if isinstance(type_node, PrimitiveTypeNode):
        return type_node.type.name.lower()
    elif isinstance(type_node, NamedTypeNode):
        return type_node.name
    elif isinstance(type_node, ArrayTypeNode):
        return f"array[{type_node.size}] of {_type_to_string(type_node.element_type)}"
    elif isinstance(type_node, StructTypeNode):
        fields = ", ".join(f"{f.name}: {_type_to_string(f.type)}" for f in type_node.fields)
        return f"struct {{ {fields} }}"
    return "unknown"


def ast_to_parsed_lustre(program: LustreProgram, raw_content: str = "") -> ParsedLustre:
    """将 AST 转换为向后兼容的 ParsedLustre 格式。

    Args:
        program: Lustre AST 程序节点。
        raw_content: 原始 Lustre 文本。

    Returns:
        向后兼容的 ParsedLustre 解析结果。
    """
    # 查找第一个节点声明
    for decl in program.declarations:
        if isinstance(decl, NodeDecl):
            inputs = []
            for param in decl.inputs:
                type_str = _type_to_string(param.type)
                for name in param.names:
                    inputs.append(Variable(name=name, type=type_str))

            outputs = []
            for param in decl.outputs:
                type_str = _type_to_string(param.type)
                for name in param.names:
                    outputs.append(Variable(name=name, type=type_str))

            locals_list = []
            for var in decl.locals:
                type_str = _type_to_string(var.type)
                for name in var.names:
                    locals_list.append(Variable(name=name, type=type_str))

            equations = []
            for eq in decl.equations:
                for name in eq.lhs:
                    # 简单地将表达式转换为字符串
                    eq_str = _expr_to_string(eq.rhs)
                    equations.append(Equation(output=name, expression=eq_str))

            return ParsedLustre(
                node_name=decl.name,
                inputs=inputs,
                outputs=outputs,
                locals=locals_list,
                equations=equations,
                raw_content=raw_content,
            )

    return ParsedLustre(raw_content=raw_content)


def _expr_to_string(expr: ExprNode) -> str:
    """将表达式节点转换为字符串表示。"""
    if isinstance(expr, IntLiteralNode):
        return str(expr.value)
    elif isinstance(expr, FloatLiteralNode):
        return str(expr.value)
    elif isinstance(expr, BoolLiteralNode):
        return "true" if expr.value else "false"
    elif isinstance(expr, IdentifierNode):
        return expr.name
    elif isinstance(expr, BinaryOpNode):
        left = _expr_to_string(expr.left)
        right = _expr_to_string(expr.right)
        return f"({left} {expr.op.value} {right})"
    elif isinstance(expr, UnaryOpNode):
        operand = _expr_to_string(expr.operand)
        if expr.op == UnaryOp.PRE:
            return f"pre {operand}"
        elif expr.op == UnaryOp.NOT:
            return f"not {operand}"
        elif expr.op == UnaryOp.NEG:
            return f"-{operand}"
        elif expr.op == UnaryOp.ABS:
            return f"abs({operand})"
    elif isinstance(expr, PreNode):
        operand = _expr_to_string(expr.operand)
        return f"pre {operand}"
    elif isinstance(expr, ArrowNode):
        initial = _expr_to_string(expr.initial)
        current = _expr_to_string(expr.current)
        return f"({initial} -> {current})"
    elif isinstance(expr, IfThenElseNode):
        cond = _expr_to_string(expr.condition)
        then_expr = _expr_to_string(expr.then_expr)
        else_expr = _expr_to_string(expr.else_expr)
        return f"if {cond} then {then_expr} else {else_expr}"
    elif isinstance(expr, FunctionCallNode):
        args = ", ".join(_expr_to_string(arg) for arg in expr.args)
        return f"{expr.name}({args})"
    elif isinstance(expr, ArrayLiteralNode):
        elements = ", ".join(_expr_to_string(e) for e in expr.elements)
        return f"[{elements}]"
    elif isinstance(expr, ArrayAccessNode):
        array = _expr_to_string(expr.array)
        index = _expr_to_string(expr.index)
        return f"{array}[{index}]"
    elif isinstance(expr, FieldAccessNode):
        record = _expr_to_string(expr.record)
        return f"{record}.{expr.field}"
    elif isinstance(expr, MergeNode):
        true_expr = _expr_to_string(expr.true_expr)
        false_expr = _expr_to_string(expr.false_expr)
        return f"merge {expr.clock}({true_expr}, {false_expr})"
    elif isinstance(expr, FbyNode):
        initial = _expr_to_string(expr.initial)
        return f"fby({initial}, {expr.count})"
    elif isinstance(expr, WhenNode):
        inner = _expr_to_string(expr.expr)
        clock = _expr_to_string(expr.clock)
        return f"{inner} when {clock}"
    elif isinstance(expr, CurrentNode):
        inner = _expr_to_string(expr.operand)
        return f"current {inner}"
    elif isinstance(expr, LastNode):
        inner = _expr_to_string(expr.operand)
        return f"last {inner}"
    elif isinstance(expr, NorNode):
        operands = ", ".join(_expr_to_string(o) for o in expr.operands)
        return f"nor({operands})"
    elif isinstance(expr, ConversionNode):
        inner = _expr_to_string(expr.operand)
        return f"{expr.func}({inner})"

    return "unknown"
