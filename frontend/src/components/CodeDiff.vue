<script setup lang="ts">
/**
 * CodeDiff 代码 Diff 展示组件
 * 使用 Monaco DiffEditor 替代自定义 LCS 算法
 */
import MonacoDiffEditor from "./MonacoDiffEditor.vue";

interface Props {
  /** 修复前代码 */
  before: string;
  /** 修复后代码 */
  after: string;
  /** 文件名（可选，用于显示标题） */
  filename?: string;
}

defineProps<Props>();
</script>
<template>
  <MonacoDiffEditor
    :before="before"
    :after="after"
    :filename="filename ?? 'code.c'"
    class="code-diff"
  />
</template>

<style scoped>
.code-diff {
  height: 100%;
  min-height: 300px;
}
</style>
