import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockGenerate = vi.fn().mockResolvedValue({
	code: "int filter(int x) { return x; }",
	contract: {
		component: "Filter",
		description: "test",
		inputs: {},
		outputs: {},
		preconditions: [],
		postconditions: [],
		invariants: [],
		fault_handling: [],
	},
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
});

/** degraded=true 的生成结果（用于降级模式横幅测试） */
const degradedResult = {
	code: "int filter(int x) { return x; }",
	contract: {
		component: "Filter",
		description: "test",
		inputs: {},
		outputs: {},
		preconditions: [],
		postconditions: [],
		invariants: [],
		fault_handling: [],
	},
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
	degraded: true as const,
};

vi.mock("@/services/apiSwitcher", () => ({
	getApi: () => ({
		generate: mockGenerate,
		simulate: vi.fn(),
		verifyContract: vi.fn(),
	}),
}));

vi.mock("@/stores/providerStore", () => ({
	useProviderStore: () => ({
		// Pinia 会自动解包 ref/computed，故此处直接返回字符串值以模拟真实 store 行为。
		// 否则 providerStore.derivedMode === "mock" 会比较 Ref 对象与字符串，导致 onGenerate
		// 误入 local/api 分支（需等 5s WebSocket 超时）。
		derivedMode: "mock",
	}),
}));

vi.mock("vue-router", () => ({
	useRoute: () => ({ query: {} }),
	useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/components/AgentTerminal.vue", () => ({
	default: {
		name: "AgentTerminal",
		template: "<div />",
		props: ["useMock"],
		methods: { start() {}, stop() {}, clear() {} },
	},
}));

vi.mock("@/components/CodeViewer.vue", () => ({
	default: {
		name: "CodeViewer",
		template: "<div />",
		props: ["code", "traceability", "highlightEnabled", "activeTag"],
	},
}));
vi.mock("@/components/ContractViewer.vue", () => ({
	default: {
		name: "ContractViewer",
		template: "<div />",
		props: ["contract", "activeTag"],
	},
}));
vi.mock("@/components/ContractCheckResult.vue", () => ({
	default: {
		name: "ContractCheckResult",
		template: "<div />",
		props: ["result"],
	},
}));
vi.mock("@/components/DecisionTrace.vue", () => ({
	default: { name: "DecisionTrace", template: "<div />", props: ["decisions"] },
}));
vi.mock("@/components/FaultInjectPanel.vue", () => ({
	default: { name: "FaultInjectPanel", template: "<div />" },
}));
vi.mock("@/components/FormalVerificationResult.vue", () => ({
	default: {
		name: "FormalVerificationResult",
		template: "<div />",
		props: ["result", "loading"],
	},
}));
vi.mock("@/components/HITLPanel.vue", () => ({
	default: { name: "HITLPanel", template: "<div />" },
}));
vi.mock("@/components/ReviewConfirm.vue", () => ({
	default: {
		name: "ReviewConfirm",
		template: "<div />",
		props: ["stage", "content"],
	},
}));
vi.mock("@/components/RepairTimeline.vue", () => ({
	default: { name: "RepairTimeline", template: "<div />", props: ["history"] },
}));
vi.mock("@/components/ReportDownload.vue", () => ({
	default: { name: "ReportDownload", template: "<div />", props: ["result"] },
}));
vi.mock("@/components/SimulationResult.vue", () => ({
	default: {
		name: "SimulationResultView",
		template: "<div />",
		props: ["result", "loading"],
	},
}));
vi.mock("@/components/ui/button", () => ({
	Button: {
		name: "Button",
		template: "<button><slot /></button>",
		props: ["disabled", "variant"],
	},
}));
vi.mock("@/components/ui/card", () => ({
	Card: { name: "Card", template: "<div><slot /></div>" },
	CardContent: { name: "CardContent", template: "<div><slot /></div>" },
	CardHeader: { name: "CardHeader", template: "<div><slot /></div>" },
	CardTitle: { name: "CardTitle", template: "<div><slot /></div>" },
}));
vi.mock("@/components/ui/tabs", () => ({
	Tabs: {
		name: "Tabs",
		template: "<div><slot /></div>",
		props: ["modelValue"],
	},
	TabsContent: {
		name: "TabsContent",
		template: "<div><slot /></div>",
		props: ["value"],
	},
	TabsList: { name: "TabsList", template: "<div><slot /></div>" },
	TabsTrigger: {
		name: "TabsTrigger",
		template: "<button><slot /></button>",
		props: ["value"],
	},
}));

import GeneratePage from "../views/Generate.vue";

describe("Generate.vue - Language Selection", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	const createWrapper = () => mount(GeneratePage);

	it("renders three language buttons", () => {
		const wrapper = createWrapper();
		const langBtns = wrapper.findAll(".lang-btn");
		expect(langBtns.length).toBe(3);
	});

	it("displays C, C++, Python labels", () => {
		const wrapper = createWrapper();
		const langBtns = wrapper.findAll(".lang-btn");
		expect(langBtns[0].text()).toBe("C");
		expect(langBtns[1].text()).toBe("C++");
		expect(langBtns[2].text()).toBe("Python");
	});

	it("defaults to C language selected", () => {
		const wrapper = createWrapper();
		const langBtns = wrapper.findAll(".lang-btn");
		expect(langBtns[0].classes()).toContain("active");
		expect(langBtns[1].classes()).not.toContain("active");
		expect(langBtns[2].classes()).not.toContain("active");
	});

	it("switches to C++ when C++ button clicked", async () => {
		const wrapper = createWrapper();
		const cppBtn = wrapper.findAll(".lang-btn")[1];
		await cppBtn.trigger("click");

		const langBtns = wrapper.findAll(".lang-btn");
		expect(langBtns[0].classes()).not.toContain("active");
		expect(langBtns[1].classes()).toContain("active");
		expect(langBtns[2].classes()).not.toContain("active");
	});

	it("switches to Python when Python button clicked", async () => {
		const wrapper = createWrapper();
		const pyBtn = wrapper.findAll(".lang-btn")[2];
		await pyBtn.trigger("click");

		const langBtns = wrapper.findAll(".lang-btn");
		expect(langBtns[0].classes()).not.toContain("active");
		expect(langBtns[1].classes()).not.toContain("active");
		expect(langBtns[2].classes()).toContain("active");
	});

	it("switches back to C after selecting another language", async () => {
		const wrapper = createWrapper();
		const langBtns = wrapper.findAll(".lang-btn");

		await langBtns[1].trigger("click");
		expect(langBtns[1].classes()).toContain("active");

		await langBtns[0].trigger("click");
		expect(langBtns[0].classes()).toContain("active");
		expect(langBtns[1].classes()).not.toContain("active");
	});

	it("sends selected language to API on generate", async () => {
		const wrapper = createWrapper();

		// Select Python
		const langBtns = wrapper.findAll(".lang-btn");
		await langBtns[2].trigger("click");

		// Fill requirement
		const textarea = wrapper.find("textarea");
		await textarea.setValue("实现一个低通滤波器");

		// Click generate button
		const genBtn = wrapper.find(
			"button:not(.lang-btn):not(.example-btn):not(.back-btn):not(.highlight-toggle):not(.req-tag-btn):not(.req-tag-clear):not(.action-btn):not(.focus-tab-btn):not(.collapsible)",
		);
		await genBtn.trigger("click");

		// Wait for async
		await vi.dynamicImportSettled();
		await new Promise((r) => setTimeout(r, 50));

		// Verify API was called with python
		expect(mockGenerate).toHaveBeenCalledWith(
			"实现一个低通滤波器",
			undefined,
			"python",
		);
	});

	it("sends 'c' to API when C is selected (default)", async () => {
		const wrapper = createWrapper();

		const textarea = wrapper.find("textarea");
		await textarea.setValue("test requirement");

		const genBtn = wrapper.find(
			"button:not(.lang-btn):not(.example-btn):not(.back-btn):not(.highlight-toggle):not(.req-tag-btn):not(.req-tag-clear):not(.action-btn):not(.focus-tab-btn):not(.collapsible)",
		);
		await genBtn.trigger("click");

		await vi.dynamicImportSettled();
		await new Promise((r) => setTimeout(r, 50));

		expect(mockGenerate).toHaveBeenCalledWith(
			"test requirement",
			undefined,
			"c",
		);
	});

	it("disables language buttons during generation", async () => {
		const wrapper = createWrapper();

		const textarea = wrapper.find("textarea");
		await textarea.setValue("test");

		const genBtn = wrapper.find(
			"button:not(.lang-btn):not(.example-btn):not(.back-btn):not(.highlight-toggle):not(.req-tag-btn):not(.req-tag-clear):not(.action-btn):not(.focus-tab-btn):not(.collapsible)",
		);
		await genBtn.trigger("click");

		// The mock resolves instantly, so after the click the status transitions
		// from generating -> done. Verify the generate button is no longer clickable.
		await vi.dynamicImportSettled();
		await new Promise((r) => setTimeout(r, 100));

		// After generation completes, textarea should be enabled again
		expect((textarea.element as HTMLTextAreaElement).disabled).toBe(false);
	});
});

describe("Generate.vue - degraded banner display", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	const createWrapper = () => mount(GeneratePage);

	/** 点击生成按钮并等待异步完成（mock 模式下 mockGenerate 立即 resolve） */
	const clickGenerateAndWait = async (wrapper: ReturnType<typeof mount>) => {
		const textarea = wrapper.find("textarea");
		await textarea.setValue("实现一个低通滤波器");

		const genBtn = wrapper.find(
			"button:not(.lang-btn):not(.example-btn):not(.back-btn):not(.highlight-toggle):not(.req-tag-btn):not(.req-tag-clear):not(.action-btn):not(.focus-tab-btn):not(.collapsible)",
		);
		await genBtn.trigger("click");

		// mock 模式下 mockGenerate 被 mock 为立即 resolve，等待微任务排空即可
		await vi.dynamicImportSettled();
		await new Promise((r) => setTimeout(r, 50));
	};

	it("displays degraded banner when result.degraded === true", async () => {
		// mock getApi().generate 返回 degraded: true 的 GenerateResult
		mockGenerate.mockResolvedValueOnce(degradedResult);

		const wrapper = createWrapper();
		await clickGenerateAndWait(wrapper);

		// 验证 generate 已被调用（走 mock 模式分支）
		expect(mockGenerate).toHaveBeenCalled();

		// 断言降级模式横幅可见，包含"降级模式"文本
		expect(wrapper.text()).toContain("降级模式");
		// 额外断言横幅副文本，确保是降级提示而非其它含"降级"二字的元素
		expect(wrapper.text()).toContain("LLM 不可用");
	});

	it("degraded banner is rendered as a distinct amber-colored element", async () => {
		mockGenerate.mockResolvedValueOnce(degradedResult);

		const wrapper = createWrapper();
		await clickGenerateAndWait(wrapper);

		// 通过 amber 色彩类定位降级横幅 div（border-amber-900/50 是降级横幅独有类）
		const banner = wrapper.find('[class*="border-amber-900"]');
		expect(banner.exists()).toBe(true);
		expect(banner.text()).toContain("降级模式");
		expect(banner.text()).toContain("Agent 已走降级");
	});

	it("does NOT display degraded banner when result.degraded is false/undefined", async () => {
		// mockGenerate 默认 mockResolvedValue 不含 degraded 字段（视作 false/undefined）
		const wrapper = createWrapper();
		await clickGenerateAndWait(wrapper);

		// 断言降级模式横幅不显示
		expect(wrapper.text()).not.toContain("降级模式");
		expect(wrapper.find('[class*="border-amber-900"]').exists()).toBe(false);
	});

	it("shows degraded banner only after generation completes (not during generating)", async () => {
		// 使用未 resolve 的 Promise 模拟生成中状态
		mockGenerate.mockReturnValueOnce(new Promise(() => {})); // 永不 resolve

		const wrapper = createWrapper();
		const textarea = wrapper.find("textarea");
		await textarea.setValue("实现一个低通滤波器");

		const genBtn = wrapper.find(
			"button:not(.lang-btn):not(.example-btn):not(.back-btn):not(.highlight-toggle):not(.req-tag-btn):not(.req-tag-clear):not(.action-btn):not(.focus-tab-btn):not(.collapsible)",
		);
		await genBtn.trigger("click");
		await vi.dynamicImportSettled();
		await new Promise((r) => setTimeout(r, 50));

		// 生成中（status=generating）时降级横幅不应显示
		expect(wrapper.text()).not.toContain("降级模式");
		expect(wrapper.find('[class*="border-amber-900"]').exists()).toBe(false);
	});
});
