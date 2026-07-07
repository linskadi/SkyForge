/**
 * Mock 数据常量
 * 所有硬编码的 mock 数据集中在此文件，供 mock API 函数层使用
 */

import type {
  AgentLog,
  Contract,
  ContractCheckResult,
  MisraViolation,
  RepairIteration,
  SimulationResult,
  LLMStatus,
  MisraRule,
  HILApproval,
  HILHistoryItem,
} from "@/types/domain";

// ===================== Agent 日志 =====================

/** 模拟的 Agent 思考日志流（参考文档 11.2.1 节时间轴，0-30s 浓缩为 5s） */
export const MOCK_AGENT_LOGS: AgentLog[] = [
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

// ===================== 示例需求 =====================

/** 模拟的示例需求 */
export const EXAMPLE_REQUIREMENTS: string[] = [
  "实现一个低通滤波器，截止频率 10Hz，用于滤除传感器高频噪声",
  "实现一个 PID 控制器，Kp=2.0, Ki=0.5, Kd=0.1，控制无人机俯仰角",
  "实现一个 ARINC 429 字解析函数，将 32 位字解码为标签、SDI、数据",
  "实现一个余度管理器，双通道输入取均值，偏差 > 5% 时报警",
];

// ===================== 契约数据 =====================

/** mock 的契约数据 */
export const MOCK_CONTRACT: Contract = {
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

// ===================== C 代码 =====================

/** mock 的 C 代码（含 [REQ-xxx] 与 [MISRA-Rule-x.x] Tag） */
export const MOCK_CODE = `/**
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

// ===================== MISRA 违规 =====================

/** mock 的 MISRA 违规列表（初始发现，共 4 个；修复历史见 MOCK_REPAIR_HISTORY） */
export const MOCK_VIOLATIONS: MisraViolation[] = [
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

// ===================== 追溯矩阵 =====================

/** mock 的追溯矩阵 */
export const MOCK_TRACEABILITY: Record<string, number[]> = {
  "REQ-001": [11, 16, 18, 23, 27, 38],
  "REQ-002": [23, 28, 29, 33],
};

// ===================== MISRA 规则说明 =====================

/** MISRA 规则说明（用于 tooltip 显示） */
export const MISRA_RULE_DOCS: Record<string, string> = {
  "MISRA-Rule-8.1": "Required: All declarations shall be qualified with appropriate type specifiers.",
  "MISRA-Rule-9.1": "Mandatory: The value of an object with automatic storage shall not be read before being set.",
  "MISRA-Rule-10.4": "Required: Both operands of an operator shall have the same essential type category.",
  "MISRA-Rule-8.13": "Advisory: A pointer parameter in a function prototype should be declared as pointer-to-const if the pointer is not used to modify the addressed object.",
};

// ===================== 修复代码版本 =====================

/** 修复前代码 V0：初始生成，含 4 个违规（Patch 1 查改解耦 - 查） */
export const MOCK_REPAIR_CODE_V0 = `typedef struct {
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
export const MOCK_REPAIR_CODE_V1 = `typedef struct {
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
export const MOCK_REPAIR_CODE_V2 = `typedef struct {
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

// ===================== 修复历史 =====================

/** mock 的修复历史（Patch 1 查改解耦闭环：2 轮修复，4 → 1 → 0） */
export const MOCK_REPAIR_HISTORY: RepairIteration[] = [
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

// ===================== 契约校验结果 =====================

/** mock 的契约校验结果（Patch 2 契约转断言：YAML -> C assert 注入 test_harness） */
export const MOCK_CONTRACT_CHECK_RESULT: ContractCheckResult = {
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

// ===================== 数字孪生仿真数据 =====================

/** 仿真步数 */
export const SIM_STEPS = 200;
/** 一阶 IIR 滤波系数（fc=10Hz, fs=100Hz -> alpha≈0.0909） */
export const FILTER_ALPHA = 0.0909;
/** uint16 中点 */
export const ADC_CENTER = 32768;
/** 正弦波幅度 */
export const SINE_AMP = 20000;

/** 正常仿真日志（无故障，契约全通过） */
export const MOCK_SIM_LOGS: AgentLog[] = [
  { agent: "SYSTEM", level: "info", thought: "$ gcc -fsanitize=address code.c test_harness.c -o sim" },
  { agent: "SYSTEM", level: "success", thought: "编译成功，test_harness.c 已注入 6 条契约断言（Patch 2）" },
  { agent: "SYSTEM", level: "info", thought: "$ ./sim --steps 200 --input sine_10Hz.bin" },
  { agent: "TERMINAL", level: "info", thought: "[sim] step 0: input=32768, output=2982 (初始化瞬态)" },
  { agent: "TERMINAL", level: "info", thought: "[sim] step 50: input=52768, output=51023 (稳态跟踪)" },
  { agent: "TERMINAL", level: "info", thought: "[sim] step 100: input=12768, output=14539 (稳态跟踪)" },
  { agent: "TERMINAL", level: "success", thought: "[sim] 全部 200 步仿真完成，6/6 契约断言通过" },
  { agent: "SYSTEM", level: "success", thought: "✅ 数字孪生仿真通过，契约零违约" },
];

// ===================== LLM 状态 =====================

/** mock LLM 状态 */
export const MOCK_LLM_STATUS: LLMStatus = {
  available: false,
  endpoint: "http://localhost:1234/v1",
  use_llm: false,
  models: [
    {
      id: "google/gemma-4-e4b",
      name: "Gemma 4 E4B",
      size: 4.0,
      context_length: 8192,
      loaded: true,
    },
    {
      id: "qwen/qwen3.5-9b",
      name: "Qwen 3.5 9B",
      size: 6.0,
      context_length: 16384,
      loaded: false,
    },
  ],
  current_model: "google/gemma-4-e4b",
  response_time_ms: 0,
  total_calls: 0,
};

// ===================== 组件组合数据 =====================

/** mock 低通滤波器组件代码 */
export const MOCK_LP_CODE = `/* LowPassFilter.c */
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
export const MOCK_HP_CODE = `/* HighPassFilter.c */
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
export const MOCK_LP_CONTRACT = `component: LowPassFilter
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
export const MOCK_HP_CONTRACT = `component: HighPassFilter
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
export const MOCK_COMPOSED_CODE_SEQUENTIAL = `/* ComposedFilter_Sequential.c */
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
export const MOCK_COMPOSED_CODE_PARALLEL = `/* ComposedFilter_Parallel.c */
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
export const MOCK_COMPOSED_CODE_FEEDBACK = `/* ComposedFilter_Feedback.c */
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

// ===================== MISRA 规则库 =====================

/** mock 的 MISRA 规则库（基于 MISRA_RULE_DOCS 扩展） */
export const MOCK_MISRA_RULES: MisraRule[] = [
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

// ===================== HIL 审批数据 =====================

/** mock HIL 待审批列表 */
export const MOCK_HIL_PENDING: HILApproval[] = [
  {
    request_id: "HIL-REQ-001",
    checkpoint: "requirement_review",
    checkpoint_name: "需求审查",
    content_preview:
      "需求：实现一个低通滤波器，截止频率 10Hz，用于滤除传感器高频噪声。包含 REQ-001, REQ-002 两个需求条目。",
    content_detail:
      "完整需求文档：\n[REQ-001] 截止频率 fc=10Hz\n[REQ-002] 输出范围 [0, 65535]\n[REQ-003] 采样率 fs=100Hz",
    submitted_at: 0, // will be set at runtime
    deadline: 0,
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
    submitted_at: 0,
    deadline: 0,
    status: "pending",
  },
];

// ===================== API 基础地址 =====================

/** mock 的 API 基础地址（仅用于 downloadReport 返回 URL） */
export const MOCK_API_BASE_URL = "http://localhost:8000";
