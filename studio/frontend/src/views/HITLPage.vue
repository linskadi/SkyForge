<script setup lang="ts">
import {
	ArrowLeft,
	CheckCircle2,
	ClipboardList,
	Clock,
	Download,
	FileText,
	Filter,
	History,
	Loader2,
	MessageSquare,
	RefreshCw,
	Shield,
	ShieldCheck,
	ShieldX,
	XCircle,
} from "@lucide/vue";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { getHITLHistory } from "@/services/api";
import { getApi } from "@/services/apiSwitcher";
import { useExecutionStore } from "@/stores/executionStore";
import type { ReviewComment, ReviewTemplate } from "@/stores/hitlStore";
import { useHITLStore } from "@/stores/hitlStore";
import type {
	HITLApproval,
	HITLCheckpointType,
	HITLHistoryItem,
} from "@/types/domain";

const router = useRouter();
const execution = useExecutionStore();
const hitlStore = useHITLStore();

const currentTemplate = ref<ReviewTemplate | null>(null);
const currentComments = ref<ReviewComment[]>([]);
const newCommentText = ref("");
const submittingComment = ref(false);

const pendingList = ref<HITLApproval[]>([]);
const historyList = ref<HITLHistoryItem[]>([]);
const loading = ref<boolean>(false);
const actionLoading = ref<Record<string, boolean>>({});
const errorMsg = ref<string>("");
const selectedId = ref<string>("");
const commentText = ref<string>("");
const selectedIds = ref<Set<string>>(new Set());
const now = ref<number>(Date.now());
let timer: ReturnType<typeof setInterval> | null = null;

type HistoryFilterType = "all" | HITLCheckpointType;
type HistoryFilterResult = "all" | "approved" | "rejected";

const historyFilterType = ref<HistoryFilterType>("all");
const historyFilterResult = ref<HistoryFilterResult>("all");

const checkpointConfig: Record<
	HITLCheckpointType,
	{ name: string; icon: string; color: string }
> = {
	requirement_review: {
		name: "需求审查",
		icon: "📝",
		color: "text-sky-500 bg-sky-500/10",
	},
	contract_review: {
		name: "契约审查",
		icon: "📋",
		color: "text-violet-500 bg-violet-500/10",
	},
	code_review: {
		name: "代码审查",
		icon: "💻",
		color: "text-emerald-500 bg-emerald-500/10",
	},
	final_review: {
		name: "最终审查",
		icon: "🏁",
		color: "text-rose-500 bg-rose-500/10",
	},
};

interface StatCard {
	label: string;
	value: number;
	trend: number;
	icon: typeof ClipboardList;
	variant: "default" | "success" | "destructive" | "warning";
}

const stats = computed<StatCard[]>(() => {
	const s = hitlStore.stats;
	const pending = s?.pending_count ?? pendingList.value.length;
	const approved =
		s?.approved_count ??
		historyList.value.filter((h) => h.status === "approved").length;
	const rejected =
		s?.rejected_count ??
		historyList.value.filter((h) => h.status === "rejected").length;
	const timeout =
		s?.timeout_count ??
		pendingList.value.filter((item) => item.deadline - now.value <= 0).length;

	return [
		{
			label: "待审查",
			value: pending,
			trend: 2,
			icon: ClipboardList,
			variant: "default",
		},
		{
			label: "已通过",
			value: approved,
			trend: 5,
			icon: ShieldCheck,
			variant: "success",
		},
		{
			label: "已拒绝",
			value: rejected,
			trend: -1,
			icon: ShieldX,
			variant: "destructive",
		},
		{
			label: "超时",
			value: timeout,
			trend: 0,
			icon: Clock,
			variant: "warning",
		},
	];
});

const groupedPending = computed(() => {
	const groups: Record<HITLCheckpointType, HITLApproval[]> = {
		requirement_review: [],
		contract_review: [],
		code_review: [],
		final_review: [],
	};
	for (const item of pendingList.value) {
		groups[item.checkpoint].push(item);
	}
	return groups;
});

const selectedItem = computed(() => {
	return pendingList.value.find((item) => item.request_id === selectedId.value);
});

const filteredHistory = computed(() => {
	let result = [...historyList.value];
	if (historyFilterType.value !== "all") {
		result = result.filter((h) => h.checkpoint === historyFilterType.value);
	}
	if (historyFilterResult.value !== "all") {
		result = result.filter((h) => h.status === historyFilterResult.value);
	}
	return result;
});

const loadPending = async () => {
	loading.value = true;
	errorMsg.value = "";
	try {
		const [pending, history] = await Promise.all([
			getApi().getHITLPendingApprovals(),
			getHITLHistory(),
		]);
		pendingList.value = pending;
		historyList.value = history;
		if (pending.length > 0 && !selectedId.value) {
			selectedId.value = pending[0].request_id;
		}
	} catch (err) {
		console.error("[HITLPage] 加载失败：", err);
		errorMsg.value = err instanceof Error ? err.message : "加载失败";
	} finally {
		loading.value = false;
	}
};

const remainingTime = (
	deadline: number,
): { text: string; urgent: boolean; expired: boolean } => {
	const diff = deadline - now.value;
	if (diff <= 0) {
		return { text: "已超时", urgent: true, expired: true };
	}
	const minutes = Math.floor(diff / 60000);
	const seconds = Math.floor((diff % 60000) / 1000);
	return {
		text: `${minutes}m ${seconds}s`,
		urgent: diff < 5 * 60 * 1000,
		expired: false,
	};
};

const formatTime = (ts: number): string => {
	const d = new Date(ts);
	const pad = (n: number) => n.toString().padStart(2, "0");
	return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

const formatFullTime = (ts: number): string => {
	const d = new Date(ts);
	const pad = (n: number) => n.toString().padStart(2, "0");
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
};

const selectItem = (id: string) => {
	selectedId.value = id;
	commentText.value = "";
};

const toggleSelect = (id: string, event: Event) => {
	event.stopPropagation();
	if (selectedIds.value.has(id)) {
		selectedIds.value.delete(id);
	} else {
		selectedIds.value.add(id);
	}
	selectedIds.value = new Set(selectedIds.value);
};

const onApprove = async () => {
	const item = selectedItem.value;
	if (!item) return;
	actionLoading.value = { ...actionLoading.value, [item.request_id]: true };
	try {
		await getApi().hitlApprove(item.request_id, commentText.value);
		commentText.value = "";
		await loadPending();
	} catch (err) {
		console.error("[HITLPage] 批准失败：", err);
		errorMsg.value = err instanceof Error ? err.message : "批准失败";
	} finally {
		actionLoading.value = { ...actionLoading.value, [item.request_id]: false };
	}
};

const onReject = async () => {
	const item = selectedItem.value;
	if (!item) return;
	if (!commentText.value.trim()) {
		errorMsg.value = "拒绝时必须填写理由";
		return;
	}
	actionLoading.value = { ...actionLoading.value, [item.request_id]: true };
	try {
		await getApi().hitlReject(item.request_id, commentText.value);
		commentText.value = "";
		await loadPending();
	} catch (err) {
		console.error("[HITLPage] 拒绝失败：", err);
		errorMsg.value = err instanceof Error ? err.message : "拒绝失败";
	} finally {
		actionLoading.value = { ...actionLoading.value, [item.request_id]: false };
	}
};

const batchApprove = async () => {
	if (selectedIds.value.size === 0) return;
	for (const id of selectedIds.value) {
		actionLoading.value = { ...actionLoading.value, [id]: true };
		try {
			await getApi().hitlApprove(id, "");
		} catch (err) {
			console.error("[HITLPage] 批量批准失败：", err);
		} finally {
			actionLoading.value = { ...actionLoading.value, [id]: false };
		}
	}
	selectedIds.value = new Set();
	await loadPending();
};

const exportHistory = () => {
	console.log("[HITLPage] 导出审查历史");
};

watch(selectedId, async (newId) => {
	if (newId) {
		const pending = pendingList.value.find((p) => p.request_id === newId);
		if (pending) {
			currentTemplate.value = await hitlStore.fetchTemplate(pending.checkpoint);
			currentComments.value = await hitlStore.fetchComments(newId);
		}
		hitlStore.fetchStats();
	} else {
		currentTemplate.value = null;
		currentComments.value = [];
	}
});

const onAddComment = async () => {
	if (!selectedId.value || !newCommentText.value.trim()) return;
	submittingComment.value = true;
	try {
		const ok = await hitlStore.addComment(
			selectedId.value,
			newCommentText.value.trim(),
		);
		if (ok) {
			currentComments.value = await hitlStore.fetchComments(selectedId.value);
			newCommentText.value = "";
		}
	} finally {
		submittingComment.value = false;
	}
};

const onUpdateCommentStatus = async (
	commentId: string,
	status: "open" | "addressed" | "resolved",
) => {
	if (!selectedId.value) return;
	await hitlStore.updateCommentStatus(selectedId.value, commentId, status);
	currentComments.value = await hitlStore.fetchComments(selectedId.value);
};

const nextStatus = (current: string): "open" | "addressed" | "resolved" => {
	if (current === "open") return "addressed";
	if (current === "addressed") return "resolved";
	return "open";
};

const statusLabel: Record<string, string> = {
	open: "待处理",
	addressed: "已回应",
	resolved: "已解决",
};

const statusClass: Record<string, string> = {
	open: "bg-amber-500/10 text-amber-500 border-amber-500/20",
	addressed: "bg-sky-500/10 text-sky-500 border-sky-500/20",
	resolved: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
};

onMounted(() => {
	loadPending();
	timer = setInterval(() => {
		now.value = Date.now();
	}, 1000);
	document.addEventListener("visibilitychange", handleVisibilityChange);
});

onBeforeUnmount(() => {
	if (timer) {
		clearInterval(timer);
		timer = null;
	}
	document.removeEventListener("visibilitychange", handleVisibilityChange);
});

function handleVisibilityChange() {
	if (document.hidden) {
		if (timer) {
			clearInterval(timer);
			timer = null;
		}
	} else if (!timer) {
		timer = setInterval(() => {
			now.value = Date.now();
		}, 1000);
	}
}
</script>

<template>
	<div class="min-h-screen bg-background">
		<div class="mx-auto max-w-[1400px] px-8 py-6">
			<header class="mb-6">
				<div class="flex items-center gap-3 mb-2">
					<button
						class="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:border-primary hover:text-primary"
						@click="router.push('/')"
						title="返回首页"
					>
						<ArrowLeft class="h-4 w-4" />
					</button>
					<h1 class="text-2xl font-semibold text-foreground flex items-center gap-2">
						<ClipboardList class="h-6 w-6 text-primary" />
						HITL 审查工作台
					</h1>
				</div>
				<p class="text-sm text-muted-foreground ml-11">
					需求审查 / 契约审查 / 代码审查 / 最终审查 — Human-in-the-Loop 检查点管理
				</p>
			</header>

			<section class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
				<Card
					v-for="stat in stats"
					:key="stat.label"
					class="bg-card border border-border rounded-component-md shadow-card transition-all hover:shadow-md"
				>
					<CardContent class="p-5">
						<div class="flex items-start justify-between">
							<div>
								<p class="text-sm text-muted-foreground mb-1">{{ stat.label }}</p>
								<p class="text-3xl font-semibold text-foreground">{{ stat.value }}</p>
								<p
									class="text-xs mt-1"
									:class="
										stat.trend >= 0
											? 'text-emerald-500'
											: 'text-rose-500'
									"
								>
									{{ stat.trend >= 0 ? "+" : "" }}{{ stat.trend }} 较昨日
								</p>
							</div>
							<div
								class="inline-flex h-10 w-10 items-center justify-center rounded-lg"
								:class="{
									'bg-primary/10 text-primary': stat.variant === 'default',
									'bg-emerald-500/10 text-emerald-500': stat.variant === 'success',
									'bg-rose-500/10 text-rose-500': stat.variant === 'destructive',
									'bg-amber-500/10 text-amber-500': stat.variant === 'warning',
								}"
							>
								<component :is="stat.icon" class="h-5 w-5" />
							</div>
						</div>
					</CardContent>
				</Card>
			</section>

			<Tabs defaultValue="pending" class="w-full">
				<TabsList class="mb-6">
					<TabsTrigger value="pending" class="gap-2">
						<Shield class="h-4 w-4" />
						待审查
						<Badge variant="secondary" class="ml-1">{{ pendingList.length }}</Badge>
					</TabsTrigger>
					<TabsTrigger value="history" class="gap-2">
						<History class="h-4 w-4" />
						审查历史
					</TabsTrigger>
				</TabsList>

				<TabsContent value="pending">
					<div class="grid grid-cols-1 lg:grid-cols-10 gap-4">
						<Card
							class="lg:col-span-3 bg-card border border-border rounded-component-md shadow-card overflow-hidden"
						>
							<CardHeader class="pb-3 border-b border-border">
								<div class="flex items-center justify-between">
									<CardTitle class="text-base font-semibold">
										待审查列表
									</CardTitle>
									<Button
										variant="ghost"
										size="sm"
										:disabled="loading"
										@click="loadPending"
										class="h-8 px-2"
									>
										<RefreshCw v-if="loading" class="h-4 w-4 animate-spin" />
										<RefreshCw v-else class="h-4 w-4" />
									</Button>
								</div>
							</CardHeader>
							<CardContent class="p-0">
								<div v-if="loading && pendingList.length === 0" class="p-8 text-center">
									<Loader2 class="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
									<p class="mt-2 text-sm text-muted-foreground">加载中...</p>
								</div>
								<div v-else-if="pendingList.length === 0" class="p-8 text-center">
									<CheckCircle2 class="h-8 w-8 mx-auto text-emerald-500" />
									<p class="mt-2 text-sm text-muted-foreground">暂无待审查项</p>
								</div>
								<div v-else class="max-h-[600px] overflow-y-auto">
									<template
										v-for="(items, type) in groupedPending"
										:key="type"
									>
										<div v-if="items.length > 0" class="px-4 py-2 bg-muted/30 border-b border-border">
											<span class="text-xs font-medium text-muted-foreground uppercase tracking-wide">
												{{ checkpointConfig[type as HITLCheckpointType].name }}
												({{ items.length }})
											</span>
										</div>
										<div
											v-for="item in items"
											:key="item.request_id"
											class="px-4 py-3 border-b border-border cursor-pointer transition-colors"
											:class="{
												'bg-muted/50 hover:bg-muted/70': selectedId !== item.request_id,
												'bg-primary/10': selectedId === item.request_id,
											}"
											@click="selectItem(item.request_id)"
										>
											<div class="flex items-start gap-3">
												<input
													type="checkbox"
													class="mt-1 h-4 w-4 rounded border-border"
													:checked="selectedIds.has(item.request_id)"
													@click="(e) => toggleSelect(item.request_id, e)"
												/>
												<div class="flex-1 min-w-0">
													<div class="flex items-center gap-2 mb-1">
														<span class="text-base">
															{{ checkpointConfig[item.checkpoint].icon }}
														</span>
														<Badge
															variant="secondary"
															class="text-xs"
														>
															{{ item.checkpoint_name }}
														</Badge>
													</div>
													<p class="text-sm font-medium text-foreground line-clamp-2 mb-1">
														{{ item.content_preview }}
													</p>
													<div class="flex items-center gap-2 text-xs text-muted-foreground">
														<code class="font-mono">{{ item.request_id }}</code>
													</div>
													<div
														class="mt-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium"
														:class="{
															'bg-emerald-500/10 text-emerald-500':
																!remainingTime(item.deadline).urgent &&
																!remainingTime(item.deadline).expired,
															'bg-amber-500/10 text-amber-500':
																remainingTime(item.deadline).urgent &&
																!remainingTime(item.deadline).expired,
															'bg-rose-500/10 text-rose-500':
																remainingTime(item.deadline).expired,
														}"
													>
														<Clock class="h-3 w-3" />
														{{ remainingTime(item.deadline).text }}
													</div>
												</div>
											</div>
										</div>
									</template>
								</div>
							</CardContent>
						</Card>

						<Card
							class="lg:col-span-5 bg-card border border-border rounded-component-md shadow-card overflow-hidden"
						>
							<CardHeader class="pb-3 border-b border-border">
								<CardTitle class="text-base font-semibold">
									详情预览
								</CardTitle>
							</CardHeader>
							<CardContent class="p-0">
								<div v-if="!selectedItem" class="p-8 text-center">
									<FileText class="h-8 w-8 mx-auto text-muted-foreground" />
									<p class="mt-2 text-sm text-muted-foreground">
										请选择一个审查项
									</p>
								</div>
								<template v-else>
									<div class="p-5 border-b border-border">
										<div class="flex items-center gap-2 mb-3">
											<span class="text-lg">
												{{ checkpointConfig[selectedItem.checkpoint].icon }}
											</span>
											<h3 class="text-lg font-semibold text-foreground">
												{{ selectedItem.checkpoint_name }}
											</h3>
											<Badge variant="secondary" class="ml-auto">
												{{ selectedItem.request_id }}
											</Badge>
										</div>
										<div class="grid grid-cols-2 gap-4 text-sm">
											<div>
												<p class="text-muted-foreground mb-1">提交时间</p>
												<p class="font-medium">
													{{ formatFullTime(selectedItem.submitted_at) }}
												</p>
											</div>
											<div>
												<p class="text-muted-foreground mb-1">截止时间</p>
												<p
													class="font-medium"
													:class="{
														'text-rose-500': remainingTime(
															selectedItem.deadline,
														).expired,
													}"
												>
													{{ formatFullTime(selectedItem.deadline) }}
												</p>
											</div>
										</div>
									</div>
									<div class="p-5 border-b border-border">
										<h4 class="text-sm font-semibold text-foreground mb-3">
											内容预览
										</h4>
										<p class="text-sm text-muted-foreground mb-3">
											{{ selectedItem.content_preview }}
										</p>
										<div
											v-if="selectedItem.content_detail"
											class="bg-muted/50 rounded-lg p-4 overflow-x-auto"
										>
											<pre class="text-xs font-mono text-foreground whitespace-pre-wrap">
{{ selectedItem.content_detail }}</pre
											>
										</div>
									</div>
									<div class="p-5">
										<h4 class="text-sm font-semibold text-foreground mb-3">
											关联任务信息
										</h4>
										<div class="grid grid-cols-3 gap-4 text-sm">
											<div>
												<p class="text-muted-foreground mb-1">任务ID</p>
												<p class="font-medium font-mono text-xs">
													TASK-{{ selectedItem.request_id.split("-").pop() }}
												</p>
											</div>
											<div>
												<p class="text-muted-foreground mb-1">语言</p>
												<p class="font-medium">C</p>
											</div>
											<div>
												<p class="text-muted-foreground mb-1">模型</p>
												<p class="font-medium">DeepSeek</p>
											</div>
										</div>
									</div>
									<div v-if="currentTemplate" class="p-5 border-t border-border">
										<div class="flex items-center justify-between mb-3">
											<h4 class="text-sm font-semibold text-foreground">
												审查模板
											</h4>
											<Badge variant="outline" class="text-xs">
												v{{ currentTemplate.version }}
											</Badge>
										</div>
										<div v-if="currentTemplate.items.length === 0" class="text-sm text-muted-foreground">
											暂无审查项
										</div>
										<div v-else class="space-y-3">
											<div
												v-for="item in currentTemplate.items"
												:key="item.id"
												class="p-3 rounded-lg bg-muted/30 border border-border"
											>
												<div class="flex items-start gap-2">
													<span class="text-sm font-medium text-foreground">
														{{ item.title }}
													</span>
													<Badge variant="secondary" class="text-xs ml-auto">
														{{ item.category }}
													</Badge>
												</div>
												<p class="text-xs text-muted-foreground mt-1">
													{{ item.description }}
												</p>
												<p v-if="item.guideline_ref" class="text-xs text-primary mt-1">
													参考：{{ item.guideline_ref }}
												</p>
											</div>
										</div>
									</div>
								</template>
							</CardContent>
						</Card>

						<Card
							class="lg:col-span-2 bg-card border border-border rounded-component-md shadow-card overflow-hidden"
						>
							<CardHeader class="pb-3 border-b border-border">
								<CardTitle class="text-base font-semibold">
									审查操作
								</CardTitle>
							</CardHeader>
							<CardContent class="p-5">
								<div v-if="!selectedItem" class="text-center py-8">
									<Shield class="h-8 w-8 mx-auto text-muted-foreground" />
									<p class="mt-2 text-sm text-muted-foreground">
										请先选择审查项
									</p>
								</div>
								<template v-else>
									<div class="space-y-4">
										<Button
											class="w-full h-11 text-base font-medium"
											:disabled="actionLoading[selectedItem.request_id]"
											@click="onApprove"
										>
											<CheckCircle2
												v-if="!actionLoading[selectedItem.request_id]"
												class="h-5 w-5"
											/>
											<Loader2 v-else class="h-5 w-5 animate-spin" />
											批准通过
										</Button>
										<Button
											variant="destructive"
											class="w-full h-11 text-base font-medium"
											:disabled="actionLoading[selectedItem.request_id]"
											@click="onReject"
										>
											<XCircle class="h-5 w-5" />
											拒绝
										</Button>
										<div class="pt-2">
											<label
												class="text-sm font-medium text-foreground mb-2 block"
											>
												审查评论
											</label>
											<Textarea
												v-model="commentText"
												placeholder="请输入审查评论（拒绝时必填）..."
												rows="5"
												class="resize-none"
											/>
										</div>
										<div class="pt-4 border-t border-border">
											<div class="flex items-center gap-2 mb-3">
												<MessageSquare class="h-4 w-4 text-muted-foreground" />
												<label class="text-sm font-medium text-foreground">
													审查意见
												</label>
												<Badge variant="secondary" class="text-xs ml-auto">
													{{ currentComments.length }}
												</Badge>
											</div>
											<div class="space-y-2">
												<Textarea
													v-model="newCommentText"
													placeholder="添加审查意见..."
													rows="3"
													class="resize-none text-sm"
												/>
												<Button
													size="sm"
													class="w-full"
													:disabled="!newCommentText.trim() || submittingComment"
													@click="onAddComment"
												>
													<Loader2 v-if="submittingComment" class="h-4 w-4 animate-spin" />
													<MessageSquare v-else class="h-4 w-4" />
													提交意见
												</Button>
											</div>
											<div v-if="currentComments.length > 0" class="mt-4 space-y-3 max-h-[300px] overflow-y-auto">
												<div
													v-for="c in currentComments"
													:key="c.id"
													class="p-3 rounded-lg border border-border bg-muted/20"
												>
													<div class="flex items-center gap-2 mb-2">
														<span class="text-xs font-medium text-foreground">
															{{ c.author }}
														</span>
														<Badge
															variant="outline"
															class="text-xs border"
															:class="statusClass[c.status]"
														>
															{{ statusLabel[c.status] }}
														</Badge>
														<span class="text-xs text-muted-foreground ml-auto">
															{{ c.created_at }}
														</span>
													</div>
													<p class="text-sm text-foreground mb-2">
														{{ c.content }}
													</p>
													<div v-if="c.code_ref || c.contract_ref" class="text-xs text-muted-foreground mb-2 space-y-1">
														<p v-if="c.code_ref">代码: {{ c.code_ref }}</p>
														<p v-if="c.contract_ref">契约: {{ c.contract_ref }}</p>
													</div>
													<div class="flex gap-2">
														<Button
															variant="outline"
															size="sm"
															class="text-xs h-7 px-2"
															@click="onUpdateCommentStatus(c.id, nextStatus(c.status))"
														>
															标记为 {{ statusLabel[nextStatus(c.status)] }}
														</Button>
													</div>
												</div>
											</div>
										</div>
										<div
											v-if="selectedIds.size > 0"
											class="pt-4 border-t border-border"
										>
											<p class="text-xs text-muted-foreground mb-3">
												已选择 {{ selectedIds.size }} 项
											</p>
											<Button
												variant="secondary"
												size="sm"
												class="w-full"
												@click="batchApprove"
											>
												批量批准
											</Button>
										</div>
									</div>
								</template>
							</CardContent>
						</Card>
					</div>
				</TabsContent>

				<TabsContent value="history">
					<Card class="bg-card border border-border rounded-component-md shadow-card overflow-hidden">
						<CardHeader class="pb-3 border-b border-border">
							<div class="flex items-center justify-between flex-wrap gap-4">
								<CardTitle class="text-base font-semibold">
									审查历史记录
								</CardTitle>
								<div class="flex items-center gap-3">
									<div class="flex items-center gap-2">
										<Filter class="h-4 w-4 text-muted-foreground" />
										<select
											v-model="historyFilterType"
											class="h-8 rounded-md border border-border bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
										>
											<option value="all">全部类型</option>
											<option value="requirement_review">需求审查</option>
											<option value="contract_review">契约审查</option>
											<option value="code_review">代码审查</option>
											<option value="final_review">最终审查</option>
										</select>
										<select
											v-model="historyFilterResult"
											class="h-8 rounded-md border border-border bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
										>
											<option value="all">全部结果</option>
											<option value="approved">已通过</option>
											<option value="rejected">已拒绝</option>
										</select>
									</div>
									<Button variant="outline" size="sm" @click="exportHistory">
										<Download class="h-4 w-4" />
										导出
									</Button>
								</div>
							</div>
						</CardHeader>
						<CardContent class="p-0">
							<div class="overflow-x-auto">
								<table class="w-full text-sm">
									<thead class="bg-muted/30">
										<tr>
											<th
												class="text-left font-medium text-muted-foreground px-5 py-3 border-b border-border"
											>
												时间
											</th>
											<th
												class="text-left font-medium text-muted-foreground px-5 py-3 border-b border-border"
											>
												类型
											</th>
											<th
												class="text-left font-medium text-muted-foreground px-5 py-3 border-b border-border"
											>
												标题
											</th>
											<th
												class="text-left font-medium text-muted-foreground px-5 py-3 border-b border-border"
											>
												结果
											</th>
											<th
												class="text-left font-medium text-muted-foreground px-5 py-3 border-b border-border"
											>
												审查人
											</th>
											<th
												class="text-left font-medium text-muted-foreground px-5 py-3 border-b border-border"
											>
												评论
											</th>
										</tr>
									</thead>
									<tbody>
										<tr
											v-for="item in filteredHistory"
											:key="item.request_id"
											class="border-b border-border last:border-b-0 hover:bg-muted/30 transition-colors"
										>
											<td class="px-5 py-3 text-muted-foreground whitespace-nowrap">
												{{ formatFullTime(item.reviewed_at ?? 0) }}
											</td>
											<td class="px-5 py-3">
												<Badge variant="secondary" class="text-xs">
													{{ checkpointConfig[item.checkpoint].icon }}
													{{ item.checkpoint_name }}
												</Badge>
											</td>
											<td class="px-5 py-3 text-foreground max-w-xs truncate">
												{{ item.content_preview }}
											</td>
											<td class="px-5 py-3">
												<Badge
													:class="{
														'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/10':
															item.status === 'approved',
														'bg-rose-500/10 text-rose-500 hover:bg-rose-500/10':
															item.status === 'rejected',
													}"
													class="text-xs border-0"
												>
													{{ item.status === "approved" ? "✅ 通过" : "❌ 拒绝" }}
												</Badge>
											</td>
											<td class="px-5 py-3 text-foreground">
												{{ item.reviewer ?? "—" }}
											</td>
											<td class="px-5 py-3 text-muted-foreground max-w-xs truncate">
												{{ item.comments ?? "—" }}
											</td>
										</tr>
										<tr v-if="filteredHistory.length === 0">
											<td
												colspan="6"
												class="px-5 py-12 text-center text-muted-foreground"
											>
												<History class="h-8 w-8 mx-auto mb-2 opacity-50" />
												<p>暂无审查历史记录</p>
											</td>
										</tr>
									</tbody>
								</table>
							</div>
						</CardContent>
					</Card>
				</TabsContent>
			</Tabs>
		</div>
	</div>
</template>
