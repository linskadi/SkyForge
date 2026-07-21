/**
 * 机载常用组件契约模板库
 *
 * 为 Compose.vue 组件组合验证页面提供预置契约模板，支持从模板快速创建组件
 * 并填充到组合验证区域（A / B 槽位）。
 *
 * 设计参考：
 * - 后端 `backend/app/core/composable/compatibility_checker.py` 兼容两种 YAML 布局：
 *   1) 顶层布局（postconditions / preconditions / invariants 在顶层）
 *   2) interface 块布局（interface.inputs[].range / interface.outputs[].range）
 * - 本模板库统一采用带 `interface` 块的布局，便于兼容性检查器提取数值范围
 *   （_extract_input_range / _extract_output_range 优先读取 interface 块）
 * - 模板 C 代码统一保留 `double filter(double input)` 入口，与 component_combinator
 *   的 _rename_filter_def 正则匹配，可直接拖入组合验证区域
 */

/** 模板接口信号（输入/输出）定义 */
export interface ContractTemplateSignal {
	/** 信号名（如 raw_signal / filtered_signal） */
	name: string;
	/** 数据类型（如 float64 / uint16_t） */
	type: string;
	/** 数值范围 [min, max]（用于兼容性检查器提取） */
	range?: [number, number];
	/** 物理单位（如 mV / deg / V / percent） */
	unit?: string;
	/** 信号说明 */
	description?: string;
}

/** 契约条件（前置 / 后置 / 不变式 / 故障处理） */
export interface ContractTemplateCondition {
	/** 条件 ID（如 CON-LP-PRE-000） */
	id: string;
	/** 条件表达式（如 "raw_signal >= -1000.0"） */
	expression: string;
	/** 条件描述 */
	description?: string;
}

/** 契约模板分类 */
export type ContractTemplateCategory =
	| "filter"
	| "controller"
	| "sampler"
	| "limiter"
	| "hmi"
	| "sensor_fusion"
	| "mission_planning"
	| "arinc653"
	| "freertos"
	| "cpp"
	| "rust";

/** 契约模板 */
export interface ContractTemplate {
	/** 模板 ID（唯一标识，如 "lowpass-filter"） */
	id: string;
	/** 组件名（与 YAML 中 component 字段一致，如 LowPassFilter） */
	name: string;
	/** 分类 */
	category: ContractTemplateCategory;
	/** 分类显示名（中文） */
	categoryLabel: string;
	/** 模板描述 */
	description: string;
	/** 安全等级（DAL-A / DAL-B / DAL-C） */
	safetyLevel: string;
	/** 输入信号列表 */
	inputs: ContractTemplateSignal[];
	/** 输出信号列表 */
	outputs: ContractTemplateSignal[];
	/** 前置条件 */
	preconditions: ContractTemplateCondition[];
	/** 后置条件 */
	postconditions: ContractTemplateCondition[];
	/** 不变式 */
	invariants: ContractTemplateCondition[];
	/** 故障处理（可选） */
	faultHandling: ContractTemplateCondition[];
	/** C 代码（必须含 `double filter(double input)` 入口，可被组合器重命名） */
	code: string;
	/** 完整契约 YAML 字符串（直接写入 YAML 编辑器） */
	contractYaml: string;
}

// ====================================================================
// 模板 1：低通滤波器（LowPassFilter）
// ====================================================================
const LOWPASS_FILTER_TEMPLATE: ContractTemplate = {
	id: "lowpass-filter",
	name: "LowPassFilter",
	category: "filter",
	categoryLabel: "滤波器",
	description: "一阶 IIR 低通滤波器，可配置截止频率，用于滤除传感器高频噪声",
	safetyLevel: "DAL-B",
	inputs: [
		{
			name: "raw_signal",
			type: "float64",
			range: [-1000.0, 1000.0],
			unit: "mV",
			description: "原始信号输入",
		},
	],
	outputs: [
		{
			name: "filtered_signal",
			type: "float64",
			range: [-1000.0, 1000.0],
			unit: "mV",
			description: "滤波后信号",
		},
	],
	preconditions: [
		{
			id: "CON-LP-PRE-000",
			expression: "raw_signal >= -1000.0 && raw_signal <= 1000.0",
			description: "输入信号必须在 ADC 量程内",
		},
	],
	postconditions: [
		{
			id: "CON-LP-POST-000",
			expression: "filtered_signal >= -1000.0 && filtered_signal <= 1000.0",
			description: "输出信号保持有界",
		},
	],
	invariants: [
		{
			id: "CON-LP-INV-000",
			expression: "0.0 < cutoff_freq && cutoff_freq <= sample_rate / 2.0",
			description: "截止频率符合奈奎斯特采样定理（fc <= fs/2）",
		},
	],
	faultHandling: [
		{
			id: "CON-LP-FLT-000",
			expression: "if abs(raw_signal) > 1000.0 then hold prev_filtered",
			description: "输入超量程时保持上一拍输出",
		},
	],
	code: `/* LowPassFilter.c — 一阶 IIR 低通滤波器 */
#include <stdint.h>

typedef struct {
    double alpha;
    double prev_out;
    double cutoff_freq;
    double sample_rate;
} LowPassFilter_t;

static LowPassFilter_t g_lp = { 0.0909, 0.0, 10.0, 100.0 };

double filter(double input) {
    double out = g_lp.alpha * input + (1.0 - g_lp.alpha) * g_lp.prev_out;
    if (out < -1000.0) out = -1000.0;
    else if (out > 1000.0) out = 1000.0;
    g_lp.prev_out = out;
    return out;
}
`,
	contractYaml: `component: LowPassFilter
description: 一阶 IIR 低通滤波器，可配置截止频率，用于滤除传感器高频噪声
safety_level: DAL-B
interface:
  inputs:
    - name: raw_signal
      type: float64
      range: [-1000.0, 1000.0]
      unit: mV
      description: 原始信号输入
  outputs:
    - name: filtered_signal
      type: float64
      range: [-1000.0, 1000.0]
      unit: mV
      description: 滤波后信号
preconditions:
  - id: CON-LP-PRE-000
    expression: "raw_signal >= -1000.0 && raw_signal <= 1000.0"
    description: 输入信号必须在 ADC 量程内
postconditions:
  - id: CON-LP-POST-000
    expression: "filtered_signal >= -1000.0 && filtered_signal <= 1000.0"
    description: 输出信号保持有界
invariants:
  - id: CON-LP-INV-000
    expression: "0.0 < cutoff_freq && cutoff_freq <= sample_rate / 2.0"
    description: 截止频率符合奈奎斯特采样定理（fc <= fs/2）
fault_handling:
  - id: CON-LP-FLT-000
    expression: "if abs(raw_signal) > 1000.0 then hold prev_filtered"
    description: 输入超量程时保持上一拍输出
`,
};

// ====================================================================
// 模板 2：PID 控制器（PIDController）
// ====================================================================
const PID_CONTROLLER_TEMPLATE: ContractTemplate = {
	id: "pid-controller",
	name: "PIDController",
	category: "controller",
	categoryLabel: "控制器",
	description: "增量式 PID 控制器，含积分抗饱和与输出限幅，适用于俯仰角控制",
	safetyLevel: "DAL-A",
	inputs: [
		{
			name: "setpoint",
			type: "float64",
			range: [-1000.0, 1000.0],
			unit: "deg",
			description: "期望设定值",
		},
		{
			name: "measured",
			type: "float64",
			range: [-1000.0, 1000.0],
			unit: "deg",
			description: "实际测量值",
		},
	],
	outputs: [
		{
			name: "control_output",
			type: "float64",
			range: [-100.0, 100.0],
			unit: "percent",
			description: "控制输出（百分比，限幅 ±100%）",
		},
	],
	preconditions: [
		{
			id: "CON-PID-PRE-000",
			expression: "setpoint >= -1000.0 && setpoint <= 1000.0",
			description: "设定值在有效量程内",
		},
		{
			id: "CON-PID-PRE-001",
			expression: "measured >= -1000.0 && measured <= 1000.0",
			description: "测量值在有效量程内",
		},
	],
	postconditions: [
		{
			id: "CON-PID-POST-000",
			expression: "control_output >= -100.0 && control_output <= 100.0",
			description: "控制输出限幅在 [-100%, 100%]",
		},
	],
	invariants: [
		{
			id: "CON-PID-INV-000",
			expression: "abs(integral) <= 1000.0",
			description: "积分项抗饱和（|integral| <= 1000）",
		},
	],
	faultHandling: [
		{
			id: "CON-PID-FLT-000",
			expression: "if measured is NaN then control_output = 0.0",
			description: "测量值异常（NaN）时输出归零",
		},
	],
	code: `/* PIDController.c — 增量式 PID 控制器，含抗饱和与限幅 */
#include <stdint.h>
#include <math.h>

typedef struct {
    double kp, ki, kd;
    double integral;
    double prev_error;
    double out_min, out_max;
} PIDController_t;

static PIDController_t g_pid = { 2.0, 0.5, 0.1, 0.0, 0.0, -100.0, 100.0 };

double filter(double input) {
    /* input 视为误差信号 = setpoint - measured（单输入接口版本） */
    double error = input;
    g_pid.integral += error;
    if (g_pid.integral > 1000.0) g_pid.integral = 1000.0;
    else if (g_pid.integral < -1000.0) g_pid.integral = -1000.0;
    double derivative = error - g_pid.prev_error;
    double out = g_pid.kp * error + g_pid.ki * g_pid.integral + g_pid.kd * derivative;
    if (out < g_pid.out_min) out = g_pid.out_min;
    else if (out > g_pid.out_max) out = g_pid.out_max;
    g_pid.prev_error = error;
    return out;
}
`,
	contractYaml: `component: PIDController
description: 增量式 PID 控制器，含积分抗饱和与输出限幅
safety_level: DAL-A
interface:
  inputs:
    - name: setpoint
      type: float64
      range: [-1000.0, 1000.0]
      unit: deg
      description: 期望设定值
    - name: measured
      type: float64
      range: [-1000.0, 1000.0]
      unit: deg
      description: 实际测量值
  outputs:
    - name: control_output
      type: float64
      range: [-100.0, 100.0]
      unit: percent
      description: 控制输出（百分比，限幅 ±100%）
preconditions:
  - id: CON-PID-PRE-000
    expression: "setpoint >= -1000.0 && setpoint <= 1000.0"
    description: 设定值在有效量程内
  - id: CON-PID-PRE-001
    expression: "measured >= -1000.0 && measured <= 1000.0"
    description: 测量值在有效量程内
postconditions:
  - id: CON-PID-POST-000
    expression: "control_output >= -100.0 && control_output <= 100.0"
    description: 控制输出限幅在 [-100%, 100%]
invariants:
  - id: CON-PID-INV-000
    expression: "abs(integral) <= 1000.0"
    description: 积分项抗饱和（|integral| <= 1000）
fault_handling:
  - id: CON-PID-FLT-000
    expression: "if measured is NaN then control_output = 0.0"
    description: 测量值异常（NaN）时输出归零
`,
};

// ====================================================================
// 模板 3：传感器采样器（SensorSampler）
// ====================================================================
const SENSOR_SAMPLER_TEMPLATE: ContractTemplate = {
	id: "sensor-sampler",
	name: "SensorSampler",
	category: "sampler",
	categoryLabel: "采样器",
	description: "模拟传感器周期采样与 12-bit ADC 量化，含采样率约束",
	safetyLevel: "DAL-B",
	inputs: [
		{
			name: "analog_signal",
			type: "float64",
			range: [0.0, 5.0],
			unit: "V",
			description: "模拟电压信号输入",
		},
	],
	outputs: [
		{
			name: "sampled_value",
			type: "float64",
			range: [0.0, 5.0],
			unit: "V",
			description: "采样量化值",
		},
	],
	preconditions: [
		{
			id: "CON-SS-PRE-000",
			expression: "analog_signal >= 0.0 && analog_signal <= 5.0",
			description: "模拟信号在 ADC 输入量程 [0V, 5V] 内",
		},
	],
	postconditions: [
		{
			id: "CON-SS-POST-000",
			expression: "sampled_value >= 0.0 && sampled_value <= 5.0",
			description: "采样值在 ADC 量程内",
		},
	],
	invariants: [
		{
			id: "CON-SS-INV-000",
			expression: "sample_rate_hz > 0 && sample_rate_hz <= 10000",
			description: "采样率约束在 (0, 10kHz]（符合传感器规格）",
		},
	],
	faultHandling: [
		{
			id: "CON-SS-FLT-000",
			expression: "if analog_signal < 0.0 then sampled_value = 0.0",
			description: "输入负电压时输出归零（保护 ADC）",
		},
	],
	code: `/* SensorSampler.c — 周期采样 + 12-bit ADC 量化 */
#include <stdint.h>

typedef struct {
    double last_sample;
    uint32_t sample_counter;
    uint32_t sample_rate_hz;
} SensorSampler_t;

static SensorSampler_t g_sampler = { 0.0, 0, 100 };

double filter(double input) {
    /* 12-bit ADC 量化：分辨率 = 5.0V / 4095 */
    const double adc_res = 5.0 / 4095.0;
    double quantized = ((int64_t)(input / adc_res)) * adc_res;
    if (quantized < 0.0) quantized = 0.0;
    else if (quantized > 5.0) quantized = 5.0;
    g_sampler.last_sample = quantized;
    g_sampler.sample_counter++;
    return quantized;
}
`,
	contractYaml: `component: SensorSampler
description: 模拟传感器周期采样与 12-bit ADC 量化
safety_level: DAL-B
interface:
  inputs:
    - name: analog_signal
      type: float64
      range: [0.0, 5.0]
      unit: V
      description: 模拟电压信号输入
  outputs:
    - name: sampled_value
      type: float64
      range: [0.0, 5.0]
      unit: V
      description: 采样量化值
preconditions:
  - id: CON-SS-PRE-000
    expression: "analog_signal >= 0.0 && analog_signal <= 5.0"
    description: 模拟信号在 ADC 输入量程 [0V, 5V] 内
postconditions:
  - id: CON-SS-POST-000
    expression: "sampled_value >= 0.0 && sampled_value <= 5.0"
    description: 采样值在 ADC 量程内
invariants:
  - id: CON-SS-INV-000
    expression: "sample_rate_hz > 0 && sample_rate_hz <= 10000"
    description: 采样率约束在 (0, 10kHz]
fault_handling:
  - id: CON-SS-FLT-000
    expression: "if analog_signal < 0.0 then sampled_value = 0.0"
    description: 输入负电压时输出归零（保护 ADC）
`,
};

// ====================================================================
// 模板 4：限幅器（Limiter）
// ====================================================================
const LIMITER_TEMPLATE: ContractTemplate = {
	id: "limiter",
	name: "Limiter",
	category: "limiter",
	categoryLabel: "限幅器",
	description: "上下限限幅器，将输入值钳位到 [lower_limit, upper_limit] 区间",
	safetyLevel: "DAL-A",
	inputs: [
		{
			name: "value",
			type: "float64",
			range: [-1e9, 1e9],
			unit: "dimensionless",
			description: "待限幅的输入值",
		},
	],
	outputs: [
		{
			name: "clamped_value",
			type: "float64",
			range: [-100.0, 100.0],
			unit: "dimensionless",
			description: "限幅后的输出值",
		},
	],
	preconditions: [
		{
			id: "CON-LIM-PRE-000",
			expression: "lower_limit < upper_limit",
			description: "下限必须严格小于上限",
		},
	],
	postconditions: [
		{
			id: "CON-LIM-POST-000",
			expression:
				"clamped_value >= lower_limit && clamped_value <= upper_limit",
			description: "输出值严格位于 [lower_limit, upper_limit] 区间内",
		},
	],
	invariants: [
		{
			id: "CON-LIM-INV-000",
			expression: "lower_limit == -100.0 && upper_limit == 100.0",
			description: "默认限幅范围为 [-100, 100]",
		},
	],
	faultHandling: [
		{
			id: "CON-LIM-FLT-000",
			expression: "if value is NaN then clamped_value = lower_limit",
			description: "输入 NaN 时输出下限",
		},
	],
	code: `/* Limiter.c — 上下限限幅器 */
#include <stdint.h>
#include <math.h>

typedef struct {
    double lower_limit;
    double upper_limit;
} Limiter_t;

static Limiter_t g_limiter = { -100.0, 100.0 };

double filter(double input) {
    if (isnan(input)) return g_limiter.lower_limit;
    if (input < g_limiter.lower_limit) return g_limiter.lower_limit;
    if (input > g_limiter.upper_limit) return g_limiter.upper_limit;
    return input;
}
`,
	contractYaml: `component: Limiter
description: 上下限限幅器，将输入值钳位到 [lower_limit, upper_limit] 区间
safety_level: DAL-A
interface:
  inputs:
    - name: value
      type: float64
      range: [-1e9, 1e9]
      unit: dimensionless
      description: 待限幅的输入值
  outputs:
    - name: clamped_value
      type: float64
      range: [-100.0, 100.0]
      unit: dimensionless
      description: 限幅后的输出值
preconditions:
  - id: CON-LIM-PRE-000
    expression: "lower_limit < upper_limit"
    description: 下限必须严格小于上限
postconditions:
  - id: CON-LIM-POST-000
    expression: "clamped_value >= lower_limit && clamped_value <= upper_limit"
    description: 输出值位于 [lower_limit, upper_limit] 区间内
invariants:
  - id: CON-LIM-INV-000
    expression: "lower_limit == -100.0 && upper_limit == 100.0"
    description: 默认限幅范围为 [-100, 100]
fault_handling:
  - id: CON-LIM-FLT-000
    expression: "if value is NaN then clamped_value = lower_limit"
    description: 输入 NaN 时输出下限
`,
};

// ====================================================================
// 模板 5：HMI 显示叠加（HmiOverlay）
// ====================================================================
const HMI_OVERLAY_TEMPLATE: ContractTemplate = {
	id: "hmi-overlay",
	name: "HmiOverlay",
	category: "hmi",
	categoryLabel: "人机界面",
	description: "HUD 显示叠加组件，管理多个显示项的注册、值更新与告警等级计算",
	safetyLevel: "DAL-B",
	inputs: [
		{
			name: "display_value",
			type: "float64",
			range: [-1e6, 1e6],
			unit: "dimensionless",
			description: "显示项当前值",
		},
		{
			name: "item_id",
			type: "uint8_t",
			range: [0, 255],
			description: "显示项唯一标识",
		},
	],
	outputs: [
		{
			name: "warn_level",
			type: "uint8_t",
			range: [0, 3],
			description: "告警等级: 0=正常, 1=注意, 2=警告, 3=危急",
		},
		{
			name: "clamped_value",
			type: "float64",
			range: [-1e6, 1e6],
			unit: "dimensionless",
			description: "量程范围内的显示值",
		},
	],
	preconditions: [
		{
			id: "CON-HMI-PRE-000",
			expression: "item_id >= 0 && item_id <= 255",
			description: "显示项 ID 在有效范围内",
		},
		{
			id: "CON-HMI-PRE-001",
			expression: "min_val < max_val",
			description: "量程下限必须严格小于上限",
		},
	],
	postconditions: [
		{
			id: "CON-HMI-POST-000",
			expression: "warn_level >= 0 && warn_level <= 3",
			description: "告警等级在 [0, 3] 范围内",
		},
	],
	invariants: [
		{
			id: "CON-HMI-INV-000",
			expression: "max_display_items <= 12",
			description: "最大显示项数量不超过 12（安全约束）",
		},
	],
	faultHandling: [
		{
			id: "CON-HMI-FLT-000",
			expression:
				"if display_value < min_val or display_value > max_val then warn_level = 3",
			description: "输入超量程时告警等级设为危急",
		},
		{
			id: "CON-HMI-FLT-001",
			expression: "if item_id not registered then return error",
			description: "未注册的显示项 ID 返回错误",
		},
	],
	code: `/* HmiOverlay.c — HUD 显示叠加组件 */
#include <stdint.h>
#include <string.h>

#define MAX_DISPLAY_ITEMS 12

typedef struct {
    uint8_t  id;
    uint8_t  visible;
    uint8_t  priority;
    double   value;
    double   min_val;
    double   max_val;
    uint8_t  warn_level;
} HmiDisplayItem_t;

static HmiDisplayItem_t g_items[MAX_DISPLAY_ITEMS];
static uint8_t g_item_count = 0;

double filter(double input) {
    /* 简化版：输入值直接钳位到默认范围 [-1000, 1000] 并计算告警 */
    double min_val = -1000.0, max_val = 1000.0;
    double clamped = input;
    uint8_t warn = 0;
    if (clamped < min_val || clamped > max_val) {
        warn = 3;
    } else {
        double range = max_val - min_val;
        if (clamped < min_val + 0.1 * range || clamped > max_val - 0.1 * range) {
            warn = 2;
        }
    }
    return (double)warn;
}
`,
	contractYaml: `component: HmiOverlay
description: HUD 显示叠加组件，管理多个显示项的注册、值更新与告警等级计算
safety_level: DAL-B
interface:
  inputs:
    - name: display_value
      type: float64
      range: [-1e6, 1e6]
      unit: dimensionless
      description: 显示项当前值
    - name: item_id
      type: uint8_t
      range: [0, 255]
      description: 显示项唯一标识
  outputs:
    - name: warn_level
      type: uint8_t
      range: [0, 3]
      description: "告警等级: 0=正常, 1=注意, 2=警告, 3=危急"
    - name: clamped_value
      type: float64
      range: [-1e6, 1e6]
      unit: dimensionless
      description: 量程范围内的显示值
preconditions:
  - id: CON-HMI-PRE-000
    expression: "item_id >= 0 && item_id <= 255"
    description: 显示项 ID 在有效范围内
  - id: CON-HMI-PRE-001
    expression: "min_val < max_val"
    description: 量程下限必须严格小于上限
postconditions:
  - id: CON-HMI-POST-000
    expression: "warn_level >= 0 && warn_level <= 3"
    description: 告警等级在 [0, 3] 范围内
invariants:
  - id: CON-HMI-INV-000
    expression: "max_display_items <= 12"
    description: 最大显示项数量不超过 12（安全约束）
fault_handling:
  - id: CON-HMI-FLT-000
    expression: "if display_value < min_val or display_value > max_val then warn_level = 3"
    description: 输入超量程时告警等级设为危急
  - id: CON-HMI-FLT-001
    expression: "if item_id not registered then return error"
    description: 未注册的显示项 ID 返回错误
`,
};

// ====================================================================
// 模板 6：传感器融合卡尔曼滤波（SensorFusionKalman）
// ====================================================================
const SENSOR_FUSION_TEMPLATE: ContractTemplate = {
	id: "sensor-fusion-kalman",
	name: "SensorFusionKalman",
	category: "sensor_fusion",
	categoryLabel: "传感器融合",
	description:
		"扩展卡尔曼滤波器，融合 IMU 加速度计与 GPS 位置数据，输出最优状态估计",
	safetyLevel: "DAL-A",
	inputs: [
		{
			name: "imu_accel",
			type: "float64",
			range: [-50.0, 50.0],
			unit: "m/s2",
			description: "IMU 加速度计读数",
		},
		{
			name: "gps_position",
			type: "float64",
			range: [-1e7, 1e7],
			unit: "m",
			description: "GPS 位置观测值",
		},
	],
	outputs: [
		{
			name: "fused_position",
			type: "float64",
			range: [-1e7, 1e7],
			unit: "m",
			description: "融合后的位置估计",
		},
		{
			name: "estimation_variance",
			type: "float64",
			range: [0.0, 1e6],
			unit: "m2",
			description: "估计方差（不确定度）",
		},
	],
	preconditions: [
		{
			id: "CON-SF-PRE-000",
			expression: "imu_accel >= -50.0 && imu_accel <= 50.0",
			description: "IMU 加速度在传感器量程内",
		},
		{
			id: "CON-SF-PRE-001",
			expression: "dt_sec > 0.0 && dt_sec <= 0.1",
			description: "采样周期在有效范围内 (0, 100ms]",
		},
	],
	postconditions: [
		{
			id: "CON-SF-POST-000",
			expression: "estimation_variance >= 0.0",
			description: "估计方差保持非负",
		},
		{
			id: "CON-SF-POST-001",
			expression: "kalman_gain >= 0.0 && kalman_gain <= 1.0",
			description: "卡尔曼增益在 [0, 1] 范围内",
		},
	],
	invariants: [
		{
			id: "CON-SF-INV-000",
			expression: "process_noise > 0.0 && measurement_noise > 0.0",
			description: "噪声参数必须为正数",
		},
	],
	faultHandling: [
		{
			id: "CON-SF-FLT-000",
			expression: "if gps_signal_lost then only_predict_step",
			description: "GPS 丢失时仅执行预测步骤（惯性保持）",
		},
		{
			id: "CON-SF-FLT-001",
			expression:
				"if estimation_variance > threshold then trigger_degraded_mode",
			description: "估计方差超阈值时触发传感器降级",
		},
	],
	code: `/* SensorFusionKalman.c — 扩展卡尔曼滤波器 IMU/GPS 融合 */
#include <math.h>

typedef struct {
    double state;
    double variance;
    double velocity;
    double process_q;
    double measure_r;
    double dt;
} KalmanFilter_t;

static KalmanFilter_t g_kf = { 0.0, 1.0, 0.0, 0.01, 0.1, 0.01 };

double filter(double input) {
    /* 简化版：input 视为 GPS 观测值，状态估计 = 卡尔曼增益 * input */
    double kalman_gain = g_kf.variance / (g_kf.variance + g_kf.measure_r);
    double innovation = input - g_kf.state;
    g_kf.state += kalman_gain * innovation;
    g_kf.variance = (1.0 - kalman_gain) * g_kf.variance;
    g_kf.variance += g_kf.process_q;
    if (g_kf.variance < 0.0) g_kf.variance = 0.0;
    return g_kf.state;
}
`,
	contractYaml: `component: SensorFusionKalman
description: 扩展卡尔曼滤波器，融合 IMU 加速度计与 GPS 位置数据
safety_level: DAL-A
interface:
  inputs:
    - name: imu_accel
      type: float64
      range: [-50.0, 50.0]
      unit: m/s2
      description: IMU 加速度计读数
    - name: gps_position
      type: float64
      range: [-1e7, 1e7]
      unit: m
      description: GPS 位置观测值
  outputs:
    - name: fused_position
      type: float64
      range: [-1e7, 1e7]
      unit: m
      description: 融合后的位置估计
    - name: estimation_variance
      type: float64
      range: [0.0, 1e6]
      unit: m2
      description: 估计方差（不确定度）
preconditions:
  - id: CON-SF-PRE-000
    expression: "imu_accel >= -50.0 && imu_accel <= 50.0"
    description: IMU 加速度在传感器量程内
  - id: CON-SF-PRE-001
    expression: "dt_sec > 0.0 && dt_sec <= 0.1"
    description: 采样周期在有效范围内 (0, 100ms]
postconditions:
  - id: CON-SF-POST-000
    expression: "estimation_variance >= 0.0"
    description: 估计方差保持非负
  - id: CON-SF-POST-001
    expression: "kalman_gain >= 0.0 && kalman_gain <= 1.0"
    description: 卡尔曼增益在 [0, 1] 范围内
invariants:
  - id: CON-SF-INV-000
    expression: "process_noise > 0.0 && measurement_noise > 0.0"
    description: 噪声参数必须为正数
fault_handling:
  - id: CON-SF-FLT-000
    expression: "if gps_signal_lost then only_predict_step"
    description: GPS 丢失时仅执行预测步骤（惯性保持）
  - id: CON-SF-FLT-001
    expression: "if estimation_variance > threshold then trigger_degraded_mode"
    description: 估计方差超阈值时触发传感器降级
`,
};

// ====================================================================
// 模板 7：任务规划航点管理（MissionPlanner）
// ====================================================================
const MISSION_PLANNER_TEMPLATE: ContractTemplate = {
	id: "mission-planner",
	name: "MissionPlanner",
	category: "mission_planning",
	categoryLabel: "任务规划",
	description:
		"航点列表管理与任务状态机，支持 Haversine 距离判定与任务暂停/恢复/中止",
	safetyLevel: "DAL-B",
	inputs: [
		{
			name: "current_lat",
			type: "float64",
			range: [-90.0, 90.0],
			unit: "deg",
			description: "当前纬度 (WGS-84)",
		},
		{
			name: "current_lon",
			type: "float64",
			range: [-180.0, 180.0],
			unit: "deg",
			description: "当前经度 (WGS-84)",
		},
		{
			name: "current_alt",
			type: "float64",
			range: [0.0, 50000.0],
			unit: "m",
			description: "当前高度 (MSL)",
		},
	],
	outputs: [
		{
			name: "mission_state",
			type: "uint8_t",
			range: [0, 5],
			description: "任务状态: 0=空闲, 1=解锁, 2=执行, 3=暂停, 4=完成, 5=中止",
		},
		{
			name: "current_waypoint",
			type: "uint8_t",
			range: [0, 32],
			description: "当前航点索引",
		},
		{
			name: "arrival_flag",
			type: "uint8_t",
			range: [0, 1],
			description: "航点到达标志: 0=未到达, 1=已到达",
		},
	],
	preconditions: [
		{
			id: "CON-MP-PRE-000",
			expression: "current_lat >= -90.0 && current_lat <= 90.0",
			description: "纬度在有效范围内",
		},
		{
			id: "CON-MP-PRE-001",
			expression: "current_lon >= -180.0 && current_lon <= 180.0",
			description: "经度在有效范围内",
		},
	],
	postconditions: [
		{
			id: "CON-MP-POST-000",
			expression: "mission_state >= 0 && mission_state <= 5",
			description: "任务状态在有效枚举范围内",
		},
		{
			id: "CON-MP-POST-001",
			expression: "current_waypoint < max_waypoints",
			description: "当前航点索引不越界",
		},
	],
	invariants: [
		{
			id: "CON-MP-INV-000",
			expression: "max_waypoints <= 32",
			description: "最大航点数不超过 32（内存安全）",
		},
		{
			id: "CON-MP-INV-001",
			expression: "arrival_radius_m > 0.0",
			description: "到达半径必须为正数",
		},
	],
	faultHandling: [
		{
			id: "CON-MP-FLT-000",
			expression: "if wp_count == 0 then reject start command",
			description: "空航点列表禁止启动任务",
		},
		{
			id: "CON-MP-FLT-001",
			expression: "if mission_state == ABORTED then require reload",
			description: "中止后需重新加载航点列表",
		},
	],
	code: `/* MissionPlanner.c — 航点管理与任务状态机 */
#include <stdint.h>
#include <math.h>

#define MAX_WAYPOINTS 32
#define ARRIVAL_RADIUS_M 5.0

typedef struct {
    double latitude;
    double longitude;
    double altitude;
    double speed;
    uint8_t action;
} Waypoint_t;

typedef enum {
    MISSION_IDLE = 0,
    MISSION_ARMED = 1,
    MISSION_ACTIVE = 2,
    MISSION_PAUSED = 3,
    MISSION_COMPLETE = 4,
    MISSION_ABORTED = 5
} MissionState_t;

static Waypoint_t g_waypoints[MAX_WAYPOINTS];
static uint8_t g_wp_count = 0;
static uint8_t g_current_wp = 0;
static MissionState_t g_state = MISSION_IDLE;

double filter(double input) {
    /* 简化版：input 视为当前纬度，返回状态机状态值 */
    return (double)g_state;
}
`,
	contractYaml: `component: MissionPlanner
description: 航点列表管理与任务状态机，支持 Haversine 距离判定
safety_level: DAL-B
interface:
  inputs:
    - name: current_lat
      type: float64
      range: [-90.0, 90.0]
      unit: deg
      description: 当前纬度 (WGS-84)
    - name: current_lon
      type: float64
      range: [-180.0, 180.0]
      unit: deg
      description: 当前经度 (WGS-84)
    - name: current_alt
      type: float64
      range: [0.0, 50000.0]
      unit: m
      description: 当前高度 (MSL)
  outputs:
    - name: mission_state
      type: uint8_t
      range: [0, 5]
      description: "任务状态: 0=空闲, 1=解锁, 2=执行, 3=暂停, 4=完成, 5=中止"
    - name: current_waypoint
      type: uint8_t
      range: [0, 32]
      description: 当前航点索引
    - name: arrival_flag
      type: uint8_t
      range: [0, 1]
      description: "航点到达标志: 0=未到达, 1=已到达"
preconditions:
  - id: CON-MP-PRE-000
    expression: "current_lat >= -90.0 && current_lat <= 90.0"
    description: 纬度在有效范围内
  - id: CON-MP-PRE-001
    expression: "current_lon >= -180.0 && current_lon <= 180.0"
    description: 经度在有效范围内
postconditions:
  - id: CON-MP-POST-000
    expression: "mission_state >= 0 && mission_state <= 5"
    description: 任务状态在有效枚举范围内
  - id: CON-MP-POST-001
    expression: "current_waypoint < max_waypoints"
    description: 当前航点索引不越界
invariants:
  - id: CON-MP-INV-000
    expression: "max_waypoints <= 32"
    description: 最大航点数不超过 32（内存安全）
  - id: CON-MP-INV-001
    expression: "arrival_radius_m > 0.0"
    description: 到达半径必须为正数
fault_handling:
  - id: CON-MP-FLT-000
    expression: "if wp_count == 0 then reject start command"
    description: 空航点列表禁止启动任务
  - id: CON-MP-FLT-001
    expression: "if mission_state == ABORTED then require reload"
    description: 中止后需重新加载航点列表
`,
};

// ====================================================================
// 模板 8：ARINC 653 分区操作系统（Arinc653Partition）
// ====================================================================
const ARINC653_PARTITION_TEMPLATE: ContractTemplate = {
	id: "arinc653-partition",
	name: "Arinc653Partition",
	category: "arinc653",
	categoryLabel: "航空分区",
	description:
		"ARINC 653 分区操作系统，支持空间/时间隔离、分区间通信与健康监控",
	safetyLevel: "DAL-A",
	inputs: [
		{
			name: "partition_id",
			type: "uint8_t",
			range: [0, 3],
			description: "分区标识",
		},
		{
			name: "command",
			type: "uint8_t",
			range: [0, 5],
			description:
				"控制命令: 0=创建分区, 1=创建端口, 2=启动调度, 3=健康监控, 4=查询状态, 5=停止",
		},
	],
	outputs: [
		{
			name: "partition_state",
			type: "uint8_t",
			range: [0, 4],
			description: "分区状态: 0=空闲, 1=运行, 2=阻塞, 3=错误, 4=终止",
		},
		{
			name: "result_code",
			type: "uint8_t",
			range: [0, 2],
			description: "操作结果: 0=成功, 1=参数错误, 2=资源不足",
		},
	],
	preconditions: [
		{
			id: "CON-A653-PRE-000",
			expression: "partition_id >= 0 && partition_id <= 3",
			description: "分区 ID 在有效范围内 [0, 3]",
		},
		{
			id: "CON-A653-PRE-001",
			expression: "command >= 0 && command <= 5",
			description: "命令码在有效枚举范围内",
		},
	],
	postconditions: [
		{
			id: "CON-A653-POST-000",
			expression: "partition_state >= 0 && partition_state <= 4",
			description: "分区状态在有效枚举范围内",
		},
		{
			id: "CON-A653-POST-001",
			expression: "result_code >= 0 && result_code <= 2",
			description: "结果码在有效范围内",
		},
	],
	invariants: [
		{
			id: "CON-A653-INV-000",
			expression: "major_frame_ms >= 10 && major_frame_ms <= 1000",
			description: "主帧周期在 [10ms, 1000ms] 范围内",
		},
		{
			id: "CON-A653-INV-001",
			expression: "num_partitions <= 4",
			description: "最大分区数不超过 4（内存安全）",
		},
	],
	faultHandling: [
		{
			id: "CON-A653-FLT-000",
			expression: "if partition_state == ERROR then trigger_health_monitor",
			description: "分区错误时触发健康监控",
		},
		{
			id: "CON-A653-FLT-001",
			expression: "if process_timeout then restart_process",
			description: "进程超时自动重启",
		},
		{
			id: "CON-A653-FLT-002",
			expression: "if partition_fatal then shutdown_partition",
			description: "分区致命错误时关闭分区",
		},
	],
	code: `/* Arinc653Partition.c — ARINC 653 分区操作系统 */
#include <stdint.h>
#include <string.h>

#define A653_MAX_PARTITIONS 4
#define A653_MAJOR_FRAME_MS 100
#define A653_MINOR_FRAME_MS 10

typedef enum {
    PARTITION_IDLE = 0, PARTITION_RUNNABLE = 1,
    PARTITION_BLOCKED = 2, PARTITION_ERROR = 3, PARTITION_TERMINATED = 4
} A653PartitionState_t;

typedef struct {
    uint8_t partition_id;
    A653PartitionState_t state;
    uint32_t period_ms;
    uint32_t duration_ms;
} A653Partition_t;

static A653Partition_t g_partitions[A653_MAX_PARTITIONS];
static uint8_t g_part_count = 0;
static uint32_t g_tick_ms = 0;

double filter(double input) {
    /* 简化版：input 视为分区 ID，返回分区状态 */
    uint8_t idx = (uint8_t)((int)input);
    if (idx < g_part_count) {
        return (double)g_partitions[idx].state;
    }
    return 0.0;
}
`,
	contractYaml: `component: Arinc653Partition
description: ARINC 653 分区操作系统，支持空间/时间隔离、分区间通信与健康监控
safety_level: DAL-A
interface:
  inputs:
    - name: partition_id
      type: uint8_t
      range: [0, 3]
      description: 分区标识
    - name: command
      type: uint8_t
      range: [0, 5]
      description: "控制命令: 0=创建分区, 1=创建端口, 2=启动调度, 3=健康监控, 4=查询状态, 5=停止"
  outputs:
    - name: partition_state
      type: uint8_t
      range: [0, 4]
      description: "分区状态: 0=空闲, 1=运行, 2=阻塞, 3=错误, 4=终止"
    - name: result_code
      type: uint8_t
      range: [0, 2]
      description: "操作结果: 0=成功, 1=参数错误, 2=资源不足"
preconditions:
  - id: CON-A653-PRE-000
    expression: "partition_id >= 0 && partition_id <= 3"
    description: 分区 ID 在有效范围内 [0, 3]
  - id: CON-A653-PRE-001
    expression: "command >= 0 && command <= 5"
    description: 命令码在有效枚举范围内
postconditions:
  - id: CON-A653-POST-000
    expression: "partition_state >= 0 && partition_state <= 4"
    description: 分区状态在有效枚举范围内
  - id: CON-A653-POST-001
    expression: "result_code >= 0 && result_code <= 2"
    description: 结果码在有效范围内
invariants:
  - id: CON-A653-INV-000
    expression: "major_frame_ms >= 10 && major_frame_ms <= 1000"
    description: 主帧周期在 [10ms, 1000ms] 范围内
  - id: CON-A653-INV-001
    expression: "num_partitions <= 4"
    description: 最大分区数不超过 4（内存安全）
fault_handling:
  - id: CON-A653-FLT-000
    expression: "if partition_state == ERROR then trigger_health_monitor"
    description: 分区错误时触发健康监控
  - id: CON-A653-FLT-001
    expression: "if process_timeout then restart_process"
    description: 进程超时自动重启
  - id: CON-A653-FLT-002
    expression: "if partition_fatal then shutdown_partition"
    description: 分区致命错误时关闭分区
`,
};

// ====================================================================
// 模板 9：FreeRTOS 任务调度器（FreeRTOSScheduler）
// ====================================================================
const FREERTOS_SCHEDULER_TEMPLATE: ContractTemplate = {
	id: "freertos-scheduler",
	name: "FreeRTOSScheduler",
	category: "freertos",
	categoryLabel: "实时调度",
	description:
		"FreeRTOS 任务调度器，支持多级优先级、信号量/互斥锁同步、队列通信与软件定时器",
	safetyLevel: "DAL-B",
	inputs: [
		{
			name: "task_id",
			type: "uint8_t",
			range: [0, 255],
			description: "任务标识",
		},
		{
			name: "command",
			type: "uint8_t",
			range: [0, 8],
			description:
				"控制命令: 0=创建任务, 1=删除, 2=挂起, 3=恢复, 4=获取信号量, 5=释放, 6=队列发送, 7=队列接收, 8=定时器控制",
		},
	],
	outputs: [
		{
			name: "task_state",
			type: "uint8_t",
			range: [0, 4],
			description: "任务状态: 0=删除, 1=就绪, 2=运行, 3=阻塞, 4=挂起",
		},
		{
			name: "result_code",
			type: "uint8_t",
			range: [0, 3],
			description: "操作结果: 0=成功, 1=资源不足, 2=超时, 3=参数错误",
		},
	],
	preconditions: [
		{
			id: "CON-FRTOS-PRE-000",
			expression: "task_id >= 0 && task_id <= 255",
			description: "任务 ID 在有效范围内",
		},
		{
			id: "CON-FRTOS-PRE-001",
			expression: "command >= 0 && command <= 8",
			description: "命令码在有效枚举范围内",
		},
	],
	postconditions: [
		{
			id: "CON-FRTOS-POST-000",
			expression: "task_state >= 0 && task_state <= 4",
			description: "任务状态在有效枚举范围内",
		},
		{
			id: "CON-FRTOS-POST-001",
			expression: "result_code >= 0 && result_code <= 3",
			description: "结果码在有效范围内",
		},
	],
	invariants: [
		{
			id: "CON-FRTOS-INV-000",
			expression: "tick_rate_hz >= 100 && tick_rate_hz <= 10000",
			description: "系统 tick 频率在 [100Hz, 10kHz] 范围内",
		},
		{
			id: "CON-FRTOS-INV-001",
			expression: "max_tasks <= 8",
			description: "最大任务数不超过 8（内存安全）",
		},
	],
	faultHandling: [
		{
			id: "CON-FRTOS-FLT-000",
			expression: "if task_stack_overflow then delete_task",
			description: "任务栈溢出时删除任务",
		},
		{
			id: "CON-FRTOS-FLT-001",
			expression: "if mutex_deadlock then release_all_locks",
			description: "互斥锁死锁检测并释放",
		},
		{
			id: "CON-FRTOS-FLT-002",
			expression: "if queue_full then block_or_timeout",
			description: "队列满时阻塞等待或超时返回",
		},
	],
	code: `/* FreeRTOSScheduler.c — FreeRTOS 任务调度器 */
#include <stdint.h>
#include <string.h>

#define FREERTOS_MAX_TASKS 8
#define FREERTOS_MAX_SEMAPHORES 8
#define FREERTOS_MAX_QUEUES 4

typedef enum {
    TASK_DELETED = 0, TASK_READY = 1, TASK_RUNNING = 2,
    TASK_BLOCKED = 3, TASK_SUSPENDED = 4
} FRTOSTaskState_t;

typedef enum {
    PRIORITY_IDLE = 0, PRIORITY_LOW = 1, PRIORITY_NORMAL = 2,
    PRIORITY_HIGH = 3, PRIORITY_CRITICAL = 4
} FRTOSPriority_t;

typedef struct {
    uint8_t task_id;
    FRTOSPriority_t priority;
    FRTOSTaskState_t state;
    uint32_t stack_size;
    uint32_t period_ms;
} FRTOSTask_t;

static FRTOSTask_t g_tasks[FREERTOS_MAX_TASKS];
static uint8_t g_task_count = 0;

double filter(double input) {
    /* 简化版：input 视为 task_id，返回任务状态 */
    uint8_t id = (uint8_t)((int)input);
    uint8_t i;
    for (i = 0; i < g_task_count; i++) {
        if (g_tasks[i].task_id == id) {
            return (double)g_tasks[i].state;
        }
    }
    return 0.0;
}
`,
	contractYaml: `component: FreeRTOSScheduler
description: FreeRTOS 任务调度器，支持多级优先级、信号量/互斥锁同步、队列通信与软件定时器
safety_level: DAL-B
interface:
  inputs:
    - name: task_id
      type: uint8_t
      range: [0, 255]
      description: 任务标识
    - name: command
      type: uint8_t
      range: [0, 8]
      description: "控制命令: 0=创建任务, 1=删除, 2=挂起, 3=恢复, 4=获取信号量, 5=释放, 6=队列发送, 7=队列接收, 8=定时器控制"
  outputs:
    - name: task_state
      type: uint8_t
      range: [0, 4]
      description: "任务状态: 0=删除, 1=就绪, 2=运行, 3=阻塞, 4=挂起"
    - name: result_code
      type: uint8_t
      range: [0, 3]
      description: "操作结果: 0=成功, 1=资源不足, 2=超时, 3=参数错误"
preconditions:
  - id: CON-FRTOS-PRE-000
    expression: "task_id >= 0 && task_id <= 255"
    description: 任务 ID 在有效范围内
  - id: CON-FRTOS-PRE-001
    expression: "command >= 0 && command <= 8"
    description: 命令码在有效枚举范围内
postconditions:
  - id: CON-FRTOS-POST-000
    expression: "task_state >= 0 && task_state <= 4"
    description: 任务状态在有效枚举范围内
  - id: CON-FRTOS-POST-001
    expression: "result_code >= 0 && result_code <= 3"
    description: 结果码在有效范围内
invariants:
  - id: CON-FRTOS-INV-000
    expression: "tick_rate_hz >= 100 && tick_rate_hz <= 10000"
    description: 系统 tick 频率在 [100Hz, 10kHz] 范围内
  - id: CON-FRTOS-INV-001
    expression: "max_tasks <= 8"
    description: 最大任务数不超过 8（内存安全）
fault_handling:
  - id: CON-FRTOS-FLT-000
    expression: "if task_stack_overflow then delete_task"
    description: 任务栈溢出时删除任务
  - id: CON-FRTOS-FLT-001
    expression: "if mutex_deadlock then release_all_locks"
    description: 互斥锁死锁检测并释放
  - id: CON-FRTOS-FLT-002
    expression: "if queue_full then block_or_timeout"
    description: 队列满时阻塞等待或超时返回
`,
};

// ====================================================================
// 模板 10：C++ 智能指针资源管理器（CppSmartPointerManager）
// ====================================================================
const CPP_SMART_POINTER_TEMPLATE: ContractTemplate = {
	id: "cpp-smart-pointer",
	name: "CppSmartPointerManager",
	category: "cpp",
	categoryLabel: "C++ RAII",
	description:
		"基于 RAII 的智能指针资源管理器，使用 std::unique_ptr/shared_ptr 管理航电系统动态资源",
	safetyLevel: "DAL-A",
	inputs: [
		{
			name: "resource_capacity",
			type: "uint32_t",
			range: [1, 1024],
			unit: "bytes",
			description: "资源容量",
		},
		{
			name: "handler_value",
			type: "float64",
			range: [-1e6, 1e6],
			unit: "dimensionless",
			description: "处理器输入值",
		},
	],
	outputs: [
		{
			name: "processed_value",
			type: "float64",
			range: [-1e6, 1e6],
			unit: "dimensionless",
			description: "处理器输出值",
		},
		{
			name: "resource_count",
			type: "uint32_t",
			range: [0, 32],
			description: "当前资源数量",
		},
	],
	preconditions: [
		{
			id: "CON-CPP-PRE-000",
			expression: "resource_capacity > 0 && resource_capacity <= 1024",
			description: "资源容量在有效范围内",
		},
	],
	postconditions: [
		{
			id: "CON-CPP-POST-000",
			expression: "resource_count <= 32",
			description: "资源数量不超过上限",
		},
		{
			id: "CON-CPP-POST-001",
			expression: "processed_value >= -1e6 && processed_value <= 1e6",
			description: "输出值在有效范围内",
		},
	],
	invariants: [
		{
			id: "CON-CPP-INV-000",
			expression: "unique_ptr resources are not copied, only moved",
			description: "unique_ptr 资源不可拷贝，只能移动",
		},
		{
			id: "CON-CPP-INV-001",
			expression: "shared_ptr reference count is thread-safe",
			description: "shared_ptr 引用计数线程安全",
		},
	],
	faultHandling: [
		{
			id: "CON-CPP-FLT-000",
			expression: "if resource creation fails then throw std::runtime_error",
			description: "资源创建失败时抛出异常",
		},
		{
			id: "CON-CPP-FLT-001",
			expression: "if max resources exceeded then reject new allocation",
			description: "超出最大资源数时拒绝新分配",
		},
	],
	code: `/* CppSmartPointerManager.c — C++ RAII 智能指针资源管理器 */
#include <memory>
#include <vector>
#include <string>
#include <stdexcept>

class ResourceBase {
public:
    virtual ~ResourceBase() = default;
    virtual std::string get_type() const = 0;
    virtual bool is_valid() const = 0;
};

class DataBuffer final : public ResourceBase {
public:
    explicit DataBuffer(size_t cap) : m_cap(cap), m_buf(std::make_unique<uint8_t[]>(cap)) {}
    std::string get_type() const override { return "DataBuffer"; }
    bool is_valid() const override { return m_buf != nullptr; }
private:
    size_t m_cap;
    std::unique_ptr<uint8_t[]> m_buf;
};

class ResourceManager {
public:
    std::unique_ptr<ResourceBase> create_buffer(size_t cap) {
        if (m_count >= 32) throw std::runtime_error("Limit exceeded");
        m_count++;
        return std::make_unique<DataBuffer>(cap);
    }
    size_t count() const { return m_count; }
private:
    size_t m_count = 0;
};

double filter(double input) {
    ResourceManager mgr;
    auto buf = mgr.create_buffer(1024);
    return (double)mgr.count();
}
`,
	contractYaml: `component: CppSmartPointerManager
description: 基于 RAII 的智能指针资源管理器
safety_level: DAL-A
interface:
  inputs:
    - name: resource_capacity
      type: uint32_t
      range: [1, 1024]
      unit: bytes
      description: 资源容量
    - name: handler_value
      type: float64
      range: [-1e6, 1e6]
      unit: dimensionless
      description: 处理器输入值
  outputs:
    - name: processed_value
      type: float64
      range: [-1e6, 1e6]
      unit: dimensionless
      description: 处理器输出值
    - name: resource_count
      type: uint32_t
      range: [0, 32]
      description: 当前资源数量
preconditions:
  - id: CON-CPP-PRE-000
    expression: "resource_capacity > 0 && resource_capacity <= 1024"
    description: 资源容量在有效范围内
postconditions:
  - id: CON-CPP-POST-000
    expression: "resource_count <= 32"
    description: 资源数量不超过上限
  - id: CON-CPP-POST-001
    expression: "processed_value >= -1e6 && processed_value <= 1e6"
    description: 输出值在有效范围内
invariants:
  - id: CON-CPP-INV-000
    expression: "unique_ptr resources are not copied, only moved"
    description: unique_ptr 资源不可拷贝，只能移动
  - id: CON-CPP-INV-001
    expression: "shared_ptr reference count is thread-safe"
    description: shared_ptr 引用计数线程安全
fault_handling:
  - id: CON-CPP-FLT-000
    expression: "if resource creation fails then throw std::runtime_error"
    description: 资源创建失败时抛出异常
  - id: CON-CPP-FLT-001
    expression: "if max resources exceeded then reject new allocation"
    description: 超出最大资源数时拒绝新分配
`,
};

// ====================================================================
// 模板 11：C++ 异常处理层次（CppExceptionHierarchy）
// ====================================================================
const CPP_EXCEPTION_TEMPLATE: ContractTemplate = {
	id: "cpp-exception-hierarchy",
	name: "CppExceptionHierarchy",
	category: "cpp",
	categoryLabel: "C++ 异常",
	description: "C++ 自定义异常层次结构，支持安全执行包装器与全局异常处理器",
	safetyLevel: "DAL-A",
	inputs: [
		{
			name: "error_code",
			type: "int32_t",
			range: [-9999, 9999],
			description: "错误代码",
		},
		{
			name: "retry_count",
			type: "uint32_t",
			range: [0, 10],
			description: "重试次数",
		},
	],
	outputs: [
		{
			name: "success",
			type: "uint8_t",
			range: [0, 1],
			description: "执行结果: 0=失败, 1=成功",
		},
		{
			name: "result_error_code",
			type: "int32_t",
			range: [-9999, 9999],
			description: "最终错误代码",
		},
	],
	preconditions: [
		{
			id: "CON-CPP-EXC-PRE-000",
			expression: "retry_count <= 10",
			description: "重试次数不超过上限",
		},
	],
	postconditions: [
		{
			id: "CON-CPP-EXC-POST-000",
			expression: "success == 0 || success == 1",
			description: "结果为有效布尔值",
		},
	],
	invariants: [
		{
			id: "CON-CPP-EXC-INV-000",
			expression: "exceptions are caught by reference, not by value",
			description: "异常按引用捕获，避免对象切片",
		},
	],
	faultHandling: [
		{
			id: "CON-CPP-EXC-FLT-000",
			expression: "if max retries exceeded then return error result",
			description: "超过最大重试次数时返回错误结果",
		},
	],
	code: `/* CppExceptionHierarchy.c — C++ 异常处理层次 */
#include <exception>
#include <string>
#include <functional>

class SkyForgeException : public std::runtime_error {
public:
    explicit SkyForgeException(const std::string& msg, int code = -1)
        : std::runtime_error(msg), m_code(code) {}
    int error_code() const noexcept { return m_code; }
private:
    int m_code;
};

class ConfigException : public SkyForgeException {
public:
    ConfigException(const std::string& key, const std::string& reason)
        : SkyForgeException("Config[" + key + "]: " + reason, 1001) {}
};

double filter(double input) {
    try {
        if (input < 0) throw ConfigException("test", "negative");
        return input;
    } catch (const SkyForgeException& e) {
        return (double)e.error_code();
    }
}
`,
	contractYaml: `component: CppExceptionHierarchy
description: C++ 自定义异常层次结构
safety_level: DAL-A
interface:
  inputs:
    - name: error_code
      type: int32_t
      range: [-9999, 9999]
      description: 错误代码
    - name: retry_count
      type: uint32_t
      range: [0, 10]
      description: 重试次数
  outputs:
    - name: success
      type: uint8_t
      range: [0, 1]
      description: "执行结果: 0=失败, 1=成功"
    - name: result_error_code
      type: int32_t
      range: [-9999, 9999]
      description: 最终错误代码
preconditions:
  - id: CON-CPP-EXC-PRE-000
    expression: "retry_count <= 10"
    description: 重试次数不超过上限
postconditions:
  - id: CON-CPP-EXC-POST-000
    expression: "success == 0 || success == 1"
    description: 结果为有效布尔值
invariants:
  - id: CON-CPP-EXC-INV-000
    expression: "exceptions are caught by reference, not by value"
    description: 异常按引用捕获，避免对象切片
fault_handling:
  - id: CON-CPP-EXC-FLT-000
    expression: "if max retries exceeded then return error result"
    description: 超过最大重试次数时返回错误结果
`,
};

// ====================================================================
// 模板 12：C++ 多态处理器（CppPolymorphicHandler）
// ====================================================================
const CPP_INHERITANCE_TEMPLATE: ContractTemplate = {
	id: "cpp-polymorphic-handler",
	name: "CppPolymorphicHandler",
	category: "cpp",
	categoryLabel: "C++ 多态",
	description: "C++ 虚函数多态处理器链，支持增益/偏移/限幅处理器的动态组合",
	safetyLevel: "DAL-B",
	inputs: [
		{
			name: "raw_value",
			type: "float64",
			range: [-1e6, 1e6],
			unit: "dimensionless",
			description: "原始输入值",
		},
		{
			name: "handler_count",
			type: "uint32_t",
			range: [1, 16],
			description: "处理器数量",
		},
	],
	outputs: [
		{
			name: "processed_value",
			type: "float64",
			range: [-100.0, 100.0],
			unit: "dimensionless",
			description: "处理后的输出值",
		},
	],
	preconditions: [
		{
			id: "CON-CPP-POLY-PRE-000",
			expression: "handler_count >= 1 && handler_count <= 16",
			description: "处理器数量在有效范围内",
		},
	],
	postconditions: [
		{
			id: "CON-CPP-POLY-POST-000",
			expression: "processed_value >= -100.0 && processed_value <= 100.0",
			description: "输出值在限幅范围内",
		},
	],
	invariants: [
		{
			id: "CON-CPP-POLY-INV-000",
			expression: "handler chain processes in order, no reordering",
			description: "处理器链按顺序执行，不重排",
		},
	],
	faultHandling: [
		{
			id: "CON-CPP-POLY-FLT-000",
			expression: "if handler fails then return previous value",
			description: "处理器失败时返回前一个值",
		},
	],
	code: `/* CppPolymorphicHandler.c — C++ 多态处理器链 */
#include <memory>
#include <vector>
#include <string>

class Handler {
public:
    virtual ~Handler() = default;
    virtual bool process(double in, double& out) = 0;
    virtual std::string type() const = 0;
};

class GainHandler final : public Handler {
    double m_gain;
public:
    explicit GainHandler(double g) : m_gain(g) {}
    bool process(double in, double& out) override { out = in * m_gain; return true; }
    std::string type() const override { return "gain"; }
};

class ClampHandler final : public Handler {
    double m_lo, m_hi;
public:
    ClampHandler(double lo, double hi) : m_lo(lo), m_hi(hi) {}
    bool process(double in, double& out) override {
        out = (in < m_lo) ? m_lo : (in > m_hi) ? m_hi : in;
        return true;
    }
    std::string type() const override { return "clamp"; }
};

class HandlerChain {
    std::vector<std::unique_ptr<Handler>> m_handlers;
public:
    bool add(std::unique_ptr<Handler> h) { m_handlers.push_back(std::move(h)); return true; }
    bool execute(double input, double& output) {
        double cur = input, tmp;
        for (auto& h : m_handlers) { if (!h->process(cur, tmp)) return false; cur = tmp; }
        output = cur; return true;
    }
};

double filter(double input) {
    HandlerChain chain;
    chain.add(std::make_unique<GainHandler>(2.0));
    chain.add(std::make_unique<ClampHandler>(-100.0, 100.0));
    double out = 0.0;
    chain.execute(input, out);
    return out;
}
`,
	contractYaml: `component: CppPolymorphicHandler
description: C++ 虚函数多态处理器链
safety_level: DAL-B
interface:
  inputs:
    - name: raw_value
      type: float64
      range: [-1e6, 1e6]
      unit: dimensionless
      description: 原始输入值
    - name: handler_count
      type: uint32_t
      range: [1, 16]
      description: 处理器数量
  outputs:
    - name: processed_value
      type: float64
      range: [-100.0, 100.0]
      unit: dimensionless
      description: 处理后的输出值
preconditions:
  - id: CON-CPP-POLY-PRE-000
    expression: "handler_count >= 1 && handler_count <= 16"
    description: 处理器数量在有效范围内
postconditions:
  - id: CON-CPP-POLY-POST-000
    expression: "processed_value >= -100.0 && processed_value <= 100.0"
    description: 输出值在限幅范围内
invariants:
  - id: CON-CPP-POLY-INV-000
    expression: "handler chain processes in order, no reordering"
    description: 处理器链按顺序执行，不重排
fault_handling:
  - id: CON-CPP-POLY-FLT-000
    expression: "if handler fails then return previous value"
    description: 处理器失败时返回前一个值
`,
};

// ====================================================================
// 模板 13：Rust 所有权资源管理器（RustOwnershipManager）
// ====================================================================
const RUST_OWNERSHIP_TEMPLATE: ContractTemplate = {
	id: "rust-ownership-manager",
	name: "RustOwnershipManager",
	category: "rust",
	categoryLabel: "Rust 所有权",
	description:
		"Rust 所有权与借用规则示例：航电资源管理器，演示所有权转移、不可变/可变借用",
	safetyLevel: "DAL-A",
	inputs: [
		{
			name: "resource_id",
			type: "u32",
			range: [0, 4294967295],
			description: "资源标识",
		},
		{
			name: "resource_type",
			type: "u8",
			range: [0, 3],
			description: "资源类型: 0=Sensor, 1=Actuator, 2=Communication, 3=Storage",
		},
	],
	outputs: [
		{
			name: "is_active",
			type: "u8",
			range: [0, 1],
			description: "资源激活状态",
		},
		{
			name: "active_count",
			type: "u32",
			range: [0, 32],
			description: "活跃资源数量",
		},
	],
	preconditions: [
		{
			id: "CON-RUST-PRE-000",
			expression: "resource_type <= 3",
			description: "资源类型在有效枚举范围内",
		},
	],
	postconditions: [
		{
			id: "CON-RUST-POST-000",
			expression: "active_count <= 32",
			description: "活跃资源数不超过上限",
		},
	],
	invariants: [
		{
			id: "CON-RUST-INV-000",
			expression: "at most one mutable borrow at a time",
			description: "同一时刻最多一个可变借用",
		},
		{
			id: "CON-RUST-INV-001",
			expression: "no data races at compile time",
			description: "编译期无数据竞争",
		},
	],
	faultHandling: [
		{
			id: "CON-RUST-FLT-000",
			expression: "if resource limit exceeded then return Err",
			description: "超出资源限制时返回 Err",
		},
	],
	code: `// RustOwnershipManager.rs — Rust 所有权与借用
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResourceType { Sensor, Actuator, Communication, Storage }

#[derive(Debug, Clone)]
pub struct Resource {
    pub id: u32,
    pub name: String,
    pub resource_type: ResourceType,
    pub is_active: bool,
}

pub struct ResourceManager {
    resources: Vec<Resource>,
    max_resources: usize,
}

impl ResourceManager {
    pub fn new(max: usize) -> Self { Self { resources: Vec::with_capacity(max), max_resources: max } }
    pub fn get_resource(&self, id: u32) -> Option<&Resource> {
        self.resources.iter().find(|r| r.id == id)
    }
    pub fn get_resource_mut(&mut self, id: u32) -> Option<&mut Resource> {
        self.resources.iter_mut().find(|r| r.id == id)
    }
    pub fn add_resource(&mut self, r: Resource) -> Result<(), String> {
        if self.resources.len() >= self.max_resources { return Err("Full".into()); }
        self.resources.push(r); Ok(())
    }
    pub fn active_count(&self) -> usize { self.resources.iter().filter(|r| r.is_active).count() }
}

pub fn filter(input: f64) -> f64 {
    let mut mgr = ResourceManager::new(32);
    let _ = mgr.add_resource(Resource { id: input as u32, name: "s".into(), resource_type: ResourceType::Sensor, is_active: true });
    mgr.active_count() as f64
}
`,
	contractYaml: `component: RustOwnershipManager
description: Rust 所有权与借用规则示例
safety_level: DAL-A
interface:
  inputs:
    - name: resource_id
      type: u32
      range: [0, 4294967295]
      description: 资源标识
    - name: resource_type
      type: u8
      range: [0, 3]
      description: "资源类型: 0=Sensor, 1=Actuator, 2=Communication, 3=Storage"
  outputs:
    - name: is_active
      type: u8
      range: [0, 1]
      description: 资源激活状态
    - name: active_count
      type: u32
      range: [0, 32]
      description: 活跃资源数量
preconditions:
  - id: CON-RUST-PRE-000
    expression: "resource_type <= 3"
    description: 资源类型在有效枚举范围内
postconditions:
  - id: CON-RUST-POST-000
    expression: "active_count <= 32"
    description: 活跃资源数不超过上限
invariants:
  - id: CON-RUST-INV-000
    expression: "at most one mutable borrow at a time"
    description: 同一时刻最多一个可变借用
  - id: CON-RUST-INV-001
    expression: "no data races at compile time"
    description: 编译期无数据竞争
fault_handling:
  - id: CON-RUST-FLT-000
    expression: "if resource limit exceeded then return Err"
    description: 超出资源限制时返回 Err
`,
};

// ====================================================================
// 模板 14：Rust Result 错误处理（RustResultHandler）
// ====================================================================
const RUST_RESULT_TEMPLATE: ContractTemplate = {
	id: "rust-result-handler",
	name: "RustResultHandler",
	category: "rust",
	categoryLabel: "Rust Result",
	description: "Rust Result 错误处理示例：自定义错误类型、? 运算符、错误传播链",
	safetyLevel: "DAL-A",
	inputs: [
		{
			name: "config_value",
			type: "f64",
			range: [-1e6, 1e6],
			description: "配置值",
		},
		{
			name: "validate",
			type: "u8",
			range: [0, 1],
			description: "是否执行验证",
		},
	],
	outputs: [
		{
			name: "result_code",
			type: "i32",
			range: [-9999, 0],
			description: "结果代码: 0=成功, 负数=错误",
		},
		{
			name: "output_value",
			type: "f64",
			range: [-1e6, 1e6],
			description: "处理后的值",
		},
	],
	preconditions: [
		{
			id: "CON-RUST-RES-PRE-000",
			expression: "validate == 0 || validate == 1",
			description: "验证标志为有效布尔值",
		},
	],
	postconditions: [
		{
			id: "CON-RUST-RES-POST-000",
			expression: "result_code <= 0",
			description: "结果代码为非正数",
		},
	],
	invariants: [
		{
			id: "CON-RUST-RES-INV-000",
			expression: "all errors are propagated with ? operator",
			description: "所有错误使用 ? 运算符传播",
		},
	],
	faultHandling: [
		{
			id: "CON-RUST-RES-FLT-000",
			expression: "if validation fails then return Err(Validation)",
			description: "验证失败时返回 Validation 错误",
		},
	],
	code: `// RustResultHandler.rs — Rust Result 错误处理
use std::fmt;

#[derive(Debug)]
pub enum AppError {
    Config { key: String, reason: String },
    Validation(String),
    ResourceLimit { current: usize, max: usize },
}

impl fmt::Display for AppError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AppError::Config { key, reason } => write!(f, "Config[{}]: {}", key, reason),
            AppError::Validation(msg) => write!(f, "Validation: {}", msg),
            AppError::ResourceLimit { current, max } => write!(f, "Limit: {}/{}", current, max),
        }
    }
}

impl std::error::Error for AppError {}

pub type AppResult<T> = Result<T, AppError>;

pub fn validate_config(value: f64) -> AppResult<f64> {
    if value < 0.0 { return Err(AppError::Validation("Negative value".into())); }
    Ok(value)
}

pub fn filter(input: f64) -> f64 {
    match validate_config(input) {
        Ok(v) => v,
        Err(e) => { eprintln!("Error: {}", e); 0.0 }
    }
}
`,
	contractYaml: `component: RustResultHandler
description: Rust Result 错误处理示例
safety_level: DAL-A
interface:
  inputs:
    - name: config_value
      type: f64
      range: [-1e6, 1e6]
      description: 配置值
    - name: validate
      type: u8
      range: [0, 1]
      description: 是否执行验证
  outputs:
    - name: result_code
      type: i32
      range: [-9999, 0]
      description: "结果代码: 0=成功, 负数=错误"
    - name: output_value
      type: f64
      range: [-1e6, 1e6]
      description: 处理后的值
preconditions:
  - id: CON-RUST-RES-PRE-000
    expression: "validate == 0 || validate == 1"
    description: 验证标志为有效布尔值
postconditions:
  - id: CON-RUST-RES-POST-000
    expression: "result_code <= 0"
    description: 结果代码为非正数
invariants:
  - id: CON-RUST-RES-INV-000
    expression: "all errors are propagated with ? operator"
    description: 所有错误使用 ? 运算符传播
fault_handling:
  - id: CON-RUST-RES-FLT-000
    expression: "if validation fails then return Err(Validation)"
    description: 验证失败时返回 Validation 错误
`,
};

// ====================================================================
// 模板 15：Rust 异步并发管道（RustAsyncPipeline）
// ====================================================================
const RUST_ASYNC_TEMPLATE: ContractTemplate = {
	id: "rust-async-pipeline",
	name: "RustAsyncPipeline",
	category: "rust",
	categoryLabel: "Rust async",
	description:
		"Rust tokio 异步并发管道，支持 Arc<Mutex> 共享状态、mpsc 通道、并发工作池",
	safetyLevel: "DAL-B",
	inputs: [
		{
			name: "sensor_value",
			type: "f64",
			range: [-50.0, 50.0],
			unit: "m/s2",
			description: "传感器输入值",
		},
		{
			name: "worker_count",
			type: "u32",
			range: [1, 8],
			description: "并发工作线程数",
		},
	],
	outputs: [
		{
			name: "aggregated_value",
			type: "f64",
			range: [-50.0, 50.0],
			unit: "m/s2",
			description: "聚合后的值",
		},
		{
			name: "counter",
			type: "u64",
			// uint64 实际上界为 2^64-1 (18446744073709551615)，
			// 但 JS Number 精度上限为 2^53-1，用 MAX_SAFE_INTEGER 近似表示。
			range: [0, Number.MAX_SAFE_INTEGER],
			description: "原子计数器",
		},
	],
	preconditions: [
		{
			id: "CON-RUST-ASYNC-PRE-000",
			expression: "worker_count >= 1 && worker_count <= 8",
			description: "工作线程数在有效范围内",
		},
	],
	postconditions: [
		{
			id: "CON-RUST-ASYNC-POST-000",
			expression: "counter >= 0",
			description: "计数器非负",
		},
	],
	invariants: [
		{
			id: "CON-RUST-ASYNC-INV-000",
			expression: "Arc<T> is Clone and Send + Sync",
			description: "Arc<T> 满足 Clone + Send + Sync 约束",
		},
		{
			id: "CON-RUST-ASYNC-INV-001",
			expression: "no data races guaranteed by ownership system",
			description: "所有权系统保证无数据竞争",
		},
	],
	faultHandling: [
		{
			id: "CON-RUST-ASYNC-FLT-000",
			expression: "if channel closed then graceful shutdown",
			description: "通道关闭时优雅退出",
		},
	],
	code: `// RustAsyncPipeline.rs — tokio 异步并发管道
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use tokio::sync::{mpsc, RwLock};

pub struct ThreadSafeCounter {
    value: AtomicU64,
    active: AtomicBool,
}

impl ThreadSafeCounter {
    pub fn new() -> Self {
        Self { value: AtomicU64::new(0), active: AtomicBool::new(true) }
    }
    pub fn increment(&self) -> u64 { self.value.fetch_add(1, Ordering::SeqCst) }
    pub fn get(&self) -> u64 { self.value.load(Ordering::SeqCst) }
}

pub struct SharedState {
    pub data: Arc<RwLock<Vec<f64>>>,
    pub counter: Arc<ThreadSafeCounter>,
}

impl SharedState {
    pub fn new() -> Self {
        Self { data: Arc::new(RwLock::new(Vec::new())), counter: Arc::new(ThreadSafeCounter::new()) }
    }
    pub async fn push_value(&self, v: f64) {
        self.data.write().await.push(v);
        self.counter.increment();
    }
    pub async fn get_average(&self) -> f64 {
        let d = self.data.read().await;
        if d.is_empty() { 0.0 } else { d.iter().sum::<f64>() / d.len() as f64 }
    }
}

pub fn filter(input: f64) -> f64 {
    let rt = tokio::runtime::Runtime::new().unwrap();
    rt.block_on(async {
        let state = SharedState::new();
        state.push_value(input).await;
        state.get_average().await
    })
}
`,
	contractYaml: `component: RustAsyncPipeline
description: Rust tokio 异步并发管道
safety_level: DAL-B
interface:
  inputs:
    - name: sensor_value
      type: f64
      range: [-50.0, 50.0]
      unit: m/s2
      description: 传感器输入值
    - name: worker_count
      type: u32
      range: [1, 8]
      description: 并发工作线程数
  outputs:
    - name: aggregated_value
      type: f64
      range: [-50.0, 50.0]
      unit: m/s2
      description: 聚合后的值
    - name: counter
      type: u64
      range: [0, 18446744073709551615]
      description: 原子计数器
preconditions:
  - id: CON-RUST-ASYNC-PRE-000
    expression: "worker_count >= 1 && worker_count <= 8"
    description: 工作线程数在有效范围内
postconditions:
  - id: CON-RUST-ASYNC-POST-000
    expression: "counter >= 0"
    description: 计数器非负
invariants:
  - id: CON-RUST-ASYNC-INV-000
    expression: "Arc<T> is Clone and Send + Sync"
    description: Arc<T> 满足 Clone + Send + Sync 约束
  - id: CON-RUST-ASYNC-INV-001
    expression: "no data races guaranteed by ownership system"
    description: 所有权系统保证无数据竞争
fault_handling:
  - id: CON-RUST-ASYNC-FLT-000
    expression: "if channel closed then graceful shutdown"
    description: 通道关闭时优雅退出
`,
};

// ====================================================================
// 模板 16：ARINC 653 分区调度器配置（Arinc653PartitionScheduler）
// 与模板 8 (Arinc653Partition) 互补：本模板聚焦于"调度器配置"层面
// (partition_name / period / time_slice / entry_point / err_handler)
// ====================================================================
const ARINC653_PARTITION_SCHEDULER_TEMPLATE: ContractTemplate = {
	id: "arinc653-partition-scheduler",
	name: "Arinc653PartitionScheduler",
	category: "arinc653",
	categoryLabel: "ARINC653 调度配置",
	description:
		"ARINC 653 分区调度器配置模板，定义分区名/MTF周期/时间片/入口函数/错误处理函数，符合 DO-178C DAL-A",
	safetyLevel: "DAL-A",
	inputs: [
		{
			name: "partition_name",
			type: "string",
			description:
				"分区名 (默认 Partition_1，如 Display/Navigation/Health Monitoring)",
		},
		{
			name: "partition_period_ms",
			type: "uint32_t",
			range: [10, 1000],
			unit: "ms",
			description: "主时间帧 MTF 周期 (默认 200ms，符合 ARINC 653 配置约束)",
		},
		{
			name: "time_slice_ms",
			type: "uint32_t",
			range: [1, 200],
			unit: "ms",
			description: "本分区时间片 (默认 50ms，须 ≤ MTF 周期)",
		},
		{
			name: "entry_point",
			type: "string",
			description: "分区入口函数名 (默认 main_partition_1)",
		},
		{
			name: "err_handler",
			type: "string",
			description: "错误处理函数名 (默认 partition_hm_handler，超时触发)",
		},
	],
	outputs: [
		{
			name: "partition_state",
			type: "uint8_t",
			range: [0, 4],
			description:
				"分区状态: 0=IDLE, 1=RUNNABLE, 2=RUNNING, 3=BLOCKED, 4=TERMINATED",
		},
		{
			name: "result_code",
			type: "uint8_t",
			range: [0, 3],
			description: "操作结果: 0=OK, 1=INVALID_PARAM, 2=NO_RESOURCE, 3=TIMEOUT",
		},
	],
	preconditions: [
		{
			id: "CON-A653S-PRE-000",
			expression: "partition_period_ms >= 10 && partition_period_ms <= 1000",
			description: "MTF 周期必须在 [10ms, 1000ms] 范围内",
		},
		{
			id: "CON-A653S-PRE-001",
			expression: "time_slice_ms >= 1 && time_slice_ms <= partition_period_ms",
			description: "时间片必须 ≥ 1ms 且 ≤ MTF 周期 (时间片守恒)",
		},
	],
	postconditions: [
		{
			id: "CON-A653S-POST-000",
			expression: "partition_state >= 0 && partition_state <= 4",
			description: "分区状态在有效枚举范围内",
		},
		{
			id: "CON-A653S-POST-001",
			expression: "result_code >= 0 && result_code <= 3",
			description: "结果码在有效范围内",
		},
	],
	invariants: [
		{
			id: "CON-A653S-INV-000",
			expression: "time_slice_ms <= partition_period_ms",
			description: "时间片守恒约束: time_slice ≤ MTF period",
		},
		{
			id: "CON-A653S-INV-001",
			expression: "context_switch_duration_ms < 1.0",
			description: "分区上下文切换耗时 < 1ms (ARINC 653 调度约束)",
		},
		{
			id: "CON-A653S-INV-002",
			expression: "no_priority_inversion == true",
			description: "严格周期性调度，无优先级反转 (固定优先级 + 时间片)",
		},
		{
			id: "CON-A653S-INV-003",
			expression: "scheduler_jitter_us <= 100",
			description: "调度抖动 ≤ 100 μs (Strictly Periodic)",
		},
	],
	faultHandling: [
		{
			id: "CON-A653S-FLT-000",
			expression: "if partition_overrun then err_handler(OVERRUN)",
			description: "分区超时 (Overrun) 触发 err_handler 回调",
		},
		{
			id: "CON-A653S-FLT-001",
			expression: "if partition_overrun then partition_state := TERMINATED",
			description: "超时分区状态置为 TERMINATED，本 MTF 内不再调度",
		},
		{
			id: "CON-A653S-FLT-002",
			expression: "if hm_event == FATAL then enter SAFE_STATE",
			description: "致命故障时进入 SAFE_STATE，停止所有分区执行",
		},
	],
	code: `/* Arinc653PartitionScheduler.c — ARINC 653 分区调度器配置入口 */
#include <stdint.h>
#include <stddef.h>

#define A653S_MTF_PERIOD_MS         (200U)   /* 主时间帧周期 200 ms */
#define A653S_TIME_SLICE_MS         (50U)    /* Partition 1 时间片 50 ms */
#define A653S_CONTEXT_SWITCH_MAX_MS (1U)     /* 上下文切换上限 1 ms */

typedef enum {
    A653S_STATE_IDLE = 0, A653S_STATE_RUNNABLE = 1, A653S_STATE_RUNNING = 2,
    A653S_STATE_BLOCKED = 3, A653S_STATE_TERMINATED = 4
} A653S_PartitionState_t;

typedef struct {
    uint8_t              partition_id;
    A653S_PartitionState_t state;
    uint32_t             time_slice_ms;
    uint32_t             elapsed_ms;
} A653S_Partition_t;

static A653S_Partition_t g_partition = { 1U, A653S_STATE_IDLE, A653S_TIME_SLICE_MS, 0U };

/* partition_hm_handler: 错误处理函数 (弱定义，应用层可重写) */
static void partition_hm_handler(uint8_t partition_id, uint8_t event)
{
    (void)partition_id;
    if (event == 1U) {  /* OVERRUN */
        g_partition.state = A653S_STATE_TERMINATED;
    }
}

double filter(double input) {
    /* input 视为分区 ID，返回分区当前状态 (用于组合验证签名匹配) */
    (void)input;
    /* 时间片守恒不变式检查 (CON-A653S-INV-000) */
    if (g_partition.time_slice_ms > A653S_MTF_PERIOD_MS) {
        partition_hm_handler(g_partition.partition_id, 1U);
    }
    return (double)g_partition.state;
}
`,
	contractYaml: `component: Arinc653PartitionScheduler
description: ARINC 653 分区调度器配置模板，定义分区调度参数
safety_level: DAL-A
interface:
  inputs:
    - name: partition_name
      type: string
      description: 分区名 (默认 Partition_1)
    - name: partition_period_ms
      type: uint32_t
      range: [10, 1000]
      unit: ms
      description: 主时间帧 MTF 周期 (默认 200ms)
    - name: time_slice_ms
      type: uint32_t
      range: [1, 200]
      unit: ms
      description: 本分区时间片 (默认 50ms)
    - name: entry_point
      type: string
      description: 分区入口函数名 (默认 main_partition_1)
    - name: err_handler
      type: string
      description: 错误处理函数名 (默认 partition_hm_handler)
  outputs:
    - name: partition_state
      type: uint8_t
      range: [0, 4]
      description: "分区状态: 0=IDLE, 1=RUNNABLE, 2=RUNNING, 3=BLOCKED, 4=TERMINATED"
    - name: result_code
      type: uint8_t
      range: [0, 3]
      description: "操作结果: 0=OK, 1=INVALID_PARAM, 2=NO_RESOURCE, 3=TIMEOUT"
preconditions:
  - id: CON-A653S-PRE-000
    expression: "partition_period_ms >= 10 && partition_period_ms <= 1000"
    description: MTF 周期必须在 [10ms, 1000ms] 范围内
  - id: CON-A653S-PRE-001
    expression: "time_slice_ms >= 1 && time_slice_ms <= partition_period_ms"
    description: 时间片必须 ≥ 1ms 且 ≤ MTF 周期 (时间片守恒)
postconditions:
  - id: CON-A653S-POST-000
    expression: "partition_state >= 0 && partition_state <= 4"
    description: 分区状态在有效枚举范围内
  - id: CON-A653S-POST-001
    expression: "result_code >= 0 && result_code <= 3"
    description: 结果码在有效范围内
invariants:
  - id: CON-A653S-INV-000
    expression: "time_slice_ms <= partition_period_ms"
    description: 时间片守恒约束 (time_slice ≤ MTF period)
  - id: CON-A653S-INV-001
    expression: "context_switch_duration_ms < 1.0"
    description: 分区上下文切换耗时 < 1ms
  - id: CON-A653S-INV-002
    expression: "no_priority_inversion == true"
    description: 严格周期性调度，无优先级反转
  - id: CON-A653S-INV-003
    expression: "scheduler_jitter_us <= 100"
    description: 调度抖动 ≤ 100 μs (Strictly Periodic)
fault_handling:
  - id: CON-A653S-FLT-000
    expression: "if partition_overrun then err_handler(OVERRUN)"
    description: 分区超时触发 err_handler 回调
  - id: CON-A653S-FLT-001
    expression: "if partition_overrun then partition_state := TERMINATED"
    description: 超时分区状态置为 TERMINATED
  - id: CON-A653S-FLT-002
    expression: "if hm_event == FATAL then enter SAFE_STATE"
    description: 致命故障时进入 SAFE_STATE
`,
};

// ====================================================================
// 模板 17：FreeRTOS 任务调度器配置（FreeRTOSTaskScheduler）
// 与模板 9 (FreeRTOSScheduler) 互补：本模板聚焦于"任务调度参数配置"
// (task_name / priority / period_ms / budget_ms / stack_size / queue_length)
// ====================================================================
const FREERTOS_TASK_SCHEDULER_TEMPLATE: ContractTemplate = {
	id: "freertos-task-scheduler",
	name: "FreeRTOSTaskScheduler",
	category: "freertos",
	categoryLabel: "FreeRTOS 调度配置",
	description:
		"FreeRTOS 任务调度器配置模板，定义任务名/优先级/周期/执行预算/栈大小/队列长度，符合 DO-178C DAL-B",
	safetyLevel: "DAL-B",
	inputs: [
		{
			name: "task_name",
			type: "string",
			description:
				"任务名 (默认 Control_Law，如 Sensor_Reader/Control_Law/Telemetry_Output)",
		},
		{
			name: "priority",
			type: "uint8_t",
			range: [0, 7],
			description: "任务优先级 (0..7，数值越大优先级越高，默认 4)",
		},
		{
			name: "period_ms",
			type: "uint32_t",
			range: [1, 1000],
			unit: "ms",
			description: "任务周期 (默认 20ms，须 ≥ budget_ms)",
		},
		{
			name: "budget_ms",
			type: "uint32_t",
			range: [1, 100],
			unit: "ms",
			description: "执行预算 (默认 5ms，单次最大执行时间 WCET)",
		},
		{
			name: "stack_size",
			type: "uint32_t",
			range: [256, 8192],
			unit: "words",
			description: "任务栈大小 (单位: 字，默认 1024)",
		},
		{
			name: "queue_length",
			type: "uint8_t",
			range: [1, 64],
			description: "队列长度 (默认 10，用于任务间通信)",
		},
	],
	outputs: [
		{
			name: "task_state",
			type: "uint8_t",
			range: [0, 4],
			description:
				"任务状态: 0=DELETED, 1=READY, 2=RUNNING, 3=BLOCKED, 4=SUSPENDED",
		},
		{
			name: "result_code",
			type: "uint8_t",
			range: [0, 3],
			description: "操作结果: 0=OK, 1=NO_RESOURCE, 2=TIMEOUT, 3=INVALID_PARAM",
		},
	],
	preconditions: [
		{
			id: "CON-FRTOS2-PRE-000",
			expression: "priority >= 0 && priority <= 7",
			description: "任务优先级必须在 [0, 7] 范围内 (FreeRTOS 8 级优先级)",
		},
		{
			id: "CON-FRTOS2-PRE-001",
			expression: "budget_ms <= period_ms",
			description: "执行预算必须 ≤ 任务周期 (利用率 < 100%)",
		},
		{
			id: "CON-FRTOS2-PRE-002",
			expression: "stack_size >= 256 && stack_size <= 8192",
			description: "栈大小必须在 [256, 8192] 字范围内",
		},
	],
	postconditions: [
		{
			id: "CON-FRTOS2-POST-000",
			expression: "task_state >= 0 && task_state <= 4",
			description: "任务状态在有效枚举范围内",
		},
		{
			id: "CON-FRTOS2-POST-001",
			expression: "result_code >= 0 && result_code <= 3",
			description: "结果码在有效范围内",
		},
	],
	invariants: [
		{
			id: "CON-FRTOS2-INV-000",
			expression: "budget_ms <= period_ms",
			description: "执行预算 ≤ 任务周期 (无超载)",
		},
		{
			id: "CON-FRTOS2-INV-001",
			expression: "priority >= 0 && priority <= 7",
			description: "优先级固定在 [0, 7] 范围 (FreeRTOS 8 级)",
		},
		{
			id: "CON-FRTOS2-INV-002",
			expression: "static_allocation_only == true",
			description: "仅使用静态内存分配 (禁止 malloc)",
		},
		{
			id: "CON-FRTOS2-INV-003",
			expression: "priority_inheritance_enabled == true",
			description: "Mutex 优先级继承已启用 (防止优先级反转)",
		},
		{
			id: "CON-FRTOS2-INV-004",
			expression: "cpu_load_threshold_percent == 85",
			description: "CPU 利用率告警阈值 85%",
		},
	],
	faultHandling: [
		{
			id: "CON-FRTOS2-FLT-000",
			expression: "if task_overrun then trigger watchdog_reset",
			description: "任务超时 (执行时间 > 预算) 触发 watchdog_reset",
		},
		{
			id: "CON-FRTOS2-FLT-001",
			expression: "if cpu_load_percent > 85 then trigger cpu_load_alarm",
			description: "CPU 利用率 > 85% 触发 ALARM，系统降级运行",
		},
		{
			id: "CON-FRTOS2-FLT-002",
			expression: "if stack_overflow then trigger StackOverflowHook",
			description: "栈溢出触发 FreeRTOS 钩子函数",
		},
		{
			id: "CON-FRTOS2-FLT-003",
			expression: "if queue_full then drop_message_and_increment_counter",
			description: "队列满时丢弃新消息并递增丢包计数器",
		},
	],
	code: `/* FreeRTOSTaskScheduler.c — FreeRTOS 任务调度器配置入口 */
#include <stdint.h>
#include <stddef.h>

#define FRTOS2_PRIORITY_DEFAULT     (4U)     /* 默认优先级 4 */
#define FRTOS2_PERIOD_MS_DEFAULT    (20U)    /* 默认周期 20 ms */
#define FRTOS2_BUDGET_MS_DEFAULT    (5U)     /* 默认预算 5 ms */
#define FRTOS2_STACK_SIZE_DEFAULT   (1024U)  /* 默认栈 1024 字 */
#define FRTOS2_QUEUE_LENGTH_DEFAULT (10U)    /* 默认队列长度 10 */
#define FRTOS2_CPU_LOAD_ALARM_PCT   (85U)    /* CPU 利用率告警阈值 85% */

typedef enum {
    FRTOS2_STATE_DELETED = 0, FRTOS2_STATE_READY = 1, FRTOS2_STATE_RUNNING = 2,
    FRTOS2_STATE_BLOCKED = 3, FRTOS2_STATE_SUSPENDED = 4
} FRTOS2_TaskState_t;

typedef struct {
    uint8_t            priority;
    uint32_t           period_ms;
    uint32_t           budget_ms;
    uint32_t           stack_size;
    uint8_t            queue_length;
    FRTOS2_TaskState_t state;
} FRTOS2_TaskConfig_t;

static FRTOS2_TaskConfig_t g_task_cfg = {
    FRTOS2_PRIORITY_DEFAULT, FRTOS2_PERIOD_MS_DEFAULT, FRTOS2_BUDGET_MS_DEFAULT,
    FRTOS2_STACK_SIZE_DEFAULT, FRTOS2_QUEUE_LENGTH_DEFAULT, FRTOS2_STATE_READY
};

/* watchdog_reset: 任务超时回调 (弱定义，应用层可重写) */
static void watchdog_reset(uint8_t event)
{
    (void)event;
    g_task_cfg.state = FRTOS2_STATE_SUSPENDED;
}

double filter(double input) {
    /* input 视为 CPU 利用率百分比 (用于组合验证签名匹配) */
    uint8_t cpu_load = (uint8_t)input;
    /* 预算守恒检查 (CON-FRTOS2-INV-000) */
    if (g_task_cfg.budget_ms > g_task_cfg.period_ms) {
        watchdog_reset(1U);  /* OVERRUN */
    }
    /* CPU 利用率告警 (CON-FRTOS2-FLT-001) */
    if (cpu_load > FRTOS2_CPU_LOAD_ALARM_PCT) {
        watchdog_reset(3U);  /* ALARM */
    }
    return (double)g_task_cfg.state;
}
`,
	contractYaml: `component: FreeRTOSTaskScheduler
description: FreeRTOS 任务调度器配置模板，定义任务调度参数
safety_level: DAL-B
interface:
  inputs:
    - name: task_name
      type: string
      description: 任务名 (默认 Control_Law)
    - name: priority
      type: uint8_t
      range: [0, 7]
      description: 任务优先级 (0..7，默认 4)
    - name: period_ms
      type: uint32_t
      range: [1, 1000]
      unit: ms
      description: 任务周期 (默认 20ms)
    - name: budget_ms
      type: uint32_t
      range: [1, 100]
      unit: ms
      description: 执行预算 (默认 5ms)
    - name: stack_size
      type: uint32_t
      range: [256, 8192]
      unit: words
      description: 栈大小 (默认 1024 字)
    - name: queue_length
      type: uint8_t
      range: [1, 64]
      description: 队列长度 (默认 10)
  outputs:
    - name: task_state
      type: uint8_t
      range: [0, 4]
      description: "任务状态: 0=DELETED, 1=READY, 2=RUNNING, 3=BLOCKED, 4=SUSPENDED"
    - name: result_code
      type: uint8_t
      range: [0, 3]
      description: "操作结果: 0=OK, 1=NO_RESOURCE, 2=TIMEOUT, 3=INVALID_PARAM"
preconditions:
  - id: CON-FRTOS2-PRE-000
    expression: "priority >= 0 && priority <= 7"
    description: 任务优先级必须在 [0, 7] 范围内 (FreeRTOS 8 级优先级)
  - id: CON-FRTOS2-PRE-001
    expression: "budget_ms <= period_ms"
    description: 执行预算必须 ≤ 任务周期 (利用率 < 100%)
  - id: CON-FRTOS2-PRE-002
    expression: "stack_size >= 256 && stack_size <= 8192"
    description: 栈大小必须在 [256, 8192] 字范围内
postconditions:
  - id: CON-FRTOS2-POST-000
    expression: "task_state >= 0 && task_state <= 4"
    description: 任务状态在有效枚举范围内
  - id: CON-FRTOS2-POST-001
    expression: "result_code >= 0 && result_code <= 3"
    description: 结果码在有效范围内
invariants:
  - id: CON-FRTOS2-INV-000
    expression: "budget_ms <= period_ms"
    description: 执行预算 ≤ 任务周期 (无超载)
  - id: CON-FRTOS2-INV-001
    expression: "priority >= 0 && priority <= 7"
    description: 优先级固定在 [0, 7] 范围 (FreeRTOS 8 级)
  - id: CON-FRTOS2-INV-002
    expression: "static_allocation_only == true"
    description: 仅使用静态内存分配 (禁止 malloc)
  - id: CON-FRTOS2-INV-003
    expression: "priority_inheritance_enabled == true"
    description: Mutex 优先级继承已启用 (防止优先级反转)
  - id: CON-FRTOS2-INV-004
    expression: "cpu_load_threshold_percent == 85"
    description: CPU 利用率告警阈值 85%
fault_handling:
  - id: CON-FRTOS2-FLT-000
    expression: "if task_overrun then trigger watchdog_reset"
    description: 任务超时触发 watchdog_reset 回调
  - id: CON-FRTOS2-FLT-001
    expression: "if cpu_load_percent > 85 then trigger cpu_load_alarm"
    description: CPU 利用率 > 85% 触发 ALARM，系统降级运行
  - id: CON-FRTOS2-FLT-002
    expression: "if stack_overflow then trigger StackOverflowHook"
    description: 栈溢出触发 FreeRTOS 钩子函数
  - id: CON-FRTOS2-FLT-003
    expression: "if queue_full then drop_message_and_increment_counter"
    description: 队列满时丢弃新消息并递增丢包计数器
`,
};

// ====================================================================
// 模板库导出
// ====================================================================

/** 机载常用组件契约模板列表（>=7 个） */
export const CONTRACT_TEMPLATES: ContractTemplate[] = [
	LOWPASS_FILTER_TEMPLATE,
	PID_CONTROLLER_TEMPLATE,
	SENSOR_SAMPLER_TEMPLATE,
	LIMITER_TEMPLATE,
	HMI_OVERLAY_TEMPLATE,
	SENSOR_FUSION_TEMPLATE,
	MISSION_PLANNER_TEMPLATE,
	ARINC653_PARTITION_TEMPLATE,
	FREERTOS_SCHEDULER_TEMPLATE,
	CPP_SMART_POINTER_TEMPLATE,
	CPP_EXCEPTION_TEMPLATE,
	CPP_INHERITANCE_TEMPLATE,
	RUST_OWNERSHIP_TEMPLATE,
	RUST_RESULT_TEMPLATE,
	RUST_ASYNC_TEMPLATE,
	ARINC653_PARTITION_SCHEDULER_TEMPLATE,
	FREERTOS_TASK_SCHEDULER_TEMPLATE,
];

/**
 * 根据 ID 查找模板。
 * @param id 模板 ID
 * @returns 匹配的模板；未找到返回 undefined
 */
export function findTemplateById(id: string): ContractTemplate | undefined {
	return CONTRACT_TEMPLATES.find((t) => t.id === id);
}

/**
 * 将信号的范围格式化为可读字符串。
 * @example formatRange([-1000.0, 1000.0]) → "[-1000, 1000]"
 */
export function formatRange(range: [number, number] | undefined): string {
	if (!range) return "—";
	const [lo, hi] = range;
	return `[${lo}, ${hi}]`;
}

/**
 * 将信号列表格式化为简短签名串（用于卡片预览）。
 * @example formatSignals([{name:"raw_signal",type:"float64"}]) → "raw_signal: float64"
 */
export function formatSignals(signals: ContractTemplateSignal[]): string {
	if (signals.length === 0) return "—";
	return signals.map((s) => `${s.name}: ${s.type}`).join(", ");
}
