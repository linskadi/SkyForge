# SDP — 软件开发计划（Software Development Plan）

> **文档标识**: SDP-SKYFORGE-V1.0
> **日期**: 2026-07-21
> **状态**: 工程草案（比赛版）；不代表适航批准
> **DO-178C 章节**: §4.2

---

## 文档目的

本文档定义SkyForge项目的软件开发过程、方法、工具、标准和交付物。主要目的包括：
1. 规定软件开发生命周期模型和阶段划分
2. 定义开发环境、工具链和编码标准
3. 明确各阶段的输入输出和验证方法
4. 为软件验证计划（SVP）提供开发过程依据

## 适用范围

本文档适用于：
- SkyForge工具自身的软件开发过程
- SkyForge生成的机载C代码的开发过程
- 所有参与SkyForge开发的团队成员

## 引用标准

| 标准 | 版本 | 适用性 | 引用章节 |
|------|------|--------|---------|
| **DO-178C** | 2011 | 机载软件适航审定核心标准 | §4.2, §5 |
| **DO-330** | 2011 | 软件工具鉴定考量 | §12.2 |
| **MISRA-C:2012** | 2012 | C 语言安全编程规范 (143 条规则) | §4.1 |
| **PEP 8** | — | Python 编码规范 | §4.1 |
| **Biome 规则** | — | TypeScript 编码规范 | §4.1 |

---

## 1. 引言

### 1.1 范围

本文档定义 SkyForge 机载软件轻量化开发工具的软件开发生命周期、方法、工具、标准和交付物。适用于 SkyForge 工具自身及其所生成的机载 C 代码。

### 1.2 引用文档

| 文档 | 标识 |
|------|------|
| PSAC | [PSAC.md](./PSAC.md) |
| SVP | [SVP.md](./SVP.md) |
| SCMP | [SCMP.md](./SCMP.md) |
| SQAP | [SQAP.md](./SQAP.md) |
| TQP | [TQP.md](./TQP.md) |
| DO-178C | RTCA/DO-178C (2011) |
| MISRA-C:2012 | MISRA C:2012 Guidelines |

---

## 2. 开发生命周期

### 2.1 生命周期模型

采用**增量迭代 + 敏捷开发**混合模型：

```
Iteration 1 ──── Iteration 2 ──── Iteration 3
    │                │                │
    ├─ 计划           ├─ 计划           ├─ 计划
    ├─ 需求          ├─ 需求          ├─ 需求
    ├─ 设计          ├─ 设计          ├─ 设计
    ├─ 编码          ├─ 编码          ├─ 编码
    ├─ 测试          ├─ 测试          ├─ 测试
    └─ 评审          └─ 评审          └─ 评审
```

### 2.2 开发阶段

| 阶段 | 输入 | 输出 | 验证方式 |
|------|------|------|---------|
| **需求分析** | 用户自然语言需求 | HLR (结构化 JSON) | HIL 需求评审 |
| **低层需求** | HLR | LLR (细化设计需求) | 契约生成 + 校验 |
| **架构设计** | HLR + LLR | 契约 YAML (.contract) | 契约校验器 |
| **代码生成** | 契约 + HLR/LLR | MISRA-C C 代码 | Cppcheck 扫描 |
| **修复闭环** | 违规列表 | 修复后代码 | 重扫验证 |
| **仿真验证** | 编译通过代码 | 仿真结果 + 波形图 | 数字孪生仿真 |
| **报告生成** | 全流程结果 | DO-178C HTML 报告 | do178_objectives |

---

## 3. 开发环境

### 3.1 开发工具链

| 工具 | 版本 | 用途 |
|------|------|------|
| **Python** | 3.12+ | 后端运行时 |
| **Node.js** | 22.22.2 | 前端运行时 |
| **FastAPI** | >=0.115.8 | Web 框架 |
| **Vue 3** | ^3.5.13 | 前端框架 |
| **Docker** | 最新稳定版 | 容器化部署 |
| **Git** | 最新稳定版 | 版本控制 |
| **GitHub Actions** | — | CI/CD |

### 3.2 代码质量工具

| 工具 | 语言 | 配置 | 用途 |
|------|------|------|------|
| **Ruff** | Python | `pyproject.toml` | Lint + 格式化 |
| **Pyright** | Python | `pyrightconfig.json` | 类型检查 |
| **Biome** | TypeScript | `biome.json` | Lint + 格式化 |
| **vue-tsc** | TypeScript | `tsconfig.json` | 类型检查 |
| **Cppcheck** | C | `--addon=misra` | MISRA-C 静态分析 |
| **GCC** | C | `-std=c11 -O2` | 编译验证 |

### 3.3 测试工具

| 工具 | 用途 | 当前覆盖 |
|------|------|---------|
| **pytest** | 后端 / 引擎 / LLM 安全测试 | 当前验证 596 项通过 + 11 个 subtests |
| **Vitest** | 前端测试 | 当前验证 172 项通过（14 文件） |
| **数字孪生仿真** | C 代码运行时验证 | 5 类故障注入 |
| **契约校验器** | 契约前后置条件验证 | 语义分析 (pre/post/inv/fh) |

---

## 4. 开发标准

### 4.1 编码规范

| 语言 | 标准 | 工具执行 |
|------|------|---------|
| **Python** | PEP 8 + Ruff 规则 | Ruff |
| **TypeScript** | Biome 推荐规则 | Biome |
| **C (生成代码)** | MISRA-C:2012 | Cppcheck |

### 4.2 架构原则

1. **高内聚、低耦合**: Agent 间通过 Pipeline 编排器解耦
2. **契约式设计**: 接口由 .contract YAML 严格定义
3. **防御性编程**: 所有输入经 Pydantic 校验
4. **确定性优先**: 关键检查用规则引擎 (Cppcheck) 而非 LLM
5. **隔离容错**: 数字孪生 GCC 沙盒隔离执行

### 4.3 命名约定

| 元素 | 约定 | 示例 |
|------|------|------|
| Python 模块 | snake_case | `requirement_parser_agent.py` |
| Python 类 | PascalCase | `ContractChecker` |
| TypeScript 组件 | PascalCase | `CodeViewer.vue` |
| C 函数 | snake_case | `altitude_filter()` |
| 需求 ID | REQ-NNN | `REQ-001` |
| 契约 ID | CON-NNN | `CON-001` |
| 测试 ID | TST-NNN | `TST-001` |
| 问题 ID | PR-YYYY-NNNN | `PR-2026-0001` |

---

## 5. 交付物清单

### 5.1 代码交付物

| 交付物 | 格式 | 说明 |
|--------|------|------|
| 后端源代码 | Python | `src/skyforge_engine/` + `src/skyforge_llm/` + `src/skyforge_core/` + `studio/app/` 全部模块 |
| 前端源代码 | Vue 3 / TypeScript | `studio/frontend/src/` 全部组件 |
| 生成 C 代码样例 | C | `examples/` 目录 |
| Docker 配置 | YAML | `docker-compose.yml` |

### 5.2 文档交付物

| 交付物 | 格式 | 说明 |
|--------|------|------|
| 用户教程 | Markdown | `docs/user/使用教程.md` |
| 部署说明 | Markdown | `docs/user/部署说明.md` |
| 测试报告 | Markdown | `docs/user/测试报告.md` |
| DO-178C 计划文档 | Markdown | `docs/compliance/*.md` |
| 第三方组件说明 | Markdown | `ThirdParty.md` |
| 许可证 | Text | `LICENSE` |

### 5.3 数据交付物

| 交付物 | 格式 | 说明 |
|--------|------|------|
| MISRA-C 规则库 | TXT | `src/skyforge_engine/rag/data/misra_rules.txt` |
| DO-178C 合规报告 | HTML | 生成工具自动产出 |
| 追溯矩阵 | HTML/JSON | 生成工具自动产出 |
| 仿真波形数据 | JSON | 数字孪生引擎产出 |

---

## 6. 进度计划

### 6.1 迭代计划

| 迭代 | 时间 | 核心交付 | 验收标准 |
|------|------|---------|---------|
| V3.0 | 2026-07-07 | 全流程 MVP (6 Agent + 数字孪生 + 报告) | 需求→代码→报告全流程可运行 |
| V3.1 | 2026-07-10 | 查改解耦 + 契约→断言 + RAG 增强 + HIL | 契约校验通过，HITL 审查可用 |
| V3.2 | 2026-07-16 | SkyForge 重命名 + DO-178C 文档 + DAL 自适应 | 8份计划文档发布，DAL自适应可用 |
| V3.3 | 2026-07-17 | MC/DC + 正式 PR 系统 + 工具鉴定 + 合规矩阵 | 覆盖率分析器可用，PR系统正式化，工具鉴定草案完成 |
| V0.5.0 | 2026-07-21 | 数据耦合/控制耦合分析 + 独立文档拆分 | 耦合分析器可用，8份独立文档完整 |

### 6.2 里程碑

| 里程碑 | 日期 | 验收标准 | 责任人 | 状态 |
|--------|------|---------|--------|------|
| M1: 核心链路 | 2026-07-07 | 需求→代码→合规报告全流程 | 开发团队 | ✅ 完成 |
| M2: 合规增强 | 2026-07-10 | MISRA 自动修复 + 契约断言 + HIL | 开发团队 | ✅ 完成 |
| M3: DO-178C 文档 | 2026-07-16 | 8 份计划文档 + DAL 自适应 | 项目负责人 | ✅ 完成 |
| M4: V3.3-Enhanced | 2026-07-17 | 覆盖率分析器 + PR 系统 + 工具鉴定草案 + 合规矩阵 | 项目负责人 | ✅ 完成 |
| M5: 比赛交付 | 2026-07-20 | 全量开源 + 演示视频 + PPT | 全体成员 | ⏳ 待开始 |
| M6: V0.5.0 P0 | 2026-07-21 | 耦合分析 + 独立文档 | 开发团队 | ⏳ 进行中 |

---

## 附录 A: 开发命令速查

```bash
# 启动开发环境
make dev

# 代码检查
make lint

# 运行测试
make test

# 类型检查
make typecheck

# DO-178C 合规检查
make do178c-check

# 构建
make build
```
