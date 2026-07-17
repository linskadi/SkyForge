<script setup lang="ts">
import type { editor } from "monaco-editor";
/**
 * MonacoDiffEditor Diff 视图组件
 * 基于 Monaco Editor 的 DiffEditor，支持 side-by-side diff
 */
import { onMounted, ref, shallowRef, watch } from "vue";

interface Props {
	/** 修复前代码 */
	before: string;
	/** 修复后代码 */
	after: string;
	/** 文件名 */
	filename?: string;
	/** 语言 */
	language?: string;
}

const props = withDefaults(defineProps<Props>(), {
	filename: "code.c",
	language: "c",
});

const editorContainer = ref<HTMLDivElement | null>(null);
const diffEditorInstance = shallowRef<editor.IDiffEditor | null>(null);

/** 初始化 Monaco DiffEditor */
const initEditor = async () => {
	if (!editorContainer.value) return;

	const monaco = await import("monaco-editor");

	monaco.editor.defineTheme("skyforge-dark", {
		base: "vs-dark",
		inherit: true,
		rules: [],
		colors: {},
	});

	const diffEditor = monaco.editor.createDiffEditor(editorContainer.value, {
		theme: "skyforge-dark",
		readOnly: true,
		minimap: { enabled: false },
		fontSize: 13,
		fontFamily: "'Consolas', 'Courier New', monospace",
		renderSideBySide: true,
		enableSplitViewResizing: true,
		scrollbar: {
			vertical: "auto",
			horizontal: "auto",
			verticalScrollbarSize: 8,
			horizontalScrollbarSize: 8,
		},
		automaticLayout: true,
		padding: { top: 8, bottom: 8 },
	});

	const originalModel = monaco.editor.createModel(props.before, props.language);
	const modifiedModel = monaco.editor.createModel(props.after, props.language);

	diffEditor.setModel({
		original: originalModel,
		modified: modifiedModel,
	});

	diffEditorInstance.value = diffEditor;
};

/** 监听 before/after 变化 */
watch(
	() => [props.before, props.after],
	() => {
		if (!diffEditorInstance.value) return;
		const models = diffEditorInstance.value.getModel();
		if (!models) return;
		models.original.setValue(props.before);
		models.modified.setValue(props.after);
	},
);

onMounted(() => {
	initEditor();
});

/** 计算统计 */
const stats = ref({ add: 0, remove: 0 });

watch(
	() => [props.before, props.after],
	() => {
		const a = props.before.split("\n");
		const b = props.after.split("\n");
		// 简单估算：基于行数差异
		stats.value = {
			add: Math.max(0, b.length - a.length),
			remove: Math.max(0, a.length - b.length),
		};
	},
	{ immediate: true },
);
</script>

<template>
  <div class="diff-editor-wrapper">
    <div class="diff-header">
      <div class="diff-filename">
        📄 {{ filename }}
      </div>
      <div class="diff-stats">
        <span class="stat-add">+{{ stats.add }}</span>
        <span class="stat-remove">-{{ stats.remove }}</span>
      </div>
    </div>
    <div ref="editorContainer" class="diff-container" />
  </div>
</template>

<style scoped>
.diff-editor-wrapper {
  width: 100%;
  height: 100%;
  border-radius: 8px;
  overflow: hidden;
  background: #1e1e1e;
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
  flex-shrink: 0;
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

.diff-container {
  flex: 1;
  min-height: 0;
}
</style>
