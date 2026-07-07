<script setup lang="ts">
/**
 * HILPage.vue - HIL 人机协作审批独立页面
 *
 * - 顶部：页面标题
 * - 主体：HILPanel 组件
 */
import { ClipboardList } from "lucide-vue-next";
import HILPanel from "@/components/HILPanel.vue";
</script>

<template>
  <div class="hil-page">
    <header class="page-header">
      <h1 class="page-title">
        <ClipboardList class="icon" />
        HIL 人机协作审批
      </h1>
      <p class="subtitle">
        需求审查 / 契约审查 / 代码审查 / 最终审查 — 人工介入审批检查点
      </p>
    </header>

    <HILPanel />
  </div>
</template>

<style scoped>
.hil-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px 32px 64px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  padding: 4px 0 8px;
  border-bottom: 1px solid var(--border, #e4e4e7);
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  margin: 0;
  color: var(--foreground, #18181b);
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-title .icon {
  width: 24px;
  height: 24px;
  color: #ea580c;
}

.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--muted-foreground, #71717a);
}
</style>
