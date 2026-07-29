<script setup lang="ts">
import { computed } from "vue";
import { useExecutionStore } from "@/stores/executionStore";

const execution = useExecutionStore();

const nav = [
	{ label: "仪表板", to: "/" },
	{ label: "代码生成", to: "/generate" },
	{ label: "任务管理", to: "/records" },
	{ label: "合规审计", to: "/misra" },
	{ label: "仿真实验室", to: "/lab" },
	{ label: "组合验证", to: "/compose" },
	{ label: "HITL审查", to: "/hitl" },
	{ label: "文档中心", to: "/architecture" },
	{ label: "系统设置", to: "/settings" },
];

const profileLabel = computed(() => {
	const label = execution.profile.label;
	return label.length > 12 ? `${label.slice(0, 12)}…` : label;
});

const backendBadge = computed(() => {
	const map = {
		cloud: { text: "云模型", tone: "api" },
		local: { text: "本地模型", tone: "local" },
	} as const;
	return map[execution.profileId];
});
</script>

<template>
  <header class="app-topbar">
    <router-link to="/" class="brand" aria-label="SkyForge 首页">
      <span class="brand-mark">SF</span>
      <span><strong>SkyForge</strong><small>可信机载软件智能工坊</small></span>
    </router-link>

    <nav aria-label="主导航">
      <router-link v-for="item in nav" :key="item.to" :to="item.to">{{ item.label }}</router-link>
    </nav>

    <div class="profile-indicator">
      <span class="source-dot" :class="execution.profile.source" />
      <span class="profile-text">{{ profileLabel }}</span>
      <span class="llm-badge" :class="backendBadge.tone" :title="`当前执行来源：${execution.profile.label}`">{{ backendBadge.text }}</span>
    </div>
  </header>
</template>

<style scoped>
.app-topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  height: var(--topbar-h, 60px);
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto minmax(260px, 1fr);
  align-items: center;
  padding: 0 clamp(16px, 2.2vw, 30px);
  background: hsl(var(--background) / 0.8);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid hsl(var(--border));
  color: hsl(var(--foreground));
}
.brand { display: flex; align-items: center; gap: 10px; color: inherit; text-decoration: none; }
.brand-mark {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  font-weight: 900;
  background: hsl(var(--primary));
  color: hsl(var(--primary-foreground));
}
.brand strong { display: block; font-size: 17px; letter-spacing: .02em; color: hsl(var(--foreground)); }
.brand small { display: block; color: hsl(var(--muted-foreground)); font-size: 12px; line-height: 1.1; }
nav { display: flex; gap: 2px; }
nav a {
  padding: 7px 12px;
  border-radius: 8px;
  color: hsl(var(--muted-foreground));
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: background-color 150ms ease, color 150ms ease;
}
nav a:hover {
  color: hsl(var(--foreground));
  background: hsl(var(--muted));
}
nav a.router-link-active {
  color: hsl(var(--primary));
  background: hsl(var(--primary) / 0.08);
}
.profile-indicator {
  justify-self: end;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border: 1px solid hsl(var(--border));
  border-radius: 9px;
  background: hsl(var(--card));
}
.profile-text { color: hsl(var(--foreground)); font-size: 13px; font-weight: 500; }
.source-dot { width: 9px; height: 9px; border-radius: 50%; background: hsl(var(--success)); }
.source-dot.simulated { background: hsl(var(--warning)); }
.llm-badge { padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; letter-spacing: .04em; }
.llm-badge.mock { color: hsl(var(--warning)); background: hsl(var(--warning) / 0.12); border: 1px solid hsl(var(--warning) / 0.3); }
.llm-badge.api { color: hsl(var(--primary)); background: hsl(var(--primary) / 0.12); border: 1px solid hsl(var(--primary) / 0.3); }
.llm-badge.local { color: hsl(var(--success)); background: hsl(var(--success) / 0.12); border: 1px solid hsl(var(--success) / 0.3); }
@media (max-width: 1280px) {
  .app-topbar{grid-template-columns:minmax(180px,1fr) auto minmax(180px,1fr)}
  .brand small{display:none}
  nav a{padding-inline:9px}
  nav { gap: 0px; }
}
@media (max-width: 1024px) {
  .app-topbar { grid-template-columns: 1fr auto; padding: 0 16px; }
  nav { display: none; }
}
@media (max-width: 560px){.brand span:last-child{display:none}.profile-text{display:none}}
</style>
