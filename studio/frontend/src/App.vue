<script setup lang="ts">
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import TopStatusBar from "@/components/TopStatusBar.vue";
import Toaster from "@/components/ui/toast/Toaster.vue";
</script>

<template>
  <div class="app-shell">
    <TopStatusBar />
    <router-view v-slot="{ Component }">
      <Transition name="fade-slide" mode="out-in">
        <component :is="Component" />
      </Transition>
    </router-view>
    <Toaster />
    <ConfirmDialog />
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: hsl(var(--background));
}
</style>
