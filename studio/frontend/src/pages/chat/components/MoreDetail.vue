<script setup lang="ts">
/**
 * MoreDetail 更多详情侧边面板（stub）
 * TODO: 后续实现完整功能
 */
const modelValue = defineModel<boolean>();
</script>

<template>
  <div v-if="modelValue" class="fixed inset-0 z-50 flex">
    <div class="absolute inset-0 bg-black/50" @click="modelValue = false" />
    <div class="relative ml-auto w-80 bg-white h-full shadow-lg p-4">
      <h3 class="text-lg font-semibold mb-4">更多详情</h3>
      <p class="text-sm text-gray-500">功能开发中...</p>
      <button class="mt-4 text-sm text-blue-500" @click="modelValue = false">关闭</button>
    </div>
  </div>
</template>
