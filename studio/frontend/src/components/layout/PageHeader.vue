<script setup lang="ts">
defineProps<{
	eyebrow?: string;
	title?: string;
	description?: string;
}>();
</script>

<template>
  <div class="page-header">
    <div class="page-header-content">
      <span v-if="eyebrow" class="eyebrow">{{ eyebrow }}</span>
      <h1 v-if="title" class="title">{{ title }}</h1>
      <p v-if="description" class="description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="page-header-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-header-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.eyebrow {
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.14em;
  color: hsl(var(--primary));
  text-transform: uppercase;
}

.title {
  font-size: clamp(24px, 3vw, 32px);
  font-weight: 800;
  color: hsl(var(--foreground));
  line-height: 1.2;
  margin: 0;
}

.description {
  font-size: 14px;
  color: hsl(var(--muted-foreground));
  margin: 0;
  line-height: 1.5;
}

.page-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

@media (max-width: 640px) {
  .page-header {
    flex-direction: column;
  }
  .page-header-actions {
    width: 100%;
  }
}
</style>
