<script setup lang="ts">
/**
 * CodeViewer 代码展示组件（含高亮追溯 Patch 3）
 *
 * - 展示 C 代码，带行号
 * - 解析注释中的 [REQ-xxx] 和 [MISRA-Rule-x.x] Tag，渲染为可点击的彩色徽章
 * - 点击 [REQ-xxx] 徽章：高亮所有相关代码行（黄色背景）
 * - 点击 [MISRA-Rule-x.x] 徽章：显示规则说明 tooltip（native title）
 *
 * 双向追溯可视化（Patch 3 亮点）
 */
import { computed, ref } from "vue";
import { MISRA_RULE_DOCS } from "@/services/mockApi";

interface Props {
	/** C 代码内容 */
	code: string;
	/** 追溯矩阵：REQ-xxx -> 行号列表（1-based） */
	traceability?: Record<string, number[]>;
	/** 是否启用高亮追溯（由父组件的"高亮追溯"开关控制） */
	highlightEnabled?: boolean;
}

const props = defineProps<Props>();

/** 当前激活的需求标签（用于高亮），null 表示未激活 */
const activeReq = ref<string | null>(null);

/** 行类型：解析后的每行数据包含原始文本和行号 */
interface CodeLine {
	no: number;
	text: string;
}

/** 行内 Token：普通文本 / REQ 徽章 / MISRA 徽章 / CON 徽章 */
type Token =
	| { type: "text"; value: string }
	| { type: "req"; value: string }
	| { type: "misra"; value: string; doc: string }
	| { type: "con"; value: string };

/** 把一行代码解析为 token 列表，识别 [REQ-001] [MISRA-Rule-8.1] [CON-001-POST-000] 等 */
const parseLine = (text: string): Token[] => {
	const tokens: Token[] = [];
	// 正则：匹配 [REQ-xxx] / [MISRA-Rule-x.x] / [CON-xxx-XXX-nnn]
	const regex = /\[(REQ-\d+|MISRA-Rule-[\d.]+|CON-\d+-[A-Z]+-\d+)\]/g;
	let lastIdx = 0;
	let match: RegExpExecArray | null;
	while ((match = regex.exec(text)) !== null) {
		if (match.index > lastIdx) {
			tokens.push({ type: "text", value: text.slice(lastIdx, match.index) });
		}
		const tag = match[1];
		if (tag.startsWith("REQ-")) {
			tokens.push({ type: "req", value: tag });
		} else if (tag.startsWith("MISRA-Rule-")) {
			tokens.push({
				type: "misra",
				value: tag,
				doc: MISRA_RULE_DOCS[tag] ?? `未收录规则说明：${tag}`,
			});
		} else if (tag.startsWith("CON-")) {
			tokens.push({ type: "con", value: tag });
		}
		lastIdx = match.index + match[0].length;
	}
	if (lastIdx < text.length) {
		tokens.push({ type: "text", value: text.slice(lastIdx) });
	}
	return tokens;
};

/** 代码行列表（带行号） */
const lines = computed<CodeLine[]>(() => {
	return props.code.split("\n").map((text, idx) => ({
		no: idx + 1,
		text,
	}));
});

/** 解析每行的 token */
const lineTokens = computed<Token[][]>(() => {
	return lines.value.map((line) => parseLine(line.text));
});

/** 当前需要高亮的行号集合 */
const highlightedLines = computed<Set<number>>(() => {
	if (!props.highlightEnabled) return new Set();
	if (!activeReq.value) return new Set();
	const lineList = props.traceability?.[activeReq.value] ?? [];
	return new Set(lineList);
});

/** 点击 REQ 徽章 */
const onReqClick = (req: string) => {
	// 即便 highlightEnabled 关闭，也允许 toggle（只是不会高亮）
	if (activeReq.value === req) {
		activeReq.value = null;
	} else {
		activeReq.value = req;
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
                active: activeReq === token.value,
                clickable: highlightEnabled
              }"
              :title="highlightEnabled ? `点击高亮 ${token.value} 关联代码行` : `需求标签 ${token.value}（开启右上角开关可启用追溯高亮）`"
              @click="onReqClick(token.value)"
            >[{{ token.value }}]</span><span
              v-else-if="token.type === 'misra'"
              class="tag-badge misra-badge"
              :title="token.doc"
            >[{{ token.value }}]</span><span
              v-else-if="token.type === 'con'"
              class="tag-badge con-badge"
              :title="`契约条件 ${token.value}`"
            >[{{ token.value }}]</span></template></span></div></code></pre>

    <div v-if="hasCode" class="legend">
      <span class="legend-item"><span class="dot req-dot" /> REQ 需求标签</span>
      <span class="legend-item"><span class="dot misra-dot" /> MISRA 规则（hover 查看说明）</span>
      <span class="legend-item"><span class="dot con-dot" /> CON 契约条件</span>
      <span v-if="highlightEnabled && activeReq" class="legend-item active-legend">
        当前高亮：{{ activeReq }} ({{ highlightedLines.size }} 行)
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
  background: rgba(255, 213, 79, 0.22);
  box-shadow: inset 3px 0 0 #ffd54f;
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
  background: #1e6fb8;
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
  background: #ffd54f;
  color: #1e1e1e;
  box-shadow: 0 0 0 2px rgba(255, 213, 79, 0.5);
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
  color: #ffd54f;
  font-weight: 600;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  display: inline-block;
}

.req-dot {
  background: #1e6fb8;
}

.misra-dot {
  background: #b45309;
}

.con-dot {
  background: #6b21a8;
}
</style>
