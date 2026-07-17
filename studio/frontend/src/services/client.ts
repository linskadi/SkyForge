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
 */

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
			throw new ApiError(response.status, response.statusText, body);
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
