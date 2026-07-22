# SkyForge 用户指南

## 快速开始

> **版本**：v0.5.0 &nbsp;&nbsp; **更新日期**：2026-07-21

---

### 一、快速入门

#### 1.1 版本信息

| 项目 | 值 |
|------|-----|
| 版本 | v0.5.0 |
| 更新日期 | 2026-07-21 |
| 基准测试通过率 | 12/12 (100%) |
| 后端/引擎/LLM安全测试 | 596 pytest passed，11 subtests passed |
| 前端测试 | 172 Vitest passed，4 E2E passed |
| MISRA自动修复规则 | 57条 |
| DO-178C合规文档 | 9份 |
| 故障注入类型 | 5类 |

#### 1.2 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.12+ | 后端运行时 |
| Node.js | 18+ | 前端运行时 |
| pnpm | 10+ | 前端包管理器 |
| uv | 最新 | 后端包管理器 |
| Redis | 6+ | 可选，任务队列 |
| LM Studio / Ollama | 最新 | 可选，本地LLM推理 |

#### 1.3 一键启动

```bash
## 克隆项目
git clone https://atomgit.com/gcw_TTqe9ALQ/SkyForge.git
cd SkyForge

## 一键启动（推荐）
## Linux / Mac / Windows Git Bash
sh start.sh
```

手动启动：
```bash
## 后端
uv sync
make dev

## 前端
cd studio/frontend
pnpm install
pnpm dev
```

Docker部署：
```bash
docker compose up --build
```

启动后访问：
- 前端界面：http://localhost:5173
- 后端API：http://localhost:8000
- API文档：http://localhost:8000/docs

#### 1.4 前端页面总览（11个页面）

| 路径 | 页面名称 | 说明 |
|------|----------|------|
| `/` | 比赛演示首页 | 三栏布局：任务输入 / 可信流水线 / 实时结论 |
| `/architecture` | 六层架构展示 | SkyForge 六层架构可视化 |
| `/generate` | 代码生成 | 自然语言→需求→契约→代码→修复→仿真→报告 |
| `/records` | 运行记录 | 实时任务与已验证回放列表 |
| `/records/:taskId` | 回放模式 | 单个任务的详细回放 |
| `/lab` | 能力实验室 | 组件组合 / MISRA搜索 / HITL审查 入口 |
| `/settings` | 系统设置 | 执行 Profile 选择与 LLM 配置 |
| `/demo` | 比赛工作台 | 比赛专用工作台 |
| `/compose` | 组件组合验证 | 多组件接口兼容性验证 |
| `/misra` | MISRA规则搜索 | MISRA-C 编码规范查询 |
| `/hitl` | HITL人工审查 | 人工审查工作台 |

#### 1.5 顶部导航栏（6个）

导航顺序：**比赛演示** → **六层架构** → **代码生成** → **运行记录** → **能力实验室** → **系统设置**

---

### 二、执行模式（三种 Profile）

SkyForge 支持三种执行模式，可在「系统设置」页面切换。

#### 2.1 demo：浏览器模拟（simulated）

| 属性 | 值 |
|------|-----|
| 模式 | simulated（完全离线） |
| 适用场景 | 功能演示、开箱即用、无网络环境 |
| LLM | 无需配置，内置 Mock 数据 |
| 特点 | 零配置启动，主演示用途 |

**说明**：完全在浏览器中模拟运行，无需后端 LLM 推理。所有步骤均使用预设的 Mock 数据，适用于快速体验和功能演示。

#### 2.2 cloud：云模型（live）

| 属性 | 值 |
|------|-----|
| 模式 | live（服务端实时执行） |
| 适用场景 | 生产环境、真实 LLM 推理 |
| LLM | 云端大模型服务 |
| 特点 | 真实推理，效果最佳 |

**说明**：后端连接云 LLM 服务，实时执行完整流水线。需要配置有效的 LLM API 地址和密钥。

#### 2.3 local：本地模型（live/replay）

| 属性 | 值 |
|------|-----|
| 模式 | live / replay |
| 适用场景 | 数据安全要求高、本地部署 |
| LLM | Ollama / LM Studio 本地推理 |
| 特点 | 数据不出内网，支持已验证回放 |

**说明**：使用本地部署的 LLM（Ollama 或 LM Studio）进行实时推理，同时支持已验证任务的回放功能。数据完全在本地处理，满足安全合规要求。

---

### 三、功能模块详解

#### 3.1 比赛演示首页

**功能**：三栏流水线布局，自动演示从需求输入到结论输出的全流程。

**页面路径**：`/`

**三栏布局**：
1. **左栏 - 任务输入**：输入自然语言需求或选择预设任务
2. **中栏 - 可信流水线**：实时展示流水线各阶段执行状态与证据
3. **右栏 - 实时结论**：动态更新的合规结论与风险评估

**操作步骤**：
1. 进入首页默认展示比赛演示界面
2. 在左栏输入需求描述或选择预设示例
3. 点击「开始演示」观察全自动流水线
4. 中栏实时显示各阶段：需求解析 → 契约生成 → 代码生成 → 修复验证 → 仿真测试 → 报告生成
5. 右栏实时更新结论：MISRA 合规性、DO-178C 目标达成、风险等级

**证据规则**：
| 状态 | 说明 |
|------|------|
| `observed` | 已观察到，真实执行证据 |
| `simulated` | 模拟数据，demo 模式下显示 |
| `unavailable` | 证据暂不可用 |
| `failed` | 验证失败 |

#### 3.2 六层架构展示

**功能**：可视化展示 SkyForge 的六层架构设计。

**页面路径**：`/architecture`

**六层架构**：
1. **用户界面层**：Web UI、API 网关
2. **任务编排层**：Pipeline 编排、任务调度
3. **Agent 层**：需求解析、契约生成、代码生成、修复 Agent
4. **验证层**：MISRA 扫描、形式化验证、仿真测试
5. **工具链层**：z3、cbmc、cppcheck、gcc
6. **基础设施层**：LLM、存储、缓存

#### 3.3 代码生成全流程

**功能**：从自然语言需求自动生成符合DO-178C/MISRA-C标准的机载C代码

**操作步骤**：
1. 进入「代码生成」页面
2. 输入自然语言需求描述，例如：
   ```
   实现一个飞行器高度传感器滤波模块，输入为原始高度数据，
   输出为经过卡尔曼滤波的平滑高度值，需符合MISRA-C标准
   ```
3. （可选）配置 HITL 人工审查：
   - 点击「开始生成」按钮左侧的 **HITL 开关**（UserCheck 图标）启用人工审批
   - 启用后 Pipeline 在需求/契约/代码评审检查点会暂停等待审批
   - **默认关闭**（灰色），启用后变为琥珀色
   - Mock 模式下 HITL 开关隐藏

> **术语说明**：HITL = Human-in-the-Loop 人工审查；HIL = Hardware-in-the-Loop 硬件在环。本文档中人工审查统一使用 HITL。
4. 点击「开始生成」
5. 观察Agent实时执行过程：
   - REQ-Parser：需求解析
   - CON-Gen：契约生成
   - CODE-Gen：代码生成
   - REPAIR：MISRA违规修复
6. 查看生成的代码、契约、合规报告

**输出产物**：
- 结构化需求JSON
- DO-178C合规契约YAML
- MISRA-C风格C代码（含追溯注释）
- Cppcheck扫描结果与修复记录

#### 3.4 SCADE模型导入

**功能**：导入SCADE G-Lustre文件，自动转换为需求与契约

**操作步骤**：
1. 准备 `.lus` 格式的G-Lustre文件
2. 在代码生成页面点击「上传SCADE」
3. 系统自动解析并转换
4. 可选：与手写需求合并

**示例文件**：参考 `studio/app/tests/data/example.lus`

#### 3.5 组件组合验证

**功能**：验证多个机载软件组件的接口兼容性与组合正确性

**操作步骤**：
1. 进入「组件组合」页面
2. 上传或选择已有组件
3. 点击「验证兼容性」
4. 查看验证结果与冲突报告

#### 3.6 数字孪生仿真

**功能**：在虚拟环境中测试生成的代码，支持故障注入

**操作步骤**：
1. 代码生成完成后，进入「仿真」标签页
2. 选择故障类型（可选，共5类）：
   - 传感器漂移
   - 信号噪声
   - 数据丢包
   - 硬件故障
   - 时序异常
3. 点击「运行仿真」
4. 查看波形图与仿真结果

**输出**：
- 传感器输入/输出波形
- MCU处理状态
- 故障注入效果
- 仿真通过/失败判定

#### 3.7 HITL 人工审查

**功能**：在关键决策点引入人工审查，确保代码质量

**默认状态**：**禁用**（`HITL_ENABLED=false`），避免阻塞自动化 Pipeline。可随时启用，无需重启后端。

**启用方式**（二选一）：
- **UI 方式**：Generate 页面「开始生成」按钮左侧的 HITL 开关（UserCheck 图标），点击切换
  - 灰色 = 关闭，琥珀色 = 开启
  - Mock 模式下隐藏
- **API 方式**：`POST /api/hitl/toggle`，请求体 `{"enabled": true/false}`

**流程**：
```
需求解析 → [人工审批] → 契约生成 → [人工审批] → 代码生成 → [人工审批]
```

**审批超时**：每个检查点 5 分钟（300 秒），超时自动批准。

**操作**：
1. 系统在检查点暂停并通知
2. 审批人员查看内容并给出意见
3. 通过/拒绝决定流程继续或终止

#### 3.8 运行记录与回放

**功能**：查看历史任务列表，支持任务回放与详细结果追溯。

**页面路径**：`/records`（列表）、`/records/:taskId`（详情回放）

**列表页面功能**：
1. **实时任务**：正在执行的任务，实时显示进度
2. **已验证回放**：已完成并通过验证的任务，支持一键回放

**操作步骤**：
1. 进入「运行记录」页面
2. 查看任务列表：按时间倒序排列，显示任务ID、状态、创建时间
3. 点击任意任务进入详情页
4. 在详情页中查看完整执行过程，支持：
   - 逐步回放流水线各阶段
   - 查看每步的输入输出与证据
   - 对比预期与实际结果
   - 下载完整产物包

**回放模式说明**：
- 本地模式（local Profile）下支持已验证回放
- 回放数据包含完整的执行轨迹与证据链
- 可用于审计、培训与问题排查

#### 3.9 能力实验室

**功能**：集成多个专项能力工具的实验平台。

**页面路径**：`/lab`

**三个子模块**：
1. **组件组合验证**（`/compose`）：验证多组件接口兼容性
2. **MISRA规则搜索**（`/misra`）：MISRA-C 编码规范查询
3. **HITL人工审查**（`/hitl`）：人工审查工作台

**操作步骤**：
1. 进入「能力实验室」页面
2. 选择需要使用的子模块
3. 在对应页面完成专项操作

#### 3.10 系统设置

**功能**：配置执行模式与 LLM 参数。

**页面路径**：`/settings`

**执行 Profile 选择**：
| Profile | 模式 | 说明 |
|---------|------|------|
| demo | simulated | 浏览器模拟，完全离线，开箱即用 |
| cloud | live | 云模型，服务端实时执行，真实LLM |
| local | live/replay | 本地模型，Ollama/LM Studio，支持回放 |

**LLM 配置项**：
- API 基础地址
- 模型名称
- API Key
- 最大 token 数

**操作步骤**：
1. 进入「系统设置」页面
2. 选择执行 Profile
3. （可选）配置 LLM 参数
4. 点击「保存设置」

#### 3.11 DO-178C报告生成

**功能**：自动生成适航合规报告

**操作步骤**：
1. 代码生成完成后，点击「生成报告」
2. 系统自动生成HTML格式报告
3. 报告包含：
   - DO-178C目标达成情况
   - 需求-代码追溯矩阵
   - MISRA-C合规统计
4. 点击「下载报告」保存

#### 3.12 端到端完整流程示例

本节通过一个完整 walkthrough，演示从自然语言需求到 DO-178C 合规报告的端到端流程。示例使用项目内置的 `examples/filter_requirements.txt`（一阶低通滤波器需求）作为输入。

##### 步骤 1：启动系统

在项目根目录执行一键启动脚本：

```bash
bash start.sh
```

启动过程中关注后端日志，直到看到 LLM 预热完成的提示：

```
[Pipeline] 使用真实 LLM，已加载模型: ['qwen2.5-coder-7b-instruct']（将使用真实 LLM 推理）
INFO:     Uvicorn running on http://0.0.0.0:8000
```

若本地 LLM 未启动或 `SKYFORGE_LLM_MODE=mock`，系统会按当前 profile 显示 Mock/不可用状态；演示模式仍可完成 simulated 全流程。

##### 步骤 2：访问主界面

浏览器打开 http://localhost:5173 进入主界面，默认进入「代码生成」页面。页面顶部状态栏会显示当前执行来源（演示模式、云 API 或本地模型）以及后端健康状态。

##### 步骤 3：在「代码生成」页面输入需求

将 `examples/filter_requirements.txt` 的内容粘贴到「需求描述」文本框：

```
低通滤波器需求文档

需求编号: REQ-FILTER-001
需求描述: 实现一个一阶低通滤波器，对传感器采集的原始数据进行平滑处理
输入: double raw_input - 传感器原始采样值
输出: double filtered_output - 滤波后的输出值
滤波系数: alpha = 0.1 (截止频率约 1.6kHz @ 16kHz 采样率)
初始化: 首次调用时输出等于输入
约束: 符合 MISRA-C:2012 编码规范，适用于 DO-178C DAL-A 级别机载软件
```

点击「一键全流程（生成→修复→校验→仿真）」按钮。

##### 步骤 4：观察 4 个 Agent 协同过程

页面下方「Agent 思考流」面板实时展示 4 个 Agent 的推理过程（通过 WebSocket 流式推送）：

**① REQ-Parser（需求解析 Agent）**

将自然语言解析为结构化需求 JSON，关键输出：

```json
{
  "req_id": "REQ-001",
  "desc": "实现一个一阶低通滤波器...",
  "type": "filter",
  "module_name": "lowpass_filter",
  "safety_level": "DAL-A",
  "params": {"cutoff_hz": 1.6, "sample_rate_hz": 16.0, "alpha": 0.1},
  "constraints": ["WCET <= 1ms", "禁止动态内存（MISRA Rule-21.3）"]
}
```

字段含义：`req_id` 为流水线内自增的唯一追溯编号；`type` 取值为 `filter`/`control`/`comms` 三者之一；`safety_level` 依据 DO-178C 危害等级推断（A=catrophic ~ E=no-effect）。

**② CON-Gen（契约生成 Agent）**

依据需求 JSON 生成 DO-178C 契约 YAML，关键字段：

```yaml
component: lowpass_filter
version: 1.0.0
safety_level: DAL-A
traceability: [REQ-001]
interface:
  inputs:
    - name: raw_input
      type: double
      range: [-1000.0, 1000.0]
  outputs:
    - name: filtered_output
      type: double
      range: [-1000.0, 1000.0]
contracts:
  preconditions:
    - "raw_input != NULL"
  postconditions:
    - "filtered_output >= -1000.0 && filtered_output <= 1000.0"
  invariants:
    - "sample_rate == 16Hz"
  fault_handling:
    - "if raw_input == 0: set fault_detected = true"
```

字段含义：`inputs`/`outputs` 定义接口信号与量程；`preconditions` 为调用前必须成立的断言；`postconditions` 为调用后必须成立的断言；`invariants` 为模块运行期间恒成立的不变式；`fault_handling` 为按 DAL 等级生成的故障处理分支。

**③ CODE-Gen（代码生成 Agent）**

生成 MISRA-C 风格 C 代码，每处函数/变量强制标注追溯注释：

```c
/* [REQ-001] [MISRA-Rule-8.13] 机载信号滤波器实现
 * Traceability: REQ-001
 * 模块: lowpass_filter
 * 截止频率: 1.6Hz, 采样率: 16Hz
 */
#include "lowpass_filter.h"

/* [REQ-001] [MISRA-Rule-8.9] 模块内部状态，静态持久化 */
static double s_prev_output = 0.0;
static int    s_initialized = 0;

/* [REQ-001] [MISRA-Rule-15.7] 一阶 IIR 低通滤波 */
double lowpass_filter_apply(double raw_input)
{
    double filtered_output;
    /* [REQ-001] [MISRA-Rule-10.1] 未初始化保护 */
    if (0 == s_initialized) {
        lowpass_filter_init();
    }
    /* [REQ-001] [MISRA-Rule-10.4] 浮点运算显式类型 */
    filtered_output = 0.100000 * raw_input + (1.0 - 0.100000) * s_prev_output;
    s_prev_output = filtered_output;
    return filtered_output;
}
```

`[REQ-001]` 实现需求到代码的正向追溯；`[MISRA-Rule-8.13]` 等标注适用的 MISRA-C:2012 规则编号，便于审查。

**④ REPAIR（修复 Agent）**

扫描 MISRA 违规并修复（最多 3 轮闭环）：
1. 调 `cppcheck_scanner.scan(code)` 检出违规列表
2. 若无违规 → 跳出循环
3. 调 `code_repairer_agent.repair(code, violations)` 修复
4. 调 `contract_checker.check(修复代码, contract)` 验证契约仍满足
5. 回到步骤 1（最多 3 轮）

每轮迭代在「修复历史」Tab 中以时间线形式展示违规数变化与修复动作。

##### 步骤 5：进入「仿真」页面，运行数字孪生仿真

切换到「数字孪生」Tab，系统已默认运行一次无故障仿真（200 步）。仿真结果展示：
- 传感器输入波形（raw_input 时序曲线）
- 滤波输出波形（filtered_output 时序曲线）
- MCU 处理状态（虚拟微控制器执行日志）
- 契约断言实时校验结果（preconditions/postconditions/invariants 通过数）

##### 步骤 6：注入故障，对比波形

在「故障注入」面板选择故障类型 `sensor_drift`（传感器漂移），参数设置 `drift_percent: 10`（10% 漂移），点击「注入故障」。

系统调用 `simulate` 接口重新仿真，波形图叠加显示正常 vs 故障曲线：
- 正常曲线（蓝色）：滤波器平滑跟随输入
- 故障曲线（红色）：传感器漂移 10% 后，输出偏离正常值
- 故障标注线：在故障注入时刻打垂直标记

若故障导致 postconditions 违反（如输出超量程），仿真结果判定为 `passed=false`。

##### 步骤 7：点击「生成报告」，查看 DO-178C 合规报告

切换到「DO-178C 报告」Tab，点击「下载报告」生成 HTML 格式报告。报告内嵌 CSS，支持浏览器打印为 PDF，包含以下章节：
1. **项目概览**：组件名、DAL 等级、生成时间
2. **需求-代码追溯矩阵**：`[REQ-xxx]` ↔ 代码行号 ↔ `[CON-xxx]` 三向追溯
3. **MISRA-C 合规摘要**：Cppcheck 扫描结果 + 修复历史 + 最终违规数
4. **测试覆盖**：仿真通过/失败 + 契约断言覆盖率
5. **DO-178C 目标符合性表**：Level C 关键目标（Table A-2 ~ A-9）逐项评估

##### 步骤 8：在「组件组合」页面验证组件兼容性

进入「组件组合」页面，验证低通滤波器与高通滤波器组合的接口兼容性：
1. 左栏组件 A：保留默认 `LowPassFilter`（预设低通滤波器）
2. 右栏组件 B：保留默认 `HighPassFilter`（预设高通滤波器）
3. 中间连接方式选择「顺序组合」（A → B，A 的输出作为 B 的输入）
4. 点击「验证兼容性」，查看兼容性检查报告（信号量程匹配、类型匹配、采样率一致等）
5. 点击「组合仿真」运行组合后代码的数字孪生仿真

#### 3.13 各产物说明

本节详细说明流水线各产物的结构、字段含义与解读方式。

##### 3.13.1 需求 JSON

由 REQ-Parser 生成，是后续所有 Agent 的输入源头。

| 字段 | 类型 | 说明 |
|------|------|------|
| `req_id` | string | 需求唯一编号，流水线内自增（如 `REQ-001`），用于追溯 |
| `desc` | string | 原始自然语言需求文本（去首尾空白） |
| `type` | string | 需求类型，取值 `filter` / `control` / `comms` |
| `module_name` | string | 推导的模块名（如 `lowpass_filter`），用于 C 代码命名 |
| `safety_level` | string | DO-178C DAL 等级（`DAL-A` ~ `DAL-E`），依据危害等级表推断 |
| `params` | object | 参数字典（如 `cutoff_hz` / `sample_rate_hz` / `alpha`），由正则与 LLM 联合提取 |
| `constraints` | string[] | 非功能约束列表（如 `WCET <= 1ms`、`禁止动态内存`） |

示例解读：`safety_level=DAL-A` 表示该模块失效会导致灾难性后果，需最严格的适航审查；`constraints` 中的 `禁止动态内存（MISRA Rule-21.3）` 直接对应 MISRA-C:2012 Rule 21.3。

##### 3.13.2 契约 YAML

由 CON-Gen 生成，定义组件接口与可验证断言。

| 字段 | 类型 | 说明 |
|------|------|------|
| `component` | string | 组件名（与 `module_name` 一致） |
| `version` | string | 契约版本号（语义化版本，如 `1.0.0`） |
| `safety_level` | string | DAL 等级（同需求 JSON） |
| `traceability` | string[] | 关联的需求编号列表（如 `[REQ-001]`） |
| `interface.inputs` | array | 输入信号列表，每项含 `name`/`type`/`range` |
| `interface.outputs` | array | 输出信号列表，每项含 `name`/`type`/`range` |
| `contracts.preconditions` | string[] | 前置条件断言（调用前必须成立，如 `raw_input != NULL`） |
| `contracts.postconditions` | string[] | 后置条件断言（调用后必须成立，如 `filtered_output >= -1000.0`） |
| `contracts.invariants` | string[] | 不变式（运行期间恒成立，如 `sample_rate == 16Hz`） |
| `contracts.fault_handling` | string[] | 故障处理分支（按 DAL 等级生成，机载软件必填） |

示例解读：`preconditions` 在契约校验阶段被转换为 C 断言代码（`assert(raw_input != NULL);`），在数字孪生仿真中实时校验；`fault_handling` 段不可省略，机载软件契约必须含故障处理。

##### 3.13.3 生成的 C 代码

由 CODE-Gen 生成，符合 MISRA-C:2012 风格。

**函数签名规范**：
- 模块初始化：`void <module>_init(void)`
- 模块处理：`double <module>_apply(double raw_input)`（滤波类）/ `double <module>_compute(double setpoint, double feedback)`（控制类）

**追溯注释格式**（必填，缺失会被 CODE-Gen 自动补全）：

| Tag 格式 | 含义 | 示例 |
|----------|------|------|
| `[REQ-xxx]` | 关联的需求编号 | `[REQ-001]` |
| `[CON-xxx]` | 关联的契约条件编号 | `[CON-LP-PRE-000]` |
| `[MISRA-Rule x.x]` | 适用的 MISRA-C:2012 规则 | `[MISRA-Rule-8.13]` |
| `[TST-xxx]` | 关联的测试用例编号 | `[TST-FILTER-001]` |

**MISRA 合规要点**（代码生成时强制遵守）：
- Rule 8.9：模块内部状态变量声明为 `static`，限制作用域
- Rule 8.13：接口仅暴露必要符号，只读指针标注 `const`
- Rule 10.1：未初始化保护（首次调用前自动 init）
- Rule 10.4：浮点运算显式类型（避免隐式转换）
- Rule 15.7：所有 `if`/`else` 必须用花括号包裹
- Rule 17.7：函数返回值必须检查
- Rule 21.3：禁止动态内存（`malloc`/`free`）

##### 3.13.4 合规报告 HTML

由 DO-178C 报告生成器生成，内嵌 CSS，支持浏览器打印为 PDF。

**报告章节**：
1. **项目概览**：组件名、DAL 等级、生成时间戳、流水线版本
2. **需求-代码追溯矩阵**：`[REQ-xxx]` → 代码行号 → `[CON-xxx]` 三向追溯表，每行可点击跳转
3. **MISRA-C 合规统计**：
   - Cppcheck 扫描违规总数（按 severity：error/warn）
   - 修复历史轮次与每轮违规数变化
   - 最终违规数（修复闭环后）
4. **测试覆盖**：
   - 数字孪生仿真通过/失败状态
   - 契约断言覆盖率（preconditions/postconditions/invariants 通过数 / 总数）
   - 故障注入测试结果
5. **DO-178C 目标符合性表**：依据 Level C 关键目标（Table A-2 ~ A-9）自动评估，逐项标注 satisfied / not-satisfied / not-applicable

**Tag Badge 颜色规范**（报告内追溯标签着色）：
- `[REQ-xxx]`：蓝色（需求）
- `[CON-xxx]`：绿色（契约）
- `[TST-xxx]`：紫色（测试）
- `[MISRA-Rule-x.x]`：橙色（MISRA 规则）

##### 3.13.5 仿真波形

由数字孪生仿真引擎生成，通过 ECharts 在前端渲染。

**波形组成**：
- **传感器输入曲线**：raw_input 时序数据（横轴为仿真步数，纵轴为信号值）
- **输出曲线**：filtered_output 时序数据，与输入曲线叠加对比
- **MCU 处理状态**：虚拟微控制器执行日志（每步的指令计数、内存占用、WCET）
- **故障注入效果标注**：在故障注入时刻打垂直标记线，故障曲线以红色高亮

**解读方式**：
- 正常仿真：输出曲线应平滑跟随输入，无超量程
- 故障仿真：对比正常曲线，观察故障对输出的影响程度
- 契约断言：波形下方实时显示 preconditions/postconditions/invariants 通过数，任一违反则仿真判定失败

---

### 四、LLM配置（可选）

#### 4.1 使用本地LM Studio / Ollama

1. 安装 [LM Studio](https://lmstudio.ai/)
2. 下载模型（推荐：Qwen2.5-Coder-7B或更高）
3. 启动本地服务器（默认端口1234）
4. 配置环境变量：
   ```env
   USE_LLM=true
   LMSTUDIO_BASE_URL=http://localhost:1234/v1
   ```
5. 重启SkyForge

#### 4.2 使用Mock模式

如不配置LLM，系统将使用内置Mock模式：
- 自动生成符合格式的代码模板
- 适用于功能演示与测试
- 无需额外配置

#### 4.3 高级配置

所有环境变量在 `src/skyforge_engine/config.py` 中定义，基于 `pydantic-settings` 从环境变量和 `.env` 文件加载。可在项目根目录创建 `.env` 文件或在 `config/` 目录创建 `.env.dev` / `.env.prod` 覆盖默认值。

##### 完整环境变量列表

```env
## ===== LLM 配置 =====
USE_LLM=true
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LLM_MODEL=qwen2.5-coder-7b
LLM_API_KEY=
LLM_MAX_TOKENS=8192

## ===== 性能优化 =====
LLM_CACHE_ENABLED=true
LLM_CACHE_TTL=3600

## ===== HITL 人工审查 =====
HIL_ENABLED=false
HIL_TIMEOUT=300

## ===== 真实工具链 =====
USE_REAL_CPPCHECK=false
USE_REAL_GCC=false

## ===== Redis（可选）=====
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=10

## ===== 系统配置 =====
ENV=dev
LOG_LEVEL=INFO
DEBUG=true
MAX_RETRIES=3
SERVER_HOST=http://localhost:8000
CORS_ALLOW_ORIGINS=*
```

##### 环境变量详解

**LLM 配置**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `USE_LLM` | `false` | 是否启用 LLM 推理（`true` 启用，`false` 使用 Mock） |
| `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` | LM Studio 本地服务地址 |
| `LLM_MODEL` | `None` | 模型名（如 `qwen2.5-coder-7b`），未设置时使用 LM Studio 默认模型 |
| `LLM_API_KEY` | `None` | API Key（本地 LM Studio 可留空） |
| `LLM_MAX_TOKENS` | `8192` | 单次生成最大 token 数 |

**性能优化**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_CACHE_ENABLED` | `true` | 是否启用 LLM 响应缓存（对相同 prompt + system_prompt 的非流式调用做缓存） |
| `LLM_CACHE_TTL` | `3600` | 缓存生存时间（秒），过期后自动失效 |

**HITL 人工审查**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HIL_ENABLED` | `false` | 是否启用 HITL（Human-in-the-Loop）人工审查模式 |
| `HIL_TIMEOUT` | `300` | 人工审查超时时间（秒），超时视为拒绝 |

> 注：环境变量名保留 `HIL_` 前缀为历史兼容，功能均指 HITL 人工审查。

**真实工具链**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `USE_REAL_CPPCHECK` | `false` | `true`：调用真实 `cppcheck --addon=misra --dump`；`false`：使用基于代码模式匹配的 Mock 扫描。真实模式不可用或失败时优雅降级到 Mock |
| `USE_REAL_GCC` | `false` | `true`：数字孪生使用真实 GCC 编译（需系统已安装 gcc）；`false`：使用虚拟 MCU 解释执行。失败时降级到 Mock |

**Redis 配置（可选）**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接地址（用于任务队列与缓存共享） |
| `REDIS_MAX_CONNECTIONS` | `10` | 连接池最大连接数 |

**系统配置**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ENV` | `dev` | 环境名称，决定加载 `.env.dev` / `.env.prod` 配置文件 |
| `LOG_LEVEL` | `INFO` | 日志级别（`DEBUG` / `INFO` / `WARNING` / `ERROR`） |
| `DEBUG` | `true` | 调试模式（开启详细日志） |
| `MAX_RETRIES` | `3` | LLM 调用最大重试次数 |
| `SERVER_HOST` | `http://localhost:8000` | 后端服务地址（用于报告生成中的绝对 URL） |
| `CORS_ALLOW_ORIGINS` | `*` | CORS 允许来源，支持 `*` / 逗号分隔 / JSON 数组格式 |

##### Agent 级别 LLM 配置（可选）

每个 Agent 支持独立配置不同的 LLM 提供商与模型，未设置时回退到全局 `LMSTUDIO_BASE_URL` / `LLM_MODEL`：

```env
## REQ-Parser Agent
REQ_PARSER_API_TYPE=openai-chat
REQ_PARSER_API_KEY=
REQ_PARSER_MODEL=
REQ_PARSER_BASE_URL=
REQ_PARSER_MAX_TOKENS=4096

## CON-Gen Agent
CON_GEN_API_TYPE=openai-chat
CON_GEN_API_KEY=
CON_GEN_MODEL=
CON_GEN_BASE_URL=
CON_GEN_MAX_TOKENS=4096

## CODE-Gen Agent
CODE_GEN_API_TYPE=openai-chat
CODE_GEN_API_KEY=
CODE_GEN_MODEL=
CODE_GEN_BASE_URL=
CODE_GEN_MAX_TOKENS=4096

## REPAIR Agent
REPAIR_API_TYPE=openai-chat
REPAIR_API_KEY=
REPAIR_MODEL=
REPAIR_BASE_URL=
REPAIR_MAX_TOKENS=4096
```

支持的 `API_TYPE` 取值：`openai-chat` / `openai-responses` / `anthropic`。

##### 配置文件优先级

`setting.py` 在启动时按以下顺序加载配置（后者覆盖前者）：
1. `.env`（基础配置）
2. `.env.<ENV>`（环境特定配置，如 `.env.dev` / `.env.prod`）
3. 进程环境变量（最高优先级）

---

### 五、MISRA-C规则查询

**功能**：搜索和查看MISRA-C编码规范

**操作步骤**：
1. 进入「能力实验室」→「MISRA规则搜索」页面（`/misra`）
2. 输入规则编号或关键词搜索
3. 查看规则详情与示例

**MISRA自动修复规则**：系统支持 **57条** MISRA 规则的自动修复。

**支持的查询方式**：
- 按规则编号：`Rule 8.13`
- 按关键词：`指针` `数组` `类型转换`
- 按分类：`必要规则` ` required` ` advisory`

---

### 六、常见问题

#### Q1: 启动时报端口占用
```bash
## 查找占用端口的进程
lsof -i :5173
lsof -i :8000

## 杀死进程
kill -9 <PID>
```

#### Q2: LLM连接失败
- 检查LM Studio是否启动
- 确认端口1234是否可访问
- 系统会自动降级为Mock模式

#### Q3: 代码生成报错
- 检查网络连接
- 查看后端日志：`logs/`
- 尝试使用Mock模式

#### Q4: 仿真运行失败
- 检查生成的代码是否完整
- 确认契约格式正确
- 查看仿真引擎日志

#### Q5: 如何启用 HITL 人工审查模式？

设置环境变量 `HITL_ENABLED=true` 后重启服务：

```env
## .env 或 .env.dev
HITL_ENABLED=true
HITL_TIMEOUT=300
```

启用后，流水线在三个检查点暂停等待人工审查：
1. `requirement_review`：需求评审（与契约生成并行执行，HITL 拒绝时丢弃契约结果）
2. `contract_review`：契约评审
3. `code_review`：代码评审

审批通过流程继续；拒绝则流水线终止并返回 `aborted=true`。前端「代码生成」页面右侧会显示 `HITLPanel` 审批面板。也可进入「能力实验室」→「HITL人工审查」页面（`/hitl`）进行集中审批。

#### Q6: 如何切换真实 Cppcheck？

默认使用基于代码模式匹配的 Mock 扫描（无需安装 cppcheck）。切换到真实 Cppcheck：

```env
USE_REAL_CPPCHECK=true
```

前置条件：系统已安装 `cppcheck`（推荐 2.x 版本），可通过 `cppcheck --version` 验证。系统会调用 `cppcheck --addon=misra --dump` 执行扫描；若 cppcheck 不可用或调用失败，会优雅降级到 Mock 模式（不影响主流程）。

#### Q7: 如何启用真实 GCC 编译？

数字孪生仿真默认使用虚拟 MCU 解释执行 C 代码。启用真实 GCC 编译：

```env
USE_REAL_GCC=true
```

前置条件：系统已安装 `gcc`，可通过 `gcc --version` 验证。启用后虚拟 MCU 会真实编译生成的 C 代码并执行；编译失败时降级到 Mock 解释执行。

#### Q8: LLM 缓存如何配置？

LLM 响应缓存对相同 `prompt + system_prompt` 的非流式调用做缓存，避免重复推理：

```env
LLM_CACHE_ENABLED=true   # 启用缓存（默认 true）
LLM_CACHE_TTL=3600       # 缓存生存时间，单位秒（默认 3600 = 1 小时）
```

适用场景：开发调试时反复运行相同需求可显著加速；生产环境若需每次生成不同结果可设置 `LLM_CACHE_ENABLED=false` 关闭。

#### Q9: 模型预热失败怎么办？

若日志显示本地 LLM 不可用或当前模式为 mock，按以下步骤排查：

1. **检查 LM Studio 进程**：确认 LM Studio 应用已启动并运行
2. **检查模型加载**：在 LM Studio 中确认目标模型（如 `qwen2.5-coder-7b-instruct`）已下载并加载到内存
3. **检查端口可达性**：浏览器访问 http://localhost:1234/v1/models 应返回 JSON 模型列表
4. **检查环境变量**：确认 `SKYFORGE_LLM_MODE=local` 且 `LOCAL_LLM_BASE_URL` / `LMSTUDIO_BASE_URL` 与本地服务配置一致
5. **降级运行**：若无法立即修复，切换到 `demo` profile 或设置 `SKYFORGE_LLM_MODE=mock`，系统仍可完成 simulated 演示全流程

#### Q10: 并行化是否影响结果？

不影响。流水线中的并行化（`asyncio.gather`）仅用于 HITL 启用时的「需求评审等待」与「契约生成」并行执行：
- 契约生成只依赖 `req_json`，不依赖 HITL 审查结果
- HITL 拒绝时丢弃并行生成的契约结果并中止流水线
- HITL 通过时使用并行生成的契约，与串行执行结果完全一致

HITL 禁用时（`HITL_ENABLED=false`）HITL 立即返回 `skipped`，并行无收益，保持原有串行行为。结果完全一致。

#### Q11: 组件契约模板库如何使用？

在「组件组合」页面（`Compose.vue`）使用契约模板库快速创建组件：

1. 进入「组件组合」页面
2. 在组件 A 或组件 B 槽位点击「从模板创建」按钮
3. 在弹出的模板选择器中选择预置模板，模板按分类组织：
   - `filter`：滤波器（低通 / 高通 / 带通）
   - `controller`：控制器（PID / 限幅）
   - `sampler`：采样器
   - `limiter`：限幅器
4. 选中后模板的契约 YAML 与 C 代码自动填充到对应槽位
5. 可在编辑器中进一步修改后点击「验证兼容性」

模板统一采用带 `interface` 块的 YAML 布局（含 `range` 数值范围），便于兼容性检查器提取；C 代码统一保留 `double filter(double input)` 入口，可直接拖入组合验证区域。

#### Q12: SCADE 导入支持哪些版本？

SkyForge 支持 SCADE Suite 导出的 **G-Lustre 格式**（`.lus` 文件），通过 `src/skyforge_engine/scade/lustre_parser.py` 解析。兼容性说明：
- 格式：标准 Lustre 语法子集（node 定义 / let ... tel 块 / equations）
- 字段：支持 `inputs` / `outputs` / `locals` 声明与 equation 表达式
- 转换：自动将 G-Lustre 转换为需求 JSON 与契约 YAML，可与手写需求合并

参考示例文件：`studio/app/tests/data/example.lus`（基础 G-Lustre 示例）。在「代码生成」页面点击「SCADE 模型上传」折叠面板上传 `.lus` 文件即可。

---

### 七、技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    SkyForge 架构图                       │
├─────────────────────────────────────────────────────────┤
│  前端 (Vue 3 + TypeScript)                              │
│  ├── 代码编辑器 (Monaco)                                │
│  ├── Agent终端 (实时日志)                               │
│  ├── 波形图表 (ECharts)                                 │
│  └── 组件组合界面                                       │
├─────────────────────────────────────────────────────────┤
│  后端 (Python + FastAPI)                                │
│  ├── API路由层                                          │
│  ├── Agent编排器 (pipeline.py)                          │
│  ├── 4个Agent: 需求→契约→代码→修复                       │
│  ├── 数字孪生仿真引擎                                   │
│  ├── DO-178C报告生成器                                  │
│  └── HITL 人工审查管理器                                  │
├─────────────────────────────────────────────────────────┤
│  LLM层 (可选)                                          │
│  ├── LM Studio (本地)                                  │
│  ├── OpenAI API                                        │
│  └── Anthropic Claude                                  │
└─────────────────────────────────────────────────────────┘
```

---

### 八、API接口速查

详见「部署说明」章节中的 API 接口文档。

#### V1 唯一任务协议

**核心接口**：
- `POST /api/v1/tasks` - 创建任务（代码生成全流程）
- `WS /api/v1/tasks/{task_id}/events` - 任务事件流式推送

详细说明请参考部署说明文档。


## 部署说明

> **版本**：v0.5.0 &nbsp;&nbsp; **更新日期**：2026-07-21

---

### 一、部署方式概览

| 方式 | 适用场景 | 复杂度 | 命令 |
|------|----------|--------|------|
| 一键启动 | 快速体验、开发调试 | ⭐ 简单 | `sh start.sh` |
| 手动启动 | 开发调试、定制需求 | ⭐⭐ 中等 | `uv sync` + `make dev` |
| Docker Compose | 生产部署 | ⭐⭐⭐ 中等 | `docker compose up --build` |

---

### 二、本地开发部署

#### 2.1 一键启动（推荐）

```bash
## Linux / Mac / Windows Git Bash
sh start.sh
```

`start.sh` 脚本会自动完成：依赖安装、z3-solver 自动安装、环境变量默认配置、前后端启动。

#### 2.2 手动启动

##### 后端部署

```bash
## 1. 进入后端目录
cd .

## 2. 安装依赖
pip install uv
uv sync

## 3. 配置环境变量
cp config/.env.example config/.env
## 编辑 config/.env 文件配置 LLM 等参数

## 4. 启动后端
make dev
## 或：uvicorn app.main:app --app-dir studio --reload --host 0.0.0.0 --port 8000
```

##### 前端部署

```bash
## 1. 进入前端目录
cd studio/frontend

## 2. 安装依赖
pnpm install

## 3. 启动开发服务器
pnpm dev
```

#### 2.3 Redis（可选）

```bash
## Docker方式
docker run -d --name redis -p 6379:6379 redis:6-alpine

## 或系统安装
sudo apt install redis-server
```

#### 2.4 形式化验证工具链

`start.sh` 启动时会自动检测下列工具，缺失时打印安装提示。新用户首次启动会自动安装 **z3-solver**。

| 工具 | 用途 | 是否自动安装 | Linux/macOS | Windows |
|------|------|-------------|-------------|---------|
| **z3-solver** | 契约形式化验证(SMT) | ✅ 自动安装 | `pip install z3-solver` | 同左 |
| **cbmc** | C 代码有界模型检查 | ❌ 可选 | `apt install cbmc` / `brew install cbmc` | 双击 `tools/cbmc-6.9.0-win64.msi`（管理员权限） |
| **cppcheck** | MISRA-C 静态扫描 | ❌ 可选 | `apt install cppcheck` | `choco install cppcheck` 或官方安装包 |
| **gcc** | 代码编译 / 覆盖率插桩 | ❌ 可选 | 系统自带 | MinGW / MSYS2 |

> **Windows 注意事项**：
> - z3 通过 Python 包 `z3-solver` 提供，后端使用 `import z3` 检测可用性
> - cbmc 默认安装路径 `C:\Program Files\cbmc\bin\cbmc.exe`，后端会自动检测
> - cppcheck MISRA addon 使用 `sys.executable`（venv 内 Python）调用，避免 Windows Store python stub（exitcode 9009）问题

---

### 三、Docker Compose 部署

#### 3.1 生产环境

```bash
## 构建并启动
docker compose up -d --build

## 查看日志
docker compose logs -f

## 停止服务
docker compose down
```

服务列表：
- `skyforge-redis` - Redis缓存（端口6379）
- `skyforge-backend` - 后端API（端口8000）
- `skyforge-frontend` - 前端界面（端口80/443）

#### 3.2 开发环境

```bash
## 启动开发环境（含热重载）
docker compose -f docker-compose.dev.yml up -d --build
```

---

### 四、环境变量配置

#### 4.1 后端配置 (config/.env)

```env
## LLM配置
USE_LLM=true                     # 是否启用LLM（true/false），默认启用
LOCAL_LLM_BASE_URL=http://localhost:11434/v1  # 本地LLM地址（Ollama 默认 11434，LM Studio 默认 1234）
DEFAULT_MODEL=qwen3:8b           # 默认模型名

## 系统配置
ENV=dev                          # 环境（dev/prod）
LOG_LEVEL=INFO                   # 日志级别
DEBUG=true                       # 调试模式

## Redis（可选）
REDIS_URL=redis://localhost:6379/0

## HITL 人工审查
HITL_ENABLED=false               # 是否启用HITL 人工审查（默认禁用，避免阻塞自动化流程）
HITL_TIMEOUT=300                 # 审批超时时间（秒）
```

> 💡 `start.sh` 启动脚本会自动设置 `HITL_ENABLED=false` 并自动 `pip install z3-solver`，新用户无需手动配置。
> 本地 LLM 提供方根据端口自动识别：11434 → ollama，1234 → lmstudio，其他 → local。

> **术语说明**：HITL = Human-in-the-Loop 人工审查；HIL = Hardware-in-the-Loop 硬件在环。本文档中人工审查统一使用 HITL。

#### 4.2 前端配置 (frontend/.env.development)

```env
VITE_API_BASE_URL=http://localhost:8000
```

---

### 五、API接口文档

#### 5.1 V1 唯一任务协议

SkyForge v0.5.0 采用统一的 V1 任务协议，所有代码生成、验证、仿真等操作均通过任务接口完成。

#### 5.2 创建任务

```
POST /api/v1/tasks
```

请求体：
```json
{
  "type": "generate",
  "requirement": "实现一个高度传感器滤波模块...",
  "profile": "local",
  "options": {
    "simulate": true,
    "hitl_enabled": false
  }
}
```

响应：
```json
{
  "task_id": "task_abc123",
  "status": "pending",
  "created_at": "2026-07-21T10:00:00Z"
}
```

#### 5.3 任务事件流（WebSocket）

```
WS /api/v1/tasks/{task_id}/events
```

通过 WebSocket 实时推送任务执行事件，包括：
- 阶段变更事件（stage_change）
- 产物生成事件（artifact_ready）
- 日志输出事件（log）
- 进度更新事件（progress）
- 任务完成事件（completed）

事件格式示例：
```json
{
  "event": "stage_change",
  "data": {
    "stage": "code_generation",
    "status": "running",
    "evidence": "observed"
  },
  "timestamp": "2026-07-21T10:00:05Z"
}
```

**证据状态**：
| 状态 | 说明 |
|------|------|
| `observed` | 已观察到，真实执行证据 |
| `simulated` | 模拟数据，demo 模式下显示 |
| `unavailable` | 证据暂不可用 |
| `failed` | 验证失败 |

#### 5.4 健康检查

```
GET /api/health
```

响应：
```json
{"status": "healthy"}
```

#### 5.5 HITL 审查接口

```
GET  /api/hitl/pending      # 获取待审批项 + 当前启用状态
POST /api/hitl/approve      # 审批通过
POST /api/hitl/reject       # 审批拒绝
GET  /api/hitl/history      # 审批历史
POST /api/hitl/toggle       # 运行时切换 HITL 启用状态（无需重启）
```

> HITL 默认禁用（`HITL_ENABLED=false`），可通过 `POST /api/hitl/toggle` 或 Generate 页面开关按钮即时启用，无需重启后端。

---

### 六、生产环境配置

#### 6.1 Nginx配置

前端生产部署使用Nginx，配置文件：`frontend/nginx.conf`

```nginx
server {
    listen 80;
    server_name localhost;

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### 6.2 HTTPS配置（可选）

在Nginx配置中添加SSL证书：

```nginx
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    # ... 其他配置
}
```

---

### 七、性能优化

#### 7.1 后端优化

- 使用Redis缓存常用数据
- 调整 Worker 数量：`uvicorn app.main:app --app-dir studio --workers 4`
- 启用异步处理

#### 7.2 前端优化

- 生产构建自动代码分割
- 启用Gzip压缩（Nginx配置）
- 静态资源CDN加速

---

### 八、监控与日志

#### 8.1 日志位置

- 后端日志：`logs/`
- Docker日志：`docker compose logs`

#### 8.2 健康检查

```bash
## 检查后端状态
curl http://localhost:8000/api/health

## 检查容器状态
docker compose ps
```

---

### 九、常见问题

#### Q1: 端口被占用
```bash
## Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

## Linux/Mac
lsof -i :8000
kill -9 <PID>
```

#### Q2: Docker构建失败
```bash
## 清理缓存重新构建
docker compose down
docker system prune -a
docker compose up -d --build
```

#### Q3: LLM连接超时
- 检查LM Studio是否启动
- 确认防火墙设置
- 尝试使用Mock模式

---

### 十、工具鉴定与合规部署

#### 10.1 工具鉴定概述

根据 DO-178C §12.2 和 DO-330 标准，SkyForge 作为机载软件开发工具，需要进行工具鉴定（Tool Qualification）。鉴定计划与合规草案统一收录在 [`../developer-docs/DO178C_COMPLIANCE_PACKAGE.md`](../developer-docs/DO178C_COMPLIANCE_PACKAGE.md)。

#### 10.2 工具链合规检查

```bash
## 运行工具链验证脚本
python src/skyforge_engine/tools/tool_chain_validator.py

## 运行 DO-178C 合规检查
make do178c-check
```

#### 10.3 合规文档清单（统一合规包）

| 文档 | 路径 | 用途 |
|------|------|------|
| PSAC / SDP / SVP / SCMP / SQAP | `../developer-docs/DO178C_COMPLIANCE_PACKAGE.md` | 软件计划、开发、验证、配置管理与质量保证草案 |
| TQP / TOR / TAS | `../developer-docs/DO178C_COMPLIANCE_PACKAGE.md` | DO-330 工具鉴定计划、操作需求与总结草案 |
| 合规矩阵 | `docs/COMPLIANCE_MATRIX.csv` | DO-178C 目标覆盖矩阵 |

#### 10.4 安全部署检查清单

- [ ] 所有 LLM 调用走本地 LM Studio（数据不出内网）
- [ ] Cppcheck 作为外部工具独立运行（非链接，GPL 安全）
- [ ] 数字孪生 GCC 沙盒隔离执行
- [ ] XSS 防护启用（DOMPurify）
- [ ] API 限流启用（SlowAPI）
- [ ] 安全 Headers 启用

---

### 十一、卸载

```bash
## 停止服务
docker compose down

## 删除数据
docker compose down -v
rm -rf src/.venv
rm -rf studio/frontend/node_modules
rm -rf studio/frontend/dist
```


## 测试验证

> 更新日期：2026-07-21  
> 结论：本轮全项目审查后，前端测试、前端生产构建、Playwright 演示检查、后端/引擎/LLM 安全测试均已通过。测试数量以当前命令输出为准，不再沿用历史固定数字。

### 一、验证摘要

| 范围 | 命令 | 结果 |
|------|------|------|
| 前端单元/组件/服务测试 | `pnpm test` | 14 个测试文件，172 项测试通过 |
| 前端生产构建 | `pnpm build` | `vue-tsc -b && vite build` 通过 |
| 前端演示 E2E | `pnpm test:e2e` | 4 项 Playwright 检查通过（演示离线、设置弹窗） |
| 后端 / 引擎 / LLM 安全测试 | `uv run pytest -q` | 596 项通过 + 11 个 subtests |
| Python 静态检查 | `uv run ruff check .` | 通过 |
| Git 冲突标记 | `rg` 严格扫描 `<<<<<<< / ======= / >>>>>>>` | 未发现真实合并冲突 |
| PPT 文本溢出 | `slides_test.py` | 通过 |

### 二、前端验证

当前前端位于 `studio/frontend/`，核心技术栈为 Vue 3、Vite、Pinia、Vue Router、Vitest、Playwright、Monaco、ECharts、Tailwind CSS。

本轮升级与验证重点：

- 迁移图标库到官方 `@lucide/vue`。
- Vite / Vitest / Vue / Pinia / Vue Router 等依赖已升级并完成兼容修复。
- TypeScript 保留在 5.9.x，Tailwind 保留在 3.4.x，KaTeX 保留在 0.17.x，原因是当前 Vue 类型检查、PostCSS 和 `marked-katex-extension` 的兼容约束。
- `pnpm build` 已解决生产构建 TypeScript 错误。
- DemoGateway、模式切换、任务 Gateway、API 切换和关键 UI 组件测试均纳入前端测试。

### 三、后端与引擎验证

后端位于 `studio/app/`，核心引擎位于 `src/skyforge_engine/`，LLM 安全层位于 `src/skyforge_llm/security/`。

本轮验证覆盖：

- V1 任务协议：创建、查询、幂等、事件订阅、取消与兼容桥接。
- 任务 ID 与需求 ID 分离，`REQ-001` 仅作为任务内需求编号。
- Dashboard / 设置 / LLM 配置安全与脱敏。
- Pipeline、Agent、契约、代码修复、工具证据和数字孪生相关回归测试。
- LLM 输入净化、输出校验与安全边界测试。

### 四、证据可信度规则

测试报告不再把外部工具缺失解释为通过：

| 工具 / 阶段 | 规则 |
|-------------|------|
| Cppcheck | 不可用时必须标记 `unavailable` 或 `simulated`，不能用空数组表示零违规 |
| GCC | 记录实际命令、版本、退出码和 stderr；降级必须显式标记 |
| Z3 / CBMC | 按实际执行结果记录，不能硬编码通过 |
| 演示模式 | 输出“模拟演示报告”，不能标为适航证据 |
| 云 API / 本地模型 | 现场优先使用已验证运行包或真实运行 provenance |

### 五、建议提交前复验

```bash
cd SkyForge
uv run pytest studio/app/tests src/skyforge_engine/tests src/skyforge_llm/security/tests -q

cd studio/frontend
pnpm test
pnpm build
```

如要生成正式提交包，应排除 `.venv/`、`node_modules/`、`dist/`、临时数据库、日志和密钥文件。

### 六、边界声明

SkyForge 当前提供 DO-178C 工程辅助证据，不宣称工具本身已完成适航鉴定。演示模式为模拟数据；真实工具链结果以任务 provenance、工具版本、退出码、输出摘要和证据包哈希为准。
