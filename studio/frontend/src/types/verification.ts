/**
 * 形式化验证结果类型定义
 * ====================================================================
 * 对应后端 POST /api/verify 返回结构（见 studio/app/api/routes/pipeline.py）。
 *
 * 三层形式化验证：
 * - Z3 SMT Solver: 约束一致性 + 边界测试用例生成
 * - CBMC: 有界模型检查（可选）
 * - Mock: Z3/CBMC 均不可用时自动降级为 skipped
 */

/** 单项检查状态：通过 / 失败 / 跳过 */
export type VerificationStatus = "passed" | "failed" | "skipped";

/** 单项形式化验证检查结果 */
export interface VerificationCheck {
	/** 检查项名称（如 "Constraint consistency"） */
	name: string;
	/** 检查状态 */
	status: VerificationStatus;
	/** 耗时（毫秒） */
	duration_ms: number;
	/** 反例（仅 failed/skipped 时有值，passed 时为 null） */
	counter_example?: string | null;
	/** 使用的工具标识（"Z3" / "CBMC"），后端扩展字段 */
	tool?: string;
}

/** 形式式化验证汇总统计 */
export interface VerificationSummary {
	/** 总检查数 */
	total: number;
	/** 通过数 */
	passed: number;
	/** 失败数 */
	failed: number;
	/** 跳过数 */
	skipped: number;
}

/** 完整形式化验证结果（与 /api/verify 返回 JSON 一致） */
export interface VerificationResult {
	/** 总体状态：failed 优先，其次 passed，全 skipped 时为 skipped */
	status: VerificationStatus;
	/** 汇总统计 */
	summary: VerificationSummary;
	/** 各检查项详情 */
	checks: VerificationCheck[];
	/** 总耗时（毫秒） */
	total_duration_ms: number;
	/** 使用的工具标签：Z3 / CBMC / Z3+CBMC / Mock */
	tool: string;
	/** 错误信息（如契约文件不存在等，可选） */
	error?: string;
}

/** 调用 /api/verify 的请求体 */
export interface VerifyRequest {
	/** 契约文本（YAML 或 JSON 字符串），与 contract_path 二选一 */
	contract?: string;
	/** 契约文件路径（服务端读取），优先级低于 contract */
	contract_path?: string;
	/** 可选的 C 代码文本（提供后启用 CBMC） */
	code?: string;
}
