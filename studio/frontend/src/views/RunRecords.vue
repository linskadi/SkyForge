<script setup lang="ts">
import { Clock3, Database, RotateCcw, Trash2, X } from "@lucide/vue";
import { nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import LiveMetrics from "@/components/LiveMetrics.vue";
import { VERIFIED_RECORDINGS } from "@/data/verifiedRecordings";
import { getTaskGateway } from "@/services/taskGateway";
import { useExecutionStore } from "@/stores/executionStore";
import type { TaskSummary } from "@/types/execution";

const router = useRouter();
const route = useRoute();

const execution = useExecutionStore();
const tasks = ref<TaskSummary[]>([]);
const loading = ref(false);
const error = ref("");
const deletingId = ref<string | null>(null);
const confirmDelete = ref<{ task: TaskSummary | null; visible: boolean }>({
	task: null,
	visible: false,
});
/** 当前高亮的录像 ID（来自 ?recording=xxx 查询参数） */
const highlightedRecordingId = ref<string>("");

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
		if (cause instanceof Error && cause.message.includes("404")) {
			error.value = `任务不存在或已被删除（ID: ${task.id}）`;
			hideConfirm();
			setTimeout(() => {
				error.value = "";
				load();
			}, 2000);
		} else {
			error.value = `删除失败：${cause instanceof Error ? cause.message : String(cause)}`;
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

// 点击卡片跳转到回放模式，查看该任务的实际运行状态
function viewDetail(task: TaskSummary) {
	router.push(`/records/${task.id}`);
}

function viewRecording(recordingId: string) {
	router.push(`/records/${recordingId}`);
}

function formatRelativeTime(iso: string | undefined): string {
	if (!iso) return "--";
	const now = Date.now();
	const then = new Date(iso).getTime();
	if (Number.isNaN(then)) return "--";
	const diffMs = now - then;
	if (diffMs < 0) return "刚刚";
	const sec = Math.floor(diffMs / 1000);
	if (sec < 60) return "刚刚";
	const min = Math.floor(sec / 60);
	if (min < 60) return `${min} 分钟前`;
	const hr = Math.floor(min / 60);
	if (hr < 24) return `${hr} 小时前`;
	const day = Math.floor(hr / 24);
	return `${day} 天前`;
}

/**
 * 从 Dashboard 首页"已验证回放"卡片点击进入时，URL 携带 ?recording=xxx。
 * 这里读取该参数，定位到对应录像卡片并滚动到视口中央，同时附加高亮动画。
 */
async function applyRecordingHighlight() {
	const id = route.query.recording;
	if (typeof id !== "string" || !id) return;
	highlightedRecordingId.value = id;
	await nextTick();
	const el = document.querySelector<HTMLElement>(
		`[data-recording-id="${CSS.escape(id)}"]`,
	);
	if (el) {
		el.scrollIntoView({ behavior: "smooth", block: "center" });
		// 4 秒后自动移除高亮，避免长期残留视觉噪点
		setTimeout(() => {
			highlightedRecordingId.value = "";
		}, 4000);
	}
}

onMounted(async () => {
	await load();
	await applyRecordingHighlight();
});
watch(() => execution.profileId, load);
watch(() => route.query.recording, applyRecordingHighlight);
</script>

<template>
  <main class="simple-page">
    <header>
      <div>
        <span>RUN ARCHIVE</span>
        <h1>运行记录</h1>
        <p>任务 ID 与需求编号分离；每次运行保留状态、来源和完整产物。</p>
      </div>
      <button @click="load">
        <RotateCcw :size="15"/>刷新
      </button>
    </header>
    <section class="live-metrics-wrap">
      <LiveMetrics />
    </section>
    <section class="verified-list">
      <h2>已验证离线回放</h2>
      <article
        v-for="recording in VERIFIED_RECORDINGS"
        :key="recording.id"
        :data-recording-id="recording.id"
        class="recording-entry"
        :class="{ highlighted: highlightedRecordingId === recording.id }"
        role="button"
        tabindex="0"
        :aria-label="`打开已验证回放 ${recording.title}`"
        @click="viewRecording(recording.id)"
        @keydown.enter.prevent="viewRecording(recording.id)"
        @keydown.space.prevent="viewRecording(recording.id)"
      >
        <div>
          <span class="badge" :class="recording.profile">{{ recording.profile === 'cloud' ? '云 API' : '本地 Ollama' }}</span>
          <b>{{recording.model}}</b>
        </div>
        <h3>{{recording.title}}</h3>
        <p>{{recording.note}}</p>
        <code>SHA-256 {{recording.sha256}}</code>
        <small class="open-hint">进入工作台回放 →</small>
      </article>
    </section>
    <div v-if="loading" class="empty">正在读取记录…</div>
    <div v-else-if="error" class="error">
      {{ error }}
      <small>演示模式无需后端；真实模式请先完成预检。</small>
    </div>
    <div v-else-if="!tasks.length" class="empty">
      <Database :size="38"/>
      <strong>当前来源尚无运行记录</strong>
      <span>完成一次比赛演示后，浏览器内记录会显示在这里。</span>
    </div>
    <div v-else class="record-list">
      <article
        v-for="item in tasks"
        :key="item.id"
        class="record-card"
        :title="`点击查看详情 · ${item.id}`"
        @click="viewDetail(item)"
      >
        <div class="card-header">
          <div class="card-meta">
            <span class="badge" :class="item.source">
              {{ item.source === 'simulated' ? '模拟' : item.source === 'replay' ? '回放' : '实时' }}
            </span>
            <b class="req-id">{{ item.requirement_id || '需求编号待解析' }}</b>
          </div>
          <button
            class="delete-btn"
            @click.stop="showConfirm(item)"
            :disabled="deletingId === item.id"
            :title="'删除任务 ' + item.id"
          >
            <Trash2 v-if="deletingId !== item.id" :size="14"/>
            <div v-else class="spinner" />
          </button>
        </div>
        <h2>{{ item.requirement }}</h2>
        <footer>
          <code>{{ item.id }}</code>
          <span>
            <Clock3 :size="13"/>
            {{ item.duration_ms ? `${(item.duration_ms/1000).toFixed(1)}s` : item.status }}
            <template v-if="item.created_at"> · {{ formatRelativeTime(item.created_at) }}</template>
          </span>
        </footer>
        <div class="view-detail">查看详情 →</div>
      </article>
    </div>

    <Teleport to="body">
      <div v-if="confirmDelete.visible && confirmDelete.task" class="confirm-overlay" @click="hideConfirm">
        <div class="confirm-dialog" @click.stop>
          <button class="dialog-close" @click="hideConfirm">
            <X :size="16"/>
          </button>
          <div class="dialog-icon">
            <Trash2 :size="32"/>
          </div>
          <h3>确认删除任务</h3>
          <p class="dialog-detail">任务 ID: <code>{{ confirmDelete.task.id }}</code></p>
          <p class="dialog-preview">{{ confirmDelete.task.requirement }}</p>
          <p class="dialog-warning">此操作不可撤销，任务记录将从数据库中永久删除。</p>
          <div class="dialog-actions">
            <button class="btn-cancel" @click="hideConfirm">取消</button>
            <button class="btn-delete" @click="handleDelete(confirmDelete.task!)">
              <Trash2 :size="14"/>
              删除任务
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </main>
</template>

<style scoped>
.simple-page{min-height:calc(100vh - 64px);padding:36px clamp(24px,7vw,100px);color:#153149;background:#f2f6f9}
.simple-page>header{display:flex;justify-content:space-between;align-items:end;max-width:1200px;margin:auto}
.simple-page header span{color:#0879cf;font-size:11px;font-weight:900;letter-spacing:.12em}
.simple-page h1{margin:3px 0;font-size:32px}
.simple-page p{margin:0;color:#657d90}
.simple-page header button{display:flex;align-items:center;gap:6px;padding:9px 13px;border:1px solid #b9cedd;border-radius:7px;background:#fff}

.live-metrics-wrap{max-width:1200px;margin:20px auto 0}

.verified-list{max-width:1200px;margin:24px auto;display:grid;grid-template-columns:1fr 1fr;gap:12px}
.verified-list>h2{grid-column:1/-1;margin:0;font-size:18px}
.verified-list article{padding:15px;border:1px solid #9fcce9;border-radius:10px;background:#fff;transition:box-shadow 0.4s ease, border-color 0.4s ease, transform 0.4s ease}
.verified-list article.recording-entry{cursor:pointer}
.verified-list article.recording-entry:hover{border-color:#1687e8;box-shadow:0 8px 22px rgba(22,135,232,.12);transform:translateY(-1px)}
.verified-list article.missing{border-style:dashed}
.verified-list article.highlighted{border-color:#1687e8;box-shadow:0 0 0 4px rgba(22,135,232,.18), 0 12px 30px rgba(22,135,232,.18);transform:translateY(-2px)}
.verified-list article>div{display:flex;justify-content:space-between}
.verified-list h3{margin:10px 0 5px;font-size:14px}
.verified-list p{font-size:12px}
.verified-list code{display:block;margin-top:9px;color:#60788b;font-size:10px;word-break:break-all}
.open-hint{display:block;margin-top:9px;color:#0879cf;font-size:12px;font-weight:800}

.empty,.error{max-width:1200px;min-height:220px;margin:25px auto;display:grid;place-items:center;align-content:center;gap:8px;border:1px dashed #b9ccda;border-radius:12px;color:#71889a;background:#fff}
.error{color:#a33d3d}
.error small{color:#73899b}

.record-list{max-width:1200px;margin:25px auto;display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.record-card{padding:16px;border:1px solid #cddce6;border-radius:10px;background:#fff;overflow:hidden;cursor:pointer;transition:border-color 0.2s, box-shadow 0.2s}
.record-card:hover{border-color:#9fcce9;box-shadow:0 6px 18px rgba(15,49,75,.12)}

.card-header{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:12px}
.card-meta{display:flex;align-items:center;gap:8px;min-width:0;flex:1}
.req-id{color:#153149;font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

.delete-btn{flex-shrink:0;width:26px;height:26px;display:flex;align-items:center;justify-content:center;border:none;border-radius:6px;background:rgba(239,68,68,0.1);color:#ef4444;opacity:0;transition:opacity 0.2s, background-color 0.2s;cursor:pointer}
.record-card:hover .delete-btn{opacity:1}
.delete-btn:hover{background:rgba(239,68,68,0.2)}
.delete-btn:disabled{cursor:not-allowed;opacity:0.5}

.spinner{width:14px;height:14px;border:2px solid #ef4444;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

.badge{padding:3px 7px;border-radius:99px;background:#dff3e9;color:#16764e;font-size:11px;flex-shrink:0}
.badge.simulated{background:#fff0ca;color:#8c5500}
.badge.replay{background:#e5f3ff;color:#0966a6}
.badge.cloud{background:#e5f3ff;color:#0966a6}
.badge.local{background:#dff3e9;color:#16764e}
.record-card h2{height:44px;margin:0 0 12px;font-size:14px;line-height:1.55;overflow:hidden}
.record-card footer{display:flex;justify-content:space-between;color:#708699;font-size:11px}
.record-card footer span{display:flex;align-items:center;gap:4px}

.view-detail{margin-top:12px;padding-top:10px;border-top:1px solid #edf2f5;color:#0879cf;font-size:12px;font-weight:700;text-align:right;letter-spacing:.02em}
.record-card:hover .view-detail{color:#065a9e}

.confirm-overlay{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.5);z-index:1000}
.confirm-dialog{width:min(420px,90vw);padding:24px;border-radius:14px;background:#fff;box-shadow:0 20px 60px rgba(0,0,0,0.25)}
.dialog-close{position:absolute;top:12px;right:12px;width:28px;height:28px;display:flex;align-items:center;justify-content:center;border:none;border-radius:6px;background:rgba(0,0,0,0.05);color:#6b7280;cursor:pointer}
.dialog-close:hover{background:rgba(0,0,0,0.1)}
.dialog-icon{width:56px;height:56px;margin:0 auto 16px;display:flex;align-items:center;justify-content:center;border-radius:14px;background:rgba(239,68,68,0.1);color:#ef4444}
.confirm-dialog h3{margin:0 0 10px;font-size:18px;color:#1f2937}
.dialog-detail{margin:0 0 8px;color:#6b7280;font-size:14px}
.dialog-detail code{padding:2px 6px;border-radius:4px;background:#f3f4f6;color:#374151;font-size:12px}
.dialog-preview{margin:0 0 12px;padding:10px;border-radius:8px;background:#f9fafb;color:#4b5563;font-size:13px;line-height:1.5;max-height:60px;overflow:hidden}
.dialog-warning{margin:0 0 20px;color:#dc2626;font-size:13px}
.dialog-actions{display:flex;gap:10px;justify-content:flex-end}
.btn-cancel{padding:8px 16px;border:1px solid #d1d5db;border-radius:8px;background:#fff;color:#374151;font-size:14px;cursor:pointer}
.btn-cancel:hover{background:#f9fafb}
.btn-delete{display:flex;align-items:center;gap:6px;padding:8px 16px;border:none;border-radius:8px;background:#ef4444;color:#fff;font-size:14px;cursor:pointer}
.btn-delete:hover{background:#dc2626}
</style>
