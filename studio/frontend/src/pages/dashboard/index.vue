<script setup lang="ts">
import {
	Activity,
	ArrowRight,
	Clock,
	Code2,
	FileCode2,
	FileText,
	Server,
	ShieldCheck,
	Wrench,
} from "@lucide/vue";
import { BarChart, LineChart } from "echarts/charts";
import {
	GridComponent,
	LegendComponent,
	TooltipComponent,
} from "echarts/components";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import VChart from "vue-echarts";
import { useRouter } from "vue-router";
import SourceBadge from "@/components/SourceBadge.vue";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getApi } from "@/services/apiSwitcher";
import type {
	ComplianceTrendPoint,
	DashboardStats,
	RecentTask,
	SystemStatus,
} from "@/types/domain";

use([
	CanvasRenderer,
	LineChart,
	BarChart,
	GridComponent,
	TooltipComponent,
	LegendComponent,
]);

const router = useRouter();

const isMounted = ref(false);
const systemStatus = ref<SystemStatus | null>(null);
const recentTasks = ref<RecentTask[]>([]);
const dashboardStats = ref<DashboardStats | null>(null);
const complianceTrend = ref<ComplianceTrendPoint[]>([]);

let statusPollTimer: ReturnType<typeof setInterval> | null = null;

async function fetchSystemStatus() {
	try {
		systemStatus.value = await getApi().getSystemStatus();
	} catch {
		systemStatus.value = {
			backend: "offline",
			llm: { mode: "mock", provider: null, model: null, available: true },
			tools: { gcc: null, z3: null, cbmc: null },
			persistence: { db_rows: 0, last_write: null },
		};
	}
}

async function fetchRecentTasks() {
	try {
		recentTasks.value = await getApi().getRecentTasks(8);
	} catch {
		recentTasks.value = [];
	}
}

async function fetchDashboardStats() {
	try {
		dashboardStats.value = await getApi().getDashboardStats();
	} catch {
		dashboardStats.value = {
			today_count: 0,
			today_done: 0,
			total_count: 0,
			avg_compliance_rate: 0,
		};
	}
}

async function fetchComplianceTrend() {
	try {
		complianceTrend.value = await getApi().getComplianceTrend(10);
	} catch {
		complianceTrend.value = [];
	}
}

async function fetchAllData() {
	await Promise.all([
		fetchSystemStatus(),
		fetchRecentTasks(),
		fetchDashboardStats(),
		fetchComplianceTrend(),
	]);
}

function formatDuration(ms: number): string {
	if (ms < 1000) return "0s";
	const seconds = Math.floor(ms / 1000);
	if (seconds < 60) return `${seconds}s`;
	const minutes = Math.floor(seconds / 60);
	const secs = seconds % 60;
	return `${minutes}m ${secs}s`;
}

function formatTimeAgo(iso: string | null): string {
	if (!iso) return "-";
	const diff = Date.now() - new Date(iso).getTime();
	const mins = Math.floor(diff / 60000);
	if (mins < 1) return "刚刚";
	if (mins < 60) return `${mins} 分钟前`;
	const hours = Math.floor(mins / 60);
	if (hours < 24) return `${hours} 小时前`;
	const days = Math.floor(hours / 24);
	return `${days} 天前`;
}

const statusBadgeVariant = (status: RecentTask["status"]) => {
	switch (status) {
		case "done":
			return "default" as const;
		case "running":
			return "secondary" as const;
		case "error":
			return "destructive" as const;
		default:
			return "outline" as const;
	}
};

const statusLabel = (status: RecentTask["status"]) => {
	switch (status) {
		case "done":
			return "已完成";
		case "running":
			return "运行中";
		case "error":
			return "失败";
		default:
			return status;
	}
};

const languageBadge = (lang: string) => {
	switch (lang) {
		case "c":
			return "C";
		case "cpp":
			return "C++";
		case "python":
			return "Python";
		default:
			return lang.toUpperCase();
	}
};

const lastTask = computed(() => recentTasks.value[0] ?? null);

function handleNewTask() {
	router.push("/generate");
}

function handleContinueTask() {
	if (lastTask.value) {
		router.push(`/records/${lastTask.value.id}`);
	} else {
		router.push("/records");
	}
}

function handleImportScade() {
	router.push({ path: "/generate", query: { scade: "1" } });
}

function handleTaskClick(taskId: string) {
	router.push(`/records/${taskId}`);
}

const complianceChartOption = computed(() => {
	const data = complianceTrend.value;
	if (data.length === 0) {
		return {
			tooltip: { trigger: "axis" },
			grid: { left: 48, right: 16, top: 32, bottom: 32 },
			xAxis: { type: "category", data: [] },
			yAxis: { type: "value" },
			series: [],
		};
	}
	const labels = data.map((_, i) => `#${i + 1}`);
	return {
		tooltip: {
			trigger: "axis",
			backgroundColor: "rgba(30, 30, 30, 0.95)",
			borderColor: "#3c3c3c",
			textStyle: { color: "#d4d4d4", fontSize: 12 },
		},
		legend: {
			data: ["Mandatory", "Required", "Advisory"],
			right: 16,
			top: 0,
			textStyle: { color: "hsl(var(--muted-foreground))", fontSize: 12 },
		},
		grid: { left: 48, right: 16, top: 40, bottom: 32 },
		xAxis: {
			type: "category",
			data: labels,
			axisLine: { lineStyle: { color: "hsl(var(--border))" } },
			axisTick: { lineStyle: { color: "hsl(var(--border))" } },
			axisLabel: { color: "hsl(var(--muted-foreground))", fontSize: 11 },
		},
		yAxis: {
			type: "value",
			name: "违规数",
			nameTextStyle: { color: "hsl(var(--muted-foreground))", fontSize: 11 },
			axisLine: { lineStyle: { color: "hsl(var(--border))" } },
			axisTick: { lineStyle: { color: "hsl(var(--border))" } },
			axisLabel: { color: "hsl(var(--muted-foreground))", fontSize: 11 },
			splitLine: { lineStyle: { color: "hsl(var(--border))" } },
		},
		series: [
			{
				name: "Mandatory",
				type: "bar",
				stack: "total",
				data: data.map((d) => d.mandatory),
				itemStyle: {
					color: "hsl(var(--destructive))",
					borderRadius: [0, 0, 0, 0],
				},
			},
			{
				name: "Required",
				type: "bar",
				stack: "total",
				data: data.map((d) => d.required),
				itemStyle: { color: "hsl(var(--warning))" },
			},
			{
				name: "Advisory",
				type: "bar",
				stack: "total",
				data: data.map((d) => d.advisory),
				itemStyle: { color: "hsl(var(--chart-4))", borderRadius: [4, 4, 0, 0] },
			},
		],
	};
});

onMounted(async () => {
	isMounted.value = true;
	await fetchAllData();

	statusPollTimer = setInterval(() => {
		if (!document.hidden) {
			fetchSystemStatus();
		}
	}, 10000);
});

onBeforeUnmount(() => {
	if (statusPollTimer) {
		clearInterval(statusPollTimer);
		statusPollTimer = null;
	}
});
</script>

<template>
	<main class="dashboard-home">
		<section
			class="dashboard-section animate-slide-up stagger-delay-1"
			:class="{ 'animate-in-active': isMounted }"
		>
			<div class="section-header">
				<h2 class="section-title">系统状态</h2>
			</div>
			<div class="status-grid">
				<Card class="status-card">
					<CardContent class="status-card-content">
						<div class="status-card-icon">
							<Server :size="20" />
						</div>
						<div class="status-card-info">
							<div class="status-card-label">后端服务</div>
							<div class="status-card-value">
								<span
									class="status-dot"
									:class="systemStatus?.backend === 'online' ? 'online' : 'error'"
								/>
								{{ systemStatus?.backend === 'online' ? '在线' : '离线' }}
							</div>
						</div>
					</CardContent>
				</Card>

				<Card class="status-card">
					<CardContent class="status-card-content">
						<div class="status-card-icon">
							<Activity :size="20" />
						</div>
						<div class="status-card-info">
							<div class="status-card-label">LLM 引擎</div>
							<div class="status-card-value">
								<span
									class="status-dot"
									:class="systemStatus?.llm.available ? 'online' : 'error'"
								/>
								{{ systemStatus?.llm.available ? '在线' : '离线' }}
							</div>
							<div class="status-card-detail">
								模式: {{ systemStatus?.llm.mode === 'mock' ? '模拟' : systemStatus?.llm.mode }}
								<span v-if="systemStatus?.llm.model">
									· {{ systemStatus.llm.model }}
								</span>
							</div>
						</div>
					</CardContent>
				</Card>

				<Card class="status-card">
					<CardContent class="status-card-content">
						<div class="status-card-icon">
							<Wrench :size="20" />
						</div>
						<div class="status-card-info">
							<div class="status-card-label">工具链</div>
							<div class="status-card-value">
								<span
									class="status-dot"
									:class="
										systemStatus?.tools.gcc || systemStatus?.tools.z3
											? 'online'
											: 'error'
									"
								/>
								{{
									systemStatus?.tools.gcc || systemStatus?.tools.z3
										? '可用'
										: '离线'
								}}
							</div>
							<div class="status-card-detail">
								<span
									v-for="(available, tool) in systemStatus?.tools"
									:key="tool"
									class="tool-tag"
									:class="available ? 'available' : 'unavailable'"
								>
									{{ tool.toUpperCase() }}
								</span>
							</div>
						</div>
					</CardContent>
				</Card>
			</div>
		</section>

		<section
			class="dashboard-section animate-slide-up stagger-delay-2"
			:class="{ 'animate-in-active': isMounted }"
		>
			<div class="actions-grid">
				<Card class="action-card hover-lift active-press" @click="handleNewTask">
					<CardContent class="action-card-content">
						<div class="action-icon">
							<Code2 :size="28" />
						</div>
						<div class="action-text">
							<h3 class="action-title">新建代码生成任务</h3>
							<p class="action-desc">从自然语言需求开始，生成符合 DO-178C 的可信代码</p>
						</div>
						<ArrowRight :size="20" class="action-arrow" />
					</CardContent>
				</Card>

				<Card class="action-card hover-lift active-press" @click="handleContinueTask">
					<CardContent class="action-card-content">
						<div class="action-icon secondary">
							<Clock :size="28" />
						</div>
						<div class="action-text">
							<h3 class="action-title">继续上次任务</h3>
							<p class="action-desc">
								{{ lastTask ? '回到最近一次运行的任务上下文' : '查看历史运行记录' }}
							</p>
						</div>
						<ArrowRight :size="20" class="action-arrow" />
					</CardContent>
				</Card>

				<Card class="action-card hover-lift active-press" @click="handleImportScade">
					<CardContent class="action-card-content">
						<div class="action-icon accent">
							<FileCode2 :size="28" />
						</div>
						<div class="action-text">
							<h3 class="action-title">从 SCADE 导入</h3>
							<p class="action-desc">导入 SCADE G-Lustre 模型，转换为需求与契约</p>
						</div>
						<ArrowRight :size="20" class="action-arrow" />
					</CardContent>
				</Card>
			</div>
		</section>

		<section
			class="dashboard-section animate-slide-up stagger-delay-3"
			:class="{ 'animate-in-active': isMounted }"
		>
			<Card class="section-card">
				<CardHeader class="section-card-header">
					<CardTitle class="section-card-title flex items-center gap-2">
						<span>最近任务</span>
						<SourceBadge source="observed" label="实时数据" />
					</CardTitle>
					<router-link to="/records" class="view-all-link">
						查看全部 <ArrowRight :size="14" />
					</router-link>
				</CardHeader>
				<CardContent class="section-card-content">
					<div v-if="recentTasks.length === 0" class="empty-state">
						<FileText :size="40" class="empty-icon" />
						<p class="empty-title">暂无任务记录</p>
						<p class="empty-desc">点击上方按钮创建您的第一个代码生成任务</p>
					</div>
					<div v-else class="task-list">
						<div
							v-for="task in recentTasks"
							:key="task.id"
							class="task-item hover-lift active-press"
							@click="handleTaskClick(task.id)"
						>
							<div class="task-main">
								<p class="task-requirement">{{ task.requirement }}</p>
							</div>
							<div class="task-meta">
								<div class="task-badges">
									<Badge variant="outline" class="lang-badge">
										{{ languageBadge(task.language) }}
									</Badge>
									<Badge :variant="statusBadgeVariant(task.status)">
										{{ statusLabel(task.status) }}
									</Badge>
								</div>
								<div class="task-details">
									<span class="task-detail-item">
										<ShieldCheck :size="12" />
										{{ task.violation_count }} 违规
									</span>
									<span v-if="task.duration_ms > 0" class="task-detail-item">
										<Clock :size="12" />
										{{ formatDuration(task.duration_ms) }}
									</span>
									<span class="task-detail-item">
										{{ formatTimeAgo(task.created_at) }}
									</span>
								</div>
							</div>
						</div>
					</div>
				</CardContent>
			</Card>
		</section>

		<section
			class="dashboard-section animate-slide-up stagger-delay-4"
			:class="{ 'animate-in-active': isMounted }"
		>
			<div class="compliance-grid">
				<Card class="compliance-stats-card">
					<CardHeader class="compliance-card-header">
						<CardTitle class="compliance-card-title flex items-center gap-2">
							<span>DO-178C 合规率</span>
							<SourceBadge source="observed" label="统计数据" />
						</CardTitle>
					</CardHeader>
					<CardContent class="compliance-stats-content">
						<div class="compliance-rate">
							<span class="compliance-rate-value">
								{{
									dashboardStats
										? Math.round(dashboardStats.avg_compliance_rate * 100)
										: 0
								}}%
							</span>
							<span class="compliance-rate-label">平均合规率</span>
						</div>
						<div class="compliance-metrics">
							<div class="metric-item">
								<span class="metric-value">{{ dashboardStats?.today_count ?? 0 }}</span>
								<span class="metric-label">今日任务</span>
							</div>
							<div class="metric-item">
								<span class="metric-value">{{ dashboardStats?.today_done ?? 0 }}</span>
								<span class="metric-label">已完成</span>
							</div>
							<div class="metric-item">
								<span class="metric-value">{{ dashboardStats?.total_count ?? 0 }}</span>
								<span class="metric-label">总任务数</span>
							</div>
						</div>
					</CardContent>
				</Card>

				<Card class="compliance-chart-card">
					<CardHeader class="compliance-card-header">
						<CardTitle class="compliance-card-title">违规数趋势</CardTitle>
					</CardHeader>
					<CardContent class="compliance-chart-content">
						<v-chart
							v-if="complianceTrend.length > 0"
							:option="complianceChartOption"
							class="compliance-chart"
							autoresize
						/>
						<div v-else class="chart-empty">
							<Activity :size="32" class="empty-icon" />
							<p>暂无趋势数据</p>
						</div>
					</CardContent>
				</Card>
			</div>
		</section>
	</main>
</template>

<style scoped>
.dashboard-home {
	min-height: calc(100dvh - var(--topbar-h, 60px));
	padding: clamp(16px, 2vh, 24px) clamp(16px, 4vw, 48px) 24px;
	background: hsl(var(--background));
	display: flex;
	flex-direction: column;
	gap: 20px;
}

.dashboard-section {
	opacity: 0;
	transform: translateY(12px);
	transition:
		opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1),
		transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.dashboard-section.animate-in-active {
	opacity: 1;
	transform: translateY(0);
}

.section-header {
	margin-bottom: 12px;
}

.section-title {
	font-size: 15px;
	font-weight: 600;
	color: hsl(var(--foreground));
	margin: 0;
}

.status-grid {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	gap: 12px;
}

.status-card {
	border: 1px solid hsl(var(--border));
	border-radius: 16px;
	background: hsl(var(--card));
	box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.06);
	transition:
		border-color 0.2s ease,
		box-shadow 0.2s ease;
}

.status-card:hover {
	border-color: hsl(240 5% 88%);
}

.status-card-content {
	display: flex;
	align-items: center;
	gap: 14px;
	padding: 16px;
}

.status-card-icon {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 40px;
	height: 40px;
	border-radius: 10px;
	background: hsl(var(--muted));
	color: hsl(var(--foreground));
	flex-shrink: 0;
}

.status-card-info {
	display: flex;
	flex-direction: column;
	gap: 2px;
	min-width: 0;
}

.status-card-label {
	font-size: 12px;
	color: hsl(var(--muted-foreground));
	font-weight: 500;
}

.status-card-value {
	font-size: 15px;
	font-weight: 600;
	color: hsl(var(--foreground));
	display: flex;
	align-items: center;
	gap: 6px;
}

.status-card-detail {
	font-size: 11px;
	color: hsl(var(--muted-foreground));
	margin-top: 2px;
}

.tool-tag {
	display: inline-flex;
	align-items: center;
	padding: 1px 6px;
	border-radius: 4px;
	font-size: 10px;
	font-weight: 600;
	margin-right: 4px;
}

.tool-tag.available {
	background: hsl(var(--success) / 0.1);
	color: hsl(var(--success));
}

.tool-tag.unavailable {
	background: hsl(var(--muted));
	color: hsl(var(--muted-foreground));
}

.actions-grid {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	gap: 12px;
}

.action-card {
	border: 1px solid hsl(var(--border));
	border-radius: 16px;
	background: hsl(var(--card));
	box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.06);
	cursor: pointer;
}

.action-card-content {
	display: flex;
	align-items: center;
	gap: 14px;
	padding: 18px 16px;
}

.action-icon {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 48px;
	height: 48px;
	border-radius: 12px;
	background: hsl(var(--primary) / 0.1);
	color: hsl(var(--primary));
	flex-shrink: 0;
}

.action-icon.secondary {
	background: hsl(240 5% 96%);
	color: hsl(var(--foreground));
}

.action-icon.accent {
	background: hsl(var(--chart-4) / 0.1);
	color: hsl(var(--chart-4));
}

.action-text {
	flex: 1;
	min-width: 0;
}

.action-title {
	font-size: 15px;
	font-weight: 600;
	color: hsl(var(--foreground));
	margin: 0 0 2px 0;
}

.action-desc {
	font-size: 12px;
	color: hsl(var(--muted-foreground));
	margin: 0;
	line-height: 1.5;
}

.action-arrow {
	color: hsl(var(--muted-foreground));
	flex-shrink: 0;
	transition: transform 0.2s ease;
}

.action-card:hover .action-arrow {
	transform: translateX(2px);
	color: hsl(var(--foreground));
}

.section-card {
	border: 1px solid hsl(var(--border));
	border-radius: 16px;
	background: hsl(var(--card));
	box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.06);
}

.section-card-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 16px 20px;
	border-bottom: 1px solid hsl(var(--border));
}

.section-card-title {
	font-size: 15px;
	font-weight: 600;
	color: hsl(var(--foreground));
	margin: 0;
}

.view-all-link {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	font-size: 12px;
	font-weight: 500;
	color: hsl(var(--primary));
	text-decoration: none;
	transition: color 0.2s ease;
}

.view-all-link:hover {
	color: hsl(210 100% 42%);
}

.section-card-content {
	padding: 8px;
}

.empty-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 48px 24px;
	text-align: center;
}

.empty-icon {
	color: hsl(var(--muted-foreground));
	opacity: 0.5;
	margin-bottom: 12px;
}

.empty-title {
	font-size: 14px;
	font-weight: 600;
	color: hsl(var(--foreground));
	margin: 0 0 4px 0;
}

.empty-desc {
	font-size: 12px;
	color: hsl(var(--muted-foreground));
	margin: 0;
}

.task-list {
	display: flex;
	flex-direction: column;
}

.task-item {
	display: flex;
	align-items: stretch;
	gap: 16px;
	padding: 14px 16px;
	border-radius: 12px;
	cursor: pointer;
	transition:
		background-color 0.15s ease,
		transform 0.15s ease;
}

.task-item:hover {
	background: hsl(var(--muted));
}

.task-item + .task-item {
	border-top: 1px solid hsl(var(--border));
}

.task-main {
	flex: 1;
	min-width: 0;
	display: flex;
	align-items: center;
}

.task-requirement {
	font-size: 13px;
	font-weight: 500;
	color: hsl(var(--foreground));
	line-height: 1.5;
	margin: 0;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	overflow: hidden;
}

.task-meta {
	display: flex;
	flex-direction: column;
	align-items: flex-end;
	gap: 8px;
	flex-shrink: 0;
}

.task-badges {
	display: flex;
	gap: 6px;
}

.lang-badge {
	background: hsl(var(--muted));
	color: hsl(var(--foreground));
}

.task-details {
	display: flex;
	align-items: center;
	gap: 10px;
}

.task-detail-item {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	font-size: 11px;
	color: hsl(var(--muted-foreground));
	white-space: nowrap;
}

.compliance-grid {
	display: grid;
	grid-template-columns: 320px 1fr;
	gap: 12px;
}

.compliance-stats-card,
.compliance-chart-card {
	border: 1px solid hsl(var(--border));
	border-radius: 16px;
	background: hsl(var(--card));
	box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.06);
}

.compliance-card-header {
	padding: 14px 20px;
	border-bottom: 1px solid hsl(var(--border));
}

.compliance-card-title {
	font-size: 14px;
	font-weight: 600;
	color: hsl(var(--foreground));
	margin: 0;
}

.compliance-stats-content {
	padding: 20px;
}

.compliance-rate {
	display: flex;
	align-items: baseline;
	gap: 8px;
	margin-bottom: 20px;
}

.compliance-rate-value {
	font-size: 40px;
	font-weight: 700;
	color: hsl(var(--success));
	line-height: 1;
	letter-spacing: -0.02em;
}

.compliance-rate-label {
	font-size: 12px;
	color: hsl(var(--muted-foreground));
	font-weight: 500;
}

.compliance-metrics {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	gap: 12px;
	padding-top: 16px;
	border-top: 1px solid hsl(var(--border));
}

.metric-item {
	display: flex;
	flex-direction: column;
	gap: 2px;
}

.metric-value {
	font-size: 20px;
	font-weight: 700;
	color: hsl(var(--foreground));
	line-height: 1.2;
}

.metric-label {
	font-size: 11px;
	color: hsl(var(--muted-foreground));
	font-weight: 500;
}

.compliance-chart-content {
	padding: 12px;
}

.compliance-chart {
	height: 240px;
	width: 100%;
}

.chart-empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	height: 240px;
	color: hsl(var(--muted-foreground));
	font-size: 12px;
	gap: 8px;
}

.chart-empty .empty-icon {
	opacity: 0.4;
	margin-bottom: 0;
}

@media (max-width: 1024px) {
	.status-grid,
	.actions-grid {
		grid-template-columns: repeat(2, 1fr);
	}

	.compliance-grid {
		grid-template-columns: 1fr;
	}
}

@media (max-width: 640px) {
	.dashboard-home {
		padding-inline: 12px;
		gap: 16px;
	}

	.status-grid,
	.actions-grid {
		grid-template-columns: 1fr;
	}

	.task-item {
		flex-direction: column;
		gap: 10px;
	}

	.task-meta {
		align-items: flex-start;
	}

	.task-details {
		flex-wrap: wrap;
	}

	.compliance-metrics {
		grid-template-columns: repeat(3, 1fr);
	}
}

@media (prefers-reduced-motion: reduce) {
	.dashboard-section,
	.dashboard-section.animate-in-active,
	.action-card,
	.task-item,
	.action-arrow {
		transition: none !important;
		animation: none !important;
		transform: none !important;
	}

	.dashboard-section {
		opacity: 1 !important;
	}
}
</style>
