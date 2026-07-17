<script setup lang="ts">
import Toaster from "@/components/ui/toast/Toaster.vue";
import { useTheme } from "@/composables/useTheme";
import { Moon, Sun } from "lucide-vue-next";
import { ref, watch } from "vue";

const { isDark, toggleTheme } = useTheme();
const iconRotate = ref(0);

watch(isDark, () => {
	iconRotate.value += 180;
});
</script>

<template>
  <div class="app-shell">
    <button
      @click="toggleTheme"
      class="theme-toggle-btn"
      :title="isDark ? '切换亮色模式' : '切换深色模式'"
    >
      <span class="icon-wrap" :style="{ transform: `rotate(${iconRotate}deg)` }">
        <Sun v-if="isDark" class="w-4 h-4" />
        <Moon v-else class="w-4 h-4" />
      </span>
    </button>
    <router-view v-slot="{ Component }">
      <Transition name="fade-slide" mode="out-in">
        <component :is="Component" />
      </Transition>
    </router-view>
    <Toaster />
  </div>
</template>

<style scoped>
.app-shell { min-height: 100vh; }
.theme-toggle-btn {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 12px;
  border: 1px solid hsla(222, 25%, 20%, 0.5);
  background: hsla(222, 40%, 14%, 0.7);
  backdrop-filter: blur(12px);
  color: hsl(210, 15%, 60%);
  cursor: pointer;
  transition: all 0.3s ease;
}
.theme-toggle-btn:hover {
  border-color: hsl(195, 85%, 55%, 0.4);
  color: hsl(195, 85%, 55%);
}
.icon-wrap {
  display: inline-flex;
  transition: transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}
</style>
