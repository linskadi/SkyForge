import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { i18n } from "@/i18n";
import type { ExecutionProfile, ExecutionProfileId } from "@/types/execution";

/** localStorage key：execution profile 唯一持久化 key */
export const EXECUTION_PROFILE_STORAGE_KEY = "skyforge-execution-profile";

/**
 * 翻译 data 层标签：键可解析时返回译文，
 * 键缺失（t 返回键路径本身）时回退到中文默认文案。
 */
function dataT(key: string, fallback: string): string {
	const resolved = i18n.global.t(key);
	return resolved === key ? fallback : resolved;
}

const PROFILES: Record<ExecutionProfileId, ExecutionProfile> = {
	cloud: {
		id: "cloud",
		label: dataT("data.status.executionProfile.cloud", "云 API · 实时/回放"),
		available: true,
		source: "live",
		provider: "server-managed",
	},
	local: {
		id: "local",
		label: dataT("data.status.executionProfile.local", "本地模型 · 实时/回放"),
		available: true,
		source: "live",
		provider: "OpenAI-compatible",
	},
};

export const useExecutionStore = defineStore("execution-profile", () => {
	const saved = localStorage.getItem(EXECUTION_PROFILE_STORAGE_KEY);
	const profileId = ref<ExecutionProfileId>(
		saved === "cloud" || saved === "local" ? saved : "cloud",
	);
	const profile = computed(() => PROFILES[profileId.value]);

	function setProfile(id: ExecutionProfileId) {
		profileId.value = id;
		localStorage.setItem(EXECUTION_PROFILE_STORAGE_KEY, id);
	}

	return { profileId, profile, profiles: Object.values(PROFILES), setProfile };
});
