<script setup lang="ts">
import Toaster from "@/components/ui/toast/Toaster.vue";
import { useTheme } from "@/composables/useTheme";
import { Moon, Sun } from "lucide-vue-next";

const { isDark, toggleTheme } = useTheme();
</script>

<template>
  <Toaster />
  <!-- 全局主题切换按钮 -->
  <button
    @click="toggleTheme"
    class="theme-toggle-btn"
    :title="isDark ? '切换亮色模式' : '切换深色模式'"
  >
    <Sun v-if="isDark" class="w-4 h-4" />
    <Moon v-else class="w-4 h-4" />
  </button>
  <router-view />
</template>

<style scoped>
.theme-toggle-btn {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  color: #475569;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.theme-toggle-btn:hover {
  border-color: #0EA5E9;
  color: #0EA5E9;
  box-shadow: 0 0 8px rgba(14, 165, 233, 0.15);
}

/* 深色模式下的按钮样式 */
:global(.dark) .theme-toggle-btn,
:deep(.dark .theme-toggle-btn) {
  background: rgba(15, 23, 42, 0.85);
  border-color: rgba(14, 165, 233, 0.15);
  color: #94A3B8;
}

:global(.dark) .theme-toggle-btn:hover {
  background: rgba(14, 165, 233, 0.12);
  border-color: rgba(14, 165, 233, 0.3);
  color: #38BDF8;
}
</style>
