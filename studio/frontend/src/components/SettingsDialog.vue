<script setup lang="ts">
/**
 * SettingsDialog — 统一 LLM 设置入口对话框。
 *
 * 功能：
 *  - 三模式分段切换：Mock / API / 本地模型
 *  - API 模式：Provider 选择（OpenAI / Anthropic）+ API Key + Base URL + Model
 *  - 本地模式：Base URL（默认 Ollama 11434）+ 可选 Model
 *  - Provider 切换时自动填充默认 Base URL
 *  - API Key 显示/隐藏切换
 *  - 测试连接按钮三态（idle / testing / ok / fail）
 *  - 保存：写入后端 + 同步 providerStore（mode / selectedProvider）
 *
 * 用法：
 *   <SettingsDialog v-model:open="open" />
 */

import { CheckCircle2, Eye, EyeOff, Loader2, XCircle, Zap } from "@lucide/vue";
import { computed, ref, watch } from "vue";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/toast/use-toast";
import {
	getLLMConfig,
	type LLMConfig,
	type LLMTestResult,
	saveLLMConfig,
	testLLMConnection,
} from "@/services/api";
import { useExecutionStore } from "@/stores/executionStore";
import { type LLMMode, useProviderStore } from "@/stores/providerStore";

// ---- Props & Emits ----
const props = defineProps<{ open: boolean; initialMode?: LLMMode }>();
const emit = defineEmits<(e: "update:open", v: boolean) => void>();

// 桥接 props.open 与 Dialog 的 v-model:open
const open = computed<boolean>({
	get: () => props.open,
	set: (v) => emit("update:open", v),
});

// ---- Store & Toast ----
const providerStore = useProviderStore();
const executionStore = useExecutionStore();
const { toast } = useToast();

// ---- 模式选项 ----
const modes: { key: LLMMode; label: string }[] = [
	{ key: "mock", label: "演示模式" },
	{ key: "api", label: "云 API" },
	{ key: "local", label: "本地模型" },
];

// ---- 表单字段 ----
const activeMode = ref<LLMMode>(props.initialMode ?? providerStore.derivedMode);
type ApiProvider = "deepseek" | "qwen" | "openai" | "anthropic" | "custom";
const apiProvider = ref<ApiProvider>("deepseek");
const apiKey = ref<string>("");
const storedApiKeyMask = ref<string>("");
const apiBaseUrl = ref<string>("");
const apiModel = ref<string>("");
const localBaseUrl = ref<string>("http://localhost:11434/v1");
const localModel = ref<string>("");

// ---- 模型列表（测试连接成功后填充，用于下拉选择） ----
const apiModels = ref<string[]>([]);
const localModels = ref<string[]>([]);

// ---- UI 状态 ----
const showApiKey = ref<boolean>(false);
const testStatus = ref<"idle" | "testing" | "ok" | "fail">("idle");
const testResult = ref<LLMTestResult | null>(null);
const saving = ref<boolean>(false);
const remember = ref<boolean>(true);

// ---- Provider 默认 Base URL ----
const PROVIDER_DEFAULT_BASE_URL: Record<ApiProvider, string> = {
	deepseek: "https://api.deepseek.com",
	qwen: "https://dashscope.aliyuncs.com/compatible-mode/v1",
	openai: "https://api.openai.com/v1",
	anthropic: "https://api.anthropic.com",
	custom: "",
};

// Select v-model 桥接（reka-ui Select modelValue 为 AcceptableValue，
// 通过 writable computed 收窄为 'openai' | 'anthropic'）
const apiProviderSelect = computed<string>({
	get: () => apiProvider.value,
	set: (v: string) => {
		if (["deepseek", "qwen", "openai", "anthropic", "custom"].includes(v)) {
			apiProvider.value = v as ApiProvider;
		}
	},
});

// 测试中 / 保存中：禁用相关按钮
const isBusy = computed(() => testStatus.value === "testing" || saving.value);

// ---- 加载配置：先从 providerStore 同步读取，再异步从后端拉取最新 ----
async function loadConfig() {
	// 1. 从 providerStore 同步读取本地缓存（立即可用）
	const local = providerStore.getLLMConfig();
	activeMode.value = props.initialMode ?? local.mode;
	if (local.mode === "api") {
		apiProvider.value = (
			["deepseek", "qwen", "openai", "anthropic", "custom"].includes(
				local.provider ?? "",
			)
				? local.provider
				: "deepseek"
		) as ApiProvider;
		apiKey.value = local.apiKey;
		apiBaseUrl.value =
			local.baseUrl || PROVIDER_DEFAULT_BASE_URL[apiProvider.value];
		apiModel.value = local.model ?? "";
	} else if (local.mode === "local") {
		localBaseUrl.value = local.baseUrl || "http://localhost:11434/v1";
		localModel.value = local.model ?? "";
	}

	// 2. 演示 profile / Mock 模式必须保持离线：打开设置弹窗不主动访问后端。
	// 用户切到云 API / 本地模型后，测试连接或保存才会访问服务端。
	if (executionStore.profileId === "demo" || activeMode.value === "mock") {
		storedApiKeyMask.value = "";
		return;
	}

	// 3. 异步从后端拉取最新配置，若有差异以后端为准
	try {
		const remote = await getLLMConfig();
		if (remote.mode) activeMode.value = remote.mode;
		if (remote.mode === "api") {
			apiProvider.value = (
				["deepseek", "qwen", "openai", "anthropic", "custom"].includes(
					remote.provider ?? "",
				)
					? remote.provider
					: "deepseek"
			) as ApiProvider;
			// 脱敏值只作提示，不回填输入框，避免误把掩码当成新密钥提交。
			storedApiKeyMask.value = remote.apiKey ?? "";
			apiKey.value = "";
			apiBaseUrl.value =
				remote.baseUrl || PROVIDER_DEFAULT_BASE_URL[apiProvider.value];
			apiModel.value = remote.model ?? "";
		} else if (remote.mode === "local") {
			localBaseUrl.value = remote.baseUrl || "http://localhost:11434/v1";
			localModel.value = remote.model ?? "";
		}
		remember.value = remote.remember ?? true;
	} catch (err) {
		console.info("[SettingsDialog] 后端 LLM 配置暂不可用，保留本地缓存。", err);
	}
}

// 打开对话框时加载配置 + 重置测试状态 + 重置模型列表
watch(
	() => props.open,
	(val) => {
		if (val) {
			testStatus.value = "idle";
			testResult.value = null;
			apiModels.value = [];
			localModels.value = [];
			void loadConfig();
		}
	},
	{ immediate: true },
);

// ---- Provider 切换自动填充 Base URL ----
watch(apiProvider, (next, prev) => {
	if (!next || !prev || next === prev) return;
	// 若 Base URL 为空或是另一 provider 的默认值，自动填充新 provider 的默认值
	if (
		!apiBaseUrl.value ||
		apiBaseUrl.value === PROVIDER_DEFAULT_BASE_URL[prev]
	) {
		apiBaseUrl.value = PROVIDER_DEFAULT_BASE_URL[next];
	}
});

// ---- 构造当前 LLMConfig（依据 activeMode） ----
// 根据 Base URL 自动识别本地 provider：11434→ollama, 其他→local
function detectLocalProvider(baseUrl: string): string {
	try {
		const port = new URL(baseUrl).port;
		if (port === "11434") return "ollama";
	} catch {
		// URL 解析失败，走默认
	}
	return "local";
}

function buildConfig(): LLMConfig {
	if (activeMode.value === "api") {
		return {
			mode: "api",
			provider: apiProvider.value,
			apiKey: apiKey.value,
			baseUrl: apiBaseUrl.value,
			model: apiModel.value || null,
			remember: remember.value,
		};
	}
	if (activeMode.value === "local") {
		return {
			mode: "local",
			provider: detectLocalProvider(localBaseUrl.value),
			apiKey: "",
			baseUrl: localBaseUrl.value,
			model: localModel.value || null,
			remember: remember.value,
		};
	}
	// mock
	return {
		mode: "mock",
		provider: null,
		apiKey: "",
		baseUrl: "",
		model: null,
		remember: remember.value,
	};
}

// ---- 测试连接 ----
async function handleTest() {
	testStatus.value = "testing";
	testResult.value = null;
	try {
		const result = await testLLMConnection(buildConfig());
		testResult.value = result;
		testStatus.value = result.ok ? "ok" : "fail";
		// 测试成功且有模型列表：填充下拉数据
		if (result.ok && result.models && result.models.length > 0) {
			if (activeMode.value === "api") {
				apiModels.value = result.models;
				// 当前 Model 为空或不在列表中，自动选中第一个
				if (!apiModel.value || !result.models.includes(apiModel.value)) {
					apiModel.value = result.models[0];
				}
			} else if (activeMode.value === "local") {
				localModels.value = result.models;
				if (!localModel.value || !result.models.includes(localModel.value)) {
					localModel.value = result.models[0];
				}
			}
		}
	} catch (err) {
		testResult.value = {
			ok: false,
			latency_ms: 0,
			message: err instanceof Error ? err.message : "测试失败",
		};
		testStatus.value = "fail";
	}
}

// ---- 保存 ----
async function handleSave() {
	if (isBusy.value) return;
	saving.value = true;
	try {
		const config = buildConfig();
		// 1. 写入后端
		await saveLLMConfig(config);
		// 2. 写入 execution profile（同时联动 providerStore.derivedMode）
		executionStore.setProfile(
			config.mode === "mock"
				? "demo"
				: config.mode === "local"
					? "local"
					: "cloud",
		);
		// 3. 同步 selectedProvider
		//    - API 模式：openai / anthropic
		//    - 本地模式：根据 Base URL 自动识别（ollama / local）
		if (config.mode === "api") {
			providerStore.setProvider(config.provider ?? "openai");
		} else if (config.mode === "local") {
			const localProviderId = detectLocalProvider(localBaseUrl.value);
			// 仅当识别出的 provider 存在于 store 时才切换，避免 setProvider 静默失败
			providerStore.setProvider(localProviderId);
		}
		toast({
			title: "配置已保存",
			description: "LLM 设置已成功更新",
		});
		// 通知顶栏状态指示灯立即刷新（TopStatusBar 监听此事件）
		window.dispatchEvent(new Event("skyforge-llm-config-changed"));
		open.value = false;
	} catch (err) {
		toast({
			title: "保存失败",
			description: err instanceof Error ? err.message : "未知错误",
			variant: "destructive",
		});
	} finally {
		saving.value = false;
	}
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent class="max-h-[calc(100dvh-2rem)] max-w-2xl overflow-y-auto">
      <DialogHeader>
        <DialogTitle>LLM 设置</DialogTitle>
        <DialogDescription>配置后端模型连接；比赛演示数据来源仍由顶部 Profile 独立控制</DialogDescription>
      </DialogHeader>

      <!-- 模式分段按钮（自定义 button，非 shadcn Tabs） -->
      <div class="flex gap-2 border-b">
        <button
          v-for="m in modes"
          :key="m.key"
          type="button"
          class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px"
          :class="
            activeMode === m.key
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          "
          @click="activeMode = m.key"
        >
          {{ m.label }}
        </button>
      </div>

      <!-- Mock 选项卡 -->
      <div v-if="activeMode === 'mock'" class="space-y-2 py-2">
        <p class="text-sm text-muted-foreground">
          前端模拟数据，不调用任何 LLM 服务。适用于演示与开发调试。
        </p>
      </div>

      <!-- API 选项卡 -->
      <div v-else-if="activeMode === 'api'" class="space-y-4 py-2">
        <!-- Provider 选择 -->
        <div class="space-y-2">
          <Label>Provider</Label>
          <Select v-model="apiProviderSelect">
            <SelectTrigger class="w-full">
              <SelectValue placeholder="选择 Provider" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="deepseek">DeepSeek</SelectItem>
              <SelectItem value="qwen">通义千问（兼容 API）</SelectItem>
              <SelectItem value="openai">OpenAI</SelectItem>
              <SelectItem value="anthropic">Anthropic</SelectItem>
              <SelectItem value="custom">自定义 OpenAI 兼容服务</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <!-- API Key 输入（带显示/隐藏） -->
        <div class="space-y-2">
          <Label for="llm-api-key">API Key</Label>
          <div class="relative">
            <Input
              id="llm-api-key"
              v-model="apiKey"
              :type="showApiKey ? 'text' : 'password'"
              :placeholder="storedApiKeyMask ? `已配置 ${storedApiKeyMask}；留空表示不修改` : '输入 API Key；留空表示不修改'"
              class="pr-10"
            />
            <button
              type="button"
              :aria-label="showApiKey ? '隐藏 API Key' : '显示 API Key'"
              class="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              @click="showApiKey = !showApiKey"
            >
              <Eye v-if="!showApiKey" class="w-4 h-4" />
              <EyeOff v-else class="w-4 h-4" />
            </button>
          </div>
          <p class="text-xs text-muted-foreground">密钥通过 HTTPS/本机 HTTP 提交给后端，不写入 localStorage；留空会沿用已配置密钥。</p>
        </div>

        <!-- Base URL -->
        <div class="space-y-2">
          <Label>Base URL</Label>
          <Input v-model="apiBaseUrl" placeholder="https://api.openai.com/v1" />
          <p class="text-xs text-muted-foreground">
            留空将自动使用 Provider 默认地址。
          </p>
        </div>

        <!-- Model -->
        <div class="space-y-2">
          <Label>Model</Label>
          <Select v-if="apiModels.length > 0" v-model="apiModel">
            <SelectTrigger class="w-full">
              <SelectValue placeholder="选择模型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="m in apiModels"
                :key="m"
                :value="m"
              >{{ m }}</SelectItem>
            </SelectContent>
          </Select>
          <Input v-else v-model="apiModel" placeholder="gpt-4o / claude-3-5-sonnet" />
          <p class="text-xs text-muted-foreground">
            {{ apiModels.length > 0
              ? `已检测到 ${apiModels.length} 个可用模型`
              : "指定模型 ID 或点击「测试连接」自动获取列表" }}
          </p>
        </div>

        <!-- 测试连接（三态） -->
        <div class="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            :disabled="testStatus === 'testing'"
            @click="handleTest"
          >
            <Loader2 v-if="testStatus === 'testing'" class="w-3 h-3 mr-1 animate-spin" />
            <CheckCircle2 v-else-if="testStatus === 'ok'" class="w-3 h-3 mr-1 text-green-500" />
            <XCircle v-else-if="testStatus === 'fail'" class="w-3 h-3 mr-1 text-red-500" />
            <Zap v-else class="w-3 h-3 mr-1" />
            {{ testStatus === "testing" ? "测试中..." : "测试连接" }}
          </Button>
          <span v-if="testStatus === 'ok'" class="text-xs text-green-600">
            {{ testResult?.latency_ms }}ms · {{ testResult?.model }}
          </span>
          <span v-else-if="testStatus === 'fail'" class="text-xs text-red-600">
            {{ testResult?.message }}
          </span>
        </div>
      </div>

      <!-- 本地模型选项卡 -->
      <div v-else-if="activeMode === 'local'" class="space-y-4 py-2">
        <div class="space-y-2">
          <Label>Base URL</Label>
          <Input v-model="localBaseUrl" placeholder="http://localhost:11434/v1" />
          <p class="text-xs text-muted-foreground">
            本地 OpenAI 兼容端点（如 Ollama）。默认 http://localhost:11434/v1
          </p>
        </div>

        <div class="space-y-2">
          <Label>Model</Label>
          <Select v-if="localModels.length > 0" v-model="localModel">
            <SelectTrigger class="w-full">
              <SelectValue placeholder="选择模型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="m in localModels"
                :key="m"
                :value="m"
              >{{ m }}</SelectItem>
            </SelectContent>
          </Select>
          <Input v-else v-model="localModel" placeholder="auto / qwen2.5-coder:14b" />
          <p class="text-xs text-muted-foreground">
            {{ localModels.length > 0
              ? `已检测到 ${localModels.length} 个可用模型`
              : "可选；点击「测试连接」自动获取模型列表" }}
          </p>
        </div>

        <!-- 测试连接（三态） -->
        <div class="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            :disabled="testStatus === 'testing'"
            @click="handleTest"
          >
            <Loader2 v-if="testStatus === 'testing'" class="w-3 h-3 mr-1 animate-spin" />
            <CheckCircle2 v-else-if="testStatus === 'ok'" class="w-3 h-3 mr-1 text-green-500" />
            <XCircle v-else-if="testStatus === 'fail'" class="w-3 h-3 mr-1 text-red-500" />
            <Zap v-else class="w-3 h-3 mr-1" />
            {{ testStatus === "testing" ? "测试中..." : "测试连接" }}
          </Button>
          <span v-if="testStatus === 'ok'" class="text-xs text-green-600">
            {{ testResult?.latency_ms }}ms · {{ testResult?.model }}
          </span>
          <span v-else-if="testStatus === 'fail'" class="text-xs text-red-600">
            {{ testResult?.message }}
          </span>
        </div>
      </div>

      <label class="flex items-start gap-3 rounded-lg border bg-muted/30 p-3 text-sm">
        <input v-model="remember" type="checkbox" class="mt-1" />
        <span><strong class="block">在此设备上记住配置</strong><small class="text-muted-foreground">写入已被 Git 忽略的 config/.env；取消勾选会清除磁盘上的 LLM 配置和密钥。</small></span>
      </label>

      <DialogFooter>
        <Button variant="ghost" @click="open = false">取消</Button>
        <Button :disabled="isBusy" @click="handleSave">保存</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
