<script setup lang="ts">
/**
 * ApiDialog API 配置对话框（stub）
 * TODO: 后续实现完整功能
 */
const modelValue = defineModel<boolean>();
</script>

<template>
  <div v-if="modelValue" class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="absolute inset-0 bg-black/50" @click="modelValue = false" />
    <div class="relative bg-white rounded-lg shadow-lg p-6 w-96">
      <h3 class="text-lg font-semibold mb-4">API 配置</h3>
      <p class="text-sm text-gray-500">功能开发中...</p>
      <div class="mt-4 flex justify-end">
        <button class="text-sm text-blue-500" @click="modelValue = false">关闭</button>
      </div>
    </div>
  </div>
</template>
