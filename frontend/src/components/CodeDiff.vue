<script setup lang="ts">
/**
 * CodeDiff 代码 Diff 展示组件（Patch 1 查改解耦可视化）
 *
 * - 上下分栏展示 before/after 代码（移动端友好）
 * - 增加行绿色背景，删除行红色背景，未变行默认色
 * - 行号对齐
 * - 复用 CodeViewer 的 Tag 解析逻辑（[REQ-xxx] / [MISRA-Rule-x.x] / [CON-xxx]）
 *
 * 用于 RepairTimeline 中展开某轮修复时，对比修复前/后代码。
 */
import { computed } from "vue";
import { MISRA_RULE_DOCS } from "@/services/mockApi";

interface Props {
  /** 修复前代码 */
  before: string;
  /** 修复后代码 */
  after: string;
  /** 文件名（可选，用于显示标题） */
  filename?: string;
}

const props = defineProps<Props>();

/** Diff 行类型 */
type DiffOp = "equal" | "add" | "remove";

/** 一行 Diff 数据 */
interface DiffLine {
  op: DiffOp;
  /** before 中的行号（1-based），删除/未变行有值，新增行无 */
  beforeNo: number | null;
  /** after 中的行号（1-based），新增/未变行有值，删除行无 */
  afterNo: number | null;
  text: string;
}

/** 行内 Token：普通文本 / REQ 徽章 / MISRA 徽章 / CON 徽章 */
type Token =
  | { type: "text"; value: string }
  | { type: "req"; value: string }
  | { type: "misra"; value: string; doc: string }
  | { type: "con"; value: string };

/** 把一行代码解析为 token 列表 */
const parseLine = (text: string): Token[] => {
  const tokens: Token[] = [];
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

/**
 * 简单 LCS 行级 diff 算法
 * 输入两段代码（按行切分），输出 DiffLine 列表
 */
const computeDiff = (before: string, after: string): DiffLine[] => {
  const a = before.split("\n");
  const b = after.split("\n");
  const m = a.length;
  const n = b.length;

  // dp[i][j] = a[0..i) 与 b[0..j) 的 LCS 长度
  const dp: number[][] = Array.from({ length: m + 1 }, () =>
    new Array<number>(n + 1).fill(0),
  );
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (a[i - 1] === b[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // 回溯生成 diff
  const lines: DiffLine[] = [];
  let i = m;
  let j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      lines.unshift({
        op: "equal",
        beforeNo: i,
        afterNo: j,
        text: a[i - 1],
      });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      lines.unshift({
        op: "add",
        beforeNo: null,
        afterNo: j,
        text: b[j - 1],
      });
      j--;
    } else {
      lines.unshift({
        op: "remove",
        beforeNo: i,
        afterNo: null,
        text: a[i - 1],
      });
      i--;
    }
  }
  return lines;
};

/** Diff 行列表 */
const diffLines = computed<DiffLine[]>(() =>
  computeDiff(props.before, props.after),
);

/** 每行解析出的 token */
const lineTokens = computed<Token[][]>(() =>
  diffLines.value.map((l) => parseLine(l.text)),
);

/** 行 class */
const lineClass = (op: DiffOp): string => `diff-line diff-${op}`;

/** 统计 */
const stats = computed(() => {
  let add = 0;
  let remove = 0;
  for (const l of diffLines.value) {
    if (l.op === "add") add++;
    else if (l.op === "remove") remove++;
  }
  return { add, remove };
});
</script>
<template>
  <div class="code-diff">
    <!-- 头部：文件名 + 统计 -->
    <div class="diff-header">
      <div class="diff-filename">
        📄 {{ filename ?? "code.c" }}
      </div>
      <div class="diff-stats">
        <span class="stat-add">+{{ stats.add }}</span>
        <span class="stat-remove">-{{ stats.remove }}</span>
      </div>
    </div>

    <!-- Diff 主体 -->
    <div class="diff-body">
      <div
        v-for="(line, idx) in diffLines"
        :key="idx"
        :class="lineClass(line.op)"
      >
        <span class="line-no before-no">{{ line.beforeNo ?? "" }}</span>
        <span class="line-no after-no">{{ line.afterNo ?? "" }}</span>
        <span class="line-marker">
          <template v-if="line.op === 'add'">+</template>
          <template v-else-if="line.op === 'remove'">-</template>
          <template v-else> </template>
        </span>
        <span class="line-content">
          <template v-for="(tok, ti) in lineTokens[idx]" :key="ti">
            <span v-if="tok.type === 'text'" class="text-token">{{ tok.value }}</span>
            <span
              v-else-if="tok.type === 'req'"
              class="tag-badge req-badge"
              :title="`需求标签 ${tok.value}`"
            >[{{ tok.value }}]</span>
            <span
              v-else-if="tok.type === 'misra'"
              class="tag-badge misra-badge"
              :title="tok.doc"
            >[{{ tok.value }}]</span>
            <span
              v-else-if="tok.type === 'con'"
              class="tag-badge con-badge"
              :title="`契约条件 ${tok.value}`"
            >[{{ tok.value }}]</span>
          </template>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.code-diff {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.diff-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: #252526;
  border-bottom: 1px solid #3c3c3c;
}

.diff-filename {
  color: #4ec9b0;
  font-size: 12px;
  font-weight: 600;
}

.diff-stats {
  display: flex;
  gap: 8px;
  font-size: 11px;
  font-weight: 600;
}

.stat-add {
  color: #4ec9b0;
}

.stat-remove {
  color: #f44747;
}

.diff-body {
  overflow-x: auto;
  overflow-y: auto;
  max-height: 480px;
  padding: 4px 0;
}

.diff-line {
  display: flex;
  align-items: flex-start;
  padding: 0 8px;
  line-height: 1.6;
  white-space: pre;
}

.diff-line:hover {
  background: rgba(255, 255, 255, 0.04);
}

/* 三种 diff 行：未变 / 新增 / 删除 */
.diff-equal {
  background: transparent;
}

.diff-add {
  background: rgba(46, 160, 67, 0.18);
  box-shadow: inset 2px 0 0 #2ea043;
}

.diff-remove {
  background: rgba(248, 81, 73, 0.18);
  box-shadow: inset 2px 0 0 #f85149;
}

.line-no {
  flex-shrink: 0;
  width: 36px;
  text-align: right;
  margin-right: 6px;
  color: #6e7681;
  user-select: none;
  font-size: 11px;
}

.before-no {
  border-right: 1px solid #3c3c3c;
  padding-right: 6px;
}

.after-no {
  margin-right: 4px;
}

.line-marker {
  flex-shrink: 0;
  width: 14px;
  text-align: center;
  font-weight: 700;
  user-select: none;
}

.diff-add .line-marker {
  color: #2ea043;
}

.diff-remove .line-marker {
  color: #f85149;
}

.line-content {
  flex: 1;
  white-space: pre-wrap;
  min-width: 0;
}

.text-token {
  color: #d4d4d4;
}

/* 徽章样式 */
.tag-badge {
  display: inline-block;
  padding: 0 6px;
  margin: 0 2px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.req-badge {
  background: #1e6fb8;
  color: #d6e8ff;
  cursor: pointer;
}

.misra-badge {
  background: #b45309;
  color: #ffedd5;
  cursor: help;
}

.con-badge {
  background: #6b21a8;
  color: #f0e6ff;
  cursor: help;
}

.diff-body::-webkit-scrollbar {
  height: 8px;
  width: 8px;
}

.diff-body::-webkit-scrollbar-track {
  background: #1a1a1a;
}

.diff-body::-webkit-scrollbar-thumb {
  background: #3c3c3c;
  border-radius: 4px;
}
</style>