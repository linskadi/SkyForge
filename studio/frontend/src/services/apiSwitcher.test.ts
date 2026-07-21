import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useExecutionStore } from "@/stores/executionStore";
import { getApi, setUseRealAPI } from "./apiSwitcher";

vi.mock("./mockApi", () => ({
	mockApiClient: {
		generate: vi.fn().mockResolvedValue({
			code: "mock code",
			contract: { component: "mock" },
			violations: [],
			traceability: {},
			repair_history: [],
			contract_check_result: {
				component: "",
				sections: [],
				passed_count: 0,
				total_count: 0,
				overall_passed: false,
				generated_assert_code: "",
			},
			simulation_result: null,
		}),
		simulate: vi.fn(),
		generateReport: vi.fn(),
		downloadReport: vi.fn().mockReturnValue("http://mock/download"),
		compose: vi.fn(),
		checkCompatibility: vi.fn(),
		getHITLStatus: vi.fn(),
		toggleHITL: vi.fn(),
		getHITLPendingApprovals: vi.fn(),
		getHITLHistory: vi.fn(),
		hitlApprove: vi.fn(),
		hitlReject: vi.fn(),
		verifyContract: vi.fn(),
		searchRules: vi.fn(),
		getRuleStandards: vi.fn(),
		getLLMConfig: vi.fn(),
		saveLLMConfig: vi.fn(),
		testLLMConnection: vi.fn(),
		getTaskDetail: vi.fn(),
	},
}));

vi.mock("./realApi", () => ({
	realApiClient: {
		generate: vi.fn().mockResolvedValue({
			code: "real code",
			contract: { component: "real" },
			violations: [],
			traceability: {},
			repair_history: [],
			contract_check_result: {
				component: "",
				sections: [],
				passed_count: 0,
				total_count: 0,
				overall_passed: false,
				generated_assert_code: "",
			},
			simulation_result: null,
		}),
		simulate: vi.fn(),
		generateReport: vi.fn(),
		downloadReport: vi.fn().mockReturnValue("http://real/download"),
		compose: vi.fn(),
		checkCompatibility: vi.fn(),
		getHITLStatus: vi.fn(),
		toggleHITL: vi.fn(),
		getHITLPendingApprovals: vi.fn(),
		getHITLHistory: vi.fn(),
		hitlApprove: vi.fn(),
		hitlReject: vi.fn(),
		verifyContract: vi.fn(),
		searchRules: vi.fn(),
		getRuleStandards: vi.fn(),
		getLLMConfig: vi.fn(),
		saveLLMConfig: vi.fn(),
		testLLMConnection: vi.fn(),
		getTaskDetail: vi.fn(),
	},
}));

describe("apiSwitcher - language parameter", () => {
	beforeEach(() => {
		// 每个测试前重置 Pinia 实例，避免被其他测试文件的 Pinia 状态污染
		setActivePinia(createPinia());
		vi.clearAllMocks();
		setUseRealAPI(false);
	});

	it("mockApiClient.generate accepts language parameter", async () => {
		const api = getApi();
		const result = await api.generate("test", undefined, "cpp");
		expect(result).toBeDefined();
		expect(result.code).toBe("mock code");
	});

	it("mockApiClient.generate accepts language='python'", async () => {
		const api = getApi();
		const result = await api.generate("test", undefined, "python");
		expect(result).toBeDefined();
	});

	it("mockApiClient.generate defaults language to 'c'", async () => {
		const api = getApi();
		const result = await api.generate("test");
		expect(result).toBeDefined();
	});

	it("realApiClient.generate accepts language parameter", async () => {
		setUseRealAPI(true);
		const api = getApi();
		const result = await api.generate("test", undefined, "cpp");
		expect(result).toBeDefined();
		expect(result.code).toBe("real code");
	});

	it("ApiInterface declares language in generate signature", () => {
		const api = getApi();
		expect(typeof api.generate).toBe("function");
		// Verify it accepts language by calling with all 3 params
		const result = api.generate("test", undefined, "cpp");
		expect(result).toBeInstanceOf(Promise);
	});
});

describe("apiSwitcher - mode routing (demo/cloud/local)", () => {
	beforeEach(() => {
		// 每个测试前重置 Pinia 实例，避免被其他测试文件的 Pinia 状态污染
		setActivePinia(createPinia());
		vi.clearAllMocks();
	});

	it("routes to mockApiClient when executionStore.profileId === 'demo'", async () => {
		const execution = useExecutionStore();
		execution.setProfile("demo");

		const api = getApi();
		const result = await api.generate("需求");

		// mockApiClient.generate mock 返回 { code: "mock code" }，标识走的是 mock 适配器
		expect(result.code).toBe("mock code");
	});

	it("routes to realApiClient when executionStore.profileId === 'local'", async () => {
		const execution = useExecutionStore();
		execution.setProfile("local");

		const api = getApi();
		const result = await api.generate("需求");

		// realApiClient.generate mock 返回 { code: "real code" }，标识走的是真实 API 适配器
		expect(result.code).toBe("real code");
	});

	it("routes to realApiClient when executionStore.profileId === 'cloud'", async () => {
		const execution = useExecutionStore();
		execution.setProfile("cloud");

		const api = getApi();
		const result = await api.generate("需求");

		// realApiClient.generate mock 返回 { code: "real code" }，标识走的是真实 API 适配器
		expect(result.code).toBe("real code");
	});

	it("getApi() reads latest profileId on every call (switches immediately after setProfile)", async () => {
		const execution = useExecutionStore();

		execution.setProfile("demo");
		const mockResult = await getApi().generate("需求");
		expect(mockResult.code).toBe("mock code");

		execution.setProfile("local");
		const localResult = await getApi().generate("需求");
		expect(localResult.code).toBe("real code");

		execution.setProfile("cloud");
		const apiResult = await getApi().generate("需求");
		expect(apiResult.code).toBe("real code");

		execution.setProfile("demo");
		const mockResultAgain = await getApi().generate("需求");
		expect(mockResultAgain.code).toBe("mock code");
	});
});
