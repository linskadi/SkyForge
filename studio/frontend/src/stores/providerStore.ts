/**
 * Provider Store — OpenCode 风格的多供应商配置管理。
 *
 * 支持: DeepSeek / Qwen / OpenAI / Anthropic / Ollama / LM Studio / 通用兼容
 * 每个 Provider 独立 API Key + Model 列表，localStorage 持久化。
 */
import { defineStore } from "pinia";
import { computed, ref } from "vue";

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
		id: "lmstudio",
		name: "LM Studio (本地)",
		icon: "💻",
		baseURL: "http://localhost:1234/v1",
		apiKey: "lm-studio",
		models: [{ id: "auto", name: "自动检测 (Loaded Model)", isDefault: true }],
		enabled: false,
		isLocal: true,
		description: "本地推理，GUI 管理模型",
	},
];

export const useProviderStore = defineStore("provider", () => {
	// Load from localStorage or use defaults
	const saved = localStorage.getItem("skyforge-providers");
	const providers = ref<ProviderConfig[]>(
		saved ? JSON.parse(saved) : DEFAULT_PROVIDERS,
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
		localStorage.setItem("skyforge-providers", JSON.stringify(providers.value));
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

	return {
		providers,
		selectedProviderId,
		selectedModelId,
		selectedProvider,
		selectedModel,
		enabledProviders,
		isLocalModel,
		setProvider,
		setModel,
		setApiKey,
		toggleProvider,
		getCurrentProviderConfig,
	};
});
