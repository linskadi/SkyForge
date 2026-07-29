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

	return {
		history,
		sortedHistory,
		addEntry,
		clearHistory,
	};
});
