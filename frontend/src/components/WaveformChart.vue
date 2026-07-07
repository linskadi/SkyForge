<script setup lang="ts">
/**
 * WaveformChart 波形图组件（Day 3 数字孪生）
 *
 * 纯 Canvas 实现的波形图，不引入 echarts 等重型库：
 * - 输入波形（蓝色）和输出波形（绿色）叠加对比
 * - 支持鼠标滚轮缩放（X 轴方向）和拖拽平移
 * - 故障注入区间红色高亮
 * - 顶部工具栏：放大 / 缩小 / 重置 / 导出 PNG
 *
 * 参考文档第 6 章数字孪生沙盒。
 */
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ZoomIn, ZoomOut, RotateCcw, Download } from "lucide-vue-next";
import { Button } from "@/components/ui/button";

interface Props {
  /** 输入波形数据 */
  inputData: number[];
  /** 输出波形数据 */
  outputData: number[];
  /** 故障注入区间（红色高亮） */
  faultRange?: { start: number; end: number } | null;
  /** 画布高度（px） */
  height?: number;
}

const props = withDefaults(defineProps<Props>(), {
  faultRange: null,
  height: 320,
});

/** Canvas 元素引用 */
const canvasRef = ref<HTMLCanvasElement | null>(null);
/** 容器引用（用于 ResizeObserver） */
const containerRef = ref<HTMLDivElement | null>(null);

/** 视图状态：offsetX = 起始时间步，scale = X 轴放大倍数 */
const view = ref({ offsetX: 0, scale: 1 });
/** 是否正在拖拽 */
let isDragging = false;
let dragStartX = 0;
let dragStartOffset = 0;
/** ResizeObserver 实例 */
let resizeObserver: ResizeObserver | null = null;

/** 计算所有数据的 Y 轴范围（统一量程，便于对比） */
const computeYRange = (): { min: number; max: number } => {
  const all = [...props.inputData, ...props.outputData];
  if (all.length === 0) return { min: 0, max: 1 };
  let min = Math.min(...all);
  let max = Math.max(...all);
  // 上下各留 10% 余量
  const pad = (max - min) * 0.1 || 1;
  return { min: min - pad, max: max + pad };
};

/** 绘制波形图 */
const draw = () => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.clientWidth;
  const cssH = canvas.clientHeight;
  // 设置物理像素尺寸（高分屏清晰）
  if (canvas.width !== Math.floor(cssW * dpr) || canvas.height !== Math.floor(cssH * dpr)) {
    canvas.width = Math.floor(cssW * dpr);
    canvas.height = Math.floor(cssH * dpr);
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  // 布局：左边距 50（Y 轴标签），下边距 28（X 轴标签），上边距 8，右边距 8
  const padL = 50;
  const padR = 8;
  const padT = 8;
  const padB = 28;
  const plotW = cssW - padL - padR;
  const plotH = cssH - padT - padB;

  const total = props.inputData.length;
  if (total === 0) return;

  // 可见区间 [viewStart, viewEnd)
  const visibleCount = Math.max(2, Math.floor(total / view.value.scale));
  const viewStart = Math.max(0, Math.min(total - visibleCount, view.value.offsetX));
  const viewEnd = Math.min(total, viewStart + visibleCount);

  const yRange = computeYRange();

  // ===== 1. 绘制故障区间红色背景 =====
  if (props.faultRange) {
    const fxStart = Math.max(viewStart, props.faultRange.start);
    const fxEnd = Math.min(viewEnd, props.faultRange.end + 1);
    if (fxEnd > fxStart) {
      const x1 = padL + ((fxStart - viewStart) / visibleCount) * plotW;
      const x2 = padL + ((fxEnd - viewStart) / visibleCount) * plotW;
      ctx.fillStyle = "rgba(239, 68, 68, 0.12)";
      ctx.fillRect(x1, padT, Math.max(1, x2 - x1), plotH);
      // 故障区间边界虚线
      ctx.strokeStyle = "rgba(239, 68, 68, 0.5)";
      ctx.setLineDash([4, 3]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x1, padT);
      ctx.lineTo(x1, padT + plotH);
      ctx.moveTo(x2, padT);
      ctx.lineTo(x2, padT + plotH);
      ctx.stroke();
      ctx.setLineDash([]);
      // 故障区间标签
      ctx.fillStyle = "#dc2626";
      ctx.font = "11px Consolas, monospace";
      ctx.fillText("⚠ 故障区间", x1 + 4, padT + 14);
    }
  }

  // ===== 2. 绘制网格线 =====
  ctx.strokeStyle = "#e5e7eb";
  ctx.lineWidth = 1;
  ctx.font = "10px Consolas, monospace";
  ctx.fillStyle = "#9ca3af";
  // 水平网格（5 条）
  const ySteps = 5;
  for (let i = 0; i <= ySteps; i++) {
    const y = padT + (plotH / ySteps) * i;
    const val = yRange.max - ((yRange.max - yRange.min) / ySteps) * i;
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(padL + plotW, y);
    ctx.stroke();
    ctx.textAlign = "right";
    ctx.fillText(Math.round(val).toString(), padL - 4, y + 3);
  }
  // 垂直网格（X 轴刻度）
  const xTicks = 8;
  ctx.textAlign = "center";
  for (let i = 0; i <= xTicks; i++) {
    const x = padL + (plotW / xTicks) * i;
    const stepIdx = Math.round(viewStart + (visibleCount / xTicks) * i);
    ctx.beginPath();
    ctx.moveTo(x, padT);
    ctx.lineTo(x, padT + plotH);
    ctx.stroke();
    ctx.fillText(stepIdx.toString(), x, padT + plotH + 16);
  }

  // ===== 3. 绘制输入波形（蓝色） =====
  const drawWaveform = (data: number[], color: string, fillAlpha: number) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = viewStart; i < viewEnd; i++) {
      const x = padL + ((i - viewStart) / visibleCount) * plotW;
      const y = padT + ((yRange.max - data[i]) / (yRange.max - yRange.min)) * plotH;
      if (i === viewStart) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    // 填充半透明区域
    ctx.lineTo(padL + plotW, padT + plotH);
    ctx.lineTo(padL, padT + plotH);
    ctx.closePath();
    ctx.fillStyle = color.replace("rgb", "rgba").replace(")", `, ${fillAlpha})`);
    ctx.fill();
  };

  drawWaveform(props.inputData.slice(0, total), "rgb(59, 130, 246)", 0.06);
  drawWaveform(props.outputData.slice(0, total), "rgb(34, 197, 94)", 0.08);

  // ===== 4. 绘制图例 =====
  ctx.font = "11px Inter, sans-serif";
  ctx.textAlign = "left";
  const legendY = padT + 4;
  // 输入波形图例
  ctx.fillStyle = "rgb(59, 130, 246)";
  ctx.fillRect(padL + plotW - 160, legendY, 12, 3);
  ctx.fillStyle = "#374151";
  ctx.fillText("输入波形", padL + plotW - 144, legendY + 7);
  // 输出波形图例
  ctx.fillStyle = "rgb(34, 197, 94)";
  ctx.fillRect(padL + plotW - 80, legendY, 12, 3);
  ctx.fillStyle = "#374151";
  ctx.fillText("输出波形", padL + plotW - 64, legendY + 7);

  // ===== 5. 绘制坐标轴 =====
  ctx.strokeStyle = "#9ca3af";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padL, padT);
  ctx.lineTo(padL, padT + plotH);
  ctx.lineTo(padL + plotW, padT + plotH);
  ctx.stroke();

  // X 轴标签
  ctx.fillStyle = "#6b7280";
  ctx.font = "10px Inter, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("时间步 (step)", padL + plotW / 2, cssH - 2);
};

// ===== 交互事件 =====

/** 鼠标滚轮缩放 */
const onWheel = (e: WheelEvent) => {
  e.preventDefault();
  const canvas = canvasRef.value;
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const padL = 50;
  const plotW = rect.width - padL - 8;
  const total = props.inputData.length;

  // 当前鼠标对应的 step
  const visibleCount = Math.max(2, Math.floor(total / view.value.scale));
  const viewStart = Math.max(0, Math.min(total - visibleCount, view.value.offsetX));
  const mouseStep = viewStart + ((mouseX - padL) / plotW) * visibleCount;

  // 缩放
  const factor = e.deltaY > 0 ? 0.8 : 1.25;
  const newScale = Math.max(0.5, Math.min(total / 2, view.value.scale * factor));
  const newVisibleCount = Math.max(2, Math.floor(total / newScale));
  // 保持鼠标位置不变
  const newOffset = Math.max(0, Math.min(total - newVisibleCount, Math.round(mouseStep - (mouseStep - viewStart) * (newVisibleCount / visibleCount))));

  view.value = { offsetX: newOffset, scale: newScale };
  draw();
};

/** 鼠标按下开始拖拽 */
const onMouseDown = (e: MouseEvent) => {
  isDragging = true;
  dragStartX = e.clientX;
  dragStartOffset = view.value.offsetX;
  if (canvasRef.value) canvasRef.value.style.cursor = "grabbing";
};

/** 鼠标移动拖拽 */
const onMouseMove = (e: MouseEvent) => {
  if (!isDragging) return;
  const canvas = canvasRef.value;
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const dx = e.clientX - dragStartX;
  const padL = 50;
  const plotW = rect.width - padL - 8;
  const total = props.inputData.length;
  const visibleCount = Math.max(2, Math.floor(total / view.value.scale));
  // 像素位移 -> step 位移
  const stepShift = Math.round((dx / plotW) * visibleCount);
  const newOffset = Math.max(0, Math.min(total - visibleCount, dragStartOffset - stepShift));
  view.value = { ...view.value, offsetX: newOffset };
  draw();
};

/** 鼠标松开结束拖拽 */
const onMouseUp = () => {
  isDragging = false;
  if (canvasRef.value) canvasRef.value.style.cursor = "crosshair";
};

/** 工具栏：放大 */
const zoomIn = () => {
  const total = props.inputData.length;
  view.value.scale = Math.min(total / 2, view.value.scale * 1.5);
  draw();
};

/** 工具栏：缩小 */
const zoomOut = () => {
  view.value.scale = Math.max(0.5, view.value.scale / 1.5);
  const total = props.inputData.length;
  const visibleCount = Math.max(2, Math.floor(total / view.value.scale));
  view.value.offsetX = Math.max(0, Math.min(total - visibleCount, view.value.offsetX));
  draw();
};

/** 工具栏：重置视图 */
const resetView = () => {
  view.value = { offsetX: 0, scale: 1 };
  draw();
};

/** 工具栏：导出 PNG */
const exportPNG = () => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const link = document.createElement("a");
  link.download = `waveform_${Date.now()}.png`;
  link.href = canvas.toDataURL("image/png");
  link.click();
};

// ===== 生命周期 =====

onMounted(() => {
  draw();
  // 监听容器尺寸变化
  if (containerRef.value) {
    resizeObserver = new ResizeObserver(() => draw());
    resizeObserver.observe(containerRef.value);
  }
  // 全局 mouseup（防止鼠标移出 canvas 后仍处于拖拽状态）
  window.addEventListener("mouseup", onMouseUp);
});

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  window.removeEventListener("mouseup", onMouseUp);
});

// 数据变化时重绘
watch(
  () => [props.inputData, props.outputData, props.faultRange],
  () => {
    view.value = { offsetX: 0, scale: 1 };
    draw();
  },
  { deep: true },
);
</script>

<template>
  <div ref="containerRef" class="waveform-chart">
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
    <!-- Canvas 画布 -->
    <canvas
      ref="canvasRef"
      class="chart-canvas"
      :style="{ height: height + 'px' }"
      @wheel.prevent="onWheel"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
    />
    <!-- 操作提示 -->
    <div class="chart-hint">
      💡 鼠标滚轮缩放 · 拖拽平移 · 工具栏可导出 PNG
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
  background: rgb(59, 130, 246);
}

.legend-line.output {
  background: rgb(34, 197, 94);
}

.legend-line.fault {
  background: rgba(239, 68, 68, 0.5);
  border: 1px dashed #dc2626;
}

.toolbar-actions {
  display: flex;
  gap: 4px;
}

.chart-canvas {
  width: 100%;
  cursor: crosshair;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fafafa;
  display: block;
}

.chart-hint {
  font-size: 11px;
  color: #9ca3af;
  text-align: right;
}
</style>
