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
  border: 1px solid var(--border, hsl(220, 13%, 90%));
  background: var(--card, hsl(0, 0%, 100%));
  backdrop-filter: blur(8px);
  color: var(--muted-foreground, hsl(220, 9%, 46%));
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.theme-toggle-btn:hover {
  border-color: var(--primary, hsl(220, 70%, 50%));
  color: var(--primary, hsl(220, 70%, 50%));
  box-shadow: 0 0 8px hsla(220, 70%, 50%, 0.15);
}

/* 深色模式下的按钮样式 */
:global(.dark) .theme-toggle-btn,
:deep(.dark .theme-toggle-btn) {
  background: hsla(220, 25%, 7%, 0.85);
  border-color: hsla(210, 80%, 55%, 0.15);
  color: hsl(220, 10%, 60%);
}

:global(.dark) .theme-toggle-btn:hover {
  background: hsla(210, 80%, 55%, 0.12);
  border-color: hsla(210, 80%, 55%, 0.3);
  color: hsl(210, 80%, 55%);
}
</style>
