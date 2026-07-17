import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FaultInjectPanel from "../FaultInjectPanel.vue";

vi.mock("lucide-vue-next", () => ({
	AlertTriangle: { name: "AlertTriangle", template: "<span />" },
	ArrowUpDown: { name: "ArrowUpDown", template: "<span />" },
	CircleDot: { name: "CircleDot", template: "<span />" },
	Clock: { name: "Clock", template: "<span />" },
	Gauge: { name: "Gauge", template: "<span />" },
	Lock: { name: "Lock", template: "<span />" },
	RotateCcw: { name: "RotateCcw", template: "<span />" },
	SignalZero: { name: "SignalZero", template: "<span />" },
	Siren: { name: "Siren", template: "<span />" },
	ToggleLeft: { name: "ToggleLeft", template: "<span />" },
	TrendingUp: { name: "TrendingUp", template: "<span />" },
	Waves: { name: "Waves", template: "<span />" },
	Zap: { name: "Zap", template: "<span />" },
}));

vi.mock("@/components/ui/button", () => ({
	Button: {
		name: "Button",
		template:
			'<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
		props: ["variant", "size", "disabled"],
		emits: ["click"],
	},
}));

vi.mock("@/components/ui/card", () => ({
	Card: { name: "Card", template: '<div class="card"><slot /></div>' },
	CardContent: {
		name: "CardContent",
		template: '<div class="card-content"><slot /></div>',
	},
	CardHeader: {
		name: "CardHeader",
		template: '<div class="card-header"><slot /></div>',
	},
	CardTitle: {
		name: "CardTitle",
		template: '<div class="card-title"><slot /></div>',
	},
}));

vi.mock("@/components/ui/input", () => ({
	Input: {
		name: "Input",
		template:
			'<input :type="type" :modelValue="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
		props: ["type", "modelValue"],
		emits: ["update:modelValue"],
	},
}));

vi.mock("@/components/ui/label", () => ({
	Label: {
		name: "Label",
		template: "<label><slot /></label>",
	},
}));

vi.mock("@/components/ui/switch", () => ({
	Switch: {
		name: "Switch",
		template:
			'<button class="switch" :class="{ checked: modelValue }" @click="$emit(\'update:modelValue\', !modelValue)" />',
		props: ["modelValue"],
		emits: ["update:modelValue"],
	},
}));

describe("FaultInjectPanel", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders panel title", () => {
		const wrapper = mount(FaultInjectPanel);
		expect(wrapper.text()).toContain("故障注入面板");
	});

	it("renders fault type cards grouped by category", () => {
		const wrapper = mount(FaultInjectPanel);
		expect(wrapper.text()).toContain("传感器");
		expect(wrapper.text()).toContain("信号质量");
		expect(wrapper.text()).toContain("通信时序");
		expect(wrapper.text()).toContain("退化");
	});

	it("renders bias fault card", () => {
		const wrapper = mount(FaultInjectPanel);
		expect(wrapper.text()).toContain("传感器偏置");
		expect(wrapper.text()).toContain("Bias");
	});

	it("renders signal_loss fault card", () => {
		const wrapper = mount(FaultInjectPanel);
		expect(wrapper.text()).toContain("信号丢失");
		expect(wrapper.text()).toContain("Signal Loss");
	});

	it("renders all 12 fault types", () => {
		const wrapper = mount(FaultInjectPanel);
		const faultTypes = [
			"传感器偏置",
			"信号丢失",
			"高频噪声",
			"卡死故障",
			"阶跃突变",
			"饱和截断",
			"间歇性故障",
			"丢帧",
			"渐变漂移",
			"零输出",
			"符号反转",
			"跳变毛刺",
		];
		for (const name of faultTypes) {
			expect(wrapper.text()).toContain(name);
		}
	});

	it("inject button is disabled when no faults are enabled", () => {
		const wrapper = mount(FaultInjectPanel);
		const injectBtn = wrapper
			.findAll("button")
			.find((btn) => btn.text().includes("注入故障"));
		expect(injectBtn?.attributes("disabled")).toBeDefined();
	});

	it("shows hint text when no faults selected", () => {
		const wrapper = mount(FaultInjectPanel);
		expect(wrapper.text()).toContain("可同时选择多种故障类型");
	});

	it("resets all fault states when reset button clicked", async () => {
		const wrapper = mount(FaultInjectPanel);
		const switches = wrapper.findAll(".switch");
		if (switches.length > 0) {
			await switches[0].trigger("click");
			expect(wrapper.text()).toContain("已选择");
			const resetBtn = wrapper
				.findAll("button")
				.find((btn) => btn.text().includes("重置参数"));
			await resetBtn?.trigger("click");
			expect(wrapper.text()).toContain("可同时选择多种故障类型");
		}
	});

	it("shows enabled count when faults are selected", async () => {
		const wrapper = mount(FaultInjectPanel);
		const switches = wrapper.findAll(".switch");
		if (switches.length > 0) {
			await switches[0].trigger("click");
			expect(wrapper.text()).toContain("已选择 1 种故障");
		}
	});

	it("inject button is enabled after enabling a fault", async () => {
		const wrapper = mount(FaultInjectPanel);
		const switches = wrapper.findAll(".switch");
		if (switches.length > 0) {
			await switches[0].trigger("click");
			const injectBtn = wrapper
				.findAll("button")
				.find((btn) => btn.text().includes("注入故障"));
			expect(injectBtn?.attributes("disabled")).toBeUndefined();
		}
	});

	it("emits inject event with enabled faults", async () => {
		const wrapper = mount(FaultInjectPanel);
		const switches = wrapper.findAll(".switch");
		if (switches.length > 0) {
			await switches[0].trigger("click");
			const injectBtn = wrapper
				.findAll("button")
				.find((btn) => btn.text().includes("注入故障"));
			await injectBtn?.trigger("click");
			expect(wrapper.emitted("inject")).toBeTruthy();
			expect(wrapper.emitted("inject")![0][0]).toEqual(
				expect.arrayContaining([
					expect.objectContaining({
						type: expect.any(String),
						params: expect.any(Object),
					}),
				]),
			);
		}
	});

	it("shows inject count badge when multiple faults selected", async () => {
		const wrapper = mount(FaultInjectPanel);
		const switches = wrapper.findAll(".switch");
		if (switches.length >= 2) {
			await switches[0].trigger("click");
			await switches[1].trigger("click");
			expect(wrapper.text()).toContain("×2");
		}
	});

	it("does not emit inject when no faults enabled", async () => {
		const wrapper = mount(FaultInjectPanel);
		const injectBtn = wrapper
			.findAll("button")
			.find((btn) => btn.text().includes("注入故障"));
		await injectBtn?.trigger("click");
		expect(wrapper.emitted("inject")).toBeUndefined();
	});

	it("toggles fault card active class on switch click", async () => {
		const wrapper = mount(FaultInjectPanel);
		const switches = wrapper.findAll(".switch");
		if (switches.length > 0) {
			const firstCard = wrapper.find(".fault-card");
			expect(firstCard.classes("active")).toBe(false);
			await switches[0].trigger("click");
			expect(wrapper.findAll(".fault-card.active").length).toBeGreaterThan(0);
		}
	});

	it("shows parameter controls when fault is enabled", async () => {
		const wrapper = mount(FaultInjectPanel);
		const switches = wrapper.findAll(".switch");
		if (switches.length > 0) {
			await switches[0].trigger("click");
			expect(wrapper.find(".card-params").exists()).toBe(true);
		}
	});

	it("renders bias parameter slider", async () => {
		const wrapper = mount(FaultInjectPanel);
		const switches = wrapper.findAll(".switch");
		if (switches.length > 0) {
			await switches[0].trigger("click");
			expect(wrapper.find(".param-slider").exists()).toBe(true);
			expect(wrapper.text()).toContain("偏置值");
		}
	});

	it("supports enabling multiple faults simultaneously", async () => {
		const wrapper = mount(FaultInjectPanel);
		const switches = wrapper.findAll(".switch");
		if (switches.length >= 3) {
			await switches[0].trigger("click");
			await switches[1].trigger("click");
			await switches[2].trigger("click");
			expect(wrapper.text()).toContain("已选择 3 种故障");
		}
	});
});
