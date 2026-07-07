<script setup lang="ts">
/**
 * TagBadge 共享内联标签徽章组件
 * 渲染 [REQ-xxx] / [MISRA-Rule-x.x] / [CON-xxx] 为彩色徽章
 */
import type { InlineToken } from "@/utils/tagParser";

interface Props {
  token: InlineToken;
  clickable?: boolean;
  active?: boolean;
}

defineProps<Props>();

const emit = defineEmits<{
  (e: "reqClick", value: string): void;
}>();
</script>

<template>
  <span
    v-if="token.type === 'text'"
    class="text-token"
  >{{ token.value }}</span>
  <span
    v-else-if="token.type === 'req'"
    class="tag-badge req-badge"
    :class="{ clickable, active }"
    :title="clickable ? `点击高亮 ${token.value}` : `需求标签 ${token.value}`"
    @click="emit('reqClick', token.value)"
  >[{{ token.value }}]</span>
  <span
    v-else-if="token.type === 'misra'"
    class="tag-badge misra-badge"
    :title="token.doc"
  >[{{ token.value }}]</span>
  <span
    v-else-if="token.type === 'con'"
    class="tag-badge con-badge"
    :title="`契约条件 ${token.value}`"
  >[{{ token.value }}]</span>
</template>

<style scoped>
.text-token {
  color: #d4d4d4;
}

.tag-badge {
  display: inline-block;
  padding: 0 6px;
  margin: 0 2px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
  transition: all 0.15s ease;
}

.req-badge {
  background: #1e6fb8;
  color: #d6e8ff;
}

.req-badge.clickable {
  cursor: pointer;
}

.req-badge.clickable:hover {
  background: #2884d1;
}

.req-badge.active {
  background: #ffd54f;
  color: #1e1e1e;
  box-shadow: 0 0 0 2px rgba(255, 213, 79, 0.5);
}

.misra-badge {
  background: #b45309;
  color: #ffedd5;
  cursor: help;
}

.misra-badge:hover {
  background: #d97706;
}

.con-badge {
  background: #6b21a8;
  color: #f0e6ff;
  cursor: help;
}

.con-badge:hover {
  background: #7e22ce;
}
</style>
