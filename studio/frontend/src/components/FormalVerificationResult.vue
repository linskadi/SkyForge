<script setup lang="ts">
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
/**
 * FormalVerificationResult 形式化验证结果组件（Task 5.5）
 *
 * 展示 Z3 SMT Solver + CBMC 对契约的形式化验证结果：
 * - 顶部状态徽章（passed=绿 ✓ / failed=红 ✗ / skipped=灰 -）
 * - 通过/失败/跳过统计徽章
 * - 各检查项列表（名称、状态图标、耗时、工具标签）
 * - 反例展示区（failed/skipped 项展开后显示）
 * - 工具标识（Z3 / CBMC / Z3+CBMC / Mock）
 * - 空状态：loading=false 且 result=null 时提示开始验证
 * - Loading 状态：骨架屏
 *
 * 使用 shadcn-vue Card / Skeleton / Button 组件 + 内联徽章样式
 * （与 ContractCheckResult.vue 风格保持一致）。
 */
import type {
	VerificationCheck,
	VerificationResult,
} from "@/types/verification";
import {
	AlertTriangle,
	CheckCircle2,
	ChevronDown,
	ChevronRight,
	MinusCircle,
	Play,
	XCircle,
} from "lucide-vue-next";
import { computed, ref } from "vue";

interface Props {
	/** 验证结果对象（与 /api/verify 返回格式一致） */
	result: VerificationResult | null;
	/** 是否正在加载 */
	loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
	loading: false,
});

const emit = defineEmits<{
	/** 用户点击"开始验证"按钮 */
	(e: "start-verify"): void;
}>();

/** 当前展开的反例项（按 check.name 索引） */
const expanded = ref<Set<string>>(new Set());

const toggleExpand = (name: string) => {
	const next = new Set(expanded.value);
	if (next.has(name)) next.delete(name);
	else next.add(name);
	expanded.value = next;
};

/** 顶部状态配置 */
const statusConfig = computed(() => {
	if (!props.result) return null;
	const status = props.result.status;
	const map = {
		passed: {
			icon: CheckCircle2,
			label: "✅ 形式化验证通过",
			color: "#10b981",
			bg: "linear-gradient(to right, #f0fdf4, #ecfdf5)",
			border: "#10b981",
		},
		failed: {
			icon: XCircle,
			label: "❌ 形式化验证失败",
			color: "#dc2626",
			bg: "linear-gradient(to right, #fef2f2, #fff7ed)",
			border: "#f59e0b",
		},
		skipped: {
			icon: MinusCircle,
			label: "⏸ 形式化验证已跳过",
			color: "#6b7280",
			bg: "linear-gradient(to right, #f9fafb, #f3f4f6)",
			border: "#9ca3af",
		},
	} as const;
	return map[status] ?? map.skipped;
});

/** 总耗时（秒） */
const totalDurationSec = computed(() => {
	if (!props.result) return "0.000";
	return (props.result.total_duration_ms / 1000).toFixed(3);
});

/** 检查项状态图标与颜色 */
const checkVisual = (status: VerificationCheck["status"]) => {
	const map = {
		passed: { icon: CheckCircle2, color: "#10b981", symbol: "✓" },
		failed: { icon: XCircle, color: "#dc2626", symbol: "✗" },
		skipped: { icon: MinusCircle, color: "#9ca3af", symbol: "-" },
	} as const;
	return map[status] ?? map.skipped;
};

/** 单项耗时（秒） */
const formatDuration = (ms: number): string => (ms / 1000).toFixed(3);

/** 是否有可展开的反例 */
const hasCounterExample = (check: VerificationCheck): boolean => {
	return Boolean(check.counter_example);
};

const onStart = () => emit("start-verify");
</script>

<template>
  <div class="formal-verification">
    <!-- Loading 状态：骨架屏 -->
    <Card v-if="loading" class="result-card">
      <CardHeader>
        <CardTitle class="card-title">
          🔬 形式化验证进行中
          <span class="title-hint">（Z3 SMT Solver + CBMC 有界模型检查）</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div class="skeleton-list">
          <Skeleton class="skeleton-row" />
          <Skeleton class="skeleton-row" />
          <Skeleton class="skeleton-row" />
          <Skeleton class="skeleton-row short" />
        </div>
      </CardContent>
    </Card>

    <!-- 空状态：未验证 -->
    <Card v-else-if="!result" class="result-card empty-card">
      <CardHeader>
        <CardTitle class="card-title">
          🔬 形式化验证
          <span class="title-hint">（Z3 SMT Solver + CBMC 有界模型检查）</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div class="empty-state">
          <AlertTriangle class="empty-icon" />
          <p class="empty-text">
            点击上方按钮开始验证
          </p>
          <p class="empty-hint">
            将契约的前置/后置/不变式转换为 Z3 SMT 约束，验证逻辑一致性，
            并（可选）调用 CBMC 对生成的 C 代码进行有界模型检查。
          </p>
          <Button variant="outline" @click="onStart">
            <Play />
            开始形式化验证
          </Button>
        </div>
      </CardContent>
    </Card>

    <!-- 结果展示 -->
    <Card v-else class="result-card">
      <CardHeader>
        <CardTitle class="card-title">
          🔬 形式化验证结果
          <span class="title-hint">（Z3 SMT Solver + CBMC 有界模型检查）</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <!-- 顶部状态徽章 -->
        <div
          v-if="statusConfig"
          class="status-banner"
          :style="{
            background: statusConfig.bg,
            borderColor: statusConfig.border,
          }"
        >
          <component :is="statusConfig.icon" class="status-icon" :style="{ color: statusConfig.color }" />
          <div class="status-text">
            <div class="status-label" :style="{ color: statusConfig.color }">
              {{ statusConfig.label }}
            </div>
            <div class="status-meta">
              Tool: <strong>{{ result.tool }}</strong>
              · 总耗时: <strong>{{ totalDurationSec }}s</strong>
            </div>
          </div>
        </div>

        <!-- 统计徽章 -->
        <div class="summary-badges">
          <span class="badge pass">✓ Passed × {{ result.summary.passed }}</span>
          <span class="badge fail">✗ Failed × {{ result.summary.failed }}</span>
          <span class="badge skip">- Skipped × {{ result.summary.skipped }}</span>
          <span class="badge total">Total × {{ result.summary.total }}</span>
        </div>

        <!-- 错误信息（如契约文件不存在） -->
        <div v-if="result.error" class="error-banner">
          <AlertTriangle class="error-icon" />
          <span>{{ result.error }}</span>
        </div>

        <!-- 检查项列表 -->
        <ul class="check-list">
          <li
            v-for="check in result.checks"
            :key="check.name"
            class="check-item"
            :class="check.status"
          >
            <div
              class="check-header"
              :class="{ clickable: hasCounterExample(check) }"
              @click="hasCounterExample(check) && toggleExpand(check.name)"
            >
              <component
                :is="checkVisual(check.status).icon"
                class="check-icon"
                :style="{ color: checkVisual(check.status).color }"
              />
              <span class="check-name">{{ check.name }}</span>
              <span v-if="check.tool" class="check-tool">[{{ check.tool }}]</span>
              <span class="check-status" :style="{ color: checkVisual(check.status).color }">
                [{{ check.status.toUpperCase() }}]
              </span>
              <span class="check-duration">({{ formatDuration(check.duration_ms) }}s)</span>
              <component
                v-if="hasCounterExample(check)"
                :is="expanded.has(check.name) ? ChevronDown : ChevronRight"
                class="chevron"
              />
            </div>
            <div
              v-if="hasCounterExample(check) && expanded.has(check.name)"
              class="counter-example"
            >
              <div class="ce-label">
                {{ check.status === "failed" ? "❌ 反例 (Counter-example):" : "ℹ 说明:" }}
              </div>
              <pre class="ce-text">{{ check.counter_example }}</pre>
            </div>
          </li>
        </ul>

        <!-- 底部工具说明 -->
        <div class="tool-footer">
          <span class="tool-tag">{{ result.tool }}</span>
          <span class="tool-desc">
            Z3 SMT Solver 验证约束一致性 · CBMC 执行有界模型检查 ·
            工具不可用时自动降级为 SKIPPED
          </span>
        </div>
      </CardContent>
    </Card>
  </div>
</template>

<style scoped>
.formal-verification {
  font-family: 'Inter', sans-serif;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.result-card {
  border-radius: 8px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
}

.title-hint {
  font-size: 12px;
  font-weight: 400;
  color: #6b7280;
}

/* ===== Loading 骨架屏 ===== */
.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 8px 0;
}

.skeleton-row {
  height: 28px;
  width: 100%;
}

.skeleton-row.short {
  width: 60%;
}

/* ===== 空状态 ===== */
.empty-card .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 24px 12px;
  text-align: center;
}

.empty-icon {
  width: 40px;
  height: 40px;
  color: #f59e0b;
}

.empty-text {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.empty-hint {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
  margin: 0 0 8px 0;
  max-width: 480px;
}

/* ===== 顶部状态横幅 ===== */
.status-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border-radius: 8px;
  border: 2px solid;
  margin-bottom: 12px;
}

.status-icon {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
}

.status-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.status-label {
  font-size: 17px;
  font-weight: 700;
}

.status-meta {
  font-size: 12px;
  color: #6b7280;
}

.status-meta strong {
  color: #1f2937;
}

/* ===== 统计徽章 ===== */
.summary-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 14px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid;
}

.badge.pass {
  background: #ecfdf5;
  color: #047857;
  border-color: #a7f3d0;
}

.badge.fail {
  background: #fef2f2;
  color: #b91c1c;
  border-color: #fca5a5;
}

.badge.skip {
  background: #f3f4f6;
  color: #4b5563;
  border-color: #d1d5db;
}

.badge.total {
  background: #eff6ff;
  color: #1e40af;
  border-color: #bfdbfe;
}

/* ===== 错误横幅 ===== */
.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #fef3c7;
  border: 1px solid #fcd34d;
  border-radius: 6px;
  color: #92400e;
  font-size: 13px;
  margin-bottom: 12px;
}

.error-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

/* ===== 检查项列表 ===== */
.check-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.check-item {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 8px 12px;
  transition: all 0.15s;
}

.check-item.passed {
  border-left: 3px solid #10b981;
}

.check-item.failed {
  border-left: 3px solid #dc2626;
  background: #fef2f2;
}

.check-item.skipped {
  border-left: 3px solid #9ca3af;
  background: #f9fafb;
}

.check-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  cursor: default;
}

.check-header.clickable {
  cursor: pointer;
}

.check-header:hover.clickable {
  background: #f9fafb;
}

.check-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.check-name {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: #1f2937;
  min-width: 200px;
}

.check-tool {
  font-family: 'Consolas', monospace;
  font-size: 11px;
  font-weight: 600;
  background: #0F1623;
  color: #F0F4F8;
  padding: 1px 6px;
  border-radius: 3px;
}

.check-status {
  font-family: 'Consolas', monospace;
  font-size: 12px;
  font-weight: 700;
}

.check-duration {
  font-family: 'Consolas', monospace;
  font-size: 11px;
  color: #6b7280;
}

.chevron {
  width: 14px;
  height: 14px;
  color: #9ca3af;
  flex-shrink: 0;
}

/* ===== 反例展示 ===== */
.counter-example {
  margin-top: 8px;
  padding: 10px 12px;
  background: #1e1e1e;
  border-radius: 4px;
  border: 1px solid #374151;
}

.check-item.skipped .counter-example {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.ce-label {
  font-size: 11px;
  font-weight: 600;
  color: #fca5a5;
  margin-bottom: 4px;
}

.check-item.skipped .ce-label {
  color: #6b7280;
}

.ce-text {
  margin: 0;
  font-family: 'Consolas', monospace;
  font-size: 12px;
  color: #d4d4d4;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.5;
}

.check-item.skipped .ce-text {
  color: #4b5563;
}

/* ===== 底部工具说明 ===== */
.tool-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed #e5e7eb;
}

.tool-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  background: #0F1623;
  color: #4ec9b0;
  font-family: 'Consolas', monospace;
  font-size: 11px;
  font-weight: 600;
  border-radius: 3px;
}

.tool-desc {
  font-size: 11px;
  color: #6b7280;
  line-height: 1.4;
}
</style>
