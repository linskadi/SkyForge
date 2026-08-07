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
import { getApi } from "@/services/apiSwitcher";
import { genSineInput, lowpassFilter } from "@/services/simulation";
import type {
	FaultParams,
	FaultType,
	SimulationResult as SimulationResultType,
} from "@/types/domain";

const quickLinks = [
	{
		icon: GitMerge,
		labelKey: "lab.quickLinks.composeTitle",
		textKey: "lab.quickLinks.composeText",
		to: "/compose",
	},
	{
		icon: SearchCode,
		labelKey: "lab.quickLinks.misraTitle",
		textKey: "lab.quickLinks.misraText",
		to: "/misra",
	},
	{
		icon: UserCheck,
		labelKey: "lab.quickLinks.hitlTitle",
		textKey: "lab.quickLinks.hitlText",
		to: "/hitl",
	},
	{
		icon: Cpu,
		labelKey: "lab.quickLinks.hilTitle",
		textKey: "lab.quickLinks.hilText",
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
		{
			labelKey: "lab.stats.labelSteps",
			value: s.total_steps,
			unitKey: "lab.stats.unitSteps",
		},
		{
			labelKey: "lab.stats.labelRange",
			value: `${s.output_min} ~ ${s.output_max}`,
			unitKey: "lab.stats.unitRange",
		},
		{
			labelKey: "lab.stats.labelMean",
			value: s.output_mean,
			unitKey: "lab.stats.unitMean",
		},
		{
			labelKey: "lab.stats.labelVariance",
			value: computeVariance(currentResult.value.output_waveform),
			unitKey: "lab.stats.unitVariance",
		},
		{
			labelKey: "lab.stats.labelViolations",
			value: violations,
			unitKey: "lab.stats.unitViolations",
		},
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
					{{ $t("lab.eyebrow") }}
				</span>
				<h1 class="text-2xl font-semibold mt-1">{{ $t("lab.title") }}</h1>
				<p class="text-muted-foreground text-sm mt-1">
					{{ $t("lab.subtitle") }}
				</p>
			</header>

			<section class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
				<router-link
					v-for="link in quickLinks"
					:key="link.labelKey"
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
									<h3 class="text-sm font-semibold">{{ $t(link.labelKey) }}</h3>
									<p class="text-xs text-muted-foreground mt-1">
										{{ $t(link.textKey) }}
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
						<h2 class="text-lg font-semibold">{{ $t("lab.workspace.title") }}</h2>
						<p class="text-xs text-muted-foreground mt-0.5">
							{{ $t("lab.workspace.desc") }}
						</p>
					</div>
					<div class="flex flex-wrap items-center gap-3">
						<div class="flex items-center gap-2">
							<Label for="multi-compare" class="text-xs whitespace-nowrap">
								{{ $t("lab.multiCompare") }}
							</Label>
							<Switch
								id="multi-compare"
								v-model="multiCompareEnabled"
							/>
						</div>
						<Button variant="outline" size="sm" @click="handleReset">
							<RefreshCw class="w-4 h-4" />
							{{ $t("lab.btn.reset") }}
						</Button>
						<Button variant="outline" size="sm" @click="handleExport" :disabled="!currentResult">
							<Download class="w-4 h-4" />
							{{ $t("lab.btn.export") }}
						</Button>
						<Button size="sm" @click="handleStartSimulation" :disabled="isSimulating">
							<Play class="w-4 h-4" />
							{{ isSimulating ? $t("lab.btn.simulating") : $t("lab.btn.start") }}
						</Button>
					</div>
				</CardContent>
			</Card>

			<div class="grid grid-cols-1 xl:grid-cols-5 gap-6">
				<div class="xl:col-span-2 space-y-6">
					<Card>
						<CardHeader class="pb-3">
							<CardTitle class="text-base">{{ $t("lab.config.title") }}</CardTitle>
							<CardDescription class="text-xs">
								{{ $t("lab.config.desc") }}
							</CardDescription>
						</CardHeader>
						<CardContent class="pt-0">
							<Tabs v-model="activeTab" defaultValue="code">
								<TabsList class="w-full grid grid-cols-3 mb-4">
									<TabsTrigger value="code">{{ $t("lab.tab.code") }}</TabsTrigger>
									<TabsTrigger value="contract">{{ $t("lab.tab.contract") }}</TabsTrigger>
									<TabsTrigger value="fault">{{ $t("lab.tab.fault") }}</TabsTrigger>
								</TabsList>

								<TabsContent value="code" class="mt-0">
									<div class="space-y-3">
										<div>
											<Label class="text-xs mb-2 block">{{ $t("lab.code.langC") }}</Label>
											<Textarea
												v-model="codeContent"
												class="font-mono text-xs min-h-[280px] resize-y bg-muted border-border"
												spellcheck="false"
											/>
										</div>
										<div class="flex gap-3">
											<div class="flex-1">
												<Label class="text-xs mb-1.5 block">{{ $t("lab.code.inputPorts") }}</Label>
												<Input value="raw_value: uint16, sample_rate: uint16" readonly class="text-xs font-mono bg-muted" />
											</div>
											<div class="flex-1">
												<Label class="text-xs mb-1.5 block">{{ $t("lab.code.outputPorts") }}</Label>
												<Input value="filtered_value: uint16" readonly class="text-xs font-mono bg-muted" />
											</div>
										</div>
									</div>
								</TabsContent>

								<TabsContent value="contract" class="mt-0">
									<div class="space-y-4">
										<div>
											<Label class="text-xs mb-2 block">{{ $t("lab.contract.preconditions") }}</Label>
											<Textarea
												v-model="preconditions"
												:placeholder="$t('lab.contract.conditionPlaceholder')"
												class="font-mono text-xs min-h-[80px] resize-y bg-muted border-border"
												spellcheck="false"
											/>
										</div>
										<div>
											<Label class="text-xs mb-2 block">{{ $t("lab.contract.postconditions") }}</Label>
											<Textarea
												v-model="postconditions"
												:placeholder="$t('lab.contract.conditionPlaceholder')"
												class="font-mono text-xs min-h-[80px] resize-y bg-muted border-border"
												spellcheck="false"
											/>
										</div>
										<div>
											<Label class="text-xs mb-2 block">{{ $t("lab.contract.invariants") }}</Label>
											<Textarea
												v-model="invariants"
												:placeholder="$t('lab.contract.invariantPlaceholder')"
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
							<CardTitle class="text-base">{{ $t("lab.waveform.title") }}</CardTitle>
							<CardDescription class="text-xs">
								{{ $t("lab.waveform.desc") }}
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
										<span>⚠ {{ $t("lab.waveform.violation") }}</span>
										<code class="font-mono">[{{ currentResult.contract_violation.contract_id }}]</code>
									</div>
									<p class="text-xs text-muted-foreground mt-1">
										{{ $t("lab.waveform.violationDetail", {
											step: currentResult.contract_violation.timestep,
											message: currentResult.contract_violation.message,
										}) }}
									</p>
								</div>
							</div>
							<div v-else class="flex items-center justify-center h-[320px] border border-dashed border-border rounded-component-sm bg-muted/30">
								<div class="text-center">
									<div class="text-4xl mb-3">📈</div>
									<p class="text-sm text-muted-foreground">{{ $t("lab.waveform.emptyHint") }}</p>
								</div>
							</div>
						</CardContent>
					</Card>

					<Card>
						<CardHeader class="pb-3">
							<CardTitle class="text-base">{{ $t("lab.stats.title") }}</CardTitle>
							<CardDescription class="text-xs">
								{{ $t("lab.stats.desc") }}
							</CardDescription>
						</CardHeader>
						<CardContent class="pt-0">
							<div v-if="quickStats" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
								<div
									v-for="stat in quickStats"
									:key="stat.labelKey"
									class="p-3 bg-card border border-border rounded-component-sm"
								>
									<div class="text-[11px] text-muted-foreground uppercase tracking-wide">
										{{ $t(stat.labelKey) }}
									</div>
									<div class="text-lg font-semibold mt-1 font-mono">
										{{ stat.value }}
									</div>
									<div class="text-[10px] text-muted-foreground mt-0.5">
										{{ $t(stat.unitKey) }}
									</div>
								</div>
							</div>
							<div v-else class="flex items-center justify-center h-[80px] text-sm text-muted-foreground">
								{{ $t("lab.stats.empty") }}
							</div>
						</CardContent>
					</Card>

					<Card v-if="multiCompareEnabled && simulationHistory.length > 0">
						<CardHeader class="pb-3">
							<CardTitle class="text-base">
								{{ $t("lab.history.title") }}
								<span class="text-xs font-normal text-muted-foreground ml-2">
									{{ $t("lab.history.rounds", { count: simulationHistory.length }) }}
								</span>
							</CardTitle>
							<CardDescription class="text-xs">
								{{ $t("lab.history.desc") }}
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
										<span class="text-xs font-semibold">{{ $t("lab.history.round", { n: idx + 1 }) }}</span>
										<span
											class="text-[10px] px-2 py-0.5 rounded-full font-medium"
											:class="result.passed ? 'bg-success/15 text-success' : 'bg-destructive/15 text-destructive'"
										>
											{{ result.passed ? $t("lab.history.passed") : $t("lab.history.violated") }}
										</span>
									</div>
									<div class="text-[11px] text-muted-foreground space-y-1">
										<div>{{ $t("lab.history.fault", { type: result.fault_type ?? $t("lab.history.noFault") }) }}</div>
										<div>{{ $t("lab.history.stepRange", {
											steps: result.total_steps,
											min: result.statistics.output_min,
											max: result.statistics.output_max,
										}) }}</div>
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
							<CardTitle class="text-base">{{ $t("lab.detail.title") }}</CardTitle>
							<CardDescription class="text-xs">
								{{ $t("lab.detail.desc") }}
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
