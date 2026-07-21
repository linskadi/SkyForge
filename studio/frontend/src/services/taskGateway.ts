import {
	MOCK_AGENT_LOGS,
	MOCK_CONTRACT,
	MOCK_CONTRACT_CHECK_RESULT,
	MOCK_REPAIR_HISTORY,
	MOCK_SIM_LOGS,
	MOCK_TRACEABILITY,
	MOCK_VIOLATIONS,
	pickMockCodeByLanguage,
} from "./mockApi";
import "@/mock/data";

import deepseekDemo from "@/data/demo_runs/deepseek_cloud_demo.json";
import ollamaDemo from "@/data/demo_runs/ollama_local_demo.json";
import { VERIFIED_RECORDINGS } from "@/data/verifiedRecordings";
import { API_BASE_URL, deleteJSON, getJSON, postJSON } from "@/services/client";
import { generateNormalSimulationResult } from "@/services/simulation";
import type { GenerateResult } from "@/types/domain";
import type {
	CreateTaskInput,
	EventSubscription,
	ExecutionProfileId,
	TaskDetail,
	TaskEvent,
	TaskGateway,
	TaskHandle,
	TaskSummary,
} from "@/types/execution";

// 演示数据缓存
const demoDataCache = new Map<string, TaskDetail>();

// 演示数据映射：recording ID -> JSON 数据
interface DemoDataEntry {
	data: {
		id: string;
		title: string;
		status: string;
		requirement: string;
		language: string;
		profile_id: string;
		recorded_at: string;
		sha256: string;
		result?: {
			requirement?: {
				req_id?: string;
			};
			final_code?: string;
			code?: string;
			final_violations?: unknown[];
			traceability?: Record<string, number[]>;
			repair_history?: unknown[];
			contract_check_result?: unknown;
			simulation_result?: unknown;
			degraded?: boolean;
		};
		provenance?: Record<string, unknown>;
	};
	profile: string;
}

const demoDataMap: Record<string, DemoDataEntry> = {
	"cloud-deepseek-20260721": {
		data: deepseekDemo as DemoDataEntry["data"],
		profile: "cloud",
	},
	"local-ollama-20260721": {
		data: ollamaDemo as DemoDataEntry["data"],
		profile: "local",
	},
};

// 异步加载演示数据
async function loadDemoDataFile(
	recordingId: string,
): Promise<TaskDetail | null> {
	const mapping = demoDataMap[recordingId];
	if (!mapping) return null;

	// 如果已缓存，直接返回
	const cachedRecording = demoDataCache.get(recordingId);
	if (cachedRecording) {
		return cachedRecording;
	}

	try {
		const rawData = mapping.data;
		const recording = VERIFIED_RECORDINGS.find(
			(item) => item.id === recordingId,
		);
		if (!recording) return null;

		// 构建 GenerateResult，处理 JSON 数据与类型的不匹配
		const result: GenerateResult = {
			contract: MOCK_CONTRACT, // JSON 中 contract 是 YAML 字符串，使用 mock 对象
			code: rawData.result?.final_code ?? rawData.result?.code ?? "",
			violations: (rawData.result?.final_violations ??
				[]) as GenerateResult["violations"],
			traceability: rawData.result?.traceability ?? {},
			repair_history: (rawData.result?.repair_history ??
				[]) as GenerateResult["repair_history"],
			contract_check_result:
				(rawData.result
					?.contract_check_result as GenerateResult["contract_check_result"]) ??
				MOCK_CONTRACT_CHECK_RESULT,
			simulation_result:
				(rawData.result
					?.simulation_result as GenerateResult["simulation_result"]) ??
				generateNormalSimulationResult(MOCK_SIM_LOGS),
			degraded: rawData.result?.degraded ?? false,
		};

		// 构建 TaskDetail
		const detail: TaskDetail = {
			id: recordingId,
			status: rawData.status === "done" ? "done" : "degraded",
			requirement: rawData.requirement,
			requirement_id: rawData.result?.requirement?.req_id ?? "REQ-001",
			language: rawData.language as "c" | "cpp" | "python",
			profile_id: mapping.profile as ExecutionProfileId,
			source: "replay",
			current_stage: "done",
			progress: 100,
			duration_ms: 0, // JSON 中未记录
			created_at: rawData.recorded_at,
			result,
			events: [], // 回放数据不包含事件流
			provenance: {
				source: "replay",
				report_label: "已验证回放",
				manifest_id: recordingId,
				title: rawData.title,
				model: recording.model,
				sha256: rawData.sha256,
				status: recording.status,
				note: recording.note,
				disclaimer:
					"离线回放来自已提交 manifest；其中降级阶段继续标记 simulated，不构成适航证据。",
				tools: {
					llm: {
						status: "observed",
						engine: mapping.profile === "cloud" ? "DeepSeek" : "Ollama",
						model: recording.model,
					},
					static_analysis: { status: "observed", engine: "Cppcheck" },
					compilation: { status: "simulated", engine: "Python simulator" },
					simulation: { status: "simulated", engine: "Python simulator" },
				},
			},
		};

		// 缓存并返回
		demoDataCache.set(recordingId, detail);
		return detail;
	} catch (error) {
		console.error("加载演示数据失败:", error);
		return null;
	}
}

const STAGES = [
	"requirement",
	"requirement",
	"contract",
	"contract",
	"code",
	"code",
	"repair",
	"repair",
	"repair",
	"repair",
	"simulation",
	"simulation",
	"evidence",
];

function demoResult(language: CreateTaskInput["language"]): GenerateResult {
	return {
		contract: MOCK_CONTRACT,
		// Task 10: 使用 pickMockCodeByLanguage 根据 language 选择对应 mock 代码
		code: pickMockCodeByLanguage(language),
		violations: MOCK_VIOLATIONS,
		traceability: MOCK_TRACEABILITY,
		repair_history: MOCK_REPAIR_HISTORY,
		contract_check_result: MOCK_CONTRACT_CHECK_RESULT,
		simulation_result: generateNormalSimulationResult(MOCK_SIM_LOGS),
		degraded: false,
	};
}

function verifiedRecordingTask(taskId: string): TaskDetail | null {
	const recording = VERIFIED_RECORDINGS.find((item) => item.id === taskId);
	if (!recording) return null;
	const result = demoResult("c");
	const createdAt = recording.recordedAt.includes("T")
		? recording.recordedAt
		: "2026-07-17T21:04:05+08:00";
	const events: TaskEvent[] = MOCK_AGENT_LOGS.map((log, index) => {
		const evidence_status =
			index <= 5 || (index >= 6 && index <= 9) ? "observed" : "simulated";
		return {
			seq: index + 1,
			stage: STAGES[Math.min(index, STAGES.length - 1)],
			level: log.level,
			agent: log.agent,
			message: log.thought,
			evidence_status,
			created_at: createdAt,
		};
	});
	events.push({
		seq: events.length + 1,
		stage: "done",
		level: "complete",
		agent: "SYSTEM",
		message: "已验证回放加载完成；降级阶段保持 simulated 标识",
		evidence_status: "observed",
		created_at: createdAt,
		type: "complete",
		result,
		provenance: {
			source: "replay",
			manifest_id: recording.id,
			model: recording.model,
			sha256: recording.sha256,
		},
	});
	return {
		id: recording.id,
		status:
			recording.status === "verified_with_degradation" ? "degraded" : "done",
		requirement:
			"实现一个一阶低通滤波器，截止频率 10Hz，用于滤除飞控传感器高频噪声；输出限定为 uint16_t，并满足 MISRA C:2012。注入传感器卡死故障时保持上一拍安全值。",
		requirement_id: "REQ-001",
		language: "c",
		profile_id: recording.profile,
		source: "replay",
		current_stage: "done",
		progress: 100,
		duration_ms: 733_989,
		created_at: createdAt,
		result,
		events,
		provenance: {
			source: "replay",
			report_label: "已验证回放",
			manifest_id: recording.id,
			title: recording.title,
			model: recording.model,
			sha256: recording.sha256,
			status: recording.status,
			note: recording.note,
			disclaimer:
				"离线回放来自已提交 manifest；其中降级阶段继续标记 simulated，不构成适航证据。",
			tools: {
				llm: { status: "observed", engine: "Ollama", model: recording.model },
				static_analysis: { status: "observed", engine: "Cppcheck" },
				compilation: { status: "simulated", engine: "Python simulator" },
				simulation: { status: "simulated", engine: "Python simulator" },
			},
		},
	};
}

export function getVerifiedRecordingTask(taskId: string): TaskDetail | null {
	// 先检查缓存
	const cachedTask = demoDataCache.get(taskId);
	if (cachedTask) {
		return cachedTask;
	}
	// 回退到同步 mock 数据
	return verifiedRecordingTask(taskId);
}

export async function fetchVerifiedRecordingTask(
	taskId: string,
): Promise<TaskDetail | null> {
	// 先检查缓存
	const cachedTask = demoDataCache.get(taskId);
	if (cachedTask) {
		return cachedTask;
	}

	// 尝试加载真实数据
	const detail = await loadDemoDataFile(taskId);
	if (detail) {
		return detail;
	}

	// 回退到同步 mock 数据
	return verifiedRecordingTask(taskId);
}

const DEMO_RUNTIME_STORAGE_KEY = "skyforge-demo-runtimes";

interface PersistedDemoRuntime {
	detail: TaskDetail;
	events: TaskEvent[];
	createdAt: string;
	lastEventSeq: number;
}

function loadPersistedRuntimes(): Map<string, PersistedDemoRuntime> {
	try {
		const raw = localStorage.getItem(DEMO_RUNTIME_STORAGE_KEY);
		if (!raw) return new Map();
		const parsed = JSON.parse(raw) as Record<string, PersistedDemoRuntime>;
		return new Map(Object.entries(parsed));
	} catch {
		return new Map();
	}
}

function savePersistedRuntime(
	taskId: string,
	runtime: { detail: TaskDetail; events: TaskEvent[] },
) {
	try {
		const all = loadPersistedRuntimes();
		all.set(taskId, {
			detail: runtime.detail,
			events: runtime.events,
			createdAt: runtime.detail.created_at ?? new Date().toISOString(),
			lastEventSeq: runtime.events.length,
		});
		const obj: Record<string, PersistedDemoRuntime> = {};
		for (const [k, v] of all.entries()) {
			obj[k] = v;
		}
		localStorage.setItem(DEMO_RUNTIME_STORAGE_KEY, JSON.stringify(obj));
	} catch {
		// ignore
	}
}

function removePersistedRuntime(taskId: string) {
	try {
		const all = loadPersistedRuntimes();
		all.delete(taskId);
		const obj: Record<string, PersistedDemoRuntime> = {};
		for (const [k, v] of all.entries()) {
			obj[k] = v;
		}
		localStorage.setItem(DEMO_RUNTIME_STORAGE_KEY, JSON.stringify(obj));
	} catch {
		// ignore
	}
}

interface DemoRuntime {
	detail: TaskDetail;
	events: TaskEvent[];
	listeners: Set<(event: TaskEvent) => void>;
	timers: number[];
}

export class DemoTaskGateway implements TaskGateway {
	private runtimes = new Map<string, DemoRuntime>();
	private byKey = new Map<string, string>();

	static clearPersisted(): void {
		try {
			localStorage.removeItem(DEMO_RUNTIME_STORAGE_KEY);
		} catch {
			// ignore
		}
	}

	constructor() {
		this.restoreRuntimes();
	}

	private restoreRuntimes() {
		const persisted = loadPersistedRuntimes();
		const now = Date.now();

		for (const [taskId, persistedRuntime] of persisted.entries()) {
			const { detail, events } = persistedRuntime;

			if (detail.status !== "running") {
				const runtime: DemoRuntime = {
					detail,
					events,
					listeners: new Set(),
					timers: [],
				};
				this.runtimes.set(taskId, runtime);
				continue;
			}

			const createdAt = new Date(detail.created_at ?? now).getTime();
			const elapsedMs = now - createdAt;
			const totalEvents = 14;
			const eventInterval = 320;
			const completedEvents = Math.min(
				totalEvents,
				Math.floor(elapsedMs / eventInterval),
			);

			if (completedEvents >= totalEvents) {
				const language = (detail.language as "c" | "cpp" | "python") ?? "c";
				const result = demoResult(language);
				const provenance = {
					source: "simulated" as const,
					report_label: "模拟演示报告",
					tools: {
						cppcheck: { status: "simulated", engine: "recorded-demo" },
						compiler: { status: "simulated", engine: "recorded-demo" },
						contract: { status: "simulated", engine: "recorded-demo" },
					},
					disclaimer: "模拟数据，仅用于比赛讲解，不构成适航证据。",
				};
				const finalDetail: TaskDetail = {
					...detail,
					status: "done",
					current_stage: "done",
					progress: 100,
					duration_ms: 4500,
					result,
					provenance,
				};
				const completeEvent: TaskEvent = {
					seq: 14,
					stage: "done",
					level: "complete",
					agent: "SYSTEM",
					message: "模拟演示流水线完成",
					evidence_status: "simulated",
					created_at: new Date(createdAt + 4500).toISOString(),
					type: "complete",
					result,
					provenance,
				};
				const allEvents = [...events, completeEvent];
				const runtime: DemoRuntime = {
					detail: finalDetail,
					events: allEvents,
					listeners: new Set(),
					timers: [],
				};
				this.runtimes.set(taskId, runtime);
				savePersistedRuntime(taskId, runtime);
			} else {
				const runtime: DemoRuntime = {
					detail: { ...detail, status: "running" },
					events: [...events],
					listeners: new Set(),
					timers: [],
				};
				this.runtimes.set(taskId, runtime);

				for (let i = completedEvents; i < totalEvents; i++) {
					const log = MOCK_AGENT_LOGS[i];
					if (!log) continue;
					const delay = (i + 1) * eventInterval - elapsedMs;
					const timer = window.setTimeout(
						() => {
							if (runtime.detail.status === "cancelled") return;
							const event: TaskEvent = {
								seq: i + 1,
								stage: STAGES[i],
								level: log.level,
								agent: log.agent,
								message: log.thought,
								evidence_status: "simulated",
								created_at: new Date().toISOString(),
							};
							runtime.events.push(event);
							runtime.detail.current_stage = event.stage;
							runtime.detail.progress = Math.round(((i + 1) / 14) * 100);
							runtime.listeners.forEach((listener) => {
								listener(event);
							});
							savePersistedRuntime(taskId, runtime);
						},
						Math.max(0, delay),
					);
					runtime.timers.push(timer);
				}

				const completeDelay = 4500 - elapsedMs;
				const completeTimer = window.setTimeout(
					() => {
						if (runtime.detail.status === "cancelled") return;
						const language = (detail.language as "c" | "cpp" | "python") ?? "c";
						const result = demoResult(language);
						const provenance = {
							source: "simulated" as const,
							report_label: "模拟演示报告",
							tools: {
								cppcheck: { status: "simulated", engine: "recorded-demo" },
								compiler: { status: "simulated", engine: "recorded-demo" },
								contract: { status: "simulated", engine: "recorded-demo" },
							},
							disclaimer: "模拟数据，仅用于比赛讲解，不构成适航证据。",
						};
						runtime.detail = {
							...runtime.detail,
							status: "done",
							current_stage: "done",
							progress: 100,
							duration_ms: 4500,
							result,
							provenance,
						};
						const event: TaskEvent = {
							seq: 14,
							stage: "done",
							level: "complete",
							agent: "SYSTEM",
							message: "模拟演示流水线完成",
							evidence_status: "simulated",
							created_at: new Date().toISOString(),
							type: "complete",
							result,
							provenance,
						};
						runtime.events.push(event);
						runtime.listeners.forEach((listener) => {
							listener(event);
						});
						savePersistedRuntime(taskId, runtime);
					},
					Math.max(0, completeDelay),
				);
				runtime.timers.push(completeTimer);
			}
		}
	}

	async createTask(input: CreateTaskInput): Promise<TaskHandle> {
		const duplicate = this.byKey.get(input.idempotency_key);
		if (duplicate) {
			const runtime = this.runtimes.get(duplicate);
			if (runtime) return runtime.detail;
			this.byKey.delete(input.idempotency_key);
		}

		const id = `DEMO-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;
		const runtime: DemoRuntime = {
			detail: {
				id,
				status: "running",
				requirement: input.requirement,
				requirement_id: "REQ-001",
				language: input.language,
				profile_id: "demo",
				source: "simulated",
				current_stage: "queued",
				progress: 0,
				created_at: new Date().toISOString(),
			},
			events: [],
			listeners: new Set(),
			timers: [],
		};
		this.runtimes.set(id, runtime);
		this.byKey.set(input.idempotency_key, id);
		savePersistedRuntime(id, runtime);

		MOCK_AGENT_LOGS.forEach((log, index) => {
			const timer = window.setTimeout(
				() => {
					if (runtime.detail.status === "cancelled") return;
					const event: TaskEvent = {
						seq: index + 1,
						stage: STAGES[index],
						level: log.level,
						agent: log.agent,
						message: log.thought,
						evidence_status: "simulated",
						created_at: new Date().toISOString(),
					};
					runtime.events.push(event);
					runtime.detail.current_stage = event.stage;
					runtime.detail.progress = Math.round(((index + 1) / 14) * 100);
					runtime.listeners.forEach((listener) => {
						listener(event);
					});
					savePersistedRuntime(id, runtime);
				},
				320 * (index + 1),
			);
			runtime.timers.push(timer);
		});

		const completeTimer = window.setTimeout(() => {
			if (runtime.detail.status === "cancelled") return;
			const result = demoResult(input.language);
			const provenance = {
				source: "simulated",
				report_label: "模拟演示报告",
				tools: {
					cppcheck: { status: "simulated", engine: "recorded-demo" },
					compiler: { status: "simulated", engine: "recorded-demo" },
					contract: { status: "simulated", engine: "recorded-demo" },
				},
				disclaimer: "模拟数据，仅用于比赛讲解，不构成适航证据。",
			};
			runtime.detail = {
				...runtime.detail,
				status: "done",
				current_stage: "done",
				progress: 100,
				duration_ms: 4500,
				result,
				provenance,
			};
			const event: TaskEvent = {
				seq: 14,
				stage: "done",
				level: "complete",
				agent: "SYSTEM",
				message: "模拟演示流水线完成",
				evidence_status: "simulated",
				created_at: new Date().toISOString(),
				type: "complete",
				result,
				provenance,
			};
			runtime.events.push(event);
			runtime.listeners.forEach((listener) => {
				listener(event);
			});
			savePersistedRuntime(id, runtime);
		}, 4500);
		runtime.timers.push(completeTimer);
		return runtime.detail;
	}

	subscribe(
		taskId: string,
		afterSeq: number,
		onEvent: (event: TaskEvent) => void,
	): EventSubscription {
		const runtime = this.runtimes.get(taskId);
		if (!runtime) throw new Error(`Demo task not found: ${taskId}`);
		runtime.events.filter((event) => event.seq > afterSeq).forEach(onEvent);
		runtime.listeners.add(onEvent);
		return { close: () => runtime.listeners.delete(onEvent) };
	}

	async getTask(taskId: string): Promise<TaskDetail> {
		const recording = verifiedRecordingTask(taskId);
		if (recording) return recording;
		const runtime = this.runtimes.get(taskId);
		if (!runtime) throw new Error(`Demo task not found: ${taskId}`);
		return { ...runtime.detail, events: [...runtime.events] };
	}

	async listTasks(): Promise<TaskSummary[]> {
		return [...this.runtimes.values()].map((runtime) => runtime.detail);
	}

	async cancelTask(taskId: string): Promise<void> {
		const runtime = this.runtimes.get(taskId);
		if (!runtime) return;
		runtime.timers.forEach(window.clearTimeout);
		runtime.detail.status = "cancelled";
		runtime.detail.current_stage = "cancelled";
		savePersistedRuntime(taskId, runtime);
	}

	async deleteTask(taskId: string): Promise<void> {
		const runtime = this.runtimes.get(taskId);
		if (!runtime) return;
		runtime.timers.forEach(window.clearTimeout);
		runtime.listeners.clear();
		for (const [key, id] of this.byKey.entries()) {
			if (id === taskId) {
				this.byKey.delete(key);
				break;
			}
		}
		this.runtimes.delete(taskId);
		removePersistedRuntime(taskId);
	}
}

export class ServerTaskGateway implements TaskGateway {
	async createTask(input: CreateTaskInput): Promise<TaskHandle> {
		if (input.profile_id === "demo")
			throw new Error("Demo profile is browser-only");
		return postJSON<TaskHandle>("/api/v1/tasks", input);
	}

	subscribe(
		taskId: string,
		afterSeq: number,
		onEvent: (event: TaskEvent) => void,
		onError?: (error: Error) => void,
	): EventSubscription {
		const wsBase = API_BASE_URL.replace(/^http/, "ws");
		const socket = new WebSocket(
			`${wsBase}/api/v1/tasks/${encodeURIComponent(taskId)}/events?after_seq=${afterSeq}`,
		);
		socket.onmessage = (message) => {
			try {
				const event = JSON.parse(message.data) as TaskEvent;
				onEvent(event);
				if (event.type === "complete") socket.close();
			} catch (error) {
				onError?.(error instanceof Error ? error : new Error(String(error)));
			}
		};
		socket.onerror = () => onError?.(new Error("任务事件连接失败"));
		return { close: () => socket.close() };
	}

	async getTask(taskId: string): Promise<TaskDetail> {
		return getJSON<TaskDetail>(`/api/v1/tasks/${encodeURIComponent(taskId)}`);
	}

	async listTasks(): Promise<TaskSummary[]> {
		const response = await getJSON<{ tasks: TaskSummary[] }>("/api/v1/tasks");
		return response.tasks;
	}

	async cancelTask(taskId: string): Promise<void> {
		await postJSON(`/api/v1/tasks/${encodeURIComponent(taskId)}/cancel`, {});
	}

	async deleteTask(taskId: string): Promise<void> {
		await deleteJSON(`/api/v1/tasks/${encodeURIComponent(taskId)}`);
	}
}

const demoGateway = new DemoTaskGateway();
const serverGateway = new ServerTaskGateway();

export function getTaskGateway(profile: ExecutionProfileId): TaskGateway {
	return profile === "demo" ? demoGateway : serverGateway;
}
