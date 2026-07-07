<script setup lang="ts">
/**
 * TerminalFrame 共享 VSCode 终端外框组件
 * 提取 AgentTerminal / SimulationResult 重复的终端样式
 */
interface Props {
  title?: string;
  showTrafficLights?: boolean;
}

withDefaults(defineProps<Props>(), {
  title: "Terminal",
  showTrafficLights: true,
});
</script>

<template>
  <div class="terminal-frame">
    <div class="terminal-header">
      <div v-if="showTrafficLights" class="traffic-lights">
        <span class="light red" />
        <span class="light yellow" />
        <span class="light green" />
      </div>
      <div class="terminal-title">
        {{ title }}
      </div>
      <div class="header-actions">
        <slot name="header-actions" />
      </div>
    </div>
    <div class="terminal-body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.terminal-frame {
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
</style>
