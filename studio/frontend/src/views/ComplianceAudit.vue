<script setup lang="ts">
import {
	AlertTriangle,
	CheckCircle,
	CheckCircle2,
	Clock,
	FileText,
	Info,
	Search,
	Shield,
	ShieldCheck,
	XCircle,
	X,
} from "@lucide/vue";
import { computed, ref } from "vue";
import SourceBadge from "@/components/SourceBadge.vue";
import Badge from "@/components/ui/badge/Badge.vue";
import {
	Tabs,
	TabsContent,
	TabsList,
	TabsTrigger,
} from "@/components/ui/tabs";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { MisraRule, RuleStandard } from "@/types/domain";
import {
	MOCK_MISRA_RULES,
	MOCK_MISRA_CPP_RULES,
	MOCK_PYTHON_SAFETY_RULES,
	MOCK_RULE_STANDARDS,
} from "@/mock/data";

const activeTab = ref("misra");

// ==================== 视图 A: MISRA 规则实验室 ====================

const misraQuery = ref("");
const misraResults = ref<MisraRule[]>([]);
const misraSearched = ref(false);
const misraLoading = ref(false);
const misraExpandedRule = ref<string | null>(null);
const misraStandards = ref<RuleStandard[]>(MOCK_RULE_STANDARDS);
const misraCurrentStandardId = ref("misra_c_2012");

interface MisraDisplayConfig {
	placeholder: string;
	emptyHint: string;
	hintTags: string[];
}

const MISRA_DISPLAY_CONFIG: Record<string, MisraDisplayConfig> = {
	misra_c_2012: {
		placeholder: "搜索 MISRA-C 规则 ID、标题或描述...",
		emptyHint: "输入关键词搜索 MISRA-C:2012 规则",
		hintTags: ["Rule 8.1", "初始化", "指针", "Required"],
	},
	jsf_av_cpp: {
		placeholder: "搜索 MISRA-C++ / JSF AV C++ 规则...",
		emptyHint: "输入关键词搜索 C++ 编码标准规则",
		hintTags: ["new/delete", "异常", "RAII", "Mandatory"],
	},
	python_safety: {
		placeholder: "搜索 Python 军工规范规则...",
		emptyHint: "输入关键词搜索 Python 军工软件编程规范",
		hintTags: ["eval", "exec", "global", "强制"],
	},
};

const misraCurrentConfig = computed<MisraDisplayConfig>(() => {
	return (
		MISRA_DISPLAY_CONFIG[misraCurrentStandardId.value] ??
		MISRA_DISPLAY_CONFIG.misra_c_2012
	);
});

const misraCurrentStandardName = computed<string>(() => {
	const std = misraStandards.value.find(
		(s) => s.id === misraCurrentStandardId.value,
	);
	if (std) {
		const langLabel =
			std.language === "c"
				? "C 语言"
				: std.language === "cpp"
					? "C++ 语言"
					: "Python 语言";
		return `${std.name} (${langLabel})`;
	}
	return "MISRA-C:2012 (C 语言)";
});

const misraCategoryVariant = (
	category: string,
): "destructive" | "warning" | "default" | "secondary" => {
	const cat = category.toLowerCase();
	if (cat.includes("mandatory") || cat === "必须" || cat === "强制")
		return "destructive";
	if (cat.includes("required") || cat === "要求") return "warning";
	if (cat.includes("advisory") || cat === "建议") return "default";
	return "secondary";
};

const misraCategoryIcon = (category: string) => {
	const cat = category.toLowerCase();
	if (cat.includes("mandatory") || cat === "必须" || cat === "强制")
		return AlertTriangle;
	if (cat.includes("required") || cat === "要求") return Info;
	if (cat.includes("advisory") || cat === "建议") return CheckCircle;
	return Info;
};

const getMisraRulesPool = (): MisraRule[] => {
	switch (misraCurrentStandardId.value) {
		case "jsf_av_cpp":
			return MOCK_MISRA_CPP_RULES;
		case "python_safety":
			return MOCK_PYTHON_SAFETY_RULES;
		default:
			return MOCK_MISRA_RULES;
	}
};

const onMisraSearch = () => {
	const q = misraQuery.value.trim();
	misraLoading.value = true;
	misraSearched.value = true;
	misraExpandedRule.value = null;
	setTimeout(() => {
		const pool = getMisraRulesPool();
		if (!q) {
			misraResults.value = [...pool];
		} else {
			const lower = q.toLowerCase();
			misraResults.value = pool.filter(
				(r) =>
					r.rule_id.toLowerCase().includes(lower) ||
					r.title.toLowerCase().includes(lower) ||
					r.description.toLowerCase().includes(lower) ||
					(r.section?.toLowerCase().includes(lower) ?? false),
			);
		}
		misraLoading.value = false;
	}, 200);
};

const onMisraSwitchStandard = (standardId: string) => {
	if (standardId === misraCurrentStandardId.value) return;
	misraCurrentStandardId.value = standardId;
	misraQuery.value = "";
	misraResults.value = [];
	misraSearched.value = false;
	misraExpandedRule.value = null;
};

const onMisraHintTag = (tag: string) => {
	misraQuery.value = tag;
	onMisraSearch();
};

const toggleMisraExpand = (ruleId: string) => {
	misraExpandedRule.value =
		misraExpandedRule.value === ruleId ? null : ruleId;
};

const clearMisraSearch = () => {
	misraQuery.value = "";
	misraResults.value = [];
	misraSearched.value = false;
	misraExpandedRule.value = null;
};

// ==================== 视图 B: 契约验证 ====================

interface ContractCheckItemLocal {
	id: string;
	expression: string;
	description?: string;
	passed: boolean;
	failure_reason?: string;
	assert_code: string;
}

interface ContractSectionLocal {
	title: string;
	key: "preconditions" | "postconditions" | "invariants" | "fault_handling";
	items: ContractCheckItemLocal[];
}

const contractSections: ContractSectionLocal[] = [
	{
		title: "前置条件 Preconditions",
		key: "preconditions",
		items: [
			{
				id: "CON-001-PRE-000",
				expression: "sample_rate > 0",
				description: "采样率必须大于 0",
				passed: true,
				assert_code: "assert(sample_rate > 0);",
			},
			{
				id: "CON-001-PRE-001",
				expression: "raw_value <= 65535",
				description: "原始值不超过 uint16 范围",
				passed: true,
				assert_code: "assert(raw_value <= 65535);",
			},
			{
				id: "CON-001-PRE-002",
				expression: "f != NULL",
				description: "滤波器结构体指针非空",
				passed: false,
				failure_reason:
					"反例: f=NULL, 调用 filter_apply(NULL, 1000) 导致空指针解引用",
				assert_code: "assert(f != NULL);",
			},
		],
	},
	{
		title: "后置条件 Postconditions",
		key: "postconditions",
		items: [
			{
				id: "CON-001-POST-000",
				expression: "0 <= filtered_value <= 65535",
				description: "输出值在合法范围内",
				passed: true,
				assert_code:
					"assert(result >= 0 && result <= 65535);",
			},
			{
				id: "CON-001-POST-001",
				expression:
					"filtered_value == round(alpha * raw_value + (1 - alpha) * prev)",
				description: "符合一阶 IIR 滤波公式",
				passed: true,
				assert_code:
					"assert(abs(result - expected) < TOLERANCE);",
			},
		],
	},
	{
		title: "不变式 Invariants",
		key: "invariants",
		items: [
			{
				id: "CON-001-INV-000",
				expression: "0.0f <= alpha <= 1.0f",
				description: "滤波系数 alpha 始终在 [0,1] 范围",
				passed: true,
				assert_code:
					"assert(f->alpha >= 0.0f && f->alpha <= 1.0f);",
			},
		],
	},
	{
		title: "故障处理 Fault Handling",
		key: "fault_handling",
		items: [
			{
				id: "CON-001-FLT-000",
				expression: "if sample_rate == 0 then return prev_filtered",
				description: "采样率异常时保持上一拍输出",
				passed: true,
				assert_code:
					"if (sample_rate == 0) return f->prev_out;",
			},
			{
				id: "CON-001-FLT-001",
				expression: "if raw_value out of range then clamp",
				description: "输入越界时钳位到合法范围",
				passed: false,
				failure_reason:
					"反例: raw_value=70000（超出 uint16 上限时未做输入钳位",
				assert_code:
					"if (raw_value > 65535) raw_value = 65535;",
			},
		],
	},
];

const contractPassed = computed(() =>
	contractSections.reduce(
		(sum, s) =>
			sum + s.items.filter((i) => i.passed).length,
		0,
	),
);
const contractTotal = computed(() =>
	contractSections.reduce((sum, s) => sum + s.items.length, 0),
);
const contractFailed = computed(
	() => contractTotal.value - contractPassed.value,
);
const contractPending = ref(2);

const contractSectionColor = (key: string): string => {
	const map: Record<string, string> = {
		preconditions: "hsl(200, 80%, 50%)",
		postconditions: "hsl(140, 60%, 40%)",
		invariants: "hsl(35, 90%, 50%)",
		fault_handling: "hsl(0, 80%, 55%)",
	};
	return map[key] ?? "hsl(240, 60%, 60%)";
};

// ==================== 视图 C: 形式化验证 ====================

interface FormalCheckItem {
	name: string;
	status: "passed" | "failed" | "timeout";
	duration_ms: number;
	tool: string;
	detail: string;
	counter_example?: string;
}

const formalZ3Checks: FormalCheckItem[] = [
	{
		name: "类型范围约束一致性",
		status: "passed",
		duration_ms: 23,
		tool: "Z3",
		detail: "所有整数类型范围约束一致，无矛盾",
	},
	{
		name: "边界条件检查",
		status: "passed",
		duration_ms: 11,
		tool: "Z3",
		detail: "上下界边界条件全部满足",
	},
	{
		name: "空指针安全性",
		status: "failed",
		duration_ms: 45,
		tool: "Z3",
		detail: "发现空指针解引用风险",
		counter_example: "f=NULL, 调用 filter_apply(NULL, 1000)",
	},
	{
		name: "数组越界检查",
		status: "passed",
		duration_ms: 18,
		tool: "Z3",
		detail: "所有数组访问均在合法范围内",
	},
	{
		name: "算术溢出检查",
		status: "timeout",
		duration_ms: 5000,
		tool: "Z3",
		detail: "超时（建议使用 CBMC 进行有界模型检查）",
	},
];

interface BoundaryTestCase = {
	id: string;
	description: string;
	input: string;
	expected: string;
	status: "passed" | "failed";
};

const boundaryTestCases: BoundaryTestCase[] = [
	{
		id: "BTC-001",
		description: "输入最小值边界",
		input: "raw_value = 0",
		expected: "filtered_value = 0",
		status: "passed",
	},
	{
		id: "BTC-002",
		description: "输入最大值边界",
		input: "raw_value = 65535",
		expected: "filtered_value = 65535",
		status: "passed",
	},
	{
		id: "BTC-003",
		description: "采样率为 0 故障模式",
		input: "sample_rate = 0",
		expected: "保持上一拍输出",
		status: "passed",
	},
	{
		id: "BTC-004",
		description: "Alpha 系数下限边界",
		input: "alpha = 0.0",
		expected: "输出 = 输入",
		status: "passed",
	},
	{
		id: "BTC-005",
		description: "Alpha 系数上限边界",
		input: "alpha = 1.0",
		expected: "输出 = 前值",
		status: "passed",
	},
];

interface CBMCCheckItem {
	name: string;
	status: "passed" | "failed" | "timeout";
	duration_ms: number;
	bound: number;
	detail: string;
}

const cbmcChecks: CBMCCheckItem[] = [
	{
		name: "有界循环展开深度 10",
		status: "passed",
		duration_ms: 120,
		bound: 10,
		detail: "所有路径在展开深度 10 内安全",
	},
	{
		name: "有界循环展开深度 50",
		status: "passed",
		duration_ms: 850,
		bound: 50,
		detail: "所有路径在展开深度 50 内安全",
	},
	{
		name: "整数溢出有界检查",
		status: "failed",
		duration_ms: 2300,
		bound: 100,
		detail: "在第 87 步发现整数溢出",
	},
];

const statusBadgeVariant = (
	status: "passed" | "failed" | "timeout",
): "success" | "destructive" | "warning" | "secondary" => {
	if (status === "passed") return "success";
	if (status === "failed") return "destructive";
	return "warning";
};

const statusText = (status: "passed" | "failed" | "timeout") => {
	if (status === "passed") return "通过";
	if (status === "failed") return "失败";
	return "超时";
};

// ==================== 视图 D: DO-178C 合规 ====================

type CoverageStatus = "covered" | "partial" | "uncovered" | "na";

interface DO178CObjective {
	id: string;
	title: string;
	level: "A" | "B" | "C" | "D" | "E";
	coverage: Record<string, CoverageStatus>;
}

const processAreas = ["规划", "需求", "设计", "编码", "验证"];

const do178cObjectives: DO178CObjective[] = [
	{ id: "OBJ-01", title: "软件计划制定", level: "A", coverage: { 规划: "covered", 需求: "covered", 设计: "covered", 编码: "covered", 验证: "covered" } },
	{ id: "OBJ-02", title: "开发环境建立", level: "A", coverage: { 规划: "covered", 需求: "covered", 设计: "covered", 编码: "covered", 验证: "partial" } },
	{ id: "OBJ-03", title: "软件需求分析", level: "A", coverage: { 规划: "na", 需求: "covered", 设计: "covered", 编码: "covered", 验证: "covered" } },
	{ id: "OBJ-04", title: "软件需求评审", level: "A", coverage: { 规划: "na", 需求: "covered", 设计: "covered", 编码: "partial", 验证: "covered" } },
	{ id: "OBJ-05", title: "软件架构设计", level: "A", coverage: { 规划: "na", 需求: "covered", 设计: "covered", 编码: "covered", 验证: "covered" } },
	{ id: "OBJ-06", title: "软件详细设计", level: "A", coverage: { 规划: "na", 需求: "partial", 设计: "covered", 编码: "covered", 验证: "partial" } },
	{ id: "OBJ-07", title: "软件编码", level: "A", coverage: { 规划: "na", 需求: "na", 设计: "covered", 编码: "covered", 验证: "covered" } },
	{ id: "OBJ-08", title: "代码评审", level: "A", coverage: { 规划: "na", 需求: "na", 设计: "covered", 编码: "covered", 验证: "covered" } },
	{ id: "OBJ-09", title: "单元测试", level: "A", coverage: { 规划: "na", 需求: "na", 设计: "partial", 编码: "covered", 验证: "covered" } },
	{ id: "OBJ-10", title: "集成测试", level: "A", coverage: { 规划: "na", 需求: "partial", 设计: "covered", 编码: "covered", 验证: "covered" } },
	{ id: "OBJ-11", title: "软件配置管理", level: "B", coverage: { 规划: "covered", 需求: "covered", 设计: "covered", 编码: "covered", 验证: "covered" } },
	{ id: "OBJ-12", title: "问题报告与解决", level: "B", coverage: { 规划: "covered", 需求: "covered", 设计: "covered", 编码: "covered", 验证: "covered" } },
	{ id: "OBJ-13", title: "质量保证", level: "B", coverage: { 规划: "covered", 需求: "covered", 设计: "covered", 编码: "partial", 验证: "covered" } },
	{ id: "OBJ-14", title: "验证与确认", level: "B", coverage: { 规划: "covered", 需求: "covered", 设计: "covered", 编码: "partial", 验证: "covered" } },
	{ id: "OBJ-15", title: "需求追溯性分析", level: "C", coverage: { 规划: "na", 需求: "covered", 设计: "covered", 编码: "covered", 验证: "covered" } },
	{ id: "OBJ-16", title: "软件开发标准", level: "C", coverage: { 规划: "covered", 需求: "covered", 设计: "covered", 编码: "covered", 验证: "na" } },
	{ id: "OBJ-17", title: "工具鉴定", level: "C", coverage: { 规划: "partial", 需求: "na", 设计: "na", 编码: "na", 验证: "uncovered" } },
	{ id: "OBJ-18", title: "风险分析", level: "D", coverage: { 规划: "covered", 需求: "covered", 设计: "na", 编码: "na", 验证: "partial" } },
	{ id: "OBJ-19", title: "适航认证支持", level: "E", coverage: { 规划: "uncovered", 需求: "uncovered", 设计: "uncovered", 编码: "uncovered", 验证: "partial" } },
];

const coverageCellClass = (status: CoverageStatus): string => {
	switch (status) {
		case "covered":
			return "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border-emerald-500/30";
		case "partial":
			return "bg-amber-500/20 text-amber-700 dark:text-amber-400 border-amber-500/30";
		case "uncovered":
			return "bg-red-500/20 text-red-700 dark:text-red-400 border-red-500/30";
		case "na":
			return "bg-muted/50 text-muted-foreground border-border";
	}
};

const coverageText = (status: CoverageStatus): string => {
	switch (status) {
		case "covered":
			return "✓";
		case "partial":
			return "◐";
		case "uncovered":
			return "✗";
		case "na":
			return "—";
	}
};

const coverageTitle = (status: CoverageStatus): string => {
	switch (status) {
		case "covered":
			return "已覆盖";
		case "partial":
			return "部分覆盖";
		case "uncovered":
			return "未覆盖";
		case "na":
			return "不适用";
	}
};

const evidenceChainItems = [
	{ from: "REQ-001", to: "CON-001-PRE-000", type: "需求→契约" },
	{ from: "REQ-001", to: "filter_init()", type: "需求→代码" },
	{ from: "CON-001-PRE-000", to: "assert(sample_rate > 0)", type: "契约→断言" },
	{ from: "REQ-002", to: "CON-001-POST-000", type: "需求→契约" },
	{ from: "CON-001-POST-000", to: "TC-003", type: "契约→测试" },
	{ from: "TC-003", to: "BTC-001", type: "测试→边界用例" },
];

const levelBadgeVariant = (
	level: "A" | "B" | "C" | "D" | "E",
): "destructive" | "warning" | "default" | "secondary" | "outline" => {
	switch (level) {
		case "A":
			return "destructive";
		case "B":
			return "warning";
		case "C":
			return "default";
		case "D":
			return "secondary";
		case "E":
			return "outline";
	}
};

const coveredCount = computed(() => {
	let count = 0;
	for (const obj of do178cObjectives) {
		for (const area of processAreas) {
			if (obj.coverage[area] === "covered") count++;
		}
	}
	return count;
});

const partialCount = computed(() => {
	let count = 0;
	for (const obj of do178cObjectives) {
		for (const area of processAreas) {
			if (obj.coverage[area] === "partial") count++;
		}
	}
	return count;
});

const uncoveredCount = computed(() => {
	let count = 0;
	for (const obj of do178cObjectives) {
		for (const area of processAreas) {
			if (obj.coverage[area] === "uncovered") count++;
		}
	}
	return count;
});

const naCount = computed(() => {
	let count = 0;
	for (const obj of do178cObjectives) {
		for (const area of processAreas) {
			if (obj.coverage[area] === "na") count++;
		}
	}
	return count;
});
</script>

<template>
	<div class="compliance-audit-page">
		<header class="page-header">
			<div class="header-content">
				<span class="eyebrow">COMPLIANCE AUDIT CENTER</span>
				<h1 class="title">合规审计中心</h1>
				<p class="description">
					整合 MISRA 规则、契约验证、形式化验证与 DO-178C
					合规四大审计视图，实现航空软件全流程合规追溯
				</p>
			</div>
		</header>

		<Tabs v-model="activeTab" class="tabs-wrapper">
			<TabsList class="tabs-list">
				<TabsTrigger value="misra" class="tab-trigger">
					<Shield :size="16" />
					MISRA 规则实验室
				</TabsTrigger>
				<TabsTrigger value="contract" class="tab-trigger">
					<FileText :size="16" />
					契约验证
				</TabsTrigger>
				<TabsTrigger value="formal" class="tab-trigger">
					<CheckCircle2 :size="16" />
					形式化验证
				</TabsTrigger>
				<TabsTrigger value="do178c" class="tab-trigger">
					<ShieldCheck :size="16" />
					DO-178C 合规
				</TabsTrigger>
			</TabsList>

			<!-- ==================== 视图 A: MISRA 规则实验室 ==================== -->
			<TabsContent value="misra" class="tab-content">
				<div class="misra-view">
					<div class="standards-tabs">
						<button
							v-for="std in misraStandards"
							:key="std.id"
							:class="[
								'standard-tab',
								{ active: std.id === misraCurrentStandardId },
							]"
							@click="onMisraSwitchStandard(std.id)"
						>
							<span class="tab-name">{{ std.name }}</span>
							<span class="tab-lang">
								{{
									std.language === "c"
										? "C"
										: std.language === "cpp"
											? "C++"
											: "Python"
								}}
							</span>
						</button>
					</div>

					<div class="current-standard text-muted-foreground flex items-center gap-2">
						<span>{{ misraCurrentStandardName }}</span>
						<SourceBadge source="observed" label="规则库" />
					</div>

					<div class="search-bar">
						<div class="search-input-wrapper">
							<Search class="search-icon" :size="16" />
							<Input
								v-model="misraQuery"
								class="search-input"
								:placeholder="misraCurrentConfig.placeholder"
								@keydown.enter="onMisraSearch"
							/>
							<button
								v-if="misraQuery"
								class="clear-btn"
								@click="clearMisraSearch"
							>
								<X :size="16" />
							</button>
						</div>
						<Button
							class="search-btn"
							:disabled="!misraQuery.trim() || misraLoading"
							@click="onMisraSearch"
						>
							{{ misraLoading ? "搜索中..." : "搜索" }}
						</Button>
					</div>

					<div
						v-if="!misraSearched"
						class="empty-state"
					>
						<Search
							:size="48"
							class="text-muted-foreground/40"
						/>
						<p class="text-muted-foreground">
							{{ misraCurrentConfig.emptyHint }}
						</p>
						<div class="hint-tags">
							<span
								v-for="tag in misraCurrentConfig.hintTags"
								:key="tag"
								class="hint-tag"
								@click="onMisraHintTag(tag)"
							>
								{{ tag }}
							</span>
						</div>
					</div>

					<div v-else-if="misraLoading" class="empty-state">
						<div class="loading-spinner" />
						<p>正在搜索...</p>
					</div>

					<div
						v-else-if="misraResults.length === 0"
						class="empty-state"
					>
						<Search
							:size="48"
							class="text-muted-foreground/40"
						/>
						<p class="text-muted-foreground">未找到匹配的规则</p>
					</div>

					<div v-else class="results-list">
						<div class="results-count text-muted-foreground">
							找到 {{ misraResults.length }} 条规则
						</div>
						<Card
							v-for="rule in misraResults"
							:key="rule.rule_id"
							class="rule-card"
							@click="toggleMisraExpand(rule.rule_id)"
						>
							<CardContent class="rule-card-content">
								<div class="rule-header">
									<span class="rule-id-badge">
										{{ rule.rule_id }}
									</span>
									<span class="rule-title">{{ rule.title }}</span>
									<Badge
										:variant="misraCategoryVariant(rule.category)"
										class="category-badge"
									>
										<component
											:is="misraCategoryIcon(rule.category)"
											:size="12"
										/>
										{{ rule.category }}
									</Badge>
									<span
										v-if="rule.section"
										class="section-text text-muted-foreground"
									>
										{{ rule.section }}
									</span>
								</div>
								<p class="rule-desc text-muted-foreground">
									{{ rule.description }}
								</p>

								<div
									v-if="misraExpandedRule === rule.rule_id"
									class="rule-detail"
									@click.stop
								>
									<div
										v-if="rule.bad_example"
										class="example-block bad"
									>
										<div class="example-label">违规示例</div>
										<pre class="example-code">
{{ rule.bad_example }}</pre
										>
									</div>
									<div
										v-if="rule.good_example"
										class="example-block good"
									>
										<div class="example-label">合规示例</div>
										<pre class="example-code">
{{ rule.good_example }}</pre
										>
									</div>
								</div>
							</CardContent>
						</Card>
					</div>
				</div>
			</TabsContent>

			<!-- ==================== 视图 B: 契约验证 ==================== -->
			<TabsContent value="contract" class="tab-content">
				<div class="contract-view">
					<div class="flex items-center gap-2 mb-4">
						<span class="text-sm font-semibold">契约验证结果</span>
						<SourceBadge source="observed" label="形式化验证" />
					</div>
					<div class="stats-row">
						<Card class="stat-card pass">
							<CardContent class="stat-content">
								<CheckCircle2 :size="24" class="stat-icon" />
								<div class="stat-info">
									<span class="stat-value">{{ contractPassed }}</span>
									<span class="stat-label">通过</span>
								</div>
							</CardContent>
						</Card>
						<Card class="stat-card pending">
							<CardContent class="stat-content">
								<Clock :size="24" class="stat-icon" />
								<div class="stat-info">
									<span class="stat-value">{{ contractPending }}</span>
									<span class="stat-label">待审</span>
								</div>
							</CardContent>
						</Card>
						<Card class="stat-card fail">
							<CardContent class="stat-content">
								<XCircle :size="24" class="stat-icon" />
								<div class="stat-info">
									<span class="stat-value">{{ contractFailed }}</span>
									<span class="stat-label">失败</span>
								</div>
							</CardContent>
						</Card>
					</div>

					<div class="sections-grid">
						<div
							v-for="section in contractSections"
							:key="section.key"
							class="condition-section"
						>
							<Card class="section-card">
								<CardHeader class="section-header">
									<CardTitle
										class="section-title"
										:style="{ borderLeftColor: contractSectionColor(section.key) }"
									>
										<span>{{ section.title }}</span>
										<Badge variant="secondary" class="section-count">
											{{
												section.items.filter((i) => i.passed)
													.length
											}}/{{ section.items.length }}
										</Badge>
									</CardTitle>
								</CardHeader>
								<CardContent class="section-items">
									<div
										v-for="item in section.items"
										:key="item.id"
										class="check-item"
										:class="{ pass: item.passed, fail: !item.passed }"
									>
										<div class="item-header">
											<component
												:is="item.passed ? CheckCircle2 : XCircle"
												:size="16"
												class="item-icon"
												:class="{ pass: item.passed, fail: !item.passed }"
											/>
											<span class="item-id">{{ item.id }}</span>
											<code class="item-expr">
												{{ item.expression }}
											</code>
											<Badge
												:variant="
													item.passed ? 'success' : 'destructive'
												"
												class="item-status"
											>
												{{ item.passed ? "通过" : "失败" }}
											</Badge>
										</div>
										<div
											v-if="item.description"
											class="item-desc text-muted-foreground"
										>
											{{ item.description }}
										</div>
										<div
											v-if="!item.passed && item.failure_reason"
											class="failure-reason"
										>
											<div class="reason-label">❌ 失败原因：</div>
											<div class="reason-text">
												{{ item.failure_reason }}
											</div>
										</div>
										<div class="assert-code">
											<span class="assert-label">assert:</span>
											<code class="assert-expr">
												{{ item.assert_code }}
											</code>
										</div>
									</div>
								</CardContent>
							</Card>
						</div>
					</div>
				</div>
			</TabsContent>

			<!-- ==================== 视图 C: 形式化验证 ==================== -->
			<TabsContent value="formal" class="tab-content">
				<div class="formal-view">
					<Card class="formal-section">
						<CardHeader>
							<div class="flex items-center justify-between">
								<div>
									<CardTitle class="section-heading flex items-center gap-2">
										<span>Z3 约束一致性检查</span>
										<SourceBadge source="observed" label="SMT求解" />
									</CardTitle>
									<CardDescription>
										基于 SMT 求解器的约束满足性验证
									</CardDescription>
								</div>
							</div>
						</CardHeader>
						<CardContent>
							<table class="data-table">
								<thead>
									<tr>
										<th>检查点</th>
										<th>状态</th>
										<th>工具</th>
										<th>耗时</th>
										<th>详情</th>
									</tr>
								</thead>
								<tbody>
									<tr v-for="check in formalZ3Checks" :key="check.name">
										<td class="cell-name">{{ check.name }}</td>
										<td>
											<Badge
												:variant="statusBadgeVariant(check.status)"
											>
												{{ statusText(check.status) }}
											</Badge>
										</td>
										<td class="cell-tool">{{ check.tool }}</td>
										<td class="cell-duration">
											{{ check.duration_ms }}ms
										</td>
										<td class="cell-detail">
											{{ check.detail }}
											<div
												v-if="check.counter_example"
												class="counter-example"
											>
												反例: {{ check.counter_example }}
											</div>
										</td>
									</tr>
								</tbody>
							</table>
						</CardContent>
					</Card>

					<Card class="formal-section">
						<CardHeader>
							<CardTitle class="section-heading">
								边界测试用例生成
							</CardTitle>
							<CardDescription>
								自动生成的边界条件测试用例
							</CardDescription>
						</CardHeader>
						<CardContent>
							<table class="data-table">
								<thead>
									<tr>
										<th>用例 ID</th>
										<th>描述</th>
										<th>输入</th>
										<th>期望输出</th>
										<th>状态</th>
									</tr>
								</thead>
								<tbody>
									<tr
										v-for="tc in boundaryTestCases"
										:key="tc.id"
									>
										<td class="cell-id">{{ tc.id }}</td>
										<td class="cell-name">{{ tc.description }}</td>
										<td>
											<code class="inline-code">
												{{ tc.input }}
											</code>
										</td>
										<td>
											<code class="inline-code">
												{{ tc.expected }}
											</code>
										</td>
										<td>
											<Badge
												:variant="
													tc.status === 'passed'
														? 'success'
														: 'destructive'
												"
											>
												{{ tc.status === "passed" ? "通过" : "失败" }}
											</Badge>
										</td>
									</tr>
								</tbody>
							</table>
						</CardContent>
					</Card>

					<Card class="formal-section">
						<CardHeader>
							<CardTitle class="section-heading">
								CBMC 有界模型检查
							</CardTitle>
							<CardDescription>
								基于有界模型检查器的路径穷尽验证
							</CardDescription>
						</CardHeader>
						<CardContent>
							<table class="data-table">
								<thead>
									<tr>
										<th>检查项</th>
										<th>状态</th>
										<th>展开深度</th>
										<th>耗时</th>
										<th>详情</th>
									</tr>
								</thead>
								<tbody>
									<tr v-for="check in cbmcChecks" :key="check.name">
										<td class="cell-name">{{ check.name }}</td>
										<td>
											<Badge
												:variant="statusBadgeVariant(check.status)"
											>
												{{ statusText(check.status) }}
											</Badge>
										</td>
										<td>{{ check.bound }}</td>
										<td class="cell-duration">
											{{ check.duration_ms }}ms
										</td>
										<td class="cell-detail">{{ check.detail }}</td>
									</tr>
								</tbody>
							</table>
						</CardContent>
					</Card>
				</div>
			</TabsContent>

			<!-- ==================== 视图 D: DO-178C 合规 ==================== -->
			<TabsContent value="do178c" class="tab-content">
				<div class="do178c-view">
					<div class="do178c-stats">
						<Card class="do-stat">
							<CardContent class="do-stat-content">
								<div class="do-stat-icon covered">✓</div>
								<div>
									<div class="do-stat-value">{{ coveredCount }}</div>
									<div class="do-stat-label text-muted-foreground">已覆盖</div>
								</div>
							</CardContent>
						</Card>
						<Card class="do-stat">
							<CardContent class="do-stat-content">
								<div class="do-stat-icon partial">◐</div>
								<div>
									<div class="do-stat-value">{{ partialCount }}</div>
									<div class="do-stat-label text-muted-foreground">部分覆盖</div>
								</div>
							</CardContent>
						</Card>
						<Card class="do-stat">
							<CardContent class="do-stat-content">
								<div class="do-stat-icon uncovered">✗</div>
								<div>
									<div class="do-stat-value">{{ uncoveredCount }}</div>
									<div class="do-stat-label text-muted-foreground">未覆盖</div>
								</div>
							</CardContent>
						</Card>
						<Card class="do-stat">
							<CardContent class="do-stat-content">
								<div class="do-stat-icon na">—</div>
								<div>
									<div class="do-stat-value">{{ naCount }}</div>
									<div class="do-stat-label text-muted-foreground">不适用</div>
								</div>
							</CardContent>
						</Card>
					</div>

					<Card class="matrix-card">
						<CardHeader>
							<div class="matrix-header">
								<div>
									<CardTitle class="section-heading flex items-center gap-2">
										<span>DO-178C 目标覆盖矩阵</span>
										<SourceBadge source="observed" label="合规评估" />
									</CardTitle>
									<CardDescription>
										19 个软件级目标 × 5 个过程域
									</CardDescription>
								</div>
								<Button>生成合规报告</Button>
							</div>
						</CardHeader>
						<CardContent>
							<div class="matrix-wrapper">
								<table class="coverage-matrix">
									<thead>
										<tr>
											<th class="col-obj">目标</th>
											<th class="col-level">级别</th>
											<th
												v-for="area in processAreas"
												:key="area"
												class="col-area"
											>
												{{ area }}
											</th>
										</tr>
									</thead>
									<tbody>
										<tr
											v-for="obj in do178cObjectives"
											:key="obj.id"
										>
											<td class="col-obj cell-obj">
												<span class="obj-id">{{ obj.id }}</span>
												<span class="obj-title">{{ obj.title }}</span>
											</td>
											<td class="col-level">
												<Badge
													:variant="levelBadgeVariant(obj.level)"
												>
													Level {{ obj.level }}
												</Badge>
											</td>
											<td
												v-for="area in processAreas"
												:key="area"
												class="coverage-cell"
												:class="coverageCellClass(obj.coverage[area])"
												:title="coverageTitle(obj.coverage[area])"
											>
												{{ coverageText(obj.coverage[area]) }}
											</td>
										</tr>
									</tbody>
								</table>
							</div>

							<div class="legend">
								<span class="legend-item">
									<span class="legend-swatch covered"></span>
									已覆盖
								</span>
								<span class="legend-item">
									<span class="legend-swatch partial"></span>
									部分覆盖
								</span>
								<span class="legend-item">
									<span class="legend-swatch uncovered"></span>
									未覆盖
								</span>
								<span class="legend-item">
									<span class="legend-swatch na"></span>
									不适用
								</span>
							</div>
						</CardContent>
					</Card>

					<Card class="evidence-card">
						<CardHeader>
							<CardTitle class="section-heading">证据链追溯</CardTitle>
							<CardDescription>
								需求 → 契约 → 代码 → 测试的双向追溯
							</CardDescription>
						</CardHeader>
						<CardContent>
							<div class="evidence-chain">
								<div
									v-for="(item, idx) in evidenceChainItems"
									:key="idx"
									class="evidence-item"
								>
									<span class="evidence-from">{{ item.from }}</span>
									<span class="evidence-arrow">→</span>
									<span class="evidence-to">{{ item.to }}</span>
									<Badge variant="secondary" class="evidence-type">
										{{ item.type }}
									</Badge>
								</div>
							</div>
						</CardContent>
					</Card>
				</div>
			</TabsContent>
		</Tabs>
	</div>
</template>

<style scoped>
.compliance-audit-page {
	min-height: calc(100vh - 64px);
	padding: 32px clamp(20px, 4vw, 48px);
	display: flex;
	flex-direction: column;
	gap: 24px;
	background: hsl(var(--background));
	color: hsl(var(--foreground));
}

.page-header {
	display: flex;
	flex-direction: column;
	gap: 8px;
}

.eyebrow {
	font-size: 11px;
	font-weight: 900;
	letter-spacing: 0.14em;
	color: hsl(var(--primary));
	text-transform: uppercase;
}

.title {
	font-size: clamp(24px, 3vw, 32px);
	font-weight: 800;
	margin: 0;
	line-height: 1.2;
}

.description {
	font-size: 14px;
	color: hsl(var(--muted-foreground));
	margin: 0;
	line-height: 1.5;
	max-width: 640px;
}

.tabs-wrapper {
	display: flex;
	flex-direction: column;
	gap: 20px;
}

.tabs-list {
	display: flex;
	gap: 4px;
	padding: 4px;
	background: hsl(var(--muted) / 0.5);
	border: 1px solid hsl(var(--border));
	border-radius: 12px;
	width: fit-content;
}

.tab-trigger {
	display: inline-flex;
	align-items: center;
	gap: 8px;
	padding: 10px 18px;
	font-size: 13px;
	font-weight: 600;
	border-radius: 8px;
	color: hsl(var(--muted-foreground));
	cursor: pointer;
	transition: all 0.15s ease;
	border: none;
	background: transparent;
	white-space: nowrap;
}

.tab-trigger:hover {
	color: hsl(var(--foreground));
}

.tab-trigger[data-state="active"] {
	background: hsl(var(--background));
	color: hsl(var(--foreground));
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.tab-content {
	outline: none;
}

/* ==================== MISRA 视图 ==================== */
.misra-view {
	display: flex;
	flex-direction: column;
	gap: 16px;
}

.standards-tabs {
	display: flex;
	gap: 8px;
	flex-wrap: wrap;
}

.standard-tab {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	padding: 8px 16px;
	border: 1px solid hsl(var(--border));
	border-radius: 8px;
	background: hsl(var(--background));
	color: hsl(var(--muted-foreground));
	cursor: pointer;
	font-size: 13px;
	transition: all 0.15s;
}

.standard-tab:hover {
	border-color: hsl(var(--primary));
	color: hsl(var(--primary));
}

.standard-tab.active {
	border-color: hsl(var(--primary));
	background: hsl(var(--primary));
	color: hsl(var(--primary-foreground));
}

.tab-name {
	font-weight: 600;
}

.tab-lang {
	font-size: 11px;
	padding: 1px 6px;
	border-radius: 4px;
	background: hsla(0, 0%, 0%, 0.08);
}

.standard-tab.active .tab-lang {
	background: hsla(0, 0%, 100%, 0.2);
}

.current-standard {
	font-size: 13px;
}

.search-bar {
	display: flex;
	gap: 8px;
}

.search-input-wrapper {
	flex: 1;
	position: relative;
	display: flex;
	align-items: center;
}

.search-icon {
	position: absolute;
	left: 12px;
	color: hsl(var(--muted-foreground));
	pointer-events: none;
	z-index: 1;
}

.search-input {
	padding-left: 36px !important;
	padding-right: 36px !important;
}

.clear-btn {
	position: absolute;
	right: 8px;
	display: flex;
	align-items: center;
	justify-content: center;
	width: 24px;
	height: 24px;
	border: none;
	background: transparent;
	color: hsl(var(--muted-foreground));
	cursor: pointer;
	border-radius: 4px;
}

.clear-btn:hover {
	background: hsl(var(--secondary));
}

.search-btn {
	white-space: nowrap;
}

.empty-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 12px;
	padding: 64px 16px;
	color: hsl(var(--muted-foreground));
	text-align: center;
}

.hint-tags {
	display: flex;
	gap: 8px;
	flex-wrap: wrap;
	justify-content: center;
	margin-top: 8px;
}

.hint-tag {
	padding: 4px 12px;
	border: 1px solid hsl(var(--border));
	border-radius: 16px;
	font-size: 12px;
	cursor: pointer;
	transition: all 0.15s;
	background: hsl(var(--background));
	color: hsl(var(--muted-foreground));
}

.hint-tag:hover {
	border-color: hsl(var(--primary));
	color: hsl(var(--primary));
}

.loading-spinner {
	width: 32px;
	height: 32px;
	border: 3px solid hsl(var(--border));
	border-top-color: hsl(var(--primary));
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.results-count {
	font-size: 13px;
}

.results-list {
	display: flex;
	flex-direction: column;
	gap: 12px;
}

.rule-card {
	cursor: pointer;
	transition: all 0.15s ease;
}

.rule-card:hover {
	border-color: hsl(var(--primary) / 0.5);
	box-shadow: 0 2px 8px hsl(var(--primary) / 0.08);
}

.rule-card-content {
	padding: 16px !important;
}

.rule-header {
	display: flex;
	align-items: center;
	gap: 10px;
	flex-wrap: wrap;
}

.rule-id-badge {
	font-family: "Consolas", monospace;
	font-size: 12px;
	font-weight: 700;
	padding: 3px 8px;
	border-radius: 4px;
	background: hsl(var(--foreground));
	color: hsl(var(--background));
}

.rule-title {
	font-size: 15px;
	font-weight: 600;
	flex: 1;
}

.category-badge {
	display: inline-flex;
	align-items: center;
	gap: 4px;
}

.section-text {
	font-size: 11px;
}

.rule-desc {
	margin: 8px 0 0;
	font-size: 13px;
	line-height: 1.6;
}

.rule-detail {
	margin-top: 12px;
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.example-block {
	border-radius: 6px;
	overflow: hidden;
	border: 1px solid hsl(var(--border));
}

.example-block.bad {
	border-color: hsl(0, 80%, 80%);
	background: hsl(0, 80%, 97%);
}

.example-block.good {
	border-color: hsl(140, 60%, 75%);
	background: hsl(140, 60%, 96%);
}

.example-label {
	font-size: 11px;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: 0.5px;
	padding: 4px 10px;
}

.example-block.bad .example-label {
	color: hsl(0, 70%, 35%);
	background: hsl(0, 80%, 92%);
}

.example-block.good .example-label {
	color: hsl(140, 70%, 30%);
	background: hsl(140, 60%, 90%);
}

.example-code {
	margin: 0;
	padding: 10px 12px;
	font-family: "Consolas", monospace;
	font-size: 12px;
	line-height: 1.5;
	white-space: pre-wrap;
	word-break: break-all;
	color: hsl(var(--foreground));
}

/* ==================== 契约验证视图 ==================== */
.contract-view {
	display: flex;
	flex-direction: column;
	gap: 20px;
}

.stats-row {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	gap: 12px;
}

.stat-card {
	border: 1px solid hsl(var(--border));
}

.stat-card.pass {
	border-left: 3px solid hsl(140, 60%, 45%);
}

.stat-card.pending {
	border-left: 3px solid hsl(35, 90%, 50%);
}

.stat-card.fail {
	border-left: 3px solid hsl(0, 80%, 55%);
}

.stat-content {
	display: flex;
	align-items: center;
	gap: 12px;
	padding: 16px !important;
}

.stat-icon {
	flex-shrink: 0;
}

.stat-card.pass .stat-icon {
	color: hsl(140, 60%, 45%);
}

.stat-card.pending .stat-icon {
	color: hsl(35, 90%, 50%);
}

.stat-card.fail .stat-icon {
	color: hsl(0, 80%, 55%);
}

.stat-info {
	display: flex;
	flex-direction: column;
}

.stat-value {
	font-size: 28px;
	font-weight: 800;
	line-height: 1;
}

.stat-label {
	font-size: 12px;
	color: hsl(var(--muted-foreground));
	margin-top: 4px;
}

.sections-grid {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 12px;
}

@media (max-width: 900px) {
	.sections-grid {
		grid-template-columns: 1fr;
	}
}

.section-card {
	border: 1px solid hsl(var(--border));
}

.section-header {
	padding: 14px 16px !important;
	border-bottom: 1px solid hsl(var(--border));
}

.section-title {
	display: flex;
	align-items: center;
	justify-content: space-between;
	font-size: 14px;
	font-weight: 600;
	padding-left: 10px;
	border-left: 3px solid;
}

.section-count {
	font-size: 11px;
}

.section-items {
	display: flex;
	flex-direction: column;
	gap: 8px;
	padding: 12px 16px !important;
}

.check-item {
	background: hsl(var(--muted) / 0.3);
	border-radius: 6px;
	padding: 10px 12px;
	border-left: 3px solid hsl(140, 60%, 45%);
}

.check-item.fail {
	border-left-color: hsl(0, 80%, 55%);
	background: hsl(0, 80%, 97%);
}

.item-header {
	display: flex;
	align-items: center;
	gap: 8px;
	flex-wrap: wrap;
}

.item-icon {
	flex-shrink: 0;
}

.item-icon.pass {
	color: hsl(140, 60%, 45%);
}

.item-icon.fail {
	color: hsl(0, 80%, 55%);
}

.item-id {
	font-family: "Consolas", monospace;
	font-size: 11px;
	font-weight: 600;
	padding: 2px 6px;
	border-radius: 3px;
	background: hsl(var(--foreground));
	color: hsl(var(--background));
}

.item-expr {
	flex: 1;
	font-size: 12px;
	color: hsl(var(--muted-foreground));
	word-break: break-all;
}

.item-status {
	font-size: 11px;
}

.item-desc {
	font-size: 11px;
	margin-top: 4px;
	padding-left: 24px;
}

.failure-reason {
	margin-top: 6px;
	padding: 6px 8px;
	background: hsl(0, 80%, 92%);
	border-radius: 4px;
	border: 1px solid hsl(0, 80%, 85%);
	margin-left: 24px;
}

.reason-label {
	font-size: 11px;
	font-weight: 600;
	color: hsl(0, 70%, 35%);
	margin-bottom: 2px;
}

.reason-text {
	font-size: 11px;
	color: hsl(0, 70%, 30%);
	line-height: 1.5;
}

.assert-code {
	margin-top: 6px;
	display: flex;
	align-items: flex-start;
	gap: 6px;
	padding: 4px 6px;
	background: hsl(var(--muted));
	border-radius: 4px;
	margin-left: 24px;
}

.assert-label {
	font-size: 10px;
	color: hsl(160, 60%, 40%);
	font-weight: 600;
	flex-shrink: 0;
	padding-top: 1px;
}

.assert-expr {
	flex: 1;
	font-size: 11px;
	color: hsl(var(--foreground));
	word-break: break-all;
	font-family: "Consolas", monospace;
}

/* ==================== 形式化验证视图 ==================== */
.formal-view {
	display: flex;
	flex-direction: column;
	gap: 16px;
}

.formal-section {
	border: 1px solid hsl(var(--border));
}

.section-heading {
	font-size: 16px;
	font-weight: 600;
}

.data-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 13px;
}

.data-table th {
	text-align: left;
	padding: 10px 12px;
	font-weight: 600;
	font-size: 12px;
	color: hsl(var(--muted-foreground));
	border-bottom: 1px solid hsl(var(--border));
	background: hsl(var(--muted) / 0.3);
}

.data-table td {
	padding: 10px 12px;
	border-bottom: 1px solid hsl(var(--border));
	vertical-align: top;
}

.data-table tbody tr:hover {
	background: hsl(var(--muted) / 0.3);
}

.data-table tbody tr:last-child td {
	border-bottom: none;
}

.cell-name {
	font-weight: 500;
}

.cell-tool {
	font-family: "Consolas", monospace;
	font-size: 12px;
}

.cell-duration {
	font-family: "Consolas", monospace;
	font-size: 12px;
	color: hsl(var(--muted-foreground));
}

.cell-detail {
	color: hsl(var(--muted-foreground));
	font-size: 12px;
}

.counter-example {
	margin-top: 4px;
	font-size: 11px;
	color: hsl(0, 70%, 45%);
	font-family: "Consolas", monospace;
}

.cell-id {
	font-family: "Consolas", monospace;
	font-size: 12px;
	font-weight: 600;
}

.inline-code {
	font-family: "Consolas", monospace;
	font-size: 12px;
	padding: 2px 6px;
	background: hsl(var(--muted));
	border-radius: 4px;
}

/* ==================== DO-178C 视图 ==================== */
.do178c-view {
	display: flex;
	flex-direction: column;
	gap: 16px;
}

.do178c-stats {
	display: grid;
	grid-template-columns: repeat(4, 1fr);
	gap: 12px;
}

.do-stat {
	border: 1px solid hsl(var(--border));
}

.do-stat-content {
	display: flex;
	align-items: center;
	gap: 12px;
	padding: 16px !important;
}

.do-stat-icon {
	width: 40px;
	height: 40px;
	display: flex;
	align-items: center;
	justify-content: center;
	border-radius: 8px;
	font-size: 18px;
	font-weight: 700;
	flex-shrink: 0;
}

.do-stat-icon.covered {
	background: hsl(140, 60%, 90%);
	color: hsl(140, 70%, 30%);
}

.do-stat-icon.partial {
	background: hsl(35, 90%, 90%);
	color: hsl(35, 90%, 35%);
}

.do-stat-icon.uncovered {
	background: hsl(0, 80%, 92%);
	color: hsl(0, 70%, 40%);
}

.do-stat-icon.na {
	background: hsl(var(--muted));
	color: hsl(var(--muted-foreground));
}

.do-stat-value {
	font-size: 24px;
	font-weight: 800;
	line-height: 1;
}

.do-stat-label {
	font-size: 12px;
	margin-top: 4px;
}

.matrix-card {
	border: 1px solid hsl(var(--border));
}

.matrix-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 16px;
}

.matrix-wrapper {
	overflow-x: auto;
}

.coverage-matrix {
	width: 100%;
	border-collapse: collapse;
	font-size: 12px;
	min-width: 600px;
}

.coverage-matrix th {
	text-align: left;
	padding: 10px 12px;
	font-weight: 600;
	font-size: 11px;
	color: hsl(var(--muted-foreground));
	border-bottom: 1px solid hsl(var(--border));
	background: hsl(var(--muted) / 0.3);
	white-space: nowrap;
}

.coverage-matrix td {
	padding: 8px 12px;
	border-bottom: 1px solid hsl(var(--border));
	vertical-align: middle;
}

.coverage-matrix tbody tr:hover {
	background: hsl(var(--muted) / 0.3);
}

.col-obj {
	min-width: 200px;
}

.col-level {
	width: 80px;
}

.col-area {
	width: 80px;
	text-align: center !important;
}

.cell-obj {
	display: flex;
	flex-direction: column;
	gap: 2px;
}

.obj-id {
	font-family: "Consolas", monospace;
	font-size: 11px;
	color: hsl(var(--muted-foreground));
	font-weight: 600;
}

.obj-title {
	font-size: 13px;
	font-weight: 500;
}

.coverage-cell {
	text-align: center;
	font-weight: 700;
	border: 1px solid hsl(var(--border));
}

.matrix-legend {
	display: flex;
	gap: 16px;
	margin-top: 12px;
	flex-wrap: wrap;
}

.legend-item {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	font-size: 12px;
	color: hsl(var(--muted-foreground));
}

.legend-swatch {
	width: 16px;
	height: 16px;
	border-radius: 4px;
	border: 1px solid hsl(var(--border));
}

.legend-swatch.covered {
	background: hsl(140, 60%, 50%);
}

.legend-swatch.partial {
	background: hsl(35, 90%, 55%);
}

.legend-swatch.uncovered {
	background: hsl(0, 80%, 55%);
}

.legend-swatch.na {
	background: hsl(var(--muted));
}

.evidence-card {
	border: 1px solid hsl(var(--border));
}

.evidence-chain {
	display: flex;
	flex-direction: column;
	gap: 8px;
}

.evidence-item {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 10px 12px;
	background: hsl(var(--muted) / 0.3);
	border-radius: 6px;
}

.evidence-from {
	font-family: "Consolas", monospace;
	font-size: 12px;
	font-weight: 600;
	padding: 2px 8px;
	background: hsl(var(--background));
	border: 1px solid hsl(var(--border));
	border-radius: 4px;
}

.evidence-arrow {
	color: hsl(var(--muted-foreground));
	font-weight: 600;
}

.evidence-to {
	font-family: "Consolas", monospace;
	font-size: 12px;
	font-weight: 600;
	padding: 2px 8px;
	background: hsl(var(--primary) / 0.1);
	color: hsl(var(--primary));
	border-radius: 4px;
}

.evidence-type {
	margin-left: auto;
	font-size: 11px;
}

@media (max-width: 768px) {
	.stats-row {
		grid-template-columns: 1fr;
	}

	.do178c-stats {
		grid-template-columns: repeat(2, 1fr);
	}

	.tabs-list {
		width: 100%;
		overflow-x: auto;
	}
}
</style>
