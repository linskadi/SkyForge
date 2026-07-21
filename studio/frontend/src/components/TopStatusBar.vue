<script setup lang="ts">
import { computed } from "vue";
import { useExecutionStore } from "@/stores/executionStore";

const execution = useExecutionStore();

const nav = [
	{ label: "比赛演示", to: "/" },
	{ label: "六层架构", to: "/architecture" },
	{ label: "代码生成", to: "/generate" },
	{ label: "运行记录", to: "/records" },
	{ label: "能力实验室", to: "/lab" },
	{ label: "系统设置", to: "/settings" },
];

const profileLabel = computed(() => {
	const label = execution.profile.label;
	return label.length > 12 ? `${label.slice(0, 12)}…` : label;
});

/** 运行后端徽章：按 ExecutionProfile 展示，避免把 profile 与旧 LLM mode 混用。 */
const backendBadge = computed(() => {
	const map = {
		demo: { text: "浏览器模拟", tone: "mock" },
		cloud: { text: "云模型", tone: "api" },
		local: { text: "本地模型", tone: "local" },
	} as const;
	return map[execution.profileId];
});
</script>

<template>
  <header class="competition-topbar">
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
.competition-topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  height: var(--topbar-h, 60px);
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto minmax(260px, 1fr);
  align-items: center;
  padding: 0 clamp(16px, 2.2vw, 30px);
  color: #fff;
  background: linear-gradient(100deg, #061a2e 0%, #0a2843 62%, #0b3555 100%);
  border-bottom: 2px solid #1b95df;
  box-shadow: 0 5px 20px rgba(5, 24, 49, .2);
}
.brand { display: flex; align-items: center; gap: 10px; color: inherit; text-decoration: none; }
.brand-mark { display: grid; place-items: center; width: 36px; height: 36px; border:1px solid rgba(255,255,255,.2);border-radius: 10px; font-weight: 900; background: linear-gradient(145deg, #30b5f4, #0964bd);box-shadow:0 6px 16px rgba(0,0,0,.18) }
.brand strong { display: block; font-size: 17px; letter-spacing: .02em; }
.brand small { display: block; color: #a9c6df; font-size: 12px; line-height: 1.1; }
nav { display: flex; gap: 4px; }
nav a { padding: 9px 12px; border-radius: 8px; color: #c5d8e9; font-size: 13px; font-weight: 700; text-decoration: none; }
nav a:hover, nav a.router-link-active { color: #fff; background: rgba(39, 151, 242, .2); }
.profile-indicator { justify-self: end; display: flex; align-items: center; gap: 8px; padding: 6px 12px; border: 1px solid #3b607d; border-radius: 9px; background: rgba(17,48,74,.9); }
.profile-text { color: #c5d8e9; font-size: 13px; font-weight: 700; }
.source-dot { width: 9px; height: 9px; border-radius: 50%; background: #67c23a; box-shadow: 0 0 0 4px rgba(103,194,58,.13); }
.source-dot.simulated { background: #f5a623; box-shadow: 0 0 0 4px rgba(245,166,35,.16); }
.llm-badge { padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 800; letter-spacing: .04em; }
.llm-badge.mock { color: #f5a623; background: rgba(245,166,35,.16); border: 1px solid rgba(245,166,35,.35); }
.llm-badge.api { color: #5dc7ff; background: rgba(93,199,255,.16); border: 1px solid rgba(93,199,255,.35); }
.llm-badge.local { color: #67c23a; background: rgba(103,194,58,.16); border: 1px solid rgba(103,194,58,.35); }
@media (max-width: 1220px) {
  .competition-topbar{grid-template-columns:minmax(180px,1fr) auto minmax(180px,1fr)}
  .brand small{display:none}
  nav a{padding-inline:9px}
}
@media (max-width: 940px) {
  .competition-topbar { grid-template-columns: 1fr auto; padding: 0 16px; }
  nav { display: none; }
}
@media (max-width: 560px){.brand span:last-child{display:none}.profile-text{display:none}}
</style>
