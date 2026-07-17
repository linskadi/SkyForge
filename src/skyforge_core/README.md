# Layer 2 — skyforge-core · CLI 工具

> **开发/CI 集成 · +5MB · 4 子命令**

```bash
pip install skyforge-core
```

## 子命令

```bash
# 生成代码
skyforge generate --requirement "设计一个10Hz低通滤波器" --output ./output/

# 检查 MISRA-C 合规性
skyforge check --code ./output/main.c

# 数字孪生仿真
skyforge simulate --code ./output/main.c --contract ./output/contract.yaml

# 生成 DO-178C 报告
skyforge report --code ./output/main.c --contract ./output/contract.yaml
```

## 安装

```bash
# 完整安装（自动依赖 engine + llm）
pip install skyforge-core

# 仅 CLI（不含 LLM，使用 Mock 降级）
pip install skyforge-core --no-deps
pip install skyforge-engine
```

## 架构

```
skyforge_core/
├── cli.py               # Click CLI (generate/check/simulate/report)
├── pyproject.toml       # 独立包，entry point: skyforge
└── __init__.py
```

> 此层仅封装 CLI 入口，所有实际逻辑委托给 engine 层。
