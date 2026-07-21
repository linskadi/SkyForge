# Layer 0 — skyforge-engine · 核心引擎

> **可独立机载部署 · 6 包依赖 · ~80MB · 零 LLM · MIT**

```bash
pip install skyforge-engine
```

## 功能

- **5 Agent 协同流水线** — REQ-Parser → LLR-Gen → CON-Gen → CODE-Gen → REPAIR
- **契约式设计** — .contract YAML 生成 + AST+Cppcheck 双重验证 + Z3/CBMC 形式化证明
- **数字孪生仿真** — VirtualMCU + VirtualSensor + 5 类故障注入
- **DO-178C 合规** — DAL A~E 全覆盖，19 项目标，MC/DC 覆盖率计算
- **MISRA-C:2012** — 175 条规则库 (136KB)，143 条已验证，56 条自动修复
- **SCADE 支持** — ANTLR4 G-Lustre 解析器，SCADE → 需求转换
- **插件系统** — 完整框架，5 个示例插件
- **证据收集** — 自动生成 DO-178C 合规证据包

## 安装

```bash
# 仅引擎（6 个依赖，零 LLM）
pip install skyforge-engine

# 形式化验证（可选，z3-solver 纯 Python 包，纯 SMT 求解）
pip install z3-solver

# CBMC C 有界模型检查器（可选，外部二进制工具）
# Linux:   apt install cbmc
# macOS:   brew install cbmc
# Windows: 官方 msi 安装到 C:\Program Files\cbmc\bin\

# 嵌入式编译（远期目标）
nuitka skyforge_engine → <15MB 单文件
```

> **Windows 注意**：cppcheck MISRA addon 使用 `sys.executable`（venv 内 Python）调用，避免 Windows Store python stub（exitcode 9009）问题；z3 通过 Python 包检测而非命令行二进制；cbmc 额外检测 `C:\Program Files\cbmc\bin\cbmc.exe` 默认路径。

## 运行

```python
from skyforge_engine import run_full_pipeline

result = await run_full_pipeline(
    requirement="设计一个10Hz低通滤波器，DA-B级",
    simulate=True,
)
# result → {code, contract, violations, simulation_result, evidence_package}
```

## 架构

```
skyforge_engine/
├── pipeline.py          # 全流程编排
├── agents/              # 5 Agent (LLM → Mock 降级)
├── tools/               # Cppcheck/CBMC/Z3/Semgrep/Frama-C
├── digital_twin/        # VirtualMCU + HIL 适配器
├── report/              # DO-178C 报告 + 证据收集
├── rag/                 # MISRA-C 知识库
├── scade/               # G-Lustre 解析 + MATLAB/Simulink
├── composable/          # 组件组合
├── dal/                 # DAL 自适应 + MC/DC
├── plugins/             # 插件系统
└── schemas/             # DAL 目标定义
```

## 依赖

| 包 | 用途 |
|----|------|
| pyyaml | 契约解析 |
| numpy | 仿真计算 |
| loguru | 日志 |
| packaging | 版本管理 |

> 不依赖任何 LLM 库、Web 框架、数据库。可部署在机载 ARM64/RISC-V 设备。
