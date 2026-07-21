<script setup lang="ts">
/**
 * Generate.vue - 代码生成页面
 *
 * 三阶段面板布局：
 * 阶段 1: 需求输入（文本框 + 语言选择 + 示例按钮）
 * 阶段 2: Agent 执行（实时终端日志 + 进度指示）
 * 阶段 3: 结果面板（8 个 Tab：代码/修复/契约/仿真/验证/报告/追溯/审核）
 */
import {
	ArrowLeft,
	Check,
	Copy,
	Download,
	Loader2,
	Play,
	RotateCcw,
	ShieldCheck,
	UserCheck,
} from "@lucide/vue";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AgentTerminal from "@/components/AgentTerminal.vue";
import CodeViewer from "@/components/CodeViewer.vue";
import ContractCheckResult from "@/components/ContractCheckResult.vue";
import ContractViewer from "@/components/ContractViewer.vue";
import DecisionTrace from "@/components/DecisionTrace.vue";
import FaultInjectPanel from "@/components/FaultInjectPanel.vue";
import FormalVerificationResult from "@/components/FormalVerificationResult.vue";
import RepairTimeline from "@/components/RepairTimeline.vue";
import ReportDownload from "@/components/ReportDownload.vue";
import ReviewConfirm from "@/components/ReviewConfirm.vue";
import SimulationResultView from "@/components/SimulationResult.vue";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast/use-toast";
import { getHITLStatus, getTaskDetail, toggleHITL } from "@/services/api";
import { getApi } from "@/services/apiSwitcher";
import {
	type Contract,
	type ContractCheckResult as ContractCheckResultType,
	type ContractCondition,
	EXAMPLE_REQUIREMENTS,
	type FaultParams,
	type FaultType,
	type GenerateResult,
	type MisraViolation,
	type RepairIteration,
	type SimulationResult,
	type StreamCompletePayload,
} from "@/services/mockApi";
import { useProviderStore } from "@/stores/providerStore";
import type { VerificationResult } from "@/types/verification";

/** 路由实例（用于读取 query 参数，例如从 SCADE 上传跳转回来） */
const route = useRoute();
const router = useRouter();

/** Provider 状态（用于决定 AgentTerminal 数据源：mock 模式显示假数据，local/api 模式连接真实 WebSocket） */
const providerStore = useProviderStore();

/** Toast 提示（用于生成失败等错误通知） */
const { toast } = useToast();

/** AgentTerminal 是否使用 mock 数据源：仅当 LLM mode=mock 时为 true。
 * 兼容页只在用户点击生成后显式启动；编辑需求不会连接或创建任务。 */
const useMockAgentTerminal = computed(
	() => providerStore.derivedMode === "mock",
);

/** 需求文本 */
const requirement = ref<string>("");

/** 目标语言 */
const selectedLanguage = ref<"c" | "cpp" | "python">("c");

/** 状态机：idle / generating / done / error */
const status = ref<"idle" | "generating" | "done" | "error">("idle");

/** 生成结果 */
const result = ref<GenerateResult | null>(null);

/** 错误信息 */
const errorMsg = ref<string>("");

/** 高亮追溯开关（Patch 3） */
const highlightEnabled = ref<boolean>(true);

/** 当前双向追溯激活的 Tag（REQ/CON/TST），null 表示未激活。
 *  由需求区 / 代码区 / 契约区任一 Tag 点击驱动，三区联动高亮。 */
const activeTag = ref<string | null>(null);

/** 当前激活的 tab：result / repair / contract / simulation / verify / report */
const activeTab = ref<
	"result" | "repair" | "contract" | "simulation" | "verify" | "report"
>("result");

/** 聚焦面板：null=三栏均显示，'code'/'contract'/'misra'=聚焦某一个 */
const focusedPanel = ref<"code" | "contract" | "misra" | null>(null);

/** 数字孪生仿真结果（默认用 mockGenerate 返回的，故障注入后更新） */
const simResult = ref<SimulationResult | null>(null);
/** 是否正在执行故障仿真 */
const simulating = ref<boolean>(false);

/** 形式化验证结果（Task 5: Z3 + CBMC 形式化验证） */
const verifyResult = ref<VerificationResult | null>(null);
/** 是否正在执行形式化验证 */
const verifying = ref<boolean>(false);

/** 当前 AgentTerminal 组件引用 */
const terminalRef = ref<InstanceType<typeof AgentTerminal> | null>(null);

/** 是否展开 SCADE 上传面板 */
const scadeExpanded = ref<boolean>(false);

/**
 * HITL 人工审查（Human-in-the-Loop）开关（默认关闭）。
 *
 * 开启后 pipeline 在需求/契约/代码评审检查点暂停等待人工审批
 * （5 分钟超时自动批准）。关闭时 pipeline 直接跑完全流程不阻塞。
 * 仅 local/api 模式有意义；mock 模式下开关不显示。
 *
 * 注意：与 HIL（Hardware-in-the-Loop 硬件在环，digital_twin/）无关。
 */
const hitlEnabled = ref<boolean>(false);
const hitlLoading = ref<boolean>(false);

const onToggleHITL = async () => {
	if (hitlLoading.value) return;
	hitlLoading.value = true;
	const next = !hitlEnabled.value;
	try {
		const actual = await toggleHITL(next);
		hitlEnabled.value = actual;
	} catch (err) {
		console.error("[Generate] 切换 HITL 失败:", err);
		toast({
			title: "HITL 切换失败",
			description: err instanceof Error ? err.message : "请检查后端服务",
			variant: "destructive",
		});
	} finally {
		hitlLoading.value = false;
	}
};

/** 挂载时拉取 HITL 当前状态（仅 local/api 模式） */
const loadHITLStatus = async () => {
	if (providerStore.derivedMode === "mock") return;
	try {
		hitlEnabled.value = await getHITLStatus();
	} catch (err) {
		console.warn("[Generate] 拉取 HITL 状态失败:", err);
	}
};

/** 决策追溯数据 */
interface AgentDecision {
	agent: string;
	prompt: string;
	reasoning: string;
	output: string;
	timestamp: number;
}
const decisions = ref<AgentDecision[]>([]);

/** 是否可点击生成 */
const canGenerate = computed(
	() => requirement.value.trim().length > 0 && status.value !== "generating",
);

/** 点击示例需求 */
const fillExample = (text: string) => {
	requirement.value = text;
};

/** 代码区点击 Tag 徽章：更新激活 Tag（联动需求/契约区） */
const onCodeTagClick = (tag: string | null) => {
	activeTag.value = tag;
};

/** 契约区点击 CON 标签：更新激活 Tag 并跳转到代码面板以展示高亮 */
const onContractTagClick = (tag: string | null) => {
	activeTag.value = tag;
	if (tag) focusedPanel.value = "code";
};

/**
 * AgentTerminal WebSocket 收到 complete 信号时触发。
 *
 * 由 AgentTerminal 在非 mock 模式下通过 `emit("complete", payload)` 调用，
 * payload 携带后端 `level: "complete"` 消息中的 `{ result, degraded }` 字段。
 * 主工作台使用 V1 订阅；本兼容页只消费一次明确启动后的完成事件。
 */
const onTerminalComplete = (payload?: StreamCompletePayload) => {
	// 仅 WS 模式（从最近任务进入 running 任务）：直接用 WS result 渲染结果
	if (isWsOnlyMode.value && payload?.result && status.value === "generating") {
		try {
			const raw = payload.result as Record<string, unknown>;
			const rawContract = raw.contract ?? raw.contract_yaml;
			const contract: Contract =
				typeof rawContract === "string"
					? (() => {
							const lines = rawContract.split("\n");
							const comp =
								lines
									.find((l) => l.startsWith("component:"))
									?.split(":")[1]
									?.trim() ?? "";
							return {
								component: comp,
								description: rawContract,
								inputs: {},
								outputs: {},
								preconditions: [],
								postconditions: [],
								invariants: [],
								fault_handling: [],
							};
						})()
					: ((rawContract as Contract) ?? {
							component: "",
							description: "",
							inputs: {},
							outputs: {},
							preconditions: [],
							postconditions: [],
							invariants: [],
							fault_handling: [],
						});
			const res: GenerateResult = {
				contract,
				code: (raw.code as string) ?? (raw.final_code as string) ?? "",
				violations:
					(raw.violations as MisraViolation[]) ??
					(raw.cppcheck_result as MisraViolation[]) ??
					(raw.final_violations as MisraViolation[]) ??
					[],
				traceability: (raw.traceability as Record<string, number[]>) ?? {},
				repair_history: (raw.repair_history as RepairIteration[]) ?? [],
				contract_check_result:
					(raw.contract_check_result as ContractCheckResultType) ?? {
						component: "",
						sections: [],
						passed_count: 0,
						total_count: 0,
						overall_passed: false,
						generated_assert_code: "",
					},
				simulation_result:
					(raw.simulation_result as SimulationResult) ??
					(raw.simulation as SimulationResult),
				degraded: (raw.degraded as boolean) ?? false,
			};
			result.value = res;
			decisions.value = buildDecisions(res);
			simResult.value = res.simulation_result;
			status.value = "done";
			toast({
				title: "生成完成",
				description: res.degraded ? "部分降级完成" : "全流程完成",
			});
		} catch (err) {
			console.error("[Generate] WS complete 结果解析失败:", err);
			status.value = "error";
			errorMsg.value = "结果解析失败";
		}
	}
};

/** 是否为仅 WS 模式（从最近任务进入正在运行的任务，没有发起 HTTP 请求） */
const isWsOnlyMode = ref(false);

/** 订阅模式：从 Dashboard 点击 running 任务进入时，传入 task_id 让 AgentTerminal
 * 走订阅模式（发送 {task_id, action: "subscribe"} 给 WS），不启动新 pipeline，
 * 只接收已有运行中 task 的实时日志。 */
const subscribeTaskId = ref<string>("");

/** 点击生成按钮（一键全流程：生成 + 修复 + 校验） */
const onGenerate = async () => {
	if (!canGenerate.value) return;

	isWsOnlyMode.value = false;
	subscribeTaskId.value = ""; // 新生成时清空订阅模式
	status.value = "generating";
	result.value = null;
	errorMsg.value = "";
	activeTab.value = "result";
	activeTag.value = null;
	decisions.value = [];

	// 所有模式均只在此处的显式用户动作后启动；输入变化只更新表单。
	// 先清空旧日志，避免上一轮残留。
	terminalRef.value?.clear?.();

	// mock 模式：mockGenerate 的内置延迟已与 mockAgentStream 总时长对齐
	// （见 mockApi.ts 的 MOCK_AGENT_TOTAL_DURATION_MS），无需额外的双通道门控。
	if (providerStore.derivedMode === "mock") {
		// 等待 AgentTerminal 挂载完成后显式启动 mock 流（onMounted 三分支逻辑在 mock 模式下不自动启动）
		await nextTick();
		terminalRef.value?.stop?.();
		terminalRef.value?.start?.();
		try {
			const res = await getApi().generate(
				requirement.value,
				undefined,
				selectedLanguage.value,
			);
			result.value = res;
			decisions.value = buildDecisions(res);
			simResult.value = res.simulation_result;
			status.value = "done";
		} catch (err) {
			console.error("[Generate] 生成失败：", err);
			status.value = "error";
			errorMsg.value =
				err instanceof Error && err.message
					? err.message
					: "生成失败，请检查后端服务是否运行";
			toast({
				title: "生成失败",
				description: errorMsg.value,
				variant: "destructive",
			});
		}
		return;
	}

	// 兼容页只保留一个启动通道：用户点击后显式启动 WebSocket 流。
	// Phase 5：主通道为 V1（POST /api/v1/tasks + WS /api/v1/tasks/{id}/events），
	// AgentTerminal 默认 channelMode="v1"。旧 /ws/agent-stream 通道作为 fallback：
	// V1 通道 5s 内无输出或 POST 失败时，AgentTerminal 自动连接旧通道。
	isWsOnlyMode.value = true;
	await nextTick();
	terminalRef.value?.stop?.();
	terminalRef.value?.start?.();
};

/** 重置 */
const onReset = () => {
	isWsOnlyMode.value = false;
	subscribeTaskId.value = ""; // 重置时清空订阅模式
	status.value = "idle";
	result.value = null;
	errorMsg.value = "";
	activeTab.value = "result";
	activeTag.value = null;
	simResult.value = null;
	simulating.value = false;
	verifyResult.value = null;
	verifying.value = false;
	decisions.value = [];
	terminalRef.value?.stop?.();
	terminalRef.value?.clear?.();
};

/** 审核确认处理 */
const onReviewApprove = (comment: string) => {
	console.log("[Review] 通过审核:", comment);
	// 在实际实现中，这里会调用后端API记录审核结果
};

const onReviewReject = (comment: string) => {
	console.log("[Review] 拒绝:", comment);
	// 在实际实现中，这里会调用后端API记录审核结果
};

/** 故障注入：通过 apiSwitcher 调用 simulate 重新仿真（支持多故障叠加） */
const onInjectFault = async (
	faults: { type: FaultType; params: FaultParams }[],
) => {
	simulating.value = true;
	try {
		const code = result.value?.code ?? "";
		const contractYaml = result.value
			? contractToYaml(result.value.contract)
			: "";
		// 逐个故障依次注入，最后一个的结果作为最终仿真结果
		let res: SimulationResult | undefined;
		for (const f of faults) {
			res = await getApi().simulate(code, contractYaml, f.type, f.params);
		}
		if (res) simResult.value = res;
	} catch (err) {
		console.error("[Generate] 故障仿真失败：", err);
	} finally {
		simulating.value = false;
	}
};

/** 形式化验证：将当前生成的契约 + 代码提交给 Z3/CBMC 验证（Task 5） */
const onVerify = async () => {
	if (!result.value) return;
	verifying.value = true;
	verifyResult.value = null;
	try {
		const contractYaml = contractToYaml(result.value.contract);
		const code = result.value.code ?? "";
		const res = await getApi().verifyContract({
			contract: contractYaml,
			code,
		});
		verifyResult.value = res;
	} catch (err) {
		console.error("[Generate] 形式化验证失败：", err);
		verifyResult.value = {
			status: "skipped",
			summary: { total: 0, passed: 0, failed: 0, skipped: 0 },
			checks: [],
			total_duration_ms: 0,
			tool: "Mock",
			error: err instanceof Error ? err.message : "未知错误",
		};
	} finally {
		verifying.value = false;
	}
};

/** 违规统计 */
const violationStats = computed(() => {
	if (!result.value) return { error: 0, warn: 0, total: 0 };
	const list = result.value.violations;
	return {
		error: list.filter((v) => v.severity === "error").length,
		warn: list.filter((v) => v.severity === "warn").length,
		total: list.length,
	};
});

/** 复制按钮反馈状态 */
const copiedCode = ref<boolean>(false);
const copiedContract = ref<boolean>(false);

/** 将 Contract 对象序列化为 YAML 字符串（无 js-yaml 依赖时手动转换） */
const contractToYaml = (
	contract?: GenerateResult["contract"] | null,
): string => {
	if (!contract) return "";
	const lines: string[] = [];
	lines.push(`component: "${contract.component ?? ""}"`);
	lines.push(`description: "${contract.description ?? ""}"`);
	lines.push("inputs:");
	for (const [k, v] of Object.entries(contract.inputs ?? {})) {
		lines.push(`  ${k}: ${v}`);
	}
	lines.push("outputs:");
	for (const [k, v] of Object.entries(contract.outputs ?? {})) {
		lines.push(`  ${k}: ${v}`);
	}
	const emitSection = (key: string, items?: ContractCondition[] | null) => {
		lines.push(`${key}:`);
		for (const c of items ?? []) {
			lines.push(`  - id: ${c.id}`);
			lines.push(`    expression: "${c.expression}"`);
			if (c.description) lines.push(`    description: "${c.description}"`);
		}
	};
	emitSection("preconditions", contract.preconditions);
	emitSection("postconditions", contract.postconditions);
	emitSection("invariants", contract.invariants);
	emitSection("fault_handling", contract.fault_handling);
	return lines.join("\n");
};

/**
 * 构建决策追溯数据（4 个 Agent 的 prompt/reasoning/output）。
 *
 * 在 mock 模式成功路径、local/api 模式 HTTP 成功路径、local/api 模式 WS result
 * 降级路径中复用，避免 decisions 逻辑重复（SkyForge Spec 修复 A Task 4）。
 *
 * T4.2: reasoning 仅基于 res 中真实可观测的字段（违规数、修复次数、契约字段数等）
 * 构造，不再写死"低通滤波器""Rule 8.4"等编造文本。
 */
const buildDecisions = (res: GenerateResult): AgentDecision[] => {
	const contractFieldCount =
		(res.contract.preconditions?.length ?? 0) +
		(res.contract.postconditions?.length ?? 0) +
		(res.contract.invariants?.length ?? 0) +
		(res.contract.fault_handling?.length ?? 0);
	const codeLineCount = res.code ? res.code.split("\n").length : 0;
	const violationCount = res.violations?.length ?? 0;
	const repairCount = res.repair_history?.length ?? 0;
	return [
		{
			agent: "REQ-Parser",
			prompt: `请解析以下需求：\n${requirement.value}`,
			reasoning: `已解析需求文本，长度 ${requirement.value.length} 字符；输出结构化需求对象。`,
			output: JSON.stringify({ requirement: requirement.value }, null, 2),
			timestamp: Date.now() - 30000,
		},
		{
			agent: "CON-Gen",
			prompt: `基于需求生成DO-178C契约：\n${requirement.value}`,
			reasoning: `生成契约 ${res.contract.component || "(未命名)"}：${contractFieldCount} 个条件子句（前置/后置/不变式/异常处理）。`,
			output: contractToYaml(res.contract),
			timestamp: Date.now() - 20000,
		},
		{
			agent: "CODE-Gen",
			prompt: "依据需求和契约生成MISRA-C代码",
			reasoning: `生成代码共 ${codeLineCount} 行；契约追溯注释按 [REQ-xxx] 标注。`,
			output: res.code,
			timestamp: Date.now() - 10000,
		},
		{
			agent: "REPAIR",
			prompt: `修复MISRA-C违规：${violationCount}条违规`,
			reasoning: `检测到 ${violationCount} 条违规，已完成 ${repairCount} 轮修复迭代。`,
			output: `修复了 ${repairCount} 处违规`,
			timestamp: Date.now(),
		},
	];
};

/** 复制文本到剪贴板（带 2s 按钮反馈） */
const copyToClipboard = async (
	text: string,
	feedback: "code" | "contract",
): Promise<void> => {
	try {
		await navigator.clipboard.writeText(text);
		if (feedback === "code") {
			copiedCode.value = true;
			setTimeout(() => {
				copiedCode.value = false;
			}, 2000);
		} else {
			copiedContract.value = true;
			setTimeout(() => {
				copiedContract.value = false;
			}, 2000);
		}
	} catch (err) {
		console.error("[Generate] 复制失败：", err);
	}
};

/** 下载文本文件工具函数 */
const downloadTextFile = (
	filename: string,
	content: string,
	mime = "text/plain",
) => {
	const blob = new Blob([content], { type: `${mime};charset=utf-8` });
	const url = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = url;
	a.download = filename;
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);
	URL.revokeObjectURL(url);
};

/** 复制 C 代码 */
const onCopyCode = () => {
	if (!result.value) return;
	copyToClipboard(result.value.code, "code");
};

/** 下载 C 代码文件 */
const onDownloadCFile = () => {
	if (!result.value) return;
	const name = (result.value.contract.component || "generated").replace(
		/[^A-Za-z0-9_]/g,
		"_",
	);
	downloadTextFile(`${name}.c`, result.value.code, "text/x-c");
};

// 挂载时检查路由 query，若来自 SCADE 上传则自动填充需求；若带 task_id 则加载对应任务
onMounted(() => {
	const query = route.query;
	if (query.requirement && typeof query.requirement === "string") {
		requirement.value = query.requirement;
	}
	if (query.from === "scade") {
		scadeExpanded.value = false;
	}
	if (query.task_id && typeof query.task_id === "string") {
		void loadTaskFromId(query.task_id);
	}
	void loadHITLStatus();
});

async function loadTaskFromId(taskId: string): Promise<void> {
	try {
		const task = await getTaskDetail(taskId);
		requirement.value = task.requirement;
		if (
			task.language === "c" ||
			task.language === "cpp" ||
			task.language === "python"
		) {
			selectedLanguage.value = task.language;
		}
		if (task.status === "running") {
			isWsOnlyMode.value = true;
			// 关键：先设置 subscribeTaskId，再渲染 AgentTerminal（status=generating 触发渲染）。
			// 这样 AgentTerminal 初始化时 startStream() 走订阅模式，不会触发新 pipeline。
			subscribeTaskId.value = taskId;
			status.value = "generating";
			result.value = null;
			activeTab.value = "result";
			activeTag.value = null;
			decisions.value = [];
			terminalRef.value?.clear?.();
		} else {
			// 已完成任务：跳转到回放页（/records/:taskId），由 CompetitionDemo
			// 在 onMounted 中通过 TaskGateway.getTask 加载历史详情并展示评委摘要。
			// 不再使用已删除的 v1 路由 /task/:task_id。
			router.replace(`/records/${taskId}`);
		}
	} catch (err) {
		console.warn("[Generate] 加载任务失败:", err);
	}
}

// providerStore.derivedMode 切换时重新拉取 HITL 状态
watch(
	() => providerStore.derivedMode,
	() => {
		void loadHITLStatus();
	},
);
</script>
<template>
  <div class="h-full overflow-y-auto">
    <div class="generate-page">

      <!-- ===== 页头 ===== -->
      <header class="page-header">
        <div class="title-area">
          <div class="title-row">
            <button class="back-btn" @click="router.push('/')" title="返回首页">
              <ArrowLeft class="icon" />
            </button>
            <h1>代码生成</h1>
          </div>
          <p>需求解析 → 契约生成 → 代码生成 → 修复 → 仿真 → HITL 人工审查 → 报告</p>
        </div>
      </header>

      <!-- ===== 阶段 1: 需求输入 ===== -->
      <div class="generate-stage">
        <div class="flex items-center gap-2 mb-3">
          <div class="w-6 h-6 rounded-full bg-sky-500/10 flex items-center justify-center text-[11px] font-bold text-sky-500">1</div>
          <h2 class="text-sm font-semibold text-foreground">需求输入</h2>
          <div class="flex-1 h-px bg-border/50 ml-2" />
          <div class="flex items-center gap-2">
            <button
              v-for="lang in (['c', 'cpp', 'python'] as const)"
              :key="lang"
              type="button"
              class="lang-btn"
              :class="{ active: selectedLanguage === lang }"
              @click="selectedLanguage = lang"
            >{{ { c: 'C', cpp: 'C++', python: 'Python' }[lang] }}</button>
          </div>
        </div>

        <textarea
          v-model="requirement"
          class="req-textarea"
          placeholder="例如：实现一个低通滤波器，截止频率 10Hz，用于滤除传感器高频噪声..."
          :disabled="status === 'generating'"
          rows="4"
        />

        <div class="flex items-center justify-between mt-3">
          <div class="flex items-center gap-1.5 flex-wrap">
            <span class="text-[10px] text-muted-foreground mr-1">示例:</span>
            <button
              v-for="(ex, idx) in EXAMPLE_REQUIREMENTS"
              :key="idx"
              type="button"
              class="example-btn"
              :disabled="status === 'generating'"
              @click="fillExample(ex)"
            >{{ ex.length > 24 ? ex.slice(0, 24) + '...' : ex }}</button>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <Button
              v-if="providerStore.derivedMode !== 'mock'"
              size="sm"
              variant="outline"
              :disabled="hitlLoading || status === 'generating'"
              :class="['hitl-toggle-btn', { active: hitlEnabled }]"
              :title="hitlEnabled ? 'HITL 已开启：pipeline 将在评审检查点暂停等待人工审查' : 'HITL 已关闭：pipeline 直接跑完全流程'"
              @click="onToggleHITL"
            >
              <Loader2 v-if="hitlLoading" class="w-3.5 h-3.5 animate-spin" />
              <UserCheck v-else class="w-3.5 h-3.5" />
              HITL {{ hitlEnabled ? '开' : '关' }}
            </Button>
            <Button size="sm" :disabled="!canGenerate" @click="onGenerate" class="generate-btn">
              <Loader2 v-if="status === 'generating'" class="w-3.5 h-3.5 animate-spin" />
              <Play v-else class="w-3.5 h-3.5" />
              {{ status === 'generating' ? '生成中...' : '开始生成' }}
            </Button>
            <Button v-if="status !== 'idle'" size="sm" variant="outline" @click="onReset">
              <RotateCcw class="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </div>

      <!-- ===== 阶段 2: Agent 执行 ===== -->
      <div v-if="status !== 'idle'" class="generate-stage">
        <div class="flex items-center gap-2 mb-3">
          <div class="w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold"
               :class="status === 'generating' ? 'bg-sky-500/10 text-sky-500' : status === 'done' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'">2</div>
          <h2 class="text-sm font-semibold text-foreground">Agent 执行</h2>
          <div class="flex-1 h-px bg-border/50 ml-2" />
          <span v-if="status === 'generating'" class="text-[10px] text-sky-400 flex items-center gap-1">
            <span class="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse" /> 执行中
          </span>
          <span v-else-if="status === 'done'" class="text-[10px] text-emerald-400 flex items-center gap-1">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400" /> 完成
          </span>
          <span v-else-if="status === 'error'" class="text-[10px] text-red-400">失败</span>
        </div>

        <div class="terminal-wrapper rounded-lg border border-border/50 bg-black/20 overflow-hidden">
          <AgentTerminal
            ref="terminalRef"
            :use-mock="useMockAgentTerminal"
            :requirement="requirement"
            :language="selectedLanguage"
            :subscribe-task-id="subscribeTaskId"
            channel-mode="v1"
            @complete="onTerminalComplete"
          />
        </div>
      </div>

      <!-- ===== 阶段 3: 结果面板 ===== -->
      <div v-if="status === 'done' && result" class="generate-stage">
        <div class="flex items-center gap-2 mb-3">
          <div class="w-6 h-6 rounded-full bg-emerald-500/10 flex items-center justify-center text-[11px] font-bold text-emerald-500">3</div>
          <h2 class="text-sm font-semibold text-foreground">生成结果</h2>
          <div class="flex-1 h-px bg-border/50 ml-2" />
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-muted-foreground">{{ result.code.length }} 字符</span>
            <span class="text-[10px] text-muted-foreground">·</span>
            <span class="text-[10px] text-muted-foreground">{{ result.repair_history.length }} 次修复</span>
            <Button size="sm" variant="outline" @click="onDownloadCFile" class="h-7 text-[11px]">
              <Download class="w-3 h-3 mr-1" /> 下载
            </Button>
          </div>
        </div>

        <!-- 降级模式警告横幅 -->
        <div v-if="result.degraded" class="mb-3 rounded-lg border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-xs text-amber-300 flex items-center gap-2">
          <span class="text-amber-400 font-bold">⚠ 降级模式</span>
          <span>LLM 不可用，Agent 已走降级（mock）路径。代码由模板生成，可能不反映真实需求。请检查 LLM 设置。</span>
        </div>

        <Tabs v-model="activeTab" class="result-tabs">
          <TabsList class="tabs-list">
            <TabsTrigger value="result">代码</TabsTrigger>
            <TabsTrigger value="repair">修复 <span class="tab-count">{{ result.repair_history.length }}</span></TabsTrigger>
            <TabsTrigger value="contract">契约 <span class="tab-count" :class="result.contract_check_result.overall_passed ? 'ok' : 'fail'">{{ result.contract_check_result.passed_count }}/{{ result.contract_check_result.total_count }}</span></TabsTrigger>
            <TabsTrigger value="simulation">仿真 <span v-if="simResult" class="tab-count" :class="simResult.passed ? 'ok' : 'fail'">{{ simResult.passed ? '✓' : '✗' }}</span></TabsTrigger>
            <TabsTrigger value="verify">验证</TabsTrigger>
            <TabsTrigger value="report">报告</TabsTrigger>
            <TabsTrigger value="trace">追溯</TabsTrigger>
            <!-- T4.4: 审核按钮为死链（后端无 /api/review/{task_id}），暂时隐藏 -->
            <TabsTrigger v-if="false" value="review">审核</TabsTrigger>
          </TabsList>

          <!-- 代码 Tab -->
          <TabsContent value="result">
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <Card class="lg:col-span-2 result-card">
                <CardHeader class="py-3">
                  <CardTitle class="text-xs font-semibold flex items-center justify-between">
                    <span>代码 <span class="text-muted-foreground font-normal">（含追溯徽章）</span></span>
                    <div class="flex items-center gap-1">
                      <button @click="onCopyCode" class="icon-action" :title="copiedCode ? '已复制' : '复制'">
                        <Check v-if="copiedCode" class="w-3 h-3 text-emerald-500" />
                        <Copy v-else class="w-3 h-3" />
                      </button>
                      <button @click="onDownloadCFile" class="icon-action" title="下载">
                        <Download class="w-3 h-3" />
                      </button>
                    </div>
                  </CardTitle>
                </CardHeader>
                <CardContent class="pt-0">
                  <CodeViewer
                    :code="result.code"
                    :traceability="result.traceability"
                    :highlight-enabled="highlightEnabled"
                    :active-tag="activeTag"
                    @tag-click="onCodeTagClick"
                  />
                </CardContent>
              </Card>

              <div class="space-y-4">
                <Card class="result-card">
                  <CardHeader class="py-3">
                    <CardTitle class="text-xs font-semibold">契约</CardTitle>
                  </CardHeader>
                  <CardContent class="pt-0">
                    <ContractViewer
                      :contract="result.contract"
                      :active-tag="activeTag"
                      @tag-click="onContractTagClick"
                    />
                  </CardContent>
                </Card>

                <Card class="result-card">
                  <CardHeader class="py-3">
                    <CardTitle class="text-xs font-semibold flex items-center justify-between">
                      <span>MISRA 校验</span>
                      <span class="text-[10px] font-normal">
                        <span class="text-red-400">Err {{ violationStats.error }}</span>
                        <span class="text-muted-foreground mx-1">·</span>
                        <span class="text-amber-400">Warn {{ violationStats.warn }}</span>
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent class="pt-0 max-h-[300px] overflow-y-auto">
                    <div v-if="result.violations.length > 0" class="space-y-1.5">
                      <div v-for="(v, idx) in result.violations" :key="idx"
                           class="p-2 rounded-md text-[11px] border"
                           :class="v.severity === 'error' ? 'bg-red-950/30 border-red-900/50' : 'bg-amber-950/30 border-amber-900/50'">
                        <div class="flex items-center gap-1.5 mb-0.5">
                          <span class="font-mono font-medium" :class="v.severity === 'error' ? 'text-red-400' : 'text-amber-400'">{{ v.rule }}</span>
                          <span class="text-muted-foreground">@L{{ v.line }}</span>
                        </div>
                        <div class="text-muted-foreground">{{ v.message }}</div>
                      </div>
                    </div>
                    <div v-else class="text-[11px] text-emerald-400 text-center py-4">无 MISRA 违规</div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          <!-- 修复 Tab -->
          <TabsContent value="repair">
            <Card class="result-card">
              <CardContent class="pt-4">
                <RepairTimeline :history="result.repair_history" />
              </CardContent>
            </Card>
          </TabsContent>

          <!-- 契约校验 Tab -->
          <TabsContent value="contract">
            <Card class="result-card">
              <CardContent class="pt-4">
                <ContractCheckResult :result="result.contract_check_result" />
              </CardContent>
            </Card>
          </TabsContent>

          <!-- 仿真 Tab -->
          <TabsContent value="simulation">
            <div class="space-y-4">
              <FaultInjectPanel @inject="onInjectFault" />
              <Card class="result-card">
                <CardContent class="pt-4">
                  <SimulationResultView v-if="simResult" :result="simResult" :loading="simulating" />
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <!-- 验证 Tab -->
          <TabsContent value="verify">
            <div class="space-y-4">
              <Card class="result-card">
                <CardContent class="pt-4">
                  <div class="flex items-center gap-3">
                    <Button :disabled="verifying" @click="onVerify" size="sm">
                      <Loader2 v-if="verifying" class="w-3.5 h-3.5 animate-spin" />
                      <ShieldCheck v-else class="w-3.5 h-3.5" />
                      {{ verifyResult ? '重新验证' : '开始验证' }}
                    </Button>
                    <span class="text-[10px] text-muted-foreground">Z3 SMT + CBMC 有界模型检查</span>
                  </div>
                </CardContent>
              </Card>
              <FormalVerificationResult :result="verifyResult" :loading="verifying" @start-verify="onVerify" />
            </div>
          </TabsContent>

          <!-- 报告 Tab -->
          <TabsContent value="report">
            <ReportDownload :result="result" />
          </TabsContent>

          <!-- 追溯 Tab -->
          <TabsContent value="trace">
            <DecisionTrace :decisions="decisions" />
          </TabsContent>

          <!-- 审核 Tab -->
          <!-- T4.4: 审核按钮为死链（后端无 /api/review/{task_id}），暂时隐藏整个 Tab 内容 -->
          <TabsContent v-if="false" value="review">
            <div class="space-y-3">
              <ReviewConfirm stage="代码生成审核" :content="`AI已生成${result?.code?.length || 0}字符的C代码，请审核`" @approve="onReviewApprove" @reject="onReviewReject" />
              <ReviewConfirm stage="MISRA-C修复审核" :content="`已修复${result?.repair_history?.length || 0}处违规`" @approve="onReviewApprove" @reject="onReviewReject" />
              <ReviewConfirm stage="DO-178C报告审核" content="AI已生成DO-178C合规报告，请审核" @approve="onReviewApprove" @reject="onReviewReject" />
            </div>
          </TabsContent>
        </Tabs>
      </div>

      <!-- 错误提示 -->
      <div v-if="status === 'error'" class="rounded-lg border border-red-900/50 bg-red-950/30 p-4 text-sm text-red-400">
        <div class="flex items-center justify-between gap-3">
          <span>{{ errorMsg }}</span>
          <Button size="sm" variant="outline" :disabled="!canGenerate" @click="onGenerate" class="shrink-0 border-red-900/50 text-red-400 hover:bg-red-950/50 hover:text-red-300">
            <RotateCcw class="w-3.5 h-3.5 mr-1" /> 重试
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
<style src="@/assets/styles/generate.css"></style>
