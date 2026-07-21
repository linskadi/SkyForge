<script setup lang="ts">
import { Check } from "@lucide/vue";
import type { StageInfo } from "@/composables/usePipeline";
import type { TaskDetail } from "@/types/execution";

interface Props {
	stages: readonly StageInfo[];
	currentStageIndex: number;
	task: TaskDetail | null;
}

defineProps<Props>();
</script>

<template>
	<section class="pipeline-panel panel">
		<div class="panel-title"><span>02</span> 可信流水线</div>
		<div class="pipeline-flow">
			<div
				v-for="(stage, index) in stages"
				:key="stage.key"
				class="stage-row"
				:class="{
					active: task && index === currentStageIndex,
					done: task && index < currentStageIndex,
				}"
			>
				<div class="stage-icon">
					<Check v-if="task && index < currentStageIndex" :size="16" />
					<span v-else>{{ index + 1 }}</span>
				</div>
				<div>
					<strong>{{ stage.name }}</strong>
					<small>{{
						index < 4
							? "AI Agent 生成与关联"
							: "确定性工具执行与记录"
					}}</small>
				</div>
				<span class="stage-state">
					{{
						!task
							? "等待"
							: index < currentStageIndex
								? "完成"
								: index === currentStageIndex
									? "执行中"
									: "等待"
					}}
				</span>
			</div>
		</div>
	</section>
</template>

<style scoped>
.pipeline-panel {
	padding: 18px 22px;
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
.pipeline-panel .pipeline-flow {
	flex: 1;
	align-content: start;
	gap: 10px;
}
.pipeline-flow {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 10px;
}
.stage-row {
	display: grid;
	grid-template-columns: 44px 1fr auto;
	align-items: center;
	gap: 10px;
	min-height: 96px;
	padding: 12px 14px;
	border: 1px solid #dae4eb;
	border-radius: 10px;
	background: #f8fafc;
}
.stage-row:last-child {
	grid-column: 1 / -1;
}
.stage-row.active {
	border-color: #2288da;
	background: #edf7ff;
	box-shadow: inset 4px 0 #1687e8;
}
.stage-row.done {
	border-color: #9bd3b5;
	background: #effaf4;
}
.stage-icon {
	display: grid;
	place-items: center;
	width: 38px;
	height: 38px;
	border-radius: 10px;
	color: #5c7183;
	background: #e6edf2;
	font-size: 14px;
	font-weight: 900;
}
.done .stage-icon {
	color: #fff;
	background: #20a167;
}
.active .stage-icon {
	color: #fff;
	background: #1687e8;
}
.stage-row strong {
	display: block;
	font-size: 14px;
}
.stage-row small {
	display: block;
	margin-top: 4px;
	color: #6c8295;
	font-size: 12px;
}
.stage-state {
	color: #718496;
	font-size: 12px;
	font-weight: 800;
}
.active .stage-state {
	color: #0875c9;
}
.done .stage-state {
	color: #168355;
}
@media (max-width: 1200px) and (min-width: 901px) {
	.pipeline-panel {
		padding-inline: 12px;
	}
	.stage-row {
		grid-template-columns: 34px 1fr auto;
	}
	.stage-row small {
		font-size: 10px;
	}
}
@media (max-height: 850px) and (min-width: 901px) {
	.stage-row {
		min-height: 64px;
	}
}
@media (max-width: 900px) {
	.pipeline-flow {
		grid-template-columns: 1fr 1fr;
	}
}
@media (max-width: 580px) {
	.pipeline-flow {
		grid-template-columns: 1fr;
	}
	.stage-row:last-child {
		grid-column: auto;
	}
}
</style>
