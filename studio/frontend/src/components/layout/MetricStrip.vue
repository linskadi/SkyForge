<script setup lang="ts">
interface MetricItem {
	label: string;
	value: string | number;
	hint?: string;
	tone?: "default" | "success" | "warning" | "danger";
}

defineProps<{
	metrics: MetricItem[];
}>();
</script>

<template>
  <div class="metric-strip">
    <div
      v-for="(item, index) in metrics"
      :key="index"
      class="metric-item"
      :class="`tone-${item.tone ?? 'default'}`"
    >
      <small class="metric-label">{{ item.label }}</small>
      <strong class="metric-value">{{ item.value }}</strong>
      <span v-if="item.hint" class="metric-hint">{{ item.hint }}</span>
    </div>
  </div>
</template>

<style scoped>
.metric-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(0, 1fr));
  border: 1px solid hsl(var(--border));
  border-radius: 10px;
  overflow: hidden;
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 18px;
  border-right: 1px solid hsl(var(--border));
  min-width: 0;
}

.metric-item:last-child {
  border-right: none;
}

.metric-label {
  font-size: 11px;
  font-weight: 600;
  color: hsl(var(--muted-foreground));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.metric-value {
  font-size: 20px;
  font-weight: 800;
  color: hsl(var(--foreground));
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.metric-hint {
  font-size: 12px;
  color: hsl(var(--muted-foreground));
}

.metric-item.tone-success .metric-value {
  color: hsl(142 71% 45%);
}

.metric-item.tone-warning .metric-value {
  color: hsl(38 92% 50%);
}

.metric-item.tone-danger .metric-value {
  color: hsl(0 84% 60%);
}

@media (max-width: 640px) {
  .metric-strip {
    grid-template-columns: 1fr 1fr;
  }
  .metric-item:nth-child(2n) {
    border-right: none;
  }
  .metric-item:nth-child(n + 3) {
    border-top: 1px solid hsl(var(--border));
  }
}
</style>
