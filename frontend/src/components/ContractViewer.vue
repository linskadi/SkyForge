<script setup lang="ts">
/**
 * ContractViewer 契约展示组件
 *
 * - 展示 YAML 契约，语法高亮（key 紫色 / string 绿色 / number 橙色）
 * - preconditions / postconditions / invariants / fault_handling 分区展示
 * - 每个条件标 [CON-xxx] Tag（紫色徽章）
 */
import { computed } from "vue";
import type { Contract, ContractCondition } from "@/services/mockApi";

interface Props {
	contract: Contract | null;
}

const props = defineProps<Props>();

interface Section {
	title: string;
	key: keyof Pick<
		Contract,
		"preconditions" | "postconditions" | "invariants" | "fault_handling"
	>;
	color: string;
	icon: string;
}

const sections: Section[] = [
	{ title: "前置条件 Preconditions", key: "preconditions", color: "#1e6fb8", icon: "📥" },
	{ title: "后置条件 Postconditions", key: "postconditions", color: "#15803d", icon: "📤" },
	{ title: "不变式 Invariants", key: "invariants", color: "#b45309", icon: "🔒" },
	{ title: "故障处理 Fault Handling", key: "fault_handling", color: "#dc2626", icon: "⚠" },
];

/** 把输入/输出字典转为数组，便于渲染 */
const inputEntries = computed<Array<[string, string]>>(() => {
	if (!props.contract) return [];
	return Object.entries(props.contract.inputs);
});

const outputEntries = computed<Array<[string, string]>>(() => {
	if (!props.contract) return [];
	return Object.entries(props.contract.outputs);
});

/** 从一行表达式中识别 [CON-xxx-XXX-nnn] 标签 */
const parseTags = (text: string): Array<{ type: "text" | "con"; value: string }> => {
	const tokens: Array<{ type: "text" | "con"; value: string }> = [];
	const regex = /\[(CON-\d+-[A-Z]+-\d+)\]/g;
	let lastIdx = 0;
	let match: RegExpExecArray | null;
	while ((match = regex.exec(text)) !== null) {
		if (match.index > lastIdx) {
			tokens.push({ type: "text", value: text.slice(lastIdx, match.index) });
		}
		tokens.push({ type: "con", value: match[1] });
		lastIdx = match.index + match[0].length;
	}
	if (lastIdx < text.length) {
		tokens.push({ type: "text", value: text.slice(lastIdx) });
	}
	return tokens;
};

/** YAML 颜色高亮（简单实现：对 string / number / key 着色） */
const renderYaml = (text: string): string => {
	// 转义 HTML
	let safe = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
	// key: value（行首到冒号）
	safe = safe.replace(
		/^(\s*)([A-Za-z_][\w-]*)(:)/gm,
		'$1<span class="yaml-key">$2</span>$3',
	);
	// "string"
	safe = safe.replace(
		/"([^"]*)"/g,
		'<span class="yaml-str">"$1"</span>',
	);
	// 数字
	safe = safe.replace(
		/\b(\d+(?:\.\d+)?f?)\b/g,
		'<span class="yaml-num">$1</span>',
	);
	// 注释
	safe = safe.replace(
		/(#.*)$/gm,
		'<span class="yaml-comment">$1</span>',
	);
	return safe;
};

/** 生成 YAML 字符串（基于结构化数据） */
const yamlText = computed(() => {
	if (!props.contract) return "";
	const c = props.contract;
	const lines: string[] = [];
	lines.push(`# ${c.description}`);
	lines.push(`component: ${c.component}`);
	lines.push("inputs:");
	for (const [k, v] of Object.entries(c.inputs)) {
		lines.push(`  ${k}: ${v}`);
	}
	lines.push("outputs:");
	for (const [k, v] of Object.entries(c.outputs)) {
		lines.push(`  ${k}: ${v}`);
	}
	const renderCond = (key: string, list: ContractCondition[]) => {
		lines.push(`${key}:`);
		for (const cond of list) {
			lines.push(`  - id: ${cond.id}`);
			lines.push(`    expression: "${cond.expression}"`);
			if (cond.description) {
				lines.push(`    description: "${cond.description}"`);
			}
		}
	};
	renderCond("preconditions", c.preconditions);
	renderCond("postconditions", c.postconditions);
	renderCond("invariants", c.invariants);
	renderCond("fault_handling", c.fault_handling);
	return lines.join("\n");
});

const yamlHtml = computed(() => renderYaml(yamlText.value));
</script>

<template>
  <div v-if="!contract" class="empty">
    暂无契约
  </div>
  <div v-else class="contract-viewer">
    <!-- 契约元信息 -->
    <div class="contract-header">
      <div class="component-name">
        <span class="icon">📦</span>
        <span class="name">{{ contract.component }}</span>
      </div>
      <div class="component-desc">
        {{ contract.description }}
      </div>
    </div>

    <!-- 输入输出 -->
    <div class="io-section">
      <div class="io-block">
        <div class="io-title">
          📥 Inputs
        </div>
        <div v-for="[k, v] in inputEntries" :key="k" class="io-item">
          <code class="io-key">{{ k }}</code>
          <code class="io-type">{{ v }}</code>
        </div>
      </div>
      <div class="io-block">
        <div class="io-title">
          📤 Outputs
        </div>
        <div v-for="[k, v] in outputEntries" :key="k" class="io-item">
          <code class="io-key">{{ k }}</code>
          <code class="io-type">{{ v }}</code>
        </div>
      </div>
    </div>

    <!-- 条件分区 -->
    <div class="conditions-grid">
      <div v-for="section in sections" :key="section.key" class="condition-section">
        <div class="section-title" :style="{ borderLeftColor: section.color }">
          <span class="section-icon">{{ section.icon }}</span>
          <span>{{ section.title }}</span>
          <span class="count">{{ contract[section.key].length }}</span>
        </div>
        <div v-if="contract[section.key].length === 0" class="empty-section">
          （无）
        </div>
        <div
          v-for="cond in contract[section.key]"
          :key="cond.id"
          class="condition-item"
          :style="{ borderLeftColor: section.color }"
        >
          <div class="cond-row">
            <span class="con-badge" :style="{ backgroundColor: section.color }">{{ cond.id }}</span>
            <code class="cond-expr">
              <template v-for="(tok, ti) in parseTags(cond.expression)" :key="ti"><span
                  v-if="tok.type === 'text'"
                >{{ tok.value }}</span><span v-else class="con-tag">[{{ tok.value }}]</span></template>
            </code>
          </div>
          <div v-if="cond.description" class="cond-desc">
            {{ cond.description }}
          </div>
        </div>
      </div>
    </div>

    <!-- 原始 YAML -->
    <details class="yaml-block">
      <summary>📄 查看原始 YAML</summary>
      <pre class="yaml-pre" v-html="yamlHtml" />
    </details>
  </div>
</template>

<style scoped>
.contract-viewer {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  color: #d4d4d4;
  background: #1e1e1e;
  border-radius: 8px;
  overflow: hidden;
  padding: 12px;
}

.empty {
  padding: 24px;
  text-align: center;
  color: #6a6a6a;
  font-style: italic;
  background: #1e1e1e;
  border-radius: 8px;
  font-family: 'Consolas', monospace;
}

.contract-header {
  padding-bottom: 10px;
  border-bottom: 1px solid #3c3c3c;
  margin-bottom: 10px;
}

.component-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #d4d4d4;
}

.component-name .icon {
  font-size: 18px;
}

.component-desc {
  margin-top: 4px;
  color: #9d9d9d;
  font-size: 12px;
  font-family: 'Inter', sans-serif;
}

.io-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}

.io-block {
  background: #252526;
  padding: 8px 10px;
  border-radius: 6px;
}

.io-title {
  font-weight: 600;
  color: #4ec9b0;
  margin-bottom: 6px;
  font-size: 12px;
}

.io-item {
  display: flex;
  gap: 8px;
  align-items: baseline;
  margin: 2px 0;
}

.io-key {
  color: #569cd6;
}

.io-type {
  color: #ce9178;
  font-size: 12px;
  word-break: break-all;
}

.conditions-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 10px;
}

.condition-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: #d4d4d4;
  border-left: 3px solid;
  padding-left: 8px;
  font-size: 12px;
  font-family: 'Inter', sans-serif;
}

.section-icon {
  font-size: 14px;
}

.count {
  background: #3c3c3c;
  color: #d4d4d4;
  font-size: 10px;
  padding: 0 6px;
  border-radius: 8px;
  font-weight: 600;
}

.empty-section {
  color: #6a6a6a;
  font-style: italic;
  padding-left: 8px;
  font-size: 11px;
}

.condition-item {
  background: #252526;
  padding: 6px 8px;
  border-left: 3px solid;
  border-radius: 4px;
}

.cond-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  flex-wrap: wrap;
}

.con-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  color: #fff;
  letter-spacing: 0.3px;
  white-space: nowrap;
}

.cond-expr {
  flex: 1;
  color: #ce9178;
  word-break: break-all;
  font-size: 12px;
}

.con-tag {
  color: #c586c0;
  font-weight: 600;
}

.cond-desc {
  color: #9d9d9d;
  font-size: 11px;
  margin-top: 4px;
  font-family: 'Inter', sans-serif;
}

.yaml-block {
  margin-top: 8px;
  border-top: 1px solid #3c3c3c;
  padding-top: 8px;
}

.yaml-block summary {
  cursor: pointer;
  color: #4ec9b0;
  font-size: 12px;
  font-weight: 600;
  user-select: none;
}

.yaml-pre {
  background: #181818;
  padding: 10px;
  border-radius: 4px;
  margin: 6px 0 0;
  overflow-x: auto;
  color: #d4d4d4;
  font-size: 12px;
  line-height: 1.5;
}

:deep(.yaml-key) {
  color: #569cd6;
}

:deep(.yaml-str) {
  color: #ce9178;
}

:deep(.yaml-num) {
  color: #b5cea8;
}

:deep(.yaml-comment) {
  color: #6a9955;
  font-style: italic;
}
</style>
