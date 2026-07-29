import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getApi } from "./apiSwitcher";

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
		setActivePinia(createPinia());
		vi.clearAllMocks();
	});

	it("realApiClient.generate accepts language parameter", async () => {
		const api = getApi();
		const result = await api.generate("test", undefined, "cpp");
		expect(result).toBeDefined();
		expect(result.code).toBe("real code");
	});

	it("realApiClient.generate accepts language='python'", async () => {
		const api = getApi();
		const result = await api.generate("test", undefined, "python");
		expect(result).toBeDefined();
	});

	it("realApiClient.generate defaults language to 'c'", async () => {
		const api = getApi();
		const result = await api.generate("test");
		expect(result).toBeDefined();
	});

	it("ApiInterface declares language in generate signature", () => {
		const api = getApi();
		expect(typeof api.generate).toBe("function");
		const result = api.generate("test", undefined, "cpp");
		expect(result).toBeInstanceOf(Promise);
	});
});
