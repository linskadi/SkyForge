<script setup lang="ts">
/**
 * HILPanel 人机协作审批面板组件
 *
 * - 待审批列表（每项一个卡片）：
 *   - 检查点名称（需求审查/契约审查/代码审查/最终审查）
 *   - 内容预览
 *   - 批准/拒绝按钮 + 评论输入框
 * - 审批历史列表
 * - 超时倒计时
 *
 * 放在 Generate.vue 侧边栏或独立页面
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  ClipboardList,
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  History,
  AlertCircle,
} from "lucide-vue-next";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  mockGetHILHistory,
  type HILApproval,
  type HILHistoryItem,
  type HILCheckpointType,
} from "@/services/mockApi";
import { getApi } from "@/services/apiSwitcher";

/** 待审批列表 */
const pendingList = ref<HILApproval[]>([]);
/** 审批历史 */
const historyList = ref<HILHistoryItem[]>([]);
/** 加载状态 */
const loading = ref<boolean>(false);
/** 操作中状态 */
const actionLoading = ref<Record<string, boolean>>({});
/** 错误信息 */
const errorMsg = ref<string>("");
/** 展开的审批项 ID */
const expandedId = ref<string>("");
/** 当前激活的评论框 ID */
const commentMap = ref<Record<string, string>>({});
/** 是否显示历史列表 */
const showHistory = ref<boolean>(false);
/** 当前时间戳（用于倒计时计算，每秒更新） */
const now = ref<number>(Date.now());
let timer: ReturnType<typeof setInterval> | null = null;

/** 检查点图标映射 */
const checkpointIconMap: Record<HILCheckpointType, string> = {
  requirement_review: "📝",
  contract_review: "📋",
  code_review: "💻",
  final_review: "🏁",
};

/** 检查点颜色映射 */
const checkpointColorMap: Record<HILCheckpointType, string> = {
  requirement_review: "#0EA5E9",
  contract_review: "#8B5CF6",
  code_review: "#15803d",
  final_review: "#dc2626",
};

/** 加载待审批列表 */
const loadPending = async () => {
  loading.value = true;
  errorMsg.value = "";
  try {
    // 待审批列表通过 apiSwitcher 调用，审批历史仍用 mock（不在切换范围）
    const [pending, history] = await Promise.all([
      getApi().getPendingApprovals(),
      mockGetHILHistory(),
    ]);
    pendingList.value = pending;
    historyList.value = history;
  } catch (err) {
    console.error("[HILPanel] 加载失败：", err);
    errorMsg.value = err instanceof Error ? err.message : "加载失败";
  } finally {
    loading.value = false;
  }
};

/** 切换展开 */
const toggleExpand = (id: string) => {
  if (expandedId.value === id) {
    expandedId.value = "";
  } else {
    expandedId.value = id;
  }
};

/** 获取评论 */
const getComment = (id: string): string => {
  return commentMap.value[id] ?? "";
};

/** 设置评论 */
const setComment = (id: string, value: string) => {
  commentMap.value[id] = value;
};

/** 批准 */
const onApprove = async (item: HILApproval) => {
  actionLoading.value = { ...actionLoading.value, [item.request_id]: true };
  try {
    const comments = getComment(item.request_id);
    await getApi().approve(item.request_id, comments);
    await loadPending();
    showHistory.value = true;
  } catch (err) {
    console.error("[HILPanel] 批准失败：", err);
    errorMsg.value = err instanceof Error ? err.message : "批准失败";
  } finally {
    actionLoading.value = { ...actionLoading.value, [item.request_id]: false };
  }
};

/** 拒绝 */
const onReject = async (item: HILApproval) => {
  const comments = getComment(item.request_id);
  if (!comments.trim()) {
    errorMsg.value = "拒绝时必须填写理由";
    return;
  }
  actionLoading.value = { ...actionLoading.value, [item.request_id]: true };
  try {
    await getApi().reject(item.request_id, comments);
    await loadPending();
    showHistory.value = true;
  } catch (err) {
    console.error("[HILPanel] 拒绝失败：", err);
    errorMsg.value = err instanceof Error ? err.message : "拒绝失败";
  } finally {
    actionLoading.value = { ...actionLoading.value, [item.request_id]: false };
  }
};

/** 计算剩余时间 */
const remainingTime = (deadline: number): { text: string; urgent: boolean; expired: boolean } => {
  const diff = deadline - now.value;
  if (diff <= 0) {
    return { text: "已超时", urgent: true, expired: true };
  }
  const minutes = Math.floor(diff / 60000);
  const seconds = Math.floor((diff % 60000) / 1000);
  return {
    text: `${minutes}m ${seconds}s`,
    urgent: diff < 5 * 60 * 1000, // 小于 5 分钟
    expired: false,
  };
};

/** 格式化时间 */
const formatTime = (ts: number): string => {
  const d = new Date(ts);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

/** 待审批数量 */
const pendingCount = computed(() => pendingList.value.length);

onMounted(() => {
  loadPending();
  timer = setInterval(() => {
    now.value = Date.now();
  }, 1000);
});

onBeforeUnmount(() => {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
});
</script>

<template>
  <Card class="hil-panel-card">
    <CardHeader>
      <CardTitle class="card-title">
        <ClipboardList class="title-icon" />
        HIL 人机协作审批
        <span class="title-hint">
          待审批
          <span class="count-badge">{{ pendingCount }}</span>
        </span>
        <Button variant="ghost" size="sm" class="refresh-btn" :disabled="loading" @click="loadPending">
          <RefreshCw v-if="loading" class="animate-spin" />
          <RefreshCw v-else />
          刷新
        </Button>
      </CardTitle>
    </CardHeader>
    <CardContent>
      <div v-if="errorMsg" class="error-msg">
        <AlertCircle class="error-icon" />
        <span>{{ errorMsg }}</span>
        <button type="button" class="retry-btn" @click="loadPending">重试</button>
      </div>

      <div v-if="loading && pendingList.length === 0" class="loading-state">
        <Loader2 class="animate-spin" />
        <p>正在加载待审批列表...</p>
      </div>

      <div v-else-if="pendingList.length === 0" class="empty-state">
        <CheckCircle2 class="success-icon" />
        <p>暂无待审批项</p>
      </div>

      <!-- 待审批列表 -->
      <div v-else class="pending-list">
        <div
          v-for="item in pendingList"
          :key="item.request_id"
          class="approval-card"
          :style="{ borderLeftColor: checkpointColorMap[item.checkpoint] }"
        >
          <!-- 卡片头部 -->
          <div class="card-header-row" @click="toggleExpand(item.request_id)">
            <span class="checkpoint-icon">{{ checkpointIconMap[item.checkpoint] }}</span>
            <div class="card-info">
              <div class="card-title-row">
                <span class="checkpoint-name">{{ item.checkpoint_name }}</span>
                <code class="request-id">{{ item.request_id }}</code>
              </div>
              <div class="card-preview">{{ item.content_preview }}</div>
            </div>
            <!-- 倒计时 -->
            <div class="countdown" :class="{ urgent: remainingTime(item.deadline).urgent, expired: remainingTime(item.deadline).expired }">
              <Clock class="clock-icon" />
              <span>{{ remainingTime(item.deadline).text }}</span>
            </div>
            <component
              :is="expandedId === item.request_id ? ChevronDown : ChevronRight"
              class="chevron"
            />
          </div>

          <!-- 展开后内容 -->
          <div v-if="expandedId === item.request_id" class="card-detail">
            <div v-if="item.content_detail" class="detail-content">
              <pre>{{ item.content_detail }}</pre>
            </div>
            <div class="meta-row">
              <span>提交时间：{{ formatTime(item.submitted_at) }}</span>
              <span>截止时间：{{ formatTime(item.deadline) }}</span>
            </div>
            <textarea
              class="comment-input"
              :value="getComment(item.request_id)"
              @input="setComment(item.request_id, ($event.target as HTMLTextAreaElement).value)"
              placeholder="请输入审批评论（拒绝时必填）..."
              rows="3"
            />
            <div class="action-row">
              <Button
                :disabled="actionLoading[item.request_id]"
                @click="onApprove(item)"
              >
                <CheckCircle2 v-if="!actionLoading[item.request_id]" />
                <Loader2 v-else class="animate-spin" />
                批准
              </Button>
              <Button
                variant="outline"
                :disabled="actionLoading[item.request_id]"
                @click="onReject(item)"
              >
                <XCircle />
                拒绝
              </Button>
            </div>
          </div>
        </div>
      </div>

      <!-- 审批历史 -->
      <div class="history-section">
        <div class="history-header" @click="showHistory = !showHistory">
          <History class="history-icon" />
          <span class="history-title">审批历史</span>
          <span class="count-badge">{{ historyList.length }}</span>
          <component
            :is="showHistory ? ChevronDown : ChevronRight"
            class="chevron"
          />
        </div>
        <div v-if="showHistory" class="history-list">
          <div v-if="historyList.length === 0" class="empty-state small">
            <p>暂无审批历史</p>
          </div>
          <div
            v-for="h in historyList"
            :key="h.request_id"
            class="history-item"
            :class="{ approved: h.status === 'approved', rejected: h.status === 'rejected' }"
          >
            <div class="history-row">
              <span class="history-icon">{{ checkpointIconMap[h.checkpoint] }}</span>
              <span class="history-name">{{ h.checkpoint_name }}</span>
              <code class="request-id">{{ h.request_id }}</code>
              <span class="status-badge" :class="h.status">
                {{ h.status === "approved" ? "✅ 已批准" : "❌ 已拒绝" }}
              </span>
              <span v-if="h.reviewed_at" class="reviewed-time">{{ formatTime(h.reviewed_at) }}</span>
            </div>
            <div v-if="h.comments" class="history-comments">
              评论：{{ h.comments }}
            </div>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>

<style scoped>
.hil-panel-card {
  border-left: 3px solid #ea580c;
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
  color: #ea580c;
}

.title-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--muted-foreground, #a1a1aa);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 18px;
  padding: 0 6px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 9px;
  background: #ea580c;
  color: #fff;
}

.refresh-btn {
  margin-left: auto;
  font-size: 12px;
}

.refresh-btn :deep(svg) {
  width: 14px;
  height: 14px;
}

.error-msg {
  padding: 10px 12px;
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 6px;
  color: #991b1b;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.error-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.retry-btn {
  margin-left: auto;
  padding: 4px 10px;
  background: #fff;
  border: 1px solid #fca5a5;
  border-radius: 4px;
  color: #991b1b;
  font-size: 12px;
  cursor: pointer;
}

.retry-btn:hover {
  background: #fee2e2;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px;
  color: var(--muted-foreground, #9ca3af);
  font-size: 13px;
  text-align: center;
}

.empty-state.small {
  padding: 12px;
}

.loading-state .animate-spin,
.empty-state .success-icon {
  width: 24px;
  height: 24px;
}

.empty-state .success-icon {
  color: #10b981;
}

.pending-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.approval-card {
  background: #fff;
  border: 1px solid var(--border, #e5e7eb);
  border-left: 3px solid;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.15s;
}

.approval-card:hover {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.card-header-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
  user-select: none;
}

.checkpoint-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.card-info {
  flex: 1;
  min-width: 0;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.checkpoint-name {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.request-id {
  font-family: 'Consolas', monospace;
  font-size: 11px;
  color: #6b7280;
  background: #f3f4f6;
  padding: 1px 6px;
  border-radius: 3px;
}

.card-preview {
  font-size: 12px;
  color: var(--muted-foreground, #6b7280);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.countdown {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  font-family: 'Consolas', monospace;
  background: #f0fdf4;
  color: #15803d;
  border: 1px solid #bbf7d0;
  flex-shrink: 0;
}

.countdown.urgent {
  background: #fef3c7;
  color: #b45309;
  border-color: #fde68a;
}

.countdown.expired {
  background: #fee2e2;
  color: #b91c1c;
  border-color: #fecaca;
}

.clock-icon {
  width: 12px;
  height: 12px;
}

.chevron {
  width: 14px;
  height: 14px;
  color: var(--muted-foreground, #9ca3af);
  flex-shrink: 0;
}

.card-detail {
  padding: 0 12px 12px 12px;
  border-top: 1px solid var(--border, #e5e7eb);
  margin-top: 0;
  padding-top: 10px;
}

.detail-content {
  background: #1e1e1e;
  border-radius: 4px;
  padding: 10px;
  margin-bottom: 8px;
  overflow-x: auto;
}

.detail-content pre {
  margin: 0;
  color: #d4d4d4;
  font-family: 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}

.meta-row {
  display: flex;
  gap: 16px;
  font-size: 11px;
  color: var(--muted-foreground, #6b7280);
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.comment-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border, #d4d4d8);
  border-radius: 4px;
  font-size: 12px;
  font-family: inherit;
  background: var(--background, #fff);
  color: var(--foreground, #1f2937);
  resize: vertical;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}

.comment-input:focus {
  border-color: #ea580c;
  box-shadow: 0 0 0 2px rgba(234, 88, 12, 0.15);
}

.action-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.history-section {
  margin-top: 16px;
  border-top: 1px solid var(--border, #e5e7eb);
  padding-top: 12px;
}

.history-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  font-weight: 600;
  color: var(--foreground, #1f2937);
}

.history-icon {
  width: 16px;
  height: 16px;
  color: #6b7280;
}

.history-title {
  flex: 1;
}

.history-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.history-item {
  padding: 8px 10px;
  background: #f9fafb;
  border-left: 3px solid #d1d5db;
  border-radius: 4px;
  font-size: 12px;
}

.history-item.approved {
  border-left-color: #10b981;
  background: #f0fdf4;
}

.history-item.rejected {
  border-left-color: #ef4444;
  background: #fef2f2;
}

.history-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.history-icon {
  font-size: 14px;
}

.history-name {
  font-weight: 600;
  color: #1f2937;
}

.status-badge {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 600;
  margin-left: auto;
}

.status-badge.approved {
  background: #dcfce7;
  color: #15803d;
}

.status-badge.rejected {
  background: #fee2e2;
  color: #b91c1c;
}

.reviewed-time {
  font-family: 'Consolas', monospace;
  font-size: 10px;
  color: var(--muted-foreground, #6b7280);
}

.history-comments {
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px dashed var(--border, #e5e7eb);
  font-size: 11px;
  color: var(--muted-foreground, #6b7280);
  line-height: 1.5;
}

.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
