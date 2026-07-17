<script setup lang="ts">
import { type InlineToken, parseInlineTags } from "@/utils/tagParser";
/**
 * CodeViewer 代码展示组件（含高亮追溯 Patch 3 + 双向联动）
 *
 * - 展示 C 代码，带行号
 * - 解析注释中的 [REQ-xxx] / [MISRA-Rule-x.x] / [CON-xxx] / [TST-xxx] Tag
 * - 点击 [REQ-xxx] 徽章：高亮所有相关代码行（REQ 走 traceability 矩阵）
 * - 点击 [CON-xxx] / [TST-xxx] 徽章：高亮包含该 Tag 的代码行（扫描）
 * - 点击 [MISRA-Rule-x.x] 徽章：显示规则说明 tooltip（native title）
 *
 * 双向追溯可视化（Patch 3 亮点）：
 * - 通过 activeTag prop 接收父组件传入的激活 Tag（如需求区点击 [REQ-001]）
 * - 通过 tagClick emit 通知父组件代码中点击的 Tag（联动需求/契约区）
 */
import { computed, ref } from "vue";

interface Props {
	/** C 代码内容 */
	code: string;
	/** 追溯矩阵：REQ-xxx -> 行号列表（1-based） */
	traceability?: Record<string, number[]>;
	/** 是否启用高亮追溯（由父组件的"高亮追溯"开关控制） */
	highlightEnabled?: boolean;
	/** 外部激活的 Tag（双向追溯：父组件点击需求/契约 Tag 时传入）。
	 *  传入 undefined 表示不接管（由组件内部点击驱动）；
	 *  传入 null 表示显式取消激活；传入字符串表示激活该 Tag。 */
	activeTag?: string | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{
	/** 点击代码中的 Tag 徽章时触发，null 表示取消激活 */
	tagClick: [value: string | null];
}>();

/** 内部激活的 Tag（组件内点击驱动），null 表示未激活 */
const internalTag = ref<string | null>(null);

/** 实际生效的激活 Tag：外部 prop 优先（非 undefined 时接管），否则回退到内部状态 */
const effectiveTag = computed<string | null>(() => {
	if (props.activeTag !== undefined) return props.activeTag;
	return internalTag.value;
});

/** 行类型：解析后的每行数据包含原始文本和行号 */
interface CodeLine {
	no: number;
	text: string;
}

/** 代码行列表（带行号） */
const lines = computed<CodeLine[]>(() => {
	return props.code.split("\n").map((text, idx) => ({
		no: idx + 1,
		text,
	}));
});

/** 解析每行的 token */
const lineTokens = computed<InlineToken[][]>(() => {
	return lines.value.map((line) => parseInlineTags(line.text));
});

/** 当前需要高亮的行号集合 */
const highlightedLines = computed<Set<number>>(() => {
	if (!props.highlightEnabled) return new Set();
	const tag = effectiveTag.value;
	if (!tag) return new Set();
	// REQ：使用追溯矩阵
	if (tag.startsWith("REQ-")) {
		const lineList = props.traceability?.[tag] ?? [];
		return new Set(lineList);
	}
	// CON / TST：扫描包含该 Tag 文本的代码行
	const result = new Set<number>();
	const tagText = `[${tag}]`;
	for (const line of lines.value) {
		if (line.text.includes(tagText)) {
			result.add(line.no);
		}
	}
	return result;
});

/** 点击任意可追溯 Tag 徽章（REQ/CON/TST） */
const onTagClick = (tag: string) => {
	// 即便 highlightEnabled 关闭，也允许 toggle（只是不会高亮）
	if (effectiveTag.value === tag) {
		internalTag.value = null;
		emit("tagClick", null);
	} else {
		internalTag.value = tag;
		emit("tagClick", tag);
	}
};

/** 是否有任何可点击徽章（用于空状态判断） */
const hasCode = computed(() => props.code.length > 0);
</script>

<template>
  <div class="code-viewer">
    <div v-if="!hasCode" class="empty-hint">
      暂无代码
    </div>
    <pre v-else class="code-block"><code><div
        v-for="(tokens, idx) in lineTokens"
        :key="idx"
        class="code-line"
        :class="{ highlighted: highlightedLines.has(lines[idx].no) }"
      ><span class="line-no">{{ lines[idx].no }}</span><span class="line-content"><template
            v-for="(token, ti) in tokens"
            :key="ti"
          ><span v-if="token.type === 'text'" class="text-token">{{ token.value }}</span><span
              v-else-if="token.type === 'req'"
              class="tag-badge req-badge"
              :class="{
                active: effectiveTag === token.value,
                clickable: highlightEnabled
              }"
              :title="highlightEnabled ? `点击高亮 ${token.value} 关联代码行（双向追溯）` : `需求标签 ${token.value}（开启高亮追溯可启用联动）`"
              @click="onTagClick(token.value)"
            >[{{ token.value }}]</span><span
              v-else-if="token.type === 'misra'"
              class="tag-badge misra-badge"
              :title="token.doc"
            >[{{ token.value }}]</span><span
              v-else-if="token.type === 'con'"
              class="tag-badge con-badge"
              :class="{
                active: effectiveTag === token.value,
                clickable: highlightEnabled
              }"
              :title="highlightEnabled ? `点击高亮 ${token.value} 关联代码行（双向追溯）` : `契约条件 ${token.value}`"
              @click="onTagClick(token.value)"
            >[{{ token.value }}]</span><span
              v-else-if="token.type === 'tst'"
              class="tag-badge tst-badge"
              :class="{
                active: effectiveTag === token.value,
                clickable: highlightEnabled
              }"
              :title="highlightEnabled ? `点击高亮 ${token.value} 关联代码行（双向追溯）` : `测试标签 ${token.value}`"
              @click="onTagClick(token.value)"
            >[{{ token.value }}]</span></template></span></div></code></pre>

    <div v-if="hasCode" class="legend">
      <span class="legend-item"><span class="dot req-dot" /> REQ 需求标签</span>
      <span class="legend-item"><span class="dot misra-dot" /> MISRA 规则（hover 查看说明）</span>
      <span class="legend-item"><span class="dot con-dot" /> CON 契约条件</span>
      <span class="legend-item"><span class="dot tst-dot" /> TST 测试标签</span>
      <span v-if="highlightEnabled && effectiveTag" class="legend-item active-legend">
        当前高亮：{{ effectiveTag }} ({{ highlightedLines.size }} 行)
      </span>
    </div>
  </div>
</template>

<style scoped>
.code-viewer {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.code-block {
  margin: 0;
  padding: 8px 0;
  overflow-x: auto;
  overflow-y: auto;
  flex: 1;
  display: block;
}

.code-block::-webkit-scrollbar {
  height: 8px;
  width: 8px;
}

.code-block::-webkit-scrollbar-track {
  background: #1a1a1a;
}

.code-block::-webkit-scrollbar-thumb {
  background: #3c3c3c;
  border-radius: 4px;
}

.code-line {
  display: flex;
  align-items: flex-start;
  padding: 0 12px;
  line-height: 1.6;
  transition: background-color 0.2s ease;
}

.code-line.highlighted {
  background: rgba(255, 213, 79, 0.18);
  box-shadow: inset 4px 0 0 #f59e0b;
  border-left: none;
}

.code-line.highlighted .line-no {
  color: #f59e0b;
  font-weight: 700;
}

.line-no {
  flex-shrink: 0;
  width: 40px;
  text-align: right;
  margin-right: 16px;
  color: #6e7681;
  user-select: none;
}

.line-content {
  flex: 1;
  white-space: pre-wrap;
  min-width: 0;
}

.text-token {
  color: #d4d4d4;
}

/* 徽章通用样式 */
.tag-badge {
  display: inline-block;
  padding: 0 6px;
  margin: 0 2px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
  transition: all 0.15s ease;
}

/* REQ 徽章：蓝色（与 AgentTerminal REQ-Parser 配色对齐） */
.req-badge {
  background: #0EA5E9;
  color: #d6e8ff;
  cursor: pointer;
}

.req-badge:hover {
  background: #2884d1;
}

.req-badge.clickable {
  cursor: pointer;
}

.req-badge.active {
  background: #f59e0b;
  color: #1e1e1e;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.4), 0 0 12px rgba(245, 158, 11, 0.3);
  transform: scale(1.08);
  font-weight: 700;
}

/* MISRA 徽章：橙色 */
.misra-badge {
  background: #b45309;
  color: #ffedd5;
  cursor: help;
}

.misra-badge:hover {
  background: #d97706;
}

/* CON 徽章：紫色 */
.con-badge {
  background: #6b21a8;
  color: #f0e6ff;
  cursor: help;
}

.con-badge:hover {
  background: #7e22ce;
}

.con-badge.clickable {
  cursor: pointer;
}

.con-badge.active {
  background: #a855f7;
  color: #fff;
  box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.4), 0 0 12px rgba(168, 85, 247, 0.3);
  transform: scale(1.08);
  font-weight: 700;
}

/* TST 徽章：绿色 */
.tst-badge {
  background: #15803d;
  color: #dcfce7;
  cursor: help;
}

.tst-badge:hover {
  background: #16a34a;
}

.tst-badge.clickable {
  cursor: pointer;
}

.tst-badge.active {
  background: #22c55e;
  color: #052e16;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.4), 0 0 12px rgba(34, 197, 94, 0.3);
  transform: scale(1.08);
  font-weight: 700;
}

.empty-hint {
  padding: 24px;
  text-align: center;
  color: #6a6a6a;
  font-style: italic;
}

.legend {
  padding: 6px 12px;
  background: #252526;
  border-top: 1px solid #3c3c3c;
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 11px;
  color: #9d9d9d;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.active-legend {
  color: #f59e0b;
  font-weight: 700;
  background: rgba(245, 158, 11, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  display: inline-block;
}

.req-dot {
  background: #0EA5E9;
}

.misra-dot {
  background: #b45309;
}

.con-dot {
  background: #6b21a8;
}

.tst-dot {
  background: #15803d;
}
</style>
