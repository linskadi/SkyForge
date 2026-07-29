import { defineStore } from "pinia";
import { ref } from "vue";
import { getApi } from "@/services/apiSwitcher";

export interface ReviewTemplateItem {
	id: string;
	title: string;
	description: string;
	category: string;
	guideline_ref: string;
}

export interface ReviewTemplate {
	checkpoint: string;
	items: ReviewTemplateItem[];
	version: string;
}

export interface ReviewComment {
	id: string;
	item_id: string;
	content: string;
	author: string;
	status: "open" | "addressed" | "resolved";
	code_ref: string;
	contract_ref: string;
	created_at: string;
	updated_at: string;
}

export interface HITLStats {
	total_requests: number;
	pending_count: number;
	approved_count: number;
	rejected_count: number;
	timeout_count: number;
	approval_rate: number;
	avg_review_time_sec: number;
	by_checkpoint: Record<string, Record<string, number>>;
	generated_at: string;
}

export const useHITLStore = defineStore("hitl", () => {
	const stats = ref<HITLStats | null>(null);
	const templates = ref<Record<string, ReviewTemplate>>({});
	const comments = ref<Record<string, ReviewComment[]>>({});
	const loading = ref(false);

	async function fetchStats() {
		try {
			const res = await fetch("/api/hil/stats");
			if (res.ok) {
				stats.value = await res.json();
			}
		} catch (e) {
			console.warn("[HITLStore] 获取统计失败:", e);
		}
	}

	async function fetchTemplate(checkpoint: string): Promise<ReviewTemplate | null> {
		if (templates.value[checkpoint]) {
			return templates.value[checkpoint];
		}
		try {
			const res = await fetch(`/api/hil/template/${checkpoint}`);
			if (res.ok) {
				const tpl = await res.json();
				templates.value[checkpoint] = tpl;
				return tpl;
			}
		} catch (e) {
			console.warn("[HITLStore] 获取模板失败:", e);
		}
		return null;
	}

	async function fetchComments(requestId: string): Promise<ReviewComment[]> {
		try {
			const res = await fetch(`/api/hil/comments/${requestId}`);
			if (res.ok) {
				const data = await res.json();
				comments.value[requestId] = data.comments || [];
				return comments.value[requestId];
			}
		} catch (e) {
			console.warn("[HITLStore] 获取意见失败:", e);
		}
		return [];
	}

	async function addComment(requestId: string, content: string, itemId: string = ""): Promise<boolean> {
		try {
			const res = await fetch(`/api/hil/comments/${requestId}`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ content, item_id: itemId, author: "reviewer" }),
			});
			if (res.ok) {
				await fetchComments(requestId);
				return true;
			}
		} catch (e) {
			console.warn("[HITLStore] 添加意见失败:", e);
		}
		return false;
	}

	async function updateCommentStatus(
		requestId: string,
		commentId: string,
		status: "open" | "addressed" | "resolved",
	): Promise<boolean> {
		try {
			const res = await fetch(`/api/hil/comments/${requestId}/${commentId}`, {
				method: "PATCH",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ status }),
			});
			if (res.ok) {
				await fetchComments(requestId);
				return true;
			}
		} catch (e) {
			console.warn("[HITLStore] 更新意见失败:", e);
		}
		return false;
	}

	return {
		stats,
		templates,
		comments,
		loading,
		fetchStats,
		fetchTemplate,
		fetchComments,
		addComment,
		updateCommentStatus,
	};
});
