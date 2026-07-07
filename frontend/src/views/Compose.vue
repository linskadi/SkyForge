<script setup lang="ts">
/**
 * Compose.vue - 组件组合验证页面
 *
 * - 左右两栏：组件 A 和组件 B
 *   - 每栏：代码编辑器 + 契约 YAML 编辑器
 *   - 预设示例：低通滤波器 + 高通滤波器
 * - 中间：连接方式选择（顺序/并行/反馈）+ "组合验证"按钮
 * - 底部结果区：
 *   - 兼容性检查结果
 *   - 组合后代码预览（CodeViewer 复用）
 *   - 组合仿真结果（SimulationResult 复用）
 */
import { ref, computed } from "vue";
import { Loader2, Play, RotateCcw, Layers, GitBranch, GitFork, Copy, Check } from "lucide-vue-next";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import CodeViewer from "@/components/CodeViewer.vue";
import SimulationResultView from "@/components/SimulationResult.vue";
import {
  PRESET_LP_CODE,
  PRESET_LP_CONTRACT,
  PRESET_HP_CODE,
  PRESET_HP_CONTRACT,
  type ComposeConnection,
  type ComposeResult,
  type CompatibilityResult,
  type SimulationResult,
} from "@/services/mockApi";
import { getApi } from "@/services/apiSwitcher";

/** 组件 A 名称 */
const compAName = ref<string>("LowPassFilter");
/** 组件 A 代码 */
const compACode = ref<string>(PRESET_LP_CODE);
/** 组件 A 契约 YAML */
const compAContract = ref<string>(PRESET_LP_CONTRACT);

/** 组件 B 名称 */
const compBName = ref<string>("HighPassFilter");
/** 组件 B 代码 */
const compBCode = ref<string>(PRESET_HP_CODE);
/** 组件 B 契约 YAML */
const compBContract = ref<string>(PRESET_HP_CONTRACT);

/** 连接方式 */
const connection = ref<ComposeConnection>("sequential");

/** 状态机 */
const status = ref<"idle" | "composing" | "done" | "error">("idle");
/** 错误信息 */
const errorMsg = ref<string>("");
/** 组合结果 */
const composeResult = ref<ComposeResult | null>(null);
/** 兼容性检查结果 */
const compatibilityResult = ref<CompatibilityResult | null>(null);
/** 兼容性检查中 */
const checkingCompat = ref<boolean>(false);

/** 连接方式选项 */
const connectionOptions: Array<{ value: ComposeConnection; label: string; icon: any; desc: string }> = [
  { value: "sequential", label: "顺序组合", icon: GitBranch, desc: "A → B（A 的输出作为 B 的输入）" },
  { value: "parallel", label: "并行组合", icon: GitFork, desc: "A ∥ B（同时运行，输出合并）" },
  { value: "feedback", label: "反馈组合", icon: RotateCcw, desc: "A → B → A（B 的输出反馈到 A）" },
];

/** 是否可点击组合验证 */
const canCompose = computed(
  () =>
    compACode.value.trim().length > 0 &&
    compBCode.value.trim().length > 0 &&
    status.value !== "composing",
);

/** 点击组合验证按钮 */
const onCompose = async () => {
  if (!canCompose.value) return;
  status.value = "composing";
  composeResult.value = null;
  compatibilityResult.value = null;
  errorMsg.value = "";
  try {
    // 通过 apiSwitcher 调用组合接口（mock 或真实 API）
    // mock 模式仅使用名称字符串；真实 API 模式 api.ts 内部会从对象中提取 code/contract
    const res = await getApi().compose(
      { name: compAName.value, code: compACode.value, contract: compAContract.value },
      { name: compBName.value, code: compBCode.value, contract: compBContract.value },
      connection.value,
    );
    composeResult.value = res;
    compatibilityResult.value = res.compatibility;
    status.value = "done";
  } catch (err) {
    console.error("[Compose] 组合失败：", err);
    errorMsg.value = err instanceof Error ? err.message : "组合失败";
    status.value = "error";
  }
};

/** 单独检查兼容性 */
const onCheckCompatibility = async () => {
  checkingCompat.value = true;
  errorMsg.value = "";
  try {
    const res = await getApi().checkCompatibility(
      compAContract.value,
      compBContract.value,
      connection.value,
    );
    compatibilityResult.value = res;
  } catch (err) {
    console.error("[Compose] 兼容性检查失败：", err);
    errorMsg.value = err instanceof Error ? err.message : "兼容性检查失败";
  } finally {
    checkingCompat.value = false;
  }
};

/** 重置 */
const onReset = () => {
  status.value = "idle";
  composeResult.value = null;
  compatibilityResult.value = null;
  errorMsg.value = "";
};

/** 加载预设示例 */
const loadPreset = () => {
  compAName.value = "LowPassFilter";
  compACode.value = PRESET_LP_CODE;
  compAContract.value = PRESET_LP_CONTRACT;
  compBName.value = "HighPassFilter";
  compBCode.value = PRESET_HP_CODE;
  compBContract.value = PRESET_HP_CONTRACT;
};

/** 当前仿真结果（来自 composeResult） */
const simResult = ref<SimulationResult | null>(null);
/** 监听 composeResult 变化，更新 simResult */
const updateSimResult = () => {
  if (composeResult.value) {
    simResult.value = composeResult.value.simulation;
  } else {
    simResult.value = null;
  }
};
// 在 composeResult 变化时同步更新
import { watch } from "vue";
watch(composeResult, updateSimResult, { immediate: true });

/** 兼容性通过率百分比 */
const compatPassPercent = computed(() => {
  if (!compatibilityResult.value) return 0;
  const { passed_count, total_count } = compatibilityResult.value;
  if (total_count === 0) return 100;
  return Math.round((passed_count / total_count) * 100);
});

/** 兼容性颜色 */
const compatColor = computed(() => {
  if (!compatibilityResult.value) return "#6b7280";
  return compatibilityResult.value.overall_compatible ? "#15803d" : "#f59e0b";
});

/** 复制组合代码按钮反馈状态 */
const copiedComposed = ref<boolean>(false);

/** 复制组合后代码到剪贴板 */
const onCopyComposedCode = async () => {
  if (!composeResult.value) return;
  try {
    await navigator.clipboard.writeText(composeResult.value.composed_code);
    copiedComposed.value = true;
    setTimeout(() => (copiedComposed.value = false), 2000);
  } catch (err) {
    console.error("[Compose] 复制失败：", err);
  }
};

/** 兼容性通过/失败计数 */
const compatStats = computed(() => {
  if (!compatibilityResult.value) return { pass: 0, fail: 0 };
  const checks = compatibilityResult.value.checks;
  return {
    pass: checks.filter((c) => c.passed).length,
    fail: checks.filter((c) => !c.passed).length,
  };
});
</script>

<template>
  <div class="compose-page">
    <header class="page-header">
      <div class="title-area">
        <h1 class="page-title">
          <Layers class="icon" />
          组件组合验证
        </h1>
        <p class="subtitle">
          验证两个组件的契约兼容性，并生成组合后的 C 代码和仿真结果
        </p>
      </div>
      <div class="header-actions">
        <Button variant="outline" @click="loadPreset">
          <Play />
          加载预设示例
        </Button>
      </div>
    </header>

    <!-- 两栏组件输入 -->
    <div class="components-grid">
      <!-- 组件 A -->
      <Card class="comp-card comp-a">
        <CardHeader>
          <CardTitle class="card-title">
            <span class="comp-badge a">A</span>
            <input
              v-model="compAName"
              class="comp-name-input"
              placeholder="组件 A 名称"
            >
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="editor-section">
            <div class="section-label">💻 C 代码</div>
            <textarea
              v-model="compACode"
              class="code-editor"
              rows="12"
              spellcheck="false"
            />
          </div>
          <div class="editor-section">
            <div class="section-label">📋 契约 YAML</div>
            <textarea
              v-model="compAContract"
              class="yaml-editor"
              rows="10"
              spellcheck="false"
            />
          </div>
        </CardContent>
      </Card>

      <!-- 中间连接配置 -->
      <Card class="connection-card">
        <CardHeader>
          <CardTitle class="card-title">
            <GitBranch class="title-icon" />
            连接方式
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="connection-options">
            <label
              v-for="opt in connectionOptions"
              :key="opt.value"
              class="connection-option"
              :class="{ active: connection === opt.value }"
            >
              <input
                v-model="connection"
                type="radio"
                :value="opt.value"
                class="radio-input"
              >
              <component :is="opt.icon" class="opt-icon" />
              <div class="opt-info">
                <div class="opt-label">{{ opt.label }}</div>
                <div class="opt-desc">{{ opt.desc }}</div>
              </div>
            </label>
          </div>

          <div class="compose-actions">
            <Button :disabled="!canCompose" @click="onCompose">
              <Loader2 v-if="status === 'composing'" class="animate-spin" />
              <Layers v-else />
              组合验证
            </Button>
            <Button variant="outline" :disabled="checkingCompat" @click="onCheckCompatibility">
              <Loader2 v-if="checkingCompat" class="animate-spin" />
              <GitBranch v-else />
              仅检查兼容性
            </Button>
          </div>

          <div v-if="errorMsg" class="error-msg">
            ❌ {{ errorMsg }}
          </div>

          <div v-if="status === 'composing'" class="status-text generating">
            正在组合验证...
          </div>
          <div v-else-if="status === 'done'" class="status-text done">
            ✅ 组合验证完成
          </div>
        </CardContent>
      </Card>

      <!-- 组件 B -->
      <Card class="comp-card comp-b">
        <CardHeader>
          <CardTitle class="card-title">
            <span class="comp-badge b">B</span>
            <input
              v-model="compBName"
              class="comp-name-input"
              placeholder="组件 B 名称"
            >
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="editor-section">
            <div class="section-label">💻 C 代码</div>
            <textarea
              v-model="compBCode"
              class="code-editor"
              rows="12"
              spellcheck="false"
            />
          </div>
          <div class="editor-section">
            <div class="section-label">📋 契约 YAML</div>
            <textarea
              v-model="compBContract"
              class="yaml-editor"
              rows="10"
              spellcheck="false"
            />
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- 结果区 -->
    <div v-if="compatibilityResult || composeResult" class="results-section">
      <!-- 兼容性检查结果 -->
      <Card v-if="compatibilityResult" class="result-card compat-card">
        <CardHeader>
          <CardTitle class="card-title">
            📐 兼容性检查结果
            <span class="title-hint">
              {{ compatibilityResult.component_a }} → {{ compatibilityResult.component_b }}
              （{{ connectionOptions.find(o => o.value === compatibilityResult?.connection)?.label }}）
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="compat-overview" :class="{ pass: compatibilityResult.overall_compatible, fail: !compatibilityResult.overall_compatible }">
            <div class="overview-left">
              <span class="overview-title">
                {{ compatibilityResult.overall_compatible ? "✅ 兼容" : "⚠ 部分不兼容" }}
              </span>
              <span class="overview-rate" :style="{ color: compatColor }">
                {{ compatibilityResult.passed_count }}/{{ compatibilityResult.total_count }}
              </span>
            </div>
            <div class="overview-right">
              <div class="pass-bar">
                <div class="pass-bar-fill" :style="{ width: compatPassPercent + '%', backgroundColor: compatColor }" />
              </div>
              <div class="pass-percent">{{ compatPassPercent }}%</div>
            </div>
          </div>

          <div class="compat-summary-badges">
            <span class="compat-badge pass">✅ 通过 {{ compatStats.pass }}</span>
            <span v-if="compatStats.fail > 0" class="compat-badge fail">❌ 失败 {{ compatStats.fail }}</span>
          </div>

          <div class="compat-checks">
            <div
              v-for="check in compatibilityResult.checks"
              :key="check.id"
              class="check-item"
              :class="{ pass: check.passed, fail: !check.passed }"
            >
              <div class="check-header">
                <span class="check-icon">{{ check.passed ? "✅" : "❌" }}</span>
                <code class="check-id">{{ check.id }}</code>
                <span class="check-text">{{ check.check }}</span>
              </div>
              <div v-if="!check.passed && check.reason" class="check-reason">
                ⚠ {{ check.reason }}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- 组合后代码 -->
      <Card v-if="composeResult" class="result-card code-card">
        <CardHeader>
          <CardTitle class="card-title">
            💻 组合后代码
            <span class="title-hint">
              {{ composeResult.component_a }} + {{ composeResult.component_b }}
              （{{ connectionOptions.find(o => o.value === composeResult?.connection)?.label }}）
            </span>
            <button
              type="button"
              class="action-btn"
              :title="copiedComposed ? '已复制' : '复制组合代码'"
              @click="onCopyComposedCode"
            >
              <Check v-if="copiedComposed" class="action-icon ok" />
              <Copy v-else class="action-icon" />
            </button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <CodeViewer :code="composeResult.composed_code" :highlight-enabled="false" />
        </CardContent>
      </Card>

      <!-- 组合仿真结果 -->
      <Card v-if="composeResult && simResult" class="result-card sim-card">
        <CardHeader>
          <CardTitle class="card-title">
            🧪 组合仿真结果
          </CardTitle>
        </CardHeader>
        <CardContent>
          <SimulationResultView :result="simResult" />
        </CardContent>
      </Card>
    </div>

    <!-- 空状态提示 -->
    <div v-if="status === 'idle' && !compatibilityResult" class="empty-tip">
      <Layers class="empty-icon" />
      <p>选择连接方式，点击"组合验证"开始</p>
    </div>

    <!-- 重置按钮 -->
    <div v-if="status !== 'idle'" class="reset-row">
      <Button variant="outline" @click="onReset">
        <RotateCcw />
        重置
      </Button>
    </div>
  </div>
</template>

<style scoped>
.compose-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px 32px 64px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0 8px;
  border-bottom: 1px solid var(--border, #e4e4e7);
}

.title-area h1 {
  font-size: 22px;
  font-weight: 700;
  margin: 0;
  color: var(--foreground, #18181b);
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-area h1 .icon {
  width: 24px;
  height: 24px;
  color: hsl(260, 60%, 55%);
}

.title-area p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--muted-foreground, #71717a);
}

.components-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
  align-items: start;
}

@media (max-width: 1100px) {
  .components-grid {
    grid-template-columns: 1fr;
  }
}

.comp-card {
  border: 1px solid var(--border, #e4e4e7);
  border-radius: 10px;
}

.comp-card.comp-a {
  border-top: 3px solid hsl(220, 70%, 50%);
}

.comp-card.comp-b {
  border-top: 3px solid #059669;
}

.connection-card {
  border-top: 3px solid hsl(260, 60%, 55%);
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-icon {
  width: 18px;
  height: 18px;
  color: hsl(260, 60%, 55%);
}

.title-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--muted-foreground, #a1a1aa);
  margin-left: 4px;
}

.comp-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  color: #fff;
  font-weight: 700;
  font-size: 13px;
  flex-shrink: 0;
}

.comp-badge.a {
  background: hsl(220, 70%, 50%);
}

.comp-badge.b {
  background: #059669;
}

.comp-name-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 14px;
  font-weight: 600;
  color: var(--foreground, #1f2937);
  outline: none;
  border-bottom: 1px dashed transparent;
  padding: 2px 4px;
}

.comp-name-input:hover,
.comp-name-input:focus {
  border-bottom-color: var(--border, #d4d4d8);
}

.editor-section {
  margin-bottom: 12px;
}

.editor-section:last-child {
  margin-bottom: 0;
}

.section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted-foreground, #6b7280);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.code-editor,
.yaml-editor {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border, #d4d4d8);
  border-radius: 4px;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
  background: #1e1e1e;
  color: #d4d4d4;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}

.code-editor:focus,
.yaml-editor:focus {
  border-color: hsl(260, 60%, 55%);
  box-shadow: 0 0 0 2px hsla(260, 60%, 55%, 0.15);
}

.connection-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.connection-option {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.connection-option:hover {
  border-color: hsl(260, 60%, 55%);
  background: hsla(260, 60%, 55%, 0.04);
}

.connection-option.active {
  border-color: hsl(260, 60%, 55%);
  background: hsla(260, 60%, 55%, 0.08);
  box-shadow: 0 0 0 1px hsl(260, 60%, 55%);
}

.radio-input {
  margin-top: 2px;
  accent-color: hsl(260, 60%, 55%);
}

.opt-icon {
  width: 16px;
  height: 16px;
  color: hsl(260, 60%, 55%);
  flex-shrink: 0;
  margin-top: 1px;
}

.opt-info {
  flex: 1;
}

.opt-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--foreground, #1f2937);
}

.opt-desc {
  font-size: 11px;
  color: var(--muted-foreground, #6b7280);
  margin-top: 2px;
}

.compose-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.error-msg {
  padding: 8px 10px;
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 4px;
  color: #991b1b;
  font-size: 12px;
  margin-bottom: 8px;
}

.status-text {
  font-size: 12px;
  font-weight: 500;
  padding: 6px 10px;
  border-radius: 4px;
}

.status-text.generating {
  color: hsl(220, 70%, 50%);
  background: hsla(220, 70%, 50%, 0.08);
}

.status-text.done {
  color: #059669;
  background: rgba(5, 150, 105, 0.08);
}

.results-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-card {
  border: 1px solid var(--border, #e4e4e7);
  border-radius: 10px;
}

.compat-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-radius: 6px;
  border: 2px solid;
  margin-bottom: 12px;
}

.compat-overview.pass {
  background: #f0fdf4;
  border-color: #10b981;
}

.compat-overview.fail {
  background: #fffbeb;
  border-color: #f59e0b;
}

.overview-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.overview-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
}

.overview-rate {
  font-family: 'Consolas', monospace;
  font-size: 18px;
  font-weight: 800;
}

.overview-right {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 200px;
}

.pass-bar {
  flex: 1;
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
}

.pass-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.pass-percent {
  font-size: 12px;
  font-weight: 700;
  color: var(--foreground, #1f2937);
  font-family: 'Consolas', monospace;
}

.compat-checks {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.check-item {
  padding: 8px 10px;
  background: var(--background, #fff);
  border: 1px solid var(--border, #e5e7eb);
  border-left: 3px solid;
  border-radius: 4px;
}

.check-item.pass {
  border-left-color: #10b981;
}

.check-item.fail {
  border-left-color: #f44747;
  background: #fef2f2;
}

.check-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.check-icon {
  font-size: 14px;
}

.check-id {
  font-family: 'Consolas', monospace;
  font-size: 11px;
  font-weight: 600;
  background: #0F1623;
  color: #F0F4F8;
  padding: 1px 6px;
  border-radius: 3px;
  border: 1px solid rgba(14, 165, 233, 0.1);
}

.check-text {
  font-size: 12px;
  color: var(--foreground, #1f2937);
  flex: 1;
}

.check-reason {
  margin-top: 4px;
  padding: 6px 8px;
  background: #fef3c7;
  border: 1px solid #fde68a;
  border-radius: 3px;
  font-size: 11px;
  color: #92400e;
  line-height: 1.5;
}

.empty-tip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 16px;
  color: var(--muted-foreground, #9ca3af);
  text-align: center;
  background: var(--secondary, #f9fafb);
  border-radius: 8px;
  border: 1px dashed var(--border, #d4d4d8);
}

.empty-icon {
  width: 32px;
  height: 32px;
  color: #9ca3af;
}

.empty-tip p {
  margin: 0;
  font-size: 13px;
}

.reset-row {
  display: flex;
  justify-content: flex-end;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  margin-left: auto;
  border: 1px solid var(--border, #d4d4d8);
  border-radius: 6px;
  background: var(--secondary, #f4f4f5);
  color: var(--foreground, #3f3f46);
  cursor: pointer;
  transition: all 0.15s;
}

.action-btn:hover {
  border-color: hsl(260, 60%, 55%);
  color: hsl(260, 60%, 55%);
  background: hsla(260, 60%, 55%, 0.08);
}

.action-icon {
  width: 14px;
  height: 14px;
}

.action-icon.ok {
  color: #059669;
}

.compat-summary-badges {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.compat-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
  border-radius: 12px;
}

.compat-badge.pass {
  background: #dcfce7;
  color: #059669;
}

.compat-badge.fail {
  background: #fee2e2;
  color: #b91c1c;
}

@media (max-width: 768px) {
  .compose-page {
    padding: 12px 12px 32px;
    gap: 12px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .title-area h1 {
    font-size: 18px;
  }

  .overview-right {
    min-width: 120px;
  }
}

.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
