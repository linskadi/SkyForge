<script setup lang="ts">
/**
 * AgentTerminal 组件（VSCode 终端样式 + 虚拟滚动）
 *
 * - 顶部：红黄绿三圆点 + 标题
 * - 主体：日志列表，虚拟滚动支持万级日志
 * - 打字机效果：逐字推入（20ms/字）
 * - 闪烁光标 ▊
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useVirtualizer } from "@tanstack/vue-virtual";
import {
	connectAgentStream,
	type AgentLog,
	type AgentType,
	type LogLevel,
	mockAgentStream,
} from "@/services/mockApi";
import { agentColorMap, levelColorMap } from "@/utils/colors";

interface Props {
	useMock?: boolean;
	wsUrl?: string;
	typeInterval?: number;
	maxLogs?: number;
}

const props = withDefaults(defineProps<Props>(), {
	useMock: true,
	wsUrl: "ws://localhost:8000/ws/agent-stream",
	typeInterval: 20,
	maxLogs: 5000,
});

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
watch(logs, () => {
	virtualizer.value.setOptions({
		...virtualizer.value.options,
		count: logs.value.length,
	});
}, { deep: true });

let typingIndex = -1;
let typingTimer: ReturnType<typeof setTimeout> | null = null;
let stopStream: (() => void) | null = null;

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

const startStream = () => {
	if (props.useMock) {
		stopStream = mockAgentStream(pushLog, () => {
			finishCurrent();
		});
	} else {
		stopStream = connectAgentStream(pushLog, undefined, props.wsUrl);
	}
};

const stopAll = () => {
	if (typingTimer) {
		clearTimeout(typingTimer);
		typingTimer = null;
	}
	if (stopStream) {
		stopStream();
		stopStream = null;
	}
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

const badgeStyle = (agent: AgentType) => {
	const c = agentColorMap[agent];
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
		startStream();
	},
	{ immediate: false },
);

startStream();

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

.light.red { background: #ff5f56; }
.light.yellow { background: #ffbd2e; }
.light.green { background: #27c93f; }

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
  padding: 2px 0;
  word-break: break-word;
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
  text-shadow: 0 0 6px rgba(56, 189, 248, 0.4);
  animation: blink 1s steps(2, start) infinite;
}

@keyframes blink {
  to { visibility: hidden; }
}
</style>
