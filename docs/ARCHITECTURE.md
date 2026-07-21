# SkyForge 架构文档

## 概述

SkyForge 采用**四层可剥离部署架构**（Layer 0-3: Engine/LLM/CLI/Studio），从轻量级核心引擎到完整的 Web 工作室，可根据需求灵活部署。

引擎内部架构升级为**六层引擎架构**（L0-L5），实现协议驱动、工具链可插拔、多 Agent 协同的可信代码生成流水线。

## 部署架构层次（四层可剥离）

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer 3: Web 工作室                        │
│              (FastAPI + Vue 3 + WebSocket)                   │
├─────────────────────────────────────────────────────────────┤
│                    Layer 2: CLI 工具                          │
│               (skyforge-core CLI)                            │
├─────────────────────────────────────────────────────────────┤
│                    Layer 1: LLM 抽象层                       │
│           (skyforge-llm 多模型支持)                          │
├─────────────────────────────────────────────────────────────┤
│                    Layer 0: 核心引擎                         │
│            (skyforge-engine 零LLM零Web)                      │
└─────────────────────────────────────────────────────────────┘
```

## 引擎内部架构（六层 L0-L5）

```
┌─────────────────────────────────────────────────────────────────────┐
│  L5 编排层 (Orchestration)                                          │
│  PipelineOrchestrator · 12个Stage调度 · 可信证据包生成              │
├─────────────────────────────────────────────────────────────────────┤
│  L4 Agent 策略层 (Agent Strategy)                                   │
│  需求解析 · LLR生成 · 架构设计 · 契约 · 代码生成 · 修复 · MISRA适配 │
├─────────────────────────────────────────────────────────────────────┤
│  L3 验证工具链层 (Verifier Chain)                                   │
│  Z3 · CBMC · Cppcheck · GCC · 形式化 · 静态分析 · 可插拔链          │
├─────────────────────────────────────────────────────────────────────┤
│  L2 HIL 适配器层 (HIL Adapter)                                      │
│  QEMU · 串口 · ARINC653 · 虚拟MCU · 虚拟传感器 · 故障注入           │
├─────────────────────────────────────────────────────────────────────┤
│  L1 LLM 客户端层 (LLM Client)                                       │
│  Mock · 云API · 本地OpenAI兼容 · 路由                              │
├─────────────────────────────────────────────────────────────────────┤
│  L0 基础设施协议层 (Protocols)                                      │
│  协议 · 抽象基类 · 模式守卫 · 执行契约                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 引擎六层详细说明

| 层级 | 名称 | 核心职责 | 关键模块 |
|------|------|----------|----------|
| L0 | 基础设施协议层 | 定义全系统协议、抽象基类、模式守卫、执行契约 | protocols/ |
| L1 | LLM 客户端层 | 多模型客户端统一接口、路由、Mock 降级 | strategies/ |
| L2 | HIL 适配器层 | 硬件在环与数字孪生适配，支持多种仿真后端 | adapters/ · digital_twin/ |
| L3 | 验证工具链层 | 形式化验证与静态分析工具可插拔链 | verifiers/ · tools/ |
| L4 | Agent 策略层 | 多 Agent 协同完成需求到代码的全流程 | agents/ |
| L5 | 编排层 | PipelineOrchestrator 串联各层，调度 12 个 Stage | core/orchestrator.py · stages/ |

## Layer 0: 核心引擎 (skyforge_engine)

核心引擎是整个系统的基础，不依赖 LLM 和 Web 框架，可独立运行。

### 模块结构

```
skyforge_engine/
├── core/                      # 核心编排
│   ├── orchestrator.py        #   PipelineOrchestrator
│   ├── stages/                #   12个阶段
│   │   ├── requirement_parse.py
│   │   ├── llr_gen.py
│   │   ├── architecture_design.py
│   │   ├── contract_gen.py
│   │   ├── code_gen.py
│   │   ├── cppcheck.py
│   │   ├── repair_loop.py
│   │   ├── formal_verification.py
│   │   ├── simulation.py
│   │   ├── hil_checkpoint.py
│   │   ├── report_gen.py
│   │   └── ...
│   ├── verifiers/             #   验证器链
│   │   ├── z3.py
│   │   ├── cbmc.py
│   │   ├── cppcheck.py
│   │   ├── contract.py
│   │   └── chain.py
│   ├── strategies/            #   LLM/Mock 策略
│   ├── protocols/             #   协议定义
│   ├── standards/             #   编码标准
│   ├── adapters/              #   HIL 适配器
│   └── renderers/             #   HTML/Markdown/PDF 渲染
├── agents/                    # 多 Agent 系统
│   ├── requirement_parser.py  #   需求解析 Agent
│   ├── llr_generator.py       #   LLR 生成 Agent
│   ├── architecture_designer.py # 架构设计 Agent
│   ├── contract_generator.py  #   契约生成 Agent
│   ├── code_generator.py      #   代码生成 Agent (C)
│   ├── code_generator_multi.py #  多语言代码生成 (C++/Python)
│   ├── code_repairer.py       #   代码修复 Agent
│   ├── misra_fixes.py         #   MISRA-C 修复规则
│   └── python_fixes.py        #   Python 修复规则
├── digital_twin/              # 数字孪生
│   ├── virtual_sensor.py      #   虚拟传感器
│   ├── virtual_mcu.py         #   虚拟 MCU
│   ├── fault_injector.py      #   故障注入
│   ├── hil_adapter.py         #   HIL 适配器
│   ├── qemu_adapter.py        #   QEMU 适配器
│   ├── serial_hil.py          #   串口 HIL
│   ├── arinc653_adapter.py    #   ARINC653 适配器
│   └── simulation_engine.py   #   仿真引擎
├── composable/                # 组件组合验证
│   ├── compatibility_checker.py
│   ├── component_combinator.py
│   └── composition_simulator.py
├── tools/                     # 工具链
│   ├── cppcheck_scanner.py    #   Cppcheck 集成
│   ├── z3_verifier.py         #   Z3 形式化验证
│   ├── cbmc_verifier.py       #   CBMC 模型检测
│   ├── contract_checker.py    #   契约校验
│   ├── contract_formal_verifier.py # 契约形式化验证
│   └── tool_chain_validator.py #  工具链验证
├── report/                    # DO-178C 报告
│   ├── do178_objectives.py    #   合规目标
│   ├── coverage_analyzer.py   #   覆盖率分析
│   ├── traceability_matrix.py #   可追溯性矩阵
│   ├── psac_generator.py      #   PSAC 生成器
│   ├── evidence_collector.py  #   证据收集器
│   └── report_generator.py    #   报告生成器
├── rag/                       # RAG 知识库
│   ├── misra_searcher.py      #   MISRA 搜索
│   ├── rag_enhancer.py        #   RAG 增强器
│   ├── rule_parser.py         #   规则解析器
│   └── semantic_search.py     #   语义搜索
├── coding_standards/          # 可插拔编码标准系统
│   ├── misra_c.py             #   MISRA-C
│   ├── misra_cpp.py           #   MISRA-C++
│   └── python_safety.py       #   Python 安全标准
├── streaming/                 # 流处理
│   └── task_stream_registry.py #  任务流注册
├── dal/                       # DAL 目标覆盖
│   ├── gcov_collector.py      #   GCOV 收集器
│   └── mcdc_calculator.py     #   MC/DC 计算器
└── scade/                     # SCADE G-Lustre 解析器
```

### 可插拔编码标准系统

DO-178C 过程标准固定不动，编码标准通过插件化注册机制实现可插拔：

```python
# coding_standards/base.py
from skyforge_engine.coding_standards import get_registry

registry = get_registry()
# 获取所有已注册标准
for std in registry.list_all():
    print(f"{std.id}: {std.name} ({std.language})")

# 按语言获取
cpp_standards = registry.get_by_language("cpp")
```

当前已注册的编码标准：
- `misra_c_2012`: MISRA-C:2012 (10 条红线规则, 56 个修复器)
- `jsf_av_cpp`: JSF AV C++ (5 条红线规则)
- `python_safety`: Python 安全标准 (3 条红线规则, 4 个修复器)

### 核心流程（PipelineOrchestrator + 12 个 Stage）

```python
# core/orchestrator.py - PipelineOrchestrator
class PipelineOrchestrator:
    def run(self, requirement: str, profile: str = "demo") -> TaskResult:
        # 12 个 Stage 流水线
        stages = [
            "requirement_parse",    # 需求解析
            "llr_gen",            # LLR 生成
            "architecture_design", # 架构设计
            "contract_gen",       # 契约生成
            "code_gen",           # 代码生成
            "cppcheck",           # 静态分析
            "repair_loop",        # 自动修复循环
            "formal_verification", # 形式化验证
            "simulation",         # 数字孪生仿真
            "hil_checkpoint",     # HIL 检查点
            "report_gen",         # 报告生成
            # ... 更多阶段
        ]
        # 串联六层架构协作，生成可信证据包
```

## Layer 1: LLM 抽象层 (skyforge_llm)

提供统一的 LLM 接口，支持多种模型提供商。

### 模块结构

```
skyforge_llm/
├── providers/               # 模型提供商
│   ├── openai.py            # OpenAI 兼容
│   ├── anthropic.py         # Anthropic
│   └── local.py             # 本地模型(LM Studio)
├── security/                # 安全封装
│   ├── sanitizer.py         # 输入清理
│   └── auditor.py           # 审计日志
├── client.py                # 统一客户端
├── router.py                # 模型路由
└── cache.py                 # LLM 响应缓存
```

## Layer 2: CLI 工具 (skyforge_core)

提供命令行接口，方便开发者快速使用。

```bash
skyforge generate   # 代码生成
skyforge check      # 合规检查
skyforge simulate   # 数字孪生仿真
skyforge report     # 生成报告
```

## Layer 3: Web 工作室 (app + frontend)

### 后端 (FastAPI) - V1 任务协议

```
studio/app/
├── api/v1/                  # V1 唯一任务协议
│   ├── routes/
│   │   ├── tasks.py         #   POST /tasks (idempotency_key)
│   │   │                    #   GET /tasks/{task_id}
│   │   │                    #   GET /tasks
│   │   ├── task_events.py   #   WS /tasks/{task_id}/events?after_seq=N
│   │   ├── profiles.py      #   GET /execution-profiles
│   │   │                    #   GET /preflight/{profile}
│   │   └── recordings.py    #   GET /recordings
│   │                        #   GET /recordings/{id}
├── core/                     # 核心功能(HIL / LLM / Streaming)
├── services/                 # 服务层(Redis / WebSocket)
├── schemas/                  # Pydantic 数据模型
├── rag/                      # MISRA-C 检索
└── main.py                   # FastAPI 入口
```

#### V1 唯一任务协议接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/tasks` | 唯一创建入口，使用 idempotency_key |
| GET | `/api/v1/tasks/{task_id}` | 读取状态、完整产物与 provenance |
| GET | `/api/v1/tasks` | 运行记录列表 |
| WS | `/api/v1/tasks/{task_id}/events?after_seq=N` | 事件订阅，支持事件续传 |
| GET | `/api/v1/execution-profiles` | 执行 Profile 列表 |
| GET | `/api/v1/preflight/{profile}` | 可用性预检 |
| GET | `/api/v1/recordings` | 离线运行包列表 |
| GET | `/api/v1/recordings/{id}` | 核验并读取离线运行包 |

### 前端 (Vue 3) - 11 个页面

```
studio/frontend/src/
├── pages/                    # 路由页面（11个）
│   ├── Home.vue              #   比赛演示首页 (/)
│   ├── Architecture.vue      #   六层架构 (/architecture)
│   ├── Generate.vue          #   代码生成 (/generate)
│   ├── Records.vue           #   运行记录 (/records)
│   ├── RecordDetail.vue      #   回放模式 (/records/:taskId)
│   ├── Lab.vue               #   能力实验室 (/lab)
│   ├── Settings.vue          #   系统设置 (/settings)
│   ├── Demo.vue              #   比赛工作台 (/demo)
│   ├── Compose.vue           #   组件组合验证 (/compose)
│   ├── Misra.vue             #   MISRA 规则搜索 (/misra)
│   └── HITL.vue              #   HITL人工审查 (/hitl)
├── components/               # UI 组件
│   ├── TopStatusBar.vue      #   顶部状态栏
│   ├── NavBar.vue            #   顶部导航栏（6项）
│   ├── StatusDot.vue         #   状态指示灯
│   ├── StatCard.vue          #   KPI 统计卡片
│   ├── PipelineFlow.vue      #   Agent 流水线可视化
│   ├── AgentTerminal.vue     #   Agent 终端输出
│   ├── CodeViewer.vue        #   代码查看器
│   ├── SimulationResult.vue  #   仿真结果展示
│   └── ui/                   #   shadcn-vue 基础组件
├── services/                 # API 调用 + Mock 实现
├── router/                   # 路由配置(11 条路由)
└── utils/                    # 工具函数
```

#### 顶部导航栏（6个）

| 序号 | 名称 | 路由 |
|------|------|------|
| 1 | 比赛演示 | `/` |
| 2 | 六层架构 | `/architecture` |
| 3 | 代码生成 | `/generate` |
| 4 | 运行记录 | `/records` |
| 5 | 能力实验室 | `/lab` |
| 6 | 系统设置 | `/settings` |

## 数据流

### 代码生成流程

```
用户输入 → 需求解析 → 契约生成 → 代码生成 → 合规检查 → 报告生成
    │          │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼          ▼
  文本      JSON       YAML        C        HTML        PDF
```

### HITL 人工审查流程

```
Agent 决策 → 风险评估 → 人工审批 → 结果反馈 → 流程继续
    │          │          │          │
    ▼          ▼          ▼          ▼
  自动       高风险     需要审批    更新状态
```

## 技术栈

### 后端

| 技术 | 用途 |
|------|------|
| Python 3.12+ | 运行时 |
| FastAPI | Web 框架 |
| Pydantic | 数据验证 |
| Ruff | 代码检查 |
| unittest | 测试框架 |
| Loguru | 日志记录 |

### 前端

| 技术 | 用途 |
|------|------|
| Vue 3 | UI 框架 |
| TypeScript | 类型安全 |
| Vite | 构建工具 |
| Pinia | 状态管理 |
| Tailwind CSS | 样式框架 |
| shadcn-vue | UI 组件库 |
| Vitest | 测试框架 |
| Biome | 代码检查 |

### 基础设施

| 技术 | 用途 |
|------|------|
| Docker | 容器化 |
| Redis | 缓存/队列 |
| GitHub Actions | CI/CD |

## 执行模式 Profile

| 模式 | 类型 | 说明 |
|------|------|------|
| demo | 浏览器模拟 (simulated) | 完全离线，主演示用 |
| cloud | 云模型 (live) | 服务端实时执行 |
| local | 本地模型 (live/replay) | Ollama/LM Studio实时执行，支持已验证回放 |

## 术语约定

- **HITL** = 人工审查 (Human-in-the-Loop)
- **HIL** = 硬件在环 (Hardware-in-the-Loop)
- **证据规则**：observed / simulated / unavailable / failed

## 测试覆盖

- 后端/引擎/LLM 安全测试：593 pytest passed
- 前端测试：171 Vitest passed

## 性能优化

### 关键优化点

1. **并行处理**：Agent 可并行执行独立任务
2. **增量更新**：只重新生成受影响的部分
3. **缓存机制**：缓存 LLM 响应和中间结果
4. **懒加载**：按需加载非核心模块
5. **前端轮询降频 + 后台暂停**：4 个长轮询组件使用 `visibilitychange` API，页面切后台时停止轮询，切回前台立即刷新并恢复
6. **LLM 长任务超时**：generate / repair / generateReport 接口统一 3 分钟（180s）超时，兼容本地模型推理时间
7. **Windows 工具链兼容**：cppcheck MISRA addon 使用 `sys.executable` 调用 venv 内 Python，避免 Windows Store python stub 问题

### 前端轮询组件

| 组件 | 轮询周期 | 后台暂停策略 |
|------|----------|-------------|
| TopStatusBar（顶部状态栏） | 10s | visibilitychange 暂停 |
| Dashboard 系统状态 | 10s | visibilitychange 暂停 |
| HILPanel（HITL 倒计时） | 1s | visibilitychange 暂停 |

### 资源消耗

| 层级 | 内存占用 | 磁盘占用 |
|------|---------|---------|
| Layer 0 | ~50MB | ~80MB |
| Layer 1 | +20MB | +50MB |
| Layer 2 | +5MB | +5MB |
| Layer 3 | +100MB | +315MB |

## 扩展点

### 自定义编码标准

```python
from skyforge_engine.coding_standards.base import CodingStandard, get_registry

# 创建自定义编码标准
my_std = CodingStandard(
    id="my_custom_standard",
    name="My Custom Standard",
    language="c",
    version="1.0",
    red_line_rules=["R1", "R2"],
    fixers={"R1": my_fixer_func},
)

# 注册到全局 Registry
registry = get_registry()
registry.register(my_std)
```

### 自定义 Agent

```python
from skyforge_engine.agents.agent import BaseAgent

class CustomAgent(BaseAgent):
    def execute(self, input_data):
        # 自定义逻辑
        pass
```

### 自定义工具

```python
from skyforge_engine.tools import BaseTool

class CustomTool(BaseTool):
    def run(self, params):
        # 自定义工具逻辑
        pass
```

## 安全考虑

### 输入验证

- 所有用户输入都经过 Pydantic 验证
- LLM 输出经过安全检查和清理
- 防止注入攻击

### 权限控制

- API 密钥安全存储
- 角色基础的访问控制
- 操作审计日志

---

**版本**: v0.5.0
**更新日期**: 2026-07-21
