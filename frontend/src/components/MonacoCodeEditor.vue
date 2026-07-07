<script setup lang="ts">
/**
 * MonacoCodeEditor 代码编辑器组件
 * 基于 Monaco Editor，支持 C 语言语法高亮、只读/编辑模式、REQ/MISRA/CON 标签装饰
 */
import { ref, watch, onMounted, shallowRef } from "vue";
import type { editor } from "monaco-editor";
import { parseInlineTags } from "@/utils/tagParser";

interface Props {
  /** 代码内容 */
  code: string;
  /** 语言 */
  language?: string;
  /** 是否只读 */
  readOnly?: boolean;
  /** 追溯矩阵：REQ-xxx -> 行号列表 */
  traceability?: Record<string, number[]>;
  /** 高亮的需求标签 */
  highlightReq?: string | null;
}

const props = withDefaults(defineProps<Props>(), {
  language: "c",
  readOnly: true,
  traceability: undefined,
  highlightReq: null,
});

const emit = defineEmits<{
  (e: "update:code", value: string): void;
  (e: "reqClick", value: string): void;
}>();

const editorContainer = ref<HTMLDivElement | null>(null);
const editorInstance = shallowRef<editor.IStandaloneCodeEditor | null>(null);
const monacoInstance = shallowRef<typeof import("monaco-editor") | null>(null);

/** REQ 标签装饰 ID 列表 */
let reqDecorations: string[] = [];

/** 初始化 Monaco Editor */
const initEditor = async () => {
  if (!editorContainer.value) return;

  const monaco = await import("monaco-editor");
  monacoInstance.value = monaco;

  // 注册 C 语言自定义主题（标签高亮色）
  monaco.editor.defineTheme("skyforge-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {},
  });

  const editor = monaco.editor.create(editorContainer.value, {
    value: props.code,
    language: props.language,
    theme: "skyforge-dark",
    readOnly: props.readOnly,
    minimap: { enabled: false },
    fontSize: 13,
    fontFamily: "'Consolas', 'Courier New', monospace",
    lineNumbers: "on",
    scrollBeyondLastLine: false,
    padding: { top: 8, bottom: 8 },
    renderLineHighlight: "gutter",
    overviewRulerLanes: 0,
    scrollbar: {
      vertical: "auto",
      horizontal: "auto",
      verticalScrollbarSize: 8,
      horizontalScrollbarSize: 8,
    },
    automaticLayout: true,
  });

  editorInstance.value = editor;

  // 监听内容变化
  editor.onDidChangeModelContent(() => {
    if (!props.readOnly) {
      emit("update:code", editor.getValue());
    }
  });

  // 注入点击 REQ 标签的逻辑
  editor.onMouseDown((e) => {
    const position = e.target.position;
    if (!position) return;
    const lineContent = editor.getModel()?.getLineContent(position.lineNumber) ?? "";
    const tokens = parseInlineTags(lineContent);
    let col = 0;
    for (const token of tokens) {
      if (token.type === "req") {
        const startCol = lineContent.indexOf(token.value, col) - 1; // -1 for [
        const endCol = startCol + token.value.length + 2; // +2 for [ ]
        if (position.column >= startCol && position.column <= endCol) {
          emit("reqClick", token.value);
          break;
        }
      }
      col += token.value.length;
    }
  });

  updateDecorations();
};

/** 更新 REQ 标签装饰（黄色高亮关联行） */
const updateDecorations = () => {
  if (!editorInstance.value || !monacoInstance.value) return;
  const monaco = monacoInstance.value;
  const editor = editorInstance.value;
  const model = editor.getModel();
  if (!model) return;

  const newDecorations: editor.IModelDeltaDecoration[] = [];

  if (props.highlightReq && props.traceability?.[props.highlightReq]) {
    const lineNumbers = props.traceability[props.highlightReq];
    for (const lineNo of lineNumbers) {
      if (lineNo >= 1 && lineNo <= model.getLineCount()) {
        newDecorations.push({
          range: new monaco.Range(lineNo, 1, lineNo, model.getLineMaxColumn(lineNo)),
          options: {
            isWholeLine: true,
            className: "req-highlight-line",
            overviewRuler: {
              color: "#ffd54f",
              position: monaco.editor.OverviewRulerLane.Left,
            },
          },
        });
      }
    }
  }

  reqDecorations = editor.deltaDecorations(reqDecorations, newDecorations);
};

/** 监听代码变化 */
watch(
  () => props.code,
  (newCode) => {
    const model = editorInstance.value?.getModel();
    if (model && newCode !== model.getValue()) {
      model.setValue(newCode);
    }
  },
);

/** 监听高亮需求变化 */
watch(
  () => props.highlightReq,
  () => updateDecorations(),
);

onMounted(() => {
  initEditor();
});
</script>

<template>
  <div class="monaco-editor-wrapper">
    <div ref="editorContainer" class="editor-container" />
  </div>
</template>

<style scoped>
.monaco-editor-wrapper {
  width: 100%;
  height: 100%;
  border-radius: 8px;
  overflow: hidden;
  background: #1e1e1e;
}

.editor-container {
  width: 100%;
  height: 100%;
}
</style>

<style>
/* REQ 行高亮样式（非 scoped，Monaco 注入到全局） */
.req-highlight-line {
  background: rgba(255, 213, 79, 0.15) !important;
  box-shadow: inset 3px 0 0 #ffd54f;
}
</style>
