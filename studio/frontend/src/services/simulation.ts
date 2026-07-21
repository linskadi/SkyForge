/**
 * 数字孪生仿真逻辑
 * 纯计算函数：波形生成、IIR 滤波、波形统计、故障注入
 */

import {
	ADC_CENTER,
	FILTER_ALPHA,
	MOCK_COMPOSED_CODE_FEEDBACK,
	MOCK_COMPOSED_CODE_PARALLEL,
	MOCK_COMPOSED_CODE_SEQUENTIAL,
	SIM_STEPS,
	SINE_AMP,
} from "@/mock/data";
import type {
	AgentLog,
	CompatibilityCheckItem,
	CompatibilityResult,
	ComposeConnection,
	ContractViolation,
	FaultParams,
	FaultType,
	SimulationResult,
	SimulationStatistics,
} from "@/types/domain";

/** 生成正常正弦输入波形：32768 + 20000*sin(2π·t/50) */
export function genSineInput(steps: number): number[] {
	const wave: number[] = [];
	for (let t = 0; t < steps; t++) {
		const v = ADC_CENTER + SINE_AMP * Math.sin((2 * Math.PI * t) / 50);
		wave.push(Math.round(v));
	}
	return wave;
}

/** 一阶 IIR 低通滤波：y[n] = alpha*x[n] + (1-alpha)*y[n-1] */
export function lowpassFilter(input: number[], alpha: number): number[] {
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
export function computeStats(
	input: number[],
	output: number[],
): SimulationStatistics {
	const inMin = input.reduce(
		(a, b) => Math.min(a, b),
		Number.POSITIVE_INFINITY,
	);
	const inMax = input.reduce(
		(a, b) => Math.max(a, b),
		Number.NEGATIVE_INFINITY,
	);
	const outMin = output.reduce(
		(a, b) => Math.min(a, b),
		Number.POSITIVE_INFINITY,
	);
	const outMax = output.reduce(
		(a, b) => Math.max(a, b),
		Number.NEGATIVE_INFINITY,
	);
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

/** 生成正常的无故障仿真结果（可复用的 IIFE 计算） */
export function generateNormalSimulationResult(
	logs: AgentLog[],
): SimulationResult {
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
		logs,
	};
}

/**
 * 故障注入仿真：根据故障类型生成对应的故障波形和仿真结果
 */
export function runFaultInjection(
	faultType: FaultType,
	params: FaultParams,
): {
	faultedInput: number[];
	faultRange: { start: number; end: number } | null;
	violation: ContractViolation | null;
	logs: AgentLog[];
	finalOutput: number[];
} {
	const input = genSineInput(SIM_STEPS);
	const baseOutput = lowpassFilter(input, FILTER_ALPHA);

	let faultedInput = [...input];
	let faultRange: { start: number; end: number } | null = null;
	let violation: ContractViolation | null = null;
	let logs: AgentLog[] = [];

	switch (faultType) {
		case "bias": {
			const bias = params.bias_value ?? 20000;
			const start = 40;
			faultedInput = input.map((v, t) =>
				t >= start ? Math.min(65535, v + bias) : v,
			);
			faultRange = { start, end: SIM_STEPS - 1 };
			logs = [
				{
					agent: "SYSTEM",
					level: "info",
					thought: `$ ./sim --fault bias --bias ${bias} --start ${start}`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] step ${start}: 注入传感器偏置 +${bias}`,
				},
				{
					agent: "TERMINAL",
					level: "error",
					thought: `[sim] step ${start + 2}: assert(filtered_value <= 65535) FAILED → 输出溢出`,
				},
				{
					agent: "SYSTEM",
					level: "error",
					thought: "❌ 契约违约 [CON-001-POST-000]：输出值超出 uint16 范围",
				},
				{
					agent: "SYSTEM",
					level: "info",
					thought:
						"💡 沙盒已捕获 core dump，未影响宿主环境（参考文档 6.6 沙盒隔离）",
				},
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
			const duration = params.loss_duration ?? 30;
			const start = 50;
			const end = Math.min(SIM_STEPS - 1, start + duration);
			faultedInput = input.map((v, t) => (t >= start && t < end ? 0 : v));
			faultRange = { start, end };
			logs = [
				{
					agent: "SYSTEM",
					level: "info",
					thought: `$ ./sim --fault signal_loss --duration ${duration} --start ${start}`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] step ${start}: 信号丢失，输入强制为 0，持续 ${duration} 步`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] step ${end}: 信号恢复`,
				},
				{
					agent: "SYSTEM",
					level: "warn",
					thought:
						"⚠ 信号丢失期间输出保持上一拍（CON-001-FLT-000 故障处理生效）",
				},
				{
					agent: "SYSTEM",
					level: "success",
					thought: "✅ 故障处理契约通过，但输出跟踪误差超阈值",
				},
			];
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
			const amp = params.noise_amplitude ?? 5000;
			faultedInput = input.map((v) =>
				Math.max(
					0,
					Math.min(65535, v + Math.round((Math.random() - 0.5) * 2 * amp)),
				),
			);
			faultRange = { start: 0, end: SIM_STEPS - 1 };
			logs = [
				{
					agent: "SYSTEM",
					level: "info",
					thought: `$ ./sim --fault noise --amplitude ${amp}`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] 全程注入高频噪声，幅度 ±${amp}`,
				},
				{
					agent: "TERMINAL",
					level: "error",
					thought:
						"[sim] step 73: assert(filtered_value == round(alpha*x + (1-alpha)*prev)) FAILED",
				},
				{
					agent: "SYSTEM",
					level: "error",
					thought:
						"❌ 契约违约 [CON-001-POST-001]：噪声破坏 IIR 滤波公式一致性",
				},
			];
			violation = {
				contract_id: "CON-001-POST-001",
				assertion:
					"assert(fabs(filtered_value - (alpha*raw_value + (1-alpha)*prev)) < 1e-6)",
				timestep: 73,
				actual_value: baseOutput[73] ?? 0,
				message: `高频噪声 ±${amp} 导致 IIR 公式浮点精度被破坏（第 73 步触发）`,
			};
			break;
		}
		case "stuck": {
			const stuckVal = params.stuck_value ?? 40000;
			const start = 60;
			faultedInput = input.map((v, t) => (t >= start ? stuckVal : v));
			faultRange = { start, end: SIM_STEPS - 1 };
			logs = [
				{
					agent: "SYSTEM",
					level: "info",
					thought: `$ ./sim --fault stuck --value ${stuckVal} --start ${start}`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] step ${start}: 传感器卡死在 ${stuckVal}`,
				},
				{
					agent: "TERMINAL",
					level: "info",
					thought: `[sim] step ${start + 20}: 输出收敛至 ${Math.round(stuckVal * FILTER_ALPHA + 32768 * (1 - FILTER_ALPHA))}`,
				},
				{
					agent: "SYSTEM",
					level: "warn",
					thought: "⚠ 卡死故障未触发契约违约，但输出已偏离真实信号",
				},
				{
					agent: "SYSTEM",
					level: "info",
					thought: "💡 建议增加余度管理器检测卡死（参考文档余度管理章节）",
				},
			];
			violation = null;
			break;
		}
		case "step": {
			const stepTime = params.step_time ?? 80;
			const stepVal = params.step_value ?? 60000;
			faultedInput = input.map((v, t) => (t >= stepTime ? stepVal : v));
			faultRange = { start: stepTime, end: SIM_STEPS - 1 };
			logs = [
				{
					agent: "SYSTEM",
					level: "info",
					thought: `$ ./sim --fault step --time ${stepTime} --value ${stepVal}`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] step ${stepTime}: 阶跃突变，输入跳变至 ${stepVal}`,
				},
				{
					agent: "TERMINAL",
					level: "error",
					thought: `[sim] step ${stepTime + 1}: assert(filtered_value <= 65535) FAILED → 阶跃导致输出溢出`,
				},
				{
					agent: "SYSTEM",
					level: "error",
					thought: "❌ 契约违约 [CON-001-POST-000]：阶跃突变导致输出越界",
				},
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
		case "saturation": {
			// 饱和截断：输入超出 [lower_limit, upper_limit] 时被截断（设计性限幅，通常不违约）
			const upper = params.upper_limit ?? 60000;
			const lower = params.lower_limit ?? 5000;
			faultedInput = input.map((v) => Math.max(lower, Math.min(upper, v)));
			faultRange = { start: 0, end: SIM_STEPS - 1 };
			logs = [
				{
					agent: "SYSTEM",
					level: "info",
					thought: `$ ./sim --fault saturation --upper ${upper} --lower ${lower}`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] 全程启用饱和限幅，范围 [${lower}, ${upper}]`,
				},
				{
					agent: "TERMINAL",
					level: "info",
					thought: `[sim] step 0: 输入 ${input[0]} 限幅后 ${faultedInput[0]}`,
				},
				{
					agent: "SYSTEM",
					level: "success",
					thought:
						"✅ 设计性限幅生效，输出始终在 uint16 范围内，未触发契约违约",
				},
			];
			violation = null;
			break;
		}
		case "intermittent": {
			// 间歇性故障：周期性（interval 步）出现故障值，持续 duration 步
			const interval = params.interval ?? 20;
			const dur = params.duration ?? 5;
			const faultyVal = 65000; // 故障期间的固定异常值
			faultedInput = input.map((v, t) => {
				const phase = t % interval;
				return phase < dur ? faultyVal : v;
			});
			faultRange = { start: 0, end: SIM_STEPS - 1 };
			const triggerStep = interval; // 第一次故障触发步
			logs = [
				{
					agent: "SYSTEM",
					level: "info",
					thought: `$ ./sim --fault intermittent --interval ${interval} --duration ${dur}`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] step ${triggerStep}: 间歇性故障触发，输入强制为 ${faultyVal}，持续 ${dur} 步`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] step ${triggerStep + dur}: 故障恢复，等待下一周期（${interval} 步）`,
				},
				{
					agent: "SYSTEM",
					level: "warn",
					thought: "⚠ 周期性故障已触发轻度跟踪误差警告，建议增加余度管理器",
				},
			];
			violation = {
				contract_id: "CON-001-POST-001",
				assertion: "assert(fabs(filtered_value - expected) < 1e-6)",
				timestep: triggerStep + 1,
				actual_value: faultyVal,
				message: `间歇性故障在周期 ${triggerStep} 步触发，输入跳变至 ${faultyVal} 导致 IIR 跟踪误差超阈值`,
			};
			break;
		}
		case "drift": {
			// 渐变漂移：从 step 0 开始输入线性增加 drift_rate * t
			const rate = params.drift_rate ?? 500;
			faultedInput = input.map((v, t) =>
				Math.min(65535, Math.max(0, v + rate * t)),
			);
			faultRange = { start: 0, end: SIM_STEPS - 1 };
			// 找出首次溢出步
			const overflowStep = faultedInput.findIndex((v) => v >= 65535);
			const triggerStep = overflowStep > 0 ? overflowStep : SIM_STEPS - 1;
			logs = [
				{
					agent: "SYSTEM",
					level: "info",
					thought: `$ ./sim --fault drift --rate ${rate}`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] step 0: 启动渐变漂移，每步增量 +${rate}`,
				},
				{
					agent: "TERMINAL",
					level: "error",
					thought: `[sim] step ${triggerStep}: assert(filtered_value <= 65535) FAILED → 漂移累积导致输出溢出`,
				},
				{
					agent: "SYSTEM",
					level: "error",
					thought:
						"❌ 契约违约 [CON-001-POST-000]：渐变漂移累积导致输出超出 uint16 范围",
				},
			];
			violation = {
				contract_id: "CON-001-POST-000",
				assertion: "assert(filtered_value <= 65535)",
				timestep: triggerStep,
				actual_value: faultedInput[triggerStep] ?? 65535,
				message: `漂移速率 +${rate}/步累积 ${triggerStep} 步后导致滤波输出溢出 uint16 范围`,
			};
			break;
		}
		case "timeout": {
			// 丢帧/延迟：从 timeout_start 步开始信号冻结（保持上一拍值）
			const start = params.timeout_start ?? 50;
			faultedInput = input.map((v, t) =>
				t >= start ? (input[start - 1] ?? v) : v,
			);
			faultRange = { start, end: SIM_STEPS - 1 };
			logs = [
				{
					agent: "SYSTEM",
					level: "info",
					thought: `$ ./sim --fault timeout --start ${start}`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] step ${start}: 总线超时，输入冻结在 step ${start - 1} 的值 ${input[start - 1] ?? 0}`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] step ${SIM_STEPS - 1}: 信号仍未恢复，持续冻结`,
				},
				{
					agent: "SYSTEM",
					level: "warn",
					thought:
						"⚠ 跟踪误差超出容差 1e-6（CON-001-POST-001），建议增加超时检测与余度切换",
				},
			];
			violation = {
				contract_id: "CON-001-POST-001",
				assertion: "assert(fabs(filtered_value - expected) < 1e-6)",
				timestep: start + 10,
				actual_value: baseOutput[start + 10] ?? 0,
				message: `从 step ${start} 起信号冻结，IIR 跟踪误差超出容差 1e-6`,
			};
			break;
		}
		case "glitch": {
			// 跳变毛刺：随机 glitch_count 个时刻出现 glitch_magnitude 尖峰
			const mag = params.glitch_magnitude ?? 30000;
			const count = params.glitch_count ?? 5;
			// 确定性选取 glitch 时刻：均匀分布在中后段，避免集中在开头
			const glitchSteps = new Set<number>();
			if (count > 0 && SIM_STEPS > 20) {
				const span = SIM_STEPS - 20;
				for (let i = 0; i < count; i++) {
					const step = 10 + Math.floor((span * i) / Math.max(1, count));
					glitchSteps.add(step);
				}
			}
			faultedInput = input.map((v, t) =>
				glitchSteps.has(t) ? Math.min(65535, Math.max(0, v + mag)) : v,
			);
			const sortedSteps = [...glitchSteps].sort((a, b) => a - b);
			const firstStep = sortedSteps[0] ?? 10;
			const lastStep = sortedSteps[sortedSteps.length - 1] ?? SIM_STEPS - 1;
			faultRange = { start: firstStep, end: lastStep };
			logs = [
				{
					agent: "SYSTEM",
					level: "info",
					thought: `$ ./sim --fault glitch --magnitude ${mag} --count ${count}`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] 注入 ${count} 次毛刺，幅度 +${mag}，时刻 [${sortedSteps.join(", ")}]`,
				},
				{
					agent: "TERMINAL",
					level: "error",
					thought: `[sim] step ${firstStep}: assert(filtered_value <= 65535) FAILED → 毛刺尖峰导致瞬时溢出`,
				},
				{
					agent: "SYSTEM",
					level: "error",
					thought: "❌ 契约违约 [CON-001-POST-000]：毛刺尖峰触发偶发输出越界",
				},
			];
			violation = {
				contract_id: "CON-001-POST-000",
				assertion: "assert(filtered_value <= 65535)",
				timestep: firstStep,
				actual_value: faultedInput[firstStep] ?? 0,
				message: `毛刺幅度 +${mag} 在 step ${firstStep} 触发瞬时输出溢出 uint16 范围`,
			};
			break;
		}
		case "stuck_zero": {
			// 零输出：从 stuck_start 步开始输入恒为 0
			const start = params.stuck_start ?? 40;
			faultedInput = input.map((v, t) => (t >= start ? 0 : v));
			faultRange = { start, end: SIM_STEPS - 1 };
			logs = [
				{
					agent: "SYSTEM",
					level: "info",
					thought: `$ ./sim --fault stuck_zero --start ${start}`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] step ${start}: 传感器完全失效，输入恒为 0`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] step ${start + 20}: 输出持续向 0 收敛，跟踪误差累积`,
				},
				{
					agent: "SYSTEM",
					level: "warn",
					thought:
						"⚠ 跟踪误差超出容差（CON-001-POST-001），建议余度管理器切换到备份传感器",
				},
			];
			violation = {
				contract_id: "CON-001-POST-001",
				assertion: "assert(fabs(filtered_value - expected) < 1e-6)",
				timestep: start + 5,
				actual_value: baseOutput[start + 5] ?? 0,
				message: `从 step ${start} 起输入恒为 0，IIR 输出跟踪误差超出容差 1e-6`,
			};
			break;
		}
		case "polarity": {
			// 符号反转：全程信号取反（× -1），可能产生负值
			faultedInput = input.map((v) => -v);
			faultRange = { start: 0, end: SIM_STEPS - 1 };
			logs = [
				{
					agent: "SYSTEM",
					level: "info",
					thought: `$ ./sim --fault polarity`,
				},
				{
					agent: "TERMINAL",
					level: "warn",
					thought: `[sim] step 0: 极性反转，输入 × -1 = ${faultedInput[0]}`,
				},
				{
					agent: "TERMINAL",
					level: "error",
					thought: `[sim] step 0: assert(filtered_value >= 0) FAILED → 负值违反 uint16 范围契约`,
				},
				{
					agent: "SYSTEM",
					level: "error",
					thought:
						"❌ 契约违约 [CON-001-POST-000]：符号反转导致输入/输出为负，违反 uint16 范围",
				},
			];
			violation = {
				contract_id: "CON-001-POST-000",
				assertion: "assert(filtered_value >= 0 && filtered_value <= 65535)",
				timestep: 0,
				actual_value: faultedInput[0],
				message: `符号反转导致输入 ${input[0]} → ${faultedInput[0]}，违反 uint16 非负范围契约`,
			};
			break;
		}
	}

	let finalOutput: number[];
	if (
		faultType === "stuck" ||
		faultType === "step" ||
		faultType === "bias" ||
		// 限幅/噪声/漂移/毛刺类故障：直接对 faultedInput 做低通滤波
		faultType === "noise" ||
		faultType === "saturation" ||
		faultType === "intermittent" ||
		faultType === "drift" ||
		faultType === "glitch"
	) {
		finalOutput = lowpassFilter(faultedInput, FILTER_ALPHA);
	} else if (faultType === "polarity") {
		// 符号反转：负值不能进入 uint16，强制截断到 0 后再滤波
		finalOutput = lowpassFilter(
			faultedInput.map((v) => Math.max(0, v)),
			FILTER_ALPHA,
		);
	} else {
		// signal_loss / timeout / stuck_zero：保持上一拍值（CON-001-FLT-000 故障处理生效）
		finalOutput = [...baseOutput];
		if (faultRange) {
			for (
				let t = faultRange.start;
				t <= faultRange.end && t < finalOutput.length;
				t++
			) {
				finalOutput[t] = finalOutput[faultRange.start - 1] ?? 0;
			}
		}
	}

	return { faultedInput, faultRange, violation, logs, finalOutput };
}

// ===================== 组合仿真 =====================

/** 根据连接方式选择 mock 组合代码 */
export function pickComposedCode(connection: ComposeConnection): string {
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
export function buildCompatibility(
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
			reason:
				connection === "feedback"
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
