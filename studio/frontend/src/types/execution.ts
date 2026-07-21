import type { GenerateResult } from "@/types/domain";

export type ExecutionProfileId = "demo" | "cloud" | "local";
export type RunSource = "simulated" | "live" | "replay";
export type EvidenceStatus =
	| "observed"
	| "simulated"
	| "unavailable"
	| "failed";

export interface ExecutionProfile {
	id: ExecutionProfileId;
	label: string;
	available: boolean;
	source: RunSource;
	provider?: string;
	model?: string;
}

export interface CreateTaskInput {
	requirement: string;
	language: "c" | "cpp" | "python";
	profile_id: ExecutionProfileId;
	idempotency_key: string;
	scade_file?: string;
}

export interface TaskHandle {
	id: string;
	status: string;
	events_url?: string;
}

export interface TaskEvent {
	seq: number;
	stage: string;
	level: string;
	agent: string;
	message: string;
	evidence_status: EvidenceStatus;
	created_at: string;
	type?: "event" | "complete";
	result?: GenerateResult;
	provenance?: Record<string, unknown>;
}

export interface TaskSummary extends TaskHandle {
	requirement?: string;
	requirement_id?: string | null;
	language?: string;
	profile_id?: ExecutionProfileId;
	source?: RunSource;
	current_stage?: string;
	progress?: number;
	duration_ms?: number | null;
	created_at?: string;
}

export interface TaskDetail extends TaskSummary {
	result?: GenerateResult | null;
	provenance?: Record<string, unknown> | null;
	error?: string | null;
	events?: TaskEvent[];
}

export interface EventSubscription {
	close(): void;
}

export interface TaskGateway {
	createTask(input: CreateTaskInput): Promise<TaskHandle>;
	subscribe(
		taskId: string,
		afterSeq: number,
		onEvent: (event: TaskEvent) => void,
		onError?: (error: Error) => void,
	): EventSubscription;
	getTask(taskId: string): Promise<TaskDetail>;
	listTasks(): Promise<TaskSummary[]>;
	cancelTask(taskId: string): Promise<void>;
	deleteTask(taskId: string): Promise<void>;
}
