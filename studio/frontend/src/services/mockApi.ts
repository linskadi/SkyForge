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
	AgentType,
	CompatibilityResult,
	ComposeConnection,
	ComposeResult,
	DashboardTaskRecord,
	FaultParams,
	FaultType,
	GenerateResult,
	HITLApproval,
	HITLHistoryItem,
	LogLevel,
	MisraRule,
	ReportResult,
	RuleStandard,
	SimulationResult,
} from "@/types/domain";
import type {
	VerificationCheck,
	VerificationResult,
	VerifyRequest,
} from "@/types/verification";
import type {
	ApiClient,
	ComposeInput,
	LLMConfig,
	LLMTestResult,
} from "./apiProtocol";

// Re-export all types for backward compatibility
export type {
	AgentLog,
	AgentType,
	CompatibilityCheckItem,
	CompatibilityResult,
	ComposeConnection,
	ComposeResult,
	Contract,
	ContractCheckResult,
	ContractCondition,
	ContractViolation,
	FaultParams,
	FaultType,
	GenerateResult,
	HITLApproval,
	HITLCheckpointType,
	HITLHistoryItem,
	LogLevel,
	MisraRule,
	MisraViolation,
	RepairIteration,
	ReportResult,
	ReportSummary,
	RuleStandard,
	ScadeEquation,
	ScadeVariable,
	SimulationResult,
	SimulationStatistics,
} from "@/types/domain";

// Re-export verification types for backward compatibility
export type {
	VerificationCheck,
	VerificationResult,
	VerificationStatus,
	VerifyRequest,
} from "@/types/verification";

// ===================== 数据常量导入 =====================
import {
	MOCK_AGENT_LOGS,
	MOCK_API_BASE_URL,
	MOCK_CODE,
	MOCK_CODE_CPP_PID,
	MOCK_CODE_PY_PREPROCESS,
	MOCK_CONTRACT,
	MOCK_CONTRACT_CHECK_RESULT,
	MOCK_HITL_PENDING,
	MOCK_HP_CODE,
	MOCK_HP_CONTRACT,
	MOCK_LP_CODE,
	MOCK_LP_CONTRACT,
	MOCK_MISRA_CPP_RULES,
	MOCK_MISRA_RULES,
	MOCK_PYTHON_SAFETY_RULES,
	MOCK_REPAIR_HISTORY,
	MOCK_RULE_STANDARDS,
	MOCK_SIM_LOGS,
	MOCK_TRACEABILITY,
	MOCK_VIOLATIONS,
	SIM_STEPS,
} from "@/mock/data";

// Re-export data constants for backward compatibility
export {
	EXAMPLE_REQUIREMENTS,
	MISRA_RULE_DOCS,
	MOCK_AGENT_LOGS,
	MOCK_CODE,
	MOCK_CODE_CPP_PID,
	MOCK_CODE_PY_PREPROCESS,
	MOCK_CONTRACT,
	MOCK_CONTRACT_CHECK_RESULT,
	MOCK_HITL_PENDING,
	MOCK_HP_CODE,
	MOCK_HP_CONTRACT,
	MOCK_LP_CODE,
	MOCK_LP_CONTRACT,
	MOCK_MISRA_CPP_RULES,
	MOCK_MISRA_RULES,
	MOCK_PYTHON_SAFETY_RULES,
	MOCK_REPAIR_HISTORY,
	MOCK_RULE_STANDARDS,
	MOCK_SIM_LOGS,
	MOCK_TRACEABILITY,
	MOCK_VIOLATIONS,
	SIM_STEPS,
} from "@/mock/data";

// Re-export preset code/contract aliases
export const PRESET_LP_CODE = MOCK_LP_CODE;
export const PRESET_LP_CONTRACT = MOCK_LP_CONTRACT;
export const PRESET_HP_CODE = MOCK_HP_CODE;
export const PRESET_HP_CONTRACT = MOCK_HP_CONTRACT;

// ===================== 报告生成导入 =====================
import { buildReport } from "./reportGenerator";
// ===================== 仿真逻辑导入 =====================
import {
	buildCompatibility,
	computeStats,
	generateNormalSimulationResult,
	pickComposedCode,
	runFaultInjection,
} from "./simulation";

// ===================== 辅助数据 =====================

/** mock 的正常仿真结果（无故障，200 步，契约全部通过） */
const MOCK_SIMULATION_RESULT: SimulationResult =
	generateNormalSimulationResult(MOCK_SIM_LOGS);

/** mock HITL 待审批列表（运行时可变） */
const mockHITLPending: HITLApproval[] = MOCK_HITL_PENDING.map((item) => ({
	...item,
	submitted_at: Date.now() - 1000 * 60 * 5,
	deadline: Date.now() + 1000 * 60 * 25,
}));

/** mock HITL 审批历史 */
const mockHITLHistory: HITLHistoryItem[] = [];

// ===================== Mock API 函数 =====================

/**
 * Mock Agent 流的日志推送间隔（秒）。
 *
 * 由 mockAgentStream 与 mockGenerate 共享，确保 mockGenerate 的延迟与
 * mockAgentStream 全部日志推送完毕的总时长一致，避免出现"Agent 还在思考、
 * 结果已显示"的时序错乱。详见 SkyForge Spec 修复 A Task 3。
 */
export const MOCK_AGENT_INTERVAL_SEC = 1.5;

/**
 * Mock Agent 流的总播放时长（毫秒）= 日志条数 × 间隔。
 *
 * mockGenerate 等待此时长后再 resolve，使结果展示与 AgentTerminal 日志播放同步。
 */
export const MOCK_AGENT_TOTAL_DURATION_MS =
	MOCK_AGENT_INTERVAL_SEC * MOCK_AGENT_LOGS.length * 1000;

/** 生成结果：模拟 POST /api/generate 的响应
 *
 * 延迟与 mockAgentStream 的总播放时长一致，确保 AgentTerminal 日志播放完毕后才显示结果。
 *
 * 参数回显（T3.1）：mock 模式下用户选择的 scadeFile/language 会参与生成结果：
 * - 代码顶部注入 `// mock: language=..., scadeFile=..., requirement=...` 注释，
 *   使 mock 结果与用户选项可见地关联（不再"完全不参与生成"）。
 * - 根据 language 选择不同 mock 代码模板：
 *   - c → 一阶低通滤波器（默认，使用 MOCK_CODE）
 *   - cpp → PID 控制器（MOCK_CODE_CPP_PID）
 *   - python → 数据预处理函数（MOCK_CODE_PY_PREPROCESS）
 *   - 其他 → 默认低通滤波器
 * - degraded 固定为 false：mock 模式不触发 LLM 降级路径（T3.2）。
 */
export function mockGenerate(
	requirement: string,
	scadeFile?: string,
	language = "c",
): Promise<GenerateResult> {
	const lang = language || "c";
	console.log(
		"[mockApi] 调用 mockGenerate，需求：",
		requirement,
		"语言:",
		lang,
		"scadeFile:",
		scadeFile ? "provided" : "none",
	);
	const originalMockCode = pickMockCodeByLanguage(lang);
	const header = `// mock: language=${lang}, scadeFile=${scadeFile ? "provided" : "none"}, requirement=${requirement.slice(0, 50)}`;
	const code = `${header}\n${originalMockCode}`;
	return new Promise((resolve) => {
		setTimeout(() => {
			resolve({
				contract: MOCK_CONTRACT,
				code,
				violations: MOCK_VIOLATIONS,
				traceability: MOCK_TRACEABILITY,
				repair_history: MOCK_REPAIR_HISTORY,
				contract_check_result: MOCK_CONTRACT_CHECK_RESULT,
				simulation_result: MOCK_SIMULATION_RESULT,
				degraded: false,
			});
		}, MOCK_AGENT_TOTAL_DURATION_MS);
	});
}

/**
 * 根据目标语言选择对应的 mock 代码模板（T3.1）
 *
 * - c → 一阶低通滤波器（默认）
 * - cpp → PID 控制器
 * - python → 数据预处理函数
 * - 其他 → 默认低通滤波器
 */
export function pickMockCodeByLanguage(language: string): string {
	switch (language) {
		case "cpp":
			return MOCK_CODE_CPP_PID;
		case "python":
			return MOCK_CODE_PY_PREPROCESS;
		default:
			return MOCK_CODE;
	}
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
 * WebSocket complete 信号携带的数据
 *
 * 由 `connectAgentStream` 在收到后端 `level: "complete"` 消息时填充并透传给
 * `onDone` 回调；`mockAgentStream` 不会填充此 payload（mock 模式无 result）。
 * `result` 字段结构与后端 `run_full_pipeline` 返回值一致，可用于 HTTP 失败时
 * 的降级 fallback。
 */
export interface StreamCompletePayload {
	result?: unknown;
	degraded?: boolean;
}

/**
 * 默认 WebSocket URL：优先使用环境变量 VITE_WS_URL（须包含完整路径），
 * 否则基于当前页面 location.host 拼接 `/ws/agent-stream`，适配 dev proxy 与生产同源部署。
 *
 * .. deprecated::
 *   ``/ws/agent-stream`` is deprecated. New code should connect to the V1
 *   task events socket at ``/api/v1/tasks/{task_id}/events`` via
 *   ``connectV1TaskEvents``. This constant is kept for one release as a
 *   fallback for clients that have not migrated yet.
 */
export const DEFAULT_WS_URL =
	import.meta.env.VITE_WS_URL || `ws://${location.host}/ws/agent-stream`;

/**
 * 模拟 WebSocket 推送 6 个 Agent 的思考日志
 */
export function mockAgentStream(
	onLog: (log: AgentLog) => void,
	onDone?: (data?: StreamCompletePayload) => void,
): () => void {
	let stopped = false;
	let timer: ReturnType<typeof setTimeout> | null = null;

	const interval = MOCK_AGENT_INTERVAL_SEC;

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
 *
 * 两种模式：
 * - 生成模式（默认）：发送 `{requirement, language}` 触发后端 `/ws/agent-stream` 新 pipeline。
 * - 订阅模式：传入 `taskId` 时发送 `{task_id, action: "subscribe"}` 订阅已有运行中的 task，
 *   不启动新 pipeline。立即收到历史日志回放，并继续接收实时输出。
 *
 * 兼容多种后端消息字段：agent/agent_name、thought/message/content、level/type=complete。
 *
 * complete 信号处理：当收到 `level: "complete"` 或 `type: "complete"` 消息时，
 * 把后端透传的 `result` / `degraded` 字段通过 onDone 回调返回给调用方，
 * 供 Generate.vue 在 HTTP 失败时作为降级 fallback 使用。
 */
export function connectAgentStream(
	onLog: (log: AgentLog) => void,
	onDone?: (data?: StreamCompletePayload) => void,
	wsUrl: string = DEFAULT_WS_URL,
	requirement?: string,
	language = "c",
	taskId?: string,
): () => void {
	let stopped = false;
	let ws: WebSocket | null = null;
	try {
		ws = new WebSocket(wsUrl);
	} catch (err) {
		console.error("[mockApi] WebSocket 创建失败：", err);
		onDone?.();
		return () => {};
	}

	ws.onopen = () => {
		console.log("[mockApi] WebSocket 已连接:", wsUrl);
		// 订阅模式：发送 {task_id, action: "subscribe"} 不启动新 pipeline
		if (taskId) {
			ws?.send(JSON.stringify({ task_id: taskId, action: "subscribe" }));
			console.log(`[mockApi] 已发送订阅请求: task_id=${taskId}`);
			return;
		}
		// 生成模式：发送 requirement 触发后端独立 pipeline
		if (requirement) {
			ws?.send(JSON.stringify({ requirement, language }));
		}
	};

	ws.onmessage = (event) => {
		if (stopped) return;
		try {
			const data = JSON.parse(event.data) as {
				agent?: AgentType;
				agent_name?: AgentType;
				level?: string;
				type?: string;
				thought?: string;
				message?: string;
				content?: string;
				time?: number;
				result?: unknown;
				degraded?: boolean;
			};
			// 兼容现有消息格式：complete 信号触发结束并透传 result/degraded 字段
			if (data.level === "complete" || data.type === "complete") {
				onDone?.({ result: data.result, degraded: data.degraded });
				return;
			}
			onLog({
				agent: data.agent ?? data.agent_name ?? "SYSTEM",
				level: (data.level ?? "info") as LogLevel,
				thought: data.thought ?? data.message ?? data.content ?? "",
				ts: data.time ?? Date.now(),
			});
		} catch (err) {
			console.warn("[mockApi] 消息解析失败：", err);
		}
	};

	ws.onerror = (err) => {
		console.error("[mockApi] WebSocket 错误：", err);
	};

	ws.onclose = () => {
		console.log("[mockApi] WebSocket 已关闭");
		if (!stopped) onDone?.();
	};

	return () => {
		stopped = true;
		if (ws && ws.readyState === WebSocket.OPEN) {
			ws.close();
		}
	};
}

/**
 * V1 task events WebSocket 连接（Phase 5 优先通道）
 *
 * 通过 `wsBase/api/v1/tasks/{task_id}/events?after_seq=...` 订阅指定 task 的
 * 事件流。该通道为单一实时事件通道，**推荐替代** ``/ws/agent-stream``。
 *
 * 行为：
 * - 收到后端透传的 V1 事件对象，转换为 `AgentLog` 推送给 `onLog`。
 * - 收到 `type === "complete"` 事件时填充 `result/degraded` 并通过 `onDone` 回调。
 * - 支持 `afterSeq` 从指定 seq 之后重放（断线重连场景）。
 * - 不会触发新 pipeline；pipeline 由 POST `/api/v1/tasks` 启动。
 */
export function connectV1TaskEvents(
	taskId: string,
	onLog: (log: AgentLog) => void,
	onDone?: (data?: StreamCompletePayload) => void,
	afterSeq = 0,
	wsBaseOverride?: string,
	onFirstMessage?: () => void,
): () => void {
	let stopped = false;
	let ws: WebSocket | null = null;
	let firstMessageFired = false;
	// 优先使用 VITE_API_BASE_URL；缺省时退回 location.host（dev proxy / 同源部署）。
	const apiBase =
		wsBaseOverride ??
		(import.meta.env.VITE_API_BASE_URL as string | undefined) ??
		`http://${location.host}`;
	const wsBase = apiBase.replace(/^http/, "ws");
	const url = `${wsBase}/api/v1/tasks/${encodeURIComponent(taskId)}/events?after_seq=${afterSeq}`;
	try {
		ws = new WebSocket(url);
	} catch (err) {
		console.error("[mockApi] V1 WebSocket 创建失败：", err);
		onDone?.();
		return () => {};
	}

	ws.onopen = () => {
		console.log("[mockApi] V1 WebSocket 已连接:", url);
	};

	ws.onmessage = (event) => {
		if (stopped) return;
		if (!firstMessageFired) {
			firstMessageFired = true;
			onFirstMessage?.();
		}
		try {
			const data = JSON.parse(event.data) as {
				agent?: AgentType;
				level?: string;
				type?: string;
				stage?: string;
				message?: string;
				thought?: string;
				created_at?: string;
				result?: unknown;
				task?: { result?: unknown };
				degraded?: boolean;
			};
			if (data.type === "complete" || data.level === "complete") {
				// V1 complete: result 嵌套在 data.task.result 中
				onDone?.({
					result: data.result ?? data.task?.result,
					degraded: data.degraded,
				});
				return;
			}
			onLog({
				agent: data.agent ?? "SYSTEM",
				level: ((data.level as LogLevel) ?? "info") as LogLevel,
				thought: data.message ?? data.thought ?? `[${data.stage ?? "stage"}]`,
				ts: data.created_at ? Date.parse(data.created_at) : Date.now(),
			});
		} catch (err) {
			console.warn("[mockApi] V1 消息解析失败：", err);
		}
	};

	ws.onerror = (err) => {
		console.error("[mockApi] V1 WebSocket 错误：", err);
	};

	ws.onclose = () => {
		console.log("[mockApi] V1 WebSocket 已关闭");
		// 不在此处调 onDone：只在收到完整 complete 消息时才算完成。
		// WS 关闭（任务未完成/已完成但 WS 连晚了）由 AgentTerminal 的 5s fallback 或重试机制处理。
	};

	return () => {
		stopped = true;
		if (ws && ws.readyState === WebSocket.OPEN) {
			ws.close();
		}
	};
}

/**
 * 通过 V1 通道创建 task 并订阅 events（Phase 5 推荐路径）。
 *
 * 先 POST `/api/v1/tasks` 拿到 `task_id`，再连接 V1 events WebSocket。
 * 返回 disconnect 函数与 task_id，方便 UI 在重置/卸载时清理。
 *
 * @returns ``{ taskId, stop }``；taskId 在创建失败时为 null。
 */
export async function createTaskAndSubscribeV1(
	requirement: string,
	language: "c" | "cpp" | "python",
	profileId: "cloud" | "local" = "local",
	onLog: (log: AgentLog) => void,
	onDone?: (data?: StreamCompletePayload) => void,
	onFirstMessage?: () => void,
): Promise<{ taskId: string | null; stop: () => void }> {
	try {
		const { postJSON } = await import("@/services/client");
		const idempotencyKey = `studio-${Date.now()}-${Math.random()
			.toString(36)
			.slice(2, 10)}`;
		const handle = await postJSON<{ id: string; events_url?: string }>(
			"/api/v1/tasks",
			{
				requirement,
				language,
				profile_id: profileId,
				idempotency_key: idempotencyKey,
			},
		);
		if (!handle?.id) {
			onDone?.();
			return { taskId: null, stop: () => {} };
		}
		const stop = connectV1TaskEvents(
			handle.id,
			onLog,
			onDone,
			0,
			undefined,
			onFirstMessage,
		);
		return { taskId: handle.id, stop };
	} catch (err) {
		console.error("[mockApi] V1 创建任务失败：", err);
		onDone?.();
		return { taskId: null, stop: () => {} };
	}
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
 * mock 获取待审批列表
 */
export function mockGetPendingApprovals(): Promise<HITLApproval[]> {
	console.log("[mockApi] 调用 mockGetPendingApprovals");
	return new Promise((resolve) => {
		setTimeout(() => {
			resolve([...mockHITLPending]);
		}, 300);
	});
}

/**
 * mock 批准 HITL 请求
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
			const idx = mockHITLPending.findIndex((p) => p.request_id === requestId);
			if (idx >= 0) {
				const item = mockHITLPending[idx];
				mockHITLPending.splice(idx, 1);
				mockHITLHistory.unshift({
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
 * mock 拒绝 HITL 请求
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
			const idx = mockHITLPending.findIndex((p) => p.request_id === requestId);
			if (idx >= 0) {
				const item = mockHITLPending[idx];
				mockHITLPending.splice(idx, 1);
				mockHITLHistory.unshift({
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
 * mock 获取 HITL 审批历史
 */
export function mockGetHITLHistory(): Promise<HITLHistoryItem[]> {
	console.log("[mockApi] 调用 mockGetHITLHistory");
	return new Promise((resolve) => {
		setTimeout(() => {
			resolve([...mockHITLHistory]);
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

/**
 * mock 搜索指定规则集的规则
 *
 * 根据 standardId 返回对应规则集的 mock 数据：
 * - misra_c_2012：MISRA-C:2012 规则
 * - jsf_av_cpp：MISRA-C++ / JSF AV C++ 规则
 * - python_safety：Python 军工规范规则
 */
export function mockSearchRules(
	query: string,
	standardId?: string,
): Promise<MisraRule[]> {
	console.log(
		"[mockApi] 调用 mockSearchRules，查询：",
		query,
		"规则集：",
		standardId,
	);
	return new Promise((resolve) => {
		setTimeout(() => {
			// 根据规则集 ID 选择对应 mock 数据
			let pool: MisraRule[];
			switch (standardId) {
				case "jsf_av_cpp":
					pool = MOCK_MISRA_CPP_RULES;
					break;
				case "python_safety":
					pool = MOCK_PYTHON_SAFETY_RULES;
					break;
				default:
					pool = MOCK_MISRA_RULES;
					break;
			}
			const q = query.trim().toLowerCase();
			if (!q) {
				resolve([...pool]);
				return;
			}
			const filtered = pool.filter(
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

/** mock 获取所有可用规则集列表 */
export function mockGetRuleStandards(): Promise<RuleStandard[]> {
	console.log("[mockApi] 调用 mockGetRuleStandards");
	return new Promise((resolve) => {
		setTimeout(() => {
			resolve([...MOCK_RULE_STANDARDS]);
		}, 200);
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
			resolve([
				"bias",
				"signal_loss",
				"noise",
				"stuck",
				"step",
				"saturation",
				"intermittent",
				"drift",
				"timeout",
				"glitch",
				"stuck_zero",
				"polarity",
			]);
		}, 200);
	});
}

/** mock 生成报告（接受 pipelineResult 任意对象） */
export function mockGenerateReportByPipeline(
	pipelineResult: GenerateResult,
): Promise<ReportResult> {
	console.log("[mockApi] 调用 mockGenerateReportByPipeline");
	if (pipelineResult?.contract && pipelineResult.code) {
		return mockGenerateReport(pipelineResult);
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

// ====================================================================
// ApiClient 协议实现（mockApiClient）
// ====================================================================

/** HITL 状态 mock（默认 false） */
let mockHITLEnabled = false;

async function mockToggleHITL(enabled: boolean): Promise<boolean> {
	mockHITLEnabled = enabled;
	return enabled;
}

async function mockGetHITLStatus(): Promise<boolean> {
	return mockHITLEnabled;
}

/** LLMConfig mock（仅用于 SettingsDialog 兼容） */
function mockGetLLMConfig(): Promise<LLMConfig> {
	return Promise.resolve({
		mode: "mock",
		provider: null,
		apiKey: "",
		baseUrl: "",
		model: null,
		remember: true,
	});
}

async function mockSaveLLMConfig(
	config: LLMConfig,
): Promise<{ ok: boolean; message: string }> {
	console.log("[mockApi] mockSaveLLMConfig", config);
	return { ok: true, message: "mock saved" };
}

async function mockTestLLMConnection(): Promise<LLMTestResult> {
	return {
		ok: true,
		latency_ms: 10,
		message: "mock",
		model: "mock-model",
		models: ["mock-model-1", "mock-model-2"],
	};
}

async function mockGetTaskDetail(taskId: string): Promise<DashboardTaskRecord> {
	return {
		id: taskId,
		requirement: "mock requirement",
		language: "c",
		status: "done",
		degraded: false,
		code_hash: "",
		violation_count: 0,
		mandatory_count: 0,
		required_count: 0,
		advisory_count: 0,
		stage_reached: "done",
		duration_ms: 0,
		created_at: null,
	};
}

/**
 * mockApi 的 ApiClient 实例。
 *
 * 大部分方法直接转发到本文件中的 mockXxx 函数；
 * - mockApprove / mockReject 返回带数据的 Promise，ApiClient 要求 Promise<void>，此处丢弃返回值；
 * - mockCompose / mockCheckCompatibility 的 connection 参数类型严格为 ComposeConnection，
 *   ApiClient 声明为 string，此处做类型断言保持兼容；
 * - LLMConfig / HITL 状态 / 任务详情 由本地 mock 状态提供。
 *   注意：HITL（Human-in-the-Loop 人工审查）与 HIL（Hardware-in-the-Loop 硬件在环，digital_twin/）无关。
 */
export const mockApiClient: ApiClient = {
	generate: (requirement, scadeFile, language = "c") =>
		mockGenerate(requirement, scadeFile, language),
	simulate: mockSimulateByCode,
	generateReport: mockGenerateReportByPipeline,
	downloadReport: mockDownloadReport,
	compose: (compA: ComposeInput, compB: ComposeInput, connection: string) =>
		mockCompose(
			typeof compA === "string" ? compA : (compA?.name ?? "ComponentA"),
			typeof compB === "string" ? compB : (compB?.name ?? "ComponentB"),
			connection as ComposeConnection,
		),
	checkCompatibility: (
		contractA: string,
		contractB: string,
		connection: string,
	) =>
		mockCheckCompatibility(
			contractA,
			contractB,
			connection as ComposeConnection,
		),
	getHITLStatus: mockGetHITLStatus,
	toggleHITL: mockToggleHITL,
	getHITLPendingApprovals: mockGetPendingApprovals,
	getHITLHistory: mockGetHITLHistory,
	hitlApprove: async (requestId, comments) => {
		await mockApprove(requestId, comments);
	},
	hitlReject: async (requestId, comments) => {
		await mockReject(requestId, comments);
	},
	verifyContract: mockVerifyContract,
	searchRules: mockSearchRules,
	getRuleStandards: mockGetRuleStandards,
	getLLMConfig: mockGetLLMConfig,
	saveLLMConfig: mockSaveLLMConfig,
	testLLMConnection: mockTestLLMConnection,
	getTaskDetail: mockGetTaskDetail,
};
