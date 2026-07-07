<script setup lang="ts">
/**
 * AgentTerminal 组件（Patch 4 重点）
 *
 * VSCode 终端样式：黑色背景 #1e1e1e，Consolas 字体，#d4d4d4 文字色
 * - 顶部：红黄绿三圆点 + 标题"🤖 AirborneAI Agent Console"
 * - 主体：日志列表，自动滚动到底部
 * - 每行日志：时间戳 + Agent 徽章（彩色） + 内容
 * - 打字机效果：逐字推入（20ms/字）
 * - 闪烁光标 ▊
 * - 日志分级：error #f44747 / warn #cca700 / success #4ec9b0 / info 默认色
 *
 * 默认走 mock 模式；将 useMock 设为 false 时连接真实 WebSocket。
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import {
	connectAgentStream,
	type AgentLog,
	type AgentType,
	type LogLevel,
	mockAgentStream,
} from "@/services/mockApi";

interface Props {
	/** 是否使用 mock 数据演示（后端未完成时为 true） */
	useMock?: boolean;
	/** WebSocket 地址（仅 useMock=false 时生效） */
	wsUrl?: string;
	/** 打字机效果每字间隔（毫秒） */
	typeInterval?: number;
	/** 最大保留日志条数 */
	maxLogs?: number;
}

const props = withDefaults(defineProps<Props>(), {
	useMock: true,
	wsUrl: "ws://localhost:8000/ws/agent-stream",
	typeInterval: 20,
	maxLogs: 200,
});

/** 已渲染的日志条目（含正在打字中的） */
interface RenderedLog {
	ts: number;
	agent: AgentType;
	level: LogLevel;
	/** 已经"打字"出来的内容（逐步增长） */
	visibleText: string;
	/** 完整内容 */
	fullText: string;
	/** 是否已打字完毕 */
	done: boolean;
}

const logs = ref<RenderedLog[]>([]);
const logContainerRef = ref<HTMLDivElement | null>(null);

/** Agent 徽章颜色（与文档 11.2.1 节对齐） */
const agentColorMap: Record<AgentType, { bg: string; fg: string }> = {
	"REQ-Parser": { bg: "#1e6fb8", fg: "#d6e8ff" },
	"CON-Gen": { bg: "#7e22ce", fg: "#f0e6ff" },
	"CODE-Gen": { bg: "#15803d", fg: "#dcfce7" },
	REPAIR: { bg: "#ea580c", fg: "#ffedd5" },
	SYSTEM: { bg: "#525252", fg: "#e5e5e5" },
	TERMINAL: { bg: "#0891b2", fg: "#cffafe" },
};

/** 日志级别颜色 */
const levelColorMap: Record<LogLevel, string> = {
	info: "#d4d4d4",
	success: "#4ec9b0",
	warn: "#cca700",
	error: "#f44747",
};

/** 当前正在打字的日志索引与定时器 */
let typingIndex = -1;
let typingTimer: ReturnType<typeof setTimeout> | null = null;
let stopStream: (() => void) | null = null;

/** 把一条日志加入列表，并启动打字机效果 */
const pushLog = (log: AgentLog) => {
	if (logs.value.length >= props.maxLogs) {
		logs.value.shift();
	}
	// 前一条立即打字完成
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

/** 启动打字机效果 */
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

/** 强制把当前正在打字的日志立即完整显示 */
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

/** 自动滚动到底部 */
const scrollToBottom = () => {
	nextTick(() => {
		const el = logContainerRef.value;
		if (el) {
			el.scrollTop = el.scrollHeight;
		}
	});
};

/** 启动日志流（mock 或真实 WS） */
const startStream = () => {
	if (props.useMock) {
		stopStream = mockAgentStream(pushLog, () => {
			// mock 全部推送完毕
			finishCurrent();
		});
	} else {
		stopStream = connectAgentStream(pushLog, undefined, props.wsUrl);
	}
};

/** 停止日志流 */
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

/** 清空日志 */
const clearLogs = () => {
	logs.value = [];
	typingIndex = -1;
};

/** 暴露给父组件：手动追加日志 / 启动 / 停止 / 清空 */
defineExpose({
	start: startStream,
	stop: stopAll,
	clear: clearLogs,
	push: pushLog,
	finish: finishCurrent,
});

/** 时间戳格式化 HH:MM:SS.mmm */
const formatTs = (ts: number) => {
	const d = new Date(ts);
	const pad = (n: number, len = 2) => n.toString().padStart(len, "0");
	return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(
		d.getSeconds(),
	)}.${pad(d.getMilliseconds(), 3)}`;
};

/** Agent 徽章样式 */
const badgeStyle = (agent: AgentType) => {
	const c = agentColorMap[agent];
	return {
		backgroundColor: c.bg,
		color: c.fg,
	};
};

/** 主内容颜色 */
const contentStyle = (level: LogLevel) => ({
	color: levelColorMap[level],
});

/** 是否显示闪烁光标（只在最新一条未完成时显示） */
const showCursor = computed(() => {
	const last = logs.value[logs.value.length - 1];
	return last && !last.done;
});

/** 组件挂载即开始流式输出 */
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
        🤖 AirborneAI Agent Console
      </div>
      <div class="header-actions">
        <span v-if="useMock" class="mock-badge">MOCK</span>
        <button class="clear-btn" type="button" title="清空日志" @click="clearLogs">清空</button>
      </div>
    </div>

    <!-- 终端日志主体 -->
    <div ref="logContainerRef" class="terminal-body">
      <div v-if="!logs.length" class="empty-hint">
        等待 Agent 思考日志流入...
      </div>
      <div v-for="(log, i) in logs" :key="i" class="log-line">
        <span class="log-ts">{{ formatTs(log.ts) }}</span>
        <span class="log-badge" :style="badgeStyle(log.agent)">{{ log.agent }}</span>
        <span class="log-content" :style="contentStyle(log.level)">
          <span>{{ log.visibleText }}</span><span v-if="showCursor && i === logs.length - 1"
            class="cursor">▊</span>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-terminal {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1e1e1e;
  border-radius: 8px;
  overflow: hidden;
  font-family: 'Consolas', 'Courier New', monospace;
  color: #d4d4d4;
}

.terminal-header {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: #2d2d2d;
  border-bottom: 1px solid #3c3c3c;
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

.light.red {
  background: #ff5f56;
}

.light.yellow {
  background: #ffbd2e;
}

.light.green {
  background: #27c93f;
}

.terminal-title {
  font-size: 13px;
  color: #cccccc;
  font-weight: 500;
  flex: 1;
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
  border: 1px solid #555;
  color: #aaa;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 3px;
  cursor: pointer;
  font-family: inherit;
}

.clear-btn:hover {
  background: #3c3c3c;
  color: #fff;
}

.terminal-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
  scroll-behavior: smooth;
}

.terminal-body::-webkit-scrollbar {
  width: 8px;
}

.terminal-body::-webkit-scrollbar-track {
  background: transparent;
}

.terminal-body::-webkit-scrollbar-thumb {
  background: #3c3c3c;
  border-radius: 4px;
}

.terminal-body::-webkit-scrollbar-thumb:hover {
  background: #505050;
}

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
  color: #6a9955;
  flex-shrink: 0;
  font-size: 12px;
  padding-top: 1px;
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
  color: #d4d4d4;
  animation: blink 1s steps(2, start) infinite;
}

@keyframes blink {
  to {
    visibility: hidden;
  }
}
</style>
