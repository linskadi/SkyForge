<script setup lang="ts">
import HILPanel from "@/components/HILPanel.vue";
/**
 * HILPage.vue - HIL 人机协作审批独立页面
 *
 * - 顶部：页面标题
 * - 主体：HILPanel 组件
 */
import { ArrowLeft, ClipboardList } from "lucide-vue-next";
import { useRouter } from "vue-router";

const router = useRouter();
</script>

<template>
  <div class="hil-page">
    <header class="page-header">
      <div class="title-area">
        <div class="title-row">
          <button class="back-btn" @click="router.push('/')" title="返回首页">
            <ArrowLeft class="icon" />
          </button>
          <h1 class="page-title">
            <ClipboardList class="icon" />
            HIL 人机协作审批
          </h1>
        </div>
        <p class="subtitle">
          需求审查 / 契约审查 / 代码审查 / 最终审查 — 人工介入审批检查点
        </p>
      </div>
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
  border-bottom: 1px solid hsl(var(--border));
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--card));
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.back-btn:hover {
  border-color: hsl(220, 70%, 50%);
  color: hsl(220, 70%, 50%);
  background: hsla(220, 70%, 50%, 0.05);
}

.back-btn .icon {
  width: 16px;
  height: 16px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  margin: 0;
  color: hsl(var(--foreground));
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-title .icon {
  width: 24px;
  height: 24px;
  color: hsl(220, 70%, 50%);
}

.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: hsl(var(--muted-foreground));
}
</style>
