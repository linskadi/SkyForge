<script setup lang="ts">
import {
	CheckCircle2,
	ChevronDown,
	CloudCog,
	Cpu,
	Download,
	Eye,
	EyeOff,
	FolderOpen,
	Hammer,
	LayoutPanelLeft,
	Loader2,
	Monitor,
	Moon,
	Palette,
	RefreshCw,
	ShieldCheck,
	Sparkles,
	Sun,
	Terminal,
	Wrench,
	XCircle,
	Zap,
} from "@lucide/vue";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import SettingsDialog from "@/components/SettingsDialog.vue";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast/use-toast";
import { useTheme } from "@/composables/useTheme";
import {
	getLLMConfig,
	type LLMConfig,
	type LLMTestResult,
	saveLLMConfig,
	testLLMConnection,
} from "@/services/api";
import { useExecutionStore } from "@/stores/executionStore";
import { useProviderStore } from "@/stores/providerStore";
import { useToolchainStore } from "@/stores/toolchainStore";
import type { ExecutionProfileId } from "@/types/execution";

const execution = useExecutionStore();
const providerStore = useProviderStore();
const { isDark, toggleTheme } = useTheme();
const { toast } = useToast();
const toolchainStore = useToolchainStore();

const activeInstallHint = ref<string>("");
const installHintTool = ref<string>("");

onMounted(() => {
	toolchainStore.fetchTools();
	toolchainStore.startPolling();
});

onBeforeUnmount(() => {
	toolchainStore.stopPolling();
});

async function showInstallHint(toolName: string) {
	installHintTool.value = toolName;
	const hints = await toolchainStore.getInstallHint(toolName);
	const platform = navigator.platform.toLowerCase();
	let key = "linux";
	if (platform.includes("win")) key = "windows";
	else if (platform.includes("mac")) key = "macos";
	activeInstallHint.value =
		hints[key] || hints["linux"] || "请参考官方文档安装";
}

function closeInstallHint() {
	activeInstallHint.value = "";
	installHintTool.value = "";
}

function getToolStatusLabel(tool: { found: boolean; version: string }) {
	if (tool.found && tool.version) return "已检测";
	return "未安装";
}

const llmSettingsOpen = ref(false);
const activeTab = ref("profile");

const profileDescriptions: Record<
	ExecutionProfileId,
	{ title: string; description: string; limitation: string }
> = {
	cloud: {
		title: "云 API",
		description: "DeepSeek、Qwen、OpenAI、Anthropic 或自定义兼容 API。",
		limitation: "需要有效的 API Key 与网络连接",
	},
	local: {
		title: "本地模型",
		description: "连接 Ollama、LM Studio 等本机 OpenAI-compatible 服务。",
		limitation: "需要本机运行 LLM 服务，性能取决于硬件",
	},
};

type ApiProvider = "deepseek" | "qwen" | "openai" | "anthropic" | "custom";
const PROVIDER_DEFAULT_BASE_URL: Record<ApiProvider, string> = {
	deepseek: "https://api.deepseek.com",
	qwen: "https://dashscope.aliyuncs.com/compatible-mode/v1",
	openai: "https://api.openai.com/v1",
	anthropic: "https://api.anthropic.com",
	custom: "",
};

const activeMode = ref(providerStore.derivedMode);
const apiProvider = ref<ApiProvider>("deepseek");
const apiKey = ref("");
const storedApiKeyMask = ref("");
const apiBaseUrl = ref("");
const apiModel = ref("");
const localBaseUrl = ref("http://localhost:11434/v1");
const localModel = ref("");
const apiModels = ref<string[]>([]);
const localModels = ref<string[]>([]);
const showApiKey = ref(false);
const testStatus = ref<"idle" | "testing" | "ok" | "fail">("idle");
const testResult = ref<LLMTestResult | null>(null);
const saving = ref(false);
const remember = ref(true);

const apiProviderSelect = computed<string>({
	get: () => apiProvider.value,
	set: (v: string) => {
		if (["deepseek", "qwen", "openai", "anthropic", "custom"].includes(v)) {
			apiProvider.value = v as ApiProvider;
		}
	},
});

const isBusy = computed(() => testStatus.value === "testing" || saving.value);

watch(apiProvider, (next, prev) => {
	if (!next || !prev || next === prev) return;
	if (
		!apiBaseUrl.value ||
		apiBaseUrl.value === PROVIDER_DEFAULT_BASE_URL[prev]
	) {
		apiBaseUrl.value = PROVIDER_DEFAULT_BASE_URL[next];
	}
});

async function loadLlmConfig() {
	const local = providerStore.getLLMConfig();
	activeMode.value = local.mode;
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

	if (activeMode.value === "mock") {
		storedApiKeyMask.value = "";
		return;
	}

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
		console.info("[SystemSettings] 后端 LLM 配置暂不可用，保留本地缓存。", err);
	}
}

loadLlmConfig();

function detectLocalProvider(baseUrl: string): string {
	try {
		const port = new URL(baseUrl).port;
		if (port === "11434") return "ollama";
	} catch {
		// empty
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
	return {
		mode: "mock",
		provider: null,
		apiKey: "",
		baseUrl: "",
		model: null,
		remember: remember.value,
	};
}

async function handleTest() {
	testStatus.value = "testing";
	testResult.value = null;
	try {
		const result = await testLLMConnection(buildConfig());
		testResult.value = result;
		testStatus.value = result.ok ? "ok" : "fail";
		if (result.ok && result.models && result.models.length > 0) {
			if (activeMode.value === "api") {
				apiModels.value = result.models;
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

async function handleSaveLlm() {
	if (isBusy.value) return;
	saving.value = true;
	try {
		const config = buildConfig();
		await saveLLMConfig(config);
		execution.setProfile(config.mode === "local" ? "local" : "cloud");
		if (config.mode === "api") {
			providerStore.setProvider(config.provider ?? "deepseek");
		} else if (config.mode === "local") {
			const localProviderId = detectLocalProvider(localBaseUrl.value);
			providerStore.setProvider(localProviderId);
		}
		toast({
			title: "配置已保存",
			description: "LLM 设置已成功更新",
		});
		window.dispatchEvent(new Event("skyforge-llm-config-changed"));
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

const themeMode = ref<"light" | "dark" | "system">(
	isDark.value ? "dark" : "light",
);
const defaultLanguage = ref<"c" | "cpp" | "python">(
	(localStorage.getItem("skyforge-default-lang") as "c" | "cpp" | "python") ||
		"c",
);
const desktopNotifications = ref(
	localStorage.getItem("skyforge-notif-desktop") !== "false",
);
const browserNotifications = ref(
	localStorage.getItem("skyforge-notif-browser") !== "false",
);
const reduceMotion = ref(
	localStorage.getItem("skyforge-reduce-motion") === "true",
);

function applyThemeMode() {
	const root = document.documentElement;
	if (themeMode.value === "system") {
		const prefersDark = window.matchMedia(
			"(prefers-color-scheme: dark)",
		).matches;
		isDark.value = prefersDark;
	} else {
		isDark.value = themeMode.value === "dark";
	}
	localStorage.setItem("skyforge-theme-mode", themeMode.value);
}

function setDefaultLang(lang: "c" | "cpp" | "python") {
	defaultLanguage.value = lang;
	localStorage.setItem("skyforge-default-lang", lang);
}

function setDesktopNotifications(val: boolean) {
	desktopNotifications.value = val;
	localStorage.setItem("skyforge-notif-desktop", String(val));
}

function setBrowserNotifications(val: boolean) {
	browserNotifications.value = val;
	localStorage.setItem("skyforge-notif-browser", String(val));
}

function setReduceMotion(val: boolean) {
	reduceMotion.value = val;
	localStorage.setItem("skyforge-reduce-motion", String(val));
	if (val) {
		document.documentElement.classList.add("reduce-motion");
	} else {
		document.documentElement.classList.remove("reduce-motion");
	}
}

const savedThemeMode = localStorage.getItem("skyforge-theme-mode") as
	| "light"
	| "dark"
	| "system"
	| null;
if (savedThemeMode) {
	themeMode.value = savedThemeMode;
}

const savedReduceMotion = localStorage.getItem("skyforge-reduce-motion");
if (savedReduceMotion === "true") {
	document.documentElement.classList.add("reduce-motion");
}
</script>

<template>
	<main class="min-h-[calc(100dvh-var(--topbar-h,52px))] bg-background">
		<div class="mx-auto max-w-6xl px-4 py-8 md:px-8">
			<header class="mb-8">
				<h1 class="text-2xl font-semibold tracking-tight md:text-3xl">系统设置</h1>
				<p class="mt-2 text-sm text-muted-foreground md:text-base">
					配置运行来源、模型连接、工具链与界面偏好。所有设置均在本地保存，敏感信息由后端安全管理。
				</p>
			</header>

			<Tabs v-model="activeTab" class="flex flex-col gap-6 md:flex-row md:items-start">
				<TabsList class="flex md:w-56 md:flex-col md:items-stretch md:gap-1 md:bg-transparent md:p-0">
					<TabsTrigger value="profile" class="flex items-center justify-center gap-2 md:justify-start">
						<Monitor class="h-4 w-4" />
						<span>运行来源</span>
					</TabsTrigger>
					<TabsTrigger value="model" class="flex items-center justify-center gap-2 md:justify-start">
						<CloudCog class="h-4 w-4" />
						<span>模型连接</span>
					</TabsTrigger>
					<TabsTrigger value="toolchain" class="flex items-center justify-center gap-2 md:justify-start">
						<Wrench class="h-4 w-4" />
						<span>工具链配置</span>
					</TabsTrigger>
					<TabsTrigger value="preferences" class="flex items-center justify-center gap-2 md:justify-start">
						<Palette class="h-4 w-4" />
						<span>界面偏好</span>
					</TabsTrigger>
				</TabsList>

				<div class="flex-1">
					<TabsContent value="profile" class="mt-0">
						<Card>
							<CardHeader>
								<CardTitle class="text-xl">运行来源</CardTitle>
								<CardDescription>选择当前页面和新任务的数据来源。切换后立即生效。</CardDescription>
							</CardHeader>
							<CardContent class="space-y-3">
								<label
									v-for="profile in execution.profiles"
									:key="profile.id"
									class="group relative flex cursor-pointer items-start gap-4 rounded-lg border p-4 transition-all hover:border-border"
									:class="
										execution.profileId === profile.id
											? 'border-primary bg-primary/5'
											: 'border-border'
									"
								>
									<input
										type="radio"
										name="profile"
										:checked="execution.profileId === profile.id"
										@change="execution.setProfile(profile.id as ExecutionProfileId)"
										class="sr-only"
									/>
									<div
										class="flex h-10 w-10 shrink-0 items-center justify-center rounded-md"
										:class="[
											profile.id === 'cloud' ? 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400' : '',
											profile.id === 'local' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400' : '',
										]"
									>
										<CloudCog v-if="profile.id === 'cloud'" class="h-5 w-5" />
										<Cpu v-else class="h-5 w-5" />
									</div>
									<div class="min-w-0 flex-1">
										<div class="flex items-center gap-2">
											<span class="font-medium">{{ profileDescriptions[profile.id].title }}</span>
											<span
												class="rounded-full px-2 py-0.5 text-xs font-medium"
												:class="[
													profile.source === 'simulated'
														? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400'
														: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400',
												]"
											>
												{{ profile.source === "simulated" ? "模拟" : "实时/回放" }}
											</span>
										</div>
										<p class="mt-1 text-sm text-muted-foreground">
											{{ profileDescriptions[profile.id].description }}
										</p>
										<p class="mt-2 text-xs text-muted-foreground">
											限制：{{ profileDescriptions[profile.id].limitation }}
										</p>
									</div>
									<div
										class="h-4 w-4 shrink-0 rounded-full border-2 transition-all"
										:class="
											execution.profileId === profile.id
												? 'border-primary'
												: 'border-muted-foreground/30 group-hover:border-muted-foreground/50'
										"
									>
										<div
											v-if="execution.profileId === profile.id"
											class="m-0.5 h-2 w-2 rounded-full bg-primary"
										/>
									</div>
								</label>
							</CardContent>
						</Card>
					</TabsContent>

					<TabsContent value="model" class="mt-0">
						<Card>
							<CardHeader>
								<CardTitle class="text-xl">模型连接</CardTitle>
								<CardDescription>配置后端 LLM 连接。API Key 由后端安全管理，不写入浏览器存储。</CardDescription>
							</CardHeader>
							<CardContent class="space-y-6">
								<div class="space-y-3">
									<Label>运行模式</Label>
									<div class="grid grid-cols-3 gap-2">
										<button
											v-for="m in [{ key: 'mock', label: '模拟' }, { key: 'api', label: '云 API' }, { key: 'local', label: '本地' }]"
											:key="m.key"
											type="button"
											class="rounded-md border px-3 py-2 text-sm font-medium transition-all"
											:class="
												activeMode === m.key
													? 'border-primary bg-primary/5 text-primary'
													: 'border-border text-muted-foreground hover:border-border hover:text-foreground'
											"
											@click="activeMode = m.key as 'mock' | 'api' | 'local'"
										>
											{{ m.label }}
										</button>
									</div>
								</div>

								<div v-if="activeMode === 'mock'" class="rounded-lg border bg-muted/30 p-4">
									<p class="text-sm text-muted-foreground">
										前端模拟数据，不调用任何 LLM 服务。适用于无后端时的开发调试。
									</p>
								</div>

								<template v-else-if="activeMode === 'api'">
									<div class="space-y-2">
										<Label>Provider</Label>
										<Select v-model="apiProviderSelect">
											<SelectTrigger>
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
												<Eye v-if="!showApiKey" class="h-4 w-4" />
												<EyeOff v-else class="h-4 w-4" />
											</button>
										</div>
										<p class="text-xs text-muted-foreground">
											密钥通过 HTTPS 提交给后端，不写入 localStorage；留空会沿用已配置密钥。
										</p>
									</div>

									<div class="space-y-2">
										<Label>Base URL</Label>
										<Input v-model="apiBaseUrl" placeholder="https://api.openai.com/v1" />
										<p class="text-xs text-muted-foreground">留空将自动使用 Provider 默认地址。</p>
									</div>

									<div class="space-y-2">
										<Label>Model</Label>
										<Select v-if="apiModels.length > 0" v-model="apiModel">
											<SelectTrigger>
												<SelectValue placeholder="选择模型" />
											</SelectTrigger>
											<SelectContent>
												<SelectItem v-for="m in apiModels" :key="m" :value="m">{{ m }}</SelectItem>
											</SelectContent>
										</Select>
										<Input v-else v-model="apiModel" placeholder="gpt-4o / claude-3-5-sonnet" />
										<p class="text-xs text-muted-foreground">
											{{ apiModels.length > 0 ? `已检测到 ${apiModels.length} 个可用模型` : '指定模型 ID 或点击「测试连接」自动获取列表' }}
										</p>
									</div>
								</template>

								<template v-else-if="activeMode === 'local'">
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
											<SelectTrigger>
												<SelectValue placeholder="选择模型" />
											</SelectTrigger>
											<SelectContent>
												<SelectItem v-for="m in localModels" :key="m" :value="m">{{ m }}</SelectItem>
											</SelectContent>
										</Select>
										<Input v-else v-model="localModel" placeholder="auto / qwen2.5-coder:14b" />
										<p class="text-xs text-muted-foreground">
											{{ localModels.length > 0 ? `已检测到 ${localModels.length} 个可用模型` : '可选；点击「测试连接」自动获取模型列表' }}
										</p>
									</div>
								</template>

								<div class="flex flex-wrap items-center gap-3">
									<Button variant="outline" size="sm" :disabled="testStatus === 'testing'" @click="handleTest">
										<Loader2 v-if="testStatus === 'testing'" class="mr-1 h-3 w-3 animate-spin" />
										<CheckCircle2 v-else-if="testStatus === 'ok'" class="mr-1 h-3 w-3 text-green-500" />
										<XCircle v-else-if="testStatus === 'fail'" class="mr-1 h-3 w-3 text-red-500" />
										<Zap v-else class="mr-1 h-3 w-3" />
										{{ testStatus === "testing" ? "测试中..." : "测试连接" }}
									</Button>
									<span v-if="testStatus === 'ok'" class="text-xs text-green-600 dark:text-green-400">
										{{ testResult?.latency_ms }}ms · {{ testResult?.model }}
									</span>
									<span v-else-if="testStatus === 'fail'" class="text-xs text-red-600 dark:text-red-400">
										{{ testResult?.message }}
									</span>
								</div>

								<label class="flex items-start gap-3 rounded-lg border bg-muted/30 p-3 text-sm">
									<input v-model="remember" type="checkbox" class="mt-1" />
									<span>
										<strong class="block">在此设备上记住配置</strong>
										<small class="text-muted-foreground">写入已被 Git 忽略的 config/.env；取消勾选会清除磁盘上的 LLM 配置和密钥。</small>
									</span>
								</label>

								<div class="flex justify-end">
									<Button :disabled="isBusy" @click="handleSaveLlm">
										{{ saving ? "保存中..." : "保存设置" }}
									</Button>
								</div>
							</CardContent>
						</Card>
					</TabsContent>

					<TabsContent value="toolchain" class="mt-0">
						<Card>
							<CardHeader>
								<CardTitle class="text-xl">工具链配置</CardTitle>
								<CardDescription>检测并配置代码分析与验证工具链。</CardDescription>
							</CardHeader>
							<CardContent class="space-y-3">
								<div v-if="toolchainStore.loading" class="rounded-lg border p-4 text-center text-muted-foreground">
									加载中...
								</div>
								<div v-else-if="toolchainStore.error" class="rounded-lg border p-4 text-center text-amber-600">
									工具链状态获取失败：{{ toolchainStore.error }}
								</div>
								<div v-else class="space-y-3">
									<div
										v-for="tool in toolchainStore.tools"
										:key="tool.name"
										class="flex flex-col rounded-lg border p-4"
									>
										<div class="flex items-center justify-between">
											<div class="flex items-center gap-4">
												<div
													class="flex h-10 w-10 items-center justify-center rounded-md"
													:class="[
														tool.found
															? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400'
															: 'bg-muted text-muted-foreground',
													]"
												>
													<Terminal class="h-5 w-5" />
												</div>
												<div>
													<div class="flex items-center gap-2">
														<span class="font-medium">{{ tool.name }}</span>
														<span v-if="tool.version" class="text-xs text-muted-foreground">
															v{{ tool.version }}
														</span>
														<span v-else class="text-xs text-muted-foreground">
															需要 >= v{{ tool.min_version }}
														</span>
													</div>
													<p class="text-xs text-muted-foreground">{{ tool.description }}</p>
													<p v-if="!tool.found && tool.install_hint" class="mt-1 text-xs text-amber-600 dark:text-amber-400">
														安装提示: {{ tool.install_hint }}
													</p>
												</div>
											</div>
											<div class="flex items-center gap-3">
												<span
													class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
													:class="[
														tool.found
															? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400'
															: 'bg-muted text-muted-foreground',
													]"
												>
													<span
														class="h-1.5 w-1.5 rounded-full"
														:class="[
															tool.found ? 'bg-emerald-500' : 'bg-muted-foreground',
														]"
													/>
													{{ getToolStatusLabel(tool) }}
												</span>
												<Button
													variant="ghost"
													size="sm"
													@click="toolchainStore.fetchTools()"
													:disabled="toolchainStore.loading"
												>
													<RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': toolchainStore.loading }" />
												</Button>
												<Button
													v-if="!tool.found"
													variant="outline"
													size="sm"
													@click="showInstallHint(tool.name)"
												>
													<Download class="mr-1.5 h-3.5 w-3.5" />
													安装指引
												</Button>
											</div>
										</div>
										<div
											v-if="activeInstallHint && installHintTool === tool.name"
											class="mt-3 rounded-lg border bg-muted/30 p-3 text-sm"
										>
											<div class="flex items-start justify-between gap-2">
												<div>
													<p class="font-medium">{{ tool.name }} 安装指引</p>
													<p class="mt-1 text-muted-foreground">{{ activeInstallHint }}</p>
												</div>
												<Button variant="ghost" size="sm" @click="closeInstallHint">
													<XCircle class="h-4 w-4" />
												</Button>
											</div>
										</div>
									</div>
								</div>
							</CardContent>
						</Card>
					</TabsContent>

					<TabsContent value="preferences" class="mt-0 space-y-6">
						<Card>
							<CardHeader>
								<CardTitle class="text-xl">外观</CardTitle>
								<CardDescription>设置主题与视觉效果。</CardDescription>
							</CardHeader>
							<CardContent class="space-y-6">
								<div class="space-y-3">
									<Label>主题</Label>
									<div class="grid grid-cols-3 gap-2">
										<button
											type="button"
											class="flex flex-col items-center gap-2 rounded-md border p-3 transition-all"
											:class="
												themeMode === 'light'
													? 'border-primary bg-primary/5'
													: 'border-border hover:border-border'
											"
											@click="themeMode = 'light'; applyThemeMode()"
										>
											<Sun class="h-5 w-5" />
											<span class="text-sm font-medium">浅色</span>
										</button>
										<button
											type="button"
											class="flex flex-col items-center gap-2 rounded-md border p-3 transition-all"
											:class="
												themeMode === 'dark'
													? 'border-primary bg-primary/5'
													: 'border-border hover:border-border'
											"
											@click="themeMode = 'dark'; applyThemeMode()"
										>
											<Moon class="h-5 w-5" />
											<span class="text-sm font-medium">深色</span>
										</button>
										<button
											type="button"
											class="flex flex-col items-center gap-2 rounded-md border p-3 transition-all"
											:class="
												themeMode === 'system'
													? 'border-primary bg-primary/5'
													: 'border-border hover:border-border'
											"
											@click="themeMode = 'system'; applyThemeMode()"
										>
											<Monitor class="h-5 w-5" />
											<span class="text-sm font-medium">跟随系统</span>
										</button>
									</div>
								</div>

								<div class="flex items-center justify-between">
									<div>
										<p class="text-sm font-medium">减少动画</p>
										<p class="text-xs text-muted-foreground">关闭非必要动画与过渡效果</p>
									</div>
									<Switch :checked="reduceMotion" @change="setReduceMotion($event)" />
								</div>
							</CardContent>
						</Card>

						<Card>
							<CardHeader>
								<CardTitle class="text-xl">语言与通知</CardTitle>
								<CardDescription>设置默认目标语言与通知偏好。</CardDescription>
							</CardHeader>
							<CardContent class="space-y-6">
								<div class="space-y-2">
									<Label>默认目标语言</Label>
									<div class="grid grid-cols-3 gap-2">
										<button
											v-for="lang in [{ key: 'c', label: 'C' }, { key: 'cpp', label: 'C++' }, { key: 'python', label: 'Python' }]"
											:key="lang.key"
											type="button"
											class="rounded-md border px-3 py-2 text-sm font-medium transition-all"
											:class="
												defaultLanguage === lang.key
													? 'border-primary bg-primary/5 text-primary'
													: 'border-border text-muted-foreground hover:border-border hover:text-foreground'
											"
											@click="setDefaultLang(lang.key as 'c' | 'cpp' | 'python')"
										>
											{{ lang.label }}
										</button>
									</div>
								</div>

								<div class="flex items-center justify-between">
									<div>
										<p class="text-sm font-medium">桌面通知</p>
										<p class="text-xs text-muted-foreground">任务完成时发送桌面通知</p>
									</div>
									<Switch :checked="desktopNotifications" @change="setDesktopNotifications($event)" />
								</div>

								<div class="flex items-center justify-between">
									<div>
										<p class="text-sm font-medium">浏览器通知</p>
										<p class="text-xs text-muted-foreground">任务进行中显示浏览器内通知</p>
									</div>
									<Switch :checked="browserNotifications" @change="setBrowserNotifications($event)" />
								</div>
							</CardContent>
						</Card>
					</TabsContent>
				</div>
			</Tabs>
		</div>

		<SettingsDialog v-model:open="llmSettingsOpen" initial-mode="api" />
	</main>
</template>
