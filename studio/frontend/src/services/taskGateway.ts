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

import { i18n } from "@/i18n";
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

/**
 * 翻译 data 层标签：键可解析时返回译文，
 * 键缺失（t 返回键路径本身）时回退到调用方提供的默认字符串。
 */
function dataT(
	key: string,
	fallback: string,
	params?: Record<string, unknown>,
): string {
	const resolved = i18n.global.t(key, params ?? {});
	return resolved === key ? fallback : resolved;
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

function mockResult(language: CreateTaskInput["language"]): GenerateResult {
	return {
		contract: MOCK_CONTRACT,
		code: pickMockCodeByLanguage(language),
		violations: MOCK_VIOLATIONS,
		traceability: MOCK_TRACEABILITY,
		repair_history: MOCK_REPAIR_HISTORY,
		contract_check_result: MOCK_CONTRACT_CHECK_RESULT,
		simulation_result: generateNormalSimulationResult(MOCK_SIM_LOGS),
		degraded: false,
	};
}

interface MockRuntime {
	detail: TaskDetail;
	events: TaskEvent[];
	listeners: Set<(event: TaskEvent) => void>;
	timers: number[];
}

export class MockTaskGateway implements TaskGateway {
	private runtimes = new Map<string, MockRuntime>();
	private byKey = new Map<string, string>();

	async createTask(input: CreateTaskInput): Promise<TaskHandle> {
		const duplicate = this.byKey.get(input.idempotency_key);
		if (duplicate) {
			const runtime = this.runtimes.get(duplicate);
			if (runtime) return runtime.detail;
			this.byKey.delete(input.idempotency_key);
		}

		const id = `MOCK-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;
		const runtime: MockRuntime = {
			detail: {
				id,
				status: "running",
				requirement: input.requirement,
				requirement_id: "REQ-001",
				language: input.language,
				profile_id: "cloud",
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
				},
				320 * (index + 1),
			);
			runtime.timers.push(timer);
		});

		const completeTimer = window.setTimeout(() => {
			if (runtime.detail.status === "cancelled") return;
			const result = mockResult(input.language);
			const provenance = {
				source: "simulated",
				report_label: "模拟报告",
				tools: {
					cppcheck: { status: "simulated", engine: "recorded-demo" },
					compiler: { status: "simulated", engine: "recorded-demo" },
					contract: { status: "simulated", engine: "recorded-demo" },
				},
				disclaimer: "模拟数据，仅用于开发调试，不构成适航证据。",
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
				message: "模拟流水线完成",
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
		if (!runtime) throw new Error(`Mock task not found: ${taskId}`);
		runtime.events.filter((event) => event.seq > afterSeq).forEach(onEvent);
		runtime.listeners.add(onEvent);
		return { close: () => runtime.listeners.delete(onEvent) };
	}

	async getTask(taskId: string): Promise<TaskDetail> {
		const runtime = this.runtimes.get(taskId);
		if (!runtime) throw new Error(`Mock task not found: ${taskId}`);
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
	}
}

export class ServerTaskGateway implements TaskGateway {
	async createTask(input: CreateTaskInput): Promise<TaskHandle> {
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
		socket.onerror = () =>
			onError?.(
				new Error(dataT("data.error.taskEventsFailed", "任务事件连接失败")),
			);
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

const serverGateway = new ServerTaskGateway();

export function getTaskGateway(_profile: ExecutionProfileId): TaskGateway {
	return serverGateway;
}

export async function fetchVerifiedRecordingTask(
	taskId: string,
): Promise<TaskDetail | null> {
	try {
		return await serverGateway.getTask(taskId);
	} catch {
		return null;
	}
}
