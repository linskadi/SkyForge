<script setup lang="ts">
/**
 * AgentStatus 4 Agent 状态指示器
 * 显示 REQ-Parser / CON-Gen / CODE-Gen / REPAIR 四个 Agent 的实时状态
 */
import { computed } from "vue";
import { CheckCircle2, Loader2, Circle, AlertCircle } from "lucide-vue-next";

type AgentStage = "pending" | "running" | "completed" | "error";

interface AgentInfo {
  key: string;
  label: string;
  enLabel: string;
  color: string;
  stage: AgentStage;
}

const props = defineProps<{
  /** 当前活跃的 Agent 类型 */
  activeAgent?: string | null;
  /** 已完成的 Agent 列表 */
  completedAgents?: string[];
  /** 是否有错误 */
  hasError?: boolean;
}>();

const agents = computed<AgentInfo[]>(() => {
  const agentDefs = [
    { key: "REQ-Parser", label: "需求解析", enLabel: "REQ-Parser", color: "#1e6fb8" },
    { key: "CON-Gen", label: "契约生成", enLabel: "CON-Gen", color: "#7e22ce" },
    { key: "CODE-Gen", label: "代码生成", enLabel: "CODE-Gen", color: "#15803d" },
    { key: "REPAIR", label: "代码修复", enLabel: "REPAIR", color: "#ea580c" },
  ];

  return agentDefs.map((def) => {
    let stage: AgentStage = "pending";
    if (props.completedAgents?.includes(def.key)) {
      stage = "completed";
    } else if (props.activeAgent === def.key) {
      stage = "running";
    } else if (props.hasError && !props.completedAgents?.includes(def.key)) {
      stage = "error";
    }
    return { ...def, stage };
  });
});

const stageIcon = (stage: AgentStage) => {
  switch (stage) {
    case "completed": return CheckCircle2;
    case "running": return Loader2;
    case "error": return AlertCircle;
    default: return Circle;
  }
};
</script>

<template>
  <div class="agent-status">
    <div
      v-for="agent in agents"
      :key="agent.key"
      class="agent-item"
      :class="[`stage-${agent.stage}`]"
    >
      <div
        class="agent-dot"
        :style="{ backgroundColor: agent.stage === 'completed' ? agent.color : agent.stage === 'running' ? agent.color : '#6b7280' }"
      >
        <component
          :is="stageIcon(agent.stage)"
          class="agent-icon"
          :class="{ 'animate-spin': agent.stage === 'running' }"
        />
      </div>
      <div class="agent-text">
        <div class="agent-label">{{ agent.label }}</div>
        <div class="agent-en">{{ agent.enLabel }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-status {
  display: flex;
  align-items: center;
  gap: 16px;
}

.agent-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  transition: all 0.2s;
}

.agent-item.stage-pending {
  opacity: 0.5;
}

.agent-item.stage-running {
  background: rgba(59, 130, 246, 0.1);
}

.agent-item.stage-completed {
  opacity: 1;
}

.agent-item.stage-error {
  background: rgba(239, 68, 68, 0.1);
}

.agent-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.agent-icon {
  width: 14px;
  height: 14px;
  color: #fff;
}

.agent-text {
  display: flex;
  flex-direction: column;
}

.agent-label {
  font-size: 12px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.2;
}

.agent-en {
  font-size: 10px;
  color: #9ca3af;
  font-family: 'Consolas', monospace;
  line-height: 1.2;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
