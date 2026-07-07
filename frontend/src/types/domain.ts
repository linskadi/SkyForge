/**
 * SkyForge Domain Types
 * Shared type definitions used across the frontend
 */

/** 日志级别（与 VSCode 终端配色对齐） */
export type LogLevel = "info" | "success" | "warn" | "error";

/** Agent 类型（与文档 11.2.1 节徽章着色对齐） */
export type AgentType =
  | "REQ-Parser"
  | "CON-Gen"
  | "CODE-Gen"
  | "REPAIR"
  | "SYSTEM"
  | "TERMINAL";

/** 单条 Agent 思考日志（参考文档 11.2.1 节） */
export interface AgentLog {
  agent: AgentType;
  level: LogLevel;
  thought: string;
  /** 时间戳，由前端在收到消息时填充 */
  ts?: number;
}

/** 契约条件 */
export interface ContractCondition {
  id: string;
  expression: string;
  description?: string;
}

/** 完整契约（YAML 结构） */
export interface Contract {
  component: string;
  description: string;
  inputs: Record<string, string>;
  outputs: Record<string, string>;
  preconditions: ContractCondition[];
  postconditions: ContractCondition[];
  invariants: ContractCondition[];
  fault_handling: ContractCondition[];
}

/** MISRA-C 违规项 */
export interface MisraViolation {
  rule: string;
  category: "Required" | "Mandatory" | "Advisory";
  severity: "error" | "warn";
  file: string;
  line: number;
  message: string;
}

/** 单轮修复迭代（Patch 1 查改解耦：每轮修复 before/after/violations_fixed/violations_remaining） */
export interface RepairIteration {
  /** 轮次编号（1-based） */
  round: number;
  /** 修复前代码 */
  before_code: string;
  /** 修复后代码 */
  after_code: string;
  /** 修复前违规数 */
  violations_before: number;
  /** 修复后违规数 */
  violations_after: number;
  /** 本轮修复的规则列表 */
  violations_fixed: string[];
  /** 本轮修复后剩余的规则列表 */
  violations_remaining: string[];
  /** 修复说明 */
  description: string;
}

/** 契约校验单项结果（Patch 2 契约转断言） */
export interface ContractCheckItem {
  /** 条件 ID（对应 ContractCondition.id） */
  id: string;
  /** 条件表达式 */
  expression: string;
  /** 条件描述 */
  description?: string;
  /** 是否通过 */
  passed: boolean;
  /** 失败原因（passed=false 时有值） */
  failure_reason?: string;
  /** 自动生成的 assert 代码片段（Patch 2 断言插桩） */
  assert_code: string;
}

/** 契约校验分区结果 */
export interface ContractCheckSection {
  /** 分区名称（中文） */
  title: string;
  /** 分区 key */
  key: "preconditions" | "postconditions" | "invariants" | "fault_handling";
  /** 该分区的所有检查项 */
  items: ContractCheckItem[];
}

/** 完整契约校验结果（Patch 2 契约转断言：YAML 契约 -> C assert 注入 test_harness） */
export interface ContractCheckResult {
  /** 组件名 */
  component: string;
  /** 校验分区列表 */
  sections: ContractCheckSection[];
  /** 通过数 */
  passed_count: number;
  /** 总数 */
  total_count: number;
  /** 整体是否通过 */
  overall_passed: boolean;
  /** 自动生成的完整 assert 代码（注入 test_harness.c） */
  generated_assert_code: string;
}

// ===================== Day 3: 数字孪生仿真类型 =====================

/** 故障类型（5 类，参考文档第 6 章数字孪生） */
export type FaultType =
  | "bias" // 传感器偏置
  | "signal_loss" // 信号丢失
  | "noise" // 高频噪声
  | "stuck" // 卡死故障
  | "step"; // 阶跃突变

/** 故障注入参数（不同故障类型使用不同字段） */
export interface FaultParams {
  /** 偏置值（bias 类型） */
  bias_value?: number;
  /** 信号丢失持续时间（signal_loss 类型，单位：步） */
  loss_duration?: number;
  /** 噪声幅度（noise 类型） */
  noise_amplitude?: number;
  /** 卡死值（stuck 类型） */
  stuck_value?: number;
  /** 突变发生时间步（step 类型） */
  step_time?: number;
  /** 突变后值（step 类型） */
  step_value?: number;
}

/** 契约违约信息（仿真中发现契约被违反时填充） */
export interface ContractViolation {
  /** 违约的契约条件 ID */
  contract_id: string;
  /** 触发断言的 assert 表达式 */
  assertion: string;
  /** 违约发生的时间步 */
  timestep: number;
  /** 违约时的实际值 */
  actual_value: number;
  /** 违约描述 */
  message: string;
}

/** 仿真统计信息 */
export interface SimulationStatistics {
  /** 仿真步数 */
  total_steps: number;
  /** 输入波形范围 [min, max] */
  input_range: [number, number];
  /** 输出波形范围 [min, max] */
  output_range: [number, number];
  /** 输出最大值 */
  output_max: number;
  /** 输出最小值 */
  output_min: number;
  /** 输出均值 */
  output_mean: number;
}

/** 数字孪生仿真结果（参考文档第 6 章数字孪生沙盒） */
export interface SimulationResult {
  /** 是否通过（契约全部满足） */
  passed: boolean;
  /** 仿真总步数 */
  total_steps: number;
  /** 注入的故障类型（null 表示无故障的正常仿真） */
  fault_type: FaultType | null;
  /** 故障参数 */
  fault_params: FaultParams;
  /** 输入波形数据（每个时间步一个采样点） */
  input_waveform: number[];
  /** 输出波形数据（每个时间步一个采样点） */
  output_waveform: number[];
  /** 故障影响区间（波形突变范围，用于红色高亮） */
  fault_range: { start: number; end: number } | null;
  /** 契约违约信息（passed=false 时有值） */
  contract_violation: ContractViolation | null;
  /** 仿真统计 */
  statistics: SimulationStatistics;
  /** 仿真终端日志（与 AgentTerminal 同级，仅含仿真相关日志） */
  logs: AgentLog[];
}

/** 生成结果 */
export interface GenerateResult {
  contract: Contract;
  code: string;
  violations: MisraViolation[];
  /** 追溯矩阵：REQ-xxx -> 代码行号列表 */
  traceability: Record<string, number[]>;
  /** 修复历史（Patch 1 查改解耦闭环，Day 2） */
  repair_history: RepairIteration[];
  /** 契约校验结果（Patch 2 契约转断言，Day 2） */
  contract_check_result: ContractCheckResult;
  /** 数字孪生仿真结果（Day 3，默认无故障仿真） */
  simulation_result: SimulationResult;
}

// ===================== Day 4+: 后端新功能类型 =====================

/** 组合连接方式 */
export type ComposeConnection = "sequential" | "parallel" | "feedback";

/** 兼容性检查单项结果 */
export interface CompatibilityCheckItem {
  /** 检查项 ID */
  id: string;
  /** 检查内容 */
  check: string;
  /** 是否通过 */
  passed: boolean;
  /** 失败原因（passed=false 时有值） */
  reason?: string;
}

/** 兼容性检查结果 */
export interface CompatibilityResult {
  /** 组件 A 名称 */
  component_a: string;
  /** 组件 B 名称 */
  component_b: string;
  /** 连接方式 */
  connection: ComposeConnection;
  /** 兼容性检查项列表 */
  checks: CompatibilityCheckItem[];
  /** 通过数 */
  passed_count: number;
  /** 总数 */
  total_count: number;
  /** 整体是否兼容 */
  overall_compatible: boolean;
}

/** 组件组合结果 */
export interface ComposeResult {
  /** 组件 A 名称 */
  component_a: string;
  /** 组件 B 名称 */
  component_b: string;
  /** 连接方式 */
  connection: ComposeConnection;
  /** 组合后 C 代码 */
  composed_code: string;
  /** 兼容性检查结果 */
  compatibility: CompatibilityResult;
  /** 组合后仿真结果 */
  simulation: SimulationResult;
}

/** LLM 模型信息 */
export interface LLMModel {
  /** 模型 ID */
  id: string;
  /** 模型名称 */
  name: string;
  /** 模型大小（GB） */
  size?: number;
  /** 上下文长度 */
  context_length?: number;
  /** 是否已加载 */
  loaded: boolean;
}

/** LLM 状态 */
export interface LLMStatus {
  /** LM Studio 是否可用 */
  available: boolean;
  /** LM Studio 连接地址 */
  endpoint: string;
  /** 当前是否使用真实 LLM（false 表示使用 Mock） */
  use_llm: boolean;
  /** 已加载模型列表 */
  models: LLMModel[];
  /** 当前选中的模型 ID */
  current_model?: string;
  /** 最近响应时间统计（毫秒） */
  response_time_ms?: number;
  /** 最近调用次数 */
  total_calls?: number;
}

/** SCADE 变量信息 */
export interface ScadeVariable {
  /** 变量名 */
  name: string;
  /** 变量类型 */
  type: string;
  /** 变量描述 */
  description?: string;
}

/** SCADE 等式信息 */
export interface ScadeEquation {
  /** 等式左侧（输出变量） */
  lhs: string;
  /** 等式右侧（表达式） */
  rhs: string;
}

/** SCADE 解析结果 */
export interface ScadeParseResult {
  /** node 名称 */
  node_name: string;
  /** 输入变量列表 */
  inputs: ScadeVariable[];
  /** 输出变量列表 */
  outputs: ScadeVariable[];
  /** 局部变量列表 */
  locals: ScadeVariable[];
  /** 等式列表 */
  equations: ScadeEquation[];
  /** 转换后的自然语言需求 */
  natural_language_requirement: string;
  /** 转换后的契约 YAML */
  contract_yaml: string;
  /** 解析时的文件名 */
  source_file: string;
}

/** HIL 检查点类型 */
export type HILCheckpointType =
  | "requirement_review"
  | "contract_review"
  | "code_review"
  | "final_review";

/** HIL 待审批项 */
export interface HILApproval {
  /** 审批请求 ID */
  request_id: string;
  /** 检查点类型 */
  checkpoint: HILCheckpointType;
  /** 检查点名称（中文） */
  checkpoint_name: string;
  /** 内容预览 */
  content_preview: string;
  /** 完整内容（按需展开） */
  content_detail?: string;
  /** 提交时间戳 */
  submitted_at: number;
  /** 超时时间戳 */
  deadline: number;
  /** 当前状态 */
  status: "pending" | "approved" | "rejected" | "timeout";
}

/** HIL 审批历史项 */
export interface HILHistoryItem extends HILApproval {
  /** 审批人 */
  reviewer?: string;
  /** 审批时间戳 */
  reviewed_at?: number;
  /** 审批评论 */
  comments?: string;
}

/** DO-178C 报告概要 */
export interface ReportSummary {
  /** 报告标题 */
  title: string;
  /** 生成时间 */
  generated_at: number;
  /** 追溯矩阵条目数 */
  traceability_entries: number;
  /** DO-178C 目标总数 */
  total_objectives: number;
  /** DO-178C 通过目标数 */
  passed_objectives: number;
  /** 通过率 */
  pass_rate: number;
  /** 仿真结果摘要 */
  simulation_summary: string;
  /** MISRA 违规数 */
  misra_violations: number;
}

/** DO-178C 报告生成结果 */
export interface ReportResult {
  /** 报告 ID */
  report_id: string;
  /** 报告 HTML 内容 */
  html: string;
  /** 报告概要 */
  summary: ReportSummary;
}

// ===================== Day 5: MISRA 搜索与修复类型 =====================

/** MISRA-C 规则详情（用于规则搜索） */
export interface MisraRule {
  /** 规则 ID，如 "MISRA-Rule-8.1" */
  rule_id: string;
  /** 规则标题 */
  title: string;
  /** 规则描述 */
  description: string;
  /** 规则分类 */
  category: "Required" | "Mandatory" | "Advisory";
  /** 规则所属章节 */
  section?: string;
  /** 违规示例代码 */
  bad_example?: string;
  /** 合规示例代码 */
  good_example?: string;
}

/** 修复结果（独立修复接口的返回类型） */
export interface RepairResult {
  /** 修复后代码 */
  final_code: string;
  /** 修复历史 */
  repair_history: RepairIteration[];
  /** 修复后剩余违规 */
  final_violations: MisraViolation[];
  /** 契约校验结果 */
  contract_check_result: ContractCheckResult;
}
