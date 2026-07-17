# Lustre 解析器 (ANTLR4 实现)

## 概述

本模块使用 ANTLR4 风格的递归下降解析器替代原有的正则表达式解析器，提供完整的 Lustre 语言支持，同时保持向后兼容性。

## 主要改进

1. **完整的词法分析和语法分析** - 支持所有 Lustre 语法元素
2. **结构化 AST** - 生成抽象语法树，便于后续处理
3. **完整的类型支持** - int, real, bool, float, double, int8, uint8, int16, uint16, int32, uint32
4. **复合类型** - 数组(array[N] of type)、结构体(struct { field: type })
5. **操作符支持** - 算术、逻辑、比较、时序操作符
6. **错误恢复** - 更好的错误处理和恢复机制
7. **向后兼容** - 保持原有 API 不变

## 文件结构

```
scade/
├── __init__.py              # 模块初始化
├── lustre_ast.py            # AST 节点定义
├── lustre_lexer.py          # 词法分析器
├── lustre_parser_impl.py    # 语法分析器
├── lustre_parser_new.py     # 新解析器封装
├── lustre_parser.py         # 向后兼容的解析器
├── lustre_visitor.py        # AST 访问者
├── lustre_to_requirement.py # 需求转换器
├── Lustre.g4               # ANTLR4 语法文件
├── test_example.lus        # 测试示例
├── test_parser.py          # 测试脚本
└── README.md               # 本文档
```

## 使用方法

### 基本用法

```python
from skyforge_engine.scade.lustre_parser import parse_glustre

# 解析 Lustre 代码
content = """
node AddNode(a: real; b: real) returns (c: real)
let
    c = a + b;
tel
"""

result = parse_glustre(content)
print(f"节点名: {result.node_name}")
print(f"输入: {result.inputs}")
print(f"输出: {result.outputs}")
print(f"等式: {result.equations}")
```

### 高级用法

```python
from skyforge_engine.scade.lustre_parser import (
    parse_glustre,
    parse_glustre_with_ast,
    validate_lustre,
    get_ast_statistics,
)

# 解析为完整 AST
program = parse_glustre_with_ast(content)

# 验证语法
is_valid, errors = validate_lustre(content)

# 获取统计信息
stats = get_ast_statistics(program)
```

### 支持的语法

#### 数据类型
- 基础类型: `int`, `real`, `bool`, `float`, `double`
- 整数类型: `int8`, `uint8`, `int16`, `uint16`, `int32`, `uint32`
- 数组类型: `array[N] of type`
- 结构体类型: `struct { field: type, ... }`

#### 操作符
- 算术: `+`, `-`, `*`, `/`, `mod`, `rem`, `^`
- 比较: `=`, `<>`, `<`, `>`, `<=`, `>=`
- 逻辑: `and`, `or`, `not`
- 时序: `pre`, `->`, `when`, `by`, `current`, `last`, `fby`

#### 定义
- 节点: `node name(params) returns (params) var ... let ... tel`
- 函数: `function name(params) returns (params) var ... let ... tel`
- 结构体: `struct name { field: type, ... }`
- 常量: `const name: type = value;`
- 类型别名: `type name = type;`
- 导入: `import name[.name]*;`
- 包: `package name;`

#### 表达式
- 字面量: 整数、浮点数、布尔值
- 标识符: 变量名
- 二元运算: `expr op expr`
- 一元运算: `-expr`, `not expr`, `pre expr`
- 条件表达式: `if expr then expr else expr`
- 数组访问: `array[index]`
- 字段访问: `record.field`
- 函数调用: `func(args)`
- 数组字面量: `[expr, expr, ...]`
- 类型转换: `bool_to_int(expr)`, `int_to_real(expr)`, `real_to_int(expr)`
- 时序操作符: `merge clock(expr1, expr2)`, `fby(expr, count)`

## 测试

运行测试脚本:

```bash
cd src/skyforge_engine/scade
python test_parser.py
```

## 向后兼容性

新的解析器完全兼容原有 API:

- `parse_glustre(content)` 函数保持不变
- `Variable`, `Equation`, `ParsedLustre` 类保持不变
- 所有现有代码无需修改即可继续工作

## 错误处理

新的解析器提供详细的错误信息:

```python
from skyforge_engine.scade.lustre_parser_new import (
    LustreLexerError,
    LustreParseError,
)

try:
    result = parse_glustre(content)
except LustreLexerError as e:
    print(f"词法错误: {e}")
except LustreParseError as e:
    print(f"语法错误: {e}")
except ValueError as e:
    print(f"解析错误: {e}")
```

## 性能

新的解析器相比正则表达式解析器有轻微的性能开销，但提供了更好的准确性和可维护性。对于大型 Lustre 文件，性能差异可以忽略不计。

## 依赖

本模块不需要额外的外部依赖，完全使用 Python 标准库实现。

## 未来计划

1. 添加完整的语义分析
2. 支持更多的 Lustre 扩展语法
3. 添加代码生成功能
4. 支持增量解析
5. 添加语法高亮支持
