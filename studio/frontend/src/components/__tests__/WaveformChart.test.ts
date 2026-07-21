import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WaveformChart from "../WaveformChart.vue";

vi.mock("vue-echarts", () => ({
	default: {
		name: "VChart",
		template: '<div class="v-chart-mock" />',
		props: ["option", "style", "autoresize"],
		setup() {
			return {
				chart: {
					getOption: vi.fn(() => ({
						dataZoom: [{ start: 0, end: 100 }],
					})),
					dispatchAction: vi.fn(),
					getDataURL: vi.fn(() => "data:image/png;base64,mockbase64data"),
				},
			};
		},
	},
}));

vi.mock("echarts/core", () => ({
	use: vi.fn(),
}));

vi.mock("echarts/charts", () => ({
	LineChart: {},
}));

vi.mock("echarts/components", () => ({
	DataZoomComponent: {},
	GridComponent: {},
	LegendComponent: {},
	MarkAreaComponent: {},
	TooltipComponent: {},
}));

vi.mock("echarts/renderers", () => ({
	CanvasRenderer: {},
}));

vi.mock("@lucide/vue", () => ({
	Download: { name: "Download", template: "<span />" },
	RotateCcw: { name: "RotateCcw", template: "<span />" },
	ZoomIn: { name: "ZoomIn", template: "<span />" },
	ZoomOut: { name: "ZoomOut", template: "<span />" },
}));

vi.mock("@/components/ui/button", () => ({
	Button: {
		name: "Button",
		template: "<button @click=\"$emit('click')\"><slot /></button>",
		props: ["variant", "size"],
		emits: ["click"],
	},
}));

describe("WaveformChart", () => {
	const defaultProps = {
		inputData: [100, 200, 300, 400, 500],
		outputData: [50, 150, 250, 350, 450],
	};

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders chart toolbar", () => {
		const wrapper = mount(WaveformChart, { props: defaultProps });
		expect(wrapper.find(".chart-toolbar").exists()).toBe(true);
	});

	it("renders legend items", () => {
		const wrapper = mount(WaveformChart, { props: defaultProps });
		expect(wrapper.find(".legend").exists()).toBe(true);
		expect(wrapper.text()).toContain("输入波形");
		expect(wrapper.text()).toContain("输出波形");
	});

	it("does not show fault range legend when no faultRange", () => {
		const wrapper = mount(WaveformChart, { props: defaultProps });
		expect(wrapper.text()).not.toContain("故障区间");
	});

	it("shows fault range legend when faultRange is provided", () => {
		const wrapper = mount(WaveformChart, {
			props: {
				...defaultProps,
				faultRange: { start: 2, end: 4 },
			},
		});
		expect(wrapper.text()).toContain("故障区间");
	});

	it("renders toolbar action buttons", () => {
		const wrapper = mount(WaveformChart, { props: defaultProps });
		expect(wrapper.findAll(".toolbar-actions button")).toHaveLength(4);
	});

	it("renders chart hint text", () => {
		const wrapper = mount(WaveformChart, { props: defaultProps });
		expect(wrapper.text()).toContain("鼠标滚轮缩放");
		expect(wrapper.text()).toContain("导出 PNG");
	});

	it("applies custom height to chart via style prop", () => {
		const wrapper = mount(WaveformChart, {
			props: { ...defaultProps, height: 500 },
		});
		const vChart = wrapper.findComponent({ name: "VChart" });
		expect(vChart.props("style")).toEqual(
			expect.objectContaining({ height: "500px" }),
		);
	});

	it("uses default height of 320px via style prop", () => {
		const wrapper = mount(WaveformChart, { props: defaultProps });
		const vChart = wrapper.findComponent({ name: "VChart" });
		expect(vChart.props("style")).toEqual(
			expect.objectContaining({ height: "320px" }),
		);
	});

	it("passes option to VChart", () => {
		const wrapper = mount(WaveformChart, { props: defaultProps });
		const vChart = wrapper.findComponent({ name: "VChart" });
		expect(vChart.props("option")).toBeDefined();
	});

	it("option contains correct series data", () => {
		const wrapper = mount(WaveformChart, { props: defaultProps });
		const vChart = wrapper.findComponent({ name: "VChart" });
		const option = vChart.props("option") as Record<string, unknown>;
		const series = option.series as Array<Record<string, unknown>>;
		expect(series[0].data).toEqual(defaultProps.inputData);
		expect(series[1].data).toEqual(defaultProps.outputData);
		expect(series[0].name).toBe("输入波形");
		expect(series[1].name).toBe("输出波形");
	});

	it("option includes fault range markArea when provided", () => {
		const wrapper = mount(WaveformChart, {
			props: {
				...defaultProps,
				faultRange: { start: 50, end: 80 },
			},
		});
		const vChart = wrapper.findComponent({ name: "VChart" });
		const option = vChart.props("option") as Record<string, unknown>;
		const series = option.series as Array<Record<string, unknown>>;
		const markArea = series[0].markArea as Record<string, unknown>;
		expect(markArea).toBeDefined();
		const markData = markArea.data as Array<Array<Record<string, number>>>;
		expect(markData[0][0].xAxis).toBe(50);
		expect(markData[0][1].xAxis).toBe(80);
	});

	it("option has no markArea when faultRange is null", () => {
		const wrapper = mount(WaveformChart, { props: defaultProps });
		const vChart = wrapper.findComponent({ name: "VChart" });
		const option = vChart.props("option") as Record<string, unknown>;
		const series = option.series as Array<Record<string, unknown>>;
		expect(series[0].markArea).toBeUndefined();
	});

	it("option includes dataZoom for scroll", () => {
		const wrapper = mount(WaveformChart, { props: defaultProps });
		const vChart = wrapper.findComponent({ name: "VChart" });
		const option = vChart.props("option") as Record<string, unknown>;
		const dataZoom = option.dataZoom as Array<Record<string, string>>;
		expect(dataZoom).toHaveLength(1);
		expect(dataZoom[0].type).toBe("inside");
	});

	it("option includes tooltip configuration", () => {
		const wrapper = mount(WaveformChart, { props: defaultProps });
		const vChart = wrapper.findComponent({ name: "VChart" });
		const option = vChart.props("option") as Record<string, unknown>;
		const tooltip = option.tooltip as Record<string, string>;
		expect(tooltip.trigger).toBe("axis");
	});

	it("tooltip formatter handles fault range warning", () => {
		const wrapper = mount(WaveformChart, {
			props: {
				...defaultProps,
				faultRange: { start: 2, end: 4 },
			},
		});
		const vChart = wrapper.findComponent({ name: "VChart" });
		const option = vChart.props("option") as Record<string, unknown>;
		const tooltip = option.tooltip as Record<
			string,
			(
				params: Array<{ seriesName: string; value: number; dataIndex: number }>,
			) => string
		>;
		const result = tooltip.formatter([
			{ seriesName: "输入波形", value: 300, dataIndex: 3 },
		]);
		expect(result).toContain("故障区间");
	});

	it("tooltip formatter without fault range does not show warning", () => {
		const wrapper = mount(WaveformChart, { props: defaultProps });
		const vChart = wrapper.findComponent({ name: "VChart" });
		const option = vChart.props("option") as Record<string, unknown>;
		const tooltip = option.tooltip as Record<
			string,
			(
				params: Array<{ seriesName: string; value: number; dataIndex: number }>,
			) => string
		>;
		const result = tooltip.formatter([
			{ seriesName: "输入波形", value: 300, dataIndex: 3 },
		]);
		expect(result).not.toContain("故障区间");
	});

	it("option includes legend configuration", () => {
		const wrapper = mount(WaveformChart, { props: defaultProps });
		const vChart = wrapper.findComponent({ name: "VChart" });
		const option = vChart.props("option") as Record<string, unknown>;
		const legend = option.legend as Record<string, string[]>;
		expect(legend.data).toEqual(["输入波形", "输出波形"]);
	});

	it("handles empty input/output arrays", () => {
		const wrapper = mount(WaveformChart, {
			props: { inputData: [], outputData: [] },
		});
		expect(wrapper.find(".chart-toolbar").exists()).toBe(true);
	});

	it("handles different length input and output", () => {
		const wrapper = mount(WaveformChart, {
			props: { inputData: [1, 2, 3], outputData: [10, 20, 30, 40, 50] },
		});
		const vChart = wrapper.findComponent({ name: "VChart" });
		const option = vChart.props("option") as Record<string, unknown>;
		const series = option.series as Array<Record<string, number[]>>;
		expect(series[0].data).toHaveLength(3);
		expect(series[1].data).toHaveLength(5);
	});
});
