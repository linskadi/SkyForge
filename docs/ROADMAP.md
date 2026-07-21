# SkyForge 路线图

## 版本规划

### v0.5.0 (当前版本)

**发布日期**: 2026-07-21

**核心功能**:
- [x] 引擎六层架构升级（L0-L5: Protocols/LLM Client/Simulation & Verification/Verifier Chain/Agent Strategy/Orchestration）
- [x] PipelineOrchestrator 编排器，调度 12 个 Stage
- [x] V1 唯一任务协议（idempotency_key + 事件续传 + provenance）
- [x] 11 个前端页面 + 6 项顶部导航栏
- [x] 三种执行模式 Profile（demo/cloud/local）
- [x] 验证工具链可插拔（Z3/CBMC/Cppcheck/GCC）
- [x] 仿真验证层（SIL: 虚拟MCU/虚拟传感器/故障注入 | PIL: QEMU/ARINC653 | HIL: 串口/JTAG-SWD）
- [x] 组件组合验证系统（compatibility_checker + component_combinator）
- [x] MISRA 规则搜索引擎（语义搜索 + RAG 增强）
- [x] DO-178C 报告生成（可追溯性矩阵/PSAC/证据收集器）
- [x] MC/DC 覆盖分析（gcov_collector + mcdc_calculator）
- [x] 测试分析闭环（覆盖率数据流：pipeline → coverage_analyzer → report_generator → DO-178C OBJ-13/14/15，GCC 14.2+ lcov 真实收集 + 静态分析自动回退）
- [x] SCADE G-Lustre 解析器
- [x] 流处理任务注册（task_stream_registry）
- [x] 四层可剥离部署架构
- [x] 多 Agent 协同系统
- [x] 可插拔编码标准系统 (MISRA-C / MISRA-C++ / Python)
- [x] 多语言支持 (C / C++ / Python)
- [x] 数字孪生仿真
- [x] HITL 人工审查
- [x] 形式化验证（z3 SMT + cbmc 有界模型检查）

**测试覆盖**:
- 后端/引擎/LLM 安全测试：596 pytest passed，11 subtests passed
- 前端测试：172 Vitest passed，4 E2E passed

---

### v0.4.x (历史版本)

#### v0.4.1 (2026-07-18)
- **工具链完善**：z3-solver 自动安装（pip）+ cbmc Windows msi 安装包（tools/cbmc-6.9.0-win64.msi）
- **HITL 默认禁用**：`HIL_ENABLED` 默认 `false`，新增运行时 toggle API（`POST /api/hil/toggle`）+ UI 开关
- **Dashboard 重构**：系统状态 4 分区（后端/LLM/工具链/持久化），工具链实时检测 gcc/z3/cbmc
- **前端性能优化**：4 个长轮询组件使用 visibilitychange 暂停策略，页面后台时停止轮询
- **LLM 长任务超时**：generate/repair/generateReport 统一 180s 超时，兼容本地模型推理
- **Windows 兼容性修复**：cppcheck MISRA addon 使用 `sys.executable` 避免 Windows Store python stub
- **测试覆盖提升**：后端 210→250 全通过 + 0 warnings；前端 135→161 全通过
- **本地 LLM Provider 自动检测**：根据 Base URL 端口识别 ollama(11434)/lmstudio(1234)/local(其他)
- **Dashboard LLM JSON 解析稳健性**：safe_parse_llm_json 返回 None 时优雅降级到规则引擎
- **前端类型安全**：修复 27 个 vue-tsc 错误 + 全部 biome lint warnings 清零

#### v0.4.0 (2026-07-17)
- 四层可剥离架构设计
- 多 Agent 协同系统
- DO-178C 合规检查引擎
- MISRA-C 自动修复
- 数字孪生仿真环境
- HITL 人工审查
- SCADE 模型集成
- Web 工作室界面
- 可插拔编码标准系统
- 航空仪表盘 UI

---

## 未来规划

### v0.6.0 (规划中)

**核心功能**:
- [ ] 更多故障注入模型
- [ ] 本地模型深度优化
- [ ] GCC 交叉编译支持
- [ ] 自动化测试用例生成
- [ ] DO-178C 工具鉴定流程
- [ ] 多模型并行推理

---

## 功能优先级

| 功能 | 目标版本 | 优先级 | 描述 |
|------|----------|--------|------|
| 工具鉴定 | v0.6.0 | 高 | 完成 DO-178C 工具鉴定流程 |
| 自动化测试生成 | v0.6.0 | 高 | 自动生成符合 DO-178C 的测试用例 |
| 多模型推理 | v0.6.0 | 中 | 支持多个 LLM 并行推理与结果融合 |
| GCC 交叉编译 | v0.6.0 | 中 | 支持多平台交叉编译验证 |

---

*最后更新: 2026-07-21*
