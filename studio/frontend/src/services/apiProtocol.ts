/**
 * SkyForge API 客户端协议层
 * ====================================================================
 * 定义统一的 API 客户端接口 `ApiClient`，约束真实后端（realApi）和
 * Mock 适配器（mockApi）共同实现的契约。
 *
 * 设计要点：
 * 1. Phase 1 状态管理统一后，所有调用方（组件、stores）只依赖 `getApi(): ApiClient`
 *    即可获得与当前 execution profile 匹配的适配器，不再关心 mock/real 切换；
 * 2. 切换依据（profileId → adapter）由 apiSwitcher 唯一负责；
 * 3. 旧版 `providerStore.mode` 字段已被 `executionStore.profileId` 取代，
 *    `ApiClient` 接口本身不再感知 mock/local/api 三态概念；
 * 4. 该接口仅描述"调用方用得到的全部后端能力"，不强制 LLM/HITL 等运行时配置语义。
 */

import type { LLMMode } from "@/stores/providerStore";
import type {
	CompatibilityResult,
	ComposeConnection,
	ComposeResult,
	DashboardTaskRecord,
	FaultParams,
	GenerateResult,
	HITLApproval,
	HITLHistoryItem,
	MisraRule,
	ReportResult,
	RuleStandard,
	SimulationResult,
} from "@/types/domain";
import type { VerificationResult, VerifyRequest } from "@/types/verification";

/** 组件组合入参：可为名称字符串或 { code, contract, name } 对象 */
export type ComposeInput =
	| string
	| { code?: string; contract?: string; name?: string };

/** LLM 配置结构（与后端 LLMConfigRequest / LLMConfigResponse 对齐） */
export interface LLMConfig {
	mode: LLMMode;
	provider: string | null;
	apiKey: string;
	baseUrl: string;
	model: string | null;
	remember?: boolean;
}

/** LLM 连接测试结果（与后端 LLMTestResponse 对齐） */
export interface LLMTestResult {
	ok: boolean;
	latency_ms: number;
	message: string;
	model?: string | null;
	models?: string[] | null;
}

/**
 * SkyForge 统一 API 客户端契约
 *
 * 真实 API（realApi）和 Mock 适配器（mockApi）都必须实现该接口的全部方法。
 * 调用方通过 `getApi()` 获取当前 profile 对应的实例。
 */
export interface ApiClient {
	// ---- 代码生成 / 修复 / 仿真 / 报告 ----
	/**
	 * 生成代码：触发完整的 requirement → contract → code → repair → simulation pipeline
	 * @param requirement 自然语言需求
	 * @param scadeFile 可选的 SCADE G-Lustre 文件内容
	 * @param language 目标语言：c / cpp / python（默认 "c"）
	 */
	generate(
		requirement: string,
		scadeFile?: string,
		language?: string,
	): Promise<GenerateResult>;

	/**
	 * 数字孪生仿真
	 * @param code 待仿真代码
	 * @param contract 契约 YAML 字符串
	 * @param faultType 可选故障类型
	 * @param faultParams 可选故障参数
	 */
	simulate(
		code: string,
		contract: string,
		faultType?: string,
		faultParams?: FaultParams,
	): Promise<SimulationResult>;

	/** 生成 DO-178C 报告 */
	generateReport(pipelineResult: GenerateResult): Promise<ReportResult>;

	/** 获取报告下载 URL（GET /api/report/download） */
	downloadReport(): string;

	// ---- 组件组合 ----
	/**
	 * 组件组合
	 * @param compA 组件 A
	 * @param compB 组件 B
	 * @param connection 连接方式：sequential / parallel / feedback
	 */
	compose(
		compA: ComposeInput,
		compB: ComposeInput,
		connection: string,
	): Promise<ComposeResult>;

	/** 兼容性检查 */
	checkCompatibility(
		contractA: string,
		contractB: string,
		connection: string,
	): Promise<CompatibilityResult>;

	// ---- HITL 人工审批（Human-in-the-Loop）----
	// 注意：与 HIL（Hardware-in-the-Loop 硬件在环，digital_twin/）无关。
	/** 查询 HITL 启用状态 */
	getHITLStatus(): Promise<boolean>;

	/** 切换 HITL 启用状态 */
	toggleHITL(enabled: boolean): Promise<boolean>;

	/** 获取待审批列表 */
	getHITLPendingApprovals(): Promise<HITLApproval[]>;

	/** 获取审批历史 */
	getHITLHistory(): Promise<HITLHistoryItem[]>;

	/** 批准 HITL 请求 */
	hitlApprove(requestId: string, comments: string): Promise<void>;

	/** 拒绝 HITL 请求 */
	hitlReject(requestId: string, comments: string): Promise<void>;

	// ---- 形式化验证 / 规则搜索 ----
	/** 形式化验证契约 */
	verifyContract(payload: VerifyRequest): Promise<VerificationResult>;

	/** 搜索指定规则集规则 */
	searchRules(query: string, standardId?: string): Promise<MisraRule[]>;

	/** 获取所有可用规则集列表 */
	getRuleStandards(): Promise<RuleStandard[]>;

	// ---- LLM 配置管理 ----
	/** 读取当前 LLM 配置 */
	getLLMConfig(): Promise<LLMConfig>;

	/** 保存 LLM 配置 */
	saveLLMConfig(config: LLMConfig): Promise<{ ok: boolean; message: string }>;

	/** 测试 LLM 连接 */
	testLLMConnection(config: LLMConfig): Promise<LLMTestResult>;

	// ---- 报告（生成 + 下载）----
	/** 生成报告（语义同 generateReport，保留别名以兼容旧组件） */
	generateReportHTML?: (
		pipelineResult: GenerateResult,
	) => Promise<ReportResult>;

	// ---- Dashboard ----
	/** 获取 Dashboard 任务详情 */
	getTaskDetail(taskId: string): Promise<DashboardTaskRecord>;
}

/**
 * Connection 类型辅助别名（仅用于 compose / checkCompatibility 的 connection 参数）
 * 与 types/domain 的 ComposeConnection 保持一致，此处 re-export 以便调用方 import 自此文件。
 */
export type { ComposeConnection };
