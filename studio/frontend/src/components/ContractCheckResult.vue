<script setup lang="ts">
import type { ContractCheckResult } from "@/services/mockApi";
import { parseConTags } from "@/utils/tagParser";
import {
	CheckCircle2,
	ChevronDown,
	ChevronRight,
	Code2,
	XCircle,
} from "lucide-vue-next";
/**
 * ContractCheckResult 契约校验结果组件（Patch 2 契约转断言）
 *
 * - 4 个分区：Preconditions / Postconditions / Invariants / Fault Handling
 * - 每项显示：条件内容 + ✅通过 / ❌失败
 * - 失败项红色高亮，点击展开失败原因
 * - 顶部总览：通过率 X/Y + 整体 pass/fail 徽章
 * - 展示自动生成的 assert 代码片段（Patch 2 断言插桩）
 */
import { computed, ref } from "vue";

interface Props {
	result: ContractCheckResult;
}

const props = defineProps<Props>();

const expandedFailures = ref<Set<string>>(new Set());
const showAssertCode = ref(false);

const toggleFailure = (id: string) => {
	const next = new Set(expandedFailures.value);
	if (next.has(id)) next.delete(id);
	else next.add(id);
	expandedFailures.value = next;
};

const passRate = computed(
	() => `${props.result.passed_count}/${props.result.total_count}`,
);

const passPercent = computed(() => {
	if (props.result.total_count === 0) return 100;
	return Math.round(
		(props.result.passed_count / props.result.total_count) * 100,
	);
});

const sectionColor = (key: string): string => {
	const map: Record<string, string> = {
		preconditions: "#0EA5E9",
		postconditions: "#15803d",
		invariants: "#b45309",
		fault_handling: "#dc2626",
	};
	return map[key] ?? "#6366f1";
};

const sectionIcon = (key: string): string => {
	const map: Record<string, string> = {
		preconditions: "📥",
		postconditions: "📤",
		invariants: "🔒",
		fault_handling: "⚠",
	};
	return map[key] ?? "📋";
};
</script>
<template>
  <div class="contract-check">
    <!-- 顶部总览 -->
    <div class="overview" :class="{ pass: result.overall_passed, fail: !result.overall_passed }">
      <div class="overview-left">
        <component
          :is="result.overall_passed ? CheckCircle2 : XCircle"
          class="overview-icon"
        />
        <div class="overview-text">
          <div class="overview-title">
            {{ result.overall_passed ? "✅ 契约校验通过" : "❌ 契约校验未通过" }}
          </div>
          <div class="overview-sub">
            组件：{{ result.component }}
          </div>
        </div>
      </div>
      <div class="overview-right">
        <div class="pass-rate">
          {{ passRate }}
        </div>
        <div class="pass-label">
          通过率
        </div>
        <div class="pass-bar">
          <div class="pass-bar-fill" :style="{ width: passPercent + '%' }" />
        </div>
      </div>
    </div>

    <!-- 4 个分区 -->
    <div class="sections">
      <div
        v-for="section in result.sections"
        :key="section.key"
        class="section"
      >
        <div class="section-title" :style="{ borderLeftColor: sectionColor(section.key) }">
          <span class="section-icon">{{ sectionIcon(section.key) }}</span>
          <span>{{ section.title }}</span>
          <span class="section-count">
            {{ section.items.filter(i => i.passed).length }}/{{ section.items.length }}
          </span>
        </div>
        <div
          v-for="item in section.items"
          :key="item.id"
          class="check-item"
          :class="{ pass: item.passed, fail: !item.passed }"
        >
          <div class="item-header" @click="!item.passed && toggleFailure(item.id)">
            <component
              :is="item.passed ? CheckCircle2 : XCircle"
              class="item-icon"
              :class="{ pass: item.passed, fail: !item.passed }"
            />
            <span class="item-id">{{ item.id }}</span>
            <code class="item-expr">
              <template v-for="(tok, ti) in parseConTags(item.expression)" :key="ti">
                <span v-if="tok.type === 'text'">{{ tok.value }}</span>
                <span v-else class="con-tag">[{{ tok.value }}]</span>
              </template>
            </code>
            <component
              v-if="!item.passed"
              :is="expandedFailures.has(item.id) ? ChevronDown : ChevronRight"
              class="chevron"
            />
          </div>
          <div v-if="item.description" class="item-desc">
            {{ item.description }}
          </div>
          <div v-if="!item.passed && expandedFailures.has(item.id)" class="failure-reason">
            <div class="reason-label">
              ❌ 失败原因：
            </div>
            <div class="reason-text">
              {{ item.failure_reason }}
            </div>
          </div>
          <div class="assert-code">
            <span class="assert-label">assert:</span>
            <code class="assert-expr">{{ item.assert_code }}</code>
          </div>
        </div>
      </div>
    </div>

    <!-- 自动生成的 assert 代码（可折叠） -->
    <div class="generated-code">
      <div class="code-header" @click="showAssertCode = !showAssertCode">
        <Code2 class="code-icon" />
        <span class="code-title">
          自动生成的 assert 代码（注入 test_harness.c）
        </span>
        <component
          :is="showAssertCode ? ChevronDown : ChevronRight"
          class="chevron"
        />
      </div>
      <div v-if="showAssertCode" class="code-body">
        <pre class="code-pre"><code>{{ result.generated_assert_code }}</code></pre>
      </div>
    </div>
  </div>
</template>
<style scoped>
.contract-check {
  font-family: 'Inter', sans-serif;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-radius: 8px;
  border: 2px solid;
}

.overview.pass {
  background: linear-gradient(to right, #f0fdf4, #ecfdf5);
  border-color: #10b981;
}

.overview.fail {
  background: linear-gradient(to right, #fef2f2, #fff7ed);
  border-color: #f59e0b;
}

.overview-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.overview-icon {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
}

.overview.pass .overview-icon {
  color: #10b981;
}

.overview.fail .overview-icon {
  color: #f59e0b;
}

.overview-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2937;
}

.overview-sub {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
}

.overview-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  min-width: 160px;
}

.pass-rate {
  font-size: 28px;
  font-weight: 800;
  font-family: 'Consolas', monospace;
}

.overview.pass .pass-rate {
  color: #10b981;
}

.overview.fail .pass-rate {
  color: #f59e0b;
}

.pass-label {
  font-size: 11px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.pass-bar {
  width: 100%;
  height: 6px;
  background: #e5e7eb;
  border-radius: 3px;
  overflow: hidden;
  margin-top: 4px;
}

.pass-bar-fill {
  height: 100%;
  background: #10b981;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.overview.fail .pass-bar-fill {
  background: #f59e0b;
}

.sections {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

@media (max-width: 768px) {
  .sections {
    grid-template-columns: 1fr;
  }
}

.section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 13px;
  color: #1f2937;
  border-left: 3px solid;
  padding-left: 8px;
  padding-bottom: 2px;
}

.section-icon {
  font-size: 14px;
}

.section-count {
  background: #f3f4f6;
  color: #4b5563;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 8px;
}

.check-item {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 8px 10px;
  transition: all 0.15s;
}

.check-item.pass {
  border-left: 3px solid #10b981;
}

.check-item.fail {
  border-left: 3px solid #f44747;
  background: #fef2f2;
}

.item-header {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  cursor: default;
}

.check-item.fail .item-header {
  cursor: pointer;
}

.item-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.item-icon.pass {
  color: #10b981;
}

.item-icon.fail {
  color: #f44747;
}

.item-id {
  font-family: 'Consolas', monospace;
  font-size: 11px;
  font-weight: 600;
  background: #0F1623;
  color: #F0F4F8;
  padding: 1px 6px;
  border-radius: 3px;
  border: 1px solid rgba(14, 165, 233, 0.1);
}

.item-expr {
  flex: 1;
  font-size: 12px;
  color: #4b5563;
  word-break: break-all;
}

.con-tag {
  color: #0EA5E9;
  font-weight: 600;
}

.chevron {
  width: 14px;
  height: 14px;
  color: #9ca3af;
  flex-shrink: 0;
}

.item-desc {
  font-size: 11px;
  color: #6b7280;
  margin-top: 4px;
  padding-left: 22px;
}

.failure-reason {
  margin-top: 6px;
  padding: 8px 10px;
  background: #fee2e2;
  border-radius: 4px;
  border: 1px solid #fca5a5;
}

.reason-label {
  font-size: 12px;
  font-weight: 600;
  color: #991b1b;
  margin-bottom: 2px;
}

.reason-text {
  font-size: 12px;
  color: #7f1d1d;
  line-height: 1.5;
}

.assert-code {
  margin-top: 6px;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 4px 6px;
  background: #1e1e1e;
  border-radius: 4px;
}

.assert-label {
  font-size: 10px;
  color: #4ec9b0;
  font-weight: 600;
  flex-shrink: 0;
  padding-top: 1px;
}

.assert-expr {
  flex: 1;
  font-size: 11px;
  color: #ce9178;
  word-break: break-all;
  font-family: 'Consolas', monospace;
}

.generated-code {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.code-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #0F1623;
  color: #F0F4F8;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}

.code-header:hover {
  background: #1E293B;
}

.code-icon {
  width: 16px;
  height: 16px;
  color: #4ec9b0;
}

.code-title {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
}

.code-body {
  background: #181818;
  overflow-x: auto;
}

.code-pre {
  margin: 0;
  padding: 12px;
  font-family: 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #d4d4d4;
  white-space: pre;
}

.code-pre::-webkit-scrollbar {
  height: 8px;
  width: 8px;
}

.code-pre::-webkit-scrollbar-track {
  background: #1a1a1a;
}

.code-pre::-webkit-scrollbar-thumb {
  background: #3c3c3c;
  border-radius: 4px;
}
</style>