/**
 * 真实后端 API 服务层（realApi）
 * ====================================================================
 * SkyForge 后端 11 个端点的封装 + ApiClient 协议实现。
 *
 * 设计要点：
 * 1. Phase 1 状态管理统一后，本文件导出 `realApiClient: ApiClient`
 *    与 `mockApiClient` 共同实现 `apiProtocol.ApiClient` 契约；
 * 2. 仍保留所有原 named export（generate / simulate / compose / ...），
 *    以兼容旧版组件直接 import 的用法；
 * 3. 使用统一 HTTP 客户端 (./client.ts)，无 axios 依赖；
 * 4. 后端响应字段与 mockApi 类型存在差异，本层负责字段转换；
 * 5. 本层只负责真实后端调用，调用失败时直接抛错，由调用方决定如何处理；
 *    mock / real 切换由 apiSwitcher 统一根据 executionStore.profileId 路由。
 */

import type { LLMMode } from "@/stores/providerStore";
import type {
	CompatibilityResult,
	ComposeConnection,
	ComposeResult,
	DashboardTaskRecord,
	FaultParams,
	FaultType,
	GenerateResult,
	HITLApproval,
	HITLCheckpointType,
	HITLHistoryItem,
	MisraRule,
	ReportResult,
	RuleStandard,
	SimulationResult,
} from "@/types/domain";
import type { VerificationResult, VerifyRequest } from "@/types/verification";
import type {
	ApiClient,
	ComposeInput,
	LLMConfig,
	LLMTestResult,
} from "./apiProtocol";
import { API_BASE_URL, getJSON, postJSON, request } from "./client";

// biome-ignore lint/suspicious/noExplicitAny: 后端 API 返回的原始 JSON 数据，结构在运行时确定
type RawResponse = any;

/**
 * LLM 长耗时操作超时（毫秒）
 *
 * 本地 LLM（如 qwen3:8b）生成代码需要 60-180s，使用默认 30s 会触发
 * `AbortError: signal is aborted without reason`。这里给 3 分钟宽松窗口。
 * 适用于 generate / generateReport / compose 等触发完整 pipeline 的端点。
 */
const LLM_LONG_TIMEOUT_MS = 180_000;

// ====================================================================
// 字段转换工具：后端响应 → mockApi 类型
// ====================================================================

// ====================================================================
// Task 7: contract_check_result 结构对齐（扁平 → 嵌套）
// ====================================================================

/**
 * 将后端扁平结构 contract_check_result 转换为前端嵌套结构
 *
 * 后端返回：passed / preconditions / postconditions / invariants / fault_handling
 * 前端期望：sections[] / passed_count / total_count / overall_passed
 */
function transformContractCheckResult(
	raw: RawResponse,
): GenerateResult["contract_check_result"] {
	// 已是嵌套结构（mock 数据）
	if (raw?.sections && Array.isArray(raw.sections)) {
		return raw as GenerateResult["contract_check_result"];
	}
	// 扁平结构（真实 API）→ 转换为嵌套
	const sections = [
		{
			title: "前置条件",
			key: "preconditions" as const,
			items: raw?.preconditions ?? [],
		},
		{
			title: "后置条件",
			key: "postconditions" as const,
			items: raw?.postconditions ?? [],
		},
		{
			title: "不变式",
			key: "invariants" as const,
			items: raw?.invariants ?? [],
		},
		{
			title: "故障处理",
			key: "fault_handling" as const,
			items: raw?.fault_handling ?? [],
		},
	].filter((s) => s.items.length > 0);

	const allItems = sections.flatMap((s) => s.items);
	const passedCount = allItems.filter(
		(i: { passed?: boolean }) => i.passed,
	).length;

	return {
		component: raw?.component ?? "",
		sections,
		passed_count: passedCount,
		total_count: allItems.length,
		overall_passed: raw?.passed ?? passedCount === allItems.length,
		generated_assert_code: raw?.assert_code ?? raw?.generated_assert_code ?? "",
	};
}

// ====================================================================
// Task 8: contract 字段类型转换（YAML 字符串 → 对象）
// ====================================================================

/**
 * 简易 YAML 解析：提取 component 字段
 * 真实场景应使用 js-yaml 库，此处仅做基本提取
 */
function parseContractYaml(yamlStr: string): GenerateResult["contract"] {
	const lines = yamlStr.split("\n");
	const component =
		lines
			.find((l) => l.startsWith("component:"))
			?.split(":")[1]
			?.trim() ?? "";
	return {
		component,
		description: yamlStr,
		inputs: {},
		outputs: {},
		preconditions: [],
		postconditions: [],
		invariants: [],
		fault_handling: [],
	};
}

/**
 * 将后端 /api/generate 响应转换为 GenerateResult
 *
 * 后端字段：code / cppcheck_result / repair_history / contract_check_result /
 *          simulation_result / final_violations / hil_approvals
 * mockApi 字段：code / violations / repair_history / contract_check_result /
 *              simulation_result / traceability / contract
 */
function transformGenerateResponse(raw: RawResponse): GenerateResult {
	// Task 8: contract 字段类型转换
	const contract = (() => {
		const c = raw.contract ?? raw.contract_yaml;
		if (typeof c === "string") {
			try {
				return parseContractYaml(c);
			} catch {
				return {
					component: "",
					description: c,
					inputs: {},
					outputs: {},
					preconditions: [],
					postconditions: [],
					invariants: [],
					fault_handling: [],
				};
			}
		}
		return (
			c ?? {
				component: "",
				description: "",
				inputs: {},
				outputs: {},
				preconditions: [],
				postconditions: [],
				invariants: [],
				fault_handling: [],
			}
		);
	})();

	return {
		contract,
		code: raw.code ?? raw.final_code ?? "",
		violations:
			raw.violations ?? raw.cppcheck_result ?? raw.final_violations ?? [],
		traceability: raw.traceability ?? {},
		repair_history: raw.repair_history ?? [],
		// Task 7: 使用转换函数
		contract_check_result: transformContractCheckResult(
			raw.contract_check_result ?? raw.contract_check ?? { sections: [] },
		),
		// Task 12: simulation_result 默认值
		simulation_result: raw.simulation_result ??
			raw.simulation ?? {
				passed: false,
				total_steps: 0,
				fault_type: null,
				fault_params: {},
				input_waveform: [],
				output_waveform: [],
				fault_range: null,
				contract_violation: null,
				logs: [],
				statistics: {
					total_steps: 0,
					input_range: [0, 0],
					output_range: [0, 0],
					output_max: 0,
					output_min: 0,
					output_mean: 0,
				},
			},
		degraded: raw.degraded ?? false,
	};
}

/**
 * 将后端 /api/simulate 响应转换为 SimulationResult
 *
 * 后端字段：passed / total_steps / fault_type / input_waveform /
 *          output_waveform / contract_violation / statistics /
 *          compilation / terminal_log
 * mockApi 字段：补全 fault_params / fault_range / logs
 */
function transformSimulationResponse(raw: RawResponse): SimulationResult {
	const rawLogs = raw.logs ?? raw.terminal_log;
	let logs: SimulationResult["logs"] = [];
	if (Array.isArray(rawLogs)) {
		logs = rawLogs;
	} else if (typeof rawLogs === "string" && rawLogs.trim()) {
		logs = rawLogs
			.split("\n")
			.filter(Boolean)
			.map((line, i) => ({
				id: `term-${i}`,
				agent: "TERMINAL" as const,
				level: "info" as const,
				thought: line,
			}));
	}
	return {
		passed: raw.passed ?? false,
		total_steps: raw.total_steps ?? 0,
		fault_type: (raw.fault_type ?? null) as FaultType | null,
		fault_params: raw.fault_params ?? {},
		input_waveform: raw.input_waveform ?? [],
		output_waveform: raw.output_waveform ?? [],
		fault_range: raw.fault_range ?? null,
		contract_violation: raw.contract_violation ?? null,
		statistics: raw.statistics ?? {
			total_steps: raw.total_steps ?? 0,
			input_range: [0, 0],
			output_range: [0, 0],
			output_max: 0,
			output_min: 0,
			output_mean: 0,
		},
		logs,
	};
}

/**
 * 将后端 /api/compose 响应转换为 ComposeResult
 *
 * 后端字段：composed_code / composed_contract / compatibility_check /
 *          simulation_result / warnings / connection
 */
function transformComposeResponse(
	raw: RawResponse,
	compA: ComposeInput,
	compB: ComposeInput,
	connection: string,
): ComposeResult {
	const compatRaw = raw.compatibility_check ?? raw.compatibility;
	return {
		component_a:
			typeof compA === "string" ? compA : (compA?.name ?? "ComponentA"),
		component_b:
			typeof compB === "string" ? compB : (compB?.name ?? "ComponentB"),
		connection: (raw.connection ?? connection) as ComposeConnection,
		composed_code: raw.composed_code ?? "",
		compatibility: transformCompatibilityResponse(
			compatRaw,
			compA,
			compB,
			connection,
		),
		simulation: transformSimulationResponse(
			raw.simulation_result ?? raw.simulation ?? {},
		),
	};
}

/**
 * 将后端 /api/check-compatibility 响应转换为 CompatibilityResult
 *
 * 后端字段：compatible / checked_pairs / violations / warnings / connection
 */
function transformCompatibilityResponse(
	raw: RawResponse,
	compA: ComposeInput,
	compB: ComposeInput,
	connection: string,
): CompatibilityResult {
	// 后端的 violations / warnings 是字符串数组，转换为 mockApi 的 checks 列表
	const violations: string[] = raw.violations ?? [];
	const warnings: string[] = raw.warnings ?? [];
	const checks = [
		...violations.map((v: string, i: number) => ({
			id: `COMPAT-V-${i + 1}`,
			check: v,
			passed: false,
			reason: v,
		})),
		...warnings.map((w: string, i: number) => ({
			id: `COMPAT-W-${i + 1}`,
			check: w,
			passed: true,
			reason: w,
		})),
	];
	const passedCount = checks.filter((c) => c.passed).length;
	return {
		component_a:
			typeof compA === "string" ? compA : (compA?.name ?? "ComponentA"),
		component_b:
			typeof compB === "string" ? compB : (compB?.name ?? "ComponentB"),
		connection: (raw.connection ?? connection) as ComposeConnection,
		checks:
			checks.length > 0
				? checks
				: [
						{
							id: "COMPAT-001",
							check: "兼容性检查",
							passed: raw.compatible ?? raw.overall_compatible ?? true,
						},
					],
		passed_count: raw.passed_count ?? passedCount,
		total_count: raw.total_count ?? checks.length,
		overall_compatible: raw.overall_compatible ?? raw.compatible ?? true,
	};
}

/**
 * 将后端 /api/hil/pending 响应转换为 HITLApproval[]
 */
function transformPendingResponse(raw: RawResponse): HITLApproval[] {
	return raw.pending ?? raw ?? [];
}

/** HITL 检查点中文名映射（与 HITLPanel.vue checkpointIconMap 对齐） */
const HITL_CHECKPOINT_NAMES: Record<HITLCheckpointType, string> = {
	requirement_review: "需求审查",
	contract_review: "契约审查",
	code_review: "代码审查",
	final_review: "最终审查",
};

/**
 * 将后端 /api/hil/history 响应转换为 HITLHistoryItem[]
 *
 * 后端 ApprovalResult 字段：request_id / checkpoint / approved / comments /
 *   reviewer / timestamp(ISO 字符串) / status(approved/rejected/timeout/skipped)
 * 前端 HITLHistoryItem 额外需要：checkpoint_name / reviewed_at(number ms) /
 *   submitted_at / deadline / content_preview（历史记录中无内容，置空）
 */
function transformHITLHistoryResponse(raw: RawResponse): HITLHistoryItem[] {
	const items: RawResponse[] = raw.history ?? raw ?? [];
	return items.map((item: RawResponse): HITLHistoryItem => {
		const checkpoint = (item.checkpoint ??
			"requirement_review") as HITLCheckpointType;
		const reviewedAt = item.timestamp
			? new Date(item.timestamp as string).getTime()
			: undefined;
		return {
			request_id: item.request_id ?? "",
			checkpoint,
			checkpoint_name:
				HITL_CHECKPOINT_NAMES[checkpoint] ?? item.checkpoint ?? "",
			content_preview: "",
			submitted_at: 0,
			deadline: 0,
			status: (item.status ?? "approved") as HITLHistoryItem["status"],
			reviewer: item.reviewer ?? "",
			reviewed_at: reviewedAt,
			comments: item.comments ?? "",
		};
	});
}

/**
 * 将后端 /api/report 响应转换为 ReportResult
 *
 * 后端字段：report_html / traceability_matrix / do178_objectives
 */
function transformReportResponse(raw: RawResponse): ReportResult {
	const objectives: RawResponse[] = raw.do178_objectives ?? [];
	const passedObj = objectives.filter(
		(o) => o.passed ?? o.status === "passed",
	).length;
	const totalObj = objectives.length || 66;
	const matrix: RawResponse[] = raw.traceability_matrix ?? [];
	return {
		report_id: `DO178C-REPORT-${Date.now()}`,
		html: raw.report_html ?? raw.html ?? "",
		summary: {
			title: "DO-178C 报告",
			generated_at: Date.now(),
			traceability_entries: matrix.length,
			total_objectives: totalObj,
			passed_objectives: passedObj,
			pass_rate: totalObj > 0 ? passedObj / totalObj : 0,
			simulation_summary: "详见报告内容",
			misra_violations: 0,
		},
	};
}

// ====================================================================
// 公共 API 函数（与 mockApi 签名一致）
// ====================================================================

/**
 * 生成代码：POST /api/generate
 *
 * @param requirement 自然语言需求
 * @param scadeFile 可选的 SCADE G-Lustre 文件内容
 * @param language 目标语言：c / cpp / python（默认 "c"）
 */
export async function generate(
	requirement: string,
	scadeFile?: string,
	language?: string,
): Promise<GenerateResult> {
	const raw = await postJSON<RawResponse>(
		"/api/generate",
		{
			requirement,
			scade_file: scadeFile ?? "",
			language: language ?? "c",
		},
		LLM_LONG_TIMEOUT_MS,
	);
	return transformGenerateResponse(raw);
}

/**
 * 数字孪生仿真：POST /api/simulate
 */
export async function simulate(
	code: string,
	contract: string,
	faultType?: string,
	faultParams?: FaultParams,
): Promise<SimulationResult> {
	const raw = await postJSON("/api/simulate", {
		code,
		contract,
		fault_type: faultType ?? null,
		fault_params: faultParams ?? null,
		steps: 200,
	});
	return transformSimulationResponse(raw);
}

/**
 * 生成 DO-178C 报告：POST /api/report
 *
 * @param pipelineResult /api/generate 返回的全流程结果
 */
export async function generateReport(
	pipelineResult: GenerateResult,
): Promise<ReportResult> {
	const raw = await postJSON<RawResponse>(
		"/api/report",
		{
			pipeline_result: pipelineResult,
		},
		LLM_LONG_TIMEOUT_MS,
	);
	return transformReportResponse(raw);
}

/**
 * 获取报告下载 URL：GET /api/report/download
 *
 * @returns 报告下载地址（直接打开即可下载）
 */
export function downloadReport(): string {
	return `${API_BASE_URL}/api/report/download`;
}

/**
 * 组件组合：POST /api/compose
 *
 * @param compA 组件 A（名称字符串或 {code, contract, name} 对象）
 * @param compB 组件 B
 * @param connection 连接方式：sequential / parallel / feedback
 */
export async function compose(
	compA: ComposeInput,
	compB: ComposeInput,
	connection: string,
): Promise<ComposeResult> {
	// 兼容 mockApi 的字符串入参（仅传名称）和真实 API 的对象入参
	const specA =
		typeof compA === "string" ? { code: "", contract: "", name: compA } : compA;
	const specB =
		typeof compB === "string" ? { code: "", contract: "", name: compB } : compB;

	const raw = await postJSON("/api/compose", {
		component_a: { code: specA.code ?? "", contract: specA.contract ?? "" },
		component_b: { code: specB.code ?? "", contract: specB.contract ?? "" },
		connection,
		simulate: true,
		steps: 200,
	});
	return transformComposeResponse(raw, compA, compB, connection);
}

/**
 * 兼容性检查：POST /api/check-compatibility
 */
export async function checkCompatibility(
	contractA: string,
	contractB: string,
	connection: string,
): Promise<CompatibilityResult> {
	const raw = await postJSON("/api/check-compatibility", {
		contract_a: contractA,
		contract_b: contractB,
		connection,
	});
	return transformCompatibilityResponse(raw, contractA, contractB, connection);
}

/**
 * 切换 HITL 人工审批启用状态：POST /api/hil/toggle
 *
 * 默认禁用。开启后 pipeline 在需求/契约/代码评审检查点会暂停等待人工审批。
 *
 * 注意：与 HIL（Hardware-in-the-Loop 硬件在环，digital_twin/）无关。
 */
export async function toggleHITL(enabled: boolean): Promise<boolean> {
	const raw = await postJSON<RawResponse>("/api/hil/toggle", { enabled });
	return Boolean(raw?.enabled);
}

/**
 * 查询 HITL 当前启用状态：GET /api/hil/status
 * Task 11: 独立轻量端点，不返回待审批列表
 */
export async function getHITLStatus(): Promise<boolean> {
	const raw = await getJSON<RawResponse>("/api/hil/status");
	return Boolean(raw?.enabled);
}

/**
 * 获取待审批列表：GET /api/hil/pending
 */
export async function getHITLPendingApprovals(): Promise<HITLApproval[]> {
	const raw = await getJSON("/api/hil/pending");
	return transformPendingResponse(raw);
}

/**
 * 获取审批历史：GET /api/hil/history
 *
 * 后端返回 { history: ApprovalResult[], count: N }，本函数转换为 HITLHistoryItem[]。
 * 调用失败时抛错，由调用方决定 UI 错误态展示。
 */
export async function getHITLHistory(): Promise<HITLHistoryItem[]> {
	const raw = await getJSON<RawResponse>("/api/hil/history");
	return transformHITLHistoryResponse(raw);
}

/**
 * 批准 HITL 请求：POST /api/hil/approve
 */
export async function hitlApprove(
	requestId: string,
	comments: string,
): Promise<void> {
	await postJSON("/api/hil/approve", {
		request_id: requestId,
		comments,
		reviewer: "reviewer",
	});
}

/**
 * 拒绝 HITL 请求：POST /api/hil/reject
 */
export async function hitlReject(
	requestId: string,
	comments: string,
): Promise<void> {
	await postJSON("/api/hil/reject", {
		request_id: requestId,
		comments,
		reviewer: "reviewer",
	});
}

/**
 * 搜索指定规则集的规则：GET /api/rules/search?standard_id=xxx&q=xxx
 *
 * 支持通过 standard_id 切换 MISRA-C / MISRA-C++ / Python 军工规范 三种规则集。
 * 不传 standard_id 时默认为 misra_c_2012。
 */
export async function searchRules(
	query: string,
	standardId?: string,
): Promise<MisraRule[]> {
	const params = new URLSearchParams();
	params.set("q", query);
	if (standardId) {
		params.set("standard_id", standardId);
	}
	const raw = await getJSON<RawResponse>(
		`/api/rules/search?${params.toString()}`,
	);
	return raw.rules ?? raw ?? [];
}

/**
 * 获取所有可用规则集列表：GET /api/rules/standards
 *
 * 返回 3 个规则集的元数据（id / name / language / version）。
 */
export async function getRuleStandards(): Promise<RuleStandard[]> {
	const raw = await getJSON<RawResponse>("/api/rules/standards");
	return raw.standards ?? raw ?? [];
}

/**
 * 形式化验证契约：POST /api/verify
 *
 * 调用底层 Z3 SMT Solver + CBMC 对契约执行形式化验证。
 * Z3/CBMC 不可用时后端自动降级为 skipped 检查项。
 *
 * @param payload 契约数据（contract 文本 或 contract_path 文件路径），可选 code
 */
export async function verifyContract(
	payload: VerifyRequest,
): Promise<VerificationResult> {
	const raw = await postJSON<VerificationResult>("/api/verify", payload);
	return raw as VerificationResult;
}

// ====================================================================
// LLM 配置管理（mode / provider / apiKey / baseUrl / model）
// ====================================================================

/**
 * 读取当前 LLM 配置：GET /api/llm/config
 *
 * 后端返回的 apiKey 已脱敏（前 3 + **** + 后 4），可直接回填表单占位符。
 * LLMMode 类型从 providerStore 复用，避免重复定义。
 */
export async function getLLMConfig(): Promise<LLMConfig> {
	const raw = await getJSON<LLMConfig>("/api/llm/config");
	return {
		mode: (raw.mode ?? "mock") as LLMMode,
		provider: raw.provider ?? null,
		apiKey: raw.apiKey ?? "",
		baseUrl: raw.baseUrl ?? "",
		model: raw.model ?? null,
		remember: raw.remember ?? true,
	};
}

/**
 * 保存 LLM 配置：PUT /api/llm/config
 *
 * 请求体: { mode, provider, apiKey, baseUrl, model }
 * 后端写入环境变量与 settings，并同步 4 个 Agent 子配置。
 *
 * @param config LLM 配置
 * @returns 后端返回的 { ok, message }
 */
export async function saveLLMConfig(
	config: LLMConfig,
): Promise<{ ok: boolean; message: string }> {
	const raw = await request<{ ok: boolean; message: string }>(
		"/api/llm/config",
		{
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				mode: config.mode,
				provider: config.provider,
				apiKey: config.apiKey,
				baseUrl: config.baseUrl,
				model: config.model,
				remember: config.remember ?? true,
			}),
		},
	);
	return {
		ok: raw.ok ?? false,
		message: raw.message ?? "",
	};
}

/**
 * 测试 LLM 连接：POST /api/llm/test
 *
 * 请求体: { mode, provider, apiKey, baseUrl, model }
 * 后端直接使用 httpx 发起测试，不依赖 UnifiedLLMClient。
 *
 * @param config LLM 配置
 * @returns 测试结果 { ok, latency_ms, message, model? }
 */
export async function testLLMConnection(
	config: LLMConfig,
): Promise<LLMTestResult> {
	const raw = await postJSON<LLMTestResult>("/api/llm/test", {
		mode: config.mode,
		provider: config.provider,
		apiKey: config.apiKey,
		baseUrl: config.baseUrl,
		model: config.model,
		remember: config.remember ?? true,
	});
	return {
		ok: raw.ok ?? false,
		latency_ms: raw.latency_ms ?? 0,
		message: raw.message ?? "",
		model: raw.model ?? null,
		models: raw.models ?? null,
	};
}

/** API 基础地址已统一从 ./client.ts 导出，此处仅 re-export 供下游兼容 */
export { API_BASE_URL };

/**
 * 获取任务详情：GET /api/dashboard/tasks/{task_id}
 *
 * 由 Generate.vue 在 loadTaskFromId 中调用，用于从 Dashboard 点击 running 任务
 * 进入工作台时回填需求/语言字段并切换到 WebSocket 订阅模式。
 */
export async function getTaskDetail(
	taskId: string,
): Promise<DashboardTaskRecord> {
	return getJSON<DashboardTaskRecord>(
		`/api/dashboard/tasks/${encodeURIComponent(taskId)}`,
	);
}

// ====================================================================
// ApiClient 协议实现（realApiClient）
// ====================================================================

/**
 * realApi 的 ApiClient 实例。
 *
 * 所有方法直接转发到本文件导出的 named export，确保字段转换、
 * 错误传播行为与旧版完全一致；老调用方（import { generate } from "./api"）
 * 仍可通过 re-export shim（api.ts）继续工作。
 */
export const realApiClient: ApiClient = {
	generate,
	simulate,
	generateReport,
	downloadReport,
	compose,
	checkCompatibility,
	getHITLStatus,
	toggleHITL,
	getHITLPendingApprovals,
	getHITLHistory,
	hitlApprove,
	hitlReject,
	verifyContract,
	searchRules,
	getRuleStandards,
	getLLMConfig,
	saveLLMConfig,
	testLLMConnection,
	getTaskDetail,
};
