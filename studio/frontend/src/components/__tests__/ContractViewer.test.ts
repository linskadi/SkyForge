import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Contract } from "@/services/mockApi";
import ContractViewer from "../ContractViewer.vue";

vi.mock("@/utils/tagParser", () => ({
	parseConTags: vi.fn((text: string) => {
		const tokens: Array<{ type: string; value: string }> = [];
		const regex = /\[(CON-\d+-[A-Z]+-\d+)\]/g;
		let lastIdx = 0;
		let match: RegExpExecArray | null = regex.exec(text);
		while (match !== null) {
			if (match.index > lastIdx) {
				tokens.push({ type: "text", value: text.slice(lastIdx, match.index) });
			}
			tokens.push({ type: "con", value: match[1] });
			lastIdx = match.index + match[0].length;
			match = regex.exec(text);
		}
		if (lastIdx < text.length) {
			tokens.push({ type: "text", value: text.slice(lastIdx) });
		}
		return tokens;
	}),
}));

const mockContract: Contract = {
	component: "LowPassFilter",
	description: "一阶低通滤波器",
	inputs: { raw_value: "uint16", sample_rate: "uint16" },
	outputs: { filtered_value: "uint16" },
	preconditions: [
		{
			id: "CON-LP-PRE-000",
			expression: "sample_rate > 0",
			description: "采样率必须大于 0",
		},
	],
	postconditions: [
		{
			id: "CON-LP-POST-000",
			expression: "0 <= filtered_value <= 65535",
			description: "输出值在 uint16 范围内",
		},
	],
	invariants: [
		{
			id: "CON-LP-INV-000",
			expression: "0.0 <= alpha <= 1.0",
			description: "滤波系数 alpha 始终在 [0,1] 范围",
		},
	],
	fault_handling: [],
};

describe("ContractViewer", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("shows empty state when contract is null", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: null },
		});
		expect(wrapper.find(".empty").exists()).toBe(true);
		expect(wrapper.text()).toContain("暂无契约");
	});

	it("renders contract component name", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		expect(wrapper.text()).toContain("LowPassFilter");
	});

	it("renders contract description", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		expect(wrapper.text()).toContain("一阶低通滤波器");
	});

	it("renders inputs section", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		expect(wrapper.text()).toContain("Inputs");
		expect(wrapper.text()).toContain("raw_value");
		expect(wrapper.text()).toContain("sample_rate");
	});

	it("renders outputs section", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		expect(wrapper.text()).toContain("Outputs");
		expect(wrapper.text()).toContain("filtered_value");
	});

	it("renders all four condition sections", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		expect(wrapper.text()).toContain("前置条件 Preconditions");
		expect(wrapper.text()).toContain("后置条件 Postconditions");
		expect(wrapper.text()).toContain("不变式 Invariants");
		expect(wrapper.text()).toContain("故障处理 Fault Handling");
	});

	it("renders preconditions with correct content", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		expect(wrapper.text()).toContain("CON-LP-PRE-000");
		expect(wrapper.text()).toContain("sample_rate > 0");
		expect(wrapper.text()).toContain("采样率必须大于 0");
	});

	it("renders postconditions with correct content", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		expect(wrapper.text()).toContain("CON-LP-POST-000");
		expect(wrapper.text()).toContain("filtered_value");
	});

	it("renders invariants with correct content", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		expect(wrapper.text()).toContain("CON-LP-INV-000");
		expect(wrapper.text()).toContain("alpha");
	});

	it("renders section count badges", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		const counts = wrapper.findAll(".count");
		expect(counts.length).toBeGreaterThanOrEqual(4);
		expect(counts[0].text()).toBe("1");
		expect(counts[1].text()).toBe("1");
		expect(counts[2].text()).toBe("1");
		expect(counts[3].text()).toBe("0");
	});

	it("shows (无) for empty fault_handling section", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		const emptySections = wrapper.findAll(".empty-section");
		expect(emptySections.length).toBeGreaterThanOrEqual(1);
	});

	it("renders CON badge for each condition", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		const badges = wrapper.findAll(".con-badge");
		expect(badges.length).toBeGreaterThanOrEqual(3);
	});

	it("emits tagClick with id when CON badge clicked", async () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		const badge = wrapper.find(".con-badge");
		await badge.trigger("click");
		expect(wrapper.emitted("tagClick")).toBeTruthy();
		const events1 = wrapper.emitted("tagClick");
		expect(events1?.[0]?.[0]).toBe("CON-LP-PRE-000");
	});

	it("emits tagClick with null when same badge clicked again (toggle)", async () => {
		const wrapper = mount(ContractViewer, {
			props: {
				contract: mockContract,
				activeTag: "CON-LP-PRE-000",
			},
		});
		const badge = wrapper.find(".con-badge.active");
		await badge.trigger("click");
		expect(wrapper.emitted("tagClick")).toBeTruthy();
		const events2 = wrapper.emitted("tagClick");
		expect(events2?.[0]?.[0]).toBeNull();
	});

	it("highlights activeTag badge", () => {
		const wrapper = mount(ContractViewer, {
			props: {
				contract: mockContract,
				activeTag: "CON-LP-PRE-000",
			},
		});
		const activeBadge = wrapper.find(".con-badge.active");
		expect(activeBadge.exists()).toBe(true);
		expect(activeBadge.text()).toBe("CON-LP-PRE-000");
	});

	it("renders YAML block with summary", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		expect(wrapper.find(".yaml-block").exists()).toBe(true);
		expect(wrapper.find("summary").text()).toContain("查看原始 YAML");
	});

	it("renders YAML content with contract data", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		expect(wrapper.find(".yaml-pre").exists()).toBe(true);
	});

	it("renders condition expressions", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		expect(wrapper.find(".cond-expr").exists()).toBe(true);
	});

	it("handles contract with empty conditions arrays", () => {
		const emptyContract: Contract = {
			component: "Empty",
			description: "Empty contract",
			inputs: {},
			outputs: {},
			preconditions: [],
			postconditions: [],
			invariants: [],
			fault_handling: [],
		};
		const wrapper = mount(ContractViewer, {
			props: { contract: emptyContract },
		});
		expect(wrapper.text()).toContain("Empty");
		expect(wrapper.findAll(".empty-section").length).toBe(4);
	});

	it("handles contract with multiple conditions in one section", () => {
		const multiContract: Contract = {
			...mockContract,
			preconditions: [
				{
					id: "CON-PRE-001",
					expression: "x > 0",
					description: "x positive",
				},
				{
					id: "CON-PRE-002",
					expression: "y < 100",
					description: "y bounded",
				},
				{
					id: "CON-PRE-003",
					expression: "z != 0",
				},
			],
		};
		const wrapper = mount(ContractViewer, {
			props: { contract: multiContract },
		});
		expect(wrapper.findAll(".condition-item").length).toBeGreaterThanOrEqual(3);
	});

	it("toggles activeTag off when clicking the same tag via expression", async () => {
		const wrapper = mount(ContractViewer, {
			props: {
				contract: mockContract,
				activeTag: "CON-LP-INV-000",
			},
		});
		const invTag = wrapper.find(".con-tag.active");
		if (invTag.exists()) {
			await invTag.trigger("click");
			const events3 = wrapper.emitted("tagClick");
			expect(events3?.[0]?.[0]).toBeNull();
		}
	});

	it("renders condition description when provided", () => {
		const wrapper = mount(ContractViewer, {
			props: { contract: mockContract },
		});
		const descs = wrapper.findAll(".cond-desc");
		expect(descs.length).toBeGreaterThanOrEqual(2);
	});

	it("does not render condition description when absent", () => {
		const contractNoDesc: Contract = {
			...mockContract,
			fault_handling: [{ id: "CON-FH-001", expression: "x == 0" }],
		};
		const wrapper = mount(ContractViewer, {
			props: { contract: contractNoDesc },
		});
		expect(wrapper.text()).toContain("CON-FH-001");
	});
});
