import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./client", () => ({
	postJSON: vi.fn(),
	getJSON: vi.fn(),
	request: vi.fn(),
	API_BASE_URL: "http://localhost:8000",
}));

vi.mock("./mockApi", () => ({
	mockGenerate: vi.fn(),
}));

import { generate } from "./api";
import { postJSON } from "./client";
import { mockGenerate } from "./mockApi";

const mockPostJSON = vi.mocked(postJSON);
const mockMockGenerate = vi.mocked(mockGenerate);

describe("api.ts - generate language parameter", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("sends language='c' by default", async () => {
		mockPostJSON.mockResolvedValue({
			code: "int main() {}",
			contract: "component: test",
			cppcheck_result: [],
			repair_history: [],
			simulation_result: null,
		});

		await generate("test requirement");

		expect(mockPostJSON).toHaveBeenCalledWith(
			"/api/generate",
			{
				requirement: "test requirement",
				scade_file: "",
				language: "c",
			},
			180_000,
		);
	});

	it("sends language='cpp' when specified", async () => {
		mockPostJSON.mockResolvedValue({
			code: "int main() {}",
			contract: "component: test",
			cppcheck_result: [],
			repair_history: [],
			simulation_result: null,
		});

		await generate("test requirement", undefined, "cpp");

		expect(mockPostJSON).toHaveBeenCalledWith(
			"/api/generate",
			{
				requirement: "test requirement",
				scade_file: "",
				language: "cpp",
			},
			180_000,
		);
	});

	it("sends language='python' when specified", async () => {
		mockPostJSON.mockResolvedValue({
			code: "def main(): pass",
			contract: "component: test",
			cppcheck_result: [],
			repair_history: [],
			simulation_result: null,
		});

		await generate("test requirement", undefined, "python");

		expect(mockPostJSON).toHaveBeenCalledWith(
			"/api/generate",
			{
				requirement: "test requirement",
				scade_file: "",
				language: "python",
			},
			180_000,
		);
	});

	it("sends language alongside scadeFile", async () => {
		mockPostJSON.mockResolvedValue({
			code: "int main() {}",
			contract: "component: test",
			cppcheck_result: [],
			repair_history: [],
			simulation_result: null,
		});

		await generate("test requirement", "node Main\n  x = 1;\nend", "cpp");

		expect(mockPostJSON).toHaveBeenCalledWith(
			"/api/generate",
			{
				requirement: "test requirement",
				scade_file: "node Main\n  x = 1;\nend",
				language: "cpp",
			},
			180_000,
		);
	});

	it("defaults to 'c' when language is undefined", async () => {
		mockPostJSON.mockResolvedValue({
			code: "int main() {}",
			contract: "component: test",
			cppcheck_result: [],
			repair_history: [],
			simulation_result: null,
		});

		await generate("test", undefined, undefined);

		expect(mockPostJSON).toHaveBeenCalledWith(
			"/api/generate",
			{
				requirement: "test",
				scade_file: "",
				language: "c",
			},
			180_000,
		);
	});
});

describe("api.ts - backend failure propagation (no mockGenerate fallback)", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("rejects when postJSON returns 500 and does NOT call mockGenerate", async () => {
		// 模拟后端 500 错误（client.ts 在 response.ok=false 时抛 ApiError）
		const httpError = new Error("HTTP 500 Internal Server Error");
		mockPostJSON.mockRejectedValueOnce(httpError);

		// 调用 generate 应该 reject（抛出错误），而不是静默降级到 mockGenerate
		await expect(generate("需求")).rejects.toThrow();

		// 关键断言：后端失败时不应调用 mockGenerate（Spec Task 1 移除了 withFallback）
		expect(mockMockGenerate).not.toHaveBeenCalled();
	});

	it("rejects with ApiError-like error when backend returns non-ok status", async () => {
		const apiError = new Error("HTTP 503 Service Unavailable");
		mockPostJSON.mockRejectedValueOnce(apiError);

		await expect(generate("需求", undefined, "cpp")).rejects.toThrow(
			"HTTP 503 Service Unavailable",
		);

		expect(mockMockGenerate).not.toHaveBeenCalled();
	});

	it("does not silently fall back to mockGenerate on network errors", async () => {
		const networkError = new Error("Failed to fetch");
		mockPostJSON.mockRejectedValueOnce(networkError);

		await expect(generate("需求")).rejects.toThrow("Failed to fetch");

		// 网络错误同样不应触发 mockGenerate 降级
		expect(mockMockGenerate).not.toHaveBeenCalled();
	});
});
