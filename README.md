# SkyForge (天锻)

> **SkyForge** — AI 驱动的航空机载软件开发平台,覆盖 DO-178C 适航认证全流程,从需求到代码自动生成。
> *AI-Powered Aviation Software Development Platform for DO-178C Compliance.*

**航空工业软件开源创新大赛** · 机上软件开发工具研发赛道 · 赛题二:AI 智能体驱动的机载软件轻量化开发工具

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Vue 3](https://img.shields.io/badge/Vue-3-42B883.svg?logo=vue.js&logoColor=white)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![DO-178C](https://img.shields.io/badge/DO--178C-Compliant-red.svg)](./docs/compliance/PSAC.md)
[![MISRA-C:2012](https://img.shields.io/badge/MISRA--C-2012-AutoFix-orange.svg)](./docs/compliance/CODING_STANDARD.md)
[![Z3](https://img.shields.io/badge/Formal-Z3-purple.svg)](./src/skyforge_engine/tools/z3_verifier.py)
[![CBMC](https://img.shields.io/badge/Verify-CBMC-teal.svg)](./src/skyforge_engine/tools/cbmc_verifier.py)
[![Multi-Agent](https://img.shields.io/badge/Multi--Agent-6-green.svg)](#-multi-agent-协同管道)

---

## 📊 关键指标

| 指标 | 数值 | 校准来源 |
|------|------|----------|
| 后端测试通过 | **204** ✅ | `studio/app/tests/`(13 个测试文件,`def test_*` 统计) |
| 前端测试通过 | **116** ✅ | `studio/frontend/src/**/*.test.ts`(8 个测试文件,`it()` 统计) |
| DO-178C 合规目标 | **19/19 ✅** | `src/skyforge_engine/report/do178_objectives.py`(OBJ-1 ~ OBJ-19) |
| MISRA-C 自动修复规则 | **57** 条 | `docs/review/量化效率数据.md`(175 条中可自动修复 33%) |
| Multi-Agent 协同管道 | **6** 个 | `src/skyforge_engine/agents/*.py` |
| REST API 端点 | **26** 个 | `studio/app/api/routes/*.py`(`@router.*` 装饰器) |
| WebSocket 端点 | **2** 个 | `studio/app/api/routes/task_ws.py` |
| 基准测试示例 | **12 / 12**(100%) | `docs/benchmark/benchmark_report.md` |
| 故障注入类型 | **5** 类 | `src/skyforge_engine/digital_twin/fault_injector.py` |
| 契约模板数 | **17** 个 | `studio/frontend/src/utils/contractTemplates.ts` |
| DO-178C 合规文档 | **9** 份 | `docs/compliance/*.md` |
| 全流程响应时间(Mock) | **15-20 秒** | `docs/review/量化效率数据.md` |
| 代码行数 | **50,000+** | Python + TypeScript |

---

## 🏗️ 架构概览

SkyForge 采用**四层可剥离架构**(Layer 0-3),每一层均可独立部署,适配从机载轻量到云端全栈的不同场景。

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 3: SkyForge Studio  (FastAPI + Vue 3 + WebSocket)         │  ← Web UI + REST API
│  - Vue 3 + Vite + Pinia + shadcn-vue + Tailwind CSS              │
│  - FastAPI + WebSocket + Redis(任务队列 / HIL 人机协作)           │
├──────────────────────────────────────────────────────────────────┤
│  Layer 2: SkyForge Core  (Multi-Agent Pipeline)                  │  ← 业务编排
│  RequirementParser → LLRGenerator → ArchitectureDesigner         │
│     → ContractGenerator → CodeGenerator → CodeRepairer           │
├──────────────────────────────────────────────────────────────────┤
│  Layer 1: SkyForge LLM  (LLM Adapter)                            │  ← LLM 适配
│  - Qwen / Gemma / LM Studio / OpenAI / Anthropic / Mock 多供应商  │
├──────────────────────────────────────────────────────────────────┤
│  Layer 0: SkyForge Engine  (Core Engine)                         │  ← 核心引擎
│  - DO-178C Compliance Checker (OBJ-1 ~ OBJ-19)                   │
│  - MISRA-C Static Analyzer (Cppcheck 集成)                       │
│  - Contract Formal Verifier (Z3 + CBMC)                          │
│  - Digital Twin Simulator (5 类故障注入: bias / signal_loss ...)  │
│  - HIL Human Collaboration (Redis-based 审批工作流)               │
│  - SCADE G-Lustre Parser (ANTLR4)                                │
└──────────────────────────────────────────────────────────────────┘
```

### 🤖 Multi-Agent 协同管道

| # | Agent | 职责 | 输出 |
|---|-------|------|------|
| 1 | `RequirementParserAgent` | 自然语言需求解析为结构化 JSON | `requirement.json` |
| 2 | `LLRGeneratorAgent` | HLR → LLR 低层需求生成 | `llr.json` |
| 3 | `ArchitectureDesigner` | 模块划分 + 状态机设计 | `architecture.json` |
| 4 | `ContractGeneratorAgent` | 生成 DO-178C 合规契约 YAML | `contract.yaml` |
| 5 | `CodeGeneratorAgent` | 契约 → MISRA-C 风格 C 代码 | `output.c` |
| 6 | `CodeRepairerAgent` | Cppcheck 扫描 + Agent 智能修复闭环 | `repaired.c` |

### 📦 层级剥离指南

| 部署场景 | 安装命令 | 大小 | 关键依赖 |
|----------|----------|------|----------|
| 机载轻量部署 | `pip install skyforge-engine` | ~80MB | pyyaml, numpy, loguru, packaging |
| + 云端 LLM 增强 | `pip install skyforge-llm` | +50MB | httpx, openai, anthropic |
| + 命令行开发 | `pip install skyforge-core` | +5MB | click |
| + Web 演示 | `docker compose up` | +315MB | FastAPI, Vue 3, Redis |
| 嵌入式编译 | `nuitka skyforge_engine` | → <15MB 单文件 | — |

详见 [架构详解](./docs/ARCHITECTURE.md)。

---

## 🚀 快速开始(3 步走)

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

> 💡 **Mock 模式开箱即用,无需 LLM / GCC / Cppcheck / Z3 / CBMC**。所有外部工具缺失时仍可完整演示端到端流程。

### 🛡️ Mock 模式:优雅降级策略

在 `config/.env` 设置 `USE_LLM=false` 即可启用 Mock 模式。Pipeline 启动时会打印 `[Pipeline] 使用 Mock 模式` 或 `[Pipeline] 使用真实 LLM` 便于确认。

| 外部依赖 | 缺失时降级方案 | 实现位置 |
|----------|----------------|----------|
| LLM (LM Studio / OpenAI / Anthropic) | 关键词匹配 + 模板拼接 | `src/skyforge_llm/local.py` |
| GCC 编译器 | 跳过编译,返回 Mock 输出 | `src/skyforge_engine/tools/` |
| Cppcheck 静态扫描 | 返回 Mock 违规列表 | `src/skyforge_engine/tools/cppcheck_scanner.py` |
| Z3 / CBMC 形式化验证 | 跳过验证,返回 Mock 通过 | `src/skyforge_engine/tools/z3_verifier.py` |
| Redis 任务队列 | 内存队列回退 | `studio/app/services/redis_manager.py` |

> Mock 模式仅作为降级方案,不代表项目的 AI 能力。运行日志中会出现 `[Mock]` 标记,表示该 Agent 未使用 LLM。详见 [部署说明](./docs/user/部署说明.md)。

---

## 🏆 比赛评分维度对照

| 评分维度 | 分值 | 对应能力 | 详见章节 |
|----------|------|----------|----------|
| **创新性** | 30 | Multi-Agent 协同、DO-178C 自动合规、形式化验证 (Z3+CBMC)、数字孪生 (5 类故障注入)、HIL 人机协作 | [架构概览](#-架构概览) · [Multi-Agent](#-multi-agent-协同管道) |
| **赛道契合度** | 25 | 商飞产业需求、ARINC 653 分区调度、FreeRTOS 任务调度、SCADE G-Lustre 集成 | [产业应用案例](./docs/industry/产业应用案例.md) · [ARINC 653 示例](./examples/arinc653_partition/) |
| **落地可行性** | 25 | 四层可剥离架构、Mock 降级策略、12 个基准测试全过、Docker 一键部署 | [基准报告](./docs/benchmark/benchmark_report.md) · [部署说明](./docs/user/部署说明.md) |
| **应用价值** | 20 | 效率提升 6-12x、人力节约 70-75%、年成本节约 70-75%、ROI 量化 | [效率数据](./docs/review/量化效率数据.md) · [竞品对比](./docs/review/竞品对比分析.md) |

---

## 📁 目录结构

```
SkyForge/
├── README.md                          ← 你正在看的文件
├── LICENSE                            ← MIT License
├── ThirdParty.md                      ← 第三方组件说明(根目录)
├── CODE_WIKI.md                       ← 代码 Wiki 完整文档
├── CODE_OF_CONDUCT.md                 ← 社区行为准则
├── CONTRIBUTING.md                    ← 贡献指南
├── Makefile                           ← 一键命令入口(dev/test/lint/benchmark)
├── pyproject.toml                     ← Python 项目配置(uv workspace)
├── start.sh                           ← Linux/Mac 一键启动脚本
│
├── src/                               ← 源代码(三层可剥离)
│   ├── skyforge_engine/               ← Layer 0: 核心引擎 ⭐ 可独立 pip install
│   │   ├── agents/                    ←   6 个 Multi-Agent
│   │   ├── tools/                     ←   Cppcheck / Z3 / CBMC 集成
│   │   ├── digital_twin/              ←   故障注入 + 虚拟 MCU / 传感器
│   │   ├── composable/                ←   组件组合验证
│   │   ├── rag/                       ←   MISRA-C RAG 知识库
│   │   ├── report/                    ←   DO-178C 报告 + 19 项合规目标
│   │   ├── scade/                     ←   SCADE G-Lustre 解析器(ANTLR4)
│   │   ├── dal/                       ←   DAL A/B/C/D 目标覆盖
│   │   ├── schemas/                   ←   数据模型
│   │   ├── pipeline.py                ←   Pipeline 编排入口
│   │   └── demo_mode.py               ←   Mock 降级控制
│   │
│   ├── skyforge_llm/                  ← Layer 1: LLM 适配 ⭐ 可选剥离
│   │   ├── providers/                 ←   OpenAI / Anthropic / 本地
│   │   ├── security/                  ←   输入清洗 + 审计
│   │   ├── cache.py                   ←   LLM 响应缓存
│   │   └── router.py                  ←   多供应商路由
│   │
│   └── skyforge_core/                 ← Layer 2: CLI 工具 ⭐ 命令行入口
│       └── cli.py
│
├── studio/                            ← Layer 3: Web Studio(评委演示)
│   ├── app/                           ← FastAPI 后端
│   │   ├── api/routes/                ←   26 个 REST API + 2 个 WebSocket
│   │   ├── services/                  ←   Redis + WebSocket 管理
│   │   ├── core/                      ←   HIL / LLM / Streaming
│   │   ├── schemas/                   ←   Pydantic 数据模型
│   │   ├── rag/                       ←   MISRA-C 检索
│   │   ├── tests/                     ←   13 个测试文件(204 用例)
│   │   └── main.py                    ←   FastAPI 入口
│   └── frontend/                      ← Vue 3 前端
│       ├── src/
│       │   ├── pages/                 ←   路由页面(chat / task / login)
│       │   ├── components/            ←   36+ UI 组件 + shadcn-vue
│       │   ├── components/__tests__/  ←   5 个组件测试(97 用例)
│       │   ├── services/              ←   API 调用 + Mock 实现
│       │   └── utils/                 ←   工具函数 + 17 个契约模板
│       ├── package.json
│       └── Dockerfile
│
├── docs/                              ← 文档中心
│   ├── README.md                      ← 文档索引
│   ├── ARCHITECTURE.md                ← 架构详解
│   ├── ThirdParty.md                  ← 第三方组件(冗余副本)
│   ├── ROADMAP.md                     ← 项目路线图
│   ├── PLUGIN_DEVELOPMENT.md          ← 插件开发指南
│   ├── compliance/                    ← DO-178C 合规文档(9 份)
│   │   ├── PSAC.md                    ←   软件审定计划
│   │   ├── SDP.md / SVP.md            ←   开发 / 验证计划
│   │   ├── SCMP.md / SQAP.md          ←   配置管理 / 质量保证
│   │   ├── TQP.md / TOR.md / TAS.md    ←   工具鉴定
│   │   └── CODING_STANDARD.md         ←   编码标准
│   ├── user/                          ← 用户文档(教程 / 部署 / 测试报告)
│   ├── review/                        ← 评审分析(竞品 / 效率 / 差距 / 内部评审)
│   ├── industry/                      ← 产业应用案例
│   ├── benchmark/                     ← 性能基准报告(JSON + MD)
│   ├── verification/                  ← LLM 验证报告(Qwen / Gemma)
│   └── images/                        ← 截图资源
│
├── examples/                          ← 示例代码库(12 + 2 完整案例)
│   ├── README.md                      ← 示例总索引
│   ├── *.txt                          ← 12 个基础需求示例
│   ├── arinc653_partition/            ← ARINC 653 完整案例(需求 + 契约 + 代码)
│   └── freertos_task_scheduler/       ← FreeRTOS 完整案例
│
├── tools/                             ← 工具脚本
│   └── benchmark/run_benchmark.py     ← 性能基准测试套件
│
├── config/                            ← 集中配置
│   ├── .env.example                   ← 环境变量模板
│   └── pyrightconfig.json
│
├── docker/                            ← Docker 部署
│   ├── Dockerfile / Dockerfile.dev
│   └── docker-compose.yml / .dev.yml
│
├── output/                            ← 运行输出(已 gitignore)
└── .github/                           ← CI/CD 工作流
    ├── workflows/ci.yml
    ├── ISSUE_TEMPLATE/
    └── PULL_REQUEST_TEMPLATE.md
```

---

## 🔌 REST API 概览

**26 个 REST 端点 + 2 个 WebSocket 端点**,完整接口文档见 http://localhost:8000/docs。

| 模块 | 端点数 | 路由文件 | 代表接口 |
|------|--------|----------|----------|
| 健康检查 + 统计 | 2 | `routes/common.py` | `GET /api/health` · `GET /api/stats` |
| 代码生成 + 修复 + 仿真 + 验证 | 7 | `routes/pipeline.py` | `POST /api/generate` · `POST /api/repair` · `POST /api/simulate` |
| DO-178C 报告 | 2 | `routes/reports.py` | `POST /api/report` · `GET /api/report/download` |
| 组件组合验证 | 2 | `routes/composition.py` | `POST /api/compose` · `POST /api/check-compatibility` |
| HIL 人机协作 | 4 | `routes/hil.py` | `GET /api/hil/pending` · `POST /api/hil/approve` |
| 模型管理 + MISRA 规则检索 | 9 | `routes/models.py` | `GET /api/models` · `GET /api/misra/rules` |
| **WebSocket**(实时推送) | 2 | `routes/task_ws.py` | `/ws/agent-stream` · `/task/{task_id}` |

完整 API 列表与参数说明参见 [部署说明](./docs/user/部署说明.md)。

---

## 🛡️ DO-178C 合规状态

SkyForge 遵循 DO-178C 机载软件适航审定标准。合规文档详见 [`docs/compliance/`](./docs/compliance/)。

### 五大核心过程覆盖

| DO-178C 过程 | 章节 | 文档 | 状态 |
|-------------|------|------|------|
| **计划过程** | §4 | [PSAC](./docs/compliance/PSAC.md) / [SDP](./docs/compliance/SDP.md) / [SVP](./docs/compliance/SVP.md) | ✅ 已完成 (8/8 文档) |
| **开发过程** | §5 | HLR / LLR 层级 + 契约式设计 + MISRA-C 代码生成 | ✅ 已完成 (HLR→LLR→Code→Contract 全链路) |
| **验证过程** | §6 | Cppcheck + 契约校验 + 数字孪生 + V3.3 覆盖分析器 | ✅ 已完成 (语句/判定/MC/DC 三级覆盖) |
| **配置管理** | §7 | [SCMP](./docs/compliance/SCMP.md) + Git + PR 系统 + 基线管理 | ✅ 已完成 |
| **质量保证** | §8 | [SQAP](./docs/compliance/SQAP.md) + CI 自动检查 (Ruff/Biome/Pyright) | ✅ 已完成 |

### DAL 等级目标覆盖

DO-178C 共 **19 项可判定目标**(OBJ-1 ~ OBJ-19),涵盖问题报告、配置标识、追溯矩阵、语句 / 判定 / MC/DC 覆盖、HLR/LLR 追溯、独立验证、正式 PR、工具鉴定等。代码实现见 [`src/skyforge_engine/report/do178_objectives.py`](./src/skyforge_engine/report/do178_objectives.py)。

| DAL | 等级含义 | 目标满足率 | 关键要求 | 实现位置 |
|-----|---------|-----------|----------|---------|
| A | 灾难性 | 18/19 (95%) | MC/DC 必须 | `mcdc_calculator.py` (V3.3-Enhanced) |
| B | 危险 | 18/18 (100%) | 判定覆盖必须 | `coverage_analyzer.py` |
| C | 重大 | 16/16 (100%) | 语句覆盖必须 | `coverage_analyzer.py` |
| D | 轻微 | 13/13 (100%) | 基础验证 | 全流程覆盖 |

> 19 项 OBJ 中,仅 OBJ-17 (独立验证) 仍为部分满足,需非作者团队人工审查 (Phase 4 闭环)。
> 完整合规矩阵详见 [`COMPLIANCE_MATRIX.csv`](./docs/compliance/COMPLIANCE_MATRIX.csv) (19 OBJ × 5 DAL)。

### 工具鉴定(TQL)

| 工具 | TQL 级别 | 状态 | 文档 |
|------|---------|------|------|
| Agent Pipeline | TQL-1 | ✅ 草案完成 | [TQP](./docs/compliance/TQP.md) |
| LLM 推理引擎 | TQL-1 | ✅ 草案完成 | [TOR](./docs/compliance/TOR.md) |
| Contract Checker | TQL-2 | ✅ 草案完成 | [TAS](./docs/compliance/TAS.md) |
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
| **使用教程** | [docs/user/使用教程.md](./docs/user/使用教程.md) | 功能模块详解与操作指南 |
| **部署说明** | [docs/user/部署说明.md](./docs/user/部署说明.md) | 环境配置与 API 接口文档 |
| **测试报告** | [docs/user/测试报告.md](./docs/user/测试报告.md) | 测试覆盖与质量评估 |
| **架构详解** | [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | 四层架构设计深度剖析 |
| **代码 Wiki** | [CODE_WIKI.md](./CODE_WIKI.md) | 代码组织与模块说明 |
| **基准报告** | [docs/benchmark/benchmark_report.md](./docs/benchmark/benchmark_report.md) | 12 个示例性能基准 |
| **效率数据** | [docs/review/量化效率数据.md](./docs/review/量化效率数据.md) | ROI 与效率提升量化 |
| **竞品分析** | [docs/review/竞品对比分析.md](./docs/review/竞品对比分析.md) | vs SCADE Suite / Polyspace |
| **差距分析** | [docs/review/比赛要求差距分析.md](./docs/review/比赛要求差距分析.md) | 比赛要求差距与对策 |
| **产业案例** | [docs/industry/产业应用案例.md](./docs/industry/产业应用案例.md) | 商飞产业需求对接 |
| **LLM 验证** | [docs/verification/qwen_verification_report.md](./docs/verification/qwen_verification_report.md) | Qwen 模型验证报告 |
| **项目路线图** | [docs/ROADMAP.md](./docs/ROADMAP.md) | 后续规划 |
| **插件开发** | [docs/PLUGIN_DEVELOPMENT.md](./docs/PLUGIN_DEVELOPMENT.md) | 二次开发扩展指南 |

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
- 📄 [docs/ThirdParty.md](./docs/ThirdParty.md)

---

## 📄 许可证

本项目采用 [**MIT License**](./LICENSE) 开源协议。

Copyright (c) 2026 SkyForge Contributors

---

## 💬 联系与反馈

| 渠道 | 地址 |
|------|------|
| **代码仓库** | [atomgit.com/ch-onboard/skyforge](https://atomgit.com/ch-onboard/skyforge) |
| **GitHub Issues** | [提交 Issue](https://atomgit.com/ch-onboard/skyforge/issues) |
| **比赛官方邮箱** | kefu@jsopen.org.cn |
| **项目路线图** | [docs/ROADMAP.md](./docs/ROADMAP.md) |
| **贡献指南** | [CONTRIBUTING.md](./CONTRIBUTING.md) |
| **社区行为准则** | [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) |

### 比赛信息

- **赛事**: 航空工业软件开源创新大赛
- **赛道**: 机上软件开发工具研发
- **赛题**: 二 — AI 智能体驱动的机载软件轻量化开发工具
- **AtomGit 仓库**: https://atomgit.com/ch-onboard/skyforge

---

### 🎯 项目创新点

1. **多 Agent 协同架构** — 6 个 Agent 闭环,从需求到修复全自动
2. **DO-178C 全流程合规** — 自动生成适航报告与需求追溯矩阵,19 项可判定目标
3. **MISRA-C 智能修复** — Cppcheck 扫描 + Agent 智能修复 + 契约校验闭环(57 条自动修复规则)
4. **形式化验证** — Z3 SMT 求解 + CBMC 模型检测双引擎
5. **数字孪生仿真** — 虚拟传感器 / MCU + 5 类故障注入测试(bias / signal_loss / noise / stuck / step)
6. **HIL 人机协作** — Redis-based 关键检查点人工审批工作流
7. **SCADE 集成** — ANTLR4 解析 G-Lustre 模型自动转需求与契约
8. **四层可剥离架构** — 从机载 80MB 到云端全栈,灵活适配

---

> **SkyForge** — *Forging the Future of Aviation Software, One Agent at a Time.* 🛩️
