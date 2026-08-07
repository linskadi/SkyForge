# misra_fixes.py 重构方案

> **文件**: `src/skyforge_engine/agents/misra_fixes.py`
> **当前状态**: 3576 行，130 个几乎相同的修复函数
> **问题**: AI 生成的大量重复代码（经典 AI slop）

---

## 问题分析

每个修复函数都有完全相同的结构：

```python
def _fix_rule_XX_X(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule XX.X：描述。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(...)
    old_line = lines[v.line - 1]
    # 尝试正则替换
    new_line = re.sub(...)
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-XX.X] TODO: ... */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(...)
    return new_code, action
```

130 个函数中，90% 的逻辑完全相同，只有：
- 正则表达式模式
- 替换字符串
- 描述文本

---

## 重构方案

### 方案 A：通用修复器 + 规则配置（推荐）

```python
# 规则配置表
_MISRA_RULES: dict[str, dict[str, str]] = {
    "1.1": {
        "description": "函数声明必须包含原型",
        "pattern": r"^(void|int|double|...)\s+(\w+)\s*\([^)]*\)\s*\{?\s*$",
        "replacement": r"\1 \2(/* parameters */)",
        "todo_template": "/* [Rule-1.1] TODO: 添加函数原型 */",
    },
    "8.1": {
        "description": "函数必须要有原型",
        "pattern": r"^(void|int|double|float|char|short|long|unsigned|static\s+\w+)\s+(\w+)\s*\(([^)]*)\)\s*\{?\s*$",
        "replacement": r"\1 \2(\3);",
        "todo_template": "/* [Rule-8.1] TODO: 添加函数原型声明 */",
    },
    # ... 更多规则
}

def _generic_fix_rule(code: str, v: "Violation", rule_config: dict) -> tuple[str, "RepairAction"]:
    """通用 MISRA 规则修复函数。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(rule_id=v.rule_id, line=v.line, description=f"{rule_config['description']}: 行号越界，跳过")
    old_line = lines[v.line - 1]
    new_line = re.sub(rule_config["pattern"], rule_config["replacement"], old_line)
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + f"  {rule_config['todo_template']}\n"
    lines[v.line - 1] = new_line
    return "".join(lines), RepairAction(
        rule_id=v.rule_id, line=v.line,
        description=rule_config["description"],
        before=old_line.strip(), after=new_line.strip(),
    )

# FIXERS 字典改用 lambda
FIXERS: dict[str, Callable] = {
    rule_id: lambda code, v, cfg=cfg: _generic_fix_rule(code, v, cfg)
    for rule_id, cfg in _MISRA_RULES.items()
}
```

### 方案 B：保留原函数，添加 `@register_fixer` 装饰器

```python
_fixer_registry: dict[str, Callable] = {}

def register_fixer(rule_id: str, description: str, pattern: str, replacement: str, todo: str):
    """注册 MISRA 修复函数的装饰器。"""
    def decorator(func):
        _fixer_registry[rule_id] = func
        return func
    return decorator

@register_fixer("8.1", "函数必须要有原型", r"...", r"...", "/* [Rule-8.1] TODO */")
def _fix_rule_8_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    return _generic_fix(code, v, pattern, replacement, todo)
```

---

## 预期效果

| 指标 | 重构前 | 重构后 |
|------|--------|--------|
| 总行数 | 3576 | ~600 |
| 函数数量 | 130 | 1 + 130 个配置条目 |
| 重复代码 | ~90% | <10% |
| 新增规则成本 | ~20 行代码 | 1 行配置 |
| 可维护性 | 低 | 高 |

---

## 风险评估

- **中风险**：正则表达式行为可能因代码上下文不同而有细微差异
- **建议**：先对 5 个最常用规则做试点重构，验证行为一致性后再全量迁移
- **回归测试**：确保现有测试 `test_code_repairer.py` 全部通过

---

## 实施步骤

1. 提取所有 130 个函数的正则/替换/描述 → 规则配置表
2. 实现 `_generic_fix_rule()` 通用函数
3. 替换 FIXERS 字典
4. 运行测试验证
5. 删除旧的 130 个独立函数

---

> **状态**: 待实施（建议作为独立迭代）
> **优先级**: 中（当前功能正常，重构收益在长期维护）
