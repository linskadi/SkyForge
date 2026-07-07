<script setup lang="ts">
/**
 * ReportDownload DO-178C 报告下载组件
 *
 * - 顶部：报告生成按钮（点击调用 mockGenerateReport）
 * - 生成中：loading 动画
 * - 生成完成：
 *   - 概要卡片：追溯矩阵条目数 / DO-178C 目标通过率 / 仿真结果摘要
 *   - 预览区域：iframe 展示 HTML 报告
 *   - 下载按钮：下载 HTML 文件
 *   - 打印按钮：window.print()
 */
import { ref, computed } from "vue";
import { Loader2, FileText, Download, Printer, Sparkles } from "lucide-vue-next";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type GenerateResult,
  type ReportResult,
} from "@/services/mockApi";
import { getApi } from "@/services/apiSwitcher";

interface Props {
  /** 生成结果（用于填充报告内容） */
  result: GenerateResult | null;
}

const props = defineProps<Props>();

/** 报告状态：idle / generating / done / error */
const status = ref<"idle" | "generating" | "done" | "error">("idle");
/** 报告内容 */
const report = ref<ReportResult | null>(null);
/** 错误信息 */
const errorMsg = ref<string>("");
/** iframe 预览 src（用 blob URL） */
const previewSrc = ref<string>("");
/** iframe 引用 */
const iframeRef = ref<HTMLIFrameElement | null>(null);

/** 是否可生成报告 */
const canGenerate = computed(() => props.result !== null && status.value !== "generating");

/** 点击生成报告 */
const onGenerate = async () => {
  if (!props.result) return;
  status.value = "generating";
  report.value = null;
  errorMsg.value = "";
  // 释放旧的 blob URL
  if (previewSrc.value) {
    URL.revokeObjectURL(previewSrc.value);
    previewSrc.value = "";
  }
  try {
    const res = await getApi().generateReport(props.result);
    report.value = res;
    // 构造 blob URL 用于 iframe 预览
    const blob = new Blob([res.html], { type: "text/html" });
    previewSrc.value = URL.createObjectURL(blob);
    status.value = "done";
  } catch (err) {
    console.error("[ReportDownload] 生成报告失败：", err);
    errorMsg.value = err instanceof Error ? err.message : "未知错误";
    status.value = "error";
  }
};

/** 下载 HTML 文件 */
const onDownload = () => {
  if (!report.value) return;
  const blob = new Blob([report.value.html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${report.value.report_id}.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

/** 打印报告（在 iframe 内打印，避免影响主页面） */
const onPrint = () => {
  if (iframeRef.value?.contentWindow) {
    iframeRef.value.contentWindow.focus();
    iframeRef.value.contentWindow.print();
  } else {
    // 后备方案：新窗口打印
    if (!previewSrc.value) return;
    const win = window.open(previewSrc.value, "_blank");
    if (win) {
      win.onload = () => win.print();
    }
  }
};

/** 通过率百分比 */
const passRatePercent = computed(() => {
  if (!report.value) return 0;
  return Math.round(report.value.summary.pass_rate * 100);
});

/** 通过率条颜色 */
const passRateColor = computed(() => {
  if (!report.value) return "#6b7280";
  const rate = report.value.summary.pass_rate;
  if (rate >= 0.9) return "#15803d";
  if (rate >= 0.7) return "#f59e0b";
  return "#dc2626";
});
</script>

<template>
  <div class="report-download">
    <!-- 顶部操作区 -->
    <Card class="action-card">
      <CardHeader>
        <CardTitle class="card-title">
          📄 DO-178C 报告生成
          <span class="title-hint">（适航合规报告，可下载 / 打印）</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div class="action-row">
          <Button :disabled="!canGenerate" @click="onGenerate">
            <Loader2 v-if="status === 'generating'" class="animate-spin" />
            <Sparkles v-else />
            生成 DO-178C 报告
          </Button>
          <Button v-if="status === 'done' && report" variant="outline" @click="onDownload">
            <Download />
            下载 HTML
          </Button>
          <Button v-if="status === 'done' && report" variant="outline" @click="onPrint">
            <Printer />
            打印
          </Button>
          <span v-if="status === 'generating'" class="status-text generating">
            正在生成报告...
          </span>
          <span v-else-if="status === 'done'" class="status-text done">
            ✅ 报告已生成
          </span>
          <span v-else-if="status === 'error'" class="status-text error">
            ❌ {{ errorMsg }}
          </span>
          <span v-else-if="!result" class="status-text muted">
            请先生成代码后再生成报告
          </span>
        </div>
      </CardContent>
    </Card>

    <!-- 报告概要卡片 -->
    <div v-if="status === 'done' && report" class="summary-grid">
      <div class="summary-card">
        <div class="summary-icon">📋</div>
        <div class="summary-info">
          <div class="summary-value">{{ report.summary.traceability_entries }}</div>
          <div class="summary-label">追溯矩阵条目</div>
        </div>
      </div>
      <div class="summary-card">
        <div class="summary-icon">🎯</div>
        <div class="summary-info">
          <div class="summary-value" :style="{ color: passRateColor }">
            {{ report.summary.passed_objectives }}/{{ report.summary.total_objectives }}
          </div>
          <div class="summary-label">DO-178C 目标</div>
          <div class="pass-bar">
            <div class="pass-bar-fill" :style="{ width: passRatePercent + '%', backgroundColor: passRateColor }" />
          </div>
        </div>
      </div>
      <div class="summary-card">
        <div class="summary-icon">🧪</div>
        <div class="summary-info">
          <div class="summary-value">{{ report.summary.simulation_summary }}</div>
          <div class="summary-label">仿真结果摘要</div>
        </div>
      </div>
      <div class="summary-card">
        <div class="summary-icon">⚠</div>
        <div class="summary-info">
          <div class="summary-value">{{ report.summary.misra_violations }}</div>
          <div class="summary-label">MISRA 违规数</div>
        </div>
      </div>
    </div>

    <!-- 报告预览 iframe -->
    <Card v-if="status === 'done' && report" class="preview-card">
      <CardHeader>
        <CardTitle class="card-title">
          <FileText class="icon" />
          报告预览
          <span class="title-hint">（{{ report.report_id }}）</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <iframe
          ref="iframeRef"
          :src="previewSrc"
          class="report-iframe"
          title="DO-178C Report Preview"
        />
      </CardContent>
    </Card>

    <!-- 空状态提示 -->
    <div v-if="status === 'idle'" class="empty-tip">
      <FileText class="empty-icon" />
      <p>点击"生成 DO-178C 报告"按钮开始</p>
    </div>
  </div>
</template>

<style scoped>
.report-download {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.action-card :deep(.card-title) {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--muted-foreground, #a1a1aa);
}

.action-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.status-text {
  font-size: 13px;
  font-weight: 500;
}

.status-text.generating { color: #0EA5E9; }
.status-text.done { color: #15803d; }
.status-text.error { color: #dc2626; }
.status-text.muted { color: var(--muted-foreground, #71717a); }

.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.summary-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--background, #fff);
  border: 1px solid var(--border, #e5e7eb);
  border-left: 3px solid #0EA5E9;
  border-radius: 8px;
}

.summary-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.summary-info {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.summary-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--foreground, #1f2937);
  word-break: break-word;
}

.summary-label {
  font-size: 11px;
  color: var(--muted-foreground, #6b7280);
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-top: 2px;
}

.pass-bar {
  width: 100%;
  height: 4px;
  background: #e5e7eb;
  border-radius: 2px;
  overflow: hidden;
  margin-top: 4px;
}

.pass-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.preview-card :deep(.card-title) {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.preview-card .icon {
  width: 18px;
  height: 18px;
  color: #0EA5E9;
}

.report-iframe {
  width: 100%;
  height: 600px;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
  background: #fff;
}

.empty-tip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 16px;
  color: var(--muted-foreground, #9ca3af);
  text-align: center;
  background: var(--secondary, #f9fafb);
  border-radius: 8px;
  border: 1px dashed var(--border, #d4d4d8);
}

.empty-icon {
  width: 32px;
  height: 32px;
  color: #9ca3af;
}

.empty-tip p {
  margin: 0;
  font-size: 13px;
}
</style>
