<script setup lang="ts">
/**
 * TaskStatusBar 底部状态栏
 * 显示 MISRA 检查状态、数字孪生状态、文件数量
 */
interface Props {
  /** 合规检查通过率 */
  complianceRate?: string | null;
  /** 数字孪生状态 */
  twinStatus?: "idle" | "running" | "passed" | "failed" | null;
  /** 文件数量 */
  fileCount?: number;
}

const props = withDefaults(defineProps<Props>(), {
  complianceRate: null,
  twinStatus: null,
  fileCount: 0,
});

void props;

const twinStatusLabel = {
  idle: "待运行",
  running: "运行中",
  passed: "已通过",
  failed: "未通过",
};

const twinStatusColor = {
  idle: "#9ca3af",
  running: "#0EA5E9",
  passed: "#22c55e",
  failed: "#ef4444",
};
</script>

<template>
  <div class="task-status-bar">
    <div class="status-left">
      <span class="status-item">
        <span class="status-label">文件:</span>
        <span class="status-value">{{ fileCount }}</span>
      </span>
      <span v-if="complianceRate" class="status-item">
        <span class="status-label">MISRA:</span>
        <span class="status-value compliance">{{ complianceRate }}</span>
      </span>
    </div>
    <div class="status-right">
      <span v-if="twinStatus" class="status-item">
        <span class="status-label">数字孪生:</span>
        <span
          class="status-value"
          :style="{ color: twinStatusColor[twinStatus] }"
        >{{ twinStatusLabel[twinStatus] }}</span>
      </span>
    </div>
  </div>
</template>

<style scoped>
.task-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 16px;
  border-top: 1px solid #e5e7eb;
  background: #f9fafb;
  font-size: 12px;
  color: #6b7280;
}

.status-left,
.status-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.status-label {
  color: #9ca3af;
}

.status-value {
  font-family: 'Consolas', monospace;
  font-weight: 600;
}

.status-value.compliance {
  color: #22c55e;
}
</style>
