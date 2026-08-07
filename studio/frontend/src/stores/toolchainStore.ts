import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { i18n } from "@/i18n";

export interface ToolchainTool {
	name: string;
	min_version: string;
	description: string;
	install_hint: string;
	found: boolean;
	version: string;
}

/**
 * 翻译 data 层标签：键可解析时返回译文，
 * 键缺失（t 返回键路径本身）时回退到调用方提供的默认字符串。
 */
function dataT(
	key: string,
	fallback: string,
	params?: Record<string, unknown>,
): string {
	const resolved = i18n.global.t(key, params ?? {});
	return resolved === key ? fallback : resolved;
}

export const useToolchainStore = defineStore("toolchain", () => {
	const tools = ref<ToolchainTool[]>([]);
	const loading = ref(false);
	const error = ref<string | null>(null);

	const availableCount = computed(
		() => tools.value.filter((t) => t.found).length,
	);
	const totalCount = computed(() => tools.value.length);

	async function fetchTools() {
		loading.value = true;
		error.value = null;
		try {
			const res = await fetch("/api/tools/registry");
			if (res.ok) {
				tools.value = await res.json();
			} else {
				throw new Error(
					dataT("data.error.httpStatus", `HTTP ${res.status}`, {
						status: res.status,
						statusText: res.statusText,
					}),
				);
			}
		} catch (e) {
			error.value =
				e instanceof Error
					? e.message
					: dataT("data.error.unknown", "未知错误");
			console.warn("[toolchainStore] 获取工具链状态失败:", e);
		} finally {
			loading.value = false;
		}
	}

	let pollTimer: ReturnType<typeof setInterval> | null = null;
	const POLL_INTERVAL_MS = 60000;

	function startPolling() {
		if (pollTimer) return;
		pollTimer = setInterval(() => {
			fetchTools();
		}, POLL_INTERVAL_MS);
	}

	function stopPolling() {
		if (pollTimer) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
	}

	async function getInstallHint(
		toolName: string,
	): Promise<Record<string, string>> {
		try {
			const res = await fetch(`/api/tools/${toolName}/install-hint`);
			if (res.ok) {
				const data = await res.json();
				return data.hints || {};
			}
		} catch (e) {
			console.warn("[toolchainStore] 获取安装指引失败:", e);
		}
		return {};
	}

	async function checkTool(toolName: string): Promise<boolean> {
		await fetchTools();
		const tool = tools.value.find((t) => t.name === toolName);
		return tool?.found ?? false;
	}

	return {
		tools,
		loading,
		error,
		availableCount,
		totalCount,
		fetchTools,
		startPolling,
		stopPolling,
		getInstallHint,
		checkTool,
	};
});
