<script setup lang="ts">
import { CloudCog, Cpu, KeyRound, MonitorCog, ShieldCheck } from "@lucide/vue";
import { ref } from "vue";
import SettingsDialog from "@/components/SettingsDialog.vue";
import { useExecutionStore } from "@/stores/executionStore";
import type { ExecutionProfileId } from "@/types/execution";

const execution = useExecutionStore();
const llmSettingsOpen = ref(false);

const profileDescriptions: Record<ExecutionProfileId, string> = {
	demo: "浏览器内确定性时间线，不连接后端，适合比赛主演示。",
	cloud: "DeepSeek、Qwen、OpenAI、Anthropic 或自定义兼容 API。",
	local: "连接 Ollama、LM Studio 等本机 OpenAI-compatible 服务。",
};

function profileSourceLabel(profileId: ExecutionProfileId) {
	return profileId === "demo" ? "模拟" : "实时/回放";
}
</script>

<template>
  <main class="settings-page">
    <section class="settings-shell">
      <header class="settings-hero">
        <div>
          <span class="eyebrow">SYSTEM CONTROL</span>
          <h1>系统与模型连接</h1>
          <p>运行来源是任务的数据边界；模型连接是后端执行配置。两者分别设置、清晰可见。</p>
        </div>
      </header>

      <div class="settings-grid">
        <section class="panel profile-panel">
          <div class="panel-title"><MonitorCog :size="19" /><div><h2>运行来源</h2><p>选择当前页面和新任务的数据来源</p></div></div>
          <label
            v-for="profile in execution.profiles"
            :key="profile.id"
            class="profile-option"
            :class="{ active: execution.profileId === profile.id }"
          >
            <input
              type="radio"
              name="profile"
              :checked="execution.profileId === profile.id"
              @change="execution.setProfile(profile.id as ExecutionProfileId)"
            />
            <span class="profile-icon" :class="profile.id">
              <ShieldCheck v-if="profile.id === 'demo'" :size="18" />
              <CloudCog v-else-if="profile.id === 'cloud'" :size="18" />
              <Cpu v-else :size="18" />
            </span>
            <span class="profile-copy">
              <strong>{{ profile.label }}</strong>
              <small>{{ profileDescriptions[profile.id] }}</small>
            </span>
            <em :class="profile.source">{{ profileSourceLabel(profile.id) }}</em>
          </label>
        </section>

        <aside class="panel connection-panel">
          <div class="panel-title"><KeyRound :size="19" /><div><h2>模型连接</h2><p>由后端安全管理，不放进浏览器存储</p></div></div>
          <div class="connection-visual">
            <span class="secure-ring"><ShieldCheck :size="28" /></span>
            <strong>Backend-managed secret</strong>
            <p>支持 DeepSeek、通义千问、OpenAI、Anthropic、Ollama、LM Studio 与自定义兼容端点。</p>
          </div>
          <button class="primary-action connection-panel-action" @click="llmSettingsOpen = true">
            <KeyRound :size="18" /> 配置 LLM 连接
          </button>
          <ul>
            <li>API Key 只在输入时传给后端</li>
            <li>前端仅保存 provider、model 与 profile</li>
            <li>本机持久化文件已被 Git 忽略</li>
          </ul>
        </aside>
      </div>
    </section>
    <SettingsDialog v-model:open="llmSettingsOpen" initial-mode="api" />
  </main>
</template>

<style scoped>
.settings-page{min-height:calc(100dvh - var(--topbar-h,60px));padding:clamp(22px,4vw,52px);color:#102a43;background:radial-gradient(circle at 82% 8%,rgba(30,136,229,.12),transparent 30%),linear-gradient(145deg,#eef5fa 0%,#f8fbfd 48%,#edf6fb 100%)}
.settings-shell{max-width:1120px;margin:auto}.settings-hero{display:flex;align-items:end;justify-content:space-between;gap:28px;margin-bottom:24px}.eyebrow{color:#0878c9;font-size:12px;font-weight:900;letter-spacing:.15em}.settings-hero h1{margin:5px 0 8px;color:#071d33;font-size:clamp(28px,3vw,42px);letter-spacing:-.025em}.settings-hero p{max-width:680px;margin:0;color:#587187;font-size:15px;line-height:1.7}
.primary-action,.secondary-action{display:inline-flex;align-items:center;justify-content:center;gap:8px;border:0;border-radius:10px;font-weight:850;cursor:pointer}.primary-action{flex:none;padding:12px 18px;color:#fff;background:linear-gradient(135deg,#0985d8,#0756b4);box-shadow:0 10px 24px rgba(5,99,177,.22)}.secondary-action{width:100%;padding:10px 14px;color:#075d9e;background:#e4f3fd;border:1px solid #a7d3ef}
.settings-grid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(300px,.65fr);gap:18px}.panel{padding:22px;border:1px solid #c8dbe7;border-radius:16px;background:rgba(255,255,255,.92);box-shadow:0 10px 32px rgba(18,59,91,.08)}.panel-title{display:flex;align-items:center;gap:10px;margin-bottom:17px;color:#096fae}.panel-title h2{margin:0;color:#102a43;font-size:18px}.panel-title p{margin:3px 0 0;color:#70879a;font-size:12px}
.profile-option{display:grid;grid-template-columns:20px 42px minmax(0,1fr) auto;align-items:center;gap:11px;margin-top:10px;padding:14px;border:1px solid #d4e1e9;border-radius:12px;cursor:pointer;transition:border-color .18s,background .18s,transform .18s}.profile-option:hover{border-color:#8fc5e6;transform:translateY(-1px)}.profile-option.active{border-color:#1989d2;background:#eef8fe;box-shadow:inset 3px 0 #1687d9}.profile-icon{display:grid;place-items:center;width:38px;height:38px;border-radius:10px;color:#127abf;background:#e2f2fc}.profile-icon.demo{color:#936000;background:#fff1c8}.profile-icon.local{color:#147453;background:#dff4e9}.profile-copy strong,.profile-copy small{display:block}.profile-copy strong{font-size:14px}.profile-copy small{margin-top:4px;color:#657e92;font-size:12px;line-height:1.45}.profile-option em{padding:4px 8px;border-radius:999px;color:#126847;background:#e0f4e9;font-size:11px;font-style:normal;font-weight:850}.profile-option em.simulated{color:#855700;background:#ffefc6}
.connection-panel{display:flex;flex-direction:column}.connection-visual{display:grid;justify-items:center;padding:18px 10px;text-align:center}.secure-ring{display:grid;place-items:center;width:68px;height:68px;margin-bottom:12px;border:1px solid #9fd0ee;border-radius:50%;color:#0877bc;background:linear-gradient(145deg,#e8f7ff,#fff);box-shadow:0 8px 22px rgba(13,111,177,.12)}.connection-visual strong{font-size:14px}.connection-visual p{margin:8px 0;color:#607a8f;font-size:12px;line-height:1.6}.connection-panel ul{display:grid;gap:8px;margin:17px 0 0;padding:0;list-style:none;color:#587187;font-size:12px}.connection-panel li{padding-left:18px;position:relative}.connection-panel li:before{content:'✓';position:absolute;left:0;color:#16845a;font-weight:900}
.connection-panel-action{width:100%;margin-top:12px}
@media(max-width:860px){.settings-page{padding:20px 16px}.settings-hero{align-items:flex-start;flex-direction:column}.settings-grid{grid-template-columns:1fr}.primary-action{width:100%}}
@media(max-height:820px) and (min-width:861px){.settings-page{padding-block:22px}.settings-hero{margin-bottom:16px}.panel{padding:17px}.profile-option{padding:10px}.connection-visual{padding:10px}}
@media(prefers-reduced-motion:reduce){.profile-option{transition:none}}
</style>
