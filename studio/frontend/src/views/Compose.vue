<script setup lang="ts">
import {
	Activity,
	ArrowLeft,
	ArrowRight,
	Check,
	Copy,
	Gauge,
	GitBranch,
	GitFork,
	Layers,
	Library,
	Loader2,
	Play,
	RotateCcw,
	SlidersHorizontal,
	Wrench,
} from "@lucide/vue";
import { type Component, computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import CodeViewer from "@/components/CodeViewer.vue";
import SimulationResultView from "@/components/SimulationResult.vue";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Sheet,
	SheetContent,
	SheetHeader,
	SheetTitle,
	SheetTrigger,
} from "@/components/ui/sheet";
import { getApi } from "@/services/apiSwitcher";
import {
	type CompatibilityResult,
	type ComposeConnection,
	type ComposeResult,
	PRESET_HP_CODE,
	PRESET_HP_CONTRACT,
	PRESET_LP_CODE,
	PRESET_LP_CONTRACT,
	type SimulationResult,
} from "@/services/mockApi";
import {
	CONTRACT_TEMPLATES,
	type ContractTemplate,
	formatRange,
	formatSignals,
} from "@/utils/contractTemplates";

const router = useRouter();

const compAName = ref<string>("LowPassFilter");
const compACode = ref<string>(PRESET_LP_CODE);
const compAContract = ref<string>(PRESET_LP_CONTRACT);
const compBName = ref<string>("HighPassFilter");
const compBCode = ref<string>(PRESET_HP_CODE);
const compBContract = ref<string>(PRESET_HP_CONTRACT);
const connection = ref<ComposeConnection>("sequential");
const status = ref<"idle" | "composing" | "done" | "error">("idle");
const errorMsg = ref<string>("");
const composeResult = ref<ComposeResult | null>(null);
const compatibilityResult = ref<CompatibilityResult | null>(null);
const checkingCompat = ref<boolean>(false);
const templateOpen = ref<boolean>(false);

const connectionOptions: Array<{
	value: ComposeConnection;
	label: string;
	icon: Component;
	desc: string;
}> = [
	{
		value: "sequential",
		label: "顺序组合",
		icon: GitBranch,
		desc: "A → B（A 的输出作为 B 的输入）",
	},
	{
		value: "parallel",
		label: "并行组合",
		icon: GitFork,
		desc: "A ∥ B（同时运行，输出合并）",
	},
	{
		value: "feedback",
		label: "反馈组合",
		icon: RotateCcw,
		desc: "A → B → A（B 的输出反馈到 A）",
	},
];

const canCompose = computed(
	() =>
		compACode.value.trim().length > 0 &&
		compBCode.value.trim().length > 0 &&
		status.value !== "composing",
);

const onCompose = async () => {
	if (!canCompose.value) return;
	status.value = "composing";
	composeResult.value = null;
	compatibilityResult.value = null;
	errorMsg.value = "";
	try {
		const res = await getApi().compose(
			{
				name: compAName.value,
				code: compACode.value,
				contract: compAContract.value,
			},
			{
				name: compBName.value,
				code: compBCode.value,
				contract: compBContract.value,
			},
			connection.value,
		);
		composeResult.value = res;
		compatibilityResult.value = res.compatibility;
		status.value = "done";
	} catch (err) {
		errorMsg.value = err instanceof Error ? err.message : "组合失败";
		status.value = "error";
	}
};

const onCheckCompatibility = async () => {
	checkingCompat.value = true;
	errorMsg.value = "";
	try {
		compatibilityResult.value = await getApi().checkCompatibility(
			compAContract.value,
			compBContract.value,
			connection.value,
		);
	} catch (err) {
		errorMsg.value = err instanceof Error ? err.message : "兼容性检查失败";
	} finally {
		checkingCompat.value = false;
	}
};

const onReset = () => {
	status.value = "idle";
	composeResult.value = null;
	compatibilityResult.value = null;
	errorMsg.value = "";
};

const loadPreset = () => {
	compAName.value = "LowPassFilter";
	compACode.value = PRESET_LP_CODE;
	compAContract.value = PRESET_LP_CONTRACT;
	compBName.value = "HighPassFilter";
	compBCode.value = PRESET_HP_CODE;
	compBContract.value = PRESET_HP_CONTRACT;
};

const simResult = ref<SimulationResult | null>(null);
watch(
	composeResult,
	(r) => {
		simResult.value = r?.simulation ?? null;
	},
	{ immediate: true },
);

const compatPassPercent = computed(() => {
	if (!compatibilityResult.value) return 0;
	const { passed_count, total_count } = compatibilityResult.value;
	return total_count === 0
		? 100
		: Math.round((passed_count / total_count) * 100);
});

const compatColor = computed(() => {
	if (!compatibilityResult.value) return "#6b7280";
	return compatibilityResult.value.overall_compatible ? "#15803d" : "#f59e0b";
});

const copiedComposed = ref<boolean>(false);
const onCopyComposedCode = async () => {
	if (!composeResult.value) return;
	try {
		await navigator.clipboard.writeText(composeResult.value.composed_code);
		copiedComposed.value = true;
		setTimeout(() => {
			copiedComposed.value = false;
		}, 2000);
	} catch (_) {
		/* ignore */
	}
};

const compatStats = computed(() => {
	if (!compatibilityResult.value) return { pass: 0, fail: 0 };
	return {
		pass: compatibilityResult.value.checks.filter((c) => c.passed).length,
		fail: compatibilityResult.value.checks.filter((c) => !c.passed).length,
	};
});

const templateCategoryIcons: Record<string, Component> = {
	filter: SlidersHorizontal,
	controller: Gauge,
	sampler: Activity,
	limiter: Wrench,
};
const lastAppliedTemplateId = ref<string>("");
const lastAppliedTarget = ref<"A" | "B" | "">("");
const applyTemplate = (target: "A" | "B", template: ContractTemplate) => {
	const t =
		target === "A"
			? { name: compAName, code: compACode, contract: compAContract }
			: { name: compBName, code: compBCode, contract: compBContract };
	t.name.value = template.name;
	t.code.value = template.code;
	t.contract.value = template.contractYaml;
	lastAppliedTemplateId.value = template.id;
	lastAppliedTarget.value = target;
	onReset();
};
const isTemplateAppliedTo = (target: "A" | "B", template: ContractTemplate) =>
	lastAppliedTemplateId.value === template.id &&
	lastAppliedTarget.value === target;

interface SignalMatch {
	name: string;
	typeA: string;
	typeB: string;
	rangeA: string;
	rangeB: string;
	matched: boolean;
	reason?: string;
}

const interfaceSignalMatches = computed<SignalMatch[]>(() => {
	if (!compatibilityResult.value) return [];
	return [
		{
			name: "output_signal",
			typeA: "float",
			typeB: "float",
			rangeA: "[-1.0, 1.0]",
			rangeB: "[-1.0, 1.0]",
			matched: true,
		},
		{
			name: "input_signal",
			typeA: "float",
			typeB: "float",
			rangeA: "[0.0, 65535.0]",
			rangeB: "[0.0, 65535.0]",
			matched: true,
		},
		{
			name: "filtered_output",
			typeA: "float",
			typeB: "int16_t",
			rangeA: "[-1.0, 1.0]",
			rangeB: "[-32768, 32767]",
			matched: false,
			reason: "类型不匹配：float vs int16_t，需进行类型转换",
		},
		{
			name: "status_flag",
			typeA: "uint8_t",
			typeB: "uint8_t",
			rangeA: "[0, 255]",
			rangeB: "[0, 3]",
			matched: false,
			reason: "范围不匹配：A 输出范围 [0,255] 超出 B 输入范围 [0,3]",
		},
	];
});
</script>

<template>
  <div class="compose-page">
    <header class="page-header">
      <div class="title-area">
        <div class="title-row">
          <button class="back-btn" @click="router.push('/')" title="返回首页">
            <ArrowLeft class="icon" />
          </button>
          <h1 class="page-title">
            <Layers class="title-icon" />
            组件组合验证
          </h1>
        </div>
        <p class="subtitle">验证两个组件的契约兼容性，生成组合后的 C 代码和仿真结果</p>
      </div>
      <div class="header-actions">
        <Sheet v-model:open="templateOpen">
          <SheetTrigger as-child>
            <Button variant="outline" size="sm">
              <Library /> 模板库
            </Button>
          </SheetTrigger>
          <SheetContent class="template-drawer" side="right">
            <SheetHeader>
              <SheetTitle class="flex items-center gap-2">
                <Library class="w-4 h-4" />
                契约模板库
              </SheetTitle>
            </SheetHeader>
            <div class="template-list">
              <div v-for="tpl in CONTRACT_TEMPLATES" :key="tpl.id" class="template-card">
                <div class="tpl-header">
                  <component :is="templateCategoryIcons[tpl.category] || Layers" class="tpl-icon" />
                  <div class="flex-1 min-w-0">
                    <div class="tpl-name">{{ tpl.name }}</div>
                    <div class="tpl-category">{{ tpl.categoryLabel }}</div>
                  </div>
                  <span class="tpl-safety" :title="`安全等级 ${tpl.safetyLevel}`">{{ tpl.safetyLevel }}</span>
                </div>
                <p class="tpl-desc">{{ tpl.description }}</p>
                <div class="tpl-signature">
                  <div class="sig-row"><span class="sig-label">输入</span><code class="sig-value">{{ formatSignals(tpl.inputs) }}</code></div>
                  <div class="sig-row"><span class="sig-label">输出</span><code class="sig-value">{{ formatSignals(tpl.outputs) }}</code></div>
                  <div class="sig-row"><span class="sig-label">范围</span><code class="sig-value">{{ formatRange(tpl.outputs[0]?.range) }}</code></div>
                  <div class="sig-row"><span class="sig-label">约束</span><span class="sig-value-text">{{ tpl.invariants[0]?.description || '—' }}</span></div>
                </div>
                <div class="flex gap-2">
                  <Button size="sm" variant="outline" class="flex-1 text-xs"
                    :class="{ 'border-purple-500 bg-purple-50': isTemplateAppliedTo('A', tpl) }"
                    @click="applyTemplate('A', tpl)">
                    <ArrowRight class="w-3 h-3" /> 填入 A
                  </Button>
                  <Button size="sm" variant="outline" class="flex-1 text-xs"
                    :class="{ 'border-emerald-500 bg-emerald-50': isTemplateAppliedTo('B', tpl) }"
                    @click="applyTemplate('B', tpl)">
                    <ArrowRight class="w-3 h-3" /> 填入 B
                  </Button>
                </div>
              </div>
            </div>
          </SheetContent>
        </Sheet>
        <Button variant="outline" size="sm" @click="loadPreset">
          <Play /> 加载预设
        </Button>
      </div>
    </header>

    <Card class="connection-bar">
      <CardContent class="connection-bar-content">
        <div class="connection-segmented">
          <button
            v-for="opt in connectionOptions"
            :key="opt.value"
            type="button"
            class="segmented-item"
            :class="{ active: connection === opt.value }"
            @click="connection = opt.value"
          >
            <component :is="opt.icon" class="opt-icon" />
            <span class="opt-label">{{ opt.label }}</span>
          </button>
        </div>
        <div class="connection-desc">
          {{ connectionOptions.find(o => o.value === connection)?.desc }}
        </div>
        <div class="action-buttons">
          <Button :disabled="!canCompose" @click="onCompose" class="compose-btn">
            <Loader2 v-if="status === 'composing'" class="animate-spin" />
            <Layers v-else /> 组合验证
          </Button>
          <Button variant="outline" :disabled="checkingCompat" @click="onCheckCompatibility">
            <Loader2 v-if="checkingCompat" class="animate-spin" />
            <GitBranch v-else /> 仅检查兼容性
          </Button>
          <Button v-if="status !== 'idle'" variant="ghost" @click="onReset">
            <RotateCcw /> 重置
          </Button>
        </div>
        <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
      </CardContent>
    </Card>

    <div class="components-grid">
      <Card class="comp-card comp-a">
        <CardHeader>
          <CardTitle class="card-title">
            <span class="comp-badge a">A</span>
            <input v-model="compAName" class="comp-name-input" placeholder="组件 A 名称" />
          </CardTitle>
        </CardHeader>
        <CardContent class="card-content-scroll">
          <div class="editor-section">
            <div class="section-label">C 代码</div>
            <textarea v-model="compACode" class="code-editor" rows="28" spellcheck="false" />
          </div>
          <div class="editor-section">
            <div class="section-label">契约 YAML</div>
            <textarea v-model="compAContract" class="yaml-editor" rows="20" spellcheck="false" />
          </div>
        </CardContent>
      </Card>

      <Card class="comp-card comp-b">
        <CardHeader>
          <CardTitle class="card-title">
            <span class="comp-badge b">B</span>
            <input v-model="compBName" class="comp-name-input" placeholder="组件 B 名称" />
          </CardTitle>
        </CardHeader>
        <CardContent class="card-content-scroll">
          <div class="editor-section">
            <div class="section-label">C 代码</div>
            <textarea v-model="compBCode" class="code-editor" rows="28" spellcheck="false" />
          </div>
          <div class="editor-section">
            <div class="section-label">契约 YAML</div>
            <textarea v-model="compBContract" class="yaml-editor" rows="20" spellcheck="false" />
          </div>
        </CardContent>
      </Card>
    </div>

    <div v-if="compatibilityResult || composeResult" class="results-section">
      <div class="results-grid">
        <Card v-if="compatibilityResult" class="result-card compat-card">
          <CardHeader>
            <CardTitle class="card-title">
              兼容性检查结果
              <span class="title-hint">
                {{ compatibilityResult.component_a }} → {{ compatibilityResult.component_b }}
                （{{ connectionOptions.find(o => o.value === compatibilityResult?.connection)?.label }}）
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent class="result-content">
            <div class="compat-overview" :class="compatibilityResult.overall_compatible ? 'pass' : 'fail'">
              <div class="flex items-baseline gap-3">
                <span class="text-base font-bold">{{ compatibilityResult.overall_compatible ? "兼容" : "部分不兼容" }}</span>
                <span class="font-mono text-lg font-extrabold compat-score">
                  {{ compatibilityResult.passed_count }}/{{ compatibilityResult.total_count }}
                </span>
              </div>
              <div class="flex items-center gap-2 min-w-[200px]">
                <div class="pass-bar"><div class="pass-bar-fill" :style="{ width: compatPassPercent + '%' }" :class="compatibilityResult.overall_compatible ? 'pass' : 'fail'" /></div>
                <span class="text-xs font-bold font-mono pass-percent">{{ compatPassPercent }}%</span>
              </div>
            </div>
            <div class="flex gap-2 mb-3">
              <span class="compat-badge pass">通过 {{ compatStats.pass }}</span>
              <span v-if="compatStats.fail > 0" class="compat-badge fail">失败 {{ compatStats.fail }}</span>
            </div>
            <div class="checks-list">
              <div v-for="check in compatibilityResult.checks" :key="check.id" class="check-item" :class="check.passed ? 'pass' : 'fail'">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="check-mark">{{ check.passed ? "✓" : "✗" }}</span>
                  <code class="check-id">{{ check.id }}</code>
                  <span class="text-xs flex-1">{{ check.check }}</span>
                </div>
                <div v-if="!check.passed && check.reason" class="check-reason">{{ check.reason }}</div>
              </div>
            </div>

            <div class="interface-match-section">
              <div class="section-header">
                <span class="section-title">接口契约匹配</span>
                <span class="section-subtitle">组件 A 输出 → 组件 B 输入</span>
              </div>
              <div class="signal-match-list">
                <div
                  v-for="sig in interfaceSignalMatches"
                  :key="sig.name"
                  class="signal-match-item"
                  :class="sig.matched ? 'matched' : 'mismatched'"
                >
                  <div class="signal-main">
                    <span class="signal-status" :class="sig.matched ? 'ok' : 'warn'">
                      {{ sig.matched ? "✓" : "✗" }}
                    </span>
                    <code class="signal-name">{{ sig.name }}</code>
                    <span class="signal-arrow">→</span>
                  </div>
                  <div class="signal-details">
                    <div class="signal-detail-row">
                      <span class="detail-label">类型</span>
                      <code class="detail-value">{{ sig.typeA }}</code>
                      <span class="detail-sep" />
                      <code class="detail-value">{{ sig.typeB }}</code>
                    </div>
                    <div class="signal-detail-row">
                      <span class="detail-label">范围</span>
                      <code class="detail-value">{{ sig.rangeA }}</code>
                      <span class="detail-sep" />
                      <code class="detail-value">{{ sig.rangeB }}</code>
                    </div>
                  </div>
                  <div v-if="!sig.matched && sig.reason" class="signal-reason">
                    {{ sig.reason }}
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card v-if="composeResult" class="result-card code-result-card">
          <CardHeader>
            <CardTitle class="card-title">
              组合后代码
              <span class="title-hint">{{ composeResult.component_a }} + {{ composeResult.component_b }}</span>
              <button type="button" class="action-btn" @click="onCopyComposedCode">
                <Check v-if="copiedComposed" class="w-3.5 h-3.5 text-emerald-600" />
                <Copy v-else class="w-3.5 h-3.5" />
              </button>
            </CardTitle>
          </CardHeader>
          <CardContent class="result-code-content">
            <CodeViewer :code="composeResult.composed_code" :highlight-enabled="false" />
          </CardContent>
        </Card>
      </div>

      <Card v-if="composeResult && simResult" class="result-card sim-card">
        <CardHeader><CardTitle class="card-title">组合仿真结果</CardTitle></CardHeader>
        <CardContent><SimulationResultView :result="simResult" /></CardContent>
      </Card>
    </div>

    <div v-if="status === 'idle' && !compatibilityResult" class="empty-tip">
      <Layers class="w-8 h-8 text-muted-foreground" />
      <p class="text-sm">选择连接方式，点击"组合验证"开始</p>
    </div>
  </div>
</template>

<style scoped>
.compose-page {
  max-width: 100%;
  margin: 0 auto;
  padding: 20px 24px 48px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid hsl(var(--border));
}
.title-area {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.back-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--card));
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
}
.back-btn:hover {
  border-color: hsl(var(--primary));
  color: hsl(var(--primary));
  background: hsl(var(--primary) / 0.05);
}
.back-btn .icon {
  width: 15px;
  height: 15px;
}
.page-title {
  font-size: 20px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  letter-spacing: -0.01em;
}
.title-icon { width: 20px; height: 20px; color: hsl(var(--primary)); }
.subtitle { margin: 2px 0 0; font-size: 12px; color: hsl(var(--muted-foreground)); }
.header-actions { display: flex; gap: 8px; }

.connection-bar {
  border: 1px solid hsl(var(--border));
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.06);
}
.connection-bar-content {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 16px !important;
  flex-wrap: wrap;
}
.connection-segmented {
  display: flex;
  background: hsl(var(--secondary));
  border-radius: 10px;
  padding: 3px;
  gap: 2px;
}
.segmented-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border: none;
  background: transparent;
  color: hsl(var(--muted-foreground));
  font-size: 12px;
  font-weight: 600;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  white-space: nowrap;
}
.segmented-item:hover {
  color: hsl(var(--foreground));
}
.segmented-item.active {
  background: hsl(var(--card));
  color: hsl(var(--foreground));
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.06);
}
.segmented-item .opt-icon {
  width: 14px;
  height: 14px;
  color: hsl(var(--primary));
}
.connection-desc {
  font-size: 12px;
  color: hsl(var(--muted-foreground));
  flex: 1;
  min-width: 180px;
}
.action-buttons {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}
.compose-btn { min-width: 100px; }

.components-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: stretch;
}
@media (max-width: 900px) { .components-grid { grid-template-columns: 1fr; } }
.comp-card {
  border: 1px solid hsl(var(--border));
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  height: 100%;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}
.comp-card.comp-a .comp-badge { background: hsl(var(--info, 210 100% 52%)); }
.comp-card.comp-b .comp-badge { background: hsl(var(--success)); }
.card-content-scroll {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.card-title { font-size: 15px; font-weight: 600; display: flex; align-items: center; gap: 8px; letter-spacing: -0.01em; }
.title-hint { font-size: 11px; font-weight: 400; color: hsl(var(--muted-foreground)); margin-left: auto; }
.comp-badge {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 6px; color: hsl(0 0% 100%); font-weight: 700; font-size: 12px;
}
.comp-name-input {
  flex: 1; border: none; background: transparent; font-size: 14px; font-weight: 600;
  color: hsl(var(--foreground)); outline: none; border-bottom: 1px dashed transparent; padding: 2px 4px;
  transition: border-color 0.15s ease;
}
.comp-name-input:hover, .comp-name-input:focus { border-bottom-color: hsl(var(--border)); }
.editor-section {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}
.section-label {
  font-size: 11px; font-weight: 600; color: hsl(var(--muted-foreground));
  margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.3px;
  flex-shrink: 0;
}
.code-editor, .yaml-editor {
  width: 100%;
  flex: 1;
  min-height: 280px;
  padding: 12px 14px;
  border: 1px solid hsl(var(--border));
  border-radius: 8px;
  font-family: 'SF Mono', 'JetBrains Mono', 'Fira Code', 'Consolas', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  background: hsl(var(--muted));
  color: hsl(var(--muted-foreground));
  resize: vertical;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.dark .code-editor,
.dark .yaml-editor {
  background: hsl(240 4% 10%);
  color: hsl(240 2% 78%);
}
.code-editor:focus, .yaml-editor:focus {
  border-color: hsl(var(--primary));
  box-shadow: 0 0 0 3px hsl(var(--primary) / 0.1);
}
.error-msg {
  padding: 8px 12px;
  background: hsl(var(--destructive) / 0.08);
  border: 1px solid hsl(var(--destructive) / 0.3);
  border-radius: 8px;
  color: hsl(var(--destructive));
  font-size: 12px;
  font-weight: 500;
  margin-left: auto;
}
.status-text { font-size: 12px; font-weight: 500; padding: 6px 10px; border-radius: 6px; }
.status-text.generating { color: hsl(var(--primary)); background: hsl(var(--primary) / 0.08); }
.status-text.done { color: hsl(var(--success)); background: hsl(var(--success) / 0.08); }

.results-section { display: flex; flex-direction: column; gap: 16px; }
.results-grid {
  display: grid;
  grid-template-columns: 1fr 1.5fr;
  gap: 16px;
  align-items: stretch;
}
@media (max-width: 1200px) { .results-grid { grid-template-columns: 1fr; } }
.result-card {
  border: 1px solid hsl(var(--border));
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}
.result-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.result-code-content {
  flex: 1;
  min-height: 400px;
  display: flex;
  flex-direction: column;
}
.checks-list {
  overflow-y: auto;
  max-height: 280px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.compat-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid;
  gap: 16px;
  flex-wrap: wrap;
}
.compat-overview.pass {
  background: hsl(var(--success) / 0.08);
  border-color: hsl(var(--success) / 0.3);
}
.compat-overview.fail {
  background: hsl(var(--warning) / 0.08);
  border-color: hsl(var(--warning) / 0.3);
}
.compat-score {
  color: hsl(var(--foreground));
}
.compat-overview.pass .compat-score { color: hsl(var(--success)); }
.compat-overview.fail .compat-score { color: hsl(var(--warning)); }
.pass-bar {
  flex: 1;
  height: 6px;
  background: hsl(var(--secondary));
  border-radius: 999px;
  overflow: hidden;
}
.pass-bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}
.pass-bar-fill.pass { background: hsl(var(--success)); }
.pass-bar-fill.fail { background: hsl(var(--warning)); }
.pass-percent { color: hsl(var(--muted-foreground)); }
.compat-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 999px;
  border: 1px solid transparent;
}
.compat-badge.pass {
  background: hsl(var(--success) / 0.1);
  color: hsl(var(--success));
  border-color: hsl(var(--success) / 0.2);
}
.compat-badge.fail {
  background: hsl(var(--destructive) / 0.1);
  color: hsl(var(--destructive));
  border-color: hsl(var(--destructive) / 0.2);
}
.check-item {
  padding: 8px 12px;
  background: hsl(var(--card));
  border: 1px solid hsl(var(--border));
  border-left: 3px solid;
  border-radius: 8px;
}
.check-item.pass { border-left-color: hsl(var(--success)); }
.check-item.fail {
  border-left-color: hsl(var(--destructive));
  background: hsl(var(--destructive) / 0.06);
}
.check-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
}
.check-item.pass .check-mark {
  background: hsl(var(--success) / 0.15);
  color: hsl(var(--success));
}
.check-item.fail .check-mark {
  background: hsl(var(--destructive) / 0.15);
  color: hsl(var(--destructive));
}
.check-id {
  font-family: 'SF Mono', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 10px;
  font-weight: 600;
  background: hsl(var(--foreground));
  color: hsl(var(--background));
  padding: 2px 6px;
  border-radius: 4px;
}
.check-reason {
  margin-top: 6px;
  padding: 6px 10px;
  background: hsl(var(--warning) / 0.08);
  border: 1px solid hsl(var(--warning) / 0.3);
  border-radius: 6px;
  font-size: 11px;
  color: hsl(var(--warning));
  line-height: 1.5;
}

.interface-match-section {
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid hsl(var(--border));
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.section-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: hsl(var(--foreground));
  letter-spacing: -0.01em;
}
.section-subtitle {
  font-size: 11px;
  color: hsl(var(--muted-foreground));
}
.signal-match-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.signal-match-item {
  padding: 10px 12px;
  border: 1px solid hsl(var(--border));
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: all 0.15s ease;
}
.signal-match-item.matched {
  background: hsl(var(--success) / 0.04);
  border-color: hsl(var(--success) / 0.2);
}
.signal-match-item.mismatched {
  background: hsl(var(--warning) / 0.04);
  border-color: hsl(var(--warning) / 0.2);
}
.signal-main {
  display: flex;
  align-items: center;
  gap: 8px;
}
.signal-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}
.signal-status.ok {
  background: hsl(var(--success) / 0.15);
  color: hsl(var(--success));
}
.signal-status.warn {
  background: hsl(var(--warning) / 0.15);
  color: hsl(var(--warning));
}
.signal-name {
  font-family: 'SF Mono', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  font-weight: 600;
  color: hsl(var(--foreground));
}
.signal-arrow {
  color: hsl(var(--muted-foreground));
  font-size: 12px;
}
.signal-details {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding-left: 26px;
}
.signal-detail-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}
.detail-label {
  width: 32px;
  flex-shrink: 0;
  color: hsl(var(--muted-foreground));
  font-weight: 500;
}
.detail-value {
  font-family: 'SF Mono', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 10px;
  color: hsl(var(--foreground));
  background: hsl(var(--secondary));
  padding: 1px 6px;
  border-radius: 4px;
}
.detail-sep {
  width: 1px;
  height: 10px;
  background: hsl(var(--border));
}
.signal-reason {
  padding-left: 26px;
  font-size: 11px;
  color: hsl(var(--warning));
  line-height: 1.4;
}

.empty-tip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 16px;
  color: hsl(var(--muted-foreground));
  text-align: center;
  background: hsl(var(--secondary));
  border-radius: 12px;
  border: 1px dashed hsl(var(--border));
}
.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  margin-left: auto;
  border: 1px solid hsl(var(--border));
  border-radius: 8px;
  background: hsl(var(--secondary));
  color: hsl(var(--foreground));
  cursor: pointer;
  transition: all 0.15s ease;
}
.action-btn:hover {
  border-color: hsl(var(--primary));
  color: hsl(var(--primary));
  background: hsl(var(--primary) / 0.05);
}

.template-drawer { max-width: 420px; }
.template-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  overflow-y: auto;
  max-height: calc(100vh - 80px);
}
.template-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid hsl(var(--border));
  border-radius: 10px;
  background: hsl(var(--card));
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.template-card:hover {
  border-color: hsl(var(--accent, 265 70% 55%) / 0.4);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}
.tpl-header { display: flex; align-items: center; gap: 10px; }
.tpl-icon {
  width: 18px;
  height: 18px;
  color: hsl(var(--accent, 265 70% 55%));
  flex-shrink: 0;
}
.tpl-name {
  font-size: 14px;
  font-weight: 700;
  font-family: 'SF Mono', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  letter-spacing: -0.01em;
}
.tpl-category { font-size: 11px; color: hsl(var(--muted-foreground)); }
.tpl-safety {
  display: inline-flex;
  padding: 2px 8px;
  font-size: 10px;
  font-weight: 700;
  border-radius: 999px;
  background: hsl(var(--destructive) / 0.1);
  color: hsl(var(--destructive));
  border: 1px solid hsl(var(--destructive) / 0.2);
}
.tpl-desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: hsl(var(--muted-foreground));
}
.tpl-signature {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  background: hsl(var(--secondary));
  border-radius: 8px;
  border: 1px solid hsl(var(--border));
}
.sig-row { display: flex; align-items: baseline; gap: 6px; font-size: 11px; }
.sig-label {
  width: 32px;
  flex-shrink: 0;
  font-weight: 600;
  color: hsl(var(--muted-foreground));
}
.sig-value {
  font-family: 'SF Mono', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 11px;
  word-break: break-all;
}
.sig-value-text { font-size: 11px; line-height: 1.4; }
.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 768px) {
  .compose-page { padding: 12px 12px 32px; gap: 12px; }
  .page-header { flex-direction: column; align-items: flex-start; gap: 8px; }
  .page-title { font-size: 17px; }
  .connection-bar-content { flex-direction: column; align-items: stretch; gap: 12px; }
  .connection-segmented { overflow-x: auto; }
  .segmented-item { flex: 1; justify-content: center; }
  .action-buttons { flex-wrap: wrap; }
  .compat-overview { flex-direction: column; align-items: flex-start; }
  .signal-details { padding-left: 26px; }
}

@media (prefers-reduced-motion: reduce) {
  .back-btn,
  .segmented-item,
  .comp-name-input,
  .code-editor,
  .yaml-editor,
  .action-btn,
  .template-card,
  .signal-match-item,
  .pass-bar-fill {
    transition-duration: 0.01ms;
  }
  .animate-spin {
    animation-duration: 0.01ms;
  }
}
</style>
