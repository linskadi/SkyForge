/**
 * AirborneAI Mock API 服务
 * 后端 API 尚未完成时，用 mock 数据跑通前端流程
 * 参考文档 11.2.1 节时间轴
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

/** 模拟的 Agent 思考日志流（参考文档 11.2.1 节时间轴，0-30s 浓缩为 5s） */
const MOCK_AGENT_LOGS: AgentLog[] = [
  {
    agent: "REQ-Parser",
    level: "info",
    thought: "正在解析需求... 识别关键词: 低通滤波器 / 截止频率 10Hz / 一阶 IIR",
  },
  {
    agent: "REQ-Parser",
    level: "success",
    thought: "需求解析完成：生成需求标签 [REQ-001] 截止频率 fc=10Hz；[REQ-002] 输出范围 [0, 65535]",
  },
  {
    agent: "CON-Gen",
    level: "info",
    thought: "生成契约中：postcondition output >= 0 且 output <= 65535",
  },
  {
    agent: "CON-Gen",
    level: "success",
    thought: "契约生成完成 [CON-001-POST-001]；invariant: alpha ∈ [0, 1]",
  },
  {
    agent: "CODE-Gen",
    level: "info",
    thought: "正在生成 filter() 函数... 采用一阶 IIR 结构 y[n] = alpha*x[n] + (1-alpha)*y[n-1]",
  },
  {
    agent: "CODE-Gen",
    level: "success",
    thought: "C 代码生成完成，已标注 [REQ-001] [REQ-002] [MISRA-Rule-8.1]",
  },
  {
    agent: "SYSTEM",
    level: "info",
    thought: "$ cppcheck --addon=misra --enable=all code.c",
  },
  {
    agent: "TERMINAL",
    level: "warn",
    thought: "[code.c:12] (style) Variable 'alpha' not initialized. [MISRA-Rule-9.1]",
  },
  {
    agent: "REPAIR",
    level: "info",
    thought: "检测到违规 [MISRA-Rule-9.1]：变量 alpha 未初始化，正在自动修复...",
  },
  {
    agent: "REPAIR",
    level: "success",
    thought: "已添加初始化 alpha = 0.0f；并补充类型声明 [MISRA-Rule-8.1]",
  },
  {
    agent: "SYSTEM",
    level: "info",
    thought: "$ gcc -c code.c -o code.o && gcc test_harness.c code.o -o sim",
  },
  {
    agent: "TERMINAL",
    level: "success",
    thought: "$ ./sim < input.bin  →  全部测试用例通过 (8/8)",
  },
  {
    agent: "SYSTEM",
    level: "success",
    thought: "✅ 全流程完成：5 秒合规检查，5 分钟完整交付",
  },
];

/** 模拟的示例需求 */
export const EXAMPLE_REQUIREMENTS: string[] = [
  "实现一个低通滤波器，截止频率 10Hz，用于滤除传感器高频噪声",
  "实现一个 PID 控制器，Kp=2.0, Ki=0.5, Kd=0.1，控制无人机俯仰角",
  "实现一个 ARINC 429 字解析函数，将 32 位字解码为标签、SDI、数据",
  "实现一个余度管理器，双通道输入取均值，偏差 > 5% 时报警",
];

/** mock 的契约数据 */
const MOCK_CONTRACT: Contract = {
  component: "LowPassFilter",
  description: "一阶低通滤波器，截止频率 10Hz，用于滤除传感器高频噪声",
  inputs: {
    raw_value: "uint16_t  // 原始 ADC 采样值",
    sample_rate: "uint16_t  // 采样率 (Hz)",
  },
  outputs: {
    filtered_value: "uint16_t  // 滤波后输出值",
  },
  preconditions: [
    {
      id: "CON-001-PRE-000",
      expression: "sample_rate > 0",
      description: "采样率必须大于 0",
    },
    {
      id: "CON-001-PRE-001",
      expression: "raw_value <= 65535",
      description: "原始值不超过 uint16 范围",
    },
  ],
  postconditions: [
    {
      id: "CON-001-POST-000",
      expression: "0 <= filtered_value <= 65535",
      description: "输出值在合法范围内",
    },
    {
      id: "CON-001-POST-001",
      expression: "filtered_value == round(alpha * raw_value + (1 - alpha) * prev)",
      description: "符合一阶 IIR 滤波公式",
    },
  ],
  invariants: [
    {
      id: "CON-001-INV-000",
      expression: "0.0f <= alpha <= 1.0f",
      description: "滤波系数 alpha 始终在 [0,1] 范围",
    },
  ],
  fault_handling: [
    {
      id: "CON-001-FLT-000",
      expression: "if sample_rate == 0 then return prev_filtered",
      description: "采样率异常时保持上一拍输出",
    },
  ],
};
/** mock 的 C 代码（含 [REQ-xxx] 与 [MISRA-Rule-x.x] Tag） */
const MOCK_CODE = `/**
 * @file code.c
 * @brief 一阶低通滤波器实现
 * @requirement [REQ-001] 截止频率 10Hz
 * @requirement [REQ-002] 输出范围 [0, 65535]
 */

#include <stdint.h>

/* 滤波器状态结构体 [REQ-001] [MISRA-Rule-8.1] */
typedef struct {
    float alpha;        /* 滤波系数 */
    uint16_t prev_out;  /* 上一拍输出 */
} LowPassFilter_t;

/**
 * @brief 初始化滤波器
 * @requirement [REQ-001] */
void filter_init(LowPassFilter_t *f, uint16_t sample_rate)
{
    /* 一阶 IIR: alpha = fc / (fc + fs) */
    float fc = 10.0f;  /* 截止频率 10Hz [REQ-001] */
    f->alpha = fc / (fc + (float)sample_rate);  /* [MISRA-Rule-10.4] fixed */
    f->prev_out = 0U;  /* [MISRA-Rule-9.1] fixed */
}

/**
 * @brief 执行一次滤波
 * @requirement [REQ-001] [REQ-002] */
uint16_t filter_apply(LowPassFilter_t *f, uint16_t raw_value)
{
    float in = (float)raw_value;
    float out = f->alpha * in + (1.0f - f->alpha) * (float)f->prev_out;

    /* [REQ-002] 输出范围限制 */
    if (out < 0.0f) {
        out = 0.0f;  /* [MISRA-Rule-10.4] fixed */
    } else if (out > 65535.0f) {
        out = 65535.0f;
    }

    f->prev_out = (uint16_t)out;
    return f->prev_out;  /* [CON-001-POST-000] */
}

/**
 * @brief 获取当前滤波系数
 * @requirement [REQ-001] */
float filter_get_alpha(const LowPassFilter_t *f)  /* [MISRA-Rule-8.13] fixed */
{
    return f->alpha;
}
`;

/** mock 的 MISRA 违规列表（初始发现，共 4 个；修复历史见 MOCK_REPAIR_HISTORY） */
const MOCK_VIOLATIONS: MisraViolation[] = [
  {
    rule: "MISRA-Rule-8.1",
    category: "Required",
    severity: "warn",
    file: "code.c",
    line: 11,
    message: "Struct member should be explicitly initialized.",
  },
  {
    rule: "MISRA-Rule-10.4",
    category: "Required",
    severity: "warn",
    file: "code.c",
    line: 30,
    message: "Both operands of an expression shall have the same essential type category.",
  },
  {
    rule: "MISRA-Rule-9.1",
    category: "Mandatory",
    severity: "error",
    file: "code.c",
    line: 18,
    message: "Variable 'alpha' was not initialized before use (auto-repaired).",
  },
  {
    rule: "MISRA-Rule-8.13",
    category: "Advisory",
    severity: "warn",
    file: "code.c",
    line: 40,
    message: "Pointer parameter 'f' in filter_get_alpha should be declared as pointer-to-const (auto-repaired).",
  },
];

/** mock 的追溯矩阵 */
const MOCK_TRACEABILITY: Record<string, number[]> = {
  "REQ-001": [11, 16, 18, 23, 27, 38],
  "REQ-002": [23, 28, 29, 33],
};

/** MISRA 规则说明（用于 tooltip 显示） */
export const MISRA_RULE_DOCS: Record<string, string> = {
  "MISRA-Rule-8.1": "Required: All declarations shall be qualified with appropriate type specifiers.",
  "MISRA-Rule-9.1": "Mandatory: The value of an object with automatic storage shall not be read before being set.",
  "MISRA-Rule-10.4": "Required: Both operands of an operator shall have the same essential type category.",
  "MISRA-Rule-8.13": "Advisory: A pointer parameter in a function prototype should be declared as pointer-to-const if the pointer is not used to modify the addressed object.",
};
/** 修复前代码 V0：初始生成，含 4 个违规（Patch 1 查改解耦 - 查） */
const MOCK_REPAIR_CODE_V0 = `typedef struct {
    float alpha;
    uint16_t prev_out;
} LowPassFilter_t;

void filter_init(LowPassFilter_t *f, uint16_t sample_rate)
{
    float fc = 10.0f;
    f->alpha = fc / (fc + sample_rate);  /* [MISRA-Rule-10.4] type mismatch */
    f->prev_out = 0;  /* [MISRA-Rule-9.1] not initialized with U suffix */
}

uint16_t filter_apply(LowPassFilter_t *f, uint16_t raw_value)
{
    float in = raw_value;  /* [MISRA-Rule-10.4] implicit conversion */
    float out = f->alpha * in + (1.0f - f->alpha) * f->prev_out;
    if (out < 0) out = 0;
    else if (out > 65535) out = 65535;
    f->prev_out = out;
    return f->prev_out;
}

/* [MISRA-Rule-8.13] f not modified, should be const */
float filter_get_alpha(LowPassFilter_t *f)
{
    return f->alpha;
}
`;

/** 修复后代码 V1：第 1 轮修复后，剩 1 个违规（Rule-8.13 未修） */
const MOCK_REPAIR_CODE_V1 = `typedef struct {
    float alpha;
    uint16_t prev_out;
} LowPassFilter_t;

void filter_init(LowPassFilter_t *f, uint16_t sample_rate)
{
    float fc = 10.0f;
    f->alpha = fc / (fc + (float)sample_rate);  /* [MISRA-Rule-10.4] fixed */
    f->prev_out = 0U;  /* [MISRA-Rule-9.1] fixed */
}

uint16_t filter_apply(LowPassFilter_t *f, uint16_t raw_value)
{
    float in = (float)raw_value;  /* [MISRA-Rule-10.4] fixed */
    float out = f->alpha * in + (1.0f - f->alpha) * (float)f->prev_out;
    if (out < 0.0f) out = 0.0f;
    else if (out > 65535.0f) out = 65535.0f;
    f->prev_out = (uint16_t)out;
    return f->prev_out;
}

/* [MISRA-Rule-8.13] still pending - f should be const */
float filter_get_alpha(LowPassFilter_t *f)
{
    return f->alpha;
}
`;

/** 修复后代码 V2：第 2 轮修复后，0 个违规（最终版本） */
const MOCK_REPAIR_CODE_V2 = `typedef struct {
    float alpha;
    uint16_t prev_out;
} LowPassFilter_t;

void filter_init(LowPassFilter_t *f, uint16_t sample_rate)
{
    float fc = 10.0f;
    f->alpha = fc / (fc + (float)sample_rate);
    f->prev_out = 0U;
}

uint16_t filter_apply(LowPassFilter_t *f, uint16_t raw_value)
{
    float in = (float)raw_value;
    float out = f->alpha * in + (1.0f - f->alpha) * (float)f->prev_out;
    if (out < 0.0f) out = 0.0f;
    else if (out > 65535.0f) out = 65535.0f;
    f->prev_out = (uint16_t)out;
    return f->prev_out;
}

/* [MISRA-Rule-8.13] fixed */
float filter_get_alpha(const LowPassFilter_t *f)
{
    return f->alpha;
}
`;

/** mock 的修复历史（Patch 1 查改解耦闭环：2 轮修复，4 → 1 → 0） */
const MOCK_REPAIR_HISTORY: RepairIteration[] = [
  {
    round: 1,
    before_code: MOCK_REPAIR_CODE_V0,
    after_code: MOCK_REPAIR_CODE_V1,
    violations_before: 4,
    violations_after: 1,
    violations_fixed: ["MISRA-Rule-9.1", "MISRA-Rule-10.4", "MISRA-Rule-8.1"],
    violations_remaining: ["MISRA-Rule-8.13"],
    description: "Cppcheck 扫描发现 4 个违规，LLM 自动修复 3 处：变量初始化、类型转换、显式类型限定。Rule-8.13 需第 2 轮处理。",
  },
  {
    round: 2,
    before_code: MOCK_REPAIR_CODE_V1,
    after_code: MOCK_REPAIR_CODE_V2,
    violations_before: 1,
    violations_after: 0,
    violations_fixed: ["MISRA-Rule-8.13"],
    violations_remaining: [],
    description: "修复 filter_get_alpha 的指针参数为 const，符合 Rule-8.13 Advisory。全部违规清零。",
  },
];
/** mock 的契约校验结果（Patch 2 契约转断言：YAML -> C assert 注入 test_harness） */
const MOCK_CONTRACT_CHECK_RESULT: ContractCheckResult = {
  component: "LowPassFilter",
  sections: [
    {
      title: "前置条件 Preconditions",
      key: "preconditions",
      items: [
        {
          id: "CON-001-PRE-000",
          expression: "sample_rate > 0",
          description: "采样率必须大于 0",
          passed: true,
          assert_code: 'assert(sample_rate > 0 && "[CON-001-PRE-000] 违反前置条件: 采样率必须大于 0");',
        },
        {
          id: "CON-001-PRE-001",
          expression: "raw_value <= 65535",
          description: "原始值不超过 uint16 范围",
          passed: true,
          assert_code: 'assert(raw_value <= 65535 && "[CON-001-PRE-001] 违反前置条件: 原始值超范围");',
        },
      ],
    },
    {
      title: "后置条件 Postconditions",
      key: "postconditions",
      items: [
        {
          id: "CON-001-POST-000",
          expression: "0 <= filtered_value <= 65535",
          description: "输出值在合法范围内",
          passed: true,
          assert_code: 'assert(filtered_value >= 0 && filtered_value <= 65535 && "[CON-001-POST-000] 违反后置条件: 输出越界");',
        },
        {
          id: "CON-001-POST-001",
          expression: "filtered_value == round(alpha * raw_value + (1 - alpha) * prev)",
          description: "符合一阶 IIR 滤波公式",
          passed: false,
          failure_reason: "浮点精度边界：fc=10Hz, fs=100Hz 时 alpha=0.0909，浮点误差 1e-7 触发严格 assert 失败。实际可接受，建议增加容差 eps=1e-6。",
          assert_code: 'assert(fabs(filtered_value - (alpha * raw_value + (1 - alpha) * prev)) < 1e-6 && "[CON-001-POST-001] 违反后置条件: IIR 公式不匹配");',
        },
      ],
    },
    {
      title: "不变式 Invariants",
      key: "invariants",
      items: [
        {
          id: "CON-001-INV-000",
          expression: "0.0f <= alpha <= 1.0f",
          description: "滤波系数 alpha 始终在 [0,1] 范围",
          passed: true,
          assert_code: 'assert(alpha >= 0.0f && alpha <= 1.0f && "[CON-001-INV-000] 违反不变式: alpha 超范围");',
        },
      ],
    },
    {
      title: "故障处理 Fault Handling",
      key: "fault_handling",
      items: [
        {
          id: "CON-001-FLT-000",
          expression: "if sample_rate == 0 then return prev_filtered",
          description: "采样率异常时保持上一拍输出",
          passed: true,
          assert_code: 'assert((sample_rate == 0 ? filtered_value == prev_filtered : 1) && "[CON-001-FLT-000] 违反故障处理: 采样率异常未保持输出");',
        },
      ],
    },
  ],
  passed_count: 5,
  total_count: 6,
  overall_passed: false,
  generated_assert_code: `/* ===== 自动生成的契约断言（Patch 2，请勿手动修改）===== */
/* 由 contract_to_assert.py 从 .contract YAML 自动生成 */
#include <assert.h>
#include <math.h>

static void __check_contract_CON_001(double filtered_value, double alpha,
                                     double raw_value, double prev,
                                     uint16_t sample_rate, double prev_filtered) {
    /* [CON-001-PRE-000] 采样率必须大于 0 */
    assert(sample_rate > 0 && "[CON-001-PRE-000] 违反前置条件");
    /* [CON-001-PRE-001] 原始值不超过 uint16 范围 */
    assert(raw_value <= 65535 && "[CON-001-PRE-001] 违反前置条件");
    /* [CON-001-POST-000] 输出值在合法范围内 */
    assert(filtered_value >= 0 && filtered_value <= 65535
           && "[CON-001-POST-000] 违反后置条件");
    /* [CON-001-POST-001] 符合一阶 IIR 滤波公式 */
    assert(fabs(filtered_value - (alpha * raw_value + (1 - alpha) * prev)) < 1e-6
           && "[CON-001-POST-001] 违反后置条件: IIR 公式不匹配");
    /* [CON-001-INV-000] 滤波系数 alpha 始终在 [0,1] 范围 */
    assert(alpha >= 0.0f && alpha <= 1.0f
           && "[CON-001-INV-000] 违反不变式");
    /* [CON-001-FLT-000] 采样率异常时保持上一拍输出 */
    assert((sample_rate == 0 ? filtered_value == prev_filtered : 1)
           && "[CON-001-FLT-000] 违反故障处理");
}`,
};
// ===================== Day 3: 数字孪生 mock 数据 =====================

/** 仿真步数 */
const SIM_STEPS = 200;
/** 一阶 IIR 滤波系数（fc=10Hz, fs=100Hz -> alpha≈0.0909） */
const FILTER_ALPHA = 0.0909;
/** uint16 中点 */
const ADC_CENTER = 32768;
/** 正弦波幅度 */
const SINE_AMP = 20000;

/** 生成正常正弦输入波形：32768 + 20000*sin(2π·t/50) */
function genSineInput(steps: number): number[] {
  const wave: number[] = [];
  for (let t = 0; t < steps; t++) {
    const v = ADC_CENTER + SINE_AMP * Math.sin((2 * Math.PI * t) / 50);
    wave.push(Math.round(v));
  }
  return wave;
}

/** 一阶 IIR 低通滤波：y[n] = alpha*x[n] + (1-alpha)*y[n-1] */
function lowpassFilter(input: number[], alpha: number): number[] {
  const out: number[] = [];
  let prev = 0;
  for (let i = 0; i < input.length; i++) {
    const y = alpha * input[i] + (1 - alpha) * prev;
    out.push(Math.round(y));
    prev = y;
  }
  return out;
}

/** 计算波形统计信息 */
function computeStats(input: number[], output: number[]): SimulationStatistics {
  const inMin = Math.min(...input);
  const inMax = Math.max(...input);
  const outMin = Math.min(...output);
  const outMax = Math.max(...output);
  const outMean = output.reduce((s, v) => s + v, 0) / output.length;
  return {
    total_steps: input.length,
    input_range: [inMin, inMax],
    output_range: [outMin, outMax],
    output_max: outMax,
    output_min: outMin,
    output_mean: Math.round(outMean * 100) / 100,
  };
}

/** 正常仿真日志（无故障，契约全通过） */
const MOCK_SIM_LOGS: AgentLog[] = [
  { agent: "SYSTEM", level: "info", thought: "$ gcc -fsanitize=address code.c test_harness.c -o sim" },
  { agent: "SYSTEM", level: "success", thought: "编译成功，test_harness.c 已注入 6 条契约断言（Patch 2）" },
  { agent: "SYSTEM", level: "info", thought: "$ ./sim --steps 200 --input sine_10Hz.bin" },
  { agent: "TERMINAL", level: "info", thought: "[sim] step 0: input=32768, output=2982 (初始化瞬态)" },
  { agent: "TERMINAL", level: "info", thought: "[sim] step 50: input=52768, output=51023 (稳态跟踪)" },
  { agent: "TERMINAL", level: "info", thought: "[sim] step 100: input=12768, output=14539 (稳态跟踪)" },
  { agent: "TERMINAL", level: "success", thought: "[sim] 全部 200 步仿真完成，6/6 契约断言通过" },
  { agent: "SYSTEM", level: "success", thought: "✅ 数字孪生仿真通过，契约零违约" },
];

/** mock 的正常仿真结果（无故障，200 步，契约全部通过） */
const MOCK_SIMULATION_RESULT: SimulationResult = (() => {
  const input = genSineInput(SIM_STEPS);
  const output = lowpassFilter(input, FILTER_ALPHA);
  return {
    passed: true,
    total_steps: SIM_STEPS,
    fault_type: null,
    fault_params: {},
    input_waveform: input,
    output_waveform: output,
    fault_range: null,
    contract_violation: null,
    statistics: computeStats(input, output),
    logs: MOCK_SIM_LOGS,
  };
})();

/**
 * 故障注入仿真：根据故障类型生成对应的故障波形和仿真结果
 * 不同故障会触发不同的契约违约（参考文档 6.4.1 契约断言）
 *
 * @param faultType 故障类型
 * @param params 故障参数
 * @returns 含故障的仿真结果（带契约违约信息）
 */
export function mockSimulate(
  faultType: FaultType,
  params: FaultParams,
): Promise<SimulationResult> {
  console.log("[mockApi] 调用 mockSimulate，故障类型：", faultType, "参数：", params);
  return new Promise((resolve) => {
    setTimeout(() => {
      const input = genSineInput(SIM_STEPS);
      // 先正常滤波得到基线输出
      const baseOutput = lowpassFilter(input, FILTER_ALPHA);

      let faultedInput = [...input];
      let faultRange: { start: number; end: number } | null = null;
      let violation: ContractViolation | null = null;
      let logs: AgentLog[] = [];

      switch (faultType) {
        case "bias": {
          // 传感器偏置：输入叠加固定偏置值
          const bias = params.bias_value ?? 20000;
          const start = 40;
          faultedInput = input.map((v, t) =>
            t >= start ? Math.min(65535, v + bias) : v,
          );
          faultRange = { start, end: SIM_STEPS - 1 };
          logs = [
            { agent: "SYSTEM", level: "info", thought: `$ ./sim --fault bias --bias ${bias} --start ${start}` },
            { agent: "TERMINAL", level: "warn", thought: `[sim] step ${start}: 注入传感器偏置 +${bias}` },
            { agent: "TERMINAL", level: "error", thought: `[sim] step ${start + 2}: assert(filtered_value <= 65535) FAILED → 输出溢出` },
            { agent: "SYSTEM", level: "error", thought: `❌ 契约违约 [CON-001-POST-000]：输出值超出 uint16 范围` },
            { agent: "SYSTEM", level: "info", thought: `💡 沙盒已捕获 core dump，未影响宿主环境（参考文档 6.6 沙盒隔离）` },
          ];
          violation = {
            contract_id: "CON-001-POST-000",
            assertion: "assert(filtered_value >= 0 && filtered_value <= 65535)",
            timestep: start + 2,
            actual_value: 65536 + Math.round(bias * FILTER_ALPHA),
            message: `传感器偏置 +${bias} 导致滤波输出溢出 uint16 范围（第 ${start + 2} 步触发）`,
          };
          break;
        }
        case "signal_loss": {
          // 信号丢失：指定区间内输入强制为 0
          const duration = params.loss_duration ?? 30;
          const start = 50;
          const end = Math.min(SIM_STEPS - 1, start + duration);
          faultedInput = input.map((v, t) =>
            t >= start && t < end ? 0 : v,
          );
          faultRange = { start, end };
          logs = [
            { agent: "SYSTEM", level: "info", thought: `$ ./sim --fault signal_loss --duration ${duration} --start ${start}` },
            { agent: "TERMINAL", level: "warn", thought: `[sim] step ${start}: 信号丢失，输入强制为 0，持续 ${duration} 步` },
            { agent: "TERMINAL", level: "warn", thought: `[sim] step ${end}: 信号恢复` },
            { agent: "SYSTEM", level: "warn", thought: `⚠ 信号丢失期间输出保持上一拍（CON-001-FLT-000 故障处理生效）` },
            { agent: "SYSTEM", level: "success", thought: `✅ 故障处理契约通过，但输出跟踪误差超阈值` },
          ];
          // 信号丢失触发故障处理契约，输出保持但跟踪误差大（不违约，但警告）
          violation = {
            contract_id: "CON-001-POST-001",
            assertion: "assert(fabs(filtered_value - expected) < 1e-6)",
            timestep: end,
            actual_value: baseOutput[end] ?? 0,
            message: `信号丢失 ${duration} 步后恢复，IIR 跟踪误差超出容差 1e-6（第 ${end} 步）`,
          };
          break;
        }
        case "noise": {
          // 高频噪声：输入叠加随机噪声
          const amp = params.noise_amplitude ?? 5000;
          faultedInput = input.map((v) =>
            Math.max(0, Math.min(65535, v + Math.round((Math.random() - 0.5) * 2 * amp))),
          );
          faultRange = { start: 0, end: SIM_STEPS - 1 };
          logs = [
            { agent: "SYSTEM", level: "info", thought: `$ ./sim --fault noise --amplitude ${amp}` },
            { agent: "TERMINAL", level: "warn", thought: `[sim] 全程注入高频噪声，幅度 ±${amp}` },
            { agent: "TERMINAL", level: "error", thought: `[sim] step 73: assert(filtered_value == round(alpha*x + (1-alpha)*prev)) FAILED` },
            { agent: "SYSTEM", level: "error", thought: `❌ 契约违约 [CON-001-POST-001]：噪声破坏 IIR 滤波公式一致性` },
          ];
          violation = {
            contract_id: "CON-001-POST-001",
            assertion: "assert(fabs(filtered_value - (alpha*raw_value + (1-alpha)*prev)) < 1e-6)",
            timestep: 73,
            actual_value: baseOutput[73] ?? 0,
            message: `高频噪声 ±${amp} 导致 IIR 公式浮点精度被破坏（第 73 步触发）`,
          };
          break;
        }
        case "stuck": {
          // 卡死故障：从某步起输入卡在固定值
          const stuckVal = params.stuck_value ?? 40000;
          const start = 60;
          faultedInput = input.map((v, t) =>
            t >= start ? stuckVal : v,
          );
          faultRange = { start, end: SIM_STEPS - 1 };
          logs = [
            { agent: "SYSTEM", level: "info", thought: `$ ./sim --fault stuck --value ${stuckVal} --start ${start}` },
            { agent: "TERMINAL", level: "warn", thought: `[sim] step ${start}: 传感器卡死在 ${stuckVal}` },
            { agent: "TERMINAL", level: "info", thought: `[sim] step ${start + 20}: 输出收敛至 ${Math.round(stuckVal * FILTER_ALPHA + 32768 * (1 - FILTER_ALPHA))}` },
            { agent: "SYSTEM", level: "warn", thought: `⚠ 卡死故障未触发契约违约，但输出已偏离真实信号` },
            { agent: "SYSTEM", level: "info", thought: `💡 建议增加余度管理器检测卡死（参考文档余度管理章节）` },
          ];
          // 卡死故障不触发契约违约（输出仍合法），但标记为异常
          violation = null;
          break;
        }
        case "step": {
          // 阶跃突变：指定时间步输入突变到指定值
          const stepTime = params.step_time ?? 80;
          const stepVal = params.step_value ?? 60000;
          faultedInput = input.map((v, t) =>
            t >= stepTime ? stepVal : v,
          );
          faultRange = { start: stepTime, end: SIM_STEPS - 1 };
          logs = [
            { agent: "SYSTEM", level: "info", thought: `$ ./sim --fault step --time ${stepTime} --value ${stepVal}` },
            { agent: "TERMINAL", level: "warn", thought: `[sim] step ${stepTime}: 阶跃突变，输入跳变至 ${stepVal}` },
            { agent: "TERMINAL", level: "error", thought: `[sim] step ${stepTime + 1}: assert(filtered_value <= 65535) FAILED → 阶跃导致输出溢出` },
            { agent: "SYSTEM", level: "error", thought: `❌ 契约违约 [CON-001-POST-000]：阶跃突变导致输出越界` },
          ];
          violation = {
            contract_id: "CON-001-POST-000",
            assertion: "assert(filtered_value <= 65535)",
            timestep: stepTime + 1,
            actual_value: stepVal,
            message: `阶跃突变至 ${stepVal} 导致滤波输出在 ${stepTime + 1} 步溢出 uint16 范围`,
          };
          break;
        }
      }

      // 根据故障输入重新滤波（故障会影响输出）
      let finalOutput: number[];
      if (faultType === "stuck" || faultType === "step" || faultType === "bias") {
        // 这些故障改变输入，需重新滤波
        finalOutput = lowpassFilter(faultedInput, FILTER_ALPHA);
      } else if (faultType === "noise") {
        finalOutput = lowpassFilter(faultedInput, FILTER_ALPHA);
      } else {
        // signal_loss：故障处理保持上一拍输出
        finalOutput = [...baseOutput];
        if (faultRange) {
          for (let t = faultRange.start; t <= faultRange.end && t < finalOutput.length; t++) {
            finalOutput[t] = finalOutput[faultRange.start - 1] ?? 0;
          }
        }
      }

      const passed = violation === null;
      resolve({
        passed,
        total_steps: SIM_STEPS,
        fault_type: faultType,
        fault_params: params,
        input_waveform: faultedInput,
        output_waveform: finalOutput,
        fault_range: faultRange,
        contract_violation: violation,
        statistics: computeStats(faultedInput, finalOutput),
        logs,
      });
    }, 1200);
  });
}

/** 生成结果：模拟 POST /api/generate 的响应（延迟 1.5s） */
export function mockGenerate(requirement: string): Promise<GenerateResult> {
  console.log("[mockApi] 调用 mockGenerate，需求：", requirement);
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        contract: MOCK_CONTRACT,
        code: MOCK_CODE,
        violations: MOCK_VIOLATIONS,
        traceability: MOCK_TRACEABILITY,
        repair_history: MOCK_REPAIR_HISTORY,
        contract_check_result: MOCK_CONTRACT_CHECK_RESULT,
        simulation_result: MOCK_SIMULATION_RESULT,
      });
    }, 1500);
  });
}

/**
 * 模拟 WebSocket 推送 6 个 Agent 的思考日志
 * 在 5 秒内逐条推送（与文档 11.2.1 节时间轴对齐，0-30s 浓缩为 5s）
 *
 * @param onLog 收到一条日志时的回调
 * @param onDone 全部推送完成的回调
 * @returns 返回一个 stop 函数，调用后停止推送
 */
export function mockAgentStream(
  onLog: (log: AgentLog) => void,
  onDone?: () => void,
): () => void {
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | null = null;

  // 每条日志之间的间隔（毫秒）— 5s 推完 13 条
  const interval = 5;

  const next = (index: number) => {
    if (stopped) return;
    if (index >= MOCK_AGENT_LOGS.length) {
      onDone?.();
      return;
    }
    const log = MOCK_AGENT_LOGS[index];
    onLog({ ...log, ts: Date.now() });
    timer = setTimeout(() => next(index + 1), interval * 1000);
  };

  // 首条日志立即推送
  next(0);

  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
  };
}

/**
 * 真实 WebSocket 连接（后端完成后启用）
 * 连接 ws://localhost:8000/ws/agent-stream，逐条接收 {agent, level, thought} 消息
 *
 * @param url WebSocket 地址，默认 ws://localhost:8000/ws/agent-stream
 * @param onLog 收到一条日志时的回调
 * @param onStatus 连接状态变化的回调
 * @returns 返回一个 close 函数
 */
export function connectAgentStream(
  onLog: (log: AgentLog) => void,
  onStatus?: (status: "connecting" | "connected" | "disconnected") => void,
  url = "ws://localhost:8000/ws/agent-stream",
): () => void {
  onStatus?.("connecting");
  let ws: WebSocket | null = null;
  try {
    ws = new WebSocket(url);
  } catch (err) {
    console.error("[mockApi] WebSocket 连接失败：", err);
    onStatus?.("disconnected");
    return () => {};
  }

  ws.onopen = () => {
    console.log("[mockApi] WebSocket 已连接:", url);
    onStatus?.("connected");
  };
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as AgentLog;
      onLog({ ...data, ts: Date.now() });
    } catch (err) {
      console.error("[mockApi] 解析 WebSocket 消息失败：", err);
    }
  };
  ws.onerror = (err) => {
    console.error("[mockApi] WebSocket 错误：", err);
  };
  ws.onclose = () => {
    console.log("[mockApi] WebSocket 已关闭");
    onStatus?.("disconnected");
  };

  return () => {
    ws?.close();
  };
}

// ===================== Day 4+: 后端新功能 mock 数据 =====================

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

/** mock LLM 状态 */
const MOCK_LLM_STATUS: LLMStatus = {
  available: false,
  endpoint: "http://localhost:1234/v1",
  use_llm: false,
  models: [
    {
      id: "qwen2.5-coder-7b-instruct",
      name: "Qwen2.5-Coder-7B-Instruct",
      size: 4.7,
      context_length: 32768,
      loaded: true,
    },
    {
      id: "deepseek-coder-6.7b-instruct",
      name: "DeepSeek-Coder-6.7B-Instruct",
      size: 4.0,
      context_length: 16384,
      loaded: false,
    },
  ],
  current_model: "qwen2.5-coder-7b-instruct",
  response_time_ms: 0,
  total_calls: 0,
};

/** 当前 LLM 状态（响应式副本，便于 mock 切换） */
let mockLLMState: LLMStatus = { ...MOCK_LLM_STATUS };

/** mock 低通滤波器组件代码 */
const MOCK_LP_CODE = `/* LowPassFilter.c */
#include <stdint.h>
typedef struct { float alpha; uint16_t prev_out; } LowPassFilter_t;
void filter_init(LowPassFilter_t *f, uint16_t sample_rate) {
    float fc = 10.0f;
    f->alpha = fc / (fc + (float)sample_rate);
    f->prev_out = 0U;
}
uint16_t filter_apply(LowPassFilter_t *f, uint16_t raw_value) {
    float in = (float)raw_value;
    float out = f->alpha * in + (1.0f - f->alpha) * (float)f->prev_out;
    if (out < 0.0f) out = 0.0f;
    else if (out > 65535.0f) out = 65535.0f;
    f->prev_out = (uint16_t)out;
    return f->prev_out;
}
`;

/** mock 高通滤波器组件代码 */
const MOCK_HP_CODE = `/* HighPassFilter.c */
#include <stdint.h>
typedef struct { float alpha; uint16_t prev_in; uint16_t prev_out; } HighPassFilter_t;
void hp_init(HighPassFilter_t *f, uint16_t sample_rate) {
    float fc = 10.0f;
    f->alpha = fc / (fc + (float)sample_rate);
    f->prev_in = 0U;
    f->prev_out = 0U;
}
uint16_t hp_apply(HighPassFilter_t *f, uint16_t raw_value) {
    float out = f->alpha * ((float)f->prev_out + (float)raw_value - (float)f->prev_in);
    if (out < 0.0f) out = 0.0f;
    else if (out > 65535.0f) out = 65535.0f;
    f->prev_in = raw_value;
    f->prev_out = (uint16_t)out;
    return f->prev_out;
}
`;

/** mock 低通契约 YAML */
const MOCK_LP_CONTRACT = `component: LowPassFilter
description: 一阶低通滤波器
inputs:
  raw_value: uint16_t
  sample_rate: uint16_t
outputs:
  filtered_value: uint16_t
preconditions:
  - id: CON-LP-PRE-000
    expression: "sample_rate > 0"
postconditions:
  - id: CON-LP-POST-000
    expression: "0 <= filtered_value <= 65535"
invariants:
  - id: CON-LP-INV-000
    expression: "0.0 <= alpha <= 1.0"
`;

/** mock 高通契约 YAML */
const MOCK_HP_CONTRACT = `component: HighPassFilter
description: 一阶高通滤波器
inputs:
  raw_value: uint16_t
  sample_rate: uint16_t
outputs:
  filtered_value: uint16_t
preconditions:
  - id: CON-HP-PRE-000
    expression: "sample_rate > 0"
postconditions:
  - id: CON-HP-POST-000
    expression: "0 <= filtered_value <= 65535"
invariants:
  - id: CON-HP-INV-000
    expression: "0.0 <= alpha <= 1.0"
`;

/** mock 组合后代码（顺序组合：低通 + 高通） */
const MOCK_COMPOSED_CODE_SEQUENTIAL = `/* ComposedFilter_Sequential.c */
/* 顺序组合：低通滤波 → 高通滤波（带通滤波器） */
#include <stdint.h>
typedef struct { float alpha; uint16_t prev_out; } LowPassFilter_t;
typedef struct { float alpha; uint16_t prev_in; uint16_t prev_out; } HighPassFilter_t;
typedef struct {
    LowPassFilter_t lp;
    HighPassFilter_t hp;
} BandPassFilter_t;

void bandpass_init(BandPassFilter_t *b, uint16_t sample_rate) {
    float fc = 10.0f;
    b->lp.alpha = fc / (fc + (float)sample_rate);
    b->lp.prev_out = 0U;
    b->hp.alpha = fc / (fc + (float)sample_rate);
    b->hp.prev_in = 0U;
    b->hp.prev_out = 0U;
}

uint16_t bandpass_apply(BandPassFilter_t *b, uint16_t raw_value) {
    /* Step 1: LowPass */
    float in1 = (float)raw_value;
    float lp_out = b->lp.alpha * in1 + (1.0f - b->lp.alpha) * (float)b->lp.prev_out;
    if (lp_out < 0.0f) lp_out = 0.0f;
    else if (lp_out > 65535.0f) lp_out = 65535.0f;
    b->lp.prev_out = (uint16_t)lp_out;

    /* Step 2: HighPass */
    float in2 = lp_out;
    float hp_out = b->hp.alpha * ((float)b->hp.prev_out + in2 - (float)b->hp.prev_in);
    if (hp_out < 0.0f) hp_out = 0.0f;
    else if (hp_out > 65535.0f) hp_out = 65535.0f;
    b->hp.prev_in = (uint16_t)in2;
    b->hp.prev_out = (uint16_t)hp_out;
    return b->hp.prev_out;
}
`;

/** mock 组合后代码（并行组合） */
const MOCK_COMPOSED_CODE_PARALLEL = `/* ComposedFilter_Parallel.c */
/* 并行组合：低通 + 高通并行计算，输出取均值 */
#include <stdint.h>
typedef struct { float alpha; uint16_t prev_out; } LowPassFilter_t;
typedef struct { float alpha; uint16_t prev_in; uint16_t prev_out; } HighPassFilter_t;
typedef struct {
    LowPassFilter_t lp;
    HighPassFilter_t hp;
} ParallelFilter_t;

void parallel_init(ParallelFilter_t *p, uint16_t sample_rate) {
    float fc = 10.0f;
    p->lp.alpha = fc / (fc + (float)sample_rate);
    p->lp.prev_out = 0U;
    p->hp.alpha = fc / (fc + (float)sample_rate);
    p->hp.prev_in = 0U;
    p->hp.prev_out = 0U;
}

uint16_t parallel_apply(ParallelFilter_t *p, uint16_t raw_value) {
    /* LP path */
    float lp_out = p->lp.alpha * (float)raw_value + (1.0f - p->lp.alpha) * (float)p->lp.prev_out;
    if (lp_out < 0.0f) lp_out = 0.0f;
    else if (lp_out > 65535.0f) lp_out = 65535.0f;
    p->lp.prev_out = (uint16_t)lp_out;

    /* HP path */
    float hp_out = p->hp.alpha * ((float)p->hp.prev_out + (float)raw_value - (float)p->hp.prev_in);
    if (hp_out < 0.0f) hp_out = 0.0f;
    else if (hp_out > 65535.0f) hp_out = 65535.0f;
    p->hp.prev_in = raw_value;
    p->hp.prev_out = (uint16_t)hp_out;

    /* 取均值 */
    return (uint16_t)((lp_out + hp_out) / 2.0f);
}
`;

/** mock 组合后代码（反馈组合） */
const MOCK_COMPOSED_CODE_FEEDBACK = `/* ComposedFilter_Feedback.c */
/* 反馈组合：低通输出反馈给高通输入，形成闭环 */
#include <stdint.h>
typedef struct { float alpha; uint16_t prev_out; } LowPassFilter_t;
typedef struct { float alpha; uint16_t prev_in; uint16_t prev_out; } HighPassFilter_t;
typedef struct {
    LowPassFilter_t lp;
    HighPassFilter_t hp;
    uint16_t feedback;
} FeedbackFilter_t;

void feedback_init(FeedbackFilter_t *f, uint16_t sample_rate) {
    float fc = 10.0f;
    f->lp.alpha = fc / (fc + (float)sample_rate);
    f->lp.prev_out = 0U;
    f->hp.alpha = fc / (fc + (float)sample_rate);
    f->hp.prev_in = 0U;
    f->hp.prev_out = 0U;
    f->feedback = 0U;
}

uint16_t feedback_apply(FeedbackFilter_t *f, uint16_t raw_value) {
    /* HP 处理 raw - feedback */
    int32_t diff = (int32_t)raw_value - (int32_t)f->feedback;
    uint16_t hp_in = diff < 0 ? 0 : (diff > 65535 ? 65535 : (uint16_t)diff);
    float hp_out = f->hp.alpha * ((float)f->hp.prev_out + (float)hp_in - (float)f->hp.prev_in);
    if (hp_out < 0.0f) hp_out = 0.0f;
    else if (hp_out > 65535.0f) hp_out = 65535.0f;
    f->hp.prev_in = hp_in;
    f->hp.prev_out = (uint16_t)hp_out;

    /* LP 处理 HP 输出 */
    float lp_out = f->lp.alpha * hp_out + (1.0f - f->lp.alpha) * (float)f->lp.prev_out;
    if (lp_out < 0.0f) lp_out = 0.0f;
    else if (lp_out > 65535.0f) lp_out = 65535.0f;
    f->lp.prev_out = (uint16_t)lp_out;

    /* 反馈 */
    f->feedback = f->lp.prev_out;
    return f->feedback;
}
`;

/** 根据连接方式选择 mock 组合代码 */
function pickComposedCode(connection: ComposeConnection): string {
  switch (connection) {
    case "sequential":
      return MOCK_COMPOSED_CODE_SEQUENTIAL;
    case "parallel":
      return MOCK_COMPOSED_CODE_PARALLEL;
    case "feedback":
      return MOCK_COMPOSED_CODE_FEEDBACK;
    default:
      return MOCK_COMPOSED_CODE_SEQUENTIAL;
  }
}

/** 构造兼容性检查结果（mock） */
function buildCompatibility(
  compA: string,
  compB: string,
  connection: ComposeConnection,
): CompatibilityResult {
  const checks: CompatibilityCheckItem[] = [
    {
      id: "COMPAT-001",
      check: "组件 A 输出类型与组件 B 输入类型匹配",
      passed: true,
    },
    {
      id: "COMPAT-002",
      check: "组件 A 输出范围在组件 B 输入允许范围内",
      passed: true,
    },
    {
      id: "COMPAT-003",
      check: "组件 A 后置条件与组件 B 前置条件无冲突",
      passed: true,
    },
    {
      id: "COMPAT-004",
      check: "连接方式与组件接口签名一致",
      passed: true,
    },
    {
      id: "COMPAT-005",
      check: "无循环依赖或类型循环",
      passed: connection !== "feedback",
      reason: connection === "feedback"
        ? "反馈连接需要额外的稳定性分析，建议增加收敛性检查（mock 警告）"
        : undefined,
    },
    {
      id: "COMPAT-006",
      check: "组合后不变式集合可满足",
      passed: true,
    },
  ];
  const passedCount = checks.filter((c) => c.passed).length;
  return {
    component_a: compA,
    component_b: compB,
    connection,
    checks,
    passed_count: passedCount,
    total_count: checks.length,
    overall_compatible: passedCount === checks.length,
  };
}

/**
 * mock 组件组合验证
 * 模拟 POST /api/compose
 *
 * @param compA 组件 A 名称
 * @param compB 组件 B 名称
 * @param connection 连接方式
 * @returns 组合结果（含代码、兼容性检查、仿真结果）
 */
export function mockCompose(
  compA: string,
  compB: string,
  connection: ComposeConnection,
): Promise<ComposeResult> {
  console.log("[mockApi] 调用 mockCompose，组件A:", compA, "组件B:", compB, "连接:", connection);
  return new Promise((resolve) => {
    setTimeout(() => {
      const composedCode = pickComposedCode(connection);
      const compatibility = buildCompatibility(compA, compB, connection);

      // 简单生成仿真波形
      const steps = 100;
      const input: number[] = [];
      const output: number[] = [];
      let prev = 0;
      const alpha = 0.1;
      for (let t = 0; t < steps; t++) {
        const v = 32768 + Math.round(20000 * Math.sin((2 * Math.PI * t) / 50));
        input.push(v);
        const y = alpha * v + (1 - alpha) * prev;
        output.push(Math.round(y));
        prev = y;
      }

      const simLogs: AgentLog[] = [
        { agent: "SYSTEM", level: "info", thought: "$ gcc -c composed.c -o composed.o" },
        { agent: "SYSTEM", level: "success", thought: "组合代码编译通过" },
        { agent: "SYSTEM", level: "info", thought: "$ ./composed_sim --steps 100" },
        { agent: "TERMINAL", level: "success", thought: "[sim] 全部 100 步仿真完成" },
        {
          agent: "SYSTEM",
          level: compatibility.overall_compatible ? "success" : "warn",
          thought: compatibility.overall_compatible
            ? "✅ 兼容性检查通过，组合可行"
            : "⚠ 兼容性检查有警告，组合可能不稳定",
        },
      ];

      const simulation: SimulationResult = {
        passed: compatibility.overall_compatible,
        total_steps: steps,
        fault_type: null,
        fault_params: {},
        input_waveform: input,
        output_waveform: output,
        fault_range: null,
        contract_violation: null,
        statistics: {
          total_steps: steps,
          input_range: [Math.min(...input), Math.max(...input)],
          output_range: [Math.min(...output), Math.max(...output)],
          output_max: Math.max(...output),
          output_min: Math.min(...output),
          output_mean: Math.round(output.reduce((s, v) => s + v, 0) / output.length),
        },
        logs: simLogs,
      };

      resolve({
        component_a: compA,
        component_b: compB,
        connection,
        composed_code: composedCode,
        compatibility,
        simulation,
      });
    }, 1200);
  });
}

/**
 * mock 兼容性检查
 * 模拟 POST /api/check-compatibility
 */
export function mockCheckCompatibility(
  contractA: string,
  contractB: string,
  connection: ComposeConnection,
): Promise<CompatibilityResult> {
  console.log(
    "[mockApi] 调用 mockCheckCompatibility，contractA:",
    contractA,
    "contractB:",
    contractB,
    "连接:",
    connection,
  );
  return new Promise((resolve) => {
    setTimeout(() => {
      // 简单从 YAML 字符串提取 component 名称
      const extractName = (yaml: string): string => {
        const m = yaml.match(/component:\s*(\S+)/);
        return m ? m[1] : "Component";
      };
      resolve(
        buildCompatibility(extractName(contractA), extractName(contractB), connection),
      );
    }, 600);
  });
}

/**
 * mock 获取 LLM 状态
 * 模拟 GET /api/llm/status
 */
export function mockGetLLMStatus(): Promise<LLMStatus> {
  console.log("[mockApi] 调用 mockGetLLMStatus");
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({ ...mockLLMState });
    }, 300);
  });
}

/**
 * mock 切换 LLM 开关
 * 模拟 POST /api/llm/switch
 */
export function mockSwitchLLM(useLLM: boolean): Promise<LLMStatus> {
  console.log("[mockApi] 调用 mockSwitchLLM，启用 LLM:", useLLM);
  return new Promise((resolve) => {
    setTimeout(() => {
      mockLLMState = {
        ...mockLLMState,
        use_llm: useLLM,
        available: useLLM ? true : false,
      };
      resolve({ ...mockLLMState });
    }, 400);
  });
}

/**
 * mock 获取可用模型列表
 * 模拟 GET /api/models
 */
export function mockGetModels(): Promise<LLMModel[]> {
  console.log("[mockApi] 调用 mockGetModels");
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve([...MOCK_LLM_STATUS.models]);
    }, 300);
  });
}

/**
 * mock 选择模型
 * 模拟 POST /api/models/select
 */
export function mockSelectModel(modelId: string): Promise<LLMStatus> {
  console.log("[mockApi] 调用 mockSelectModel，模型 ID:", modelId);
  return new Promise((resolve) => {
    setTimeout(() => {
      mockLLMState = {
        ...mockLLMState,
        current_model: modelId,
      };
      resolve({ ...mockLLMState });
    }, 300);
  });
}

/**
 * mock 上传 SCADE 文件并解析
 * 模拟 POST /api/upload-scade
 *
 * @param file 上传的文件
 * @returns SCADE 解析结果
 */
export function mockUploadScade(file: File): Promise<ScadeParseResult> {
  console.log("[mockApi] 调用 mockUploadScade，文件名:", file.name, "大小:", file.size);
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        node_name: "LowPassFilter",
        inputs: [
          { name: "raw_value", type: "uint16", description: "原始 ADC 采样值" },
          { name: "sample_rate", type: "uint16", description: "采样率 (Hz)" },
        ],
        outputs: [
          { name: "filtered_value", type: "uint16", description: "滤波后输出值" },
        ],
        locals: [
          { name: "alpha", type: "float", description: "滤波系数" },
          { name: "prev_out", type: "uint16", description: "上一拍输出" },
        ],
        equations: [
          {
            lhs: "alpha",
            rhs: "10.0 / (10.0 + sample_rate)",
          },
          {
            lhs: "filtered_value",
            rhs: "alpha * raw_value + (1.0 - alpha) * prev_out",
          },
        ],
        natural_language_requirement:
          "实现一个一阶低通滤波器，截止频率 10Hz，输入为 uint16 原始 ADC 采样值和 uint16 采样率，输出为 uint16 滤波后值。" +
          "滤波公式：y[n] = alpha * x[n] + (1 - alpha) * y[n-1]，其中 alpha = fc / (fc + fs)。",
        contract_yaml:
          "component: LowPassFilter\n" +
          "description: 一阶低通滤波器，截止频率 10Hz\n" +
          "inputs:\n" +
          "  raw_value: uint16  // 原始 ADC 采样值\n" +
          "  sample_rate: uint16  // 采样率 (Hz)\n" +
          "outputs:\n" +
          "  filtered_value: uint16  // 滤波后输出值\n" +
          "preconditions:\n" +
          "  - id: CON-LP-PRE-000\n" +
          "    expression: \"sample_rate > 0\"\n" +
          "    description: 采样率必须大于 0\n" +
          "postconditions:\n" +
          "  - id: CON-LP-POST-000\n" +
          "    expression: \"0 <= filtered_value <= 65535\"\n" +
          "    description: 输出值在 uint16 范围内\n" +
          "invariants:\n" +
          "  - id: CON-LP-INV-000\n" +
          "    expression: \"0.0 <= alpha <= 1.0\"\n" +
          "    description: 滤波系数 alpha 始终在 [0,1] 范围\n",
        source_file: file.name,
      });
    }, 1000);
  });
}

/** mock HIL 待审批列表 */
let mockHILPending: HILApproval[] = [
  {
    request_id: "HIL-REQ-001",
    checkpoint: "requirement_review",
    checkpoint_name: "需求审查",
    content_preview:
      "需求：实现一个低通滤波器，截止频率 10Hz，用于滤除传感器高频噪声。包含 REQ-001, REQ-002 两个需求条目。",
    content_detail:
      "完整需求文档：\n[REQ-001] 截止频率 fc=10Hz\n[REQ-002] 输出范围 [0, 65535]\n[REQ-003] 采样率 fs=100Hz",
    submitted_at: Date.now() - 1000 * 60 * 5,
    deadline: Date.now() + 1000 * 60 * 25,
    status: "pending",
  },
  {
    request_id: "HIL-REQ-002",
    checkpoint: "contract_review",
    checkpoint_name: "契约审查",
    content_preview:
      "契约 LowPassFilter: 输入 raw_value, sample_rate；输出 filtered_value；6 个契约条件。",
    content_detail:
      "契约 YAML:\ncomponent: LowPassFilter\ninputs:\n  raw_value: uint16\n  sample_rate: uint16\noutputs:\n  filtered_value: uint16",
    submitted_at: Date.now() - 1000 * 60 * 2,
    deadline: Date.now() + 1000 * 60 * 28,
    status: "pending",
  },
];

/** mock HIL 审批历史 */
let mockHILHistory: HILHistoryItem[] = [];

/**
 * mock 获取待审批列表
 * 模拟 GET /api/hil/pending
 */
export function mockGetPendingApprovals(): Promise<HILApproval[]> {
  console.log("[mockApi] 调用 mockGetPendingApprovals");
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve([...mockHILPending]);
    }, 300);
  });
}

/**
 * mock 批准 HIL 请求
 * 模拟 POST /api/hil/approve
 *
 * @param requestId 审批请求 ID
 * @param comments 审批评论
 */
export function mockApprove(
  requestId: string,
  comments: string,
): Promise<{ success: boolean; reviewer: string; reviewed_at: number }> {
  console.log("[mockApi] 调用 mockApprove，requestId:", requestId, "comments:", comments);
  return new Promise((resolve) => {
    setTimeout(() => {
      const idx = mockHILPending.findIndex((p) => p.request_id === requestId);
      if (idx >= 0) {
        const item = mockHILPending[idx];
        mockHILPending.splice(idx, 1);
        mockHILHistory.unshift({
          ...item,
          status: "approved",
          reviewer: "mock-user",
          reviewed_at: Date.now(),
          comments,
        });
      }
      resolve({
        success: true,
        reviewer: "mock-user",
        reviewed_at: Date.now(),
      });
    }, 400);
  });
}

/**
 * mock 拒绝 HIL 请求
 * 模拟 POST /api/hil/reject
 *
 * @param requestId 审批请求 ID
 * @param comments 拒绝理由
 */
export function mockReject(
  requestId: string,
  comments: string,
): Promise<{ success: boolean; reviewer: string; reviewed_at: number }> {
  console.log("[mockApi] 调用 mockReject，requestId:", requestId, "comments:", comments);
  return new Promise((resolve) => {
    setTimeout(() => {
      const idx = mockHILPending.findIndex((p) => p.request_id === requestId);
      if (idx >= 0) {
        const item = mockHILPending[idx];
        mockHILPending.splice(idx, 1);
        mockHILHistory.unshift({
          ...item,
          status: "rejected",
          reviewer: "mock-user",
          reviewed_at: Date.now(),
          comments,
        });
      }
      resolve({
        success: true,
        reviewer: "mock-user",
        reviewed_at: Date.now(),
      });
    }, 400);
  });
}

/**
 * mock 获取 HIL 审批历史
 */
export function mockGetHILHistory(): Promise<HILHistoryItem[]> {
  console.log("[mockApi] 调用 mockGetHILHistory");
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve([...mockHILHistory]);
    }, 300);
  });
}

/**
 * mock 生成 DO-178C 报告
 * 模拟 POST /api/report
 *
 * @param result 生成结果（用于填充报告内容）
 */
export function mockGenerateReport(result: GenerateResult): Promise<ReportResult> {
  console.log("[mockApi] 调用 mockGenerateReport，输入结果:", result);
  return new Promise((resolve) => {
    setTimeout(() => {
      const traceabilityCount = Object.keys(result.traceability).length;
      const misraCount = result.violations.length;
      const simPassed = result.simulation_result.passed;
      const contractPassed = result.contract_check_result.overall_passed;
      const contractPassRate = result.contract_check_result.passed_count /
        Math.max(1, result.contract_check_result.total_count);

      const reportId = `DO178C-REPORT-${Date.now()}`;
      const generatedAt = Date.now();

      const summary: ReportSummary = {
        title: `DO-178C 报告 - ${result.contract.component}`,
        generated_at: generatedAt,
        traceability_entries: traceabilityCount,
        total_objectives: 66,
        passed_objectives: Math.round(66 * (contractPassRate * 0.5 + (simPassed ? 0.3 : 0) + 0.2)),
        pass_rate: 0,
        simulation_summary: simPassed
          ? "数字孪生仿真通过，全部契约断言无违约"
          : "仿真中发现契约违约，详见仿真报告章节",
        misra_violations: misraCount,
      };
      summary.pass_rate = summary.passed_objectives / summary.total_objectives;

      // 构造简化的 DO-178C 报告 HTML
      const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>${summary.title}</title>
  <style>
    body { font-family: 'Segoe UI', 'PingFang SC', sans-serif; padding: 40px; color: #1f2937; line-height: 1.6; }
    h1 { color: #1e6fb8; border-bottom: 2px solid #1e6fb8; padding-bottom: 8px; }
    h2 { color: #1e6fb8; margin-top: 32px; }
    .summary-card { background: #f0f9ff; border-left: 4px solid #1e6fb8; padding: 16px 20px; margin: 16px 0; border-radius: 4px; }
    .stat { display: inline-block; margin: 8px 24px 8px 0; }
    .stat-value { font-size: 24px; font-weight: 700; color: #1e6fb8; }
    .stat-label { font-size: 12px; color: #6b7280; text-transform: uppercase; }
    table { width: 100%; border-collapse: collapse; margin: 12px 0; }
    th, td { padding: 8px 12px; text-align: left; border: 1px solid #e5e7eb; }
    th { background: #f3f4f6; font-weight: 600; }
    .pass { color: #15803d; }
    .fail { color: #b91c1c; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
    .badge.pass { background: #dcfce7; color: #15803d; }
    .badge.fail { background: #fee2e2; color: #991b1b; }
    code { background: #f3f4f6; padding: 2px 6px; border-radius: 3px; font-family: 'Consolas', monospace; font-size: 12px; }
    .section { margin: 24px 0; }
    ul { padding-left: 24px; }
  </style>
</head>
<body>
  <h1>${summary.title}</h1>
  <p>生成时间：${new Date(generatedAt).toLocaleString("zh-CN")} ｜ 报告 ID：<code>${reportId}</code></p>

  <div class="summary-card">
    <div class="stat">
      <div class="stat-value">${summary.passed_objectives}/${summary.total_objectives}</div>
      <div class="stat-label">DO-178C 目标通过率</div>
    </div>
    <div class="stat">
      <div class="stat-value">${summary.traceability_entries}</div>
      <div class="stat-label">追溯矩阵条目数</div>
    </div>
    <div class="stat">
      <div class="stat-value">${summary.misra_violations}</div>
      <div class="stat-label">MISRA-C 违规数</div>
    </div>
    <div class="stat">
      <div class="stat-value">${Math.round(summary.pass_rate * 100)}%</div>
      <div class="stat-label">总通过率</div>
    </div>
  </div>

  <h2>1. 执行摘要</h2>
  <p>本报告依据 DO-178C 航空软件适航标准生成，涵盖需求追溯、契约验证、MISRA-C 合规和数字孪生仿真结果。</p>
  <ul>
    <li>组件名：<code>${result.contract.component}</code></li>
    <li>组件描述：${result.contract.description}</li>
    <li>契约校验：<span class="badge ${contractPassed ? "pass" : "fail"}">${result.contract_check_result.passed_count}/${result.contract_check_result.total_count}</span></li>
    <li>数字孪生仿真：<span class="badge ${simPassed ? "pass" : "fail"}">${simPassed ? "通过" : "违约"}</span></li>
    <li>MISRA-C 违规数：${misraCount}</li>
    <li>修复迭代轮数：${result.repair_history.length}</li>
  </ul>

  <h2>2. 需求追溯矩阵</h2>
  <table>
    <thead>
      <tr><th>需求 ID</th><th>关联代码行</th></tr>
    </thead>
    <tbody>
      ${Object.entries(result.traceability)
        .map(
          ([req, lines]) =>
            `<tr><td><code>${req}</code></td><td>${lines.map((l) => `L${l}`).join(", ")}</td></tr>`,
        )
        .join("")}
    </tbody>
  </table>

  <h2>3. 契约校验结果</h2>
  <table>
    <thead>
      <tr><th>条件 ID</th><th>分区</th><th>表达式</th><th>结果</th></tr>
    </thead>
    <tbody>
      ${result.contract_check_result.sections
        .flatMap((s) =>
          s.items.map(
            (it) =>
              `<tr><td><code>${it.id}</code></td><td>${s.title}</td><td><code>${it.expression}</code></td><td><span class="badge ${it.passed ? "pass" : "fail"}">${it.passed ? "通过" : "失败"}</span></td></tr>`,
          ),
        )
        .join("")}
    </tbody>
  </table>

  <h2>4. MISRA-C 合规性</h2>
  <table>
    <thead>
      <tr><th>规则</th><th>类别</th><th>严重性</th><th>位置</th><th>说明</th></tr>
    </thead>
    <tbody>
      ${
        result.violations.length === 0
          ? `<tr><td colspan="5" style="text-align:center;color:#15803d">✅ 无 MISRA 违规</td></tr>`
          : result.violations
              .map(
                (v) =>
                  `<tr><td><code>${v.rule}</code></td><td>${v.category}</td><td>${v.severity}</td><td>${v.file}:${v.line}</td><td>${v.message}</td></tr>`,
              )
              .join("")
      }
    </tbody>
  </table>

  <h2>5. 修复历史</h2>
  <p>共 ${result.repair_history.length} 轮修复，最终违规数为 ${result.repair_history.length > 0 ? result.repair_history[result.repair_history.length - 1].violations_after : 0}。</p>
  <table>
    <thead>
      <tr><th>轮次</th><th>修复前</th><th>修复后</th><th>说明</th></tr>
    </thead>
    <tbody>
      ${result.repair_history
        .map(
          (r) =>
            `<tr><td>第 ${r.round} 轮</td><td>${r.violations_before} 个违规</td><td>${r.violations_after} 个违规</td><td>${r.description}</td></tr>`,
        )
        .join("")}
    </tbody>
  </table>

  <h2>6. 数字孪生仿真</h2>
  <p>仿真步数：${result.simulation_result.total_steps}，故障类型：${result.simulation_result.fault_type ?? "无"}。</p>
  <p>结果：${simPassed ? '<span class="pass">✅ 全部契约断言通过</span>' : '<span class="fail">❌ 存在契约违约</span>'}</p>
  <p>${summary.simulation_summary}</p>

  <h2>7. DO-178C 目标达成情况</h2>
  <p>本报告覆盖 DO-178C Level C 的核心目标：</p>
  <ul>
    <li>需求追溯：${summary.traceability_entries} 个需求条目全部追溯至代码行 ✅</li>
    <li>契约验证：${result.contract_check_result.passed_count}/${result.contract_check_result.total_count} 条契约条件通过 ${contractPassed ? "✅" : "⚠"}</li>
    <li>编码标准：MISRA-C 检查 ${misraCount === 0 ? "✅ 全部通过" : `⚠ ${misraCount} 个违规`}</li>
    <li>仿真验证：${simPassed ? "✅ 仿真无违约" : "❌ 仿真发现违约"}</li>
    <li>修复闭环：${result.repair_history.length} 轮自动修复完成 ✅</li>
  </ul>

  <hr>
  <p style="color: #6b7280; font-size: 12px; margin-top: 32px;">
    本报告由 AirborneAI 系统自动生成 · DO-178C Objectives: ${summary.passed_objectives}/${summary.total_objectives} (${Math.round(summary.pass_rate * 100)}%)
  </p>
</body>
</html>`;

      resolve({
        report_id: reportId,
        html,
        summary,
      });
    }, 1500);
  });
}

/** 预设示例：低通滤波器代码 */
export const PRESET_LP_CODE = MOCK_LP_CODE;
/** 预设示例：低通滤波器契约 */
export const PRESET_LP_CONTRACT = MOCK_LP_CONTRACT;
/** 预设示例：高通滤波器代码 */
export const PRESET_HP_CODE = MOCK_HP_CODE;
/** 预设示例：高通滤波器契约 */
export const PRESET_HP_CONTRACT = MOCK_HP_CONTRACT;

// ===================== Day 5: API 切换层补充类型与 mock 函数 =====================

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

/** mock 的 MISRA 规则库（基于 MISRA_RULE_DOCS 扩展） */
const MOCK_MISRA_RULES: MisraRule[] = [
  {
    rule_id: "MISRA-Rule-8.1",
    title: "显式类型限定符",
    description:
      "All declarations shall be qualified with appropriate type specifiers. 所有声明都应使用恰当的类型限定符显式限定。",
    category: "Required",
    section: "8.1 Declarations",
    bad_example: `static x;  /* 缺少类型限定符 */`,
    good_example: `static int32_t x;  /* 显式 int32_t 类型 */`,
  },
  {
    rule_id: "MISRA-Rule-9.1",
    title: "自动变量初始化",
    description:
      "The value of an object with automatic storage shall not be read before being set. 具有自动存储期的对象在赋值前不应被读取。",
    category: "Mandatory",
    section: "9.1 Initialization",
    bad_example: `uint16_t v;
return v;  /* v 未初始化即被读取 */`,
    good_example: `uint16_t v = 0U;  /* 显式初始化 */
return v;`,
  },
  {
    rule_id: "MISRA-Rule-10.4",
    title: "运算符类型一致性",
    description:
      "Both operands of an operator shall have the same essential type category. 运算符的两个操作数应具有相同的基本类型类别。",
    category: "Required",
    section: "10.4 Expression types",
    bad_example: `uint16_t a = 10;
float b = a + 5;  /* uint16 + int 隐式转换 */`,
    good_example: `uint16_t a = 10U;
float b = (float)a + 5.0f;  /* 显式类型转换 */`,
  },
  {
    rule_id: "MISRA-Rule-8.13",
    title: "只读指针参数",
    description:
      "A pointer parameter in a function prototype should be declared as pointer-to-const if the pointer is not used to modify the addressed object. 函数原型中的指针参数若不修改所指向对象，应声明为指向 const 的指针。",
    category: "Advisory",
    section: "8.13 Pointer parameters",
    bad_example: `float get_value(Filter *f) {
    return f->alpha;  /* f 未被修改 */
}`,
    good_example: `float get_value(const Filter *f) {
    return f->alpha;  /* const 修饰，明确只读 */
}`,
  },
];

/** mock 搜索 MISRA 规则 */
export function mockSearchMisra(query: string): Promise<MisraRule[]> {
  console.log("[mockApi] 调用 mockSearchMisra，查询：", query);
  return new Promise((resolve) => {
    setTimeout(() => {
      const q = query.trim().toLowerCase();
      if (!q) {
        resolve([...MOCK_MISRA_RULES]);
        return;
      }
      const filtered = MOCK_MISRA_RULES.filter(
        (r) =>
          r.rule_id.toLowerCase().includes(q) ||
          r.title.toLowerCase().includes(q) ||
          r.description.toLowerCase().includes(q) ||
          (r.section?.toLowerCase().includes(q) ?? false),
      );
      resolve(filtered);
    }, 300);
  });
}

/** mock 获取单条 MISRA 规则 */
export function mockGetMisraRule(ruleId: string): Promise<MisraRule> {
  console.log("[mockApi] 调用 mockGetMisraRule，ruleId：", ruleId);
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      const rule = MOCK_MISRA_RULES.find((r) => r.rule_id === ruleId);
      if (rule) {
        resolve(rule);
      } else {
        reject(new Error(`未找到规则：${ruleId}`));
      }
    }, 200);
  });
}

/** mock 修复接口 */
export function mockRepair(code: string): Promise<RepairResult> {
  console.log("[mockApi] 调用 mockRepair，代码长度：", code.length);
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        final_code: code,
        repair_history: MOCK_REPAIR_HISTORY,
        final_violations: [],
        contract_check_result: MOCK_CONTRACT_CHECK_RESULT,
      });
    }, 1000);
  });
}

/** mock 契约校验（与代码 + 契约 YAML） */
export function mockCheckContract(
  code: string,
  contract: string,
): Promise<ContractCheckResult> {
  console.log("[mockApi] 调用 mockCheckContract，代码长度：", code.length);
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(MOCK_CONTRACT_CHECK_RESULT);
    }, 600);
  });
}

/** mock 数字孪生仿真（按代码 + 契约触发，兼容真实 API 签名） */
export function mockSimulateByCode(
  code: string,
  contract: string,
  faultType?: string,
  faultParams?: FaultParams,
): Promise<SimulationResult> {
  console.log(
    "[mockApi] 调用 mockSimulateByCode，代码长度：",
    code.length,
    "故障：",
    faultType,
  );
  if (faultType) {
    return mockSimulate(faultType as FaultType, faultParams ?? {});
  }
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(MOCK_SIMULATION_RESULT);
    }, 800);
  });
}

/** mock 获取故障类型列表 */
export function mockGetFaultTypes(): Promise<FaultType[]> {
  console.log("[mockApi] 调用 mockGetFaultTypes");
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(["bias", "signal_loss", "noise", "stuck", "step"]);
    }, 200);
  });
}

/** mock 的 API 基础地址（仅用于 downloadReport 返回 URL） */
const MOCK_API_BASE_URL = "http://localhost:8000";

/** mock 生成报告（接受 pipelineResult 任意对象） */
export function mockGenerateReportByPipeline(
  pipelineResult: any,
): Promise<ReportResult> {
  console.log("[mockApi] 调用 mockGenerateReportByPipeline");
  // 若传入的是 GenerateResult，复用现有 mockGenerateReport
  if (pipelineResult && pipelineResult.contract && pipelineResult.code) {
    return mockGenerateReport(pipelineResult as GenerateResult);
  }
  // 否则用空 GenerateResult 兜底
  return mockGenerateReport({
    contract: MOCK_CONTRACT,
    code: "",
    violations: [],
    traceability: {},
    repair_history: [],
    contract_check_result: MOCK_CONTRACT_CHECK_RESULT,
    simulation_result: MOCK_SIMULATION_RESULT,
  });
}

/** mock 下载报告（返回 URL） */
export function mockDownloadReport(): string {
  return `${MOCK_API_BASE_URL}/api/report/download`;
}