<script setup lang="ts">
/**
 * TaskToolbar 顶部工具栏
 * 显示运行时长、WebSocket 状态、Agent 状态、控制按钮
 */
import { ref, onMounted, onBeforeUnmount } from "vue";
import { Button } from "@/components/ui/button";
import AgentStatus from "./AgentStatus.vue";

interface Props {
  /** WebSocket 连接状态 */
  wsStatus: "connecting" | "connected" | "disconnected" | "reconnecting";
  /** 任务是否正在运行 */
  isRunning: boolean;
  /** 是否正在请求停止 */
  isStopping?: boolean;
  /** 当前活跃的 Agent */
  activeAgent?: string | null;
  /** 已完成的 Agent 列表 */
  completedAgents?: string[];
}

const props = withDefaults(defineProps<Props>(), {
  isStopping: false,
  activeAgent: null,
  completedAgents: () => [],
});

void props;

const emit = defineEmits<{
  (e: "stop"): void;
  (e: "download"): void;
}>();

/** 运行时长 */
const startTime = ref(Date.now());
const runningDuration = ref("0s");
let timer: ReturnType<typeof setInterval> | null = null;

const formatDuration = (ms: number): string => {
  const seconds = Math.floor(ms / 1000);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m ${remainingSeconds}s`;
  if (minutes > 0) return `${minutes}m ${remainingSeconds}s`;
  return `${remainingSeconds}s`;
};

const updateDuration = () => {
  runningDuration.value = formatDuration(Date.now() - startTime.value);
};

onMounted(() => {
  timer = setInterval(updateDuration, 1000);
  updateDuration();
});

onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});

const wsStatusLabel = {
  connected: "已连接",
  connecting: "连接中",
  reconnecting: "重连中",
  disconnected: "未连接",
};
</script>

<template>
  <div class="task-toolbar">
    <div class="toolbar-left">
      <!-- 运行时长 -->
      <div class="duration">
        运行时长: <span class="duration-value">{{ runningDuration }}</span>
      </div>

      <!-- WebSocket 状态 -->
      <div class="ws-status">
        <span
          class="ws-dot"
          :class="{
            'bg-green-500': wsStatus === 'connected',
            'bg-yellow-500 animate-pulse': wsStatus === 'connecting' || wsStatus === 'reconnecting',
            'bg-red-500': wsStatus === 'disconnected',
          }"
        />
        <span class="ws-text">{{ wsStatusLabel[wsStatus] }}</span>
      </div>

      <!-- Agent 状态 -->
      <AgentStatus
        :active-agent="activeAgent"
        :completed-agents="completedAgents"
      />
    </div>

    <div class="toolbar-right">
      <Button
        v-if="isRunning"
        variant="destructive"
        :disabled="isStopping"
        size="sm"
        @click="emit('stop')"
      >
        {{ isStopping ? "停止中..." : "停止运行" }}
      </Button>
      <Button variant="outline" size="sm" @click="emit('download')">
        下载消息
      </Button>
    </div>
  </div>
</template>

<style scoped>
.task-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
  gap: 12px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.duration {
  font-size: 13px;
  color: #6b7280;
}

.duration-value {
  font-family: 'Consolas', monospace;
  color: #3b82f6;
  font-weight: 600;
}

.ws-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.ws-dot {
  display: inline-block;
  height: 8px;
  width: 8px;
  border-radius: 50%;
}

.ws-text {
  color: #6b7280;
}
</style>
