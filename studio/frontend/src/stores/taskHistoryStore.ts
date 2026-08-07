import { defineStore } from "pinia";
import { computed, ref } from "vue";

export interface HistoryEntry {
	id: string;
	timestamp: number;
	profile: "cloud" | "local";
	code: string;
	language?: string;
	requirement?: string;
	result?: {
		success: boolean;
		message?: string;
	};
}

function loadHistory(): HistoryEntry[] {
	return [];
}

function saveHistory(_list: HistoryEntry[]): void {}

export const useTaskHistoryStore = defineStore("taskHistory", () => {
	const history = ref<HistoryEntry[]>(loadHistory());

	const sortedHistory = computed(() =>
		[...history.value].sort((a, b) => b.timestamp - a.timestamp),
	);

	function addEntry(entry: HistoryEntry) {
		history.value.push(entry);
		saveHistory(history.value);
	}

	function clearHistory() {
		history.value = [];
		saveHistory(history.value);
	}

	function addTask(id: string, profile: "cloud" | "local") {
		const existing = history.value.find((e) => e.id === id);
		if (existing) return;
		history.value.push({
			id,
			timestamp: Date.now(),
			profile,
			code: "",
		});
		saveHistory(history.value);
	}

	function updateTask(id: string) {
		const entry = history.value.find((e) => e.id === id);
		if (entry) {
			entry.timestamp = Date.now();
			saveHistory(history.value);
		}
	}

	return {
		history,
		sortedHistory,
		addEntry,
		clearHistory,
		addTask,
		updateTask,
	};
});
