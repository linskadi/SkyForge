<script setup lang="ts">
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { getApi } from "@/services/apiSwitcher";
import {
	type LLMStatus as LLMStatusType,
	mockSelectModel,
} from "@/services/mockApi";
import {
	Activity,
	CheckCircle2,
	Cpu,
	Database,
	Loader2,
	XCircle,
	Zap,
} from "lucide-vue-next";
/**
 * LLMStatus LLM 状态面板组件
 *
 * - 状态卡片：LM Studio 连接状态（绿/红圆点 + 文字）
 * - 当前使用模式（Mock / 真实 LLM）
 * - 已加载模型列表（Badge）
 * - 切换按钮：Mock ↔ 真实 LLM
 * - 模型选择下拉框（如果多个模型可用）
 * - 响应时间统计（最近调用）
 *
 * 放在 Generate.vue 顶部或侧边栏
 */
import { computed, onMounted, ref } from "vue";

/** LLM 状态 */
const status = ref<LLMStatusType | null>(null);
/** 加载状态 */
const loading = ref<boolean>(false);
/** 切换中状态 */
const switching = ref<boolean>(false);
/** 错误信息 */
const errorMsg = ref<string>("");

/** 当前选中的模型 ID（本地） */
const selectedModelId = ref<string>("");

/** 加载状态 */
const loadStatus = async () => {
	loading.value = true;
	errorMsg.value = "";
	try {
		const res = await getApi().getLLMStatus();
		status.value = res;
		selectedModelId.value = res.current_model ?? res.models[0]?.id ?? "";
	} catch (err) {
		console.error("[LLMStatus] 加载状态失败：", err);
		errorMsg.value = err instanceof Error ? err.message : "加载失败";
	} finally {
		loading.value = false;
	}
};

/** 切换 LLM 开关 */
const onSwitchLLM = async (val: boolean) => {
	switching.value = true;
	try {
		// 通过 apiSwitcher 切换 LLM（接口返回 void，需重新拉取状态）
		await getApi().switchLLM(val);
		await loadStatus();
	} catch (err) {
		console.error("[LLMStatus] 切换 LLM 失败：", err);
		errorMsg.value = err instanceof Error ? err.message : "切换失败";
	} finally {
		switching.value = false;
	}
};

/** 选择模型 */
const onSelectModel = async (modelId: string) => {
	if (!modelId || modelId === selectedModelId.value) return;
	switching.value = true;
	try {
		const res = await mockSelectModel(modelId);
		status.value = res;
		selectedModelId.value = modelId;
	} catch (err) {
		console.error("[LLMStatus] 选择模型失败：", err);
		errorMsg.value = err instanceof Error ? err.message : "选择失败";
	} finally {
		switching.value = false;
	}
};

/** 已加载的模型列表 */
const loadedModels = computed(() => {
	if (!status.value) return [];
	return status.value.models.filter((m) => m.loaded);
});

/** 可用模型列表（用于下拉框） */
const availableModels = computed(() => status.value?.models ?? []);

onMounted(() => {
	loadStatus();
});
</script>

<template>
  <Card class="llm-status-card">
    <CardHeader>
      <CardTitle class="card-title">
        <Cpu class="title-icon" />
        LLM 状态
        <span v-if="loading" class="loading-hint">
          <Loader2 class="animate-spin" /> 加载中...
        </span>
        <span v-else-if="status" class="status-pill" :class="{ ok: status.available, no: !status.available }">
          <span class="dot" :class="{ ok: status.available, no: !status.available }" />
          {{ status.available ? "LM Studio 在线" : "LM Studio 离线" }}
        </span>
      </CardTitle>
    </CardHeader>
    <CardContent>
      <div v-if="errorMsg" class="error-msg">
        ❌ {{ errorMsg }}
        <button type="button" class="retry-btn" @click="loadStatus">重试</button>
      </div>

      <div v-else-if="status" class="status-grid">
        <!-- 当前模式 -->
        <div class="status-row">
          <div class="row-label">
            <Database class="row-icon" />
            当前模式
          </div>
          <div class="row-value">
            <span class="mode-badge" :class="{ real: status.use_llm, mock: !status.use_llm }">
              {{ status.use_llm ? "真实 LLM" : "Mock 模式" }}
            </span>
          </div>
          <div class="switch-wrap">
            <Switch
              :model-value="status.use_llm"
              @update:model-value="(v: boolean) => onSwitchLLM(v)"
              :disabled="switching"
            />
            <span class="switch-text">{{ status.use_llm ? "已启用" : "已禁用" }}</span>
          </div>
        </div>

        <!-- LM Studio 地址 -->
        <div class="status-row">
          <div class="row-label">
            <Activity class="row-icon" />
            LM Studio 端点
          </div>
          <div class="row-value">
            <code class="endpoint">{{ status.endpoint }}</code>
          </div>
        </div>

        <!-- 模型选择 -->
        <div class="status-row">
          <div class="row-label">
            <Cpu class="row-icon" />
            当前模型
          </div>
          <div class="row-value">
            <select
              v-model="selectedModelId"
              class="model-select"
              :disabled="switching || availableModels.length === 0"
              @change="onSelectModel(selectedModelId)"
            >
              <option value="" disabled>请选择模型</option>
              <option v-for="m in availableModels" :key="m.id" :value="m.id">
                {{ m.name }}{{ m.loaded ? " ✓" : "" }}
              </option>
            </select>
          </div>
        </div>

        <!-- 已加载模型列表 -->
        <div class="status-row">
          <div class="row-label">
            <CheckCircle2 class="row-icon" />
            已加载模型
          </div>
          <div class="row-value models-list">
            <span
              v-for="m in loadedModels"
              :key="m.id"
              class="model-badge"
              :class="{ active: m.id === status.current_model }"
            >
              {{ m.name }}
              <span v-if="m.size" class="model-size">{{ m.size }}GB</span>
            </span>
            <span v-if="loadedModels.length === 0" class="empty-hint">
              <XCircle class="empty-icon" /> 无已加载模型
            </span>
          </div>
        </div>

        <!-- 响应时间统计 -->
        <div class="status-row">
          <div class="row-label">
            <Zap class="row-icon" />
            响应时间 / 调用次数
          </div>
          <div class="row-value">
            <span class="metric">
              <span class="metric-value">{{ status.response_time_ms ?? 0 }}</span>
              <span class="metric-unit">ms</span>
            </span>
            <span class="metric-sep">·</span>
            <span class="metric">
              <span class="metric-value">{{ status.total_calls ?? 0 }}</span>
              <span class="metric-unit">次</span>
            </span>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <Loader2 class="animate-spin" />
        <p>正在加载 LLM 状态...</p>
      </div>
    </CardContent>
  </Card>
</template>

<style scoped>
.llm-status-card {
  border-left: 3px solid #8B5CF6;
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
  color: #8B5CF6;
}

.loading-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 400;
  color: hsl(var(--muted-foreground));
}

.loading-hint .animate-spin {
  width: 12px;
  height: 12px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  margin-left: auto;
}

.status-pill.ok {
  background: #dcfce7;
  color: #15803d;
}

.status-pill.no {
  background: #fee2e2;
  color: #b91c1c;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot.ok {
  background: #10b981;
  box-shadow: 0 0 4px #10b981;
}

.dot.no {
  background: #ef4444;
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

.status-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.status-row {
  display: grid;
  grid-template-columns: 140px 1fr auto;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid hsl(var(--border));
}

.status-row:last-child {
  border-bottom: none;
}

.row-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: hsl(var(--muted-foreground));
}

.row-icon {
  width: 14px;
  height: 14px;
  color: #8B5CF6;
}

.row-value {
  font-size: 13px;
  color: hsl(var(--foreground));
}

.endpoint {
  font-family: 'Consolas', monospace;
  background: #1f2937;
  color: #4ec9b0;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.mode-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.mode-badge.real {
  background: #dcfce7;
  color: #15803d;
}

.mode-badge.mock {
  background: #fef3c7;
  color: #b45309;
}

.switch-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}

.switch-text {
  font-size: 11px;
  color: hsl(var(--muted-foreground));
}

.model-select {
  padding: 4px 10px;
  border: 1px solid hsl(var(--border));
  border-radius: 4px;
  background: hsl(var(--background));
  color: hsl(var(--foreground));
  font-size: 12px;
  cursor: pointer;
  outline: none;
  min-width: 200px;
}

.model-select:focus {
  border-color: #8B5CF6;
  box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.15);
}

.models-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.model-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  background: #ede9fe;
  color: #5b21b6;
  border: 1px solid #c4b5fd;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}

.model-badge.active {
  background: #8B5CF6;
  color: #fff;
  border-color: #8B5CF6;
}

.model-size {
  font-size: 10px;
  opacity: 0.8;
}

.empty-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: hsl(var(--muted-foreground));
  font-style: italic;
}

.empty-icon {
  width: 14px;
  height: 14px;
}

.metric {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
}

.metric-value {
  font-family: 'Consolas', monospace;
  font-size: 14px;
  font-weight: 700;
  color: #1f2937;
}

.metric-unit {
  font-size: 10px;
  color: hsl(var(--muted-foreground));
}

.metric-sep {
  margin: 0 8px;
  color: hsl(var(--muted-foreground));
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px;
  color: hsl(var(--muted-foreground));
  font-size: 13px;
}

.empty-state .animate-spin {
  width: 20px;
  height: 20px;
}

.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
