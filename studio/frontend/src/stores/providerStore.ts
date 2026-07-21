/**
 * Provider Store — LLM 供应商配置 + 派生模式（Phase 1 状态管理统一）
 * ====================================================================
 * Phase 1 重构要点：
 * 1. 移除旧的 `mode` ref 与 `setMode` action：mode 改为 `derivedMode` 计算属性，
 *    来源唯一为 `executionStore.profileId`（demo → mock, cloud → api, local → local）；
 * 2. localStorage key 不再使用 `skyforge-llm-mode`，统一改为
 *    `skyforge-execution-profile`（由 executionStore 负责写入）；
 * 3. 保留 Provider / Model 选择（baseURL / model）相关字段，因为后端 LLM 配置
 *    仍需要它们作为 `LLMConfig` 的 provider / model / baseUrl 字段；
 * 4. `getLLMConfig()` 返回的 `mode` 字段来源于 derivedMode。
 */
import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { useExecutionStore } from "@/stores/executionStore";

export interface ProviderConfig {
	id: string;
	name: string;
	icon: string;
	baseURL: string;
	apiKey: string;
	models: ProviderModel[];
	enabled: boolean;
	isLocal: boolean;
	description: string;
}

export interface ProviderModel {
	id: string;
	name: string;
	isDefault: boolean;
}

/**
 * LLM 运行模式
 * - mock: 使用 mock 适配器，前端独立可用
 * - api: 调用真实云端 API
 * - local: 使用本地模型（Ollama 等 OpenAI 兼容端点）
 */
export type LLMMode = "mock" | "api" | "local";

const DEFAULT_PROVIDERS: ProviderConfig[] = [
	{
		id: "deepseek",
		name: "DeepSeek",
		icon: "🔵",
		baseURL: "https://api.deepseek.com",
		apiKey: "",
		models: [
			{ id: "deepseek-chat", name: "DeepSeek V3 (Chat)", isDefault: true },
			{
				id: "deepseek-reasoner",
				name: "DeepSeek R1 (Reasoner)",
				isDefault: false,
			},
		],
		enabled: true,
		isLocal: false,
		description: "高性价比，中文优化，代码能力强",
	},
	{
		id: "qwen",
		name: "通义千问",
		icon: "🟣",
		baseURL: "https://dashscope.aliyuncs.com/compatible-mode/v1",
		apiKey: "",
		models: [
			{ id: "qwen-plus", name: "Qwen Plus", isDefault: true },
			{ id: "qwen-max", name: "Qwen Max", isDefault: false },
			{ id: "qwen-coder-turbo", name: "Qwen Coder Turbo", isDefault: false },
		],
		enabled: true,
		isLocal: false,
		description: "国产首选，通义千问系列，阿里云提供",
	},
	{
		id: "openai",
		name: "OpenAI",
		icon: "🟢",
		baseURL: "https://api.openai.com/v1",
		apiKey: "",
		models: [
			{ id: "gpt-4o", name: "GPT-4o", isDefault: true },
			{ id: "gpt-4o-mini", name: "GPT-4o Mini", isDefault: false },
		],
		enabled: false,
		isLocal: false,
		description: "最高精度，全球领先的LLM",
	},
	{
		id: "anthropic",
		name: "Anthropic",
		icon: "🟠",
		baseURL: "https://api.anthropic.com",
		apiKey: "",
		models: [
			{ id: "claude-3-5-sonnet", name: "Claude 3.5 Sonnet", isDefault: true },
			{ id: "claude-3-haiku", name: "Claude 3 Haiku", isDefault: false },
		],
		enabled: false,
		isLocal: false,
		description: "Anthropic Claude 系列，安全可靠",
	},
	{
		id: "ollama",
		name: "Ollama (本地)",
		icon: "🦙",
		baseURL: "http://localhost:11434/v1",
		apiKey: "ollama",
		models: [
			{ id: "qwen2.5-coder:14b", name: "Qwen2.5 Coder 14B", isDefault: true },
			{
				id: "deepseek-coder-v2:16b",
				name: "DeepSeek Coder V2 16B",
				isDefault: false,
			},
			{ id: "codellama:13b", name: "CodeLlama 13B", isDefault: false },
		],
		enabled: false,
		isLocal: true,
		description: "本地推理，数据不出内网",
	},
	{
		id: "local",
		name: "本地 LLM",
		icon: "💻",
		baseURL: "http://localhost:11434/v1",
		apiKey: "local",
		models: [{ id: "auto", name: "自动检测", isDefault: true }],
		enabled: false,
		isLocal: true,
		description: "本地推理（Ollama / LM Studio 等 OpenAI 兼容端点）",
	},
];

/**
 * 将 ExecutionProfileId 映射为 LLMMode：
 * - demo  → mock
 * - cloud → api
 * - local → local
 */
function profileIdToMode(profileId: "demo" | "cloud" | "local"): LLMMode {
	if (profileId === "demo") return "mock";
	if (profileId === "cloud") return "api";
	return "local";
}

export const useProviderStore = defineStore("provider", () => {
	// Load from localStorage or use defaults
	const saved = localStorage.getItem("skyforge-providers");
	const providers = ref<ProviderConfig[]>(
		(saved ? JSON.parse(saved) : DEFAULT_PROVIDERS).map(
			(provider: ProviderConfig) => ({
				...provider,
				// Browser persistence of secrets is intentionally retired. Existing
				// plaintext keys are scrubbed on first load.
				apiKey: provider.isLocal ? provider.apiKey : "",
			}),
		),
	);

	const selectedProviderId = ref(
		localStorage.getItem("skyforge-selected-provider") || "deepseek",
	);
	const selectedModelId = ref(
		localStorage.getItem("skyforge-selected-model") || "deepseek-chat",
	);

	// Computed
	const selectedProvider = computed(() =>
		providers.value.find((p) => p.id === selectedProviderId.value),
	);
	const selectedModel = computed(() =>
		selectedProvider.value?.models.find((m) => m.id === selectedModelId.value),
	);
	const enabledProviders = computed(() =>
		providers.value.filter((p) => p.enabled),
	);
	const isLocalModel = computed(() => selectedProvider.value?.isLocal ?? false);

	/**
	 * 派生模式：唯一权威来源为 executionStore.profileId。
	 *
	 * 旧版 `providerStore.mode` ref 与 `setMode` action 已被移除，调用方应使用：
	 * - `derivedMode`：mode 的响应式只读视图
	 * - `executionStore.setProfile(...)`：修改 mode 的唯一通道
	 */
	const derivedMode = computed<LLMMode>(() =>
		profileIdToMode(useExecutionStore().profileId),
	);

	// Actions
	function setProvider(providerId: string) {
		const provider = providers.value.find((p) => p.id === providerId);
		if (!provider) return;

		selectedProviderId.value = providerId;
		localStorage.setItem("skyforge-selected-provider", providerId);

		// Auto-select default model
		const defaultModel =
			provider.models.find((m) => m.isDefault) || provider.models[0];
		if (defaultModel) {
			selectedModelId.value = defaultModel.id;
			localStorage.setItem("skyforge-selected-model", defaultModel.id);
		}
	}

	function setModel(modelId: string) {
		selectedModelId.value = modelId;
		localStorage.setItem("skyforge-selected-model", modelId);
	}

	function setApiKey(providerId: string, key: string) {
		const provider = providers.value.find((p) => p.id === providerId);
		if (provider) {
			provider.apiKey = key;
			provider.enabled = key.length > 0;
			// Kept in memory only for legacy dialogs. Competition profiles obtain
			// cloud credentials from the backend and never persist the key here.
			persist();
		}
	}

	function toggleProvider(providerId: string) {
		const provider = providers.value.find((p) => p.id === providerId);
		if (provider) {
			provider.enabled = !provider.enabled;
			persist();
		}
	}

	function persist() {
		localStorage.setItem(
			"skyforge-providers",
			JSON.stringify(
				providers.value.map((provider) => ({
					...provider,
					apiKey: provider.isLocal ? provider.apiKey : "",
				})),
			),
		);
	}

	// Get current provider info for API calls
	function getCurrentProviderConfig() {
		const provider = selectedProvider.value;
		if (!provider) return null;
		return {
			provider: provider.id,
			baseURL: provider.baseURL,
			apiKey: provider.apiKey,
			model: selectedModelId.value,
			isLocal: provider.isLocal,
		};
	}

	/**
	 * 聚合 derivedMode 与 providerStore 现有字段，返回统一的 LLM 配置结构
	 *
	 * - mode: 由 executionStore.profileId 派生（仅只读）
	 * - provider: 当前 selectedProvider 的 id（无则为 null）
	 * - apiKey: 当前 provider 的 apiKey
	 * - baseUrl: 当前 provider 的 baseURL
	 * - model: 当前 selectedModel 的 id（无则为 null）
	 */
	function getLLMConfig(): {
		mode: LLMMode;
		provider: string | null;
		apiKey: string;
		baseUrl: string;
		model: string | null;
	} {
		const provider = selectedProvider.value;
		return {
			mode: derivedMode.value,
			provider: provider?.id ?? null,
			apiKey: provider?.apiKey ?? "",
			baseUrl: provider?.baseURL ?? "",
			model: selectedModel.value?.id ?? null,
		};
	}

	return {
		providers,
		selectedProviderId,
		selectedModelId,
		derivedMode,
		selectedProvider,
		selectedModel,
		enabledProviders,
		isLocalModel,
		setProvider,
		setModel,
		setApiKey,
		toggleProvider,
		getCurrentProviderConfig,
		getLLMConfig,
	};
});
