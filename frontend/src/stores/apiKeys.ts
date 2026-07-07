import { AgentType } from "@/utils/enum";
import type { ModelConfig } from "@/utils/interface";
import { defineStore } from "pinia";
import { computed, ref } from "vue";

/** API Key 和模型配置 Store */
export const useApiKeyStore = defineStore(
	"apiKeys",
	() => {
		// ---- State ----

		/** 需求解析模型配置 (REQ-Parser) */
		const reqParserConfig = ref<ModelConfig>({
			apiKey: "",
			baseUrl: "",
			modelId: "",
			apiType: "",
			contextWindow: 128000,
		});

		/** 合约生成模型配置 (CON-Gen) */
		const conGenConfig = ref<ModelConfig>({
			apiKey: "",
			baseUrl: "",
			modelId: "",
			apiType: "",
			contextWindow: 128000,
		});

		/** 代码生成模型配置 (CODE-Gen) */
		const codeGenConfig = ref<ModelConfig>({
			apiKey: "",
			baseUrl: "",
			modelId: "",
			apiType: "",
			contextWindow: 128000,
		});

		/** 修复模型配置 (REPAIR) */
		const reviewerConfig = ref<ModelConfig>({
			apiKey: "",
			baseUrl: "",
			modelId: "",
			apiType: "",
			contextWindow: 128000,
		});

		/** OpenAlex 邮箱 */
		const openalexEmail = ref<string>("");

		// ---- Getters ----

		/** 判断所有配置是否为空 */
		const isEmpty = computed(() => {
			return Object.values(getAllAgentConfigs()).every(
				(config) => config.apiKey === "",
			);
		});

		// ---- Actions ----

		/** 设置需求解析模型配置 (REQ-Parser) */
		function setReqParserConfig(config: ModelConfig) {
			reqParserConfig.value = { ...config };
		}

		/** 设置合约生成模型配置 (CON-Gen) */
		function setConGenConfig(config: ModelConfig) {
			conGenConfig.value = { ...config };
		}

		/** 设置代码生成模型配置 (CODE-Gen) */
		function setCodeGenConfig(config: ModelConfig) {
			codeGenConfig.value = { ...config };
		}

		/** 设置修复模型配置 (REPAIR) */
		function setReviewerConfig(config: ModelConfig) {
			reviewerConfig.value = { ...config };
		}

		/** 设置 OpenAlex 邮箱 */
		function setOpenalexEmail(email: string) {
			openalexEmail.value = email;
		}

		/** 获取所有 Agent 的模型配置 */
		function getAllAgentConfigs() {
			return {
				[AgentType.REQ_PARSER]: reqParserConfig.value,
				[AgentType.CON_GEN]: conGenConfig.value,
				[AgentType.CODE_GEN]: codeGenConfig.value,
				[AgentType.REPAIR]: reviewerConfig.value,
			};
		}

		/** 重置所有配置为默认值 */
		function resetAll() {
			reqParserConfig.value = {
				apiKey: "",
				baseUrl: "",
				modelId: "",
				apiType: "",
				contextWindow: 128000,
			};
			conGenConfig.value = {
				apiKey: "",
				baseUrl: "",
				modelId: "",
				apiType: "",
				contextWindow: 128000,
			};
			codeGenConfig.value = {
				apiKey: "",
				baseUrl: "",
				modelId: "",
				apiType: "",
				contextWindow: 128000,
			};
			reviewerConfig.value = {
				apiKey: "",
				baseUrl: "",
				modelId: "",
				apiType: "",
				contextWindow: 128000,
			};
			openalexEmail.value = "";
		}

		return {
			// 状态
			reqParserConfig,
			conGenConfig,
			codeGenConfig,
			reviewerConfig,
			openalexEmail,
			isEmpty,

			// 方法
			setReqParserConfig,
			setConGenConfig,
			setCodeGenConfig,
			setReviewerConfig,
			setOpenalexEmail,
			getAllAgentConfigs,
			resetAll,
		};
	},
	{
		persist: {
			storage: sessionStorage, // 使用 sessionStorage 防止长期暴露
		},
	},
);
