# SkyForge Code Wiki

> **项目名称**:SkyForge(天锻)
> **版本**:v0.4.0
> **定位**:AI 智能体驱动的机载软件轻量化开发工具
> **License**:MIT
> **AtomGit 仓库**:https://atomgit.com/ch-onboard/skyforge

---

## 目录

- [1. 项目概览](#1-项目概览)
- [2. 整体架构](#2-整体架构)
- [3. 目录结构](#3-目录结构)
- [4. 核心引擎 skyforge_engine(Layer 0)](#4-核心引擎-skyforge_enginelayer-0)
- [5. LLM 抽象层 skyforge_llm(Layer 1)](#5-llm-抽象层-skyforge_llmlayer-1)
- [6. CLI 入口 skyforge_core(Layer 2)](#6-cli-入口-skyforge_corelayer-2)
- [7. Web 工作室 studio(Layer 3)](#7-web-工作室-studiolayer-3)
- [8. 前端 frontend(Vue 3)](#8-前端-frontendvue-3)
- [9. 依赖关系](#9-依赖关系)
- [10. 项目运行方式](#10-项目运行方式)
- [11. API 接口参考](#11-api-接口参考)
- [12. 测试体系](#12-测试体系)
- [13. 关键设计要点](#13-关键设计要点)

---

## 1. 项目概览

### 1.1 核心价值主张

SkyForge 通过**多 Agent 协同架构**,将自然语言需求自动转换为符合 **DO-178C / MISRA-C:2012** 标准的机载 C 代码,实现"需求→契约→代码→修复→仿真→报告"全流程自动化,显著提升机载软件适航审定效率。

### 1.2 六大核心功能

| 功能 | 说明 | 输入 → 输出 |
|------|------|------------|
| 需求解析 | 自然语言需求转结构化 JSON | 文本 → JSON |
| 契约生成 | 生成 DO-178C 合规契约 YAML | JSON → YAML |
| 代码生成 | 生成 MISRA-C 风格 C 代码(含追溯注释) | YAML → C |
| 合规检查 | Cppcheck MISRA-C 扫描 + Agent 自动修复(最多 3 轮闭环) | C → 修复后 C |
| 数字孪生 | 虚拟传感器 + 虚拟 MCU + 故障注入仿真 | C + 契约 → 仿真结果 |
| 报告生成 | DO-178C 合规报告(HTML,支持打印 PDF) | 全流程产物 → HTML |

### 1.3 六大创新点

1. **多 Agent 协同架构**(需求→契约→代码→修复闭环)
2. **DO-178C 合规自动生成**(适航报告 + 需求追溯矩阵)
3. **MISRA-C 自动修复**(Cppcheck + Agent 修复 + 契约校验)
4. **数字孪生仿真**(虚拟传感器/MCU + 故障注入)
5. **HIL 人机协作**(关键检查点人工审批)
6. **SCADE 集成**(导入 G-Lustre 模型,自动转换)

---

## 2. 整体架构

### 2.1 四层可剥离架构

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

**设计原则**:自底向上逐层增强,每层可独立安装与运行,满足机载软件轻量化部署需求。

| 层级 | 包名 | 安装方式 | 大小 | 关键依赖 |
|------|------|---------|------|---------|
| Layer 0 | `skyforge-engine` | `pip install skyforge-engine` | ~80MB | pyyaml, numpy, loguru, packaging |
| Layer 1 | `skyforge-llm` | `pip install skyforge-llm` | +50MB | httpx, openai, anthropic |
| Layer 2 | `skyforge-core` | `pip install skyforge-core` | +5MB | pydantic, pydantic-settings |
| Layer 3 | `studio` | `docker compose up` | +315MB | FastAPI, Vue 3, Redis |
| 嵌入式 | `nuitka skyforge_engine` | nuitka 编译 | <15MB 单文件 | — |

### 2.2 核心数据流

#### 代码生成主流程(5 阶段)

```
用户输入 → 需求解析 → 契约生成 → 代码生成 → 合规检查 → 报告生成
   │          │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼          ▼
 文本        JSON       YAML        C         HTML        PDF
```

#### 修复 Agent 闭环逻辑(最多 3 轮)

1. 调 `cppcheck_scanner.scan(code)` 检出违规列表
2. 无违规 → 跳出循环
3. 调 `code_repairer_agent.repair(code, violations)` 修复
4. 调 `contract_checker.check(修复代码, contract)` 验证契约仍满足
5. 回到步骤 1(最多 3 轮)

#### HIL 人机协作流程

启用 `HIL_ENABLED=true` 后,流水线在三个检查点暂停:

1. `requirement_review`(需求评审,与契约生成并行执行)
2. `contract_review`(契约评审)
3. `code_review`(代码评审)

审批通过流程继续,拒绝则流水线终止并返回 `aborted=true`。

---

## 3. 目录结构

```
SkyForge/
├── src/                       # Python 后端(三层可剥离)
│   ├── skyforge_engine/       #   Layer 0 — 核心引擎
│   │   ├── agents/            #     智能体系统(5 Agent)
│   │   ├── composable/        #     组件组合验证
│   │   ├── dal/               #     DAL 覆盖分析(GCOV/MC/DC)
│   │   ├── digital_twin/      #     数字孪生仿真
│   │   ├── rag/               #     RAG 知识库(MISRA-C)
│   │   ├── report/            #     DO-178C 报告生成
│   │   ├── scade/             #     SCADE G-Lustre 解析
│   │   ├── schemas/           #     数据模型(DAL 目标)
│   │   ├── tools/             #     工具链(Cppcheck/CBMC/Z3)
│   │   ├── utils/             #     通用工具
│   │   ├── pipeline.py        #     全流程编排
│   │   ├── config.py          #     配置类
│   │   └── demo_mode.py       #     演示模式
│   ├── skyforge_llm/          #   Layer 1 — LLM 抽象层
│   │   ├── providers/         #     Provider(OpenAI/Anthropic)
│   │   ├── security/          #     安全封装(sanitizer/validator/auditor)
│   │   ├── client.py          #     统一 LLM 客户端
│   │   ├── router.py          #     模型路由
│   │   ├── cache.py           #     LLM 响应缓存
│   │   ├── local.py           #     本地 GGUF 模型
│   │   └── parser.py          #     JSON 解析器
│   └── skyforge_core/         #   Layer 2 — CLI 工具
│       └── cli.py             #     skyforge 命令入口
├── studio/                    # Layer 3 — Web 工作室
│   ├── app/                   #   FastAPI 后端
│   │   ├── api/routes/        #     API 路由
│   │   ├── core/              #     核心层(hil/llm/streaming)
│   │   ├── schemas/           #     Pydantic 模型
│   │   ├── services/          #     服务层(redis/ws)
│   │   ├── rag/               #     RAG 模块
│   │   ├── utils/             #     工具
│   │   ├── tests/             #     测试套件
│   │   ├── config/            #     配置
│   │   └── main.py            #     FastAPI 入口
│   └── frontend/              #   Vue 3 前端
│       └── src/
│           ├── pages/         #     路由页面
│           ├── views/         #     辅助页面
│           ├── components/    #     业务组件 + UI 库
│           ├── stores/        #     Pinia 状态
│           ├── services/     #     API 客户端
│           ├── router/        #     Vue Router
│           ├── composables/   #     组合式函数
│           ├── types/         #     领域类型
│           └── utils/         #     工具
├── config/                    # 集中配置(.env / pyright)
├── docker/                    # Docker 配置(Compose + Dockerfile)
├── docs/                      # 项目文档 + DO-178C 合规文档
├── examples/                  # 示例需求文件(11 个)
├── models/                    # 模型存放目录
├── .github/                   # CI/CD 与 Issue 模板
├── pyproject.toml             # 顶层 workspace 配置
├── Makefile                   # 开发命令
├── start.sh                   # 一键启动脚本
└── README.md
```

---

## 4. 核心引擎 skyforge_engine(Layer 0)

> 位置:`src/skyforge_engine/`
> 定位:零 LLM、零 Web 依赖的机载轻量部署核心引擎

### 4.1 顶层文件

#### [pipeline.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/pipeline.py) — 核心编排器

**关键类型**:

| 名称 | 签名 | 作用 |
|------|------|------|
| `LogHook` | `Callable[[str, str, str], Union[None, Awaitable[None]]]` | 流式推送 hook 类型 (agent, level, message) |
| `AsyncLogHook` | `Callable[[str, str, str], Awaitable[None]]` | 归一化后的 async hook |

**关键函数**:

| 函数 | 作用 |
|------|------|
| `run_pipeline(requirement, scade_file, log_hook) -> dict` | **核心 3 Agent + Cppcheck 流水线** |
| `repair_loop(code, contract, max_iterations, req_id, log_hook) -> dict` | 修复闭环(扫描→修复→契约校验,最多 N 轮) |
| `run_full_pipeline(requirement, scade_file, log_hook, simulate) -> dict` | 完整流水线(run_pipeline + repair_loop + 仿真) |
| `_run_hil_checkpoint(checkpoint, content, hook, timeout) -> dict` | HIL 检查点请求人工审批 |
| `_push_agent_thought(hook, agent_name, context_desc)` | 推送 Agent 思考消息(LLM 流式生成) |

**`run_pipeline` 编排顺序**:

1. SCADE 输入处理:`parse_glustre` → `convert` → `convert_to_contract`
2. Agent 1 — 需求解析:`RequirementParserAgent.run`
3. Agent 1.5 — LLR 生成:`LLRGeneratorAgent.generate` [V3.3 新增]
4. 架构设计:`design_architecture` [V0.4 P3 新增]
5. HIL 检查点 1 — 需求评审 ‖ Agent 2 — 契约生成:`ContractGeneratorAgent.run`(并行)
6. HIL 检查点 2 — 契约评审
7. 契约形式化验证:`verify_contract` [P0-3 修复]
8. Agent 3 — 代码生成:`CodeGeneratorAgent.run`
9. HIL 检查点 3 — 代码评审
10. Cppcheck 扫描:`cppcheck_scan`

**`run_full_pipeline` 三阶段**:

1. `run_pipeline`(3 Agent + Cppcheck)
2. `repair_loop`(修复闭环,后修复含 CBMC + Z3 形式化验证)
3. `SimulationEngine.run_simulation_async`(数字孪生仿真)
- 全程:`EvidenceCollector` 证据收集

#### [config.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/config.py) — 全局配置中心

| 名称 | 作用 |
|------|------|
| `ApiType(str, Enum)` | LLM API 类型枚举:OPENAI_CHAT, OPENAI_RESPONSES, ANTHROPIC |
| `parse_cors(value) -> list[str]` | CORS 配置解析(支持逗号分隔/JSON 数组) |
| `Settings(BaseSettings)` | 全局配置类(LLM/HIL/Agent/工具开关) |
| `Settings.from_env(env)` | 根据环境名称加载配置 |
| `settings` | 模块级单例,全局共享 |

**Settings 关键字段分组**:
- **LLM**:`USE_LLM`, `LMSTUDIO_BASE_URL`, `LLM_MODEL`, `LLM_CACHE_ENABLED`, `LLM_CACHE_TTL`
- **HIL**:`HIL_ENABLED`, `HIL_TIMEOUT`, `HIL_INTERFACE`, `HIL_SERIAL_PORT`, `HIL_JTAG_*`
- **Agent (5 组)**:`REQ_PARSER_*`, `CON_GEN_*`, `CODE_GEN_*`, `REPAIR_*`, `LLR_GEN_*`
- **工具开关**:`USE_REAL_GCC`, `USE_REAL_CPPCHECK`, `RAG_ENABLED`

#### [demo_mode.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/demo_mode.py) — 演示模式

| 名称 | 作用 |
|------|------|
| `DemoConfig` | 强制 USE_LLM=True,禁用缓存,3 个演示需求 |
| `DemoVerifier` | 5 级验证(L1-L5:进程→模型→API→推理→输出质量) |
| `DemoRunner` | `run(readiness_check, warmup)` |
| `quick_check() -> bool` | 便捷验证函数 |

### 4.2 agents/ — 智能体(5 Agent 协同)

| 文件 | Agent | 关键方法 | 职责 |
|------|-------|---------|------|
| [requirement_parser.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/agents/requirement_parser.py) | `RequirementParserAgent` | `run(requirement_text) -> dict` | 从自然语言需求提取结构化字段(REQ-ID、描述、I/O、范围、约束、DAL 等级) |
| [llr_generator.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/agents/llr_generator.py) | `LLRGeneratorAgent` | `generate(requirements) -> dict` | 从 HLR 拆分为 LLR,建立 HLR↔LLR 追溯关系 [V3.3] |
| [architecture_designer.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/agents/architecture_designer.py) | — | `design_architecture(requirements, llr_result) -> dict` | 根据需求/LLR 设计软件架构(模块划分、接口定义、调用关系)[V0.4 P3] |
| [contract_generator.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/agents/contract_generator.py) | `ContractGeneratorAgent` | `run(requirements) -> str (YAML)` | 生成 `.contract` YAML 文件(preconditions/postconditions/invariants/fault_handling/interface) |
| [code_generator.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/agents/code_generator.py) | `CodeGeneratorAgent` | `run(requirements, contract_yaml) -> str (C)` | 基于契约生成 MISRA-C 合规 C 代码,含 `[REQ-xxx]` 追溯注释 |
| [code_repairer.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/agents/code_repairer.py) | `CodeRepairerAgent` | `run(code, violations, contract) -> str (C)` | 根据 Cppcheck 违规列表和契约,应用 MISRA 修复策略 |
| [misra_fixes.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/agents/misra_fixes.py) | — | `apply_fix(rule_id, code, context) -> str` | 56 个 MISRA 规则修复器(每个对应一条规则) |
| [types.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/agents/types.py) | `RepairAction` | dataclass | 修复动作(rule_id, action, before, after, reason) |

### 4.3 digital_twin/ — 数字孪生仿真

| 文件 | 关键类/函数 | 职责 |
|------|------------|------|
| [virtual_sensor.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/digital_twin/virtual_sensor.py) | `VirtualSensor.generate(waveform_type, params, samples) -> list[float]` | 虚拟传感器(5 种波形:正弦、方波、三角、阶跃、随机) |
| [virtual_mcu.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/digital_twin/virtual_mcu.py) | `VirtualMCU.compile(code) -> CompileResult`, `execute(binary, inputs) -> ExecutionResult` | 虚拟 MCU(GCC 编译 + 安全沙箱执行;GCC 不可用时降级到 Mock) |
| [fault_injector.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/digital_twin/fault_injector.py) | `FaultInjector.inject(signal, fault_type, params) -> Signal` | 故障注入器(5 种:bias/signal_loss/noise/stuck/step) |
| [hil_adapter.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/digital_twin/hil_adapter.py) | `SerialHilAdapter`(STM32 AN3155 UART), `JtagHilAdapter`(OpenOCD/pyOCD) | HIL 硬件在环适配器 |
| [simulation_engine.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/digital_twin/simulation_engine.py) | `SimulationEngine.run_simulation(...)`, `run_simulation_async(...)` | 仿真引擎核心(编排 VirtualMCU + VirtualSensor + FaultInjector) |

### 4.4 tools/ — 工具链(8 个文件)

| 文件 | 关键类/函数 | 职责 |
|------|------------|------|
| [cppcheck_scanner.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/tools/cppcheck_scanner.py) | `scan(code, log_callback) -> list[Violation]`, `scan_with_result(code, log_callback) -> ScanResult` | Cppcheck 集成(真实/Mock 降级,覆盖 8 种 MISRA 规则) |
| [contract_checker.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/tools/contract_checker.py) | `check(code, contract_yaml, cid) -> CheckResult` | 契约校验器(语义分析版,CCodeAnalyzer + SemanticChecker + CppcheckVerifier) |
| [contract_formal_verifier.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/tools/contract_formal_verifier.py) | `verify_contract(contract_yaml, code) -> VerificationResult` | 契约形式化验证(Z3 + CBMC 三层验证) |
| [contract_to_assert.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/tools/contract_to_assert.py) | `contract_to_assert(yaml_str, cid) -> str` | 契约→C 断言自动映射器(Jinja2 模板) |
| [cbmc_verifier.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/tools/cbmc_verifier.py) | `run_cbmc_verification(code, unwind, function, property_flags) -> CBMCResult` | CBMC 有界模型检查器 |
| [z3_verifier.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/tools/z3_verifier.py) | `verify_contract_constraints(pre, post, inv) -> Z3Result`, `generate_boundary_test_cases(...)` | Z3 SMT 约束求解器(契约验证 + 边界测试用例生成) |
| [pr_manager.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/tools/pr_manager.py) | `PRManager` 类,`create_report(...)`, `resolve(...)`, `close(...)` | 正式问题报告管理(DO-178C Table A-8,状态机:OPEN→IN_PROGRESS→RESOLVED→CLOSED) |
| [tool_chain_validator.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/tools/tool_chain_validator.py) | `validate(project_root) -> ValidationReport` | 工具链自动验证(DO-330 工具鉴定,检查 Python/Node/GCC/Cppcheck/Redis + DO-178C 文档) |

### 4.5 report/ — DO-178C 报告生成

| 文件 | 关键类/函数 | 职责 |
|------|------------|------|
| [report_generator.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/report/report_generator.py) | `generate_report(pipeline_result) -> str` | DO-178C 合规报告 HTML 生成器(Jinja2,7 章节) |
| [traceability_matrix.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/report/traceability_matrix.py) | `build_matrix(pipeline_result, include_llr) -> list[TraceEntry]`, `build_reverse_matrix(...)` | 四层追溯矩阵构建器(HLR→LLR→Code→Test) |
| [do178_objectives.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/report/do178_objectives.py) | `check_objectives(pipeline_result, dal) -> list[ObjectiveResult]` | DO-178C DAL 自适应目标符合性检查(19 项目标) |
| [coverage_analyzer.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/report/coverage_analyzer.py) | `analyze_code_coverage(code, fault_injected, dal) -> dict` | 覆盖率分析统一入口(V3.3 集成 MC/DC) |
| [evidence_collector.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/report/evidence_collector.py) | `EvidenceCollector` 类,14 个 `record_*` 方法, `generate_package() -> str` | DO-178C 合规证据自动收集器 |
| [psac_generator.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/report/psac_generator.py) | `generate_psac(pipeline_result) -> PSACDocument` | PSAC(软件审定计划)文档生成器 |

**DO-178C 19 项目标**(OBJ-1 ~ OBJ-19):需求可追溯性、契约式设计验证、源代码合规性、静态分析、仿真测试覆盖、故障注入测试、代码审查、配置管理、问题报告、独立性、编译验证、契约违约处理、语句/判定/MC/DC 覆盖率、HLR/LLR 追溯、独立验证、PR 系统、工具鉴定。

### 4.6 rag/ — RAG 检索(MISRA-C 知识库)

| 文件 | 关键类/函数 | 职责 |
|------|------------|------|
| [rule_parser.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/rag/rule_parser.py) | `MisraRule` dataclass, `parse_misra_rules(content) -> list[MisraRule]`, `categorize_rule(title, desc) -> str` | MISRA-C 规则解析器(详解 + 速查两种格式) |
| [misra_searcher.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/rag/misra_searcher.py) | `MisraRuleSearcher`(单例), `search(query, top_k)`, `get_rule(rule_id)`, `get_all_rules()`, `get_categories_summary()` | 轻量级 MISRA-C 规则检索引擎(无外部依赖,TF-IDF + 字段权重) |
| [rag_enhancer.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/rag/rag_enhancer.py) | `RagEnhancer.enhance_prompt(agent_name, task) -> str`, `build_misra_context(rule_ids) -> str` | RAG 增强 Agent prompt 构建器(10 条静态红线规则 + 动态检索) |
| [semantic_search.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/rag/semantic_search.py) | `SemanticMisraSearcher`(三级降级:chromadb → in_memory → keyword_only) | 语义搜索引擎(可选 sentence-transformers + chromadb) |

**MISRA-C 检索权重**:`_FIELD_WEIGHTS`(rule_id:8, title:4, description:2, examples:1, severity:1.5)、`_SEVERITY_WEIGHTS`(强制:1.5, 要求:1.0, 建议:0.8)。

### 4.7 scade/ — SCADE/Lustre 解析

| 文件 | 关键内容 | 职责 |
|------|---------|------|
| [Lustre.g4](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/scade/Lustre.g4) | ANTLR4 语法 | Lustre 语言形式化语法定义 |
| [lustre_lexer.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/scade/lustre_lexer.py) | `TokenType(Enum)`, `Token` dataclass, `LustreLexer` | 词法分析器(80+ token 类型) |
| [lustre_parser.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/scade/lustre_parser.py) | `parse_glustre(content) -> ParsedLustre`, `_parse_with_regex(content)` | G-Lustre 解析器主入口(先尝试 AST 解析,失败后正则后备) |
| [lustre_ast.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/scade/lustre_ast.py) | 14 种 LustreType, 14 种 BinOp, 4 种 UnaryOp, 30+ AST 节点 | Lustre AST 节点定义 |
| [lustre_visitor.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/scade/lustre_visitor.py) | `LustreVisitor(ABC)`, `LustreTransformer`, `LustreCollector`, `NameResolver` | AST 访问者模式 |
| [lustre_to_requirement.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/scade/lustre_to_requirement.py) | `convert(parsed, req_id) -> str`, `convert_to_contract(parsed, req_id) -> str` | Lustre → 需求/契约转换器(12 种类型映射) |

### 4.8 其他子模块

| 子模块 | 文件 | 关键内容 | 职责 |
|--------|------|---------|------|
| composable/ | `compatibility_checker.py`, `component_combinator.py`, `composition_simulator.py` | `CompatibilityChecker.check(...)`, `ComponentCombinator.combine(...)`, `CompositionSimulator.simulate(...)` | 组件组合验证(顺序/并行/反馈三种连接方式) |
| dal/ | `gcov_collector.py`, `mcdc_calculator.py` | `collect_coverage(executable, source)`, `analyze_coverage(code, gcov_result)` | DAL 覆盖分析(GCC gcov + MC/DC,DO-178C DAL A 要求) |
| schemas/ | `dal_objectives.py` | `DAL(Enum)` (A/B/C/D/E), `ALL_OBJECTIVES`, `get_objectives_for_dal(dal)` | DAL 目标定义(A=71, B=69, C=62, D=26, E=0 目标) |
| utils/ | `common_utils.py`, `log_util.py` | `transform_link`, `split_footnotes`, `create_task_id`, `ensure_safe_task_id`, `LoggerInitializer` | 通用工具与日志初始化 |

---

## 5. LLM 抽象层 skyforge_llm(Layer 1)

> 位置:`src/skyforge_llm/`
> 定位:LLM 抽象与安全封装层(可选剥离)

### 5.1 双轨架构设计

SkyForge 的 LLM 调用存在**两套并行机制**:

| 机制 | 适用场景 | 入口 | 特点 |
|------|---------|------|------|
| **LMStudioClient / UnifiedLLMClient** | 单轮 prompt、本地直连、Mock 降级 | `get_lmstudio_client()` | httpx 直连 LM Studio `localhost:1234/v1`,无 Redis/Web 依赖,Pipeline 实际使用 |
| **LLM + LLMFactory**(Web 层) | 多轮对话、工具调用、Redis 流式推送 | `LLMFactory(task_id).get_all_llms()` | 多 Provider(OpenAI Chat/Responses/Anthropic),带重试、tool call 修复、推送 AgentMessage 到前端 |

### 5.2 核心类与函数

#### [client.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_llm/client.py)

| 类 | 关键方法 | 作用 |
|----|---------|------|
| `LMStudioClient` | `chat(prompt, system_prompt, temperature, max_tokens) -> str`, `chat_async(...)`, `chat_stream(...)`, `is_available()` | LM Studio 轻量级客户端(httpx 直连,TTL 缓存 60s) |
| `UnifiedLLMClient` | `chat(...)`, `chat_async(...)`, `chat_stream(...)`, `get_active_backend()`, `get_status()` | 统一客户端(Local GGUF → LM Studio → Mock 三级回退) |

**回退优先级**:`LocalLLMClient`(本地 GGUF) > `LMStudioClient`(LM Studio 本地服务) > Mock(空响应)。

模块级:`get_lmstudio_client() -> UnifiedLLMClient`(全局单例,函数名沿用历史命名)。

#### [router.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_llm/router.py) — `ModelRouter`

按任务复杂度选择 LM Studio 中已加载的模型,支持超时降级与手动选择。

| 常量 | 说明 |
|------|------|
| `_TASK_COMPLEXITY` | `requirement_parse/contract_generation/report_writing/default → small`;`code_generation/code_repair → large` |
| `_MODEL_CANDIDATES` | small 候选=[gemma-3-e4b, gemma-4-e4b, qwen3.5-9b, ...];large 候选=[qwen3-coder-30b, qwen3.6-27b, gpt-oss-20b, ...] |

| 方法 | 作用 |
|------|------|
| `select_model(task_type) -> str` | 选择策略:① 手动选择优先;② 任务复杂度匹配;③ 第一个可用模型;④ 环境变量默认 |
| `select_with_fallback(task_type) -> str` | 选择模型并在超时时降级 |
| `record_latency(model_id, latency)` | 记录调用耗时,超阈值告警 |
| `set_manual_selection(model_id)` | 手动指定或清除 |

模块级:`get_model_router()`、`reset_model_router()`。

#### [cache.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_llm/cache.py) — `LLMCache`

进程级内存字典 + TTL + 线程安全缓存(仅对非流式调用生效,Mock 模式下不生效)。

| 方法 | 作用 |
|------|------|
| `make_key(prompt, system_prompt) -> str` | `SHA256(system_prompt + "\x00" + prompt)` |
| `get(key) -> Optional[str]` | 命中未过期返回值;过期惰性清理 |
| `set(key, value)` | 加锁写入,记录过期时间 |

模块级:`get_llm_cache()`(双重检查锁单例,从 `settings.LLM_CACHE_ENABLED/LLM_CACHE_TTL` 初始化)。

#### [parser.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_llm/parser.py) — `safe_parse_llm_json`

```python
def safe_parse_llm_json(text: str) -> Optional[dict]
```

三级降级解析 LLM 输出的 JSON,失败返回 `None`(不抛异常):
1. **一级**:`json.loads(text)` 直接解析
2. **二级**:正则剥离 Markdown 代码块包裹(```json ... ```)后再解析
3. **三级**:正则提取首个完整花括号块后再解析

#### [local.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_llm/local.py) — `LocalLLMClient`

基于 `llama-cpp-python` 加载 GGUF 模型,支持 GPU/CPU 自动选择、流式生成、自动下载模型。

- 默认模型:`Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF`,下载到 `~/.skyforge/models/`
- `generate(...)`, `generate_async(...)`, `generate_stream(...)`, `is_available()` (TTL 300s)

模块级:`get_local_llm_client()`。

### 5.3 providers/ — Provider 抽象层

| 文件 | 类 | 说明 |
|------|-----|------|
| [base.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_llm/providers/base.py) | `BaseProvider(ABC)` | 抽象基类,定义 `async call(messages, model, api_key, base_url, tools, tool_choice, max_tokens, top_p) -> StandardResponse` |
| [openai.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_llm/providers/openai.py) | `OpenAIChatProvider` | 基于 `AsyncOpenAI` 调用 `/v1/chat/completions`,支持 reasoning_content(DeepSeek/Qwen) |
| [openai_responses.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_llm/providers/openai_responses.py) | `OpenAIResponsesProvider` | 调用新版 `/v1/responses` API,自动格式转换(system→developer, tool→function_call_output) |
| [anthropic.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_llm/providers/anthropic.py) | `AnthropicProvider` | 基于 `AsyncAnthropic` 调用 `/v1/messages`,自动格式转换(tool_use blocks, input_schema) |

### 5.4 types.py — 类型定义

| dataclass | 字段 |
|-----------|------|
| `ToolCall` | `id: str`, `name: str`, `arguments: str`(JSON string) |
| `Usage` | `prompt_tokens: int = 0`, `completion_tokens: int = 0` |
| `StandardResponse` | `content: str | None`, `reasoning_content: str | None`, `tool_calls: list[ToolCall]`, `usage: Usage` |

### 5.5 security/ — 安全封装层

> 参照 DO-326B/DO-356A 机载网络安全要求,原则为"本地优先+数据不离机" + "AI计算,人类决策"

| 文件 | 关键内容 | 职责 |
|------|---------|------|
| [sanitizer.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_llm/security/sanitizer.py) | `SanitizedPrompt` dataclass, `sanitize_input(prompt) -> SanitizedPrompt` | 输入净化器(替换硬件寄存器地址为 `0xREG_BASE_{i:04d}`,替换用户路径为 `<PROJECT_ROOT>`) |
| [validator.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_llm/security/validator.py) | `ValidatedOutput` dataclass, `validate_output(raw_output, max_size=102400) -> ValidatedOutput` | 输出验证器(10 条 FORBIDDEN_PATTERNS:malloc/free/calloc/realloc/goto/system/exec/popen/fork/__asm + 追溯注释完整性) |
| [auditor.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_llm/security/auditor.py) | `LLMCallRecord` dataclass, `AuditLogger` 类, `get_auditor()` | 审计日志(记录时间戳、Provider+Model、输入 SHA-256、输出校验结果、Token 消耗) |

> 注:`security/` 子模块已实现但 Pipeline 当前未实际调用,属预留接口。

---

## 6. CLI 入口 skyforge_core(Layer 2)

> 位置:`src/skyforge_core/`
> 定位:命令行入口,所有逻辑委托 skyforge_engine

### CLI 命令列表

入口点:`skyforge = "skyforge_core.cli:main"`(使用 argparse + subparsers)。

| 命令 | 处理函数 | 关键参数 | 说明 |
|------|---------|---------|------|
| `skyforge generate` | `cmd_generate(args)` | `-r/--requirement`(必填), `-o/--output`(默认 ./output), `--dal`(默认 C), `--use-llm`, `--simulate`, `--fault` | 从需求生成 DO-178C 合规代码 |
| `skyforge check` | `cmd_check(args)` | `-c/--code`(必填), `-t/--contract` | 校验代码 MISRA-C 合规性和契约一致性(退出码 0/1) |
| `skyforge simulate` | `cmd_simulate(args)` | `-c/--code`(必填), `-t/--contract`, `--fault`, `--steps`(默认 200), `-o/--output` | 运行数字孪生仿真 |
| `skyforge report` | `cmd_report(args)` | `-p/--pipeline-result`(必填), `-o/--output`(默认 report.html) | 生成 DO-178C 合规报告 |

**依赖最小化**:核心 6 个包(pyyaml/numpy/loguru/pydantic/pydantic-settings);`httpx`/`openai` 通过 `[llm]` extras、`jinja2` 通过 `[report]` extras 按需安装。

---

## 7. Web 工作室 studio(Layer 3)

> 位置:`studio/app/`
> 应用入口:`studio.app.main:app`

### 7.1 FastAPI 应用架构

#### [main.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/main.py) — 应用入口

**构造**:`FastAPI(title="SkyForge", version="0.1.0", lifespan=lifespan)`

**启动流程**(`lifespan`):
1. 打印 ASCII 横幅 `get_ascii_banner()`
2. 创建 `./project` 目录
3. LLM 预热(后台异步):`asyncio.create_task(_warmup_llm(client))`,发送 "hello" 短 prompt 触发 KV-Cache 预热
4. 进入服务运行态

**中间件栈**:
- `security_headers`:注入 `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`X-XSS-Protection`、`Referrer-Policy`
- `CORSMiddleware`:从 `settings.CORS_ALLOW_ORIGINS` 读取
- `Limiter`(slowapi):全局速率限制器

**路由注册顺序**:
```
common_router      → /api/health, /api/stats
ws_router          → /task/{task_id} (WebSocket,可选,依赖 Redis)
ws_streaming_router → /ws/agent-stream (WebSocket)
pipeline_router    → /api/generate, /api/upload-scade, /api/repair,
                     /api/check-contract, /api/simulate, /api/fault-types
reports_router     → /api/report, /api/report/download
composition_router → /api/compose, /api/check-compatibility
hil_router         → /api/hil/pending, /api/hil/approve, /api/hil/reject, /api/hil/history
models_router      → /api/models, /api/models/select, /api/models/clear,
                     /api/llm/status, /api/llm/switch,
                     /api/misra/search, /api/misra/rule/{rule_id},
                     /api/misra/categories, /api/misra/rules
```

**容错设计**:`task_ws` 路由通过 `try/except ImportError` 包裹,Redis 不可导入时降级为空路由。

### 7.2 核心层 core/

#### [core/hil/hil_manager.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/core/hil/hil_manager.py) — `HILManager`

HIL 人机协作管理器,支持 Redis 持久化(多 worker)与纯内存降级。

**关键数据结构**:
- `ApprovalRequest` dataclass:`request_id`, `checkpoint`, `content`, `timeout`, `created_at`, `status`(pending/approved/rejected/timeout),内部 `_event: asyncio.Event`
- `ApprovalResult` dataclass:`request_id`, `checkpoint`, `approved`, `comments`, `reviewer`, `status`(approved/rejected/timeout/skipped)

**核心方法**:
- `request_approval(checkpoint, content, timeout) -> dict` — 创建审批请求,`asyncio.wait_for(event.wait(), timeout)` 等待,超时自动批准
- `approve(request_id, comments, reviewer) -> dict` — 委托 `_resolve(approved=True, status="approved")`
- `reject(request_id, comments, reviewer) -> dict` — 委托 `_resolve(approved=False, status="rejected")`
- `get_pending_approvals() -> list[dict]`、`get_history() -> list[dict]`、`set_enabled(enabled)`、`clear()`

**Redis 持久化**:
- `hil:pending:{request_id}`(Hash,TTL = timeout + 60s)
- `hil:history`(String,JSON list)
- `hil:resolve` 频道(Pub/Sub 跨 worker 通知)

**检查点**:`requirement_review`、`contract_review`、`code_review`、`final_review`。

模块级:`get_hil_manager()`(懒加载单例)、`reset_hil_manager()`(测试用)。

#### core/llm/ — Web 层生产级 LLM 封装

| 文件 | 关键类/函数 | 作用 |
|------|------------|------|
| [llm.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/core/llm/llm.py) | `LLM(api_type, api_key, model, base_url, task_id, max_tokens)`, `chat(history, tools, tool_choice, max_retries, agent_name)` | 生产级 LLM 封装(重试 + tool call 修复 + Redis 推送) |
| [llm_factory.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/core/llm/llm_factory.py) | `LLMFactory(task_id)`, `get_all_llms() -> tuple[LLM, LLM, LLM, LLM]` | 4 Agent LLM 工厂(REQ_PARSER/CON_GEN/CODE_GEN/REPAIR) |
| [lmstudio_client.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/core/llm/lmstudio_client.py) | `LMStudioClient`, `UnifiedLLMClient`, `get_lmstudio_client()` | LM Studio 客户端(与 skyforge_llm 同构) |
| [local_client.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/core/llm/local_client.py) | `LocalLLMClient`, `get_local_llm_client()` | 本地 GGUF 推理(llama-cpp-python) |
| [model_router.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/core/llm/model_router.py) | `ModelRouter`, `get_model_router()`, `reset_model_router()` | 多模型路由器 |
| [cache.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/core/llm/cache.py) | `LLMCache`, `get_llm_cache()` | 进程级 TTL 缓存 |
| [json_parser.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/core/llm/json_parser.py) | `safe_parse_llm_json(text)` | 三级降级 JSON 解析 |
| [types.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/core/llm/types.py) | `ToolCall`, `Usage`, `StandardResponse` | 类型定义 |

**providers/** 子目录(`base.py`、`openai_chat.py`、`openai_responses.py`、`anthropic.py`)与 skyforge_llm 同构。

#### [core/streaming/stream_manager.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/core/streaming/stream_manager.py) — `StreamManager`

WebSocket 连接池管理器(Patch 4 Agent 思考流推送)。

| 方法 | 作用 |
|------|------|
| `register(websocket) -> str` | 生成 `uuid4().hex` 作为 `ws_id`,加锁存入(调用方需先 `accept()`) |
| `unregister(websocket_id)` | 加锁 pop |
| `send_to(websocket_id, message) -> bool` | 定向推送,失败自动 `unregister` |
| `broadcast(message) -> int` | 广播到所有连接,返回成功数 |
| `count() -> int` | 当前活跃连接数 |

模块级:`get_stream_manager()`(单例)。

### 7.3 schemas/ — Pydantic 数据模型

| 文件 | 关键内容 |
|------|---------|
| [enums.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/schemas/enums.py) | `AgentType(str, Enum)`(6 类:REQUIREMENT_PARSER/CONTRACT_GENERATOR/CODE_GENERATOR/CODE_REPAIRER/SIMULATION_ENGINE/REPORT_GENERATOR)、`AgentStatus(str, Enum)`(START/WORKING/DONE/ERROR/SUCCESS) |
| [response.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/schemas/response.py) | `Message`、`SystemMessage`、`AgentMessage`、`StreamMessage` |
| [request.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/schemas/request.py) | `GenerateRequest`、`UploadScadeRequest` |
| [tool_result.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/schemas/tool_result.py) | `ToolResult` |
| [dal_objectives.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/schemas/dal_objectives.py) | `DAL(Enum)`、`DALObjectiveDefinition`、`ALL_OBJECTIVES`、`get_objectives_for_dal(dal)` |
| [base.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/schemas/base.py) | 基础模型 |

### 7.4 services/ — 服务层

| 文件 | 关键类/方法 | 职责 |
|------|------------|------|
| [redis_manager.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/services/redis_manager.py) | `RedisManager`,`get_client()`, `publish_message(task_id, message)`, `subscribe_to_task(task_id)`, `set/get`, `ping()` | Redis 连接管理 + Pub/Sub 消息转发 + 消息文件持久化(`logs/messages/{task_id}.json`) |
| [ws_manager.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/services/ws_manager.py) | `WebSocketManager`,`connect(websocket, task_id)`, `disconnect(...)`, `send_personal_message(...)`, `broadcast(...)`, `send_task_event(...)`, `send_task_progress(...)`, `send_task_error(...)`, `_heartbeat_loop()`(30s 心跳) | WebSocket 连接池管理 + 结构化事件推送 |

模块级单例:`redis_manager = RedisManager()`、`ws_manager = WebSocketManager()`。

### 7.5 rag/ — Web 层 RAG 模块

与 `skyforge_engine.rag` 独立实现(同构):
- [rule_parser.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/rag/rule_parser.py):`MisraRule` dataclass, `parse_misra_rules(content)`, `categorize_rule(...)`
- [misra_searcher.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/rag/misra_searcher.py):`MisraRuleSearcher`(单例)
- [rag_enhancer.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/rag/rag_enhancer.py):`RagEnhancer.enhance_prompt(...)`, `build_misra_context(...)`

### 7.6 utils/

| 文件 | 关键函数 | 职责 |
|------|---------|------|
| [common_utils.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/utils/common_utils.py) | `transform_link`, `split_footnotes`, `create_task_id`, `ensure_safe_task_id`, `create_work_dir`, `get_work_dir`, `get_current_files` | 通用工具 |
| [cli.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/utils/cli.py) | `center_cli_str(text, width)`, `get_ascii_banner()` | 终端输出工具 |
| [log_util.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/utils/log_util.py) | `LoggerInitializer`, `logger`(全局) | loguru 日志初始化 |

---

## 8. 前端 frontend(Vue 3)

> 位置:`studio/frontend/`
> 定位:基于 Vue 3 + Vite + Pinia + shadcn-vue 的单页应用

### 8.1 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| 框架 | Vue 3 | ^3.5.13 (`<script setup>` + Composition API) |
| 构建 | Vite | ^6.1.0 |
| 语言 | TypeScript | ~5.7.2(严格模式) |
| 路由 | vue-router | 4(createWebHistory) |
| 状态管理 | Pinia + pinia-plugin-persistedstate | ^3.0.1 / ^4.5.0 |
| UI 底座 | reka-ui | ^2.0.0(shadcn-vue 依赖) |
| 组件库 | shadcn-vue(new-york 风格) | — |
| 样式 | Tailwind CSS 3 + tailwindcss-animate | CSS 变量主题 |
| 代码编辑器 | monaco-editor | ^0.55.1 |
| 图表 | echarts + vue-echarts | ^6.1.0 / ^8.0.1 |
| 虚拟滚动 | @tanstack/vue-virtual | ^3.13.31 |
| Markdown | marked + marked-katex-extension + katex + dompurify | — |
| 图标 | lucide-vue-next | ^0.475.0 |
| 测试 | Vitest + @vue/test-utils + jsdom | ^3.2.7 |
| Lint | Biome | 1.9.4 |
| 包管理器 | pnpm | 10.6.3 |

### 8.2 路由配置

文件:[src/router/index.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/router/index.ts)

使用 `createWebHistory()`,所有路由**懒加载**(动态 import)。

| 路径 | 组件 | 说明 |
|------|------|------|
| `/` | `pages/index.vue` | 营销首页(Hero + Bento Grid) |
| `/login` | `pages/login/index.vue` | 登录页 |
| `/chat` | `pages/chat/index.vue` | 聊天中转页(Sidebar + ServiceStatus + UserStepper) |
| `/task/:task_id` | `pages/task/index.vue` | 任务工作台(`props: true` 传 task_id) |
| `/generate` | `views/Generate.vue` | 代码生成全流程页 |
| `/compose` | `views/Compose.vue` | 组件组合验证页 |
| `/hil` | `views/HILPage.vue` | HIL 人机审批独立页 |

### 8.3 页面职责

| 页面 | 核心功能 |
|------|---------|
| `pages/index.vue` | 营销首页:DO-178C 徽章、4 项指标(233 测试/26 API/4 Agent/98.5% 合规率)、效率对比条、Agent 流水线卡片、4 张 Bento 卡片 |
| `pages/login/index.vue` | 极简包裹层:Logo + `<LoginForm />` |
| `pages/chat/index.vue` | Sidebar 三栏骨架 + ServiceStatus + UserStepper;`onMounted` 调 `getHelloWorld()` 健康检查 |
| `pages/task/index.vue` | **核心工作台**:4 Agent 流水线(REQ-Parser → CON-Gen → CODE-Gen → REPAIR);顶部 TaskToolbar + 中部 ResizablePanelGroup(左 ChatArea + 右 AgentTerminal + Tabs 代码/Diff)+ 底部 TaskStatusBar |
| `views/Generate.vue` | **功能最丰富**:ProviderPanel + MisraSearch + ScadeUpload + 需求输入 + AgentTerminal + 5 Tab 结果区(生成结果/修复历史/契约校验/数字孪生/DO-178C 报告)+ HILPanel + 双向追溯 |
| `views/Compose.vue` | 契约模板库(15 个预置模板)+ 三栏组件输入(A|连接配置|B)+ 兼容性检查 + 组合后代码 + 组合仿真结果 |
| `views/HILPage.vue` | 简单包裹层:标题 + `<HILPanel />` |

### 8.4 业务组件分类

#### 代码与编辑器类
- [MonacoCodeEditor.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/MonacoCodeEditor.vue):Monaco 编辑器,C 语言高亮,REQ/MISRA/CON 标签装饰器,追溯矩阵行高亮
- [MonacoDiffEditor.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/MonacoDiffEditor.vue):Monaco Diff 视图
- [CodeViewer.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/CodeViewer.vue):只读代码查看器
- [CodeDiff.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/CodeDiff.vue):代码 Diff 展示

#### Agent 与终端类
- [AgentTerminal.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/AgentTerminal.vue):VSCode 终端样式日志面板,红黄绿三圆点 + 虚拟滚动(万级日志)+ 打字机效果 + 闪烁光标;支持 mock 与真实 WS(`ws://localhost:8000/ws/agent-stream`);expose `start/stop/clear`
- [RepairTimeline.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/RepairTimeline.vue):MISRA 修复闭环时间线

#### 契约与合规类
- [ContractViewer.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/ContractViewer.vue):契约 YAML 渲染,CON 标签解析
- [ContractCheckResult.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/ContractCheckResult.vue):契约校验结果分区展示 + assert 代码
- [MisraSearch.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/MisraSearch.vue):MISRA-C 规则搜索框

#### 数字孪生与仿真类
- [FaultInjectPanel.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/FaultInjectPanel.vue):故障注入面板(12 种故障类型,多选叠加)
- [SimulationResult.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/SimulationResult.vue):仿真结果展示(通过/失败 + 统计 + 波形图)
- [WaveformChart.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/WaveformChart.vue):ECharts 波形图(输入/输出双曲线 + 故障区间红色 markArea)

#### LLM 与供应商类
- [ProviderPanel.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/ProviderPanel.vue):OpenCode 风格多供应商切换(6 Provider:DeepSeek/Qwen/OpenAI/Anthropic/Ollama/LMStudio)
- [LLMStatus.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/LLMStatus.vue):LM Studio 状态卡片 + Mock/真实 LLM 切换
- [ScadeUpload.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/ScadeUpload.vue):SCADE 文件拖拽上传与解析

#### HIL 人机协作类
- [HILPanel.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/HILPanel.vue):待审批列表 + 审批历史 + 超时倒计时

#### 报告与文件类
- [ReportDownload.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/ReportDownload.vue):DO-178C 报告生成与下载
- [Files.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/Files.vue):文件列表通用组件
- [FileConfirmDialog.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/FileConfirmDialog.vue):文件确认对话框

#### 聊天与消息类
- [ChatArea.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/ChatArea.vue):聊天区域,`@tanstack/vue-virtual` 虚拟滚动(estimateSize 80px,overscan 10)
- [Bubble.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/Bubble.vue):单条消息气泡(user/agent 两类)
- [SystemMessage.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/SystemMessage.vue):系统消息(info/warning/success/error)
- [NotebookArea.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/NotebookArea.vue) + [NotebookCell.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/NotebookCell.vue):笔记本区域与单元格

#### 布局与导航类
- [AppSidebar.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/AppSidebar.vue):应用侧边栏(logo + 菜单 + 用户卡片 + 主题切换 + 社交图标)
- [NavUser.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/NavUser.vue) / [UserStepper.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/UserStepper.vue) / [VersionSwitcher.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/VersionSwitcher.vue)

#### 任务与文件类(`components/task/`)
- [TaskToolbar.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/task/TaskToolbar.vue):任务顶部工具栏
- [TaskStatusBar.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/task/TaskStatusBar.vue):任务底部状态栏
- [AgentStatus.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/task/AgentStatus.vue):单个 Agent 状态徽章

#### 共享组件(`components/shared/`)
- [TagBadge.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/shared/TagBadge.vue):通用标签徽章(REQ/MISRA/CON/TST)
- [TerminalFrame.vue](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/components/shared/TerminalFrame.vue):终端外框(红黄绿圆点 + 标题)

#### UI 基础组件(`components/ui/`)
shadcn-vue 生成的新 york 风格组件,共 22 个目录:`alert / avatar / breadcrumb / button / card / collapsible / dialog / dropdown-menu / input / label / resizable / scroll-area / select / separator / sheet / sidebar / skeleton / stepper / switch / tabs / tetris / textarea / toast / tooltip`

### 8.5 状态管理(Pinia Stores)

所有 store 使用组合式 API 风格(setup function)。

| Store | 文件 | 核心状态 | 持久化 |
|-------|------|---------|--------|
| `apiKeys` | [stores/apiKeys.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/stores/apiKeys.ts) | 4 Agent 的 ModelConfig + openalexEmail | sessionStorage |
| `generate` | [stores/generate.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/stores/generate.ts) | requirement / isGenerating / generateResult / contract / generatedCode / repairIterations / contractCheckResult / simulationResult / activeAgent | 持久化 requirement/contract/generatedCode |
| `providerStore` | [stores/providerStore.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/stores/providerStore.ts) | providers(6 个) / selectedProviderId / selectedModelId | 手动 localStorage |
| `task` | [stores/task.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/stores/task.ts) | messagesByTask / currentTaskId / wsStatus / isRunning | 不持久化(实时 WS) |

**task store 关键 Actions**:
- `connectWebSocket(taskId)`:构造 `${VITE_WS_URL}/task/${taskId}`,创建 `TaskWebSocket` 实例,收到消息时 `appendMessage` + 检测 system 类型 success/warning/error 自动设 isRunning=false
- `loadTaskMessages(taskId)`:调 `getTaskMessages` + `mergeMessages`
- `closeWebSocket()` / `stopTask(taskId)` / `addUserMessage(content)` / `downloadMessages()`

**task store Computed**:`messages`、`chatMessages`(过滤 user + CODE-Gen + system)、`reqParserMessages / conGenMessages / codeGenMessages / reviewerMessages`(按 Agent 过滤)、`files`(从最新 CODE-Gen 消息提取)

### 8.6 服务层

#### [client.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/services/client.ts) — 统一 HTTP 客户端
- 零 axios 依赖,纯 fetch 封装
- `API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"`
- 默认超时 30s,使用 `AbortController`
- 导出:`request<T>(path, options, timeout)` / `getJSON<T>` / `postJSON<T>` / `postFormData<T>`

#### [apiSwitcher.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/services/apiSwitcher.ts) — Mock / 真实 API 切换器
- 定义 `ApiInterface` 契约(18 个方法),`realApi` 与 `mockApi` 都必须实现
- `state = reactive({ useRealAPI: loadInitial(), connected: false })`
- `loadInitial()`:从 `localStorage['airborne_use_real_api']` 读取,默认 `false`
- `getApi()`:每次调用读取最新 state,返回 `realAdapter` 或 `mockAdapter`
- `USE_REAL_API()` composable:返回 `{ useRealAPI, connected, setUseRealAPI }`

#### [api.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/services/api.ts) — 真实后端 API 封装
- 与 `mockApi.ts` 函数签名完全一致,便于 `apiSwitcher` 互换
- `withFallback<T>(realCall, fallback, label)`:try real → 失败降级到 mock
- 7 个 transform 函数:后端响应字段 → mockApi 类型字段

#### [mockApi.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/services/mockApi.ts) — Mock API 服务
- 数据常量:`@/mock/data.ts`(MOCK_CODE / MOCK_CONTRACT / MOCK_VIOLATIONS 等)
- 延迟策略:`setTimeout` 模拟网络延迟(200ms~1500ms)
- Mock WebSocket:`mockAgentStream` 定时推送(5s/条)

#### [taskApi.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/services/taskApi.ts) — 任务相关 API
- `getHelloWorld`, `getServiceStatus`, `getTaskMessages`, `cancelTask`, `getFiles`, `getFileDownloadUrl`, `submitModelingTask`, `validateApiKey`, `saveApiConfig` 等

#### [simulation.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/services/simulation.ts) — 数字孪生仿真逻辑
- 纯计算函数(无 IO):`genSineInput`, `lowpassFilter`, `computeStats`, `generateNormalSimulationResult`, `runFaultInjection`, `pickComposedCode`, `buildCompatibility`

#### [reportGenerator.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/services/reportGenerator.ts) — DO-178C 报告生成
- `buildReport(result)`:返回 `{ reportId, summary, html }`,7 个章节,DO-178C Level C 66 个目标

### 8.7 前后端交互方式

#### REST API
- 统一前缀:大部分 `/api/*`,任务相关为根路径
- 超时:默认 30s,文件上传 30s
- 错误处理:`ApiError` 抛出,`api.ts` 通过 `withFallback` 自动降级到 mock

#### WebSocket(两类)

**1. 任务消息 WebSocket**(`TaskWebSocket` 类,[utils/websocket.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/utils/websocket.ts))
- URL:`${VITE_WS_URL}/task/${task_id}`
- 重连机制:指数退避(initialDelay 1000ms,maxDelay 30000ms,maxRetries 10)
- 心跳:服务端发 `{type:"ping"}` → 客户端回 `{type:"pong", ts}`
- 状态机:connecting → connected → disconnected → reconnecting

**2. Agent 流 WebSocket**(`connectAgentStream`)
- URL:`ws://localhost:8000/ws/agent-stream`(默认)
- 推送 Agent 思考日志到 `AgentTerminal` 组件
- 当前 `AgentTerminal` 默认 `useMock=true`

#### nginx 反代配置
- `/api/` → `http://backend:8000`(REST)
- `/ws/` → `http://backend:8000`(WebSocket,带 Upgrade,120s 超时)
- `/task/` → `http://backend:8000`(任务 WebSocket)
- `/assets/` 长期缓存(1 年,immutable)
- SPA fallback:`try_files $uri $uri/ /index.html`

### 8.8 工具与类型

| 文件 | 职责 |
|------|------|
| [types/domain.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/types/domain.ts) | 40+ 领域类型定义(单真理源) |
| [utils/enum.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/utils/enum.ts) | `AgentType` + `ApiType` 枚举 |
| [utils/response.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/utils/response.ts) | 后端消息结构(`Message` 联合类型) |
| [utils/websocket.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/utils/websocket.ts) | `TaskWebSocket` 类 |
| [utils/tagParser.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/utils/tagParser.ts) | `parseInlineTags`(REQ/MISRA-Rule/CON/TST 内联标签解析) |
| [utils/markdown.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/utils/markdown.ts) | `renderMarkdown`(marked + KaTeX + DOMPurify XSS 防护) |
| [utils/contractTemplates.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/utils/contractTemplates.ts) | 15 个机载组件契约模板 |
| [composables/useTheme.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/composables/useTheme.ts) | 主题切换(暗黑/明亮) |
| [lib/utils.ts](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/src/lib/utils.ts) | `cn()`(twMerge + clsx) |

---

## 9. 依赖关系

### 9.1 包级依赖

```
skyforge-core (Layer 2, CLI)
    │
    ├── 依赖: pyyaml, numpy, loguru, pydantic, pydantic-settings
    ├── [llm] extras: httpx, openai
    ├── [report] extras: jinja2
    └── 委托执行 → skyforge-engine (Layer 0)
                       │
                       ├── 依赖: pyyaml, numpy, loguru, packaging
                       │         pydantic-settings, jinja2
                       └── 按需调用 → skyforge-llm (Layer 1, 可选)
                                        │
                                        ├── 依赖: skyforge-engine==0.4.0, httpx[socks], openai, anthropic
                                        ├── providers/anthropic.py → anthropic SDK
                                        ├── providers/openai*.py → openai SDK
                                        ├── local.py → llama-cpp-python, huggingface_hub (运行时懒加载)
                                        └── 委托 → skyforge_engine.config.settings (读 LLM_CACHE_*)
                                                   skyforge_engine.utils.log_util.logger
```

> 注:`skyforge-llm` 反向依赖 `skyforge-engine`(用于 `settings` 与 `logger`),而 `skyforge-engine` 又在运行时按需调用 `skyforge-llm`。这是**运行时循环依赖但通过懒导入打破**(见 `pipeline.py` line 51-53 的 try/except fallback)。

### 9.2 engine 内部模块依赖关系

```
pipeline.py
  ├─ agents.requirement_parser.RequirementParserAgent
  ├─ agents.llr_generator.LLRGeneratorAgent
  ├─ agents.architecture_designer.design_architecture
  ├─ agents.contract_generator.ContractGeneratorAgent
  ├─ agents.code_generator.CodeGeneratorAgent
  ├─ agents.code_repairer.CodeRepairerAgent
  │     └─ agents.misra_fixes (56 规则修复器)
  │
  ├─ tools.contract_checker.check
  ├─ tools.cppcheck_scanner.scan (scan_with_result)
  ├─ tools.contract_formal_verifier.verify_contract
  ├─ tools.cbmc_verifier.run_cbmc_verification
  ├─ tools.z3_verifier.verify_contract_constraints
  ├─ tools.contract_to_assert.contract_to_assert (数字孪生用)
  ├─ tools.pr_manager.get_pr_manager (问题报告)
  │
  ├─ digital_twin.simulation_engine.SimulationEngine
  │     ├─ digital_twin.virtual_mcu.VirtualMCU
  │     ├─ digital_twin.virtual_sensor.VirtualSensor
  │     ├─ digital_twin.fault_injector.FaultInjector
  │     └─ digital_twin.hil_adapter.{SerialHilAdapter, JtagHilAdapter}
  │
  ├─ report.evidence_collector.get_collector
  ├─ report.report_generator.generate_report
  ├─ report.coverage_analyzer.analyze_code_coverage
  ├─ report.do178_objectives.check_objectives
  ├─ report.traceability_matrix.build_matrix
  ├─ report.psac_generator.generate_psac
  │
  ├─ scade.lustre_parser.parse_glustre
  ├─ scade.lustre_to_requirement.{convert, convert_to_contract}
  │
  ├─ rag.rag_enhancer.enhance_prompt (各 Agent 调用)
  │     └─ rag.misra_searcher.MisraRuleSearcher
  │           └─ rag.rule_parser.parse_misra_rules
  │     └─ rag.semantic_search.SemanticMisraSearcher (可选)
  │
  ├─ dal.mcdc_calculator.analyze_coverage
  ├─ dal.gcov_collector.collect_coverage
  │
  ├─ schemas.dal_objectives.{DAL, get_objectives_for_dal}
  │
  └─ utils.log_util.logger (全局日志)
```

### 9.3 skyforge_llm 被引用情况

| 文件 | 引用方式 |
|------|---------|
| `skyforge_engine/pipeline.py` | `from skyforge_llm.client import get_lmstudio_client`(try/except 包裹,失败时定义本地 fallback) |
| `skyforge_engine/agents/requirement_parser.py` | 使用 `get_lmstudio_client` / `safe_parse_llm_json` |
| `skyforge_engine/agents/contract_generator.py` | 使用 `get_lmstudio_client` |
| `skyforge_engine/agents/code_generator.py` | 使用 `get_lmstudio_client` |
| `skyforge_engine/agents/code_repairer.py` | 使用 `get_lmstudio_client` |
| `skyforge_engine/agents/architecture_designer.py` | 使用 `get_lmstudio_client` |
| `skyforge_engine/agents/llr_generator.py` | 使用 `get_lmstudio_client` |
| `skyforge_engine/demo_mode.py` | 使用 `get_lmstudio_client` / `UnifiedLLMClient` |

### 9.4 缓存层次汇总

| 层 | 类型 | 作用域 | TTL | 失效策略 |
|---|---|---|---|---|
| `LLMCache` | 进程内存 dict | 进程级 | 3600s(可配) | TTL 过期惰性清理 |
| `LMStudioClient._available` | 实例字段 | 单例进程级 | 60s | `force_recheck` 强制刷新 |
| `LocalLLMClient._available` | 实例字段 | 单例进程级 | 300s | `force_recheck` 强制刷新 |
| `ModelRouter._latency` | 实例字段 | 单例进程级 | — | 超时降级 |
| `reports._report_cache` | 模块字典 | 进程级 | 3600s + 最多 50 条 | TTL + 容量上限,LRU 清理 |
| `HILManager._requests` | 实例字典 | 进程级 | — | approve/reject 后移除 |
| `HILManager._history` | 实例列表 | 进程级 + Redis | — | 进程级 + Redis 双写 |
| `MisraRuleSearcher` | 单例 | 进程级 | — | 启动时加载一次 |
| Redis Pub/Sub | 跨进程 | 全实例 | — | 实时推送 |
| Redis Hash/String | 跨进程 | 全实例 | TTL | HIL pending `timeout+60s` |

---

## 10. 项目运行方式

### 10.1 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.12+ | 后端运行时 |
| Node.js | 18+ | 前端运行时 |
| pnpm | 10+ | 前端包管理器 |
| uv | 最新 | 后端包管理器 |
| Redis | 6+ | 可选,任务队列 |
| LM Studio | 最新 | 可选,本地 LLM |
| Cppcheck | 2.x(推荐) | 可选,MISRA-C 扫描 |
| GCC | 任意 | 可选,数字孪生真实编译 |

### 10.2 一键启动(开发模式,推荐)

**Windows**:`start.bat` 或 `.\start.ps1`
**Linux / Mac**:`bash start.sh`

`start.sh` 自动完成 6 个阶段:
1. **[0/5] 清理残留进程**:杀掉端口 8000 上的 uvicorn/python,以及 5173/5174/5175 上的 vite/node
2. **[1/5] 检查依赖**:Python(优先 `uv run python`)、Node.js、pnpm(缺失自动安装)、uv
3. **[2/5] 后端准备**:`cd src` → 若无 `.venv` 则 `uv venv` → 优先 `uv sync`,否则 `pip install -e .`
4. **[3/5] 前端准备**:`cd studio/frontend` → `pnpm install`
5. **[4/5] 启动 Redis**(可选)
6. **[5/5] 启动服务**:
   - 后端:`PYTHONPATH="$ROOT/src:$ROOT/studio"` `python -m uvicorn studio.app.main:app --host 0.0.0.0 --port 8000 --ws-ping-interval 60 --ws-ping-timeout 120 --reload`
   - 前端:`pnpm run dev`

**访问地址**:
- 前端:http://localhost:5173
- 后端 API:http://localhost:8000
- API 文档(Swagger):http://localhost:8000/docs

### 10.3 手动启动(分步)

**后端**:
```bash
cd src
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install uv
uv sync
cp ../config/.env.example ../config/.env   # 编辑配置
uvicorn studio.app.main:app --reload --host 0.0.0.0 --port 8000
```

**前端**:
```bash
cd studio/frontend
pnpm install
pnpm dev
```

### 10.4 Docker 部署

#### 生产环境([docker/docker-compose.yml](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/docker/docker-compose.yml))

```bash
docker compose up -d --build     # 在 docker/ 父目录执行
```

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| redis | skyforge_redis | 6379(内部) | redis:alpine,256MB maxmemory,allkeys-lru |
| backend | skyforge_backend | 8000:8000 | ENV=PROD,2 CPU/2G 内存,健康检查 `/api/health` |
| frontend | skyforge_frontend | 80:80 | nginx 反代 |

#### 开发环境([docker/docker-compose.dev.yml](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/docker/docker-compose.dev.yml),含热重载)

```bash
make dev-up      # 或 docker compose -f docker/docker-compose.dev.yml up --build
```

| 服务 | 端口 | 特点 |
|------|------|------|
| redis | 6379:6379 | 无密码 |
| backend | 8000:8000 | ENV=DEV,挂载 `.:/app`,volume `backend_venv` |
| frontend | 5173:5173 | 使用 `Dockerfile.dev`,挂载 `./studio/frontend:/app` |

### 10.5 环境变量配置

#### 基础环境变量([config/.env.example](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/config/.env.example))

```env
# 环境设置
ENV=dev                          # dev / prod

# LLM 配置
USE_LLM=true                     # 是否使用真实 LLM;不可用时自动降级 Mock
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LLM_MODEL=qwen2.5-coder-7b       # 未设置则用 LM Studio 默认模型
LLM_API_KEY=                     # 本地 LM Studio 可留空
LLM_MAX_TOKENS=8192

# 性能优化
LLM_CACHE_ENABLED=true           # 相同 prompt+system_prompt 缓存
LLM_CACHE_TTL=3600               # 缓存 TTL(秒)

# HIL 人机协作
HIL_ENABLED=false
HIL_TIMEOUT=300                  # 超时视为拒绝

# 真实工具链
USE_REAL_CPPCHECK=false          # true: 调用 cppcheck --addon=misra --dump
USE_REAL_GCC=false               # true: 数字孪生使用真实 GCC 编译

# Redis(可选)
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=10

# 系统配置
LOG_LEVEL=INFO                   # DEBUG/INFO/WARN/ERROR
DEBUG=true
MAX_RETRIES=3                    # LLM 调用失败重试次数
SERVER_HOST=http://localhost:8000
CORS_ALLOW_ORIGINS=http://localhost:5173,http://127.0.0.1:5173  # 支持 * / 逗号分隔 / JSON 数组
```

#### Agent 级别 LLM 配置(可选,每个 Agent 独立)

支持为每个 Agent(REQ_PARSER / CON_GEN / CODE_GEN / REPAIR)单独配置:
- `<AGENT>_API_TYPE`(`openai-chat` / `openai-responses` / `anthropic`)
- `<AGENT>_API_KEY`
- `<AGENT>_MODEL`
- `<AGENT>_BASE_URL`
- `<AGENT>_MAX_TOKENS`(默认 4096)

未设置时回退到全局 `LMSTUDIO_BASE_URL` / `LLM_MODEL`。

#### 前端环境变量([studio/frontend/.env.development](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/.env.development))

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

#### 配置文件加载优先级(`setting.py`)
1. `.env`(基础配置)
2. `.env.<ENV>`(环境特定,如 `.env.dev` / `.env.prod`)
3. 进程环境变量(最高优先级)

### 10.6 Makefile 命令清单

| 命令 | 作用 |
|------|------|
| `make help` | 显示帮助信息 |
| `make dev` | 启动本地开发环境(等价 `bash start.sh`) |
| `make dev-up` | Docker Compose 启动开发环境 |
| `make dev-down` | 停止 Docker 开发环境 |
| `make build` | 构建全部(触发 `build-frontend`) |
| `make build-frontend` | 构建前端:`cd studio/frontend && pnpm install --frozen-lockfile && pnpm build` |
| `make test` | 运行全部测试(前端 + 后端) |
| `make test-frontend` | 前端测试:`cd studio/frontend && pnpm vitest run` |
| `make test-backend` | 后端测试:`cd src && PYTHONPATH=.. uv run python -m unittest discover -s ../studio/app/tests -p "test_*.py"` |
| `make lint` | 检查代码质量(前端 Biome + 后端 Ruff) |
| `make lint-frontend` | 前端 Biome 检查 |
| `make lint-backend` | 后端 Ruff 检查 |
| `make lint-fix` | 自动修复:前端 `pnpm biome check --write ./src` + 后端 `uv run ruff check --fix .` |
| `make typecheck` | TypeScript 类型检查:`cd studio/frontend && pnpm vue-tsc -b` |
| `make do178c-check` | DO-178C 合规检查:检查 8 个文档 + 运行 `tool_chain_validator` |
| `make do178c-docs` | 列出 DO-178C 文档状态 |
| `make clean` | 清理构建产物 |

### 10.7 前端开发命令

| 命令 | 脚本 | 说明 |
|------|------|------|
| `pnpm dev` | `vite` | 启动开发服务器 |
| `pnpm build` | `vue-tsc -b && vite build` | 类型检查 + 生产构建 |
| `pnpm preview` | `vite preview` | 预览构建产物 |
| `pnpm test` | `vitest run` | 单次运行单元测试 |
| `pnpm test:watch` | `vitest` | 监听模式测试 |
| `pnpm test:coverage` | `vitest run --coverage` | 测试覆盖率 |

---

## 11. API 接口参考

### 11.1 REST API 端点

| 方法 | 路径 | 请求模型 | 作用 | 限流 |
|------|------|---------|------|------|
| GET | `/` | — | API 导航 | — |
| GET | `/favicon.ico` | — | 占位(204) | — |
| GET | `/api/health` | — | 健康检查(返回 LLM/GCC/Redis 状态) | 30/min |
| GET | `/api/stats` | — | 运行统计 | 10/min |
| POST | `/api/generate` | `GenerateRequest{requirement, scade_file}` | 触发完整 Agent 流水线(含 HIL 检查点) | — |
| POST | `/api/upload-scade` | `UploadFile` (multipart) | 上传 G-Lustre 文件并解析 | — |
| POST | `/api/repair` | `RepairRequest{code, contract, max_iterations=3, req_id}` | 单独触发修复闭环 | — |
| POST | `/api/check-contract` | `CheckContractRequest{code, contract, cid}` | 契约校验 + 断言插桩 | — |
| POST | `/api/simulate` | `SimulateRequest{code, contract, fault_type?, fault_params?, steps=200}` | 数字孪生仿真 | — |
| GET | `/api/fault-types` | — | 5 类故障描述与默认参数 | — |
| POST | `/api/report` | `ReportRequest{pipeline_result}` | 生成 DO-178C HTML 合规报告 | — |
| GET | `/api/report/download` | `?session_id=` (query) | 下载报告 | — |
| POST | `/api/compose` | `ComposeRequest{component_a, component_b, connection, simulate, steps}` | 组件组合验证 | — |
| POST | `/api/check-compatibility` | `CheckCompatibilityRequest{contract_a, contract_b, connection}` | 契约兼容性单独检查 | — |
| GET | `/api/hil/pending` | — | 获取待审批请求 | — |
| POST | `/api/hil/approve` | `HilApprovalRequest{request_id, comments, reviewer}` | 批准 HIL | — |
| POST | `/api/hil/reject` | `HilApprovalRequest{request_id, comments, reviewer}` | 拒绝 HIL | — |
| GET | `/api/hil/history` | — | 审批历史 | — |
| GET | `/api/models` | — | 列出 LM Studio 可用模型 | — |
| POST | `/api/models/select` | `ModelSelectRequest{model_id}` | 手动选择模型 | — |
| POST | `/api/models/clear` | — | 清除手动选择 | — |
| GET | `/api/llm/status` | — | LLM 状态 | — |
| POST | `/api/llm/switch` | `LlmSwitchRequest{use_llm}` | 切换 USE_LLM 开关 | — |
| GET | `/api/misra/search` | `?q=&top_k=5` | MISRA-C 关键词检索 | — |
| GET | `/api/misra/rule/{rule_id}` | path(`+` 解码为空格) | 获取单条规则 | — |
| GET | `/api/misra/categories` | — | 分类/严重程度统计 | — |
| GET | `/api/misra/rules` | `?category=&limit=0` | 列出规则(可按分类过滤) | — |

### 11.2 WebSocket 端点

#### `/ws/agent-stream` — Agent 思考流

**协议**:
1. 客户端连接后发送 JSON `{"requirement": "...", "scade_file": "..."}`
2. 服务端调用 `run_full_pipeline(..., log_hook=log_hook)`,通过 `log_hook` 逐条推送 Agent 思考消息
3. 流水线完成后推送 `{"level": "complete", "result": {...}}`

**消息格式**:
```json
{
  "agent": "REQ-Parser" | "CON-Gen" | "CODE-Gen" | "REPAIR" | "SYSTEM" | "TERMINAL",
  "level": "info" | "success" | "warn" | "error" | "complete",
  "thought": "消息内容",
  "time": "ISO 8601 时间戳",
  "result": {}
}
```

#### `/task/{task_id}` — 任务消息流(依赖 Redis)

**协议**:Redis Pub/Sub 转发模式
1. `ensure_safe_task_id(task_id)` 校验合法性(防路径遍历)
2. 检查 Redis 中 `task_id:{safe_task_id}` 键是否存在
3. `ws_manager.connect(websocket)` 注册到全局连接池
4. `redis_manager.subscribe_to_task(safe_task_id)` 订阅 `task:{task_id}:messages` 频道
5. 每 100ms 轮询 pubsub.get_message,转发给前端

---

## 12. 测试体系

### 12.1 后端测试

位置:`studio/app/tests/`,共 13 个测试文件,使用 `unittest` 框架(部分用 `fastapi.testclient.TestClient`)。

测试前设置 `USE_LLM=false`、`LMSTUDIO_BASE_URL=http://localhost:9999/v1`、`HIL_ENABLED=false` 避免触发真实 LLM/硬件。

| 测试文件 | 覆盖范围 |
|---------|---------|
| `test_day1.py` | Day 1 核心链路:`run_pipeline("实现一个低通滤波器")` → 验证需求 JSON、契约 YAML、C 代码、Cppcheck 结果、契约→断言转换 |
| `test_day2.py` | 修复闭环 + 契约校验 + MISRA 模板修复:`CodeRepairerAgent`、`repair_loop`、`contract_check`、`cppcheck_scan` |
| `test_day3.py` | 数字孪生仿真:`VirtualSensor`(5 类故障 + CSV)、`VirtualMCU`(编译/运行/降级)、`SimulationEngine`、契约断言注入 |
| `test_e2e.py` | 端到端 HTTP 流程:12 步 API 流程(generate → check-contract → simulate → report → compose → fault-types → llm/status → models → hil → upload-scade) |
| `test_hil_router.py` | HIL + 多模型路由集成:`ModelRouter`、`HILManager`、pipeline HIL 集成(reject 时正确中止) |
| `test_llm_integration.py` | LM Studio 集成:`safe_parse_llm_json` 三级降级、`USE_LLM=false` Mock、LM Studio 不可达降级 |
| `test_psac_generator.py` | PSAC 文档生成器:基本生成、Markdown 渲染、空 result、含违规、仿真失败、契约失败 |
| `test_rag.py` | RAG 知识库:`categorize_rule`、`parse_misra_rules`、`MisraRuleSearcher`、`RagEnhancer` |
| `test_report.py` | DO-178C 合规报告:HTML 报告 7 章节、追溯矩阵、12 项目标检查、API 路由 |
| `test_scade.py` | SCADE G-Lustre 输入:`parse_glustre`(简单 node / pre / if-then-else / 多变量 / locals / 范围注释)、`convert` / `convert_to_contract`、pipeline 集成 |
| `test_websocket.py` | WebSocket 流式推送:连接建立与断开、`/ws/agent-stream`、`StreamManager` 注册/注销/广播 |
| `test_composable.py` | 组件可组合性(DO-178C 6.5):顺序/并行/反馈组合、契约兼容性检查、组合后仿真 |
| `test_common_utils.py` | `create_task_id` 生成、`ensure_safe_task_id` 合法/非法(路径遍历)/空值校验 |

### 12.2 前端测试

| 文件 | 测试对象 |
|------|---------|
| `components/__tests__/AgentTerminal.test.ts` | AgentTerminal 组件 |
| `components/__tests__/ContractViewer.test.ts` | ContractViewer 组件 |
| `components/__tests__/FaultInjectPanel.test.ts` | 故障注入面板 |
| `components/__tests__/MonacoCodeEditor.test.ts` | Monaco 编辑器 |
| `components/__tests__/WaveformChart.test.ts` | 波形图 |
| `services/reportGenerator.test.ts` | 报告生成 |
| `services/simulation.test.ts` | 仿真逻辑 |
| `utils/tagParser.test.ts` | 标签解析 |

### 12.3 代码质量

- **后端**:Ruff `>=0.5`(`make lint-backend`)
- **前端**:Biome 1.9.4(`make lint-frontend`)
- **类型检查**:vue-tsc(`make typecheck`)
- **CI/CD**:GitHub Actions([.github/workflows/ci.yml](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/.github/workflows/ci.yml))

---

## 13. 关键设计要点

### 13.1 MISRA-C:2012 强制合规要点

代码生成时遵守的 MISRA-C 规则:

| 规则 | 要求 |
|------|------|
| Rule 8.9 | 模块内部状态变量声明为 `static`,限制作用域 |
| Rule 8.13 | 接口仅暴露必要符号,只读指针标注 `const` |
| Rule 10.1 | 未初始化保护(首次调用前自动 init) |
| Rule 10.4 | 浮点运算显式类型(避免隐式转换) |
| Rule 15.7 | 所有 `if`/`else` 必须用花括号包裹 |
| Rule 17.7 | 函数返回值必须检查 |
| Rule 21.3 | 禁止动态内存(`malloc`/`free`) |

### 13.2 Mock 降级策略

SkyForge 在外部工具不可用时均有优雅降级路径:

| 场景 | 降级方式 |
|------|---------|
| LLM 不可用(`USE_LLM=False`) | 各 Agent 使用 Mock 实现(规则引擎 + 模板拼接),日志标记 `[Mock]` |
| GCC 不可用(`USE_REAL_GCC=False`) | VirtualMCU 使用 Mock 编译/执行 |
| Cppcheck 不可用(`USE_REAL_CPPCHECK=False` 或未安装) | Mock 扫描(8 种规则模式匹配) |
| Z3 不可用 | 跳过形式化验证,返回 `satisfiable=True` |
| CBMC 不可用 | 跳过有界模型检查 |
| ChromaDB/sentence-transformers 不可用 | 语义搜索降级到关键词匹配 |
| Redis 不可用 | HIL 降级为纯内存模式,`task_ws` 路由降级为空 |

### 13.3 安全设计

- **输入验证**:所有用户输入经 Pydantic 验证
- **LLM 安全**:`skyforge_llm.security`(sanitizer/validator/auditor)三重封装
- **路径遍历防护**:`ensure_safe_task_id` 校验任务 ID 合法性
- **安全 Headers**:`security_headers` 中间件注入 `X-Content-Type-Options`、`X-Frame-Options`、`X-XSS-Protection`
- **CORS**:可配置 `CORS_ALLOW_ORIGINS`
- **API 限流**:SlowAPI(`/api/health` 30/min,`/api/stats` 10/min)
- **前端 XSS 防护**:DOMPurify
- **全局异常处理**:统一返回 `{"detail": "Internal server error"}` 500 响应

### 13.4 DO-178C 合规覆盖

| DO-178C 过程 | 状态 | 文档路径 |
|-------------|------|---------|
| 计划过程 (§4) | 已补齐 | `docs/compliance/PSAC.md` / `SDP.md` / `SVP.md` |
| 开发过程 (§5) | 进行中 | HLR/LLR + 契约式设计 |
| 验证过程 (§6) | 进行中 | Cppcheck + 契约校验 + 数字孪生 |
| 配置管理 (§7) | 进行中 | `docs/compliance/SCMP.md` + Git + PR 系统 |
| 质量保证 (§8) | 进行中 | `docs/compliance/SQAP.md` + CI 自动检查 |

DAL 等级支持:A(71 目标)/ B(69)/ C(62)/ D(26)/ E(0)。

### 13.5 插件系统

详见 [docs/PLUGIN_DEVELOPMENT.md](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/docs/PLUGIN_DEVELOPMENT.md)。

| 扩展类型 | 基类 | 用途 |
|---------|------|------|
| AgentPlugin | `skyforge_engine.plugins.base.AgentPlugin` | 自定义智能 Agent |
| ToolPlugin | `ToolPlugin` | 自定义工具(供 Agent 调用) |
| TemplatePlugin | `TemplatePlugin` | 自定义代码模板 |
| ReportPlugin | `ReportPlugin` | 自定义报告生成器 |
| ValidatorPlugin | `ValidatorPlugin` | 自定义验证规则 |

**插件生命周期**:UNLOADED → LOADED(`on_load`) → ACTIVE(`on_activate`) → INACTIVE(`on_deactivate`) → UNLOADED(`on_unload`);异常进入 ERROR(`on_error`)。

### 13.6 性能优化点

1. **并行处理**:Agent 可并行执行独立任务(`asyncio.gather`)
2. **增量更新**:只重新生成受影响的部分
3. **缓存机制**:缓存 LLM 响应和中间结果(`LLM_CACHE_ENABLED`,TTL 默认 3600s)
4. **懒加载**:按需加载非核心模块
5. **前端分包**:Vite manualChunks(`monaco` / `echarts` / `vendor` 三块拆分)
6. **虚拟滚动**:`@tanstack/vue-virtual`(ChatArea / AgentTerminal 万级消息)

### 13.7 已知问题与注意事项

1. **`skyforge_llm/__init__.py` vs `client.py` 的 import 不一致**:`UnifiedLLMClient._get_local` 中 `from skyforge_llm.local_client import get_local_llm_client`,但实际模块为 `local.py`。运行时该 import 会失败,导致本地 GGUF 后端永远不可用,自动降级到 LM Studio。
2. **`sanitizer.py` 部分实现**:`_VERSION_PATTERN` 定义未使用;docstring 承诺的"移除 C 代码注释""脱敏版本号""移除项目内部代号和客户信息"未实现。
3. **`security/` 子模块未接入 Pipeline**:auditor/sanitizer/validator 已实现但 engine 层未调用,属预留接口。
4. **`UnifiedLLMClient.chat_async` 默认 `max_tokens=8192`** vs `chat` 默认 `2048`:两个方法默认值不一致,可能导致行为差异。
5. **`providers/` 与 `client.py` 双轨未打通**:`UnifiedLLMClient` 未调用 `BaseProvider.call()`,Provider 抽象层当前未被 Pipeline 使用,属预留设计。

---

## 附录:关键文件路径速查

### 配置与脚本
- [README.md](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/README.md) — 项目主 README
- [pyproject.toml](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/pyproject.toml) — 顶层 workspace 配置
- [Makefile](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/Makefile) — 开发命令
- [start.sh](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/start.sh) — 一键启动脚本
- [config/.env.example](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/config/.env.example) — 环境变量示例

### 后端核心源码
- [src/skyforge_engine/pipeline.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/pipeline.py) — Pipeline 全流程编排
- [src/skyforge_engine/config.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_engine/config.py) — 引擎配置类
- [studio/app/main.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/app/main.py) — FastAPI 应用入口
- [src/skyforge_core/cli.py](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/src/skyforge_core/cli.py) — CLI 入口

### Docker 配置
- [docker/docker-compose.yml](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/docker/docker-compose.yml) — 生产环境
- [docker/docker-compose.dev.yml](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/docker/docker-compose.dev.yml) — 开发环境
- [docker/Dockerfile](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/docker/Dockerfile) — 后端镜像
- [studio/frontend/Dockerfile](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/Dockerfile) — 前端生产镜像
- [studio/frontend/nginx.conf](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/studio/frontend/nginx.conf) — Nginx 配置

### 文档
- [docs/ARCHITECTURE.md](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/docs/ARCHITECTURE.md) — 架构文档
- [docs/user/部署说明.md](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/docs/user/部署说明.md) — 部署说明
- [docs/user/使用教程.md](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/docs/user/使用教程.md) — 使用教程
- [docs/PLUGIN_DEVELOPMENT.md](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/docs/PLUGIN_DEVELOPMENT.md) — 插件开发指南
- [docs/compliance/](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/docs/compliance/) — DO-178C 合规文档(PSAC/SDP/SVP/SCMP/SQAP/TQP/TOR/TAS)
- [docs/ROADMAP.md](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/docs/ROADMAP.md) — 路线图
- [ThirdParty.md](file:///c:/Users/Lin/Desktop/Programs/Air/SkyForge/ThirdParty.md) — 第三方组件清单

---

> 本 Code Wiki 基于 SkyForge v0.4.0 源码分析生成,涵盖项目整体架构、主要模块职责、关键类与函数说明、依赖关系、项目运行方式等关键信息。如有疑问,请参阅源码注释与 `docs/` 目录下的详细文档。
