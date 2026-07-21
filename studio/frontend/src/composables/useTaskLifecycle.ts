import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
	fetchVerifiedRecordingTask,
	getTaskGateway,
} from "@/services/taskGateway";
import { useExecutionStore } from "@/stores/executionStore";
import { useTaskHistoryStore } from "@/stores/taskHistoryStore";
import type {
	EventSubscription,
	TaskDetail,
	TaskEvent,
} from "@/types/execution";

export interface UseTaskLifecycleOptions {
	onComplete?: () => void | Promise<void>;
	onEvent?: (event: TaskEvent) => void | Promise<void>;
}

export function useTaskLifecycle(options: UseTaskLifecycleOptions = {}) {
	const execution = useExecutionStore();
	const route = useRoute();
	const router = useRouter();
	const history = useTaskHistoryStore();

	const task = ref<TaskDetail | null>(null);
	const events = ref<TaskEvent[]>([]);
	const error = ref("");

	let subscription: EventSubscription | null = null;

	const replayTaskId = computed(
		() => route.params.taskId as string | undefined,
	);
	const isReplayMode = computed(() => !!replayTaskId.value);

	function subscribeToTask(taskId: string, afterSeq: number = 0) {
		const gateway = getTaskGateway(execution.profileId);
		subscription?.close();
		subscription = gateway.subscribe(
			taskId,
			afterSeq,
			async (event) => {
				events.value.push(event);
				if (task.value) task.value.current_stage = event.stage;
				history.updateTask(taskId);
				await options.onEvent?.(event);
				if (event.type === "complete" || event.level === "complete") {
					task.value = await gateway.getTask(taskId);
					await options.onComplete?.();
				}
			},
			(cause) => {
				error.value = cause.message;
			},
		);
	}

	async function start(
		requirement: string,
		language: "c" | "cpp" | "python",
	): Promise<void> {
		subscription?.close();
		error.value = "";
		events.value = [];
		const gateway = getTaskGateway(execution.profileId);
		try {
			const handle = await gateway.createTask({
				requirement,
				language,
				profile_id: execution.profileId,
				idempotency_key: crypto.randomUUID(),
			});
			task.value = {
				...handle,
				profile_id: execution.profileId,
				source: execution.profile.source,
			};
			history.addTask(handle.id, execution.profileId);
			subscribeToTask(handle.id, 0);
		} catch (cause) {
			error.value = cause instanceof Error ? cause.message : String(cause);
		}
	}

	async function attachTask(taskId: string): Promise<void> {
		subscription?.close();
		error.value = "";
		events.value = [];
		const gateway = getTaskGateway(execution.profileId);
		try {
			const detail = await gateway.getTask(taskId);
			task.value = detail;
			events.value = detail.events ?? [];
			history.addTask(taskId, detail.profile_id ?? execution.profileId);
			if (detail.status === "running") {
				const lastSeq = events.value.length;
				subscribeToTask(taskId, lastSeq);
			}
		} catch (cause) {
			error.value = cause instanceof Error ? cause.message : String(cause);
		}
	}

	async function cancel(): Promise<void> {
		if (!task.value) return;
		await getTaskGateway(execution.profileId).cancelTask(task.value.id);
		task.value.status = "cancelled";
	}

	async function loadReplayTask(): Promise<void> {
		if (!replayTaskId.value) return;
		try {
			// 优先尝试异步加载真实演示数据
			const detail = await fetchVerifiedRecordingTask(replayTaskId.value);
			if (detail) {
				task.value = detail;
				events.value = detail.events ?? [];
				history.addTask(
					replayTaskId.value,
					detail.profile_id ?? execution.profileId,
				);
			} else {
				// 回退到 API 获取
				const apiDetail = await getTaskGateway(execution.profileId).getTask(
					replayTaskId.value,
				);
				task.value = apiDetail;
				events.value = apiDetail.events ?? [];
				history.addTask(
					replayTaskId.value,
					apiDetail.profile_id ?? execution.profileId,
				);
			}
		} catch (cause) {
			const message = cause instanceof Error ? cause.message : String(cause);
			if (/not found|不存在|404/i.test(message)) {
				router.replace("/records");
				return;
			}
			error.value = message;
		}
	}

	function cleanup(): void {
		subscription?.close();
		subscription = null;
	}

	function resetTask(): void {
		task.value = null;
		events.value = [];
		error.value = "";
	}

	return {
		task,
		events,
		error,
		replayTaskId,
		isReplayMode,
		start,
		attachTask,
		cancel,
		loadReplayTask,
		cleanup,
		resetTask,
	};
}
