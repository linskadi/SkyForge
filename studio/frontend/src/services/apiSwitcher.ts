import { computed, type DeepReadonly, reactive, readonly, toRefs } from "vue";
import { useExecutionStore } from "@/stores/executionStore";
import type { ApiClient, ComposeInput } from "./apiProtocol";
import { realApiClient } from "./realApi";

const state = reactive({
	connected: false,
});

export function getApi(): ApiClient {
	return realApiClient;
}

export const useRealAPI = computed(() => {
	return true;
});

export function setUseRealAPI(_val: boolean): void {
	const execution = useExecutionStore();
	execution.setProfile("cloud");
	state.connected = false;
	console.info(`[apiSwitcher] API 模式已切换为：真实 API`);
}

export function isUsingRealAPI(): boolean {
	return useRealAPI.value;
}

export function markConnected(connected: boolean): void {
	state.connected = connected;
}

export function USE_REAL_API() {
	const refs = toRefs(readonly(state));
	return {
		useRealAPI,
		connected: refs.connected,
		setUseRealAPI,
	};
}

export const apiState: DeepReadonly<typeof state> = readonly(state);

export type {
	ComposeResult,
	GenerateResult,
	MisraRule,
	ReportResult,
	RuleStandard,
} from "./mockApi";
export type { ApiClient, ComposeInput };
