import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";

const TASK_HISTORY_STORAGE_KEY = "skyforge-task-history";
const MAX_HISTORY_ITEMS = 50;

interface HistoryEntry {
	taskId: string;
	profileId: string;
	lastUpdated: string;
}

function loadHistory(): HistoryEntry[] {
	try {
		const raw = localStorage.getItem(TASK_HISTORY_STORAGE_KEY);
		if (!raw) return [];
		const parsed = JSON.parse(raw);
		if (Array.isArray(parsed)) return parsed.slice(0, MAX_HISTORY_ITEMS);
		return [];
	} catch {
		return [];
	}
}

function saveHistory(entries: HistoryEntry[]) {
	try {
		localStorage.setItem(
			TASK_HISTORY_STORAGE_KEY,
			JSON.stringify(entries.slice(0, MAX_HISTORY_ITEMS)),
		);
	} catch {
		// storage full or unavailable, ignore
	}
}

export const useTaskHistoryStore = defineStore("task-history", () => {
	const history = ref<HistoryEntry[]>(loadHistory());

	const taskIds = computed(() => history.value.map((h) => h.taskId));

	function addTask(taskId: string, profileId: string) {
		const existing = history.value.findIndex((h) => h.taskId === taskId);
		const entry: HistoryEntry = {
			taskId,
			profileId,
			lastUpdated: new Date().toISOString(),
		};
		if (existing >= 0) {
			history.value[existing] = entry;
		} else {
			history.value.unshift(entry);
			if (history.value.length > MAX_HISTORY_ITEMS) {
				history.value = history.value.slice(0, MAX_HISTORY_ITEMS);
			}
		}
		saveHistory(history.value);
	}

	function updateTask(taskId: string) {
		const entry = history.value.find((h) => h.taskId === taskId);
		if (entry) {
			entry.lastUpdated = new Date().toISOString();
			saveHistory(history.value);
		}
	}

	function removeTask(taskId: string) {
		history.value = history.value.filter((h) => h.taskId !== taskId);
		saveHistory(history.value);
	}

	function hasTask(taskId: string): boolean {
		return history.value.some((h) => h.taskId === taskId);
	}

	function getProfileTaskIds(profileId: string): string[] {
		return history.value
			.filter((h) => h.profileId === profileId)
			.map((h) => h.taskId);
	}

	function clear() {
		history.value = [];
		saveHistory([]);
	}

	watch(
		history,
		(val) => {
			saveHistory(val);
		},
		{ deep: true },
	);

	return {
		history,
		taskIds,
		addTask,
		updateTask,
		removeTask,
		hasTask,
		getProfileTaskIds,
		clear,
	};
});
