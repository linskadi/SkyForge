<script setup lang="ts">
/**
 * ScadeUpload SCADE 文件上传组件
 *
 * - 文件拖拽上传区域
 * - 支持 .lus / .txt 文件
 * - 上传后显示解析结果：
 *   - node 名称
 *   - 输入/输出变量列表
 *   - 等式列表
 *   - 转换后的自然语言需求
 *   - 转换后的契约 YAML
 * - "使用此需求"按钮：跳转到 Generate.vue 并填充需求
 */
import { ref, computed } from "vue";
import {
  UploadCloud,
  FileCode,
  Loader2,
  CheckCircle2,
  XCircle,
  ArrowRight,
} from "lucide-vue-next";
import { useRouter } from "vue-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type ScadeParseResult,
} from "@/services/mockApi";
import { getApi } from "@/services/apiSwitcher";

/** 路由实例 */
const router = useRouter();

/** 是否正在拖拽文件 */
const isDragging = ref<boolean>(false);
/** 上传中 */
const uploading = ref<boolean>(false);
/** 错误信息 */
const errorMsg = ref<string>("");
/** 解析结果 */
const parseResult = ref<ScadeParseResult | null>(null);
/** 文件输入引用 */
const fileInputRef = ref<HTMLInputElement | null>(null);

/** 校验文件类型 */
const isValidFile = (file: File): boolean => {
  const name = file.name.toLowerCase();
  return name.endsWith(".lus") || name.endsWith(".txt") || name.endsWith(".scade");
};

/** 处理文件选择 */
const handleFile = async (file: File) => {
  if (!isValidFile(file)) {
    errorMsg.value = `不支持的文件类型：${file.name}。仅支持 .lus / .txt / .scade 文件`;
    parseResult.value = null;
    return;
  }
  errorMsg.value = "";
  parseResult.value = null;
  uploading.value = true;
  try {
    const res = await getApi().uploadScade(file);
    parseResult.value = res;
  } catch (err) {
    console.error("[ScadeUpload] 上传失败：", err);
    errorMsg.value = err instanceof Error ? err.message : "上传失败";
  } finally {
    uploading.value = false;
  }
};

/** 拖拽进入 */
const onDragEnter = (e: DragEvent) => {
  e.preventDefault();
  if (e.dataTransfer?.types?.includes("Files")) {
    isDragging.value = true;
  }
};

/** 拖拽离开 */
const onDragLeave = (e: DragEvent) => {
  e.preventDefault();
  // 当离开容器时才设置为 false（检查 relatedTarget）
  const related = e.relatedTarget as Node | null;
  const current = e.currentTarget as Node | null;
  if (!related || !current?.contains(related)) {
    isDragging.value = false;
  }
};

/** 拖拽悬停 */
const onDragOver = (e: DragEvent) => {
  e.preventDefault();
  if (e.dataTransfer) {
    e.dataTransfer.dropEffect = "copy";
  }
};

/** 拖拽释放 */
const onDrop = (e: DragEvent) => {
  e.preventDefault();
  isDragging.value = false;
  const file = e.dataTransfer?.files?.[0];
  if (file) {
    handleFile(file);
  }
};

/** 点击选择文件 */
const onClick = () => {
  fileInputRef.value?.click();
};

/** 文件输入变化 */
const onFileChange = (e: Event) => {
  const input = e.target as HTMLInputElement;
  if (input.files && input.files.length > 0) {
    handleFile(input.files[0]);
  }
  // 重置 value 以便重复选择同一文件
  input.value = "";
};

/** 使用解析出的需求，跳转到 Generate 页面 */
const onUseRequirement = () => {
  if (!parseResult.value) return;
  // 通过 query 传递需求文本
  router.push({
    path: "/generate",
    query: {
      requirement: parseResult.value.natural_language_requirement,
      contract: parseResult.value.contract_yaml,
      from: "scade",
    },
  });
};

/** 变量总数 */
const totalVariables = computed(() => {
  if (!parseResult.value) return 0;
  return (
    parseResult.value.inputs.length +
    parseResult.value.outputs.length +
    parseResult.value.locals.length
  );
});
</script>

<template>
  <Card class="scade-upload-card">
    <CardHeader>
      <CardTitle class="card-title">
        <FileCode class="title-icon" />
        SCADE 模型上传
        <span class="title-hint">（支持 .lus / .txt / .scade 文件）</span>
      </CardTitle>
    </CardHeader>
    <CardContent>
      <!-- 拖拽上传区域 -->
      <div
        class="drop-zone"
        :class="{ dragging: isDragging, uploading: uploading }"
        @dragenter="onDragEnter"
        @dragleave="onDragLeave"
        @dragover="onDragOver"
        @drop="onDrop"
        @click="onClick"
      >
        <input
          ref="fileInputRef"
          type="file"
          accept=".lus,.txt,.scade"
          class="file-input"
          @change="onFileChange"
        >
        <div v-if="uploading" class="upload-state">
          <Loader2 class="animate-spin big-icon" />
          <p class="upload-text">正在上传并解析...</p>
        </div>
        <div v-else-if="isDragging" class="upload-state">
          <UploadCloud class="big-icon drag-icon" />
          <p class="upload-text">释放鼠标以上传</p>
        </div>
        <div v-else class="upload-state">
          <UploadCloud class="big-icon" />
          <p class="upload-text">
            <strong>点击选择文件</strong> 或拖拽文件到此处
          </p>
          <p class="upload-hint">支持 SCADE .lus / .txt / .scade 文件，最大 10MB</p>
        </div>
      </div>

      <!-- 错误提示 -->
      <div v-if="errorMsg" class="error-msg">
        <XCircle class="error-icon" />
        <span>{{ errorMsg }}</span>
      </div>

      <!-- 解析结果 -->
      <div v-if="parseResult" class="parse-result">
        <div class="result-header">
          <CheckCircle2 class="success-icon" />
          <span class="success-text">解析成功</span>
          <code class="node-name">{{ parseResult.node_name }}</code>
          <span class="file-info">源文件：{{ parseResult.source_file }}</span>
        </div>

        <!-- 变量列表 -->
        <div class="vars-section">
          <h4 class="section-title">
            📋 变量列表
            <span class="count-badge">{{ totalVariables }}</span>
          </h4>
          <div class="vars-grid">
            <div class="var-block inputs">
              <div class="var-title">📥 Inputs</div>
              <div v-for="(v, i) in parseResult.inputs" :key="`in-${i}`" class="var-item">
                <code class="var-name">{{ v.name }}</code>
                <code class="var-type">{{ v.type }}</code>
                <span v-if="v.description" class="var-desc">{{ v.description }}</span>
              </div>
              <div v-if="parseResult.inputs.length === 0" class="empty">(无)</div>
            </div>
            <div class="var-block outputs">
              <div class="var-title">📤 Outputs</div>
              <div v-for="(v, i) in parseResult.outputs" :key="`out-${i}`" class="var-item">
                <code class="var-name">{{ v.name }}</code>
                <code class="var-type">{{ v.type }}</code>
                <span v-if="v.description" class="var-desc">{{ v.description }}</span>
              </div>
              <div v-if="parseResult.outputs.length === 0" class="empty">(无)</div>
            </div>
            <div class="var-block locals">
              <div class="var-title">🔧 Locals</div>
              <div v-for="(v, i) in parseResult.locals" :key="`loc-${i}`" class="var-item">
                <code class="var-name">{{ v.name }}</code>
                <code class="var-type">{{ v.type }}</code>
                <span v-if="v.description" class="var-desc">{{ v.description }}</span>
              </div>
              <div v-if="parseResult.locals.length === 0" class="empty">(无)</div>
            </div>
          </div>
        </div>

        <!-- 等式列表 -->
        <div v-if="parseResult.equations.length > 0" class="eq-section">
          <h4 class="section-title">
            ⚖ 等式列表
            <span class="count-badge">{{ parseResult.equations.length }}</span>
          </h4>
          <ul class="eq-list">
            <li v-for="(eq, i) in parseResult.equations" :key="`eq-${i}`" class="eq-item">
              <code class="eq-lhs">{{ eq.lhs }}</code>
              <span class="eq-eq">=</span>
              <code class="eq-rhs">{{ eq.rhs }}</code>
            </li>
          </ul>
        </div>

        <!-- 转换后的自然语言需求 -->
        <div class="nl-section">
          <h4 class="section-title">📝 转换后的自然语言需求</h4>
          <div class="nl-content">
            {{ parseResult.natural_language_requirement }}
          </div>
        </div>

        <!-- 转换后的契约 YAML -->
        <details class="yaml-section">
          <summary>📄 转换后的契约 YAML</summary>
          <pre class="yaml-pre">{{ parseResult.contract_yaml }}</pre>
        </details>

        <!-- 使用此需求按钮 -->
        <div class="action-row">
          <Button @click="onUseRequirement">
            <ArrowRight />
            使用此需求生成代码
          </Button>
        </div>
      </div>
    </CardContent>
  </Card>
</template>

<style scoped>
.scade-upload-card {
  border-left: 3px solid #0891b2;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.title-icon {
  width: 18px;
  height: 18px;
  color: #0891b2;
}

.title-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--muted-foreground, #a1a1aa);
}

.drop-zone {
  border: 2px dashed var(--border, #d4d4d8);
  border-radius: 8px;
  background: var(--secondary, #f9fafb);
  padding: 32px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.drop-zone:hover {
  border-color: #0891b2;
  background: rgba(8, 145, 178, 0.04);
}

.drop-zone.dragging {
  border-color: #0891b2;
  background: rgba(8, 145, 178, 0.08);
  border-style: solid;
}

.drop-zone.uploading {
  cursor: progress;
  pointer-events: none;
}

.file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  overflow: hidden;
  pointer-events: none;
}

.upload-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.big-icon {
  width: 36px;
  height: 36px;
  color: var(--muted-foreground, #9ca3af);
}

.drag-icon {
  color: #0891b2;
}

.upload-text {
  margin: 0;
  font-size: 14px;
  color: var(--foreground, #1f2937);
}

.upload-text strong {
  color: #0891b2;
}

.upload-hint {
  margin: 0;
  font-size: 12px;
  color: var(--muted-foreground, #9ca3af);
}

.error-msg {
  margin-top: 12px;
  padding: 10px 12px;
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 6px;
  color: #991b1b;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.error-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.parse-result {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 12px;
  background: #f0fdf4;
  border: 1px solid #86efac;
  border-radius: 6px;
}

.success-icon {
  width: 18px;
  height: 18px;
  color: #10b981;
}

.success-text {
  font-size: 14px;
  font-weight: 600;
  color: #15803d;
}

.node-name {
  font-family: 'Consolas', monospace;
  background: #15803d;
  color: #f0fdf4;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.file-info {
  margin-left: auto;
  font-size: 12px;
  color: var(--muted-foreground, #6b7280);
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--foreground, #1f2937);
  margin: 0 0 8px 0;
}

.count-badge {
  background: var(--secondary, #f4f4f5);
  color: var(--foreground, #3f3f46);
  font-size: 10px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 8px;
}

.vars-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}

@media (max-width: 900px) {
  .vars-grid {
    grid-template-columns: 1fr;
  }
}

.var-block {
  background: #f8fafc;
  border: 1px solid var(--border, #e5e7eb);
  border-left: 3px solid;
  border-radius: 6px;
  padding: 8px 10px;
}

.var-block.inputs {
  border-left-color: #0EA5E9;
}

.var-block.outputs {
  border-left-color: #15803d;
}

.var-block.locals {
  border-left-color: #b45309;
}

.var-title {
  font-size: 12px;
  font-weight: 600;
  color: #4b5563;
  margin-bottom: 6px;
}

.var-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 12px;
  padding: 2px 0;
}

.var-name {
  font-family: 'Consolas', monospace;
  color: #1d4ed8;
  font-weight: 600;
}

.var-type {
  font-family: 'Consolas', monospace;
  color: #b45309;
  font-size: 11px;
  background: #fef3c7;
  padding: 1px 6px;
  border-radius: 3px;
}

.var-desc {
  font-size: 11px;
  color: var(--muted-foreground, #6b7280);
}

.empty {
  font-size: 11px;
  color: var(--muted-foreground, #9ca3af);
  font-style: italic;
}

.eq-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.eq-item {
  padding: 8px 10px;
  background: #1e1e1e;
  border-radius: 4px;
  font-family: 'Consolas', monospace;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.eq-lhs {
  color: #569cd6;
  font-weight: 600;
}

.eq-eq {
  color: #d4d4d4;
}

.eq-rhs {
  color: #ce9178;
  flex: 1;
}

.nl-section {
  background: #f0f9ff;
  border-left: 3px solid #0EA5E9;
  border-radius: 6px;
  padding: 12px 14px;
}

.nl-content {
  font-size: 13px;
  color: #1f2937;
  line-height: 1.6;
}

.yaml-section {
  background: #1e1e1e;
  border-radius: 6px;
  padding: 8px 12px;
}

.yaml-section summary {
  cursor: pointer;
  color: #4ec9b0;
  font-size: 13px;
  font-weight: 600;
  user-select: none;
}

.yaml-pre {
  margin: 8px 0 0;
  padding: 12px;
  background: #181818;
  border-radius: 4px;
  color: #d4d4d4;
  font-family: 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre;
}

.action-row {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border, #e5e7eb);
}

.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
