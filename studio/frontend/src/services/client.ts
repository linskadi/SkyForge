/**
 * Unified HTTP Client
 * ====================================================================
 * Single fetch-based HTTP client replacing both:
 *   - src/utils/request.ts (axios)
 *   - src/services/api.ts (inline fetch helpers)
 *
 * Features:
 * 1. Fetch-based — no axios dependency
 * 2. Configurable timeout (default 30s)
 * 3. JSON error handling with structured ApiError
 * 4. Mock/real switching via apiSwitcher
 * 5. Re-exports the base URL for download/report scenarios
 * 6. 统一 HTTP 错误 toast 提示（T3.3）：4xx/5xx → toast `[错误] status: detail`
 */

import { toast } from "@/components/ui/toast/use-toast";

/** API 基础地址 */
export const API_BASE_URL =
	import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/** 默认请求超时（毫秒） */
const DEFAULT_TIMEOUT_MS = 30_000;

/** 结构化 API 错误 */
export class ApiError extends Error {
	constructor(
		public status: number,
		public statusText: string,
		public body?: unknown,
	) {
		super(`HTTP ${status} ${statusText}`);
		this.name = "ApiError";
	}
}

/**
 * 从 ApiError body 中提取后端 FastAPI 错误 detail 字段
 *
 * FastAPI HTTPException 默认响应体为 `{"detail": "..."}`，
 * 也可能为 `{"message": "..."}` 或纯字符串。优先取 detail，其次 message。
 */
function extractErrorDetail(body: unknown): string {
	if (body == null) return "";
	if (typeof body === "string") return body;
	if (typeof body === "object") {
		const obj = body as Record<string, unknown>;
		if (typeof obj.detail === "string") return obj.detail;
		if (typeof obj.message === "string") return obj.message;
	}
	return "";
}

/**
 * 统一 HTTP 错误 toast 提示（T3.3）
 *
 * 在抛出 ApiError 前触发 toast，格式：`[错误] ${status}: ${detail}`
 * 调用方仍可通过 try/catch 捕获 ApiError 实现自己的错误展示逻辑
 * （如 Generate.vue 的错误面板 + 重试按钮）。
 */
function notifyHttpError(err: ApiError): void {
	const detail = extractErrorDetail(err.body) || err.statusText || "未知错误";
	toast({
		title: `[错误] ${err.status}`,
		description: detail,
		variant: "destructive",
	});
}

/**
 * 带超时的 fetch 封装
 *
 * @param url 完整 URL 或相对路径（相对路径自动拼接 API_BASE_URL）
 * @param options fetch 配置
 * @param timeout 超时毫秒
 * @returns 解析后的 JSON 数据
 */
export async function request<T>(
	path: string,
	options: RequestInit = {},
	timeout: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
	const url = path.startsWith("http") ? path : `${API_BASE_URL}${path}`;
	const controller = new AbortController();
	const timer = setTimeout(() => controller.abort(), timeout);
	try {
		const response = await fetch(url, {
			...options,
			signal: controller.signal,
		});
		if (!response.ok) {
			let body: unknown;
			try {
				body = await response.json();
			} catch {
				body = await response.text().catch(() => null);
			}
			const err = new ApiError(response.status, response.statusText, body);
			notifyHttpError(err);
			throw err;
		}
		return response.json();
	} finally {
		clearTimeout(timer);
	}
}

/** GET 请求 */
export function getJSON<T>(path: string, timeout?: number): Promise<T> {
	return request<T>(
		path,
		{
			method: "GET",
			headers: { Accept: "application/json" },
		},
		timeout,
	);
}

/** POST JSON 请求 */
export function postJSON<T>(
	path: string,
	body: unknown,
	timeout?: number,
): Promise<T> {
	return request<T>(
		path,
		{
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(body),
		},
		timeout,
	);
}

/** POST FormData 请求（用于文件上传） */
export function postFormData<T>(
	path: string,
	formData: FormData,
	timeout?: number,
): Promise<T> {
	return request<T>(
		path,
		{
			method: "POST",
			body: formData,
		},
		timeout ?? 30_000,
	);
}

/** DELETE 请求 */
export function deleteJSON<T>(path: string, timeout?: number): Promise<T> {
	return request<T>(
		path,
		{
			method: "DELETE",
			headers: { Accept: "application/json" },
		},
		timeout,
	);
}
