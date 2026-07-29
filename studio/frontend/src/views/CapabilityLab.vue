<script setup lang="ts">
import {
	Cpu,
	Download,
	GitMerge,
	Play,
	RefreshCw,
	SearchCode,
	UserCheck,
} from "@lucide/vue";
import { computed, ref } from "vue";
import FaultInjectPanel from "@/components/FaultInjectPanel.vue";
import SimulationResult from "@/components/SimulationResult.vue";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import WaveformChart from "@/components/WaveformChart.vue";
import { MOCK_CODE, SIM_STEPS } from "@/mock/data";
import { getApi } from "@/services/api";
import { genSineInput, lowpassFilter } from "@/services/simulation";
import type {
	FaultParams,
	FaultType,
	SimulationResult as SimulationResultType,
} from "@/types/domain";

const quickLinks = [
	{
		icon: GitMerge,
		title: "组件组合",
		text: "组合两个已验证组件并检查接口兼容性",
		to: "/compose",
	},
	{
		icon: SearchCode,
		title: "规则实验室",
		text: "搜索 C/C++/Python 三种语言的编码标准规则",
		to: "/misra",
	},
	{
		icon: UserCheck,
		title: "HITL 人工审查",
		text: "由审查人批准、驳回或要求修改生成产物",
		to: "/hitl",
	},
	{
		icon: Cpu,
		title: "Hardware-in-the-Loop",
		text: "真实硬件在环接口预留，与人工审查语义分离",
		to: "",
	},
];

const codeContent = ref(MOCK_CODE);
const preconditions = ref("sample_rate > 0\nraw_value <= 65535");
const postconditions = ref(
	"0 <= filtered_value <= 65535\nfiltered_value == round(alpha * raw_value + (1 - alpha) * prev)",
);
const invariants = ref("0.0f <= alpha <= 1.0f");

const isSimulating = ref(false);
const multiCompareEnabled = ref(false);
const activeTab = ref("code");

const currentResult = ref<SimulationResultType | null>(null);
const simulationHistory = ref<SimulationResultType[]>([]);

const baselineWaveform = computed(() => {
	const input = genSineInput(SIM_STEPS);
	const output = lowpassFilter(input, 0.0909);
	return { input, output };
});

function buildContractYaml(): string {
	const preList = preconditions.value
		.split("\n")
		.filter((l) => l.trim())
		.map(
			(expr, i) =>
				`  - id: CON-LAB-PRE-${String(i).padStart(3, "0")}\n    expression: "${expr.trim()}"`,
		)
		.join("\n");
	const postList = postconditions.value
		.split("\n")
		.filter((l) => l.trim())
		.map(
			(expr, i) =>
				`  - id: CON-LAB-POST-${String(i).padStart(3, "0")}\n    expression: "${expr.trim()}"`,
		)
		.join("\n");
	const invList = invariants.value
		.split("\n")
		.filter((l) => l.trim())
		.map(
			(expr, i) =>
				`  - id: CON-LAB-INV-${String(i).padStart(3, "0")}\n    expression: "${expr.trim()}"`,
		)
		.join("\n");
	return `component: LabComponent
description: 仿真实验室自定义组件
inputs:
  raw_value: uint16_t
  sample_rate: uint16_t
outputs:
  filtered_value: uint16_t
preconditions:
${preList}
postconditions:
${postList}
invariants:
${invList}
fault_handling:
  - id: CON-LAB-FLT-000
    expression: "if sample_rate == 0 then return prev_filtered"
`;
}

async function runSimulation(faultType?: FaultType, faultParams?: FaultParams) {
	isSimulating.value = true;
	try {
		const contract = buildContractYaml();
		const result = await getApi().simulate(
			codeContent.value,
			contract,
			faultType,
			faultParams,
		);
		currentResult.value = result;
		if (multiCompareEnabled.value) {
			simulationHistory.value.push(result);
		}
	} finally {
		isSimulating.value = false;
	}
}

function handleStartSimulation() {
	runSimulation();
}

function handleFaultInject(faults: { type: FaultType; params: FaultParams }[]) {
	if (!faults.length) return;
	const first = faults[0];
	runSimulation(first.type, first.params);
}

function handleReset() {
	currentResult.value = null;
	simulationHistory.value = [];
}

function handleExport() {
	if (!currentResult.value) return;
	const data = JSON.stringify(currentResult.value, null, 2);
	const blob = new Blob([data], { type: "application/json" });
	const url = URL.createObjectURL(blob);
	const link = document.createElement("a");
	link.download = `simulation_result_${Date.now()}.json`;
	link.href = url;
	link.click();
	URL.revokeObjectURL(url);
}

const quickStats = computed(() => {
	if (!currentResult.value) return null;
	const s = currentResult.value.statistics;
	const violations = !currentResult.value.passed ? 1 : 0;
	return [
		{ label: "仿真步数", value: s.total_steps, unit: "steps" },
		{
			label: "输出范围",
			value: `${s.output_min} ~ ${s.output_max}`,
			unit: "uint16",
		},
		{ label: "输出均值", value: s.output_mean, unit: "mean" },
		{
			label: "输出方差",
			value: computeVariance(currentResult.value.output_waveform),
			unit: "σ²",
		},
		{ label: "契约违反", value: violations, unit: "次" },
	];
});

function computeVariance(data: number[]): number {
	if (!data.length) return 0;
	const mean = data.reduce((a, b) => a + b, 0) / data.length;
	const variance = data.reduce((a, b) => a + (b - mean) ** 2, 0) / data.length;
	return Math.round(variance * 100) / 100;
}
</script>

<template>
	<main class="min-h-screen bg-background">
		<div class="px-6 py-8 max-w-[1600px] mx-auto">
			<header class="mb-6">
				<span class="text-xs font-bold tracking-widest text-primary">
					SIMULATION LAB
				</span>
				<h1 class="text-2xl font-semibold mt-1">仿真实验室</h1>
				<p class="text-muted-foreground text-sm mt-1">
					数字孪生仿真工作台：代码建模、契约绑定、故障注入、波形分析
				</p>
			</header>

			<section class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
				<router-link
					v-for="link in quickLinks"
					:key="link.title"
					:to="link.to"
					:class="{ 'pointer-events-none opacity-60': !link.to }"
					class="block"
				>
					<Card
						class="h-full hover:border-primary/50 transition-all hover:shadow-card cursor-pointer"
					>
						<CardContent class="p-4">
							<div class="flex items-start gap-3">
								<div
									class="p-2 rounded-lg bg-primary/10 text-primary shrink-0"
								>
									<component :is="link.icon" :size="20" />
								</div>
								<div class="min-w-0">
									<h3 class="text-sm font-semibold">{{ link.title }}</h3>
									<p class="text-xs text-muted-foreground mt-1">
										{{ link.text }}
									</p>
								</div>
							</div>
						</CardContent>
					</Card>
				</router-link>
			</section>

			<Card class="mb-6">
				<CardContent class="p-4 flex flex-wrap items-center justify-between gap-4">
					<div>
						<h2 class="text-lg font-semibold">仿真工作台</h2>
						<p class="text-xs text-muted-foreground mt-0.5">
							配置代码与契约，注入故障，观察波形变化
						</p>
					</div>
					<div class="flex flex-wrap items-center gap-3">
						<div class="flex items-center gap-2">
							<Label for="multi-compare" class="text-xs whitespace-nowrap">
								多轮对比
							</Label>
							<Switch
								id="multi-compare"
								v-model="multiCompareEnabled"
								@change="(e) => (multiCompareEnabled = e.target.checked)"
							/>
						</div>
						<Button variant="outline" size="sm" @click="handleReset">
							<RefreshCw class="w-4 h-4" />
							重置
						</Button>
						<Button variant="outline" size="sm" @click="handleExport" :disabled="!currentResult">
							<Download class="w-4 h-4" />
							导出结果
						</Button>
						<Button size="sm" @click="handleStartSimulation" :disabled="isSimulating">
							<Play class="w-4 h-4" />
							{{ isSimulating ? "仿真中..." : "启动仿真" }}
						</Button>
					</div>
				</CardContent>
			</Card>

			<div class="grid grid-cols-1 xl:grid-cols-5 gap-6">
				<div class="xl:col-span-2 space-y-6">
					<Card>
						<CardHeader class="pb-3">
							<CardTitle class="text-base">配置区</CardTitle>
							<CardDescription class="text-xs">
								代码、契约、故障注入三项配置
							</CardDescription>
						</CardHeader>
						<CardContent class="pt-0">
							<Tabs v-model="activeTab" defaultValue="code">
								<TabsList class="w-full grid grid-cols-3 mb-4">
									<TabsTrigger value="code">代码</TabsTrigger>
									<TabsTrigger value="contract">契约</TabsTrigger>
									<TabsTrigger value="fault">故障注入</TabsTrigger>
								</TabsList>

								<TabsContent value="code" class="mt-0">
									<div class="space-y-3">
										<div>
											<Label class="text-xs mb-2 block">C 语言代码</Label>
											<Textarea
												v-model="codeContent"
												class="font-mono text-xs min-h-[280px] resize-y bg-muted border-border"
												spellcheck="false"
											/>
										</div>
										<div class="flex gap-3">
											<div class="flex-1">
												<Label class="text-xs mb-1.5 block">输入端口</Label>
												<Input value="raw_value: uint16, sample_rate: uint16" readonly class="text-xs font-mono bg-muted" />
											</div>
											<div class="flex-1">
												<Label class="text-xs mb-1.5 block">输出端口</Label>
												<Input value="filtered_value: uint16" readonly class="text-xs font-mono bg-muted" />
											</div>
										</div>
									</div>
								</TabsContent>

								<TabsContent value="contract" class="mt-0">
									<div class="space-y-4">
										<div>
											<Label class="text-xs mb-2 block">前置条件 Preconditions</Label>
											<Textarea
												v-model="preconditions"
												placeholder="每行一个条件表达式"
												class="font-mono text-xs min-h-[80px] resize-y bg-muted border-border"
												spellcheck="false"
											/>
										</div>
										<div>
											<Label class="text-xs mb-2 block">后置条件 Postconditions</Label>
											<Textarea
												v-model="postconditions"
												placeholder="每行一个条件表达式"
												class="font-mono text-xs min-h-[80px] resize-y bg-muted border-border"
												spellcheck="false"
											/>
										</div>
										<div>
											<Label class="text-xs mb-2 block">不变式 Invariants</Label>
											<Textarea
												v-model="invariants"
												placeholder="每行一个不变式"
												class="font-mono text-xs min-h-[60px] resize-y bg-muted border-border"
												spellcheck="false"
											/>
										</div>
									</div>
								</TabsContent>

								<TabsContent value="fault" class="mt-0">
									<FaultInjectPanel @inject="handleFaultInject" />
								</TabsContent>
							</Tabs>
						</CardContent>
					</Card>
				</div>

				<div class="xl:col-span-3 space-y-6">
					<Card>
						<CardHeader class="pb-3">
							<CardTitle class="text-base">波形对比</CardTitle>
							<CardDescription class="text-xs">
								输入/输出波形叠加 · 故障区间高亮 · 支持缩放拖动
							</CardDescription>
						</CardHeader>
						<CardContent class="pt-0">
							<div v-if="currentResult" class="space-y-4">
								<WaveformChart
									:input-data="currentResult.input_waveform"
									:output-data="currentResult.output_waveform"
									:baseline-data="baselineWaveform.output"
									:fault-range="currentResult.fault_range"
									:height="320"
								/>
								<div v-if="!currentResult.passed && currentResult.contract_violation" class="p-3 bg-destructive/10 border border-destructive/30 rounded-component-sm">
									<div class="flex items-center gap-2 text-destructive text-xs font-semibold">
										<span>⚠ 契约违约</span>
										<code class="font-mono">[{{ currentResult.contract_violation.contract_id }}]</code>
									</div>
									<p class="text-xs text-muted-foreground mt-1">
										第 {{ currentResult.contract_violation.timestep }} 步：{{ currentResult.contract_violation.message }}
									</p>
								</div>
							</div>
							<div v-else class="flex items-center justify-center h-[320px] border border-dashed border-border rounded-component-sm bg-muted/30">
								<div class="text-center">
									<div class="text-4xl mb-3">📈</div>
									<p class="text-sm text-muted-foreground">点击"启动仿真"生成波形</p>
								</div>
							</div>
						</CardContent>
					</Card>

					<Card>
						<CardHeader class="pb-3">
							<CardTitle class="text-base">统计信息</CardTitle>
							<CardDescription class="text-xs">
								仿真运行统计与契约验证结果
							</CardDescription>
						</CardHeader>
						<CardContent class="pt-0">
							<div v-if="quickStats" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
								<div
									v-for="stat in quickStats"
									:key="stat.label"
									class="p-3 bg-card border border-border rounded-component-sm"
								>
									<div class="text-[11px] text-muted-foreground uppercase tracking-wide">
										{{ stat.label }}
									</div>
									<div class="text-lg font-semibold mt-1 font-mono">
										{{ stat.value }}
									</div>
									<div class="text-[10px] text-muted-foreground mt-0.5">
										{{ stat.unit }}
									</div>
								</div>
							</div>
							<div v-else class="flex items-center justify-center h-[80px] text-sm text-muted-foreground">
								暂无仿真数据
							</div>
						</CardContent>
					</Card>

					<Card v-if="multiCompareEnabled && simulationHistory.length > 0">
						<CardHeader class="pb-3">
							<CardTitle class="text-base">
								仿真历史对比
								<span class="text-xs font-normal text-muted-foreground ml-2">
									共 {{ simulationHistory.length }} 轮
								</span>
							</CardTitle>
							<CardDescription class="text-xs">
								多轮仿真结果叠加展示，差异高亮
							</CardDescription>
						</CardHeader>
						<CardContent class="pt-0">
							<div class="space-y-3">
								<div
									v-for="(result, idx) in simulationHistory"
									:key="idx"
									class="p-3 border border-border rounded-component-sm"
									:class="result.passed ? 'border-l-4 border-l-success' : 'border-l-4 border-l-destructive'"
								>
									<div class="flex items-center justify-between mb-2">
										<span class="text-xs font-semibold">第 {{ idx + 1 }} 轮</span>
										<span
											class="text-[10px] px-2 py-0.5 rounded-full font-medium"
											:class="result.passed ? 'bg-success/15 text-success' : 'bg-destructive/15 text-destructive'"
										>
											{{ result.passed ? '通过' : '违约' }}
										</span>
									</div>
									<div class="text-[11px] text-muted-foreground space-y-1">
										<div>故障：{{ result.fault_type ?? "无" }}</div>
										<div>步数：{{ result.total_steps }} · 输出范围：{{ result.statistics.output_min }} ~ {{ result.statistics.output_max }}</div>
									</div>
									<WaveformChart
										:input-data="result.input_waveform"
										:output-data="result.output_waveform"
										:fault-range="result.fault_range"
										:height="120"
										class="mt-2"
									/>
								</div>
							</div>
						</CardContent>
					</Card>

					<Card v-if="currentResult">
						<CardHeader class="pb-3">
							<CardTitle class="text-base">仿真详情</CardTitle>
							<CardDescription class="text-xs">
								完整仿真结果与终端日志
							</CardDescription>
						</CardHeader>
						<CardContent class="pt-0">
							<SimulationResult
								:result="currentResult"
								:loading="isSimulating"
								:baseline-waveform="baselineWaveform"
							/>
						</CardContent>
					</Card>
				</div>
			</div>
		</div>
	</main>
</template>

<style scoped>
</style>
