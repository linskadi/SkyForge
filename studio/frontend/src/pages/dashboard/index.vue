<script setup lang="ts">
import {
	ArrowRight,
	Boxes,
	CheckCircle2,
	GitBranch,
	Radar,
	ShieldCheck,
} from "@lucide/vue";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { VERIFIED_RECORDINGS } from "@/data/verifiedRecordings";
import { useExecutionStore } from "@/stores/executionStore";

const router = useRouter();
const execution = useExecutionStore();

const isMounted = ref(false);
onMounted(() => {
	isMounted.value = true;
});

const pillars = [
	{
		icon: GitBranch,
		title: "端到端闭环",
		text: "需求 → 契约 → 代码 → 验证 → 证据包",
		tone: "blue",
	},
	{
		icon: ShieldCheck,
		title: "MISRA 修复",
		text: "违规定位、自动修复与前后 Diff",
		tone: "green",
	},
	{
		icon: Radar,
		title: "数字孪生",
		text: "正常波形、故障注入与契约断言",
		tone: "cyan",
	},
	{
		icon: Boxes,
		title: "全链路追溯",
		text: "REQ / LLR / CON / CODE / TST 双向关联",
		tone: "violet",
	},
];

function startDemo() {
	execution.setProfile("demo");
	router.push("/demo");
}
</script>

<template>
  <main class="cockpit-home">
    <section class="hero-panel">
      <div class="hero-copy">
        <div class="eyebrow animate-in" :style="{ '--delay': '0ms' }" :class="{ 'animate-in-active': isMounted }">
          <span /> 全国航空航天软件创新赛 · 现场演示版
        </div>
        <h1 class="animate-in" :style="{ '--delay': '80ms' }" :class="{ 'animate-in-active': isMounted }">
          把航空软件需求，锻造成<br><em>可验证、可追溯的工程证据</em>
        </h1>
        <p class="animate-in" :style="{ '--delay': '160ms' }" :class="{ 'animate-in-active': isMounted }">
          多 Agent 负责理解与生成，确定性工具负责扫描、编译和验证。3 分钟展示从自然语言需求到可信证据包的完整闭环。
        </p>
        <button
          class="primary-cta animate-in"
          :style="{ '--delay': '240ms' }"
          :class="{ 'animate-in-active': isMounted }"
          @click="startDemo"
        >
          开始 3 分钟演示 <ArrowRight :size="20" class="cta-arrow" />
        </button>
        <div class="honesty-note animate-in" :style="{ '--delay': '320ms' }" :class="{ 'animate-in-active': isMounted }">
          <span class="source-badge simulated">模拟数据</span>
          主演示完全离线运行；所有模拟结果始终明确标识，不冒充真实工具证据。
        </div>
      </div>
      <div
        class="hero-visual animate-in"
        :style="{ '--delay': '120ms' }"
        :class="{ 'animate-in-active': isMounted }"
        aria-label="SkyForge 交付闭环示意图"
      >
        <div class="orbit orbit-one" />
        <div class="orbit orbit-two" />
        <div class="core"><span>可信<br>证据包</span><CheckCircle2 :size="28" /></div>
        <div class="satellite req">需求</div>
        <div class="satellite con">契约</div>
        <div class="satellite code">代码</div>
        <div class="satellite sim">仿真</div>
      </div>
    </section>

    <section class="value-grid" aria-label="核心价值">
      <article
        v-for="(pillar, idx) in pillars"
        :key="pillar.title"
        class="value-card animate-in"
        :class="[pillar.tone, { 'animate-in-active': isMounted }]"
        :style="{ '--delay': `${280 + idx * 70}ms` }"
      >
        <div class="card-icon-glow" aria-hidden="true"></div>
        <component :is="pillar.icon" :size="26" class="card-icon" />
        <div><h2>{{ pillar.title }}</h2><p>{{ pillar.text }}</p></div>
      </article>
    </section>

    <section class="verified-section">
      <div class="animate-in" :style="{ '--delay': '520ms' }" :class="{ 'animate-in-active': isMounted }">
        <span class="section-kicker">故障兜底</span><h2>已验证运行与录像备份</h2>
      </div>
      <router-link
        v-for="(recording, idx) in VERIFIED_RECORDINGS"
        :key="recording.id"
        class="recording-card animate-in"
        :style="{ '--delay': `${580 + idx * 70}ms` }"
        :class="{ 'animate-in-active': isMounted }"
        :to="`/records?recording=${recording.id}`"
      >
        <span class="source-badge" :class="recording.profile">{{ recording.profile === 'cloud' ? '云 API' : '本地 Ollama' }}</span>
        <strong>{{ recording.title }}</strong><small>{{ recording.note }}</small>
      </router-link>
    </section>
  </main>
</template>

<style scoped>
.cockpit-home {
  min-height: calc(100dvh - var(--topbar-h,60px));
  padding: clamp(20px,3vh,30px) clamp(20px,5vw,80px) 28px;
  color: #10243a;
  background:
    radial-gradient(circle at 78% 12%,rgba(32,151,222,.13),transparent 29%),
    linear-gradient(135deg, #f4faff 0%, #fff 52%, #edf6fb 100%);
}

.animate-in {
  opacity: 0;
  transform: translateY(18px);
  transition:
    opacity 0.65s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.65s cubic-bezier(0.22, 1, 0.36, 1);
  transition-delay: var(--delay, 0ms);
}
.animate-in-active {
  opacity: 1;
  transform: translateY(0);
}

.hero-panel {
  max-width: 1380px;
  min-height: clamp(320px,42vh,400px);
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1.18fr .82fr;
  align-items: center;
  gap: clamp(28px,4vw,54px);
  margin-bottom: 28px;
}
.eyebrow {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 18px;
  color: #1164ab;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: .08em;
}
.eyebrow span { width: 28px; height: 3px; background: #1687e8; border-radius: 2px; }
h1 {
  margin: 0;
  color: #071b33;
  font-size: clamp(36px, 3.7vw, 58px);
  line-height: 1.12;
  letter-spacing: -.035em;
}
h1 em { color: #0876d1; font-style: normal; }
.hero-copy > p {
  max-width: 720px;
  margin: 22px 0;
  color: #4b6379;
  font-size: 17px;
  line-height: 1.75;
}
.primary-cta {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 15px 26px;
  border: 0;
  border-radius: 12px;
  color: white;
  background: linear-gradient(135deg, #087ee0, #0751b8);
  box-shadow: 0 12px 28px rgba(0,105,196,.25);
  font-size: 17px;
  font-weight: 850;
  cursor: pointer;
  transition:
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1);
  overflow: hidden;
}
.primary-cta::before {
  content: "";
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
  transition: left 0.5s ease;
}
.primary-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 18px 40px rgba(0,105,196,.34);
}
.primary-cta:hover::before {
  left: 100%;
}
.primary-cta:hover .cta-arrow {
  transform: translateX(4px);
}
.primary-cta:active {
  transform: translateY(0);
  box-shadow: 0 8px 20px rgba(0,105,196,.28);
}
.cta-arrow {
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.honesty-note {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 20px;
  color: #60768a;
  font-size: 13px;
}
.source-badge {
  display: inline-flex;
  align-items: center;
  width: max-content;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 850;
}
.source-badge.simulated { color: #8b5100; background: #fff0cc; border: 1px solid #edc66b; }
.source-badge.replay { color: #075c9b; background: #e5f4ff; border: 1px solid #9dcfee; }
.source-badge.cloud { color: #075c9b; background: #e5f4ff; border: 1px solid #9dcfee; }
.source-badge.local { color: #16764e; background: #dff3e9; border: 1px solid #a8dbc4; }
.hero-visual {
  position: relative;
  min-height: clamp(280px,35vh,340px);
}
.orbit {
  position: absolute;
  inset: 50%;
  border: 1px dashed #82bce8;
  border-radius: 50%;
  transform: translate(-50%, -50%);
}
.orbit-one { width: 250px; height: 250px; }
.orbit-two { width: 330px; height: 330px; opacity: .6; }
.core {
  position: absolute;
  inset: 50%;
  width: 128px;
  height: 128px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 7px;
  transform: translate(-50%,-50%);
  border-radius: 50%;
  color: white;
  text-align: center;
  font-weight: 850;
  background: linear-gradient(145deg,#116cc4,#07386e);
  box-shadow: 0 15px 45px rgba(4,72,134,.3);
}
.satellite {
  position: absolute;
  display: grid;
  place-items: center;
  width: 74px;
  height: 74px;
  border-radius: 16px;
  color: #084f8b;
  background: white;
  border: 1px solid #bbdaf0;
  box-shadow: 0 7px 25px rgba(18,77,127,.13);
  font-weight: 800;
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.3s ease;
}
.satellite:hover {
  transform: scale(1.08);
  box-shadow: 0 10px 30px rgba(18,77,127,.2);
}
.satellite.req { top: 5px; left: calc(50% - 37px); }
.satellite.con { right: 1%; top: 42%; }
.satellite.code { bottom: 0; left: calc(50% - 37px); }
.satellite.sim { left: 1%; top: 42%; }

.value-grid {
  max-width: 1380px;
  margin: 0 auto 28px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.value-card {
  position: relative;
  display: flex;
  gap: 13px;
  padding: 18px 18px;
  border: 1px solid #d2e2ec;
  border-radius: 14px;
  background: rgba(255,255,255,.94);
  box-shadow: 0 6px 20px rgba(16,57,91,.07);
  transition:
    transform 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.3s ease;
  overflow: hidden;
}
.value-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 16px 40px rgba(16,57,91,.12);
  border-color: #9dcfee;
}
.value-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, #1170b3, #1a8bdd);
  opacity: 0;
  transition: opacity 0.3s ease;
}
.value-card:hover::before {
  opacity: 1;
}
.card-icon-glow {
  position: absolute;
  top: 14px;
  left: 14px;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: radial-gradient(circle at center, rgba(26, 139, 221, 0.25), transparent 70%);
  filter: blur(6px);
  opacity: 0;
  transition: opacity 0.4s ease;
  pointer-events: none;
}
.value-card:hover .card-icon-glow {
  opacity: 1;
}
.card-icon {
  position: relative;
  flex: none;
  color: #127ed3;
  z-index: 1;
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.value-card:hover .card-icon {
  transform: scale(1.1);
}
.value-card.green .card-icon { color: #168b5c; }
.value-card.green .card-icon-glow {
  background: radial-gradient(circle at center, rgba(22, 139, 92, 0.25), transparent 70%);
}
.value-card.green::before {
  background: linear-gradient(90deg, #0d7a4e, #168b5c);
}
.value-card.green:hover {
  border-color: #8fd1b0;
}
.value-card.cyan .card-icon { color: #0e8fb8; }
.value-card.cyan .card-icon-glow {
  background: radial-gradient(circle at center, rgba(14, 143, 184, 0.25), transparent 70%);
}
.value-card.cyan::before {
  background: linear-gradient(90deg, #0b7a9e, #0e8fb8);
}
.value-card.cyan:hover {
  border-color: #7fd0e6;
}
.value-card.violet .card-icon { color: #7356c9; }
.value-card.violet .card-icon-glow {
  background: radial-gradient(circle at center, rgba(115, 86, 201, 0.25), transparent 70%);
}
.value-card.violet::before {
  background: linear-gradient(90deg, #5a3fb0, #7356c9);
}
.value-card.violet:hover {
  border-color: #c0b0e8;
}
.value-card h2 { margin: 0 0 5px; font-size: 16px; }
.value-card p { margin: 0; color: #5a7084; font-size: 13px; line-height: 1.55; }

.verified-section {
  max-width: 1380px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 270px 270px;
  gap: 16px;
  align-items: stretch;
}
.verified-section h2 { margin: 5px 0 0; font-size: 21px; }
.section-kicker { color: #1687e8; font-size: 12px; font-weight: 850; }
.recording-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 18px;
  border-radius: 12px;
  border: 1px solid #9ec9e6;
  color: inherit;
  background: #f8fbfd;
  text-decoration: none;
  transition:
    transform 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.3s ease;
}
.recording-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(16, 91, 145, 0.12);
  border-color: #5aaae6;
}
.recording-card.unavailable {
  border-style: dashed;
  border-color: #b5c9d8;
}
.recording-card.unavailable:hover {
  transform: none;
  box-shadow: none;
  border-color: #9fb3c5;
}
.recording-card strong { font-size: 14px; }
.recording-card small { color: #718496; font-size: 12px; }
.unavailable-badge {
  color: #516879;
  background: #e8eef2;
  border: 1px solid #c5d3dc;
}

@media (max-height: 850px) and (min-width:1001px) {
  .cockpit-home { padding-top: 16px; }
  .hero-panel { min-height: 300px; margin-bottom: 20px; }
  .hero-copy>p { margin: 14px 0; font-size: 15px; }
  .hero-visual { min-height: 270px; }
  .orbit-one { width: 210px; height: 210px; }
  .orbit-two { width: 280px; height: 280px; }
  .value-grid { margin-bottom: 20px; gap: 14px; }
  .value-card { padding: 14px 16px; }
  .verified-section h2 { font-size: 18px; }
  .recording-card { padding: 12px 14px; }
}
@media (max-width: 1000px) {
  .hero-panel { grid-template-columns: 1fr; }
  .hero-visual { display: none; }
  .value-grid { grid-template-columns: repeat(2, 1fr); }
  .verified-section { grid-template-columns: 1fr; }
}
@media(max-width:600px) {
  .cockpit-home { padding-inline: 16px; }
  .hero-panel { min-height: auto; padding: 18px 0 24px; }
  h1 { font-size: 34px; }
  .hero-copy>p { font-size: 15px; }
  .value-grid { grid-template-columns: 1fr; }
  .honesty-note { align-items: flex-start; }
  .primary-cta { width: 100%; justify-content: center; }
  .verified-section { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .animate-in,
  .animate-in-active,
  .primary-cta,
  .primary-cta:hover,
  .primary-cta:active,
  .primary-cta::before,
  .cta-arrow,
  .satellite,
  .satellite:hover,
  .value-card,
  .value-card:hover,
  .value-card::before,
  .card-icon,
  .value-card:hover .card-icon,
  .recording-card,
  .recording-card:hover {
    transition: none !important;
    animation: none !important;
    transform: none !important;
  }
  .animate-in {
    opacity: 1 !important;
  }
}
</style>
