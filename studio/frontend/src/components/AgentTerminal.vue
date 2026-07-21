<script setup lang="ts">
import { useVirtualizer } from "@tanstack/vue-virtual";
/**
 * AgentTerminal 组件（VSCode 终端样式 + 虚拟滚动）
 *
 * - 顶部：红黄绿三圆点 + 标题
 * - 主体：日志列表，虚拟滚动支持万级日志
 * - 打字机效果：逐字推入（20ms/字）
 * - 闪烁光标 ▊
 */
import {
	computed,
	nextTick,
	onBeforeUnmount,
	onMounted,
	ref,
	watch,
} from "vue";
import {
	type AgentLog,
	type AgentType,
	connectAgentStream,
	connectV1TaskEvents,
	createTaskAndSubscribeV1,
	DEFAULT_WS_URL,
	type LogLevel,
	mockAgentStream,
	type StreamCompletePayload,
} from "@/services/mockApi";
import { useExecutionStore } from "@/stores/executionStore";
import { agentColorMap, levelColorMap } from "@/utils/colors";

interface Props {
	useMock?: boolean;
	wsUrl?: string;
	typeInterval?: number;
	maxLogs?: number;
	requirement?: string;
	language?: string;
	/** 订阅模式：传入 task_id 时连接 WS 后发送 {task_id, action: "subscribe"}，
	 * 不启动新 pipeline，只接收已有运行中 task 的实时日志。
	 * 用于从 Dashboard 点击 running 任务恢复查看 agent 思考流。 */
	subscribeTaskId?: string;
	/**
	 * 通道模式：
	 * - "v1"（默认，Phase 5 推荐）：通过 POST /api/v1/tasks + WS
	 *   /api/v1/tasks/{task_id}/events 启动和订阅任务。
	 * - "legacy"：使用旧通道 /ws/agent-stream（一次性发送 requirement 触发）。
	 *
	 * 旧通道会在 V1 通道失败时作为 fallback 自动启用。
	 */
	channelMode?: "v1" | "legacy";
}

const props = withDefaults(defineProps<Props>(), {
	useMock: true,
	wsUrl: DEFAULT_WS_URL,
	typeInterval: 20,
	maxLogs: 5000,
	requirement: "",
	language: "c",
	subscribeTaskId: "",
	channelMode: "v1",
});
const executionStore = useExecutionStore();

/**
 * complete 事件：仅在非 mock 模式下，WebSocket 收到 `level: "complete"` 消息时触发，
 * 透传后端返回的 `{ result, degraded }` payload，供父组件（Generate.vue）实现
 * HTTP 与 WebSocket 双通道汇合门控（SkyForge Spec 修复 A Task 4）。
 */
const emit =
	defineEmits<(e: "complete", payload?: StreamCompletePayload) => void>();

interface RenderedLog {
	ts: number;
	agent: AgentType;
	level: LogLevel;
	visibleText: string;
	fullText: string;
	done: boolean;
}

const logs = ref<RenderedLog[]>([]);
const logContainerRef = ref<HTMLDivElement | null>(null);

/** 虚拟滚动 */
const virtualizer = useVirtualizer({
	count: logs.value.length,
	getScrollElement: () => logContainerRef.value,
	estimateSize: () => 24,
	overscan: 20,
});

// 监听 logs 变化更新虚拟滚动
watch(
	logs,
	() => {
		virtualizer.value.setOptions({
			...virtualizer.value.options,
			count: logs.value.length,
		});
	},
	{ deep: true },
);

let typingIndex = -1;
let typingTimer: ReturnType<typeof setTimeout> | null = null;
let stopStream: (() => void) | null = null;
let v1DoneHandled = false;
let fallbackScheduled = false;
let fallbackTimer: ReturnType<typeof setTimeout> | null = null;
let v1FirstMessageReceived = false;

const pushLog = (log: AgentLog) => {
	if (logs.value.length >= props.maxLogs) {
		logs.value.shift();
	}
	finishCurrent();

	const newLog: RenderedLog = {
		ts: log.ts ?? Date.now(),
		agent: log.agent,
		level: log.level,
		visibleText: "",
		fullText: log.thought,
		done: false,
	};
	logs.value.push(newLog);
	typingIndex = logs.value.length - 1;
	startTyping();
	scrollToBottom();
};

const startTyping = () => {
	if (typingIndex < 0 || typingIndex >= logs.value.length) return;
	const target = logs.value[typingIndex];

	const tick = () => {
		if (!target || target.done) return;
		if (target.visibleText.length >= target.fullText.length) {
			target.done = true;
			return;
		}
		target.visibleText = target.fullText.slice(
			0,
			target.visibleText.length + 1,
		);
		typingTimer = setTimeout(tick, props.typeInterval);
	};
	tick();
};

const finishCurrent = () => {
	if (typingTimer) {
		clearTimeout(typingTimer);
		typingTimer = null;
	}
	if (typingIndex >= 0 && typingIndex < logs.value.length) {
		const target = logs.value[typingIndex];
		if (target && !target.done) {
			target.visibleText = target.fullText;
			target.done = true;
		}
	}
};

const scrollToBottom = () => {
	nextTick(() => {
		if (logs.value.length > 0) {
			virtualizer.value.scrollToIndex(logs.value.length - 1, { align: "end" });
		}
	});
};

/**
 * V1 通道失败时回退到旧通道（Phase 5 兼容性策略）。
 *
 * 仅在父组件没有主动选择 legacy 模式时启用：若 V1 通道超过 5 秒仍未收到任何
 * 事件或第一条事件就是错误，自动断开 V1 并连接旧 /ws/agent-stream。
 * 父组件（Generate.vue）也可以通过显式 channelMode="legacy" 跳过回退。
 */
const scheduleLegacyFallback = (reason: string) => {
	if (fallbackScheduled) return;
	if (props.channelMode === "legacy") return;
	fallbackScheduled = true;
	fallbackTimer = setTimeout(() => {
		fallbackTimer = null;
		if (v1DoneHandled) return;
		console.warn(
			`[AgentTerminal] V1 通道未产生输出（${reason}），回退到 legacy /ws/agent-stream`,
		);
		stopAll();
		stopStream = connectAgentStream(
			pushLog,
			(data) => {
				finishCurrent();
				emit("complete", data);
			},
			props.wsUrl,
			props.requirement,
			props.language,
			props.subscribeTaskId || undefined,
		);
	}, 5_000);
};

/** 取消 legacy 回退定时器（V1 通道已收到消息时调用）。 */
const cancelFallback = () => {
	v1FirstMessageReceived = true;
	if (fallbackTimer) {
		clearTimeout(fallbackTimer);
		fallbackTimer = null;
	}
	fallbackScheduled = true; // 阻止后续再次调度
};

const startStream = () => {
	if (props.useMock) {
		stopStream = mockAgentStream(pushLog, () => {
			finishCurrent();
		});
		return;
	}
	v1DoneHandled = false;
	fallbackScheduled = false;
	v1FirstMessageReceived = false;

	// 订阅模式（已有 task_id，只订阅事件流）：直接走 V1 events 通道；不走创建流程
	if (props.subscribeTaskId) {
		stopStream = connectV1TaskEvents(
			props.subscribeTaskId,
			pushLog,
			(data) => {
				v1DoneHandled = true;
				finishCurrent();
				emit("complete", data);
			},
			0,
			undefined,
			cancelFallback,
		);
		scheduleLegacyFallback("subscribe mode");
		return;
	}

	// 显式 legacy 模式：直接走旧通道
	if (props.channelMode === "legacy") {
		stopStream = connectAgentStream(
			pushLog,
			(data) => {
				finishCurrent();
				emit("complete", data);
			},
			props.wsUrl,
			props.requirement,
			props.language,
			props.subscribeTaskId || undefined,
		);
		return;
	}

	// 默认 v1 模式：先创建 task，再订阅 events
	const lang = (
		props.language === "cpp" || props.language === "python"
			? props.language
			: "c"
	) as "c" | "cpp" | "python";
	const profileId = executionStore.profileId === "cloud" ? "cloud" : "local";
	createTaskAndSubscribeV1(
		props.requirement,
		lang,
		profileId,
		pushLog,
		(data) => {
			if (data) {
				v1DoneHandled = true;
				finishCurrent();
				emit("complete", data);
			}
		},
		cancelFallback,
	).then(({ taskId, stop }) => {
		if (!taskId) {
			// 创建失败：立即回退到 legacy 通道
			console.warn(
				"[AgentTerminal] V1 POST /api/v1/tasks 失败，回退到 legacy 通道",
			);
			stop();
			fallbackScheduled = true; // 跳过 5s 等待
			stopStream = connectAgentStream(
				pushLog,
				(d) => {
					finishCurrent();
					emit("complete", d);
				},
				props.wsUrl,
				props.requirement,
				props.language,
				props.subscribeTaskId || undefined,
			);
			return;
		}
		stopStream = stop;
		// 仅在 V1 通道尚未产生输出时才调度 fallback
		if (!v1FirstMessageReceived && !fallbackScheduled) {
			scheduleLegacyFallback("create + subscribe");
		}
	});
};

const stopAll = () => {
	if (typingTimer) {
		clearTimeout(typingTimer);
		typingTimer = null;
	}
	if (fallbackTimer) {
		clearTimeout(fallbackTimer);
		fallbackTimer = null;
	}
	if (stopStream) {
		stopStream();
		stopStream = null;
	}
	fallbackScheduled = true; // 阻止延迟回退
};

const clearLogs = () => {
	logs.value = [];
	typingIndex = -1;
};

defineExpose({
	start: startStream,
	stop: stopAll,
	clear: clearLogs,
	push: pushLog,
	finish: finishCurrent,
});

const formatTs = (ts: number) => {
	const d = new Date(ts);
	const pad = (n: number, len = 2) => n.toString().padStart(len, "0");
	return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(
		d.getSeconds(),
	)}.${pad(d.getMilliseconds(), 3)}`;
};

const badgeStyle = (agent: string) => {
	const c = agentColorMap[agent] ?? { bg: "#475569", fg: "#f1f5f9" };
	return {
		backgroundColor: c.bg,
		color: c.fg,
	};
};

const contentStyle = (level: LogLevel) => ({
	color: levelColorMap[level],
});

const showCursor = computed(() => {
	const last = logs.value[logs.value.length - 1];
	return last && !last.done;
});

watch(
	() => props.useMock,
	() => {
		stopAll();
		logs.value = [];
	},
	{ immediate: false },
);

watch(
	() => props.subscribeTaskId,
	(next, prev) => {
		// 订阅 task_id 变化时重连（仅在非 mock 模式下）
		if (next !== prev && !props.useMock && next) {
			stopAll();
			logs.value = [];
			startStream();
		}
	},
	{ immediate: false },
);

/**
 * onMounted 三分支判断：避免订阅模式下 onMounted 启动后又因 watch 重启。
 *
 * - 订阅模式（subscribeTaskId 已设置）：直接启动，startStream 内部发送
 *   {task_id, action: "subscribe"}，不会启动新 pipeline；watch 因值未变化
 *   不会再次触发，避免瞬态重复请求。
 * - 生成模式（非 mock 且有 requirement）：启动后通过 WebSocket 发送
 *   {requirement, language} 触发后端 pipeline。
 * - 其他情况（mock 模式或无需求）：不自动启动，由父组件显式调用 start()，
 *   避免 onMounted 启动 {requirement, language} 后被 subscribeTaskId watch 重启。
 */
onMounted(() => {
	if (props.subscribeTaskId) {
		startStream();
	}
	// 新任务永远由显式按钮启动；编辑 requirement 不产生网络副作用。
});

onBeforeUnmount(() => {
	stopAll();
});
</script>

<template>
  <div class="agent-terminal">
    <!-- 终端顶部栏 -->
    <div class="terminal-header">
      <div class="traffic-lights">
        <span class="light red" />
        <span class="light yellow" />
        <span class="light green" />
      </div>
      <div class="terminal-title">
        SkyForge Agent Console
      </div>
      <div class="header-actions">
        <span v-if="useMock" class="mock-badge">MOCK</span>
        <button class="clear-btn" type="button" title="清空日志" @click="clearLogs">清空</button>
      </div>
    </div>

    <!-- 终端日志主体（虚拟滚动） -->
    <div ref="logContainerRef" class="terminal-body">
      <div v-if="!logs.length" class="empty-hint">
        等待 Agent 思考日志流入...
      </div>
      <div
        :style="{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }"
      >
        <div
          v-for="virtualRow in virtualizer.getVirtualItems()"
          :key="String(virtualRow.key)"
          class="log-line"
          :style="{
            position: 'absolute',
            top: `${virtualRow.start}px`,
            left: 0,
            right: 0,
          }"
        >
          <span class="log-ts">{{ formatTs(logs[virtualRow.index].ts) }}</span>
          <span class="log-badge" :style="badgeStyle(logs[virtualRow.index].agent)">{{ logs[virtualRow.index].agent }}</span>
          <span class="log-content" :style="contentStyle(logs[virtualRow.index].level)">
            <span>{{ logs[virtualRow.index].visibleText }}</span><span v-if="showCursor && virtualRow.index === logs.length - 1"
              class="cursor">▊</span>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-terminal {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #060A12;
  border-radius: 8px;
  border: 1px solid rgba(14, 165, 233, 0.08);
  overflow: hidden;
  font-family: 'Consolas', 'Courier New', monospace;
  color: #d4d4d4;
}

.terminal-header {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: #0A1120;
  border-bottom: 1px solid rgba(14, 165, 233, 0.1);
  user-select: none;
}

.traffic-lights {
  display: flex;
  gap: 6px;
  margin-right: 12px;
}

.light {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}

.light.red { background: #ff5f56; box-shadow: 0 0 6px #ff5f5680; }
.light.yellow { background: #ffbd2e; box-shadow: 0 0 6px #ffbd2e80; }
.light.green { background: #27c93f; box-shadow: 0 0 6px #27c93f80; }

.light:hover { transform: scale(1.2); transition: transform 0.2s ease; }

.terminal-title {
  font-size: 13px;
  color: #38BDF8;
  font-weight: 500;
  flex: 1;
  text-shadow: 0 0 8px rgba(56, 189, 248, 0.3);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mock-badge {
  background: #cca700;
  color: #1e1e1e;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  letter-spacing: 0.5px;
}

.clear-btn {
  background: transparent;
  border: 1px solid rgba(14, 165, 233, 0.2);
  color: #38BDF8;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 3px;
  cursor: pointer;
  font-family: inherit;
}

.clear-btn:hover {
  background: rgba(14, 165, 233, 0.1);
  color: #7DD3FC;
}

.terminal-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
  scroll-behavior: smooth;
}

.terminal-body::-webkit-scrollbar { width: 8px; }
.terminal-body::-webkit-scrollbar-track { background: transparent; }
.terminal-body::-webkit-scrollbar-thumb { background: rgba(14, 165, 233, 0.15); border-radius: 4px; }
.terminal-body::-webkit-scrollbar-thumb:hover { background: rgba(14, 165, 233, 0.3); }

.empty-hint {
  color: #6a6a6a;
  font-style: italic;
}

.log-line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 2px 4px;
  word-break: break-word;
  border-radius: 3px;
  transition: background 0.15s ease;
}

.log-line:hover {
  background: rgba(14, 165, 233, 0.06);
}

.log-ts {
  color: #0EA5E9;
  flex-shrink: 0;
  font-size: 12px;
  padding-top: 1px;
  text-shadow: 0 0 6px rgba(14, 165, 233, 0.2);
}

.log-badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
  letter-spacing: 0.3px;
  margin-top: 1px;
}

.log-content {
  flex: 1;
  white-space: pre-wrap;
  min-width: 0;
}

.cursor {
  display: inline-block;
  margin-left: 1px;
  color: #38BDF8;
  text-shadow: 0 0 8px rgba(56, 189, 248, 0.6);
  animation: blink 1s steps(2, start) infinite;
}

@keyframes blink {
  to { visibility: hidden; }
}
</style>
