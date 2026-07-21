<script setup lang="ts">
defineProps<{
	title?: string;
}>();
</script>

<template>
  <div class="section-card">
    <div v-if="title || $slots.header" class="section-card-header">
      <h3 v-if="title" class="section-card-title">{{ title }}</h3>
      <slot name="header" />
      <div v-if="$slots.actions" class="section-card-actions">
        <slot name="actions" />
      </div>
    </div>
    <div class="section-card-content">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.section-card {
  border-radius: 12px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--card));
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  padding: 20px;
  transition: all 0.2s ease;
}

.section-card:hover {
  border-color: hsl(var(--primary) / 0.3);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}

.section-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.section-card-title {
  font-size: 16px;
  font-weight: 700;
  color: hsl(var(--foreground));
  margin: 0;
}

.section-card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.section-card-content {
  color: hsl(var(--foreground));
}
</style>
