<script setup lang="ts">
import { Clock3, Database, RotateCcw, Search, Trash2, X } from "@lucide/vue";
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import LiveMetrics from "@/components/LiveMetrics.vue";
import SourceBadge from "@/components/SourceBadge.vue";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { getTaskGateway } from "@/services/taskGateway";
import { useExecutionStore } from "@/stores/executionStore";
import type { TaskSummary } from "@/types/execution";

const router = useRouter();
const { t } = useI18n();

const execution = useExecutionStore();
const tasks = ref<TaskSummary[]>([]);
const loading = ref(false);
const error = ref("");
const deletingId = ref<string | null>(null);
const confirmDelete = ref<{ task: TaskSummary | null; visible: boolean }>({
	task: null,
	visible: false,
});

const searchQuery = ref("");
const statusFilter = ref("all");
const languageFilter = ref("all");

const filteredTasks = computed(() => {
	return tasks.value.filter((task) => {
		const matchesSearch =
			!searchQuery.value ||
			task.requirement?.toLowerCase().includes(searchQuery.value.toLowerCase());

		const matchesStatus =
			statusFilter.value === "all" ||
			(task.status && task.status.toLowerCase() === statusFilter.value);

		const matchesLanguage =
			languageFilter.value === "all" ||
			(task.language && task.language.toLowerCase() === languageFilter.value);

		return matchesSearch && matchesStatus && matchesLanguage;
	});
});

function getStatusVariant(
	status: string,
): "default" | "secondary" | "destructive" | "outline" {
	const s = status?.toLowerCase() || "";
	if (s.includes("running") || s.includes("progress")) return "default";
	if (s.includes("complete") || s.includes("success")) return "secondary";
	if (s.includes("fail") || s.includes("error")) return "destructive";
	return "outline";
}

function getStatusLabel(status: string): string {
	const s = status?.toLowerCase() || "";
	if (s.includes("running") || s.includes("progress"))
		return t("records.status.running");
	if (s.includes("complete") || s.includes("success"))
		return t("records.status.completed");
	if (s.includes("fail") || s.includes("error"))
		return t("records.status.failed");
	return status || t("records.status.unknown");
}

function getLanguageLabel(lang: string): string {
	if (!lang) return "--";
	const l = lang.toLowerCase();
	if (l === "c") return "C";
	if (l === "cpp" || l === "c++") return "C++";
	if (l === "python" || l === "py") return "Python";
	return lang;
}

function getSourceLabel(source: string): string {
	if (source === "simulated") return t("records.source.simulated");
	if (source === "replay") return t("records.source.replay");
	if (source === "live") return t("records.source.live");
	return source || "--";
}

function getSourceType(
	source: string,
): "observed" | "simulated" | "unavailable" | "failed" {
	if (source === "simulated") return "simulated";
	if (source === "live" || source === "replay") return "observed";
	if (source === "failed") return "failed";
	return "unavailable";
}

async function load() {
	loading.value = true;
	error.value = "";
	try {
		tasks.value = await getTaskGateway(execution.profileId).listTasks();
	} catch (cause) {
		error.value = cause instanceof Error ? cause.message : String(cause);
	} finally {
		loading.value = false;
	}
}

async function handleDelete(task: TaskSummary) {
	if (deletingId.value) return;
	deletingId.value = task.id;
	try {
		await getTaskGateway(execution.profileId).deleteTask(task.id);
		await load();
		hideConfirm();
	} catch (cause) {
		const msg = cause instanceof Error ? cause.message : String(cause);
		if (msg.includes("404")) {
			error.value = t("records.error.notFound", { id: task.id });
			hideConfirm();
			setTimeout(() => {
				error.value = "";
				load();
			}, 2000);
		} else if (msg.includes("401") || /unauthor|未授权/i.test(msg)) {
			error.value = t("records.error.unauthorized");
		} else {
			error.value = t("records.error.deleteFailed", {
				msg,
			});
		}
	} finally {
		deletingId.value = null;
	}
}

function showConfirm(task: TaskSummary) {
	confirmDelete.value = { task, visible: true };
}

function hideConfirm() {
	confirmDelete.value = { task: null, visible: false };
}

function viewDetail(task: TaskSummary) {
	router.push(`/records/${task.id}`);
}

function formatRelativeTime(iso: string | undefined): string {
	if (!iso) return "--";
	const now = Date.now();
	const then = new Date(iso).getTime();
	if (Number.isNaN(then)) return "--";
	const diffMs = now - then;
	if (diffMs < 0) return t("records.time.justNow");
	const sec = Math.floor(diffMs / 1000);
	if (sec < 60) return t("records.time.justNow");
	const min = Math.floor(sec / 60);
	if (min < 60) return t("records.time.minutesAgo", { n: min });
	const hr = Math.floor(min / 60);
	if (hr < 24) return t("records.time.hoursAgo", { n: hr });
	const day = Math.floor(hr / 24);
	return t("records.time.daysAgo", { n: day });
}

onMounted(async () => {
	await load();
});
watch(() => execution.profileId, load);
</script>

<template>
  <main class="min-h-[calc(100vh-64px)] bg-background px-6 py-9 md:px-[7vw] lg:px-[100px]">
    <div class="mx-auto max-w-6xl">
      <header class="mb-6 flex items-end justify-between">
        <div>
          <p class="text-xs font-bold uppercase tracking-[0.12em] text-primary">TASK CENTER</p>
          <h1 class="mt-1 text-2xl font-bold text-foreground">{{ $t("records.title") }}</h1>
          <p class="mt-1 text-sm text-muted-foreground">{{ $t("records.subtitle") }}</p>
        </div>
        <Button variant="outline" size="sm" @click="load">
          <RotateCcw :size="15" />
          {{ $t("records.btn.refresh") }}
        </Button>
      </header>

      <section class="mb-6">
        <LiveMetrics />
      </section>

      <section v-if="loading" class="flex min-h-[220px] items-center justify-center rounded-component-md border border-dashed border-border bg-card">
        <span class="text-muted-foreground">{{ $t("records.loading") }}</span>
      </section>

      <section v-else-if="error" class="flex min-h-[220px] flex-col items-center justify-center gap-2 rounded-component-md border border-dashed border-border bg-card p-6">
        <p class="text-destructive">{{ error }}</p>
        <p class="text-xs text-muted-foreground">{{ $t("records.error.hint") }}</p>
      </section>

      <section v-else-if="!tasks.length" class="flex min-h-[220px] flex-col items-center justify-center gap-2 rounded-component-md border border-dashed border-border bg-card p-6">
        <Database :size="38" class="text-muted-foreground" />
        <strong class="text-foreground">{{ $t("records.empty.title") }}</strong>
        <span class="text-sm text-muted-foreground">{{ $t("records.empty.desc") }}</span>
      </section>

      <section v-else>
        <div class="mb-4 flex flex-col gap-3 rounded-component-md border border-border bg-card p-4 sm:flex-row sm:items-center">
          <div class="relative flex-1">
            <Search :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              v-model="searchQuery"
              type="text"
              :placeholder="$t('records.placeholder.search')"
              class="pl-9"
            />
          </div>
          <Select v-model="statusFilter" default-value="all">
            <SelectTrigger class="w-full sm:w-[140px]">
              <SelectValue :placeholder="$t('records.filter.statusPlaceholder')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{{ $t("records.filter.statusAll") }}</SelectItem>
              <SelectItem value="running">{{ $t("records.status.running") }}</SelectItem>
              <SelectItem value="completed">{{ $t("records.status.completed") }}</SelectItem>
              <SelectItem value="failed">{{ $t("records.status.failed") }}</SelectItem>
            </SelectContent>
          </Select>
          <Select v-model="languageFilter" default-value="all">
            <SelectTrigger class="w-full sm:w-[140px]">
              <SelectValue :placeholder="$t('records.filter.languagePlaceholder')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{{ $t("records.filter.languageAll") }}</SelectItem>
              <SelectItem value="c">C</SelectItem>
              <SelectItem value="cpp">C++</SelectItem>
              <SelectItem value="python">Python</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div v-if="!filteredTasks.length" class="flex min-h-[160px] items-center justify-center rounded-component-md border border-dashed border-border bg-card">
          <span class="text-muted-foreground">{{ $t("records.empty.noMatch") }}</span>
        </div>

        <div v-else class="overflow-hidden rounded-component-md border border-border bg-card">
          <article
            v-for="item in filteredTasks"
            :key="item.id"
            class="group flex flex-col gap-3 border-b border-border p-4 transition-colors duration-150 last:border-b-0 md:flex-row md:items-center md:gap-4"
            :class="{ 'hover:bg-muted/50': true }"
          >
            <div class="flex min-w-0 flex-1 flex-col gap-1">
              <div class="flex items-center gap-2">
                <span class="text-[11px] text-muted-foreground">{{
                  item.requirement_id || $t('records.requirementIdPending')
                }}</span>
              </div>
              <p
                class="line-clamp-2 cursor-pointer text-sm font-medium text-foreground"
                :title="item.requirement"
                @click="viewDetail(item)"
              >
                {{ item.requirement || $t('records.noRequirement') }}
              </p>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <Badge variant="outline" class="text-[11px]">
                {{ getLanguageLabel(item.language || '') }}
              </Badge>
              <Badge :variant="getStatusVariant(item.status)" class="text-[11px]">
                {{ getStatusLabel(item.status) }}
              </Badge>
              <Badge variant="outline" class="text-[11px]">
                {{ $t('records.violations', { n: item.progress !== undefined ? item.progress : 0 }) }}
              </Badge>
              <span class="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                <Clock3 :size="12" />
                {{ item.duration_ms ? `${(item.duration_ms / 1000).toFixed(1)}s` : '--' }}
              </span>
              <span class="text-[11px] text-muted-foreground">
                {{ formatRelativeTime(item.created_at) }}
              </span>
              <SourceBadge :source="getSourceType(item.source || '')" :label="getSourceLabel(item.source || '')" />
            </div>

            <div class="flex items-center gap-2 md:ml-2">
              <Button variant="ghost" size="sm" @click="viewDetail(item)">
                {{ $t("records.btn.viewDetail") }}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                class="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                @click="showConfirm(item)"
                :disabled="deletingId === item.id"
                :title="$t('records.btn.deleteTaskTitle', { id: item.id })"
              >
                <Trash2 v-if="deletingId !== item.id" :size="15" />
                <div v-else class="h-4 w-4 animate-spin rounded-full border-2 border-destructive border-t-transparent" />
              </Button>
            </div>
          </article>
        </div>
      </section>
    </div>

    <Teleport to="body">
      <div
        v-if="confirmDelete.visible && confirmDelete.task"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        @click="hideConfirm"
      >
        <div
          class="w-full max-w-md rounded-component-md border border-border bg-card p-6 shadow-overlay animate-scale-in"
          @click.stop
        >
          <div class="mb-4 flex items-start justify-between">
            <div class="flex h-14 w-14 items-center justify-center rounded-component-md bg-destructive/10">
              <Trash2 :size="28" class="text-destructive" />
            </div>
            <Button variant="ghost" size="icon" class="h-7 w-7" @click="hideConfirm">
              <X :size="16" />
            </Button>
          </div>
          <h3 class="mb-2 text-lg font-semibold text-foreground">{{ $t("records.confirm.title") }}</h3>
          <p class="mb-2 text-sm text-muted-foreground">
            {{ $t("records.confirm.taskId") }} <code class="rounded bg-muted px-1.5 py-0.5 text-xs text-foreground">{{ confirmDelete.task.id }}</code>
          </p>
          <p class="mb-4 rounded-md bg-muted p-2.5 text-sm text-foreground line-clamp-3">
            {{ confirmDelete.task.requirement }}
          </p>
          <p class="mb-5 text-sm text-destructive">{{ $t("records.confirm.irreversible") }}</p>
          <div class="flex justify-end gap-2">
            <Button variant="outline" size="sm" @click="hideConfirm">{{ $t("confirm.cancel") }}</Button>
            <Button variant="destructive" size="sm" @click="handleDelete(confirmDelete.task!)">
              <Trash2 :size="14" />
              {{ $t("records.btn.delete") }}
            </Button>
          </div>
        </div>
      </div>
    </Teleport>
  </main>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
