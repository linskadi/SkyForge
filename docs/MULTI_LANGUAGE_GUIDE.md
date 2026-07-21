# SkyForge 多语言支持指南

**版本**: v0.5.0  
**日期**: 2026-07-21

## 概述

SkyForge 支持三种编程语言的代码生成、静态分析和形式化验证，并提供可扩展的框架以支持更多语言和编码标准。编码标准通过可插拔注册机制实现，位于 `src/skyforge_engine/coding_standards/`。

### 术语约定

| 缩写 | 全称 | 说明 |
|------|------|------|
| HITL | Human-in-the-Loop | 人工审查 |
| HIL | Hardware-in-the-Loop | 硬件在环 |

### 证据规则

| 状态 | 说明 |
|------|------|
| observed | 实际观测到的证据 |
| simulated | 仿真得到的证据 |
| unavailable | 证据不可用 |
| failed | 验证失败 |

### 可插拔编码标准系统

DO-178C 过程标准固定不动，编码标准通过 `CodingStandardRegistry` 动态注册：

```python
from skyforge_engine.coding_standards.base import get_registry

registry = get_registry()
for std in registry.get_all():
    print(f"{std.standard_id}: {std.name} ({std.languages})")
```

当前已注册标准：MISRA-C:2012 / MISRA C++ / JSF AV C++ / Python安全标准

详见 [编码标准文档](./compliance/CODING_STANDARD.md#8-可插拔编码标准系统)。

---

## 1. 支持的语言

| 语言 | 代码生成器 | 静态分析 | 编码规范 | 代码修复 | 安全等级 |
|------|-----------|----------|----------|----------|----------|
| **C** | `code_generator.py` | Cppcheck | MISRA-C:2012 | `misra_fixes.py` (57个修复器) | DO-178C Level A |
| **C++** | `code_generator_multi.py` | — | MISRA C++ / JSF AV C++ | — | DO-178C Level A |
| **Python** | `code_generator_multi.py` | Ruff + Mypy | Python安全标准 | `python_fixes.py` (4个修复器) | DO-178C Level A |

---

## 2. 静态分析工具

### 2.1 C语言 - Cppcheck

```bash
# 安装
# Ubuntu/Debian
sudo apt-get install cppcheck

# macOS
brew install cppcheck

# Windows (MSYS2)
pacman -S mingw-w64-ucrt-x86_64-cppcheck
```

**使用方式**：
```python
from skyforge_engine.tools.cppcheck_scanner import scan

violations = scan(c_code)
for v in violations:
    print(f"L{v.line}: {v.rule_id} - {v.message}")
```

### 2.2 C++语言

C++语言当前主要通过编码标准规则进行检查，静态分析工具集成待完善。编码标准通过 `coding_standards/misra_cpp.py` 注册，包含 5 条红线规则和 4 种 Mock 扫描模式。

### 2.3 Python语言 - Ruff + Mypy

```bash
# 安装
pip install mypy ruff
```

**使用方式**：
```python
from skyforge_engine.tools.base_scanner import MypyScanner, RuffScanner

# Mypy类型检查
mypy_scanner = MypyScanner()
if mypy_scanner.is_available():
    violations = mypy_scanner.scan(python_code)

# Ruff代码质量检查
ruff_scanner = RuffScanner()
if ruff_scanner.is_available():
    violations = ruff_scanner.scan(python_code)
```

### 2.4 多语言扫描器

```python
from skyforge_engine.tools.cppcheck_scanner import scan_multi

# C语言
violations = scan_multi(c_code, language="c")

# C++语言
violations = scan_multi(cpp_code, language="cpp")

# Python语言
violations = scan_multi(python_code, language="python")
```

---

## 3. 代码生成与修复

### 3.1 代码生成器

| 语言 | 生成器文件 | 说明 |
|------|----------|------|
| C | `agents/code_generator.py` | C语言专用代码生成器 |
| C++ / Python | `agents/code_generator_multi.py` | 多语言代码生成器 |

### 3.2 代码修复器

| 语言 | 修复器文件 | 修复器数量 | 说明 |
|------|----------|------------|------|
| C | `agents/misra_fixes.py` | 57 个 | MISRA-C:2012 规则修复 |
| Python | `agents/python_fixes.py` | 4 个 | Python安全标准修复 |
| C++ | — | — | 待实现 |

---

## 4. 验证器链系统

位置：`src/skyforge_engine/core/verifiers/`

SkyForge 实现了可插拔的验证器链架构，支持组合多个验证器进行多层次验证。

### 4.1 核心组件

| 组件 | 文件 | 说明 |
|------|------|------|
| VerifierChain | `chain.py` | 验证器链，支持顺序执行和 fail_fast 模式 |
| Z3 Verifier | `z3_verifier.py` | Z3 SMT 求解器 |
| CBMC Verifier | `cbmc_verifier.py` | CBMC 有界模型检查 |
| Cppcheck Verifier | `cppcheck_verifier.py` | Cppcheck 静态分析 |
| Contract Verifier | `contract_verifier.py` | 契约校验 |

### 4.2 使用方式

```python
from skyforge_engine.core.verifiers.chain import VerifierChain
from skyforge_engine.core.verifiers.z3_verifier import Z3Verifier
from skyforge_engine.core.verifiers.cppcheck_verifier import CppcheckVerifier

# 创建验证器链
chain = VerifierChain(fail_fast=False)
chain.add(Z3Verifier())
chain.add(CppcheckVerifier())

# 执行所有验证器
results = chain.verify_all(code, contract)
for result in results:
    print(f"{result.tool_name}: passed={result.passed}")
```

### 4.3 验证结果

每个验证器返回 `VerificationResult`，包含：
- `passed`: 是否通过
- `tool_name`: 工具名称
- `tool_available`: 工具是否可用
- `output`: 输出信息

---

## 5. Pipeline Stage 系统

位置：`src/skyforge_engine/core/stages/`

SkyForge 采用流水线架构，包含 11 个 Stage，按顺序执行完整的航空软件开发流程。

### 5.1 Stage 列表

| 序号 | Stage | 文件 | 说明 |
|------|-------|------|------|
| 1 | 需求解析 | `requirement_parse_stage.py` | 解析自然语言需求 |
| 2 | LLR生成 | `llr_gen_stage.py` | 生成低层需求 |
| 3 | 架构设计 | `architecture_design_stage.py` | 软件架构设计 |
| 4 | 契约生成 | `contract_gen_stage.py` | 生成形式化契约 |
| 5 | 代码生成 | `code_gen_stage.py` | 生成源代码 |
| 6 | Cppcheck扫描 | `cppcheck_stage.py` | 静态代码分析 |
| 7 | 修复循环 | `repair_loop_stage.py` | 自动修复违规 |
| 8 | 形式化验证 | `formal_verification_stage.py` | Z3/CBMC 形式化验证 |
| 9 | 数字孪生仿真 | `simulation_stage.py` | 数字孪生仿真验证 |
| 10 | HITL检查点 | `hil_checkpoint_stage.py` | 人工审查检查点 |
| 11 | 报告生成 | `report_gen_stage.py` | 生成 DO-178C 合规报告 |

---

## 6. 策略模式

位置：`src/skyforge_engine/core/strategies/`

SkyForge 使用策略模式支持不同的执行策略。

### 6.1 策略列表

| 策略 | 文件 | 说明 |
|------|------|------|
| LLM Strategy | `llm_strategy.py` | 真实 LLM 调用策略 |
| Mock Strategy | `mock_strategy.py` | Mock 测试策略，用于离线测试 |

---

## 7. 扩展性框架

### 7.1 添加新语言

要添加新的编程语言支持，需要：

1. **创建扫描器**：继承 BaseScanner 类
2. **添加规则库**：在 `rag/data/` 目录添加规则文件
3. **更新代码生成器**：在 `code_generator_multi.py` 添加语言支持
4. **更新修复规则**：创建对应的修复规则文件
5. **注册编码标准**：在 `coding_standards/` 目录添加编码标准注册文件

**示例：添加 Rust 支持**

```python
# src/skyforge_engine/tools/rust_scanner.py
from skyforge_engine.tools.base_scanner import BaseScanner, Violation

class RustScanner(BaseScanner):
    def __init__(self):
        self._clippy_path = shutil.which("cargo")
    
    def is_available(self) -> bool:
        return self._clippy_path is not None
    
    def scan(self, code: str, **kwargs) -> list[Violation]:
        # 使用 cargo clippy 扫描
        pass
```

### 7.2 添加新编码标准

要添加新的编码标准，需要：

1. **创建规则库**：在 `rag/data/` 目录添加规则文件
2. **创建注册文件**：在 `coding_standards/` 目录创建标准注册文件
3. **更新修复规则**：在 `agents/` 目录添加修复函数
4. **更新文档**：在 `docs/compliance/` 添加编码标准文档

**示例：添加 CERT C++ 规则**

```python
# src/skyforge_engine/agents/cpp_fixes.py
def _fix_cert_err50(code: str, v: Violation) -> tuple[str, RepairAction]:
    """CERT ERR50-CPP: 禁止使用 setjmp/longjmp"""
    # 移除 setjmp/longjmp 调用
    new_code = re.sub(r'\bsetjmp\s*\([^)]+\)', '0', code)
    new_code = re.sub(r'\blongjmp\s*\([^)]+\)', 'return', new_code)
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='移除 setjmp/longjmp 调用'
    )
```

---

## 8. API 使用

### 8.1 生成代码（指定语言）

```python
POST /api/generate
{
    "requirement": "实现一个低通滤波器",
    "language": "cpp"  # c, cpp, python
}
```

### 8.2 静态分析（指定语言）

```python
POST /api/check
{
    "code": "...",
    "language": "cpp"
}
```

### 8.3 修复代码（指定语言）

```python
POST /api/repair
{
    "code": "...",
    "violations": [...],
    "language": "cpp"
}
```

---

## 9. 编码标准切换

### 9.1 C语言标准切换

| 标准 | 说明 | 使用场景 |
|------|------|----------|
| MISRA-C:2012 | 汽车/航空安全标准 | 默认 |
| MISRA-C:2023 | 最新版本 | 可选 |
| CERT C | 安全编码实践 | 可选 |

### 9.2 C++语言标准切换

| 标准 | 说明 | 使用场景 |
|------|------|----------|
| MISRA C++ | C++安全编码标准 | 默认 |
| JSF AV C++ | F-35项目标准 | 航空/国防 |
| CERT C++ | 安全编码实践 | 可选 |

### 9.3 Python语言标准切换

| 标准 | 说明 | 使用场景 |
|------|------|----------|
| Python安全标准 | T/ZASDI 0002-2023 | 默认 |
| NASA Power of 10 | 航天安全规则 | 可选 |

---

## 10. 最佳实践

### 10.1 语言选择指南

| 场景 | 推荐语言 | 原因 |
|------|----------|------|
| 硬实时系统 | C/C++ | 确定性执行，WCET可分析 |
| 安全关键系统 | C++ | 类型安全，RAII资源管理 |
| 快速原型 | Python | 开发效率高，易于验证 |
| 混合系统 | C++ + Python | 核心用C++，辅助用Python |

### 10.2 编码标准选择指南

| 场景 | 推荐标准 | 原因 |
|------|----------|------|
| 汽车电子 | MISRA-C/C++ | 行业标准 |
| 航空电子 | JSF AV C++ | F-35项目验证 |
| 军工系统 | Python安全标准 | 国家标准 |
| 通用安全 | CERT C/C++ | 广泛认可 |

---

## 11. 相关文档

- [MISRA-C 规则库](../src/skyforge_engine/rag/data/misra_rules.txt)
- [MISRA-C++ 规则库](../src/skyforge_engine/rag/data/misra_cpp_rules.txt)
- [Python安全规则库](../src/skyforge_engine/rag/data/python_safety_rules.txt)
- [C++ 编码标准](./compliance/CODING_STANDARD_CPP.md)
- [Python 编码标准](./compliance/CODING_STANDARD_PYTHON.md)
- [GCC编译指南](./verification/GCC_COMPILATION_GUIDE.md)
- [多语言验证报告](./verification/MULTI_LANGUAGE_VERIFICATION.md)
