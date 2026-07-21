<script setup lang="ts">
import { Download, RotateCcw, ZoomIn, ZoomOut } from "@lucide/vue";
import { LineChart } from "echarts/charts";
import {
	DataZoomComponent,
	GridComponent,
	LegendComponent,
	MarkAreaComponent,
	TooltipComponent,
} from "echarts/components";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
/**
 * WaveformChart ECharts 波形图组件
 * 替换原有纯 Canvas 实现，提供更丰富的交互
 */
import { computed, ref } from "vue";
import VChart from "vue-echarts";
import { Button } from "@/components/ui/button";

use([
	CanvasRenderer,
	LineChart,
	GridComponent,
	TooltipComponent,
	LegendComponent,
	DataZoomComponent,
	MarkAreaComponent,
]);

interface Props {
	/** 输入波形数据 */
	inputData: number[];
	/** 输出波形数据 */
	outputData: number[];
	/** 正常基线数据（可选，用于故障注入对比） */
	baselineData?: number[];
	/** 故障注入区间（红色高亮） */
	faultRange?: { start: number; end: number } | null;
	/** 画布高度（px） */
	height?: number;
}

const props = withDefaults(defineProps<Props>(), {
	baselineData: undefined,
	faultRange: null,
	height: 320,
});

const chartRef = ref<InstanceType<typeof VChart> | null>(null);

type LinearGradientColor = {
	type: "linear";
	x: number;
	y: number;
	x2: number;
	y2: number;
	colorStops: Array<{ offset: number; color: string }>;
};

type MarkAreaOption = {
	silent: boolean;
	data: Array<
		[
			{
				xAxis: number;
				itemStyle: {
					color: string;
					borderColor: string;
					borderWidth: number;
					borderType: "dashed";
				};
			},
			{ xAxis: number },
		]
	>;
};

type WaveformSeries = {
	name: string;
	type: "line";
	data: number[];
	lineStyle: { color: string; width: number; type?: "dashed" };
	itemStyle: { color: string };
	showSymbol: boolean;
	areaStyle?: { color: LinearGradientColor };
	markArea?: MarkAreaOption;
	animation: boolean;
};

/** ECharts 配置 */
const option = computed(() => {
	const total = props.inputData.length;
	const xData = Array.from({ length: total }, (_, i) => i);

	// 故障区间标记
	const markArea: MarkAreaOption | undefined = props.faultRange
		? {
				silent: true,
				data: [
					[
						{
							xAxis: props.faultRange.start,
							itemStyle: {
								color: "rgba(239, 68, 68, 0.12)",
								borderColor: "rgba(239, 68, 68, 0.5)",
								borderWidth: 1,
								borderType: "dashed",
							},
						},
						{
							xAxis: props.faultRange.end,
						},
					],
				],
			}
		: undefined;

	const legendData = ["输入波形", "输出波形"];
	if (props.baselineData) {
		legendData.push("正常基线");
	}

	const seriesList: WaveformSeries[] = [
		{
			name: "输入波形",
			type: "line",
			data: props.inputData,
			lineStyle: { color: "#0EA5E9", width: 2 },
			itemStyle: { color: "#0EA5E9" },
			showSymbol: false,
			areaStyle: {
				color: {
					type: "linear",
					x: 0,
					y: 0,
					x2: 0,
					y2: 1,
					colorStops: [
						{ offset: 0, color: "rgba(59, 130, 246, 0.12)" },
						{ offset: 1, color: "rgba(59, 130, 246, 0.02)" },
					],
				},
			},
			markArea,
			animation: false,
		},
		{
			name: "输出波形",
			type: "line",
			data: props.outputData,
			lineStyle: { color: "#22c55e", width: 2 },
			itemStyle: { color: "#22c55e" },
			showSymbol: false,
			areaStyle: {
				color: {
					type: "linear",
					x: 0,
					y: 0,
					x2: 0,
					y2: 1,
					colorStops: [
						{ offset: 0, color: "rgba(34, 197, 94, 0.12)" },
						{ offset: 1, color: "rgba(34, 197, 94, 0.02)" },
					],
				},
			},
			animation: false,
		},
	];

	if (props.baselineData) {
		seriesList.push({
			name: "正常基线",
			type: "line",
			data: props.baselineData,
			lineStyle: { color: "#94a3b8", width: 2, type: "dashed" },
			itemStyle: { color: "#94a3b8" },
			showSymbol: false,
			animation: false,
		});
	}

	return {
		tooltip: {
			trigger: "axis",
			backgroundColor: "rgba(30, 30, 30, 0.95)",
			borderColor: "#3c3c3c",
			textStyle: {
				color: "#d4d4d4",
				fontSize: 12,
				fontFamily: "'Consolas', monospace",
			},
			formatter: (
				params: Array<{ seriesName: string; value: number; dataIndex: number }>,
			) => {
				if (!params.length) return "";
				let html = `<div style="font-weight:600;margin-bottom:4px">Step ${params[0].dataIndex}</div>`;
				for (const p of params) {
					html += `<div>${p.seriesName}: <span style="font-weight:700">${p.value}</span></div>`;
				}
				if (props.faultRange) {
					const idx = params[0].dataIndex;
					if (idx >= props.faultRange.start && idx <= props.faultRange.end) {
						html += `<div style="color:#f44747;margin-top:4px">⚠ 故障区间</div>`;
					}
				}
				return html;
			},
		},
		legend: {
			data: legendData,
			right: 16,
			top: 8,
			textStyle: {
				color: "#6b7280",
				fontSize: 12,
			},
		},
		grid: {
			left: 56,
			right: 16,
			top: 40,
			bottom: 48,
		},
		xAxis: {
			type: "category",
			data: xData,
			name: "时间步 (step)",
			nameLocation: "center",
			nameGap: 28,
			nameTextStyle: { color: "#6b7280", fontSize: 11 },
			axisLine: { lineStyle: { color: "#d1d5db" } },
			axisTick: { lineStyle: { color: "#d1d5db" } },
			axisLabel: { color: "#9ca3af", fontSize: 10 },
			splitLine: { show: true, lineStyle: { color: "#f3f4f6" } },
		},
		yAxis: {
			type: "value",
			axisLine: { lineStyle: { color: "#d1d5db" } },
			axisTick: { lineStyle: { color: "#d1d5db" } },
			axisLabel: { color: "#9ca3af", fontSize: 10 },
			splitLine: { lineStyle: { color: "#f3f4f6" } },
		},
		dataZoom: [
			{
				type: "inside",
				xAxisIndex: 0,
				filterMode: "filter",
			},
		],
		series: seriesList,
	};
});

/** 工具栏：放大 */
const zoomIn = () => {
	const chart = chartRef.value?.chart;
	if (!chart) return;
	const opt = chart.getOption() as {
		dataZoom?: Array<{ start?: number; end?: number }>;
	};
	const zoom = opt.dataZoom?.[0];
	if (!zoom) return;
	const range = (zoom.end ?? 100) - (zoom.start ?? 0);
	const newRange = range * 0.7;
	const center = ((zoom.start ?? 0) + (zoom.end ?? 100)) / 2;
	chart.dispatchAction({
		type: "dataZoom",
		start: Math.max(0, center - newRange / 2),
		end: Math.min(100, center + newRange / 2),
	});
};

/** 工具栏：缩小 */
const zoomOut = () => {
	const chart = chartRef.value?.chart;
	if (!chart) return;
	const opt = chart.getOption() as {
		dataZoom?: Array<{ start?: number; end?: number }>;
	};
	const zoom = opt.dataZoom?.[0];
	if (!zoom) return;
	const range = (zoom.end ?? 100) - (zoom.start ?? 0);
	const newRange = Math.min(100, range * 1.4);
	const center = ((zoom.start ?? 0) + (zoom.end ?? 100)) / 2;
	chart.dispatchAction({
		type: "dataZoom",
		start: Math.max(0, center - newRange / 2),
		end: Math.min(100, center + newRange / 2),
	});
};

/** 工具栏：重置视图 */
const resetView = () => {
	const chart = chartRef.value?.chart;
	chart?.dispatchAction({ type: "dataZoom", start: 0, end: 100 });
};

/** 工具栏：导出 PNG */
const exportPNG = () => {
	const chart = chartRef.value?.chart;
	if (!chart) return;
	const url = chart.getDataURL({
		type: "png",
		pixelRatio: 2,
		backgroundColor: "#fff",
	});
	const link = document.createElement("a");
	link.download = `waveform_${Date.now()}.png`;
	link.href = url;
	link.click();
};
</script>

<template>
  <div class="waveform-chart">
    <!-- 顶部工具栏 -->
    <div class="chart-toolbar">
      <div class="legend">
        <span class="legend-item">
          <span class="legend-line input" />
          输入波形
        </span>
        <span class="legend-item">
          <span class="legend-line output" />
          输出波形
        </span>
        <span v-if="baselineData" class="legend-item">
          <span class="legend-line baseline" />
          正常基线
        </span>
        <span v-if="faultRange" class="legend-item">
          <span class="legend-line fault" />
          故障区间
        </span>
      </div>
      <div class="toolbar-actions">
        <Button variant="outline" size="sm" @click="zoomIn" title="放大">
          <ZoomIn class="w-3.5 h-3.5" />
        </Button>
        <Button variant="outline" size="sm" @click="zoomOut" title="缩小">
          <ZoomOut class="w-3.5 h-3.5" />
        </Button>
        <Button variant="outline" size="sm" @click="resetView" title="重置视图">
          <RotateCcw class="w-3.5 h-3.5" />
        </Button>
        <Button variant="outline" size="sm" @click="exportPNG" title="导出 PNG">
          <Download class="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
    <!-- ECharts 图表 -->
    <v-chart
      ref="chartRef"
      :option="option"
      :style="{ height: height + 'px' }"
      autoresize
    />
    <!-- 操作提示 -->
    <div class="chart-hint">
      鼠标滚轮缩放 · 拖拽平移 · 悬浮查看数据 · 工具栏可导出 PNG
    </div>
  </div>
</template>

<style scoped>
.waveform-chart {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.legend {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: #4b5563;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.legend-line {
  display: inline-block;
  width: 20px;
  height: 3px;
  border-radius: 2px;
}

.legend-line.input {
  background: #0EA5E9;
}

.legend-line.output {
  background: #22c55e;
}

.legend-line.baseline {
  background: #94a3b8;
  background-image: repeating-linear-gradient(
    90deg,
    #94a3b8 0,
    #94a3b8 6px,
    transparent 6px,
    transparent 10px
  );
  background-color: transparent;
}

.legend-line.fault {
  background: rgba(239, 68, 68, 0.5);
  border: 1px dashed #dc2626;
}

.toolbar-actions {
  display: flex;
  gap: 4px;
}

.chart-hint {
  font-size: 11px;
  color: #9ca3af;
  text-align: right;
}
</style>
