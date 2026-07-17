grammar Lustre;

// ==================== Parser Rules ====================

// 程序结构
program
    : packageDecl* importDecl* topLevelDecl* EOF
    ;

packageDecl
    : 'package' IDENTIFIER ';'
    ;

importDecl
    : 'import' IDENTIFIER ('.' IDENTIFIER)* ';'
    ;

topLevelDecl
    : nodeDecl
    | functionDecl
    | structDecl
    | constDecl
    | typeAliasDecl
    ;

// 节点定义
nodeDecl
    : 'node' IDENTIFIER '(' paramList? ')' 'returns' '(' paramList? ')'
      varBlock? letBlock?
    ;

// 函数定义
functionDecl
    : 'function' IDENTIFIER '(' paramList? ')' 'returns' '(' paramList? ')'
      varBlock? letBlock?
    ;

// 参数列表
paramList
    : paramDecl (',' paramDecl)*
    ;

paramDecl
    : IDENTIFIER (',' IDENTIFIER)* ':' typeExpr
    ;

// 类型表达式
typeExpr
    : baseType
    | arrayType
    | structType
    | namedType
    ;

baseType
    : 'int'
    | 'real'
    | 'bool'
    | 'float'
    | 'double'
    | 'int8'
    | 'uint8'
    | 'int16'
    | 'uint16'
    | 'int32'
    | 'uint32'
    ;

arrayType
    : 'array' '[' INTEGER ']' 'of' typeExpr
    ;

structType
    : 'struct' '{' structField (',' structField)* '}'
    ;

structField
    : IDENTIFIER ':' typeExpr
    ;

namedType
    : IDENTIFIER
    ;

// 局部变量块
varBlock
    : 'var' varDecl+ 
    ;

varDecl
    : IDENTIFIER (',' IDENTIFIER)* ':' typeExpr (';' | ',')
    ;

// let块
letBlock
    : 'let' equation* 'tel'
    ;

// 方程
equation
    : singleAssign ';'
    | multiAssign ';'
    | assertStmt
    | automatonDecl
    | caseBlock
    | ifThenElseStmt
    | expression ';'
    ;

singleAssign
    : IDENTIFIER '=' expression
    ;

multiAssign
    : '(' IDENTIFIER (',' IDENTIFIER)* ')' '=' expression
    ;

// 断言
assertStmt
    : 'assert' expression
    ;

// 自动机
automatonDecl
    : 'automaton' IDENTIFIER? 'with' 'type' typeExpr
      stateBlock+
      'tel'
    ;

stateBlock
    : 'state' IDENTIFIER ':' 'until' expression
      varBlock?
      letBlock?
      ('unless' expression 'do' letBlock?)?
    ;

// case块
caseBlock
    : 'case' expression 'of'
      caseItem+
      ('else' letBlock?)?
      'end'
    ;

caseItem
    : pattern ':' letBlock?
    ;

pattern
    : INTEGER
    | IDENTIFIER
    | 'true'
    | 'false'
    | '_'
    ;

// if-then-else语句
ifThenElseStmt
    : 'if' expression 'then' letBlock
      ('elseif' expression 'then' letBlock)*
      ('else' letBlock)?
    ;

// 表达式（优先级从低到高）
expression
    : orExpr
    ;

orExpr
    : andExpr ('or' andExpr)*
    ;

andExpr
    : notExpr ('and' notExpr)*
    ;

notExpr
    : 'not' notExpr
    | compExpr
    ;

compExpr
    : addExpr (compOp addExpr)?
    ;

compOp
    : '='
    | '<>'
    | '<'
    | '>'
    | '<='
    | '>='
    ;

addExpr
    : mulExpr (addOp mulExpr)*
    ;

addOp
    : '+'
    | '-'
    ;

mulExpr
    : unaryExpr (mulOp unaryExpr)*
    ;

mulOp
    : '*'
    | '/'
    | 'mod'
    | 'rem'
    ;

unaryExpr
    : '-' unaryExpr
    | 'pre' unaryExpr
    | 'not' unaryExpr
    | powerExpr
    ;

powerExpr
    : atomExpr ('^' atomExpr)?
    ;

atomExpr
    : INTEGER
    | FLOAT
    | 'true'
    | 'false'
    | '(' expression ')'
    | arrayExpr
    | functionCall
    | atomExpr '.' IDENTIFIER
    | atomExpr '[' expression ']'
    | IDENTIFIER
    | 'if' expression 'then' expression ('elseif' expression 'then' expression)* 'else' expression
    | 'merge' IDENTIFIER '(' expression ',' expression ')'
    | 'fby' '(' expression ',' INTEGER ')'
    | 'when' expression 'by' expression
    | 'current' expression
    | 'last' expression
    | 'nor' '(' expression (',' expression)* ')'
    | 'abs' '(' expression ')'
    | 'bool_to_int' '(' expression ')'
    | 'int_to_real' '(' expression ')'
    | 'real_to_int' '(' expression ')'
    ;

// 数组表达式
arrayExpr
    : '[' expression (',' expression)* ']'
    ;

// 函数调用
functionCall
    : IDENTIFIER '(' expressionList? ')'
    ;

expressionList
    : expression (',' expression)*
    ;

// ==================== Lexer Rules ====================

// 关键字
NODE        : 'node';
FUNCTION    : 'function';
VAR         : 'var';
LET         : 'let';
TEL         : 'tel';
RETURNS     : 'returns';
IMPORT      : 'import';
PACKAGE     : 'package';
STRUCT      : 'struct';
ARRAY       : 'array';
OF          : 'of';
CONST       : 'const';
TYPE        : 'type';
TRUE        : 'true';
FALSE       : 'false';
IF          : 'if';
THEN        : 'then';
ELSE        : 'else';
ELSEIF      : 'elseif';
CASE        : 'case';
OF_KW       : 'of';
END         : 'end';
AND         : 'and';
OR          : 'or';
NOT         : 'not';
MOD         : 'mod';
REM         : 'rem';
PRE         : 'pre';
MERGE       : 'merge';
FBY         : 'fby';
WHEN        : 'when';
BY          : 'by';
CURRENT     : 'current';
LAST        : 'last';
NOR         : 'nor';
ABS         : 'abs';
BOOL_TO_INT : 'bool_to_int';
INT_TO_REAL : 'int_to_real';
REAL_TO_INT : 'real_to_int';
AUTOMATON   : 'automaton';
STATE       : 'state';
UNTIL       : 'until';
UNLESS      : 'unless';
DO          : 'do';
WITH        : 'with';

// 数据类型
INT_TYPE    : 'int';
REAL_TYPE   : 'real';
BOOL_TYPE   : 'bool';
FLOAT_TYPE  : 'float';
DOUBLE_TYPE : 'double';
INT8_TYPE   : 'int8';
UINT8_TYPE  : 'uint8';
INT16_TYPE  : 'int16';
UINT16_TYPE : 'uint16';
INT32_TYPE  : 'int32';
UINT32_TYPE : 'uint32';

// 标识符
IDENTIFIER
    : [a-zA-Z_] [a-zA-Z0-9_]*
    ;

// 数字
INTEGER
    : [0-9]+
    ;

FLOAT
    : [0-9]+ '.' [0-9]+
    | [0-9]+ ('e' | 'E') ('+' | '-')? [0-9]+
    | [0-9]+ '.' [0-9]+ ('e' | 'E') ('+' | '-')? [0-9]+
    ;

// 运算符
ASSIGN      : '=';
EQUAL       : '=';
NOT_EQUAL   : '<>';
LESS        : '<';
GREATER     : '>';
LESS_EQ     : '<=';
GREATER_EQ  : '>=';
PLUS        : '+';
MINUS       : '-';
MULTIPLY    : '*';
DIVIDE      : '/';
POWER       : '^';
ARROW       : '->';

// 分隔符
SEMICOLON   : ';';
COMMA       : ',';
COLON       : ':';
DOT         : '.';
LPAREN      : '(';
RPAREN      : ')';
LBRACKET    : '[';
RBRACKET    : ']';
LBRACE      : '{';
RBRACE      : '}';

// 注释
BLOCK_COMMENT
    : '(*' .*? '*)' -> skip
    ;

LINE_COMMENT
    : '//' ~[\r\n]* -> skip
    ;

// 空白
WS
    : [ \t\r\n]+ -> skip
    ;
