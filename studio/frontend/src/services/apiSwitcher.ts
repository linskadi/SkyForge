/**
 * API 切换器
 * ====================================================================
 * 在 mock API 和真实后端 API 之间切换的全局开关。
 *
 * 设计要点：
 * 1. 默认使用 mock（useRealAPI = false），保证前端始终可用；
 * 2. 用户偏好持久化到 localStorage；
 * 3. getApi() 根据开关返回 realApi 或 mockApi 适配器；
 * 4. 提供 USE_REAL_API composable 供 Vue3 组件响应式使用。
 */

import { type DeepReadonly, reactive, readonly, toRefs } from "vue";
import * as realApi from "./api";
import type { ComposeInput } from "./api";
import {
	type CompatibilityResult,
	type ComposeConnection,
	type ComposeResult,
	type ContractCheckResult,
	type FaultParams,
	type FaultType,
	type GenerateResult,
	type HILApproval,
	type LLMModel,
	type LLMStatus,
	type MisraRule,
	type RepairResult,
	type ReportResult,
	type ScadeParseResult,
	type SimulationResult,
	type VerifyRequest,
	type VerificationResult,
	mockApprove,
	mockCheckCompatibility,
	mockCheckContract,
	mockCompose,
	mockDownloadReport,
	mockGenerate,
	mockGenerateReportByPipeline,
	mockGetFaultTypes,
	mockGetLLMStatus,
	mockGetMisraRule,
	mockGetModels,
	mockGetPendingApprovals,
	mockReject,
	mockRepair,
	mockSearchMisra,
	mockSimulateByCode,
	mockSwitchLLM,
	mockUploadScade,
	mockVerifyContract,
} from "./mockApi";

/** localStorage 存储 key */
const STORAGE_KEY = "airborne_use_real_api";

/**
 * 统一的 API 接口契约
 * 真实 API 和 mock 适配器都必须实现此接口
 */
export interface ApiInterface {
	generate(requirement: string, scadeFile?: string): Promise<GenerateResult>;
	repair(code: string): Promise<RepairResult>;
	checkContract(code: string, contract: string): Promise<ContractCheckResult>;
	simulate(
		code: string,
		contract: string,
		faultType?: string,
		faultParams?: FaultParams,
	): Promise<SimulationResult>;
	getFaultTypes(): Promise<FaultType[]>;
	generateReport(pipelineResult: GenerateResult): Promise<ReportResult>;
	downloadReport(): string;
	compose(
		compA: ComposeInput,
		compB: ComposeInput,
		connection: string,
	): Promise<ComposeResult>;
	checkCompatibility(
		contractA: string,
		contractB: string,
		connection: string,
	): Promise<CompatibilityResult>;
	uploadScade(file: File): Promise<ScadeParseResult>;
	getLLMStatus(): Promise<LLMStatus>;
	switchLLM(useLLM: boolean): Promise<void>;
	getModels(): Promise<LLMModel[]>;
	getPendingApprovals(): Promise<HILApproval[]>;
	approve(requestId: string, comments: string): Promise<void>;
	reject(requestId: string, comments: string): Promise<void>;
	searchMisra(query: string): Promise<MisraRule[]>;
	getMisraRule(ruleId: string): Promise<MisraRule>;
	verifyContract(payload: VerifyRequest): Promise<VerificationResult>;
}

/**
 * mock 适配器：将 mockApi.ts 的函数包装成统一 ApiInterface
 *
 * 说明：
 * - mockApi 中函数命名为 mockXxx，这里去除前缀对齐到接口方法名；
 * - mockCompose/mockCheckCompatibility 的 connection 参数是 ComposeConnection 类型，
 *   接口声明为 string，此处做类型断言保持兼容；
 * - mockSwitchLLM/mockApprove/mockReject 在 mockApi 中返回带数据的 Promise，
 *   接口要求 Promise<void>，此处丢弃返回值以满足签名。
 */
const mockAdapter: ApiInterface = {
	generate: (requirement, scadeFile) => {
		void scadeFile; // mock 模式忽略 scadeFile
		return mockGenerate(requirement);
	},
	repair: mockRepair,
	checkContract: mockCheckContract,
	simulate: mockSimulateByCode,
	getFaultTypes: mockGetFaultTypes,
	generateReport: mockGenerateReportByPipeline,
	downloadReport: mockDownloadReport,
	compose: (compA, compB, connection) =>
		mockCompose(
			typeof compA === "string" ? compA : (compA?.name ?? "ComponentA"),
			typeof compB === "string" ? compB : (compB?.name ?? "ComponentB"),
			connection as ComposeConnection,
		),
	checkCompatibility: (contractA, contractB, connection) =>
		mockCheckCompatibility(
			contractA,
			contractB,
			connection as ComposeConnection,
		),
	uploadScade: mockUploadScade,
	getLLMStatus: mockGetLLMStatus,
	switchLLM: async (useLLM) => {
		await mockSwitchLLM(useLLM);
	},
	getModels: mockGetModels,
	getPendingApprovals: mockGetPendingApprovals,
	approve: async (requestId, comments) => {
		await mockApprove(requestId, comments);
	},
	reject: async (requestId, comments) => {
		await mockReject(requestId, comments);
	},
	searchMisra: mockSearchMisra,
	getMisraRule: mockGetMisraRule,
	verifyContract: mockVerifyContract,
};

/**
 * 真实 API 适配器：直接复用 api.ts 中的所有导出函数
 */
const realAdapter: ApiInterface = {
	generate: realApi.generate,
	repair: realApi.repair,
	checkContract: realApi.checkContract,
	simulate: realApi.simulate,
	getFaultTypes: realApi.getFaultTypes,
	generateReport: realApi.generateReport,
	downloadReport: realApi.downloadReport,
	compose: realApi.compose,
	checkCompatibility: realApi.checkCompatibility,
	uploadScade: realApi.uploadScade,
	getLLMStatus: realApi.getLLMStatus,
	switchLLM: realApi.switchLLM,
	getModels: realApi.getModels,
	getPendingApprovals: realApi.getPendingApprovals,
	approve: realApi.approve,
	reject: realApi.reject,
	searchMisra: realApi.searchMisra,
	getMisraRule: realApi.getMisraRule,
	verifyContract: realApi.verifyContract,
};

/**
 * 响应式状态：是否使用真实 API
 * 默认 false（使用 mock），从 localStorage 读取用户偏好
 */
function loadInitial(): boolean {
	try {
		const stored = localStorage.getItem(STORAGE_KEY);
		if (stored === "true") return true;
		if (stored === "false") return false;
	} catch (err) {
		// localStorage 不可用时，使用默认值
		console.warn("[apiSwitcher] 读取 localStorage 失败：", err);
	}
	return false;
}

/** 全局响应式状态 */
const state = reactive({
	/** 是否使用真实 API */
	useRealAPI: loadInitial(),
	/** 当前连接状态（仅用于 UI 指示灯） */
	connected: false,
});

/**
 * 切换 API 模式
 *
 * @param value true=真实 API，false=mock
 * @param persist 是否持久化到 localStorage，默认 true
 */
export function setUseRealAPI(value: boolean, persist = true): void {
	state.useRealAPI = value;
	state.connected = false; // 切换后重置连接状态，待下次真实调用时更新
	if (persist) {
		try {
			localStorage.setItem(STORAGE_KEY, value ? "true" : "false");
		} catch (err) {
			console.warn("[apiSwitcher] 写入 localStorage 失败：", err);
		}
	}
	console.info(
		`[apiSwitcher] API 模式已切换为：${value ? "真实 API" : "Mock"}`,
	);
}

/**
 * 获取当前 API 适配器
 *
 * 根据 useRealAPI 开关返回真实 API 或 mock 适配器。
 * 每次调用都会读取最新状态，因此切换后立即生效。
 */
export function getApi(): ApiInterface {
	return state.useRealAPI ? realAdapter : mockAdapter;
}

/**
 * 判断当前是否使用真实 API
 */
export function isUsingRealAPI(): boolean {
	return state.useRealAPI;
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
 * 实现要点：通过 toRefs() 将 reactive 对象的属性转为独立 Ref，
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
		/** 是否使用真实 API（只读响应式 Ref，解构后仍保持响应式） */
		useRealAPI: refs.useRealAPI,
		/** 真实 API 连接状态（只读响应式 Ref） */
		connected: refs.connected,
		/** 切换 API 模式 */
		setUseRealAPI,
	};
}

/** 导出响应式状态（只读） */
export const apiState: DeepReadonly<typeof state> = readonly(state);

/** 类型导出，便于组件使用 */
export type {
	GenerateResult,
	ComposeResult,
	ReportResult,
	MisraRule,
} from "./mockApi";
