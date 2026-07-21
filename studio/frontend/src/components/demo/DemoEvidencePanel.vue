<script setup lang="ts">
import { AlertTriangle, ShieldCheck } from "@lucide/vue";
import type { GenerateResult } from "@/types/domain";
import type { TaskDetail } from "@/types/execution";

const STAGE_NAMES = [
	"需求解析",
	"LLR",
	"契约",
	"代码",
	"扫描修复",
	"数字孪生",
	"证据包",
];

interface Props {
	task: TaskDetail | null;
	complete: boolean;
	currentStageIndex: number;
	stagesLength: number;
	result: GenerateResult | null;
	error: string;
	initialViolations: number;
	contractPassed: number;
	contractTotal: number;
}

const props = defineProps<Props>();

function progressPercent(): number {
	if (props.complete) return 100;
	return Math.round((props.currentStageIndex / props.stagesLength) * 100);
}

function currentStageName(): string {
	if (props.complete) return "证据包已汇总";
	const index = Math.min(props.currentStageIndex, props.stagesLength - 1);
	return STAGE_NAMES[index] || "";
}
</script>

<template>
	<aside class="evidence-panel panel">
		<div class="panel-title"><span>03</span> 实时结论</div>
		<div v-if="!task" class="empty-evidence">
			<ShieldCheck :size="42" />
			<strong>等待开始演示</strong>
			<p>运行时，这里只呈现当前阶段最关键的证据。</p>
		</div>
		<template v-else>
			<div
				class="progress-ring"
				:style="{
					'--progress': `${task.progress ?? progressPercent()}%`,
				}"
			>
				<strong>{{ complete ? 100 : progressPercent() }}%</strong>
				<small>交付闭环</small>
			</div>
			<div class="live-conclusion">
				<span>当前阶段</span>
				<strong>{{ currentStageName() }}</strong>
			</div>
			<div class="evidence-list">
				<div>
					<span>MISRA 修复</span>
					<strong>{{ complete ? `${initialViolations} → 0` : "—" }}</strong>
				</div>
				<div>
					<span>契约检查</span>
					<strong>{{ complete ? `${contractPassed}/${contractTotal}` : "—" }}</strong>
				</div>
				<div>
					<span>仿真步数</span>
					<strong>{{ complete ? result?.simulation_result.total_steps : "—" }}</strong>
				</div>
				<div>
					<span>追溯覆盖</span>
					<strong>{{ complete ? "100%" : "—" }}</strong>
				</div>
			</div>
		</template>
		<div v-if="error" class="error-box">
			<AlertTriangle :size="17" />
			{{ error }}
			<small>可切回演示模式继续离线演示。</small>
		</div>
	</aside>
</template>

<style scoped>
.evidence-panel {
	padding: 18px;
	min-height: 0;
	overflow: auto;
	border: 1px solid #c5d8e4;
	border-radius: 14px;
	background: rgba(255, 255, 255, 0.96);
	box-shadow: 0 6px 22px rgba(19, 55, 83, 0.08);
	display: flex;
	flex-direction: column;
}
.panel-title {
	display: flex;
	align-items: center;
	gap: 10px;
	margin-bottom: 14px;
	font-size: 15px;
	font-weight: 900;
	color: #0b345b;
	flex: none;
}
.panel-title span {
	display: grid;
	place-items: center;
	width: 28px;
	height: 28px;
	border-radius: 8px;
	color: #fff;
	background: linear-gradient(145deg, #1593dd, #075ba9);
	font-size: 12px;
}
.empty-evidence {
	flex: 1;
	min-height: 340px;
	display: grid;
	place-items: center;
	align-content: center;
	gap: 9px;
	text-align: center;
	color: #8aa0b2;
}
.empty-evidence p {
	max-width: 240px;
	margin: 0;
	font-size: 13px;
}
.progress-ring {
	--progress: 0%;
	width: 140px;
	height: 140px;
	margin: 18px auto;
	display: grid;
	place-items: center;
	align-content: center;
	border-radius: 50%;
	background:
		radial-gradient(circle, #fff 58%, transparent 60%),
		conic-gradient(#1184dc var(--progress), #dfe8ee 0);
}
.progress-ring strong {
	font-size: 28px;
	color: #075da5;
}
.progress-ring small {
	font-size: 11px;
	color: #718496;
}
.live-conclusion {
	padding: 12px;
	border-radius: 10px;
	background: #edf7ff;
}
.live-conclusion span {
	display: block;
	color: #698095;
	font-size: 11px;
}
.live-conclusion strong {
	font-size: 16px;
}
.evidence-list {
	margin-top: 12px;
}
.evidence-list div {
	display: flex;
	justify-content: space-between;
	padding: 10px 2px;
	border-bottom: 1px solid #edf1f4;
	font-size: 13px;
}
.evidence-list strong {
	color: #087352;
}
.error-box {
	display: flex;
	flex-wrap: wrap;
	gap: 8px;
	margin-top: 12px;
	padding: 10px;
	color: #8d3737;
	background: #fff0f0;
	font-size: 13px;
}
.error-box small {
	width: 100%;
}
@media (max-height: 850px) and (min-width: 901px) {
	.progress-ring {
		width: 92px;
		height: 92px;
		margin: 7px auto;
	}
}
</style>
