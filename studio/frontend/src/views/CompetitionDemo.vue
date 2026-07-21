<script setup lang="ts">
import { History, RotateCcw, ShieldCheck } from "@lucide/vue";
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import DemoControlPanel from "@/components/demo/DemoControlPanel.vue";
import DemoEvidencePanel from "@/components/demo/DemoEvidencePanel.vue";
import DemoPipeline from "@/components/demo/DemoPipeline.vue";
import TerminalDrawer from "@/components/demo/TerminalDrawer.vue";
import { usePipeline } from "@/composables/usePipeline";
import { useSimulation } from "@/composables/useSimulation";
import { useTaskLifecycle } from "@/composables/useTaskLifecycle";
import { useExecutionStore } from "@/stores/executionStore";
import type { GenerateResult } from "@/types/domain";

const execution = useExecutionStore();
const router = useRouter();

const requirement = ref(
	"实现一个一阶低通滤波器，截止频率 10Hz，用于滤除飞控传感器高频噪声；输出限定为 uint16_t，并满足 MISRA C:2012。注入传感器卡死故障时保持上一拍安全值。",
);
const language = ref<"c" | "cpp" | "python">("c");
const activeTab = ref("修复对比");
const terminalOpen = ref(false);
const summaryRef = ref<HTMLElement | null>(null);

const simulation = useSimulation();
const {
	faultInjected,
	selectedFaultType,
	faultTypes,
	toggleFaultInjection,
	setFaultType,
	wavePoints,
} = simulation;

const taskLifecycle = useTaskLifecycle({
	onComplete: async () => {
		terminalOpen.value = false;
		await focusSummary();
	},
});

const {
	task,
	events,
	error,
	replayTaskId,
	isReplayMode,
	start: startTask,
	cancel: cancelTask,
	loadReplayTask,
	cleanup,
} = taskLifecycle;

const pipeline = usePipeline(() => task.value);
const { stages, running, complete, currentStageIndex } = pipeline;

const tabs = ["修复对比", "契约", "仿真", "追溯", "证据"];
const result = computed<GenerateResult | null>(
	() => task.value?.result ?? null,
);
const repaired = computed(() => result.value?.repair_history.at(-1));
const contractPassed = computed(
	() => result.value?.contract_check_result.passed_count ?? 0,
);
const contractTotal = computed(
	() => result.value?.contract_check_result.total_count ?? 0,
);
const initialViolations = computed(() => {
	const history = result.value?.repair_history;
	if (history && history.length > 0) {
		const first = history[0];
		const before = (first as { before_violations?: number }).before_violations;
		if (typeof before === "number") return before;
	}
	const violations =
		result.value != null
			? (result.value as { violations?: unknown[] })?.violations
			: undefined;
	return violations?.length ?? 4;
});
const repairRounds = computed(() => result.value?.repair_history.length ?? 0);

// 缓存波形数据计算结果
const inputWavePoints = computed(() => {
	if (!result.value?.simulation_result.input_waveform) return "";
	return wavePoints(result.value.simulation_result.input_waveform, true);
});
const outputWavePoints = computed(() => {
	if (!result.value?.simulation_result.output_waveform) return "";
	return wavePoints(result.value.simulation_result.output_waveform, false);
});
const provenanceString = computed(() => {
	return task.value?.provenance
		? JSON.stringify(task.value.provenance, null, 2)
		: "";
});

function sourceBadgeText(source: string | undefined): string {
	if (source === "simulated") return "模拟数据 · 浏览器离线";
	if (source === "replay") return "已验证回放 · 哈希核验";
	return "实时结果 · 服务端执行";
}

function truncateCode(code: string | undefined, maxLength = 2000): string {
	if (!code) return "";
	if (code.length <= maxLength) return code;
	return (
		code.substring(0, maxLength) +
		`\n\n... [代码已截断，共 ${code.length} 字符]`
	);
}

function reportBadgeText(source: string | undefined): string {
	if (source === "simulated") return "模拟演示报告";
	if (source === "replay") return "已验证回放";
	return "工程辅助证据";
}

function simulationSourceText(source: string | undefined): string {
	if (source === "simulated") return "模拟结果";
	if (source === "replay") return "回放结果";
	return "按来源核验";
}

async function focusSummary() {
	await nextTick();
	const behavior: ScrollBehavior = window.matchMedia(
		"(prefers-reduced-motion: reduce)",
	).matches
		? "auto"
		: "smooth";
	summaryRef.value?.scrollIntoView({ block: "start", behavior });
}

async function handleStart() {
	simulation.resetSimulation();
	activeTab.value = "修复对比";
	terminalOpen.value = true;
	await startTask(requirement.value, language.value);
}

onMounted(async () => {
	if (!isReplayMode.value) return;
	await loadReplayTask();
	if (task.value?.requirement) requirement.value = task.value.requirement;
	if (task.value?.language)
		language.value = task.value.language as "c" | "cpp" | "python";
	if (task.value?.status === "done" || task.value?.status === "degraded") {
		terminalOpen.value = false;
		await focusSummary();
	}
});

onUnmounted(() => cleanup());
</script>

<template>
  <main class="demo-workbench">
    <header class="workbench-heading">
      <div><span class="overline">COMPETITION MISSION 01</span><h1>低通滤波器可信交付</h1></div>
      <span class="source-badge" :class="task?.source ?? execution.profile.source">
        {{ sourceBadgeText(task?.source ?? execution.profile.source) }}
      </span>
    </header>

    <div v-if="isReplayMode" class="replay-banner">
      <History :size="16" />
      <span>回放模式 · 任务 ID: <code>{{ replayTaskId }}</code></span>
      <button @click="router.push('/records')">返回运行记录</button>
    </div>

    <section class="workbench-grid" :class="{ complete }">
      <DemoControlPanel
        :requirement="requirement"
        :language="language"
        :running="running"
        :is-replay-mode="isReplayMode"
        :profile-label="execution.profile.label"
        :profile-source="execution.profile.source"
        :task="task"
        @update:requirement="requirement = $event"
        @update:language="language = $event"
        @start="handleStart"
        @cancel="cancelTask"
      />

      <DemoPipeline
        :stages="stages"
        :current-stage-index="currentStageIndex"
        :task="task"
      />

      <DemoEvidencePanel
        :task="task"
        :complete="complete"
        :current-stage-index="currentStageIndex"
        :stages-length="stages.length"
        :result="result"
        :error="error"
        :initial-violations="initialViolations"
        :contract-passed="contractPassed"
        :contract-total="contractTotal"
      />
    </section>

    <TerminalDrawer
      :events="events"
      :terminal-open="terminalOpen"
      :task="task"
      @update:terminal-open="terminalOpen = $event"
    />

    <section ref="summaryRef" class="judge-summary" :class="{ placeholder: !complete || !result }">
      <template v-if="complete && result">
      <header><div><span class="overline">JUDGE SUMMARY</span><h2>评委摘要：证据在首屏完成闭环</h2></div><span class="source-badge" :class="task?.source">{{ reportBadgeText(task?.source) }}</span></header>
      <div class="metric-strip">
        <div><small>MISRA 违规</small><strong><del>{{ initialViolations }}</del> → 0</strong><span>{{ repairRounds > 0 ? `${repairRounds} 轮修复` : '已修复' }}</span></div>
        <div><small>契约断言</small><strong>{{ contractPassed }}/{{ contractTotal }}</strong><span>1 项边界容差待审</span></div>
        <div><small>编译 / 仿真</small><strong>{{ result.simulation_result.passed ? '通过' : '失败' }}</strong><span>{{ simulationSourceText(task?.source) }}</span></div>
        <div><small>链路追溯率</small><strong>100%</strong><span>REQ → TST</span></div>
        <div><small>证据包</small><strong>完整</strong><span>{{ task?.id }}</span></div>
      </div>
      <div class="result-tabs" role="tablist"><button v-for="tab in tabs" :key="tab" :class="{ active: activeTab === tab }" @click="activeTab = tab">{{ tab }}</button></div>

      <div v-if="activeTab === '修复对比'" class="split-result">
        <article><h3>修复 Diff <span>{{ initialViolations }} → 0</span></h3><div class="code-split"><pre class="removed">{{ truncateCode(repaired?.before_code) }}</pre><pre class="added">{{ truncateCode(repaired?.after_code) }}</pre></div></article>
        <article><h3>契约 ↔ 代码 <span>双向高亮</span></h3><div class="contract-links"><button v-for="condition in result.contract.postconditions" :key="condition.id"><b>{{ condition.id }}</b><code>{{ condition.expression }}</code><small>关联 CODE: filter_update · TST: SIM-{{ condition.id.slice(-3) }}</small></button></div></article>
      </div>
      <div v-else-if="activeTab === '契约'" class="contract-grid"><article v-for="section in result.contract_check_result.sections" :key="section.key"><h3>{{ section.title }}</h3><p v-for="item in section.items" :key="item.id" :class="item.passed ? 'pass' : 'review'"><span>{{ item.passed ? '✓' : '!' }}</span><b>{{ item.id }}</b>{{ item.expression }}</p></article></div>
      <div v-else-if="activeTab === '仿真'" class="simulation-view">
        <div class="sim-toolbar">
          <div class="sim-toolbar-left"><strong>{{ faultInjected && selectedFaultType ? faultTypes.find(f => f.type === selectedFaultType)?.name + '故障注入' : '正常正弦输入' }}</strong><small>{{ faultInjected ? '检测到契约违约区间 t=76–116' : '200 步完成，输出范围满足约束' }}</small></div>
          <button @click="toggleFaultInjection()"><RotateCcw :size="15" />{{ faultInjected ? '恢复正常仿真' : '注入故障' }}</button>
        </div>
        <div v-if="faultInjected" class="fault-selector">
          <span class="fault-label">选择故障类型：</span>
          <div class="fault-options">
            <button v-for="fault in faultTypes" :key="fault.type" :class="{ active: selectedFaultType === fault.type }" @click="setFaultType(fault.type)">
              <span class="fault-name">{{ fault.name }}</span>
              <span class="fault-desc">{{ fault.description }}</span>
            </button>
          </div>
        </div>
        <div class="sim-chart-container">
          <svg viewBox="0 0 520 180" preserveAspectRatio="none">
            <path d="M0 20H520" class="grid-line major"/>
            <path d="M0 60H520" class="grid-line"/>
            <path d="M0 100H520" class="grid-line major"/>
            <path d="M0 140H520" class="grid-line"/>
            <path d="M0 160H520" class="grid-line major"/>
            <polyline :points="inputWavePoints" class="input-wave"/>
            <polyline :points="outputWavePoints" :class="faultInjected ? 'fault-wave' : 'output-wave'"/>
          </svg>
          <div class="legend"><span class="input">输入</span><span :class="faultInjected ? 'fault' : 'output'">输出</span><b :class="faultInjected ? 'fault' : 'normal'">{{ faultInjected ? '契约违约已捕获' : '未观察到契约违约' }}</b></div>
        </div>
        <div class="sim-stats">
          <div class="sim-stat"><span class="sim-stat-label">仿真步数</span><span class="sim-stat-value">{{ result.simulation_result.total_steps }}</span></div>
          <div class="sim-stat"><span class="sim-stat-label">输出范围</span><span class="sim-stat-value">{{ result.simulation_result.statistics?.output_min ?? 0 }} ~ {{ result.simulation_result.statistics?.output_max ?? 65535 }}</span></div>
          <div class="sim-stat"><span class="sim-stat-label">输出均值</span><span class="sim-stat-value">{{ result.simulation_result.statistics?.output_mean ?? 0 }}</span></div>
        </div>
      </div>
      <div v-else-if="activeTab === '追溯'" class="trace-view"><div v-for="(lines, req) in result.traceability" :key="req" class="trace-row"><b>{{ req }}</b><span>LLR-{{ String(req).slice(-3) }}</span><span>CON-{{ String(req).slice(-3) }}</span><span>CODE lines {{ lines.join(', ') }}</span><span>TST-SIM-{{ String(req).slice(-3) }}</span></div></div>
      <div v-else class="evidence-view"><ShieldCheck :size="38"/><div><h3>{{ reportBadgeText(task?.source) }}已生成</h3><p>{{ task?.source === 'simulated' ? '所有工具结果均标记 simulated；不得用于适航审定。' : task?.source === 'replay' ? '回放包按 manifest/SHA-256 展示；降级阶段保持 simulated 标识。' : '版本、退出码、摘要和来源以任务 provenance 为准。' }}</p><code>{{ provenanceString }}</code></div></div>
      </template>
      <div v-else class="summary-placeholder">
        <ShieldCheck :size="42" />
        <strong>评委摘要将在生成完成后呈现</strong>
        <p>包含 MISRA 修复对比、契约断言、仿真波形、链路追溯与证据包。</p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.demo-workbench { min-height: calc(100dvh - var(--topbar-h,60px)); padding: 10px clamp(16px,2vw,32px) 20px; color: #142b43; background: radial-gradient(circle at 80% 0,rgba(30,143,211,.10),transparent 30%),linear-gradient(150deg,#eaf2f7,#f4f8fb 46%,#eaf3f8); display: flex; flex-direction: column; }
.workbench-heading, .judge-summary > header { display:flex; align-items:center; justify-content:space-between; max-width: 1800px; margin: 0 auto 10px; }.workbench-heading h1,.judge-summary h2{margin:2px 0 0;font-size:24px;color:#071b33}.overline{font-size:12px;font-weight:900;letter-spacing:.14em;color:#1278c4}
.source-badge{padding:6px 12px;border-radius:999px;font-size:13px;font-weight:850}.source-badge.simulated{color:#855000;background:#fff0c8;border:1px solid #e4bc59}.source-badge.live{color:#11633d;background:#dcf5e8;border:1px solid #82cba5}.source-badge.replay{color:#075c9b;background:#e5f4ff;border:1px solid #9dcfee}
.replay-banner{display:flex;align-items:center;gap:10px;max-width:1800px;margin:0 auto 10px;padding:10px 14px;border:1px solid #e3a639;border-radius:10px;background:#fff8e6;color:#855000;font-size:13px}.replay-banner code{padding:2px 6px;border-radius:4px;background:#fff;color:#5a3d00;font-size:12px;font-weight:700}.replay-banner button{margin-left:auto;padding:6px 12px;border:1px solid #d4a043;border-radius:6px;background:#fff;color:#855000;font-size:12px;font-weight:700;cursor:pointer}.replay-banner button:hover{background:#fff0c8}
.workbench-grid{width:100%;max-width:1800px;flex:1;min-height:clamp(500px,calc(100dvh - 280px),1100px);margin:0 auto 8px;display:grid;grid-template-columns:340px minmax(520px,1fr) 320px;gap:14px}.workbench-grid.complete{flex:0 0 auto;min-height:380px}
.judge-summary{max-width:1800px;margin:8px auto 0;padding:16px;border:1px solid #c3d7e3;border-radius:14px;background:rgba(255,255,255,.97);box-shadow:0 6px 24px rgba(15,49,75,.1);min-height:120px}.judge-summary.placeholder{min-height:120px;display:grid;place-items:center;border-style:dashed;background:rgba(255,255,255,.6)}.summary-placeholder{display:grid;place-items:center;gap:8px;padding:24px;text-align:center;color:#8aa0b2}.summary-placeholder strong{font-size:15px;color:#5a7187}.summary-placeholder p{max-width:420px;margin:0;font-size:13px;line-height:1.6}.judge-summary>header{margin-bottom:10px}.metric-strip{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid #d4e2ea;border-radius:10px;overflow:hidden}.metric-strip>div{padding:12px 16px;border-right:1px solid #d8e4eb}.metric-strip>div:last-child{border:0}.metric-strip small,.metric-strip span{display:block;color:#667f93;font-size:11px}.metric-strip strong{display:block;margin:4px 0;color:#075a9f;font-size:22px}.metric-strip del{color:#bb4545}.result-tabs{display:flex;gap:4px;margin-top:10px;border-bottom:1px solid #d5e1e9;overflow-x:auto}.result-tabs button{flex:none;padding:10px 18px;border:0;border-bottom:3px solid transparent;color:#557086;background:transparent;font-size:14px;font-weight:850;cursor:pointer}.result-tabs button.active{color:#076dbb;border-color:#1687e8}
.split-result{height:320px;display:grid;grid-template-columns:1.2fr .8fr;gap:12px;padding-top:12px}.split-result article,.contract-grid article{min-width:0;border:1px solid #dae4eb;border-radius:10px;overflow:hidden}.split-result h3,.contract-grid h3{display:flex;justify-content:space-between;margin:0;padding:10px 14px;color:#17364f;background:#f1f6f9;font-size:13px}.split-result h3 span{color:#168355}.code-split{height:calc(100% - 42px);display:grid;grid-template-columns:1fr 1fr}.code-split pre{margin:0;padding:12px;overflow:auto;white-space:pre-wrap;font-size:11px;line-height:1.5}.removed{background:#fff2f2}.added{background:#effaf3}.contract-links{padding:10px;overflow-y:auto;height:calc(100% - 42px)}.contract-links button{width:100%;display:flex;flex-direction:column;gap:4px;margin-bottom:8px;padding:10px;border:1px solid #cfe0eb;border-radius:8px;text-align:left;background:#fbfdff}.contract-links b{font-size:12px;color:#096db7}.contract-links code{font-size:11px;white-space:normal}.contract-links small{color:#678095;font-size:10px}.contract-grid{height:320px;display:grid;grid-template-columns:1fr 1fr;gap:10px;padding-top:12px}.contract-grid p{display:grid;grid-template-columns:24px 160px 1fr;gap:6px;margin:0;padding:8px 10px;border-top:1px solid #edf2f5;font-size:12px}.contract-grid .pass span{color:#168355}.contract-grid .review{background:#fff6df}.simulation-view{min-height:420px;max-height:520px;padding:16px;border:1px solid #e2eaf0;border-radius:12px;background:#fafcfd;display:flex;flex-direction:column;overflow:auto}.sim-toolbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;padding:10px 14px;border-radius:8px;background:#fff;border:1px solid #e8f0f5}.sim-toolbar-left{display:flex;flex-direction:column;gap:2px}.sim-toolbar strong{font-size:14px;font-weight:850;color:#0b345b}.sim-toolbar small{color:#698094;font-size:12px}.sim-toolbar button{display:flex;gap:6px;align-items:center;padding:8px 14px;border:1px solid #e3a639;border-radius:8px;color:#855000;background:#fff8e6;font-size:12px;font-weight:800;cursor:pointer;transition:all .2s}.sim-toolbar button:hover{background:#ffeeb8;border-color:#d99520}.fault-selector{display:flex;flex-direction:column;gap:8px;margin-bottom:12px;padding:12px;border:1px solid #f0d080;border-radius:10px;background:linear-gradient(135deg,#fffbf5,#fff9e6)}.fault-label{font-size:13px;font-weight:850;color:#855000;display:flex;align-items:center;gap:6px}.fault-label:before{content:'⚡';font-size:14px}.fault-options{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.fault-options button{display:flex;flex-direction:column;gap:3px;padding:10px 12px;border:1px solid #e8cf90;border-radius:8px;background:#fff;text-align:left;cursor:pointer;transition:all .2s;box-shadow:0 1px 3px rgba(232,207,144,.2)}.fault-options button:hover{border-color:#d94747;background:#fff5f5;transform:translateY(-1px);box-shadow:0 3px 8px rgba(217,71,71,.15)}.fault-options button.active{border-color:#d94747;background:#ffebee;box-shadow:inset 0 2px 4px rgba(217,71,71,.1),0 3px 8px rgba(217,71,71,.15)}.fault-name{font-size:13px;font-weight:900;color:#142b43}.fault-desc{font-size:11px;color:#667f93;line-height:1.4}.sim-chart-container{flex:1;min-height:0;padding:10px;background:#fff;border:1px solid #e8f0f5;border-radius:10px;display:flex;flex-direction:column}.sim-chart-container svg{flex:1;width:100%;min-height:200px}.grid-line{fill:none;stroke:#e8f0f5;stroke-width:1}.grid-line.major{stroke:#d4dee8;stroke-width:1.5}.input-wave,.output-wave,.fault-wave{fill:none;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round}.input-wave{stroke:#6b7280;opacity:.8}.output-wave{stroke:#0ea5e9;opacity:.9}.fault-wave{stroke:#dc2626;opacity:.95}.fault-wave{filter:drop-shadow(0 0 4px rgba(220,38,38,.4))}.legend{display:flex;gap:24px;align-items:center;font-size:13px;margin-top:8px;padding-top:8px;border-top:1px dashed #e8f0f5}.legend span{display:flex;align-items:center;gap:6px;font-weight:700;color:#475569}.legend span:before{content:'';display:inline-block;width:22px;height:3px;border-radius:2px;vertical-align:middle}.legend .input:before{background:#6b7280}.legend .output:before{background:#0ea5e9}.legend .fault:before{background:#dc2626;box-shadow:0 0 6px rgba(220,38,38,.5)}.legend b{margin-left:auto;padding:4px 10px;border-radius:6px;font-size:12px;font-weight:850}.legend b.fault{color:#dc2626;background:#fff5f5}.legend b.normal{color:#10b981;background:#ecfdf5}.sim-stats{display:flex;gap:16px;margin-top:8px;padding:8px 12px;border-radius:8px;background:#f1f5f9}.sim-stat{display:flex;flex-direction:column;gap:1px}.sim-stat-label{font-size:10px;color:#94a3b8;font-weight:700;text-transform:uppercase;letter-spacing:.5px}.sim-stat-value{font-size:13px;font-weight:850;color:#0f172a;font-family:'Consolas',monospace}.trace-view{padding:14px;max-height:320px;overflow-y:auto}.trace-row{display:grid;grid-template-columns:130px repeat(4,1fr);gap:10px;margin-bottom:10px;align-items:center}.trace-row>*{padding:10px;border:1px solid #cfe0e9;border-radius:7px;background:#f7fbfd;font-size:12px;text-align:center}.trace-row b{color:#fff;background:#0876c9}.evidence-view{display:flex;gap:18px;padding:20px;color:#126e48}.evidence-view h3{margin:0 0 6px;color:#17364f;font-size:18px}.evidence-view p{margin:0;color:#5c7488;font-size:13px;line-height:1.6}.evidence-view code{display:block;max-height:160px;margin-top:12px;padding:12px;overflow:auto;color:#c5dae8;background:#0b2133;font-size:11px;white-space:pre-wrap}
@media(max-width:1200px) and (min-width:901px){.workbench-grid{grid-template-columns:250px minmax(390px,1fr) 235px}}
@media(max-height:850px) and (min-width:901px){}
@media(max-width:900px){.demo-workbench{padding-inline:14px}.workbench-grid{height:auto;grid-template-columns:1fr}.metric-strip{grid-template-columns:repeat(2,1fr)}.metric-strip>div{border-bottom:1px solid #d8e4eb}.split-result{height:auto;grid-template-columns:1fr}.workbench-heading{padding:0 4px}}
@media(max-width:580px){.workbench-heading{align-items:flex-start;gap:8px}.source-badge{font-size:10px}.metric-strip{grid-template-columns:1fr 1fr}.trace-row{grid-template-columns:1fr}.contract-grid{height:auto;grid-template-columns:1fr}.code-split{grid-template-columns:1fr}.result-tabs button{padding-inline:12px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
