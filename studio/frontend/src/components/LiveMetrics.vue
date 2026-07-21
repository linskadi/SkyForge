<script setup lang="ts">
/**
 * LiveMetrics · 实时指标仪表盘（比赛展示增强）
 * ====================================================================
 * 紧凑的卡片组件，每 5 秒轮询 GET /api/dashboard/system-status：
 * - 当前任务数（运行中 / 完成 / 失败）三色指示
 * - 平均响应时间（大字号）
 * - 工具可用性灯（Z3 / CBMC / Cppcheck / GCC）绿/红/灰
 * - LLM 模式徽章 + 模型名
 * - 数据库行数
 * - 模式切换次数统计
 *
 * 数字变化时使用 CSS transition 平滑动画；组件卸载时清理 setInterval。
 */
import { Activity, Cpu, Database, Gauge, Wrench } from "@lucide/vue";
import {
	computed,
	onActivated,
	onBeforeUnmount,
	onMounted,
	ref,
	watch,
} from "vue";
import { Card, CardContent } from "@/components/ui/card";
import { getJSON } from "@/services/client";
import { useExecutionStore } from "@/stores/executionStore";

/** 后端 /api/dashboard/system-status 返回结构（局部声明，避免新增类型文件） */
interface SystemStatusResponse {
	backend?: string;
	llm?: {
		mode?: string;
		provider?: string | null;
		model?: string | null;
		available?: boolean;
	};
	tools?: {
		gcc?: boolean;
		z3?: boolean;
		cbmc?: boolean;
		cppcheck?: boolean;
	};
	persistence?: {
		db_rows?: number;
		tables?: { tasks?: number; task_history?: number };
		last_write?: string | null;
	};
	cleanup?: {
		enabled?: boolean;
		work_dir_count?: number;
	};
}

interface TaskCount {
	running: number;
	completed: number;
	failed: number;
}

const execution = useExecutionStore();

/** 轮询周期（毫秒） */
const POLL_INTERVAL_MS = 5000;

const loading = ref(true);
const error = ref("");
const status = ref<SystemStatusResponse | null>(null);
/** 任务三色计数（前端从任务列表推导） */
const taskCount = ref<TaskCount>({ running: 0, completed: 0, failed: 0 });
/** 模式切换累计次数（响应 ModeSwitcher 行为：本组件只读） */
const switchCount = ref(0);
/** 平均响应时间（ms），从前端任务列表推导 */
const avgResponseMs = ref(0);

let pollTimer: ReturnType<typeof setInterval> | null = null;
let isMounted = true;

async function fetchSystemStatus() {
	try {
		const ts = Date.now();
		const data = await getJSON<SystemStatusResponse>(
			`/api/dashboard/system-status?_ts=${ts}`,
			6000,
		);
		if (!isMounted) return;
		status.value = data;
		error.value = "";
	} catch (cause) {
		if (!isMounted) return;
		error.value = cause instanceof Error ? cause.message : String(cause);
	}
}

async function fetchTaskMetrics() {
	try {
		const { getTaskGateway } = await import("@/services/taskGateway");
		const tasks = await getTaskGateway(execution.profileId).listTasks();
		if (!isMounted) return;
		const running = tasks.filter((t) => t.status === "running").length;
		const done = tasks.filter((t) => t.status === "done").length;
		const failed = tasks.filter(
			(t) => t.status === "failed" || t.status === "degraded",
		).length;
		taskCount.value = { running, completed: done, failed };
		const durations = tasks
			.map((t) => t.duration_ms)
			.filter((d): d is number => typeof d === "number" && d > 0);
		avgResponseMs.value =
			durations.length > 0
				? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length)
				: 0;
	} catch {
		// 静默忽略：任务列表失败不影响 system-status 渲染
	}
}

async function refresh() {
	if (!isMounted) return;
	loading.value = status.value === null;
	await Promise.all([fetchSystemStatus(), fetchTaskMetrics()]);
	loading.value = false;
}

onMounted(() => {
	refresh();
	pollTimer = setInterval(refresh, POLL_INTERVAL_MS);
});

/** keep-alive 重新激活时立即刷新（页面切换回来不会触发 onMounted） */
onActivated(() => {
	refresh();
});

onBeforeUnmount(() => {
	isMounted = false;
	if (pollTimer) {
		clearInterval(pollTimer);
		pollTimer = null;
	}
});

/** 模式切换时立刻刷新一次任务指标（不等待 5 秒轮询） */
watch(
	() => execution.profileId,
	() => {
		switchCount.value += 1;
		refresh();
	},
);

/** 工具状态：支持布尔、字符串、缺失三种情况 */
function toolState(
	name: "gcc" | "z3" | "cbmc" | "cppcheck",
): "ok" | "down" | "unknown" {
	const t = status.value?.tools ?? {};
	const v = t[name];
	if (typeof v === "boolean") return v ? "ok" : "down";
	return "unknown";
}

interface ToolChip {
	name: string;
	key: "gcc" | "z3" | "cbmc" | "cppcheck";
	state: "ok" | "down" | "unknown";
}

const toolChips = computed<ToolChip[]>(() => {
	return (["z3", "cbmc", "cppcheck", "gcc"] as const).map((k) => ({
		name: k.toUpperCase(),
		key: k,
		state: toolState(k),
	}));
});

const llmMode = computed(() => {
	const mode = status.value?.llm?.mode;
	if (!mode) return "未知";
	if (mode === "mock") return "Mock";
	if (mode === "local") return "Local";
	if (mode === "api" || mode === "cloud") return "API";
	return mode;
});

const llmModel = computed(() => status.value?.llm?.model ?? "—");
const llmProvider = computed(() => status.value?.llm?.provider ?? "");

const dbRows = computed(() => status.value?.persistence?.db_rows ?? 0);
const dbTables = computed(() => status.value?.persistence?.tables ?? null);
const backendOnline = computed(() => status.value?.backend === "online");

function formatMs(ms: number): string {
	if (!ms) return "—";
	if (ms < 1000) return `${ms}ms`;
	return `${(ms / 1000).toFixed(2)}s`;
}
</script>

<template>
  <Card class="live-metrics-card" aria-label="LiveMetrics 实时指标">
    <CardContent class="live-metrics-content">
      <header class="lm-header">
        <div class="lm-title">
          <Activity :size="14" />
          <strong>LiveMetrics</strong>
          <span class="lm-pulse" :class="{ active: !loading && !error }" aria-hidden="true" />
        </div>
        <span v-if="error" class="lm-error" :title="error">轮询异常</span>
        <span v-else-if="loading" class="lm-loading">加载中…</span>
        <span v-else class="lm-updated">5s 刷新</span>
      </header>

      <div class="lm-grid">
        <!-- 任务三色指示 -->
        <div class="lm-cell">
          <span class="lm-label">任务</span>
          <div class="task-dots" role="group" aria-label="任务分布">
            <span class="task-stat running" :title="`运行中 ${taskCount.running}`">
              <span class="dot" />{{ taskCount.running }} <small>运行</small>
            </span>
            <span class="task-stat done" :title="`完成 ${taskCount.completed}`">
              <span class="dot" />{{ taskCount.completed }} <small>完成</small>
            </span>
            <span class="task-stat failed" :title="`失败 ${taskCount.failed}`">
              <span class="dot" />{{ taskCount.failed }} <small>失败</small>
            </span>
          </div>
        </div>

        <!-- 平均响应时间（大字号） -->
        <div class="lm-cell metric-cell">
          <span class="lm-label"><Gauge :size="11"/> 平均响应</span>
          <span class="metric-value">{{ formatMs(avgResponseMs) }}</span>
        </div>

        <!-- 工具可用性灯 -->
        <div class="lm-cell tool-cell">
          <span class="lm-label"><Wrench :size="11"/> 工具链</span>
          <div class="tool-chips">
            <span
              v-for="t in toolChips"
              :key="t.key"
              class="tool-chip"
              :class="t.state"
              :title="`${t.name}: ${t.state === 'ok' ? '可用' : t.state === 'down' ? '不可用' : '未上报'}`"
            >
              <span class="tool-led" aria-hidden="true" />{{ t.name }}
            </span>
          </div>
        </div>

        <!-- LLM 模式徽章 + 模型名 -->
        <div class="lm-cell llm-cell">
          <span class="lm-label"><Cpu :size="11"/> LLM</span>
          <div class="llm-row">
            <span class="llm-badge" :class="llmMode.toLowerCase()">{{ llmMode }}</span>
            <span class="llm-model" :title="llmProvider ? `${llmProvider} / ${llmModel}` : llmModel">
              {{ llmModel }}
            </span>
          </div>
        </div>

        <!-- 数据库行数 -->
        <div class="lm-cell db-cell">
          <span class="lm-label"><Database :size="11"/> 数据库</span>
          <template v-if="dbTables">
            <span class="db-value">
              Tasks: {{ (dbTables.tasks ?? 0).toLocaleString() }}
              <small>|</small>
              History: {{ (dbTables.task_history ?? 0).toLocaleString() }}
            </span>
          </template>
          <template v-else>
            <span class="db-value">{{ dbRows.toLocaleString() }} <small>行</small></span>
          </template>
        </div>

        <!-- 模式切换次数 -->
        <div class="lm-cell switch-cell">
          <span class="lm-label">模式切换</span>
          <span class="switch-value">{{ switchCount }} <small>次</small></span>
        </div>

        <!-- 后端状态 -->
        <div class="lm-cell backend-cell">
          <span class="lm-label">后端</span>
          <span class="backend-state" :class="{ online: backendOnline, offline: !backendOnline && !!status }">
            <span class="state-dot" aria-hidden="true" />
            {{ backendOnline ? "在线" : (status ? "离线" : "未连接") }}
          </span>
        </div>
      </div>
    </CardContent>
  </Card>
</template>

<style scoped>
.live-metrics-card {
  border: 1px solid rgba(11, 53, 85, 0.12);
  background: linear-gradient(135deg, #ffffff 0%, #f4faff 100%);
  box-shadow: 0 6px 18px rgba(5, 24, 49, 0.08);
}
.live-metrics-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
}
.lm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.lm-title {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #0b3555;
  font-size: 13px;
  font-weight: 800;
}
.lm-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #b9cedd;
  box-shadow: 0 0 0 0 rgba(103, 194, 58, 0.4);
  transition: background-color 0.3s;
}
.lm-pulse.active {
  background: #67c23a;
  animation: pulse 1.8s ease-out infinite;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(103, 194, 58, 0.4); }
  70% { box-shadow: 0 0 0 8px rgba(103, 194, 58, 0); }
  100% { box-shadow: 0 0 0 0 rgba(103, 194, 58, 0); }
}
.lm-loading,
.lm-updated,
.lm-error {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.lm-loading { color: #0879cf; }
.lm-updated { color: #16764e; }
.lm-error { color: #a33d3d; }

.lm-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px 14px;
}
.lm-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 9px 11px;
  border: 1px solid #e0ebf3;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
  min-width: 0;
}
.lm-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #4d6377;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
.metric-value {
  font-size: 22px;
  font-weight: 900;
  color: #0b3555;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.01em;
  transition: color 0.3s ease, transform 0.3s ease;
}
.task-dots {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 1px;
}
.task-stat {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 700;
  color: #153149;
  font-variant-numeric: tabular-nums;
  transition: color 0.3s ease;
}
.task-stat small {
  color: #657d90;
  font-size: 10px;
  font-weight: 600;
}
.task-stat .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.task-stat.running .dot { background: #1687e8; box-shadow: 0 0 0 3px rgba(22,135,232,.18); }
.task-stat.done .dot { background: #52c41a; box-shadow: 0 0 0 3px rgba(82,196,26,.18); }
.task-stat.failed .dot { background: #f5222d; box-shadow: 0 0 0 3px rgba(245,34,45,.18); }

.tool-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 7px;
  border-radius: 99px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.04em;
  transition: background-color 0.3s, color 0.3s, border-color 0.3s;
}
.tool-led {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  transition: background-color 0.3s, box-shadow 0.3s;
}
.tool-chip.ok {
  background: rgba(82, 196, 26, 0.12);
  color: #16764e;
  border: 1px solid rgba(82, 196, 26, 0.3);
}
.tool-chip.ok .tool-led {
  background: #52c41a;
  box-shadow: 0 0 0 3px rgba(82, 196, 26, 0.18);
}
.tool-chip.down {
  background: rgba(245, 34, 45, 0.1);
  color: #a33d3d;
  border: 1px solid rgba(245, 34, 45, 0.28);
}
.tool-chip.down .tool-led {
  background: #f5222d;
  box-shadow: 0 0 0 3px rgba(245, 34, 45, 0.18);
}
.tool-chip.unknown {
  background: rgba(151, 151, 151, 0.1);
  color: #6b7280;
  border: 1px solid rgba(151, 151, 151, 0.25);
}
.tool-chip.unknown .tool-led {
  background: #b9cedd;
}

.llm-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.llm-badge {
  padding: 2px 7px;
  border-radius: 99px;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.04em;
  border: 1px solid;
  transition: background-color 0.3s, color 0.3s, border-color 0.3s;
}
.llm-badge.mock {
  background: rgba(24, 144, 255, 0.12);
  color: #0964bd;
  border-color: rgba(24, 144, 255, 0.3);
}
.llm-badge.api {
  background: rgba(82, 196, 26, 0.12);
  color: #16764e;
  border-color: rgba(82, 196, 26, 0.3);
}
.llm-badge.local {
  background: rgba(250, 140, 22, 0.14);
  color: #ad5310;
  border-color: rgba(250, 140, 22, 0.32);
}
.llm-model {
  font-size: 12px;
  font-weight: 700;
  color: #153149;
  font-variant-numeric: tabular-nums;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.db-value,
.switch-value {
  font-size: 16px;
  font-weight: 800;
  color: #0b3555;
  font-variant-numeric: tabular-nums;
  transition: color 0.3s ease;
}
.db-value small,
.switch-value small {
  margin-left: 2px;
  color: #657d90;
  font-size: 10px;
  font-weight: 600;
}

.backend-state {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 700;
  color: #4d6377;
  transition: color 0.3s;
}
.state-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #b9cedd;
  transition: background-color 0.3s, box-shadow 0.3s;
}
.backend-state.online {
  color: #16764e;
}
.backend-state.online .state-dot {
  background: #52c41a;
  box-shadow: 0 0 0 3px rgba(82, 196, 26, 0.2);
}
.backend-state.offline {
  color: #a33d3d;
}
.backend-state.offline .state-dot {
  background: #f5222d;
  box-shadow: 0 0 0 3px rgba(245, 34, 45, 0.2);
}
@media (max-width: 720px) {
  .lm-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
