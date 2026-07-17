# CODING_STANDARD — 航空安全编码标准

> **文档标识**: CODING_STANDARD-SKYFORGE-V1.0
> **适用范围**: SkyForge 工具自身代码（Python 后端 + TypeScript 前端）
> **依据**: DO-178C §5.2 / MISRA C:2012 思路 / T/CECC 44—2025 §7
> **日期**: 2026-07-16

---

## 1. 引言

虽然 SkyForge 本身不是机载软件，但作为**机载软件开发工具**，其自身代码质量直接影响生成的机载代码质量。本章定义适用于 SkyForge 工具代码的航空安全编码子集。

---

## 2. Python 安全编码规则（基于 Ruff）

### 2.1 必须启用的规则

在 `pyproject.toml` 的 `[tool.ruff]` 中启用以下规则：

```toml
[tool.ruff.lint]
select = [
    "E",     # pycodestyle errors
    "W",     # pycodestyle warnings
    "F",     # pyflakes
    "I",     # isort
    "N",     # pep8-naming
    "B",     # flake8-bugbear
    "SIM",   # flake8-simplify
    "C4",    # flake8-comprehensions
    "UP",    # pyupgrade
    "RUF",   # ruff-specific rules
    "T20",   # flake8-print
    "TCH",   # flake8-type-checking
    "PLC",   # pylint conventions
    "PLE",   # pylint errors
    "PLW",   # pylint warnings
    "PERF",  # perflint
]
ignore = []
```

### 2.2 航空安全专项规则

| # | 规则 | 描述 | 严重级 |
|---|------|------|--------|
| AS-P1 | 禁止裸 `except:` | 必须指定异常类型 | **强制** |
| AS-P2 | 禁止 `eval()` / `exec()` | 安全风险 | **强制** |
| AS-P3 | 禁止 `os.system()` / `subprocess(shell=True)` | 命令注入风险 | **强制** |
| AS-P4 | 文件操作使用 `with` 上下文 | 确保资源释放 | **强制** |
| AS-P5 | 所有函数有类型标注 | 类型安全 | **要求** |
| AS-P6 | 关键函数有 docstring | 可追溯 | **要求** |
| AS-P7 | 异常必须记录日志 | 可审计 | **要求** |
| AS-P8 | 递归必须有显式深度限制 | 防止栈溢出 | **强制** |
| AS-P9 | 不使用 `global` / `nonlocal` | 确定性 | **建议** |
| AS-P10 | 时间敏感代码避免动态分配 | 确定性 | **建议** |

### 2.3 Ruff 配置验证

```bash
cd backend
uv run ruff check app/ --select ALL
```

---

## 3. TypeScript 安全编码规则（基于 Biome）

### 3.1 必须启用的规则

```json
// biome.json
{
  "linter": {
    "rules": {
      "recommended": true,
      "correctness": { "all": true },
      "suspicious": {
        "noExplicitAny": "error",
        "noConsoleLog": "error"
      },
      "style": {
        "noVar": "error",
        "useConst": "error"
      }
    }
  }
}
```

### 3.2 航空安全专项规则

| # | 规则 | 描述 | 严重级 |
|---|------|------|--------|
| AS-T1 | 禁止 `any` 类型 | 类型安全 | **强制** |
| AS-T2 | 禁止 `eval()` / `Function()` | 安全风险 | **强制** |
| AS-T3 | 所有 API 响应使用 `unknown` 解析 | 数据安全 | **要求** |
| AS-T4 | DOMPurify 净化所有 HTML 插入 | XSS 防护 | **强制** |
| AS-T5 | 禁止 `console.log` 在生产代码 | 信息泄露 | **建议** |
| AS-T6 | `Promise` 必须有 `.catch()` | 异常处理 | **强制** |

### 3.3 Biome 配置验证

```bash
cd frontend
pnpm biome ci ./src
```

---

## 4. 生成代码安全编码规则（MISRA-C:2012）

生成代码遵循 MISRA-C:2012 标准，当前支持 56 条规则的自动修复（详见 `misra_fixes.py`）。

### 4.1 关键规则清单

| 规则 | 描述 | 修复方式 |
|------|------|---------|
| Rule-8.13 | 指针参数声明为 `const` | 自动添加 `const` |
| Rule-10.1 | 操作数类型兼容 | 自动添加显式类型转换 |
| Rule-11.3 | 不混用指针和整数 | 自动拆分 |
| Rule-14.2 | `for` 循环控制变量不变 | 自动改为局部变量 |
| Rule-17.7 | 函数返回值必须使用 | 自动 `(void)` 忽略 |
| Rule-21.3 | 禁止 `malloc/free` | System Prompt 约束 |

### 4.2 编码禁止项（System Prompt 级约束）

| 禁止项 | 理由 |
|--------|------|
| `malloc` / `calloc` / `realloc` / `free` | MISRA Rule-21.3 |
| 递归函数 | 确定性要求 |
| 全局可变状态（DAL-A） | 耦合风险 |
| `goto` | MISRA Rule-15.1 |
| 动态内存分配 | 机载嵌入式限制 |

---

## 5. 合规检查清单

### 每次 PR 自动检查（CI）

- [ ] Ruff lint 全部通过（Python）
- [ ] Pyright 类型检查通过（Python）
- [ ] Biome lint 全部通过（TypeScript）
- [ ] vue-tsc 类型检查通过（TypeScript）
- [ ] 所有单元测试通过
- [ ] 无 `eval()` / `exec()` / `os.system()` 使用

### 每次生成运行自动检查

- [ ] Cppcheck MISRA-C 扫描 0 残留违规
- [ ] 无 `malloc` / `free` 调用
- [ ] 无递归函数
- [ ] 追溯注释完整（`[REQ-xxx]` / `[LLR-xxx]`）

---

## 6. 安全编码度量目标

| 指标 | 目标值 | 当前值 | 工具 |
|------|--------|--------|------|
| Python 类型覆盖率 | >= 90% | ~85% | Pyright |
| Python Ruff 规则 | >= 95% 通过 | ~95% | Ruff |
| TypeScript 类型覆盖率 | >= 90% | ~90% | vue-tsc |
| 禁止 API 使用 | 0 | 0 | Grep 检查 |
| XSS 风险点 | 0 | 0 | DOMPurify 覆盖 |
| MISRA 违规（生成代码） | 0 | 0 | Cppcheck |
| 动态内存调用（生成代码） | 0 | 0 | 正则检查 |
