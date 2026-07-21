import { computed } from "vue";
import type { TaskDetail } from "@/types/execution";

export type StageKey =
	| "requirement"
	| "llr"
	| "contract"
	| "code"
	| "repair"
	| "simulation"
	| "evidence";

export interface StageInfo {
	key: StageKey;
	name: string;
}

const STAGES: readonly StageInfo[] = [
	{ key: "requirement", name: "需求解析" },
	{ key: "llr", name: "LLR" },
	{ key: "contract", name: "契约" },
	{ key: "code", name: "代码" },
	{ key: "repair", name: "扫描修复" },
	{ key: "simulation", name: "数字孪生" },
	{ key: "evidence", name: "证据包" },
] as const;

export function usePipeline(task: () => TaskDetail | null) {
	const stages = STAGES as readonly StageInfo[];

	const running = computed(() => task()?.status === "running");
	const complete = computed(
		() => task()?.status === "done" || task()?.status === "degraded",
	);

	const currentStageIndex = computed(() => {
		if (complete.value) return stages.length;
		return Math.max(
			0,
			stages.findIndex((s) => s.key === task()?.current_stage),
		);
	});

	return {
		stages,
		running,
		complete,
		currentStageIndex,
	};
}
