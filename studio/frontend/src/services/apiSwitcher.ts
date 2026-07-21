/**
 * API 切换器
 * ====================================================================
 * Phase 1 状态管理统一后，本切换器的唯一职责是：根据
 * `executionStore.profileId` 返回对应的 ApiClient 实例（mockApiClient /
 * realApiClient）。
 *
 * 设计要点：
 * 1. 切换依据：`executionStore.profileId`
 *    - "demo"  → mockApiClient
 *    - "cloud" / "local" → realApiClient
 * 2. 不再依赖 providerStore.mode / skyforge-llm-mode，profileId 为唯一权威来源；
 * 3. localStorage key 统一为 `skyforge-execution-profile`（由 executionStore 负责写入）；
 * 4. 调用方（组件、stores）通过 `getApi(): ApiClient` 获得当前 profile 的适配器，
 *    切换时自动响应（Pinia store reactive）。
 * 5. 保留 useRealAPI / setUseRealAPI 旧 API：薄壳封装，兼容已有调用方；
 *    setUseRealAPI 改写 executionStore.setProfile 而不是 providerStore.setMode。
 */

import { computed, type DeepReadonly, reactive, readonly, toRefs } from "vue";
import { useExecutionStore } from "@/stores/executionStore";
import type { ApiClient, ComposeInput } from "./apiProtocol";
import { mockApiClient } from "./mockApi";
import { realApiClient } from "./realApi";

/** 全局响应式状态：当前真实 API 连接状态（仅用于 UI 指示灯） */
const state = reactive({
	connected: false,
});

/**
 * 获取当前 API 适配器
 *
 * 根据 `executionStore.profileId` 返回：
 * - "demo"  → mockApiClient（前端独立可用）
 * - "cloud" / "local" → realApiClient
 *
 * 每次调用都会读取最新 profileId，因此切换后立即生效。
 * 不再读取 localStorage（避免与 executionStore 状态漂移）。
 */
export function getApi(): ApiClient {
	const profile = useExecutionStore().profileId;
	return profile === "demo" ? mockApiClient : realApiClient;
}

/**
 * 旧 API 兼容：是否使用真实 API
 *
 * 由 executionStore.profileId 推导：profileId !== "demo" 即视为真实 API。
 */
export const useRealAPI = computed(() => {
	const execution = useExecutionStore();
	return execution.profileId !== "demo";
});

/**
 * 旧 API 兼容：切换 API 模式
 *
 * 由 executionStore.profileId 推导：
 * - true  → profileId = "cloud"
 * - false → profileId = "demo"
 *
 * @param val true=真实 API，false=mock
 */
export function setUseRealAPI(val: boolean): void {
	const execution = useExecutionStore();
	execution.setProfile(val ? "cloud" : "demo");
	state.connected = false; // 切换后重置连接状态，待下次真实调用时更新
	console.info(`[apiSwitcher] API 模式已切换为：${val ? "真实 API" : "Mock"}`);
}

/**
 * 判断当前是否使用真实 API
 */
export function isUsingRealAPI(): boolean {
	return useRealAPI.value;
}

/**
 * 标记真实 API 已连接成功（供 api.ts 内部或外部健康检查调用）
 */
export function markConnected(connected: boolean): void {
	state.connected = connected;
}

/**
 * Vue3 Composable：响应式使用 API 模式状态
 *
 * 实现要点：useRealAPI 为由 executionStore.profileId 推导的 computed；
 * connected 通过 toRefs() 从 reactive state 转为独立 Ref，
 * 保证组件中解构（const { useRealAPI } = USE_REAL_API()）后仍保持响应式。
 *
 * 用法：
 * ```ts
 * import { USE_REAL_API } from "@/services/apiSwitcher";
 * const { useRealAPI, connected } = USE_REAL_API();
 * // 模板中自动解包：useRealAPI（无需 .value）
 * // setup 中读取值：useRealAPI.value
 * ```
 */
export function USE_REAL_API() {
	const refs = toRefs(readonly(state));
	return {
		/** 是否使用真实 API（只读响应式 computed，解构后仍保持响应式） */
		useRealAPI,
		/** 真实 API 连接状态（只读响应式 Ref） */
		connected: refs.connected,
		/** 切换 API 模式 */
		setUseRealAPI,
	};
}

/** 导出响应式状态（只读） */
export const apiState: DeepReadonly<typeof state> = readonly(state);

export type {
	ComposeResult,
	GenerateResult,
	MisraRule,
	ReportResult,
	RuleStandard,
} from "./mockApi";
/** 类型导出，便于组件使用 */
export type { ApiClient, ComposeInput };
