# SkyForge (天锻)

> **SkyForge** — AI 驱动的航空机载软件工程平台，面向 DO-178C 开发活动提供需求、代码、验证与追溯辅助证据；不宣称工具本身已完成适航鉴定。
> *AI-Powered Aviation Software Development Platform for DO-178C Compliance.*

**航空工业软件开源创新大赛** · 机上软件开发工具研发赛道 · 赛题二:AI 智能体驱动的机载软件轻量化开发工具

**多语言支持**: C / C++ / Python | **安全标准**: DO-178C Level A | **编码规范**: MISRA-C / MISRA C++ / JSF AV C++ / 军工Python指南

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Vue 3](https://img.shields.io/badge/Vue-3-42B883.svg?logo=vue.js&logoColor=white)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![DO-178C](https://img.shields.io/badge/DO--178C-Engineering%20Support-red.svg)](./docs/DO178C_COMPLIANCE_PACKAGE.md)
[![MISRA-C:2012](https://img.shields.io/badge/MISRA--C-2012-AutoFix-orange.svg)](./docs/DO178C_COMPLIANCE_PACKAGE.md)
[![Z3](https://img.shields.io/badge/Formal-Z3-purple.svg)](./src/skyforge_engine/tools/z3_verifier.py)
[![CBMC](https://img.shields.io/badge/Verify-CBMC-teal.svg)](./src/skyforge_engine/tools/cbmc_verifier.py)
[![Multi-Agent](https://img.shields.io/badge/Multi--Agent-8%2B-green.svg)](#-multi-agent-协同管道)

---

## 📊 当前可复现状态

| 指标 | 数值 | 校准来源 |
|------|------|----------|
| 后端 / 引擎 / LLM 安全测试 | **596 pytest passed；11 subtests passed** | `uv run pytest -q`，2026-07-21 |
| 前端测试与构建 | **172 Vitest passed；生产构建通过；4 E2E passed** | `pnpm test && pnpm build && pnpm test:e2e`，2026-07-21 |
| DO-178C 目标检查 | 工程辅助检查，不等同于适航符合性结论 | `src/skyforge_engine/report/do178_objectives.py` |
| MISRA-C 自动修复规则 | **57** 条 | `docs/PROJECT_REVIEW.md`(175 条中可自动修复 33%) |
| 编码标准插件 | **3** 个 | `src/skyforge_engine/coding_standards/`(MISRA-C / JSF AV C++ / Python) |
| Multi-Agent 协同管道 | **8+** 个 | `src/skyforge_engine/agents/*.py` |
| API / 测试数量 | 禁止手填；由代码与测试报告生成 | `tools/scripts/generate_project_metrics.py` |
| 基准测试示例 | **12 / 12**(100%) | `docs/benchmark/benchmark_report.md` |
| 故障注入类型 | **12** 类 | `src/skyforge_engine/digital_twin/fault_injector.py` |
| 契约模板数 | **17** 个 | `studio/frontend/src/utils/contractTemplates.ts` |
| DO-178C 合规文档 | **9** 份 | `docs/DO178C_COMPLIANCE_PACKAGE.md` |
| 比赛离线演示时间线 | **约 4.5 秒**（页面演示节奏，可继续调速） | `studio/frontend/src/services/taskGateway.ts` |
| 源代码规模 | 禁止手填；由自动化指标报告生成 | `tools/scripts/generate_project_metrics.py` |

---

## 🏗️ 架构概览

SkyForge 采用**六层引擎架构**(Layer 0-5),自底向上逐层增强,每一层职责清晰,可独立部署与替换。

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 5: Orchestration (编排层)                                  │  ← Pipeline 全流程调度
│  - PipelineOrchestrator: 串行/并行组/失败策略/产物传递           │
│  - 12 个 Stage: 需求解析→LLR→架构→契约→代码→修复→验证→仿真→报告 │
├──────────────────────────────────────────────────────────────────┤
│  Layer 4: Agent Strategy (Agent 策略层)                           │  ← 多 Agent 协同
│  - 8+ Agent: 需求解析/LLR生成/架构设计/契约生成/代码生成/修复     │
│  - MISRA 适配 / Python 适配 / 多语言代码生成                      │
├──────────────────────────────────────────────────────────────────┤
│  Layer 3: Verifier Chain (验证工具链层)                            │  ← 形式化与静态分析
│  - Z3 / CBMC / Cppcheck / GCC / Contract Checker 可插拔链        │
│  - VerifierChain: 多验证器编排与结果聚合                          │
├──────────────────────────────────────────────────────────────────┤
│  Layer 2: HIL Adapter (HIL 适配器层)                              │  ← 硬件在环与数字孪生
│  - QEMU / 串口 / ARINC 653 适配器                                 │
│  - 数字孪生: 虚拟传感器 / 虚拟 MCU / 故障注入 / 仿真引擎          │
├──────────────────────────────────────────────────────────────────┤
│  Layer 1: LLM Client (LLM 客户端层)                               │  ← LLM 适配与路由
│  - Mock / 云 API / 本地 OpenAI 兼容客户端                         │
│  - 多供应商路由 / 缓存 / 安全审计 / 输入输出清洗                  │
├──────────────────────────────────────────────────────────────────┤
│  Layer 0: Protocols (基础设施协议层)                               │  ← 协议/抽象基类/模式守卫
│  - Protocol 抽象基类 / 数据模式 / 类型守卫                        │
│  - 跨层依赖反转: Provider 注入模式                                │
└──────────────────────────────────────────────────────────────────┘
```

> 详见 [系统工程审计](./docs/SYSTEM_ENGINEERING_AUDIT_2026-07-19.md) | [架构详解](./docs/ARCHITECTURE.md) | [插件开发](./docs/PLUGIN_DEVELOPMENT.md)

---

## 🚀 快速开始(3 步走)

### 方式一：一键部署（推荐）

```bash
# Windows Git Bash / Linux / macOS
sh start.sh
```

### 方式二：手动部署

```bash
# 第 1 步:安装依赖(推荐 uv,也可用 pip)
cd SkyForge
uv sync                          # 使用 uv workspace(推荐)
# 或
pip install -e ".[dev]"

# 第 2 步:启动后端 + 前端(一键启动)
make dev                         # 启动 FastAPI (8000) + Vite (5173)
# 若无 make 环境,Linux/Mac 可直接: bash start.sh

# 第 3 步:浏览器访问
# 前端 UI:         http://localhost:5173
# API 文档(Swagger): http://localhost:8000/docs
```

### 方式三：Docker 部署

```bash
# Docker Compose 一键部署
docker compose up --build

# 或使用开发模式（支持热重载）
docker compose -f docker-compose.dev.yml up
```

> 💡 **演示模式开箱即用且完全离线**。界面和报告始终标记为 `simulated`；外部工具缺失不会被解释为“零违规”或“验证通过”。

### 🧰 工具链安装（可选,Mock 模式无需安装）

`start.sh` 启动时会自动检测下列工具,缺失时打印安装提示。新用户首次启动会自动 `pip install z3-solver`。

| 工具 | 用途 | Linux/macOS | Windows |
|------|------|-------------|---------|
| **z3-solver** | 契约形式化验证(SMT) | `pip install z3-solver`(`start.sh` 自动) | `pip install z3-solver`(`start.sh` 自动) |
| **cbmc** | C 代码有界模型检查 | `apt install cbmc` / `brew install cbmc` | 双击 `tools/cbmc-6.9.0-win64.msi`(管理员权限,装到 `C:\Program Files\cbmc\bin\`) |
| **cppcheck** | MISRA-C 静态扫描 | `apt install cppcheck` | `choco install cppcheck` 或官方安装包 |
| **gcc** | 代码编译 / 覆盖率插桩 | 系统自带 | MinGW / MSYS2 |

> 后端 z3 检测使用 `import z3`(Python 包);cbmc 检测优先 `shutil.which`,Windows 上额外检查 `C:\Program Files\cbmc\bin\cbmc.exe`。
> cppcheck MISRA addon 在 Windows 上使用 `sys.executable`(venv 内 Python)而非 `shutil.which("python")`,避免 Windows Store 的 python stub(exitcode 9009)问题。

### 🛡️ Mock 模式:优雅降级策略

在 `config/.env` 设置 `SKYFORGE_LLM_MODE=mock` 即可启用 Mock 模式；云 API 与本地模型分别使用 `api` / `local`。Pipeline 启动时会打印当前 LLM 模式与来源，便于确认。

| 外部依赖 | 缺失时降级方案 | 实现位置 |
|----------|----------------|----------|
| LLM (LM Studio / OpenAI / Anthropic) | 关键词匹配 + 模板拼接 | `src/skyforge_llm/local.py` |
| GCC 编译器 | 标记 `simulated` 或 `unavailable`，不记录真实编译通过 | `src/skyforge_engine/digital_twin/virtual_mcu.py` |
| Cppcheck 静态扫描 | 模式扫描标记 `simulated`；无扫描器则 `unavailable` | `src/skyforge_engine/tools/cppcheck_scanner.py` |
| Z3 / CBMC 形式化验证 | 跳过并标记 `unavailable`，绝不生成 Mock 通过 | `src/skyforge_engine/tools/contract_formal_verifier.py` |
| Redis 任务队列 | 内存队列回退 | `studio/app/services/redis_manager.py` |

> Mock 模式仅作为降级方案,不代表项目的 AI 能力。运行日志中会出现 `[Mock]` 标记,表示该 Agent 未使用 LLM。详见 [部署说明](./docs/USER_GUIDE.md)。

### 🤝 HITL 人工审查

HITL (Human-in-the-Loop) 在需求、契约和代码检查点等待人工决定。`HIL` 仅表示 Hardware-in-the-Loop。

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `HIL_ENABLED` 环境变量 | **`false`** | `start.sh` 默认禁用,避免阻塞自动化流程 |
| `POST /api/hil/toggle` | — | 兼容路径：运行时切换 HITL 启用状态（无需重启后端） |
| `GET /api/hil/pending` | — | 兼容路径：查询待人工审查任务与 HITL 状态 |
| Generate 页面 HITL 开关 | 隐藏(mock)/ 关(local·api) | “开始生成”按钮左侧的 UserCheck 图标按钮，关=灰色 / 开=琥珀色 |

> 旧 `/api/hil/*` 路径保留一版兼容；新产品文案和页面统一使用 HITL。

### ⚡ 比赛版前端

首页与比赛工作台不再轮询后端。演示 profile 使用浏览器内 `DemoTaskGateway`，首页、运行记录与 HITL 页面在后端关闭时仍可工作。

| 组件 | 轮询周期 | 文件 |
|------|----------|------|
| TopStatusBar(顶部状态栏) | 10s | `studio/frontend/src/components/TopStatusBar.vue` |
| Dashboard(仪表盘系统状态) | 10s | `studio/frontend/src/pages/dashboard/index.vue` |
| HILPanel（HITL 审查倒计时，文件名兼容保留） | 1s | `studio/frontend/src/components/HILPanel.vue` |
| LLM 长任务超时 | 180s | `studio/frontend/src/services/api.ts`(`LLM_LONG_TIMEOUT_MS`) |

> 顶部状态栏使用 8s HTTP 超时 + 10s 轮询,避免 LLM 阻塞期间健康检查堆积;LLM 生成 / 修复 / 报告接口统一 3 分钟超时,兼容本地模型推理时间。

---

## 🏆 比赛评分维度对照

| 评分维度 | 分值 | 对应能力 | 详见章节 |
|----------|------|----------|----------|
| **创新性** | 30 | Multi-Agent 协同、DO-178C 工程辅助证据、形式化验证、数字孪生故障注入、HITL 人工审查 | [架构概览](#-架构概览) · [Multi-Agent](#-multi-agent-协同管道) |
| **赛道契合度** | 25 | 商飞产业需求、ARINC 653 分区调度、FreeRTOS 任务调度、SCADE G-Lustre 集成 | [产业应用案例](./docs/COMPETITION_EDITION.md) · [ARINC 653 示例](./examples/arinc653_partition/) |
| **落地可行性** | 25 | 六层引擎架构、Mock 降级策略、12 个基准测试全过、Docker 一键部署 | [基准报告](./docs/benchmark/benchmark_report.md) · [部署说明](./docs/USER_GUIDE.md) |
| **应用价值** | 20 | 效率提升 6-12x、人力节约 70-75%、年成本节约 70-75%、ROI 量化 | [效率数据](./docs/PROJECT_REVIEW.md) · [竞品对比](./docs/PROJECT_REVIEW.md) |

---

## 📁 目录结构

```
SkyForge/
├── README.md                          ← 你正在看的文件
├── LICENSE                            ← MIT License
├── ThirdParty.md                      ← 第三方组件说明(根目录)
├── Makefile                           ← 一键命令入口(dev/test/lint/benchmark)
├── pyproject.toml                     ← Python 项目配置(uv workspace)
├── start.sh                            ← 一键启动脚本
│
├── src/                               ← 源代码(六层引擎架构)
│   ├── skyforge_engine/               ← 核心引擎(L0-L5 引擎层)
│   │   ├── core/                      ←   L5 编排层: orchestrator.py, stages/(12个阶段)
│   │   ├── agents/                    ←   L4 Agent策略层: 8+ Agent (需求/LLR/架构/契约/代码/修复等)
│   │   ├── verifiers/                 ←   L3 验证工具链层: VerifierChain + Z3/CBMC/Cppcheck/GCC
│   │   ├── adapters/                  ←   L2 HIL适配器层: QEMU/串口/ARINC653/数字孪生
│   │   ├── protocols/                 ←   L0 协议层: 抽象基类/模式守卫/Provider协议
│   │   ├── strategies/                ←   LLM策略: Mock策略/云API策略/本地策略
│   │   ├── standards/                 ←   可插拔编码标准(MISRA-C / MISRA C++ / Python)
│   │   ├── renderers/                 ←   报告渲染器
│   │   ├── coding_standards/          ←   编码标准插件(MISRA-C / JSF AV C++ / Python)
│   │   ├── tools/                     ←   工具链(Cppcheck / Z3 / CBMC / Contract)
│   │   ├── digital_twin/              ←   数字孪生(虚拟传感器/MCU/故障注入/仿真引擎)
│   │   ├── composable/                ←   组件组合验证
│   │   ├── rag/                       ←   RAG知识库(MISRA-C语义搜索)
│   │   ├── report/                    ←   DO-178C报告 + 19项合规目标
│   │   ├── scade/                     ←   SCADE G-Lustre解析器(ANTLR4)
│   │   ├── dal/                       ←   DAL目标覆盖(gcov/mcdc)
│   │   ├── streaming/                 ←   流处理: 任务流注册表
│   │   ├── schemas/                   ←   数据模型
│   │   ├── tests/                     ←   引擎单元测试
│   │   ├── pipeline.py                ←   Pipeline 编排入口
│   │   └── execution.py               ←   ExecutionProfile / ExecutionContext
│   │
│   ├── skyforge_llm/                  ← L1 LLM客户端层 ⭐ 可选剥离
│   │   ├── providers/                 ←   OpenAI / Anthropic / 本地
│   │   ├── security/                  ←   输入清洗 + 审计 + 验证
│   │   ├── client.py                  ←   统一LLM客户端
│   │   ├── router.py                  ←   多供应商路由
│   │   ├── cache.py                   ←   LLM响应缓存
│   │   ├── local.py                   ←   本地GGUF模型
│   │   └── types.py                   ←   类型定义
│   │
│   └── skyforge_core/                 ← CLI 工具 ⭐ 命令行入口
│       └── cli.py
│
├── studio/                            ← Web Studio (FastAPI + Vue 3)
│   ├── app/                           ← FastAPI 后端
│   │   ├── api/routes/                ←   API路由(兼容API + V1唯一任务协议)
│   │   ├── services/                  ←   服务层(Redis + WebSocket管理)
│   │   ├── core/                      ←   核心层(HITL / LLM / Streaming)
│   │   ├── schemas/                   ←   Pydantic数据模型
│   │   ├── rag/                       ←   MISRA-C检索
│   │   ├── tests/                     ←   FastAPI/任务协议/设置/回归测试
│   │   └── main.py                    ←   FastAPI入口
│   └── frontend/                      ← Vue 3 前端
│       ├── src/
│       │   ├── pages/                 ←   路由页面(11个页面)
│       │   │   └── dashboard/         ←     比赛演示首页(/)
│       │   ├── views/                 ←   页面视图(Generate / Compose / HITLPage / Demo / Records / Lab / Settings / ArchitectureView)
│       │   ├── components/            ←   40+ UI组件 + shadcn-vue
│       │   ├── stores/                ←   Pinia状态(5个store)
│       │   ├── services/              ←   API调用 + Mock + 任务网关
│       │   └── utils/                 ←   工具函数 + 契约模板
│       ├── package.json
│       └── Dockerfile
│
├── docs/                              ← 文档中心
│   ├── README.md                      ← 文档索引
│   ├── ARCHITECTURE.md                ← 架构详解
│   ├── ROADMAP.md                     ← 项目路线图
│   ├── PLUGIN_DEVELOPMENT.md          ← 插件开发指南
│   ├── compliance/                    ← DO-178C合规文档(9份)
│   ├── user/                          ← 用户文档(教程 / 部署 / 测试报告)
│   ├── review/                        ← 评审分析(竞品 / 效率 / 差距)
│   ├── benchmark/                     ← 性能基准报告
│   ├── verification/                  ← LLM / 工具链验证报告
│   └── images/                        ← 截图资源
│
├── examples/                          ← 示例代码库(12 + 2完整案例)
├── tools/                             ← 工具脚本(安装/演示/基准/一键启动)
├── config/                            ← 集中配置(.env/pyright)
├── docker/                            ← Docker部署
└── .github/                           ← CI/CD工作流
```

### 前端路由(11个页面)

| 路径 | 页面 | 文件 |
|------|------|------|
| `/` | 比赛演示首页 | `pages/dashboard/index.vue` |
| `/architecture` | 六层架构 | `views/ArchitectureView.vue` |
| `/generate` | 代码生成 | `views/Generate.vue` |
| `/records` | 运行记录 | `views/RunRecords.vue` |
| `/records/:taskId` | 回放模式 | `views/RunRecords.vue` |
| `/lab` | 能力实验室 | `views/CapabilityLab.vue` |
| `/settings` | 系统设置 | `views/SystemSettings.vue` |
| `/demo` | 比赛工作台 | `views/CompetitionDemo.vue` |
| `/compose` | 组件组合验证 | `views/Compose.vue` |
| `/misra` | MISRA规则搜索 | `pages/misra/index.vue` |
| `/hitl` | HITL人工审查 | `views/HITLPage.vue` |

### 顶部导航栏(6个)

1. 比赛演示 (`/`)
2. 六层架构 (`/architecture`)
3. 代码生成 (`/generate`)
4. 运行记录 (`/records`)
5. 能力实验室 (`/lab`)
6. 系统设置 (`/settings`)

### 三种执行模式 Profile

| Profile | 模式 | 说明 |
|---------|------|------|
| `demo` | simulated | 浏览器模拟,完全离线可用 |
| `cloud` | live | 云模型,后端真实运行 |
| `local` | live/replay | 本地模型,支持已验证回放 |

### 证据状态规则

统一使用四种证据状态:`observed` / `simulated` / `unavailable` / `failed`

| 状态 | 含义 |
|------|------|
| `observed` | 真实工具观测结果 |
| `simulated` | Mock/模拟结果,非真实验证 |
| `unavailable` | 工具缺失,跳过验证 |
| `failed` | 验证失败/违规 |

---

## 🔌 REST API 概览

端点数量以自动生成报告为准，完整接口文档见 http://localhost:8000/docs。

| 模块 | 端点数 | 路由文件 | 代表接口 |
|------|--------|----------|----------|
| 健康检查 + 统计 | 2 | `routes/common.py` | `GET /api/health` · `GET /api/stats` |
| V1 代码生成任务 | 动态统计 | `routes/tasks_v1.py` | `POST /api/v1/tasks` · `WS /api/v1/tasks/{id}/events` |
| 兼容生成 + 修复 + 仿真 + 验证 | 7 | `routes/pipeline.py` | `POST /api/generate` · `POST /api/repair` · `POST /api/simulate` |
| DO-178C 报告 | 2 | `routes/reports.py` | `POST /api/report` · `GET /api/report/download` |
| 组件组合验证 | 2 | `routes/composition.py` | `POST /api/compose` · `POST /api/check-compatibility` |
| HITL 人工审查 | 5 | `routes/hitl.py` | `GET /api/hil/pending` · `POST /api/hil/approve` · `POST /api/hil/toggle` |
| 模型管理 + MISRA 规则检索 | 9 | `routes/models.py` | `GET /api/models` · `GET /api/misra/rules` |
| 兼容 WebSocket | 2 | `routes/generate.py` / `routes/task_ws.py` | `/ws/agent-stream` · `/task/{task_id}` |

完整 API 列表与参数说明参见 [部署说明](./docs/USER_GUIDE.md)。

---

## 🛡️ DO-178C 合规状态

SkyForge 提供 DO-178C 工程辅助证据，不宣称工具本身已经完成适航鉴定。合规草案详见 [DO-178C 合规包](./docs/DO178C_COMPLIANCE_PACKAGE.md)。

### 五大核心过程覆盖

| DO-178C 过程 | 章节 | 文档 | 状态 |
|-------------|------|------|------|
| **计划过程** | §4 | [PSAC](./docs/DO178C_COMPLIANCE_PACKAGE.md) / [SDP](./docs/DO178C_COMPLIANCE_PACKAGE.md) / [SVP](./docs/DO178C_COMPLIANCE_PACKAGE.md) | ✅ 已完成 (8/8 文档) |
| **开发过程** | §5 | HLR / LLR 层级 + 契约式设计 + MISRA-C 代码生成 | ✅ 已完成 (HLR→LLR→Code→Contract 全链路) |
| **验证过程** | §6 | Cppcheck + 契约校验 + 数字孪生 + V3.3 覆盖分析器 | ✅ 已完成 (语句/判定/MC/DC 三级覆盖) |
| **配置管理** | §7 | [SCMP](./docs/DO178C_COMPLIANCE_PACKAGE.md) + Git + PR 系统 + 基线管理 | ✅ 已完成 |
| **质量保证** | §8 | [SQAP](./docs/DO178C_COMPLIANCE_PACKAGE.md) + CI 自动检查 (Ruff/Biome/Pyright) | ✅ 已完成 |

### DAL 等级目标覆盖

DO-178C 共 **19 项可判定目标**(OBJ-1 ~ OBJ-19),涵盖问题报告、配置标识、追溯矩阵、语句 / 判定 / MC/DC 覆盖、HLR/LLR 追溯、独立验证、正式 PR、工具鉴定等。代码实现见 [`src/skyforge_engine/report/do178_objectives.py`](./src/skyforge_engine/report/do178_objectives.py)。

| DAL | 等级含义 | 目标满足率 | 关键要求 | 实现位置 |
|-----|---------|-----------|----------|---------|
| A | 灾难性 | 18/19 (95%) | MC/DC 必须 | `mcdc_calculator.py` (V3.3-Enhanced) |
| B | 危险 | 18/18 (100%) | 判定覆盖必须 | `coverage_analyzer.py` |
| C | 重大 | 16/16 (100%) | 语句覆盖必须 | `coverage_analyzer.py` |
| D | 轻微 | 13/13 (100%) | 基础验证 | 全流程覆盖 |

> 19 项 OBJ 中,仅 OBJ-17 (独立验证) 仍为部分满足,需非作者团队人工审查 (Phase 4 闭环)。
> 完整合规矩阵详见 [`COMPLIANCE_MATRIX.csv`](./docs/COMPLIANCE_MATRIX.csv) (19 OBJ × 5 DAL)。

### 工具鉴定(TQL)

| 工具 | TQL 级别 | 状态 | 文档 |
|------|---------|------|------|
| Agent Pipeline | TQL-1 | ✅ 草案完成 | [TQP](./docs/DO178C_COMPLIANCE_PACKAGE.md) |
| LLM 推理引擎 | TQL-1 | ✅ 草案完成 | [TOR](./docs/DO178C_COMPLIANCE_PACKAGE.md) |
| Contract Checker | TQL-2 | ✅ 草案完成 | [TAS](./docs/DO178C_COMPLIANCE_PACKAGE.md) |
| 工具链验证 | — | ✅ 已实施 | [`tool_chain_validator.py`](./src/skyforge_engine/tools/tool_chain_validator.py) |
| Cppcheck / GCC | TQL-3 / TQL-1 | 可引用已有 | 工业标准工具 |

```bash
# 运行 DO-178C 合规检查
make do178c-check
```

---

## 📚 文档导航

| 文档 | 路径 | 用途 |
|------|------|------|
| **使用教程** | [docs/user/使用教程.md](./docs/USER_GUIDE.md) | 功能模块详解与操作指南 |
| **部署说明** | [docs/user/部署说明.md](./docs/USER_GUIDE.md) | 环境配置与 API 接口文档 |
| **测试报告** | [docs/user/测试报告.md](./docs/USER_GUIDE.md) | 测试覆盖与质量评估 |
| **架构详解** | [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | 四层架构设计深度剖析 |
| **系统工程审计** | [docs/SYSTEM_ENGINEERING_AUDIT_2026-07-19.md](./docs/SYSTEM_ENGINEERING_AUDIT_2026-07-19.md) | 比赛版任务协议、执行来源与风险口径 |
| **基准报告** | [docs/benchmark/benchmark_report.md](./docs/benchmark/benchmark_report.md) | 12 个示例性能基准 |
| **效率数据** | [docs/PROJECT_REVIEW.md](./docs/PROJECT_REVIEW.md) | ROI 与效率提升量化 |
| **竞品分析** | [docs/review/竞品对比分析.md](./docs/PROJECT_REVIEW.md) | vs SCADE Suite / Polyspace |
| **差距分析** | [docs/review/比赛要求差距分析.md](./docs/PROJECT_REVIEW.md) | 比赛要求差距与对策 |
| **产业案例** | [docs/industry/产业应用案例.md](./docs/COMPETITION_EDITION.md) | 商飞产业需求对接 |
| **LLM / 回放验证** | [docs/verification/LLM验证报告.md](./docs/VERIFICATION_REPORT.md) | 云 API、本地模型与已验证运行包口径 |
| **项目路线图** | [docs/ROADMAP.md](./docs/ROADMAP.md) | 后续规划 |
| **插件开发** | [docs/PLUGIN_DEVELOPMENT.md](./docs/PLUGIN_DEVELOPMENT.md) | 二次开发扩展指南(含编码标准插件) |
| **多语言支持** | [docs/MULTI_LANGUAGE_GUIDE.md](./docs/MULTI_LANGUAGE_GUIDE.md) | C/C++/Python 多语言支持指南 |

---

## 📦 第三方组件

**Python 后端**:
[FastAPI](https://fastapi.tiangolo.com/) · [Pydantic](https://docs.pydantic.dev/) · [Redis](https://redis.io/) · [PyYAML](https://pyyaml.org/) · [Z3 Solver](https://github.com/Z3Prover/z3) · [psutil](https://psutil.readthedocs.io/) · [httpx](https://www.python-httpx.org/) · [loguru](https://loguru.readthedocs.io/) · [click](https://click.palletsprojects.com/) · [numpy](https://numpy.org/) · [uvicorn](https://www.uvicorn.org/) · [websockets](https://websockets.readthedocs.io/)

**Frontend**:
[Vue 3](https://vuejs.org/) · [Vite](https://vitejs.dev/) · [Pinia](https://pinia.vuejs.org/) · [Vue Router](https://router.vuejs.org/) · [shadcn-vue](https://www.shadcn-vue.com/) · [Tailwind CSS](https://tailwindcss.com/) · [Radix Vue](https://www.radix-vue.com/) · [Vitest](https://vitest.dev/) · [Biome](https://biomejs.dev/)

**外部工具**(可选,缺失时自动降级为 Mock):
[Cppcheck](https://cppcheck.sourceforge.io/) · [GCC](https://gcc.gnu.org/) · [CBMC](https://www.cprover.org/cbmc/) · [LM Studio](https://lmstudio.ai/)

完整第三方组件清单(含许可证信息):
- 📄 [ThirdParty.md(根目录)](./ThirdParty.md)
- 📁 [docs/thirdparty/](./docs/thirdparty/)

---

## 📄 许可证

本项目采用 [**MIT License**](./LICENSE) 开源协议。

Copyright (c) 2026 SkyForge Contributors

---

## 💬 联系与反馈

| 渠道 | 地址 |
|------|------|
| **AtomGit 仓库** | [atomgit.com/gcw_TTqe9ALQ/SkyForge](https://atomgit.com/gcw_TTqe9ALQ/SkyForge) |
| **GitHub 仓库** | [github.com/linskadi/SkyForge](https://github.com/linskadi/SkyForge) |
| **比赛官方邮箱** | kefu@jsopen.org.cn |
| **项目路线图** | [docs/ROADMAP.md](./docs/ROADMAP.md) |

### 比赛信息

- **赛事**: 航空工业软件开源创新大赛
- **赛道**: 机上软件开发工具研发
- **赛题**: 二 — AI 智能体驱动的机载软件轻量化开发工具
- **AtomGit 仓库**: https://atomgit.com/gcw_TTqe9ALQ/SkyForge
- **GitHub 仓库**: https://github.com/linskadi/SkyForge

---

### 🎯 项目创新点

1. **六层引擎架构** — 从基础设施协议到编排层，每层职责清晰、可独立部署替换
2. **多 Agent 协同架构** — 8+ Agent 闭环,从需求到修复全自动
3. **DO-178C 工程辅助** — 生成工程报告与需求追溯矩阵，提供 19 项可判定目标检查，不替代适航审定
4. **MISRA-C 智能修复** — Cppcheck 扫描 + Agent 智能修复 + 契约校验闭环(57 条自动修复规则)
5. **可插拔编码标准** — Registry 插件化架构,支持 MISRA-C / MISRA C++ / Python 安全标准动态注册
6. **形式化验证** — Z3 SMT 求解 + CBMC 模型检测双引擎,VerifierChain 可插拔验证链
7. **数字孪生仿真** — 虚拟传感器 / MCU + 5 类故障注入测试(bias / signal_loss / noise / stuck / step)
8. **HITL 人工审查** — Redis-based 关键检查点人工审批工作流，默认禁用，可通过 UI 或兼容 API 开启；HIL 仅指真实硬件在环
9. **SCADE 集成** — ANTLR4 解析 G-Lustre 模型自动转需求与契约
10. **Pipeline 编排系统** — PipelineOrchestrator 支持串行执行、并行组、失败策略、产物传递，12 个 Stage 全流程调度

---

> **SkyForge** — *Forging the Future of Aviation Software, One Agent at a Time.* 🛩️
