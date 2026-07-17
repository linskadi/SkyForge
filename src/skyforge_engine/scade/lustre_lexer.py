"""Lustre 词法分析器。

使用正则表达式实现的 Lustre 词法分析器，作为 ANTLR4 的轻量级替代。
支持完整的 Lustre 词法元素。
"""

from __future__ import annotations

import re
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional


class TokenType(Enum):
    """Token 类型。"""
    # 关键字
    NODE = auto()
    FUNCTION = auto()
    VAR = auto()
    LET = auto()
    TEL = auto()
    RETURNS = auto()
    IMPORT = auto()
    PACKAGE = auto()
    STRUCT = auto()
    ARRAY = auto()
    OF = auto()
    CONST = auto()
    TYPE = auto()
    TRUE = auto()
    FALSE = auto()
    IF = auto()
    THEN = auto()
    ELSE = auto()
    ELSEIF = auto()
    CASE = auto()
    END = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    MOD = auto()
    REM = auto()
    PRE = auto()
    MERGE = auto()
    FBY = auto()
    WHEN = auto()
    BY = auto()
    CURRENT = auto()
    LAST = auto()
    NOR = auto()
    ABS = auto()
    BOOL_TO_INT = auto()
    INT_TO_REAL = auto()
    REAL_TO_INT = auto()
    AUTOMATON = auto()
    STATE = auto()
    UNTIL = auto()
    UNLESS = auto()
    DO = auto()
    WITH = auto()
    ASSERT = auto()

    # 数据类型
    INT_TYPE = auto()
    REAL_TYPE = auto()
    BOOL_TYPE = auto()
    FLOAT_TYPE = auto()
    DOUBLE_TYPE = auto()
    INT8_TYPE = auto()
    UINT8_TYPE = auto()
    INT16_TYPE = auto()
    UINT16_TYPE = auto()
    INT32_TYPE = auto()
    UINT32_TYPE = auto()

    # 标识符和字面量
    IDENTIFIER = auto()
    INTEGER = auto()
    FLOAT = auto()

    # 运算符
    ASSIGN = auto()
    EQUAL = auto()
    NOT_EQUAL = auto()
    LESS = auto()
    GREATER = auto()
    LESS_EQ = auto()
    GREATER_EQ = auto()
    PLUS = auto()
    MINUS = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    POWER = auto()
    ARROW = auto()

    # 分隔符
    SEMICOLON = auto()
    COMMA = auto()
    COLON = auto()
    DOT = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()

    # 特殊
    NEWLINE = auto()
    EOF = auto()
    ERROR = auto()


@dataclass
class Token:
    """词法分析器 Token。"""
    type: TokenType
    value: str
    line: int
    column: int
    length: int = 0

    def __post_init__(self):
        if self.length == 0:
            self.length = len(self.value)


# 关键字映射
KEYWORDS: dict[str, TokenType] = {
    'node': TokenType.NODE,
    'function': TokenType.FUNCTION,
    'var': TokenType.VAR,
    'let': TokenType.LET,
    'tel': TokenType.TEL,
    'returns': TokenType.RETURNS,
    'import': TokenType.IMPORT,
    'package': TokenType.PACKAGE,
    'struct': TokenType.STRUCT,
    'array': TokenType.ARRAY,
    'of': TokenType.OF,
    'const': TokenType.CONST,
    'type': TokenType.TYPE,
    'true': TokenType.TRUE,
    'false': TokenType.FALSE,
    'if': TokenType.IF,
    'then': TokenType.THEN,
    'else': TokenType.ELSE,
    'elseif': TokenType.ELSEIF,
    'case': TokenType.CASE,
    'end': TokenType.END,
    'and': TokenType.AND,
    'or': TokenType.OR,
    'not': TokenType.NOT,
    'mod': TokenType.MOD,
    'rem': TokenType.REM,
    'pre': TokenType.PRE,
    'merge': TokenType.MERGE,
    'fby': TokenType.FBY,
    'when': TokenType.WHEN,
    'by': TokenType.BY,
    'current': TokenType.CURRENT,
    'last': TokenType.LAST,
    'nor': TokenType.NOR,
    'abs': TokenType.ABS,
    'bool_to_int': TokenType.BOOL_TO_INT,
    'int_to_real': TokenType.INT_TO_REAL,
    'real_to_int': TokenType.REAL_TO_INT,
    'automaton': TokenType.AUTOMATON,
    'state': TokenType.STATE,
    'until': TokenType.UNTIL,
    'unless': TokenType.UNLESS,
    'do': TokenType.DO,
    'with': TokenType.WITH,
    'assert': TokenType.ASSERT,
    'int': TokenType.INT_TYPE,
    'real': TokenType.REAL_TYPE,
    'bool': TokenType.BOOL_TYPE,
    'float': TokenType.FLOAT_TYPE,
    'double': TokenType.DOUBLE_TYPE,
    'int8': TokenType.INT8_TYPE,
    'uint8': TokenType.UINT8_TYPE,
    'int16': TokenType.INT16_TYPE,
    'uint16': TokenType.UINT16_TYPE,
    'int32': TokenType.INT32_TYPE,
    'uint32': TokenType.UINT32_TYPE,
}

# Token 模式列表（按优先级排序）
TOKEN_PATTERNS: list[tuple[TokenType, str]] = [
    # 注释
    (None, r'\(\*.*?\*\)'),           # 块注释
    (None, r'//.*$'),                 # 行注释

    # 空白
    (None, r'[ \t]+'),                # 空格和制表符
    (None, r'\r?\n'),                 # 换行符

    # 数字
    (TokenType.FLOAT, r'\d+\.\d+(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+'),
    (TokenType.INTEGER, r'\d+'),

    # 运算符
    (TokenType.ARROW, r'->'),
    (TokenType.NOT_EQUAL, r'<>'),
    (TokenType.LESS_EQ, r'<='),
    (TokenType.GREATER_EQ, r'>='),
    (TokenType.POWER, r'\^'),
    (TokenType.ASSIGN, r'='),
    (TokenType.LESS, r'<'),
    (TokenType.GREATER, r'>'),
    (TokenType.PLUS, r'\+'),
    (TokenType.MINUS, r'-'),
    (TokenType.MULTIPLY, r'\*'),
    (TokenType.DIVIDE, r'/'),

    # 分隔符
    (TokenType.SEMICOLON, r';'),
    (TokenType.COMMA, r','),
    (TokenType.COLON, r':'),
    (TokenType.DOT, r'\.'),
    (TokenType.LPAREN, r'\('),
    (TokenType.RPAREN, r'\)'),
    (TokenType.LBRACKET, r'\['),
    (TokenType.RBRACKET, r'\]'),
    (TokenType.LBRACE, r'\{'),
    (TokenType.RBRACE, r'\}'),

    # 标识符（必须在关键字之后）
    (TokenType.IDENTIFIER, r'[a-zA-Z_][a-zA-Z0-9_]*'),
]


class LustreLexerError(Exception):
    """词法分析错误。"""
    def __init__(self, message: str, line: int, column: int):
        self.line = line
        self.column = column
        super().__init__(f"Line {line}, Column {column}: {message}")


class LustreLexer:
    """Lustre 词法分析器。"""

    def __init__(self, source: str):
        """初始化词法分析器。

        Args:
            source: Lustre 源代码字符串。
        """
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: list[Token] = []
        self._compile_patterns()

    def _compile_patterns(self):
        """编译正则表达式模式。"""
        self.patterns: list[tuple[Optional[TokenType], re.Pattern]] = []
        for token_type, pattern in TOKEN_PATTERNS:
            compiled = re.compile(pattern, re.MULTILINE | re.DOTALL)
            self.patterns.append((token_type, compiled))

    def tokenize(self) -> list[Token]:
        """执行词法分析，返回 Token 列表。

        Returns:
            Token 列表。
        """
        while self.pos < len(self.source):
            matched = False
            for token_type, pattern in self.patterns:
                m = pattern.match(self.source, self.pos)
                if m:
                    value = m.group()
                    if token_type is not None:
                        # 处理关键字
                        if token_type == TokenType.IDENTIFIER:
                            if value.lower() in KEYWORDS:
                                token_type = KEYWORDS[value.lower()]
                        self.tokens.append(Token(
                            type=token_type,
                            value=value,
                            line=self.line,
                            column=self.column,
                        ))
                    # 更新位置
                    newlines = value.count('\n')
                    if newlines > 0:
                        self.line += newlines
                        self.column = len(value) - value.rfind('\n')
                    else:
                        self.column += len(value)
                    self.pos = m.end()
                    matched = True
                    break
            if not matched:
                # 无法识别的字符
                char = self.source[self.pos]
                raise LustreLexerError(
                    f"Unexpected character: '{char}'",
                    self.line,
                    self.column,
                )

        # 添加 EOF Token
        self.tokens.append(Token(
            type=TokenType.EOF,
            value='',
            line=self.line,
            column=self.column,
        ))

        return self.tokens


def tokenize(source: str) -> list[Token]:
    """便捷函数：对 Lustre 源代码进行词法分析。

    Args:
        source: Lustre 源代码字符串。

    Returns:
        Token 列表。
    """
    lexer = LustreLexer(source)
    return lexer.tokenize()
