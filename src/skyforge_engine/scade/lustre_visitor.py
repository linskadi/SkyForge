"""Lustre AST 访问者。

提供 AST 遍历和访问功能，支持代码生成、分析等操作。
"""

from __future__ import annotations

from abc import ABC
from .lustre_ast import (
    ASTNode, LustreProgram, PackageDecl, ImportDecl,
    NodeDecl, FunctionDecl, StructDecl, ConstDecl, TypeAliasDecl,
    ParamNode, VariableNode, StructFieldNode,
    TypeNode, PrimitiveTypeNode, NamedTypeNode, ArrayTypeNode, StructTypeNode,
    IntLiteralNode, FloatLiteralNode, BoolLiteralNode, IdentifierNode,
    BinaryOpNode, UnaryOpNode, PreNode, ArrowNode, IfThenElseNode,
    ArrayLiteralNode, ArrayAccessNode, FieldAccessNode, FunctionCallNode,
    MergeNode, FbyNode, WhenNode, CurrentNode, LastNode, NorNode, ConversionNode,
    EquationNode, AssertNode,
)


class LustreVisitor(ABC):
    """Lustre AST 访问者基类。"""

    def visit(self, node: ASTNode):
        """访问节点分发方法。"""
        method_name = f'visit_{type(node).__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ASTNode):
        """默认访问方法。"""
        raise NotImplementedError(f"No visit method for {type(node).__name__}")

    # ==================== 程序 ====================

    def visit_LustreProgram(self, node: LustreProgram):
        """访问程序节点。"""
        for pkg in node.packages:
            self.visit(pkg)
        for imp in node.imports:
            self.visit(imp)
        for decl in node.declarations:
            self.visit(decl)

    def visit_PackageDecl(self, node: PackageDecl):
        """访问包声明。"""
        pass

    def visit_ImportDecl(self, node: ImportDecl):
        """访问导入声明。"""
        pass

    # ==================== 定义 ====================

    def visit_NodeDecl(self, node: NodeDecl):
        """访问节点声明。"""
        for param in node.inputs:
            self.visit(param)
        for param in node.outputs:
            self.visit(param)
        for var in node.locals:
            self.visit(var)
        for eq in node.equations:
            self.visit(eq)

    def visit_FunctionDecl(self, node: FunctionDecl):
        """访问函数声明。"""
        for param in node.inputs:
            self.visit(param)
        for param in node.outputs:
            self.visit(param)
        for var in node.locals:
            self.visit(var)
        for eq in node.equations:
            self.visit(eq)

    def visit_StructDecl(self, node: StructDecl):
        """访问结构体声明。"""
        for field in node.fields:
            self.visit(field)

    def visit_ConstDecl(self, node: ConstDecl):
        """访问常量声明。"""
        self.visit(node.type)
        self.visit(node.value)

    def visit_TypeAliasDecl(self, node: TypeAliasDecl):
        """访问类型别名声明。"""
        self.visit(node.type)

    # ==================== 参数和变量 ====================

    def visit_ParamNode(self, node: ParamNode):
        """访问参数节点。"""
        self.visit(node.type)

    def visit_VariableNode(self, node: VariableNode):
        """访问变量节点。"""
        self.visit(node.type)

    def visit_StructFieldNode(self, node: StructFieldNode):
        """访问结构体字段节点。"""
        self.visit(node.type)

    # ==================== 类型 ====================

    def visit_TypeNode(self, node: TypeNode):
        """访问类型节点。"""
        pass

    def visit_PrimitiveTypeNode(self, node: PrimitiveTypeNode):
        """访问基础类型节点。"""
        pass

    def visit_NamedTypeNode(self, node: NamedTypeNode):
        """访问命名类型节点。"""
        pass

    def visit_ArrayTypeNode(self, node: ArrayTypeNode):
        """访问数组类型节点。"""
        self.visit(node.element_type)

    def visit_StructTypeNode(self, node: StructTypeNode):
        """访问结构体类型节点。"""
        for field in node.fields:
            self.visit(field)

    # ==================== 语句 ====================

    def visit_EquationNode(self, node: EquationNode):
        """访问等式节点。"""
        self.visit(node.rhs)

    def visit_AssertNode(self, node: AssertNode):
        """访问断言节点。"""
        self.visit(node.expr)

    # ==================== 表达式 ====================

    def visit_IntLiteralNode(self, node: IntLiteralNode):
        """访问整数字面量。"""
        pass

    def visit_FloatLiteralNode(self, node: FloatLiteralNode):
        """访问浮点字面量。"""
        pass

    def visit_BoolLiteralNode(self, node: BoolLiteralNode):
        """访问布尔字面量。"""
        pass

    def visit_IdentifierNode(self, node: IdentifierNode):
        """访问标识符节点。"""
        pass

    def visit_BinaryOpNode(self, node: BinaryOpNode):
        """访问二元运算节点。"""
        self.visit(node.left)
        self.visit(node.right)

    def visit_UnaryOpNode(self, node: UnaryOpNode):
        """访问一元运算节点。"""
        self.visit(node.operand)

    def visit_PreNode(self, node: PreNode):
        """访问 pre 操作符节点。"""
        self.visit(node.operand)

    def visit_ArrowNode(self, node: ArrowNode):
        """访问箭头操作符节点。"""
        self.visit(node.initial)
        self.visit(node.current)

    def visit_IfThenElseNode(self, node: IfThenElseNode):
        """访问 if-then-else 节点。"""
        self.visit(node.condition)
        self.visit(node.then_expr)
        self.visit(node.else_expr)

    def visit_ArrayLiteralNode(self, node: ArrayLiteralNode):
        """访问数组字面量节点。"""
        for elem in node.elements:
            self.visit(elem)

    def visit_ArrayAccessNode(self, node: ArrayAccessNode):
        """访问数组访问节点。"""
        self.visit(node.array)
        self.visit(node.index)

    def visit_FieldAccessNode(self, node: FieldAccessNode):
        """访问字段访问节点。"""
        self.visit(node.record)

    def visit_FunctionCallNode(self, node: FunctionCallNode):
        """访问函数调用节点。"""
        for arg in node.args:
            self.visit(arg)

    def visit_MergeNode(self, node: MergeNode):
        """访问 merge 节点。"""
        self.visit(node.true_expr)
        self.visit(node.false_expr)

    def visit_FbyNode(self, node: FbyNode):
        """访问 fby 节点。"""
        self.visit(node.initial)

    def visit_WhenNode(self, node: WhenNode):
        """访问 when 节点。"""
        self.visit(node.expr)
        self.visit(node.clock)

    def visit_CurrentNode(self, node: CurrentNode):
        """访问 current 节点。"""
        self.visit(node.operand)

    def visit_LastNode(self, node: LastNode):
        """访问 last 节点。"""
        self.visit(node.operand)

    def visit_NorNode(self, node: NorNode):
        """访问 nor 节点。"""
        for operand in node.operands:
            self.visit(operand)

    def visit_ConversionNode(self, node: ConversionNode):
        """访问类型转换节点。"""
        self.visit(node.operand)


class LustreTransformer(LustreVisitor):
    """Lustre AST 转换器基类。

    提供不可变遍历（默认实现），子类可以重写特定方法来转换节点。
    """

    def generic_visit(self, node: ASTNode):
        """默认返回原节点（不可变遍历）。"""
        return node

    def visit_LustreProgram(self, node: LustreProgram):
        """转换程序节点。"""
        packages = [self.visit(pkg) for pkg in node.packages]
        imports = [self.visit(imp) for imp in node.imports]
        declarations = [self.visit(decl) for decl in node.declarations]
        return LustreProgram(
            packages=packages,
            imports=imports,
            declarations=declarations,
            line=node.line,
            column=node.column,
        )

    def visit_NodeDecl(self, node: NodeDecl):
        """转换节点声明。"""
        inputs = [self.visit(param) for param in node.inputs]
        outputs = [self.visit(param) for param in node.outputs]
        locals_list = [self.visit(var) for var in node.locals]
        equations = [self.visit(eq) for eq in node.equations]
        return NodeDecl(
            name=node.name,
            inputs=inputs,
            outputs=outputs,
            locals=locals_list,
            equations=equations,
            line=node.line,
            column=node.column,
        )

    def visit_EquationNode(self, node: EquationNode):
        """转换等式节点。"""
        return EquationNode(
            lhs=node.lhs,
            rhs=self.visit(node.rhs),
            line=node.line,
            column=node.column,
        )

    def visit_BinaryOpNode(self, node: BinaryOpNode):
        """转换二元运算节点。"""
        return BinaryOpNode(
            op=node.op,
            left=self.visit(node.left),
            right=self.visit(node.right),
            line=node.line,
            column=node.column,
        )

    def visit_UnaryOpNode(self, node: UnaryOpNode):
        """转换一元运算节点。"""
        return UnaryOpNode(
            op=node.op,
            operand=self.visit(node.operand),
            line=node.line,
            column=node.column,
        )


class LustreCollector(LustreVisitor):
    """Lustre AST 收集器基类。

    遍历 AST 并收集信息。
    """

    def __init__(self):
        self.results: list = []

    def collect(self, node: ASTNode) -> list:
        """遍历 AST 并收集结果。"""
        self.results = []
        self.visit(node)
        return self.results


class NameResolver(LustreVisitor):
    """名称解析器。

    遍历 AST，收集所有名称定义。
    """

    def __init__(self):
        self.names: dict[str, ASTNode] = {}
        self.current_scope: list[dict[str, ASTNode]] = [{}]

    def enter_scope(self):
        """进入新作用域。"""
        self.current_scope.append({})

    def exit_scope(self):
        """退出作用域。"""
        self.current_scope.pop()

    def define_name(self, name: str, node: ASTNode):
        """定义新名称。"""
        self.current_scope[-1][name] = node

    def lookup_name(self, name: str) -> ASTNode | None:
        """查找名称。"""
        for scope in reversed(self.current_scope):
            if name in scope:
                return scope[name]
        return None

    def visit_NodeDecl(self, node: NodeDecl):
        """处理节点声明。"""
        self.define_name(node.name, node)
        self.enter_scope()
        for param in node.inputs:
            self.visit(param)
        for param in node.outputs:
            self.visit(param)
        for var in node.locals:
            self.visit(var)
        for eq in node.equations:
            self.visit(eq)
        self.exit_scope()

    def visit_FunctionDecl(self, node: FunctionDecl):
        """处理函数声明。"""
        self.define_name(node.name, node)
        self.enter_scope()
        for param in node.inputs:
            self.visit(param)
        for param in node.outputs:
            self.visit(param)
        for var in node.locals:
            self.visit(var)
        for eq in node.equations:
            self.visit(eq)
        self.exit_scope()

    def visit_ParamNode(self, node: ParamNode):
        """处理参数节点。"""
        for name in node.names:
            self.define_name(name, node)

    def visit_VariableNode(self, node: VariableNode):
        """处理变量节点。"""
        for name in node.names:
            self.define_name(name, node)
