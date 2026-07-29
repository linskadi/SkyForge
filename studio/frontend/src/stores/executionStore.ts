import { defineStore } from "pinia";
import { computed, ref } from "vue";
import type { ExecutionProfile, ExecutionProfileId } from "@/types/execution";

/** localStorage key：execution profile 唯一持久化 key */
export const EXECUTION_PROFILE_STORAGE_KEY = "skyforge-execution-profile";

const PROFILES: Record<ExecutionProfileId, ExecutionProfile> = {
	cloud: {
		id: "cloud",
		label: "云 API · 实时/回放",
		available: true,
		source: "live",
		provider: "server-managed",
	},
	local: {
		id: "local",
		label: "本地模型 · 实时/回放",
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
