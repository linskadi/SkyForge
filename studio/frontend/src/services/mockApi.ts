/**
 * SkyForge Mock API 服务
 * 后端 API 尚未完成时，用 mock 数据跑通前端流程
 * 参考文档 11.2.1 节时间轴
 *
 * 仅包含 mock API 函数（带人工延迟的 Promise）。
 * 数据常量 → @/mock/data.ts
 * 仿真逻辑 → ./simulation.ts
 * 报告生成 → ./reportGenerator.ts
 * 类型定义 → @/types/domain.ts
 */

import type {
	AgentLog,
	CompatibilityResult,
	ComposeConnection,
	ComposeResult,
	ContractCheckResult,
	FaultParams,
	FaultType,
	GenerateResult,
	HILApproval,
	HILHistoryItem,
	LLMModel,
	LLMStatus,
	MisraRule,
	RepairResult,
	ReportResult,
	ScadeParseResult,
	SimulationResult,
} from "@/types/domain";
import type {
	VerificationCheck,
	VerificationResult,
	VerifyRequest,
} from "@/types/verification";

// Re-export all types for backward compatibility
export type {
	AgentLog,
	AgentType,
	LogLevel,
	Contract,
	ContractCondition,
	ContractCheckResult,
	ContractViolation,
	FaultParams,
	FaultType,
	GenerateResult,
	MisraViolation,
	RepairIteration,
	SimulationResult,
	SimulationStatistics,
	ComposeConnection,
	ComposeResult,
	CompatibilityResult,
	CompatibilityCheckItem,
	LLMStatus,
	LLMModel,
	ScadeVariable,
	ScadeEquation,
	ScadeParseResult,
	HILApproval,
	HILHistoryItem,
	HILCheckpointType,
	ReportSummary,
	ReportResult,
	MisraRule,
	RepairResult,
} from "@/types/domain";

// Re-export verification types for backward compatibility
export type {
	VerifyRequest,
	VerificationCheck,
	VerificationResult,
	VerificationStatus,
} from "@/types/verification";

// ===================== 数据常量导入 =====================
import {
	MOCK_AGENT_LOGS,
	MOCK_API_BASE_URL,
	MOCK_CODE,
	MOCK_CONTRACT,
	MOCK_CONTRACT_CHECK_RESULT,
	MOCK_HIL_PENDING,
	MOCK_HP_CODE,
	MOCK_HP_CONTRACT,
	MOCK_LLM_STATUS,
	MOCK_LP_CODE,
	MOCK_LP_CONTRACT,
	MOCK_MISRA_RULES,
	MOCK_REPAIR_HISTORY,
	MOCK_SIM_LOGS,
	MOCK_TRACEABILITY,
	MOCK_VIOLATIONS,
	SIM_STEPS,
} from "@/mock/data";

// Re-export data constants for backward compatibility
export {
	EXAMPLE_REQUIREMENTS,
	MISRA_RULE_DOCS,
} from "@/mock/data";

// Re-export preset code/contract aliases
export const PRESET_LP_CODE = MOCK_LP_CODE;
export const PRESET_LP_CONTRACT = MOCK_LP_CONTRACT;
export const PRESET_HP_CODE = MOCK_HP_CODE;
export const PRESET_HP_CONTRACT = MOCK_HP_CONTRACT;

// ===================== 仿真逻辑导入 =====================
import {
	buildCompatibility,
	computeStats,
	generateNormalSimulationResult,
	pickComposedCode,
	runFaultInjection,
} from "./simulation";

// ===================== 报告生成导入 =====================
import { buildReport } from "./reportGenerator";

// ===================== 辅助数据 =====================

/** 当前 LLM 状态（响应式副本，便于 mock 切换） */
let mockLLMState: LLMStatus = { ...MOCK_LLM_STATUS };

/** mock 的正常仿真结果（无故障，200 步，契约全部通过） */
const MOCK_SIMULATION_RESULT: SimulationResult =
	generateNormalSimulationResult(MOCK_SIM_LOGS);

/** mock HIL 待审批列表（运行时可变） */
const mockHILPending: HILApproval[] = MOCK_HIL_PENDING.map((item) => ({
	...item,
	submitted_at: Date.now() - 1000 * 60 * 5,
	deadline: Date.now() + 1000 * 60 * 25,
}));

/** mock HIL 审批历史 */
const mockHILHistory: HILHistoryItem[] = [];

// ===================== Mock API 函数 =====================

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
 * 故障注入仿真：根据故障类型生成对应的故障波形和仿真结果
 */
export function mockSimulate(
	faultType: FaultType,
	params: FaultParams,
): Promise<SimulationResult> {
	console.log(
		"[mockApi] 调用 mockSimulate，故障类型：",
		faultType,
		"参数：",
		params,
	);
	return new Promise((resolve) => {
		setTimeout(() => {
			const { faultedInput, faultRange, violation, logs, finalOutput } =
				runFaultInjection(faultType, params);
			resolve({
				passed: violation === null,
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

/**
 * 模拟 WebSocket 推送 6 个 Agent 的思考日志
 */
export function mockAgentStream(
	onLog: (log: AgentLog) => void,
	onDone?: () => void,
): () => void {
	let stopped = false;
	let timer: ReturnType<typeof setTimeout> | null = null;

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

	next(0);

	return () => {
		stopped = true;
		if (timer) clearTimeout(timer);
	};
}

/**
 * 真实 WebSocket 连接（后端完成后启用）
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

/**
 * mock 组件组合验证
 */
export function mockCompose(
	compA: string,
	compB: string,
	connection: ComposeConnection,
): Promise<ComposeResult> {
	console.log(
		"[mockApi] 调用 mockCompose，组件A:",
		compA,
		"组件B:",
		compB,
		"连接:",
		connection,
	);
	return new Promise((resolve) => {
		setTimeout(() => {
			const composedCode = pickComposedCode(connection);
			const compatibility = buildCompatibility(compA, compB, connection);

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
				{
					agent: "SYSTEM",
					level: "info",
					thought: "$ gcc -c composed.c -o composed.o",
				},
				{ agent: "SYSTEM", level: "success", thought: "组合代码编译通过" },
				{
					agent: "SYSTEM",
					level: "info",
					thought: "$ ./composed_sim --steps 100",
				},
				{
					agent: "TERMINAL",
					level: "success",
					thought: "[sim] 全部 100 步仿真完成",
				},
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
					input_range: [
						input.reduce((a, b) => Math.min(a, b), Number.POSITIVE_INFINITY),
						input.reduce((a, b) => Math.max(a, b), Number.NEGATIVE_INFINITY),
					],
					output_range: [
						output.reduce((a, b) => Math.min(a, b), Number.POSITIVE_INFINITY),
						output.reduce((a, b) => Math.max(a, b), Number.NEGATIVE_INFINITY),
					],
					output_max: output.reduce(
						(a, b) => Math.max(a, b),
						Number.NEGATIVE_INFINITY,
					),
					output_min: output.reduce(
						(a, b) => Math.min(a, b),
						Number.POSITIVE_INFINITY,
					),
					output_mean: Math.round(
						output.reduce((s, v) => s + v, 0) / output.length,
					),
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
			const extractName = (yaml: string): string => {
				const m = yaml.match(/component:\s*(\S+)/);
				return m ? m[1] : "Component";
			};
			resolve(
				buildCompatibility(
					extractName(contractA),
					extractName(contractB),
					connection,
				),
			);
		}, 600);
	});
}

/**
 * mock 获取 LLM 状态
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
 */
export function mockSwitchLLM(useLLM: boolean): Promise<LLMStatus> {
	console.log("[mockApi] 调用 mockSwitchLLM，启用 LLM:", useLLM);
	return new Promise((resolve) => {
		setTimeout(() => {
			mockLLMState = {
				...mockLLMState,
				use_llm: useLLM,
				available: useLLM,
			};
			resolve({ ...mockLLMState });
		}, 400);
	});
}

/**
 * mock 获取可用模型列表
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
 */
export function mockUploadScade(file: File): Promise<ScadeParseResult> {
	console.log(
		"[mockApi] 调用 mockUploadScade，文件名:",
		file.name,
		"大小:",
		file.size,
	);
	return new Promise((resolve) => {
		setTimeout(() => {
			resolve({
				node_name: "LowPassFilter",
				inputs: [
					{ name: "raw_value", type: "uint16", description: "原始 ADC 采样值" },
					{ name: "sample_rate", type: "uint16", description: "采样率 (Hz)" },
				],
				outputs: [
					{
						name: "filtered_value",
						type: "uint16",
						description: "滤波后输出值",
					},
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
					'    expression: "sample_rate > 0"\n' +
					"    description: 采样率必须大于 0\n" +
					"postconditions:\n" +
					"  - id: CON-LP-POST-000\n" +
					'    expression: "0 <= filtered_value <= 65535"\n' +
					"    description: 输出值在 uint16 范围内\n" +
					"invariants:\n" +
					"  - id: CON-LP-INV-000\n" +
					'    expression: "0.0 <= alpha <= 1.0"\n' +
					"    description: 滤波系数 alpha 始终在 [0,1] 范围\n",
				source_file: file.name,
			});
		}, 1000);
	});
}

/**
 * mock 获取待审批列表
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
 */
export function mockApprove(
	requestId: string,
	comments: string,
): Promise<{ success: boolean; reviewer: string; reviewed_at: number }> {
	console.log(
		"[mockApi] 调用 mockApprove，requestId:",
		requestId,
		"comments:",
		comments,
	);
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
 */
export function mockReject(
	requestId: string,
	comments: string,
): Promise<{ success: boolean; reviewer: string; reviewed_at: number }> {
	console.log(
		"[mockApi] 调用 mockReject，requestId:",
		requestId,
		"comments:",
		comments,
	);
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
 */
export function mockGenerateReport(
	result: GenerateResult,
): Promise<ReportResult> {
	console.log("[mockApi] 调用 mockGenerateReport，输入结果:", result);
	return new Promise((resolve) => {
		setTimeout(() => {
			const { reportId, summary, html } = buildReport(result);
			resolve({
				report_id: reportId,
				html,
				summary,
			});
		}, 1500);
	});
}

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
	_contract: string,
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
	_contract: string,
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

/** mock 生成报告（接受 pipelineResult 任意对象） */
export function mockGenerateReportByPipeline(
	pipelineResult: Record<string, unknown>,
): Promise<ReportResult> {
	console.log("[mockApi] 调用 mockGenerateReportByPipeline");
	if (pipelineResult?.contract && pipelineResult.code) {
		return mockGenerateReport(pipelineResult as unknown as GenerateResult);
	}
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

/**
 * mock 形式化验证契约
 *
 * 模拟一个典型场景：5 项检查中 4 项通过、1 项失败、1 项跳过，
 * 用于前端独立演示形式化验证结果展示（无需后端 / Z3 / CBMC）。
 *
 * @param payload 契约数据（mock 模式下仅用于日志展示）
 */
export function mockVerifyContract(
	payload: VerifyRequest,
): Promise<VerificationResult> {
	console.log(
		"[mockApi] 调用 mockVerifyContract，contract 长度:",
		payload?.contract?.length ?? 0,
		"contract_path:",
		payload?.contract_path ?? "(none)",
	);
	const checks: VerificationCheck[] = [
		{
			name: "Type range constraints",
			status: "passed",
			duration_ms: 23,
			counter_example: null,
			tool: "Z3",
		},
		{
			name: "Boundary conditions",
			status: "passed",
			duration_ms: 11,
			counter_example: null,
			tool: "Z3",
		},
		{
			name: "Null pointer safety",
			status: "failed",
			duration_ms: 45,
			counter_example: "ptr=null, expected=non-null",
			tool: "Z3",
		},
		{
			name: "Array bounds",
			status: "passed",
			duration_ms: 18,
			counter_example: null,
			tool: "Z3",
		},
		{
			name: "Arithmetic overflow",
			status: "skipped",
			duration_ms: 0,
			counter_example: "requires CBMC",
			tool: "CBMC",
		},
	];
	const passed = checks.filter((c) => c.status === "passed").length;
	const failed = checks.filter((c) => c.status === "failed").length;
	const skipped = checks.filter((c) => c.status === "skipped").length;
	const totalDuration = checks.reduce((s, c) => s + c.duration_ms, 0);
	const result: VerificationResult = {
		status: failed > 0 ? "failed" : "passed",
		summary: {
			total: checks.length,
			passed,
			failed,
			skipped,
		},
		checks,
		total_duration_ms: totalDuration,
		tool: "Z3",
	};
	return new Promise((resolve) => {
		setTimeout(() => resolve(result), 900);
	});
}
