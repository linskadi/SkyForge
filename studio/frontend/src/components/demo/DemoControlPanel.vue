<script setup lang="ts">
import { Play, Square } from "@lucide/vue";
import type { RunSource, TaskDetail } from "@/types/execution";

interface Props {
	requirement: string;
	language: "c" | "cpp" | "python";
	running: boolean;
	isReplayMode: boolean;
	profileLabel: string;
	profileSource: RunSource;
	task: TaskDetail | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{
	"update:requirement": [value: string];
	"update:language": [value: "c" | "cpp" | "python"];
	start: [];
	cancel: [];
}>();

function profileCardTitle(): string {
	return props.task?.source === "replay" ? "已验证回放" : props.profileLabel;
}

function profileCardDesc(): string {
	if (props.task?.source === "replay") {
		return "manifest/SHA-256 核验；降级阶段不伪装 observed";
	}
	return props.profileSource === "simulated"
		? "确定性时间线 · 无任何网络请求"
		: "唯一任务通道 · 失败不伪装成功";
}
</script>

<template>
	<aside class="control-panel panel">
		<div class="panel-title"><span>01</span> 任务输入</div>
		<label for="demo-requirement">航空软件需求</label>
		<textarea
			id="demo-requirement"
			:value="requirement"
			@input="emit('update:requirement', ($event.target as HTMLTextAreaElement).value)"
			:disabled="running || isReplayMode"
			rows="9"
		/>
		<label for="demo-language">目标语言</label>
		<select
			id="demo-language"
			:value="language"
			@change="emit('update:language', ($event.target as HTMLSelectElement).value as 'c' | 'cpp' | 'python')"
			:disabled="running || isReplayMode"
		>
			<option value="c">C / MISRA C:2012</option>
			<option value="cpp">C++</option>
			<option value="python">Python</option>
		</select>
		<div class="profile-card">
			<strong>{{ profileCardTitle() }}</strong>
			<small>{{ profileCardDesc() }}</small>
		</div>
		<button
			v-if="!running"
			class="run-button"
			:disabled="isReplayMode"
			:title="isReplayMode ? '回放模式下不可启动新任务' : ''"
			@click="emit('start')"
		>
			<Play :size="18" />{{ task ? "重新运行" : "开始可信生成" }}
		</button>
		<button v-else class="stop-button" @click="emit('cancel')">
			<Square :size="16" />取消任务
		</button>
		<p class="input-hint">
			{{
				isReplayMode
					? "回放模式：只读查看历史任务，不可编辑或重启。"
					: "编辑需求只更新本地表单；只有点击按钮才创建一次任务。"
			}}
		</p>
	</aside>
</template>

<style scoped>
.control-panel {
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
.control-panel label {
	display: block;
	margin: 10px 0 6px;
	font-size: 13px;
	font-weight: 800;
	color: #486176;
	flex: none;
}
.control-panel textarea,
.control-panel select {
	width: 100%;
	padding: 10px;
	border: 1px solid #b7cbd9;
	border-radius: 9px;
	color: #17344c;
	background: #fbfdff;
	font-size: 14px;
	line-height: 1.6;
	resize: none;
}
.control-panel textarea:focus,
.control-panel select:focus {
	border-color: #1687d2;
	box-shadow: 0 0 0 4px rgba(22, 135, 210, 0.1);
	outline: none;
}
.control-panel textarea {
	flex: 1;
	min-height: 240px;
}
.control-panel select {
	flex: none;
}
.profile-card {
	display: flex;
	flex-direction: column;
	gap: 4px;
	margin: 10px 0;
	padding: 10px;
	border-left: 4px solid #e7a422;
	background: #fff8e7;
	flex: none;
}
.profile-card strong {
	font-size: 14px;
}
.profile-card small,
.input-hint {
	color: #667f93;
	font-size: 12px;
	line-height: 1.5;
}
.input-hint {
	flex: none;
}
.run-button,
.stop-button {
	width: 100%;
	display: flex;
	justify-content: center;
	align-items: center;
	gap: 10px;
	padding: 12px;
	border: 0;
	border-radius: 10px;
	color: #fff;
	background: linear-gradient(135deg, #0b87d6, #075bb4);
	box-shadow: 0 8px 18px rgba(8, 107, 190, 0.22);
	font-size: 15px;
	font-weight: 850;
	cursor: pointer;
	flex: none;
}
.stop-button {
	background: #a64040;
}
.run-button:disabled {
	opacity: 0.55;
	cursor: not-allowed;
	box-shadow: none;
}
@media (max-height: 850px) and (min-width: 901px) {
	.control-panel {
		padding: 11px 14px;
	}
	.control-panel .panel-title {
		margin-bottom: 7px;
	}
	.control-panel label {
		margin: 5px 0 3px;
	}
	.profile-card {
		margin: 6px 0;
		padding: 6px 8px;
	}
	.run-button,
	.stop-button {
		padding: 8px;
	}
}
</style>
