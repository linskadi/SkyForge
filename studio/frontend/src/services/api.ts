/**
 * 真实后端 API 服务层（向后兼容 shim）
 * ====================================================================
 * Phase 1 状态管理统一后，本文件作为 re-export shim，所有实现已迁移到 ./realApi.ts。
 * 老调用方（`import { generate, ... } from "@/services/api"`）继续工作。
 *
 * 协议层定义见 ./apiProtocol.ts；ApiClient 实例见 ./realApi.ts（realApiClient）
 * 与 ./mockApi.ts（mockApiClient）。
 */

// 旧版 ComposeInput / LLMConfig / LLMTestResult 类型仍从 apiProtocol 暴露，
// 以便旧代码继续 import 自 "./api" 而无需改动。
export type { ComposeInput, LLMConfig, LLMTestResult } from "./apiProtocol";
export { API_BASE_URL } from "./client";
// 向后兼容别名（仅保留 getPendingApprovals 的旧名，其余按 HITL 命名统一后取消）。
// 阶段：HITL 命名统一后仍允许老 API 名继续工作。
/** @deprecated 请改用 `getHITLPendingApprovals` */
export {
	checkCompatibility,
	compose,
	downloadReport,
	generate,
	generateReport,
	getHITLHistory,
	getHITLPendingApprovals,
	getHITLPendingApprovals as getPendingApprovals,
	getHITLStatus,
	getLLMConfig,
	getRuleStandards,
	getTaskDetail,
	hitlApprove,
	hitlReject,
	realApiClient,
	saveLLMConfig,
	searchRules,
	simulate,
	testLLMConnection,
	toggleHITL,
	verifyContract,
} from "./realApi";
