<script setup lang="ts">
import {
	AlertTriangle,
	CheckCircle2,
	ChevronDown,
	ChevronRight,
} from "@lucide/vue";
/**
 * RepairTimeline 修复闭环时间线组件（Patch 1 查改解耦可视化）
 *
 * - 时间线样式展示修复历史（每轮一个节点）
 * - 每轮节点：轮次编号 + 修复前违规数 → 修复后违规数 + 修复的规则列表
 * - 点击某轮：展开显示修复前/后代码 diff（CodeDiff 组件）
 * - 最终轮高亮"✅ 0 违规"或"⚠️ 仍有 N 个违规"
 */
import { ref } from "vue";
import type { RepairIteration } from "@/services/mockApi";
import CodeDiff from "./CodeDiff.vue";

interface Props {
	/** 修复历史列表 */
	history: RepairIteration[];
}

const props = defineProps<Props>();

/** 当前展开的轮次（null 表示都收起） */
const expandedRound = ref<number | null>(null);

/** 切换展开/收起 */
const toggleRound = (round: number) => {
	expandedRound.value = expandedRound.value === round ? null : round;
};

/** 是否最终轮 */
const isFinal = (round: number) => round === props.history.length;

/** 最终违规数 */
const finalViolations = (): number => {
	if (props.history.length === 0) return -1;
	return props.history[props.history.length - 1].violations_after;
};
</script>
<template>
  <div v-if="history.length === 0" class="empty">
    暂无修复历史
  </div>
  <div v-else class="repair-timeline">
    <!-- 总览徽章 -->
    <div class="overview">
      <span class="overview-label">🔧 MISRA 修复闭环</span>
      <span class="overview-stat">
        共 {{ history.length }} 轮修复
      </span>
      <span class="overview-stat">
        初始 {{ history[0].violations_before }} 个违规
      </span>
      <span class="overview-stat" :class="{ 'pass': finalViolations() === 0, 'fail': finalViolations() !== 0 }">
        → 最终 {{ finalViolations() }} 个违规
      </span>
    </div>

    <!-- 时间线 -->
    <div class="timeline">
      <div
        v-for="iter in history"
        :key="iter.round"
        class="timeline-item"
        :class="{ final: isFinal(iter.round) }"
      >
        <div class="timeline-dot" :class="{ pass: iter.violations_after === 0, fail: iter.violations_after !== 0 }">
          {{ iter.round }}
        </div>
        <div class="round-card" :class="{ expanded: expandedRound === iter.round }">
          <div class="round-header" @click="toggleRound(iter.round)">
            <div class="round-title">
              <component
                :is="iter.violations_after === 0 ? CheckCircle2 : AlertTriangle"
                class="round-icon"
                :class="{ pass: iter.violations_after === 0, warn: iter.violations_after !== 0 }"
              />
              <span class="round-name">第 {{ iter.round }} 轮修复</span>
              <span v-if="isFinal(iter.round)" class="final-badge">
                最终轮
              </span>
            </div>
            <div class="round-stats">
              <span class="stat-before">{{ iter.violations_before }} 违规</span>
              <span class="stat-arrow">→</span>
              <span class="stat-after" :class="{ pass: iter.violations_after === 0, warn: iter.violations_after !== 0 }">
                {{ iter.violations_after }} 违规
              </span>
            </div>
            <component
              :is="expandedRound === iter.round ? ChevronDown : ChevronRight"
              class="chevron"
            />
          </div>
          <div class="fixed-rules">
            <span class="rules-label">修复规则：</span>
            <span
              v-for="rule in iter.violations_fixed"
              :key="rule"
              class="rule-tag fixed"
            >{{ rule }}</span>
            <span v-if="iter.violations_remaining.length > 0" class="rules-label remaining">
              剩余：
            </span>
            <span
              v-for="rule in iter.violations_remaining"
              :key="rule"
              class="rule-tag remaining"
            >{{ rule }}</span>
          </div>
          <div class="round-desc">
            {{ iter.description }}
          </div>
          <div v-if="isFinal(iter.round) && iter.violations_after === 0" class="final-status pass">
            ✅ 全部违规已修复，MISRA-C 合规检查通过
          </div>
          <div v-else-if="isFinal(iter.round) && iter.violations_after > 0" class="final-status fail">
            ⚠️ 仍有 {{ iter.violations_after }} 个违规未修复
          </div>
          <div v-if="expandedRound === iter.round" class="diff-section">
            <div class="diff-title">
              📝 代码对比（修复前 → 修复后）
            </div>
            <CodeDiff :before="iter.before_code" :after="iter.after_code" filename="code.c" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<style scoped>
.repair-timeline {
  font-family: 'Inter', sans-serif;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty {
  padding: 24px;
  text-align: center;
  color: #6b7280;
  font-style: italic;
}

.overview {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 14px;
  background: linear-gradient(to right, #eef2ff, #f0fdf4);
  border: 1px solid #c7d2fe;
  border-radius: 8px;
  font-size: 13px;
}

.overview-label {
  font-weight: 600;
  color: #4f46e5;
}

.overview-stat {
  color: #4b5563;
  font-weight: 500;
}

.overview-stat.pass {
  color: #15803d;
  font-weight: 700;
}

.overview-stat.fail {
  color: #dc2626;
  font-weight: 700;
}

.timeline {
  position: relative;
  padding-left: 8px;
}

.timeline-item {
  position: relative;
  padding-left: 36px;
  padding-bottom: 16px;
}

.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-item:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 15px;
  top: 28px;
  bottom: 0;
  width: 2px;
  background: #d1d5db;
}

.timeline-dot {
  position: absolute;
  left: 0;
  top: 4px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #6366f1;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  z-index: 1;
  border: 3px solid #fff;
  box-shadow: 0 0 0 2px #6366f1;
}

.timeline-dot.pass {
  background: #10b981;
  box-shadow: 0 0 0 2px #10b981;
}

.timeline-dot.fail {
  background: #f59e0b;
  box-shadow: 0 0 0 2px #f59e0b;
}

.round-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  transition: box-shadow 0.2s;
}

.round-card.expanded {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.timeline-item.final .round-card {
  border-color: #10b981;
  border-width: 2px;
}

.round-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}

.round-header:hover {
  background: #f9fafb;
}

.round-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 14px;
  color: #1f2937;
  flex: 1;
}

.round-icon {
  width: 18px;
  height: 18px;
}

.round-icon.pass {
  color: #10b981;
}

.round-icon.warn {
  color: #f59e0b;
}

.final-badge {
  background: #10b981;
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 8px;
  text-transform: uppercase;
}

.round-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-family: 'Consolas', monospace;
}

.stat-before {
  color: #dc2626;
  font-weight: 600;
}

.stat-arrow {
  color: #9ca3af;
}

.stat-after {
  font-weight: 700;
}

.stat-after.pass {
  color: #10b981;
}

.stat-after.warn {
  color: #f59e0b;
}

.chevron {
  width: 16px;
  height: 16px;
  color: #9ca3af;
  flex-shrink: 0;
}

.fixed-rules {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding: 0 14px 8px;
  font-size: 12px;
}

.rules-label {
  color: #6b7280;
  font-weight: 500;
}

.rules-label.remaining {
  margin-left: 8px;
}

.rule-tag {
  font-family: 'Consolas', monospace;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 3px;
}

.rule-tag.fixed {
  background: #dcfce7;
  color: #15803d;
}

.rule-tag.remaining {
  background: #fee2e2;
  color: #991b1b;
}

.round-desc {
  padding: 0 14px 10px;
  font-size: 12px;
  color: #4b5563;
  line-height: 1.5;
}

.final-status {
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
}

.final-status.pass {
  background: #f0fdf4;
  color: #15803d;
}

.final-status.fail {
  background: #fef2f2;
  color: #991b1b;
}

.diff-section {
  border-top: 1px solid #e5e7eb;
  padding: 12px 14px;
}

.diff-title {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  margin-bottom: 8px;
}
</style>