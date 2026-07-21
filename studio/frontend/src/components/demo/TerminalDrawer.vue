<script setup lang="ts">
import { ChevronDown, ChevronUp } from "@lucide/vue";
import type { EvidenceStatus, TaskDetail, TaskEvent } from "@/types/execution";

interface Props {
	events: TaskEvent[];
	terminalOpen: boolean;
	task: TaskDetail | null;
}

defineProps<Props>();

const emit = defineEmits<{
	"update:terminalOpen": [value: boolean];
}>();

function evidenceStatusText(status: EvidenceStatus): string {
	const map: Record<EvidenceStatus, string> = {
		observed: "观测",
		simulated: "模拟",
		unavailable: "不可用",
		failed: "失败",
	};
	return map[status];
}
</script>

<template>
	<section
		class="terminal-drawer"
		:class="{ collapsed: !terminalOpen, idle: !task }"
	>
		<button @click="task && emit('update:terminalOpen', !terminalOpen)">
			<span>
				<i />
				Agent 关键事件 <b>{{ events.length }}</b>
			</span>
			<ChevronUp v-if="terminalOpen" :size="17" />
			<ChevronDown v-else :size="17" />
		</button>
		<div v-show="terminalOpen" class="terminal-lines">
			<p v-for="event in events" :key="event.seq">
				<time>#{{ event.seq.toString().padStart(2, "0") }}</time>
				<b>[{{ event.agent }}]</b>
				{{ event.message }}
				<em>{{ evidenceStatusText(event.evidence_status) }}</em>
			</p>
			<p v-if="!events.length" class="terminal-empty">
				{{ task ? "等待 Agent 事件…" : "点击「开始可信生成」后，Agent 思考流将在此实时呈现。" }}
			</p>
		</div>
	</section>
</template>

<style scoped>
.terminal-drawer {
	width: 100%;
	max-width: 1800px;
	height: 280px;
	margin: 8px auto;
	border-radius: 12px;
	overflow: hidden;
	background: #071827;
	color: #c6d6e2;
	display: flex;
	flex-direction: column;
	transition: height 0.18s ease;
}
.terminal-drawer.collapsed {
	height: 44px;
}
.terminal-drawer.idle {
	opacity: 0.78;
}
.terminal-drawer.idle > button {
	cursor: default;
}
.terminal-drawer.idle i {
	background: #5b6b7a;
}
.terminal-drawer > button {
	width: 100%;
	height: 44px;
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0 16px;
	border: 0;
	color: #d4e4ef;
	background: #10273a;
	cursor: pointer;
	flex-shrink: 0;
}
.terminal-drawer button span {
	display: flex;
	align-items: center;
	gap: 10px;
	font-size: 13px;
	font-weight: 800;
}
.terminal-drawer i {
	width: 10px;
	height: 10px;
	border-radius: 50%;
	background: #32c979;
}
.terminal-drawer b {
	color: #54b7ff;
}
.terminal-lines {
	flex: 1;
	min-height: 0;
	padding: 8px 16px;
	overflow-y: auto;
	font-family: ui-monospace, monospace;
	scrollbar-width: thin;
	scrollbar-color: #2a4a66 #0d2030;
}
.terminal-lines::-webkit-scrollbar {
	width: 8px;
}
.terminal-lines::-webkit-scrollbar-track {
	background: #0d2030;
}
.terminal-lines::-webkit-scrollbar-thumb {
	background: #2a4a66;
	border-radius: 4px;
}
.terminal-lines p {
	display: grid;
	grid-template-columns: 40px 130px 1fr 50px;
	gap: 8px;
	margin: 4px 0;
	font-size: 12px;
	line-height: 1.5;
	white-space: nowrap;
	overflow: hidden;
}
.terminal-lines time {
	color: #557184;
}
.terminal-lines em {
	color: #f0bf58;
	font-style: normal;
}
.terminal-empty {
	color: #557184;
	font-size: 12px;
	text-align: center;
	padding: 20px 0;
}
@media (max-width: 900px) {
	.terminal-lines p {
		grid-template-columns: 30px 90px 1fr;
	}
	.terminal-lines em {
		display: none;
	}
}
</style>
