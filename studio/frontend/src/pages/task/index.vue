<script setup lang="ts">
import type AgentTerminal from "@/components/AgentTerminal.vue";
import ChatArea from "@/components/ChatArea.vue";
import MonacoCodeEditor from "@/components/MonacoCodeEditor.vue";
import TaskStatusBar from "@/components/task/TaskStatusBar.vue";
import TaskToolbar from "@/components/task/TaskToolbar.vue";
import {
	ResizableHandle,
	ResizablePanel,
	ResizablePanelGroup,
} from "@/components/ui/resizable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useTaskStore } from "@/stores/task";
/**
 * Task 页面 - Agent 工作流三面板布局
 * 布局：左侧 ChatArea + 右侧 Agent Terminal / Code Editor
 * 支持 4 Agent 流水线：REQ-Parser → CON-Gen → CODE-Gen → REPAIR
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

// ---- Props ----

const props = defineProps<{ task_id: string }>();

// ---- State ----

const taskStore = useTaskStore();

/** 右侧面板 Tab */
const activeTab = ref("terminal");

/** 代码内容 */
const codeContent = ref("");

/** 高亮的需求标签 */
const highlightReq = ref<string | null>(null);

/** 追溯矩阵 */
const traceability = ref<Record<string, number[]>>({});

/** 停止状态 */
const isStopping = ref(false);

/** Agent 状态 */
const activeAgent = ref<string | null>(null);
const completedAgents = ref<string[]>([]);

// ---- Terminal Ref ----
const terminalRef = ref<InstanceType<typeof AgentTerminal> | null>(null);

// ---- Computed ----

/** 合规检查通过率 */
const complianceRate = computed(() => {
	// TODO: 从消息中解析
	return null;
});

/** 数字孪生状态 */
const twinStatus = ref<"idle" | "running" | "passed" | "failed">("idle");

/** 文件数量 */
const fileCount = computed(() => taskStore.files?.length ?? 0);

// ---- Actions ----

async function handleStop() {
	isStopping.value = true;
	await taskStore.stopTask(props.task_id);
	isStopping.value = false;
}

// ---- Lifecycle ----

onMounted(async () => {
	await taskStore.loadTaskMessages(props.task_id);
	taskStore.connectWebSocket(props.task_id);
});

onBeforeUnmount(() => {
	taskStore.closeWebSocket();
});
</script>

<template>
  <div class="task-page">
    <!-- 顶部工具栏 -->
    <TaskToolbar
      :ws-status="taskStore.wsStatus"
      :is-running="taskStore.isRunning"
      :is-stopping="isStopping"
      :active-agent="activeAgent"
      :completed-agents="completedAgents"
      @stop="handleStop"
      @download="taskStore.downloadMessages"
    />

    <!-- 主内容区：左右分栏 -->
    <ResizablePanelGroup direction="horizontal" class="task-main">
      <!-- 左侧：聊天区（需求输入 + Agent 对话） -->
      <ResizablePanel :default-size="30" :min-size="20" class="panel-chat">
        <div class="panel-wrapper panel-chat-inner">
          <div class="panel-label">
            <svg class="panel-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            需求对话
          </div>
          <ChatArea :messages="taskStore.chatMessages" />
        </div>
      </ResizablePanel>

      <ResizableHandle class="panel-handle-v" />

      <!-- 右侧：Agent Terminal + Code Editor（上下分栏） -->
      <ResizablePanel :default-size="70" :min-size="30" class="panel-right">
        <ResizablePanelGroup direction="vertical" class="h-full">
          <!-- 上半：Agent Terminal（实时日志） -->
          <ResizablePanel :default-size="55" :min-size="20" class="panel-terminal">
            <div class="panel-wrapper panel-terminal-inner">
              <div class="panel-label panel-label-dark">
                <svg class="panel-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>
                </svg>
                Agent 实时日志
                <span v-if="activeAgent" class="agent-badge">{{ activeAgent }}</span>
              </div>
              <AgentTerminal
                ref="terminalRef"
                :use-mock="true"
                class="terminal-body"
              />
            </div>
          </ResizablePanel>

          <ResizableHandle class="panel-handle-h" />

          <!-- 下半：Code Editor（代码 + Diff） -->
          <ResizablePanel :default-size="45" :min-size="20" class="panel-editor">
            <div class="panel-wrapper panel-editor-inner">
              <Tabs v-model="activeTab" class="h-full flex flex-col">
                <div class="panel-label panel-label-editor">
                  <svg class="panel-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
                  </svg>
                  代码查看
                  <TabsList class="editor-tabs">
                    <TabsTrigger value="terminal" class="text-xs">代码</TabsTrigger>
                    <TabsTrigger value="diff" class="text-xs">Diff</TabsTrigger>
                  </TabsList>
                </div>
                <TabsContent value="terminal" class="flex-1 min-h-0">
                  <MonacoCodeEditor
                    :code="codeContent"
                    :read-only="true"
                    :traceability="traceability"
                    :highlight-req="highlightReq"
                    @req-click="(req) => highlightReq = highlightReq === req ? null : req"
                    class="h-full"
                  />
                </TabsContent>
                <TabsContent value="diff" class="flex-1 min-h-0">
                  <div class="empty-state">
                    <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
                      <polyline points="14 2 14 8 20 8"/>
                      <line x1="9" y1="15" x2="15" y2="15"/>
                    </svg>
                    <span>等待代码修复完成后显示 Diff 对比</span>
                  </div>
                </TabsContent>
              </Tabs>
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      </ResizablePanel>
    </ResizablePanelGroup>

    <!-- 底部状态栏 -->
    <TaskStatusBar
      :compliance-rate="complianceRate"
      :twin-status="twinStatus"
      :file-count="fileCount"
    />
  </div>
</template>

<style scoped>
/* ===== Page Layout ===== */
.task-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: hsl(var(--background));
}

.task-main {
  flex: 1;
  min-height: 0;
}

/* ===== Panel Wrappers ===== */
.panel-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* ===== Panel Labels (统一标签栏样式) ===== */
.panel-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: hsl(var(--muted-foreground));
  background: hsl(var(--muted));
  border-bottom: 1px solid hsl(var(--border));
  user-select: none;
  flex-shrink: 0;
}

.panel-label-dark {
  color: hsl(220, 10%, 60%);
  background: hsl(220, 20%, 13%);
  border-bottom-color: hsl(220, 18%, 18%);
}

.panel-label-editor {
  color: hsl(var(--muted-foreground));
  background: hsl(var(--background));
  border-bottom-color: hsl(var(--border));
}

.panel-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.agent-badge {
  margin-left: auto;
  padding: 1px 8px;
  border-radius: 9999px;
  font-size: 10px;
  font-weight: 700;
  background: hsl(var(--primary));
  color: hsl(var(--primary-foreground));
  animation: pulse-badge 2s ease-in-out infinite;
}

@keyframes pulse-badge {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* ===== Panel Inner Styles ===== */
.panel-chat-inner {
  background: hsl(var(--card));
}

.panel-terminal-inner {
  background: hsl(220, 25%, 7%);
}

.terminal-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.panel-editor-inner {
  background: hsl(var(--card));
}

/* ===== Panel Sizes ===== */
.panel-chat {
  min-width: 280px;
}

.panel-right {
  min-width: 400px;
}

.panel-terminal {
  min-height: 180px;
}

.panel-editor {
  min-height: 180px;
}

/* ===== Resize Handles ===== */
.panel-handle-v {
  width: 3px !important;
  background: transparent;
  transition: background 0.15s;
}
.panel-handle-v:hover,
.panel-handle-v[data-resize-handle-active] {
  background: hsl(var(--primary));
}

.panel-handle-h {
  height: 3px !important;
  background: transparent;
  transition: background 0.15s;
}
.panel-handle-h:hover,
.panel-handle-h[data-resize-handle-active] {
  background: hsl(var(--primary));
}

/* ===== Editor Tabs (嵌入标签栏) ===== */
.editor-tabs {
  margin-left: auto;
  height: 24px;
  padding: 0;
  background: transparent;
  border: none;
}

/* ===== Empty State ===== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 100%;
  color: hsl(var(--muted-foreground));
  font-size: 13px;
}

.empty-icon {
  width: 32px;
  height: 32px;
  opacity: 0.4;
}

/* ===== Responsive: Tablet (< 1024px) ===== */
@media (max-width: 1024px) {
  .panel-chat {
    min-width: 220px;
  }
  .panel-right {
    min-width: 320px;
  }
}

/* ===== Responsive: Mobile (< 768px) ===== */
@media (max-width: 768px) {
  .task-page {
    height: auto;
    min-height: 100vh;
    overflow: auto;
  }
  .task-main {
    flex-direction: column;
    min-height: 600px;
  }
  .panel-chat {
    min-width: unset;
    min-height: 300px;
  }
  .panel-right {
    min-width: unset;
    min-height: 400px;
  }
}
</style>
