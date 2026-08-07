<script setup lang="ts">
import {
	ArrowDown,
	ArrowLeft,
	ArrowRight,
	BookOpen,
	CheckCircle2,
	ChevronDown,
	Cog,
	FileCode,
	FileText,
	Gauge,
	Layers,
	PlayCircle,
	Search,
	ShieldCheck,
	Sparkles,
	Terminal,
	Wrench,
} from "@lucide/vue";
import type { Component } from "vue";
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const { t } = useI18n();

const isMounted = ref(false);
onMounted(() => {
	isMounted.value = true;
});

interface LayerCard {
	level: string;
	nameKey: string;
	nameEn: string;
	responsibilityKey: string;
	entry: string;
	gradient: string;
	borderGradient: string;
	files: number;
	keyFiles: string[];
}

const router = useRouter();

const layers: LayerCard[] = [
	{
		level: "L5",
		nameKey: "architecture.layers.orchestration.title",
		nameEn: "Orchestration",
		responsibilityKey: "architecture.layers.orchestration.responsibility",
		entry: "pipeline.py",
		gradient: "#f8fafc",
		borderGradient: "linear-gradient(135deg, #0b3555 0%, #1a8bdd 100%)",
		files: 1,
		keyFiles: ["pipeline.py", "core/orchestrator.py"],
	},
	{
		level: "L4",
		nameKey: "architecture.layers.agentStrategy.title",
		nameEn: "Agent Strategy",
		responsibilityKey: "architecture.layers.agentStrategy.responsibility",
		entry: "agents/code_generator.py",
		gradient: "#f8fafc",
		borderGradient: "linear-gradient(135deg, #0c4470 0%, #1a8bdd 100%)",
		files: 32,
		keyFiles: [
			"agents/code_generator.py",
			"agents/contract_generator.py",
			"agents/code_repairer.py",
			"agents/requirement_parser.py",
			"agents/architecture_designer.py",
		],
	},
	{
		level: "L3",
		nameKey: "architecture.layers.verifierChain.title",
		nameEn: "Verifier Chain",
		responsibilityKey: "architecture.layers.verifierChain.responsibility",
		entry: "tools/z3_verifier.py",
		gradient: "#f8fafc",
		borderGradient: "linear-gradient(135deg, #0e5a91 0%, #1a8bdd 100%)",
		files: 25,
		keyFiles: [
			"tools/z3_verifier.py",
			"tools/cbmc_verifier.py",
			"tools/cppcheck_scanner.py",
			"tools/contract_checker.py",
			"tools/tool_chain_validator.py",
		],
	},
	{
		level: "L2",
		nameKey: "architecture.layers.simulation.title",
		nameEn: "Simulation & Verification",
		responsibilityKey: "architecture.layers.simulation.responsibility",
		entry: "digital_twin/simulation_engine.py",
		gradient: "#f8fafc",
		borderGradient: "linear-gradient(135deg, #1170b3 0%, #1a8bdd 100%)",
		files: 30,
		keyFiles: [
			"digital_twin/hil_adapter.py",
			"digital_twin/qemu_adapter.py",
			"digital_twin/serial_hil.py",
			"digital_twin/arinc653_adapter.py",
			"digital_twin/fault_injector.py",
		],
	},
	{
		level: "L1",
		nameKey: "architecture.layers.llmClient.title",
		nameEn: "LLM Client",
		responsibilityKey: "architecture.layers.llmClient.responsibility",
		entry: "llm/router.py",
		gradient: "#f8fafc",
		borderGradient: "linear-gradient(135deg, #1170b3 0%, #30b5f4 100%)",
		files: 18,
		keyFiles: [
			"llm/router.py",
			"llm/mock_client.py",
			"llm/api_client.py",
			"llm/local_client.py",
			"llm/protocols.py",
		],
	},
	{
		level: "L0",
		nameKey: "architecture.layers.protocols.title",
		nameEn: "Protocols",
		responsibilityKey: "architecture.layers.protocols.responsibility",
		entry: "core/protocols.py",
		gradient: "#f8fafc",
		borderGradient: "linear-gradient(135deg, #1a8bdd 0%, #63d4ff 100%)",
		files: 111,
		keyFiles: [
			"core/protocols.py",
			"core/__init__.py",
			"mode_guard.py",
			"execution.py",
			"config.py",
		],
	},
];

const expandedLayer = ref<string | null>(null);

function toggleLayer(level: string) {
	expandedLayer.value = expandedLayer.value === level ? null : level;
}

interface PipelineStage {
	id: number;
	nameKey: string;
	nameEn: string;
	inputKey: string;
	outputKey: string;
	agents: string[];
	tools: string[];
}

const pipelineStages: PipelineStage[] = [
	{
		id: 1,
		nameKey: "architecture.pipeline.stages.reception.name",
		nameEn: "Requirement Reception",
		inputKey: "architecture.pipeline.stages.reception.input",
		outputKey: "architecture.pipeline.stages.reception.output",
		agents: ["requirement_parser"],
		tools: ["architecture.pipeline.tools.scadeParser"],
	},
	{
		id: 2,
		nameKey: "architecture.pipeline.stages.parsing.name",
		nameEn: "Requirement Parsing",
		inputKey: "architecture.pipeline.stages.parsing.input",
		outputKey: "architecture.pipeline.stages.parsing.output",
		agents: ["requirement_parser", "llr_generator"],
		tools: ["architecture.pipeline.tools.ragKnowledge"],
	},
	{
		id: 3,
		nameKey: "architecture.pipeline.stages.design.name",
		nameEn: "Architecture Design",
		inputKey: "architecture.pipeline.stages.design.input",
		outputKey: "architecture.pipeline.stages.design.output",
		agents: ["architecture_designer"],
		tools: ["architecture.pipeline.tools.comboVerifier"],
	},
	{
		id: 4,
		nameKey: "architecture.pipeline.stages.contracts.name",
		nameEn: "Contract Generation",
		inputKey: "architecture.pipeline.stages.contracts.input",
		outputKey: "architecture.pipeline.stages.contracts.output",
		agents: ["contract_generator"],
		tools: ["Z3 SMT"],
	},
	{
		id: 5,
		nameKey: "architecture.pipeline.stages.codegen.name",
		nameEn: "Code Generation",
		inputKey: "architecture.pipeline.stages.codegen.input",
		outputKey: "architecture.pipeline.stages.codegen.output",
		agents: ["code_generator", "code_generator_multi"],
		tools: ["architecture.pipeline.tools.misraRuleLibrary"],
	},
	{
		id: 6,
		nameKey: "architecture.pipeline.stages.misra.name",
		nameEn: "MISRA Adaptation",
		inputKey: "architecture.pipeline.stages.misra.input",
		outputKey: "architecture.pipeline.stages.misra.output",
		agents: ["misra_fixes", "misra_cpp_fixes", "python_fixes"],
		tools: ["Cppcheck", "MISRA addon"],
	},
	{
		id: 7,
		nameKey: "architecture.pipeline.stages.static.name",
		nameEn: "Static Analysis",
		inputKey: "architecture.pipeline.stages.static.input",
		outputKey: "architecture.pipeline.stages.static.output",
		agents: ["code_repairer"],
		tools: ["Cppcheck", "GCC -Wall"],
	},
	{
		id: 8,
		nameKey: "architecture.pipeline.stages.contractCheck.name",
		nameEn: "Contract Checking",
		inputKey: "architecture.pipeline.stages.contractCheck.input",
		outputKey: "architecture.pipeline.stages.contractCheck.output",
		agents: [],
		tools: ["contract_checker", "Z3"],
	},
	{
		id: 9,
		nameKey: "architecture.pipeline.stages.simulation.name",
		nameEn: "Simulation",
		inputKey: "architecture.pipeline.stages.simulation.input",
		outputKey: "architecture.pipeline.stages.simulation.output",
		agents: [],
		tools: ["QEMU", "VirtualMCU", "FaultInjector"],
	},
	{
		id: 10,
		nameKey: "architecture.pipeline.stages.formal.name",
		nameEn: "Formal Verification",
		inputKey: "architecture.pipeline.stages.formal.input",
		outputKey: "architecture.pipeline.stages.formal.output",
		agents: [],
		tools: ["CBMC", "Z3 SMT"],
	},
	{
		id: 11,
		nameKey: "architecture.pipeline.stages.hitl.name",
		nameEn: "Human-in-the-Loop",
		inputKey: "architecture.pipeline.stages.hitl.input",
		outputKey: "architecture.pipeline.stages.hitl.output",
		agents: [],
		tools: ["architecture.pipeline.tools.hitlWorkbench"],
	},
	{
		id: 12,
		nameKey: "architecture.pipeline.stages.evidence.name",
		nameEn: "Evidence Package",
		inputKey: "architecture.pipeline.stages.evidence.input",
		outputKey: "architecture.pipeline.stages.evidence.output",
		agents: [],
		tools: ["report_generator", "architecture.pipeline.tools.psacGenerator"],
	},
];

function toolLabel(tool: string): string {
	return tool.startsWith("architecture.") ? t(tool) : tool;
}

interface QuickStep {
	id: number;
	titleKey: string;
	descriptionKey: string;
	icon: Component;
	actionKey: string;
	route: string;
}

const quickSteps: QuickStep[] = [
	{
		id: 1,
		titleKey: "architecture.quickstart.steps.source.title",
		descriptionKey: "architecture.quickstart.steps.source.description",
		icon: Gauge,
		actionKey: "architecture.quickstart.steps.source.action",
		route: "/settings",
	},
	{
		id: 2,
		titleKey: "architecture.quickstart.steps.model.title",
		descriptionKey: "architecture.quickstart.steps.model.description",
		icon: Cog,
		actionKey: "architecture.quickstart.steps.model.action",
		route: "/settings",
	},
	{
		id: 3,
		titleKey: "architecture.quickstart.steps.firstTask.title",
		descriptionKey: "architecture.quickstart.steps.firstTask.description",
		icon: PlayCircle,
		actionKey: "architecture.quickstart.steps.firstTask.action",
		route: "/generate",
	},
	{
		id: 4,
		titleKey: "architecture.quickstart.steps.results.title",
		descriptionKey: "architecture.quickstart.steps.results.description",
		icon: FileText,
		actionKey: "architecture.quickstart.steps.results.action",
		route: "/records",
	},
	{
		id: 5,
		titleKey: "architecture.quickstart.steps.evidence.title",
		descriptionKey: "architecture.quickstart.steps.evidence.description",
		icon: ShieldCheck,
		actionKey: "architecture.quickstart.steps.evidence.action",
		route: "/lab",
	},
];

interface FaqItem {
	qKey: string;
	aKey: string;
}

const faqItems: FaqItem[] = [
	{
		qKey: "architecture.faq.item1.q",
		aKey: "architecture.faq.item1.a",
	},
	{
		qKey: "architecture.faq.item2.q",
		aKey: "architecture.faq.item2.a",
	},
	{
		qKey: "architecture.faq.item3.q",
		aKey: "architecture.faq.item3.a",
	},
	{
		qKey: "architecture.faq.item4.q",
		aKey: "architecture.faq.item4.a",
	},
	{
		qKey: "architecture.faq.item5.q",
		aKey: "architecture.faq.item5.a",
	},
];

const expandedFaq = ref<number | null>(null);

function toggleFaq(id: number) {
	expandedFaq.value = expandedFaq.value === id ? null : id;
}

interface StandardCategory {
	nameKey: string;
	ruleKeys: string[];
}

interface CodingStandard {
	id: string;
	nameKey: string;
	version: string;
	descriptionKey: string;
	categories: StandardCategory[];
	scenarioKeys: string[];
	referenceKeys: string[];
}

const codingStandards: CodingStandard[] = [
	{
		id: "misra-c",
		nameKey: "architecture.standards.misraC.name",
		version: "2012",
		descriptionKey: "architecture.standards.misraC.description",
		categories: [
			{
				nameKey: "architecture.standards.misraC.categories.environment.name",
				ruleKeys: [
					"architecture.standards.misraC.categories.environment.r1",
					"architecture.standards.misraC.categories.environment.r2",
					"architecture.standards.misraC.categories.environment.r3",
				],
			},
			{
				nameKey: "architecture.standards.misraC.categories.typeSafety.name",
				ruleKeys: [
					"architecture.standards.misraC.categories.typeSafety.r1",
					"architecture.standards.misraC.categories.typeSafety.r2",
					"architecture.standards.misraC.categories.typeSafety.r3",
				],
			},
			{
				nameKey: "architecture.standards.misraC.categories.memory.name",
				ruleKeys: [
					"architecture.standards.misraC.categories.memory.r1",
					"architecture.standards.misraC.categories.memory.r2",
				],
			},
			{
				nameKey: "architecture.standards.misraC.categories.controlFlow.name",
				ruleKeys: [
					"architecture.standards.misraC.categories.controlFlow.r1",
					"architecture.standards.misraC.categories.controlFlow.r2",
					"architecture.standards.misraC.categories.controlFlow.r3",
				],
			},
		],
		scenarioKeys: [
			"architecture.standards.misraC.scenarios.s1",
			"architecture.standards.misraC.scenarios.s2",
			"architecture.standards.misraC.scenarios.s3",
			"architecture.standards.misraC.scenarios.s4",
		],
		referenceKeys: [
			"architecture.standards.misraC.references.r1",
			"architecture.standards.misraC.references.r2",
			"architecture.standards.misraC.references.r3",
		],
	},
	{
		id: "misra-cpp-jsf",
		nameKey: "architecture.standards.misraCpp.name",
		version: "2023",
		descriptionKey: "architecture.standards.misraCpp.description",
		categories: [
			{
				nameKey: "architecture.standards.misraCpp.categories.typeSafety.name",
				ruleKeys: [
					"architecture.standards.misraCpp.categories.typeSafety.r1",
					"architecture.standards.misraCpp.categories.typeSafety.r2",
				],
			},
			{
				nameKey: "architecture.standards.misraCpp.categories.memory.name",
				ruleKeys: [
					"architecture.standards.misraCpp.categories.memory.r1",
					"architecture.standards.misraCpp.categories.memory.r2",
				],
			},
			{
				nameKey: "architecture.standards.misraCpp.categories.exceptions.name",
				ruleKeys: [
					"architecture.standards.misraCpp.categories.exceptions.r1",
					"architecture.standards.misraCpp.categories.exceptions.r2",
				],
			},
		],
		scenarioKeys: [
			"architecture.standards.misraCpp.scenarios.s1",
			"architecture.standards.misraCpp.scenarios.s2",
			"architecture.standards.misraCpp.scenarios.s3",
		],
		referenceKeys: [
			"architecture.standards.misraCpp.references.r1",
			"architecture.standards.misraCpp.references.r2",
			"architecture.standards.misraCpp.references.r3",
		],
	},
	{
		id: "python-safety",
		nameKey: "architecture.standards.pythonSafety.name",
		version: "1.0",
		descriptionKey: "architecture.standards.pythonSafety.description",
		categories: [
			{
				nameKey:
					"architecture.standards.pythonSafety.categories.typeSafety.name",
				ruleKeys: [
					"architecture.standards.pythonSafety.categories.typeSafety.r1",
					"architecture.standards.pythonSafety.categories.typeSafety.r2",
				],
			},
			{
				nameKey: "architecture.standards.pythonSafety.categories.security.name",
				ruleKeys: [
					"architecture.standards.pythonSafety.categories.security.r1",
					"architecture.standards.pythonSafety.categories.security.r2",
				],
			},
			{
				nameKey:
					"architecture.standards.pythonSafety.categories.reliability.name",
				ruleKeys: [
					"architecture.standards.pythonSafety.categories.reliability.r1",
					"architecture.standards.pythonSafety.categories.reliability.r2",
				],
			},
		],
		scenarioKeys: [
			"architecture.standards.pythonSafety.scenarios.s1",
			"architecture.standards.pythonSafety.scenarios.s2",
			"architecture.standards.pythonSafety.scenarios.s3",
		],
		referenceKeys: [
			"architecture.standards.pythonSafety.references.r1",
			"architecture.standards.pythonSafety.references.r2",
		],
	},
	{
		id: "do178c",
		nameKey: "architecture.standards.do178c.name",
		version: "DAL A/B/C/D",
		descriptionKey: "architecture.standards.do178c.description",
		categories: [
			{
				nameKey: "architecture.standards.do178c.categories.objectives.name",
				ruleKeys: [
					"architecture.standards.do178c.categories.objectives.r1",
					"architecture.standards.do178c.categories.objectives.r2",
					"architecture.standards.do178c.categories.objectives.r3",
					"architecture.standards.do178c.categories.objectives.r4",
				],
			},
			{
				nameKey: "architecture.standards.do178c.categories.dalLevels.name",
				ruleKeys: [
					"architecture.standards.do178c.categories.dalLevels.r1",
					"architecture.standards.do178c.categories.dalLevels.r2",
					"architecture.standards.do178c.categories.dalLevels.r3",
					"architecture.standards.do178c.categories.dalLevels.r4",
				],
			},
			{
				nameKey: "architecture.standards.do178c.categories.evidence.name",
				ruleKeys: [
					"architecture.standards.do178c.categories.evidence.r1",
					"architecture.standards.do178c.categories.evidence.r2",
					"architecture.standards.do178c.categories.evidence.r3",
					"architecture.standards.do178c.categories.evidence.r4",
					"architecture.standards.do178c.categories.evidence.r5",
					"architecture.standards.do178c.categories.evidence.r6",
					"architecture.standards.do178c.categories.evidence.r7",
				],
			},
		],
		scenarioKeys: [
			"architecture.standards.do178c.scenarios.s1",
			"architecture.standards.do178c.scenarios.s2",
			"architecture.standards.do178c.scenarios.s3",
		],
		referenceKeys: [
			"architecture.standards.do178c.references.r1",
			"architecture.standards.do178c.references.r2",
			"architecture.standards.do178c.references.r3",
		],
	},
];

function backToHome() {
	router.push("/");
}

function navigateTo(route: string) {
	router.push(route);
}
</script>

<template>
	<main class="min-h-[calc(100vh-64px)] bg-background py-8 px-4 sm:px-6 lg:px-8">
		<div class="max-w-6xl mx-auto">
			<header
				class="mb-8 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4"
				:class="{ 'animate-in': isMounted }"
			>
				<div class="flex items-start gap-3">
					<div class="p-2 rounded-lg bg-primary/10 text-primary">
						<Layers :size="24" />
					</div>
					<div>
						<p class="text-xs font-semibold tracking-wider text-primary uppercase mb-1">
							Architecture & Documentation
						</p>
						<h1 class="text-2xl sm:text-3xl font-semibold text-foreground">
							{{ t("architecture.title") }}
						</h1>
						<p class="text-muted-foreground mt-1 text-sm">
							{{ t("architecture.subtitle") }}
						</p>
					</div>
				</div>
				<Button variant="outline" size="sm" @click="backToHome">
					<ArrowLeft :size="16" class="mr-2" />
					{{ t("architecture.backHome") }}
				</Button>
			</header>

			<Tabs defaultValue="layers" class="w-full">
				<TabsList class="w-full grid grid-cols-2 sm:grid-cols-4 mb-8">
					<TabsTrigger value="layers">
						<Layers :size="16" class="mr-2" />
						{{ t("architecture.tabs.layers") }}
					</TabsTrigger>
					<TabsTrigger value="pipeline">
						<Gauge :size="16" class="mr-2" />
						{{ t("architecture.tabs.pipeline") }}
					</TabsTrigger>
					<TabsTrigger value="quickstart">
						<PlayCircle :size="16" class="mr-2" />
						{{ t("architecture.tabs.quickstart") }}
					</TabsTrigger>
					<TabsTrigger value="standards">
						<ShieldCheck :size="16" class="mr-2" />
						{{ t("architecture.tabs.standards") }}
					</TabsTrigger>
				</TabsList>

				<TabsContent value="layers" class="mt-0">
					<div class="space-y-3">
						<template v-for="(layer, idx) in layers" :key="layer.level">
							<Card
								class="overflow-hidden transition-all duration-300 ease-out cursor-pointer hover:shadow-lg"
								:class="{ 'animate-in': isMounted }"
								:style="{ '--delay': `${idx * 80}ms` }"
								@click="toggleLayer(layer.level)"
							>
								<CardContent class="p-5">
									<div class="flex items-start gap-4">
										<div
											class="shrink-0 w-12 h-12 rounded-lg bg-primary flex items-center justify-center text-primary-foreground font-bold text-lg"
										>
											{{ layer.level }}
										</div>
										<div class="flex-1 min-w-0">
											<div class="flex items-center gap-3 flex-wrap">
												<h3 class="text-lg font-semibold">
													{{ t(layer.nameKey) }}
												</h3>
												<span class="text-muted-foreground text-sm">
													{{ layer.nameEn }}
												</span>
												<Badge variant="secondary" class="ml-auto">
													<FileCode :size="12" class="mr-1" />
													{{ layer.files }} files
												</Badge>
											</div>
											<p class="text-muted-foreground mt-2 text-sm leading-relaxed">
												{{ t(layer.responsibilityKey) }}
											</p>

											<div
												v-if="expandedLayer === layer.level"
												class="mt-4 space-y-3 pt-3 border-t border-border"
											>
												<div class="flex items-center gap-2">
													<span
														class="text-xs font-medium text-muted-foreground uppercase"
													>
														{{ t("architecture.layerLabels.mainEntry") }}
													</span>
													<code
														class="bg-muted rounded-md px-2 py-1 font-mono text-xs"
													>
														skyforge_engine/{{ layer.entry }}
													</code>
												</div>
												<div>
													<span
														class="text-xs font-medium text-muted-foreground uppercase block mb-2"
													>
														{{ t("architecture.layerLabels.keyFiles") }}
													</span>
													<ul class="flex flex-wrap gap-2">
														<li v-for="f in layer.keyFiles" :key="f">
															<code
																class="bg-muted rounded-md px-2 py-1 font-mono text-xs hover:bg-muted/80 transition-colors"
															>
																skyforge_engine/{{ f }}
															</code>
														</li>
													</ul>
												</div>
											</div>
										</div>
										<div
											class="shrink-0 text-muted-foreground transition-transform duration-200"
											:class="{ 'rotate-180': expandedLayer === layer.level }"
										>
											<ChevronDown :size="20" />
										</div>
									</div>
								</CardContent>
							</Card>

							<div
								v-if="idx < layers.length - 1"
								class="flex justify-center py-1"
								aria-hidden="true"
							>
								<div class="w-7 h-7 rounded-full bg-card border border-border flex items-center justify-center text-primary">
									<ArrowDown :size="14" />
								</div>
							</div>
						</template>
					</div>
				</TabsContent>

				<TabsContent value="pipeline" class="mt-0">
					<Card>
						<CardHeader>
							<CardTitle class="flex items-center gap-2">
								<Gauge :size="20" class="text-primary" />
								{{ t("architecture.pipeline.title") }}
							</CardTitle>
							<CardDescription>
								{{ t("architecture.pipeline.description") }}
							</CardDescription>
						</CardHeader>
						<CardContent>
							<div class="relative">
								<div
									class="absolute left-4 sm:left-6 top-0 bottom-0 w-0.5 bg-border hidden sm:block"
									aria-hidden="true"
								></div>

								<div class="space-y-6">
									<div
										v-for="(stage, idx) in pipelineStages"
										:key="stage.id"
										class="relative"
									>
										<div class="flex gap-4">
											<div
												class="shrink-0 relative z-10 w-8 h-8 sm:w-12 sm:h-12 rounded-full bg-primary text-primary-foreground flex items-center justify-center font-bold text-sm sm:text-base"
											>
												{{ stage.id }}
											</div>
											<Card
												class="flex-1 hover:shadow-md transition-shadow duration-200"
											>
												<CardContent class="p-4 sm:p-5">
													<div
														class="flex items-start justify-between gap-3 flex-wrap"
													>
														<div>
															<h4 class="font-semibold text-base">
																{{ t(stage.nameKey) }}
															</h4>
															<p
																class="text-xs text-muted-foreground mt-0.5"
															>
																{{ stage.nameEn }}
															</p>
														</div>
														<Badge
															variant="outline"
															class="shrink-0"
														>
															{{ t("architecture.pipeline.stage", { id: stage.id }) }}
														</Badge>
													</div>

													<div class="mt-4 grid gap-3 sm:grid-cols-2">
														<div class="space-y-1">
															<p
																class="text-xs font-medium text-muted-foreground uppercase"
															>
																{{ t("architecture.pipeline.input") }}
															</p>
															<p class="text-sm">{{ t(stage.inputKey) }}</p>
														</div>
														<div class="space-y-1">
															<p
																class="text-xs font-medium text-muted-foreground uppercase"
															>
																{{ t("architecture.pipeline.output") }}
															</p>
															<p class="text-sm">
																{{ t(stage.outputKey) }}
															</p>
														</div>
													</div>

													<div
														v-if="stage.agents.length > 0 || stage.tools.length > 0"
														class="mt-3 flex flex-wrap gap-3"
													>
														<div
															v-if="stage.agents.length > 0"
															class="flex items-center gap-2 flex-wrap"
														>
															<span
																class="text-xs text-muted-foreground flex items-center gap-1"
															>
																<Sparkles :size="12" />
																Agents:
															</span>
															<Badge
																v-for="agent in stage.agents"
																:key="agent"
																variant="secondary"
																class="text-xs"
															>
																{{ agent }}
															</Badge>
														</div>
														<div
															v-if="stage.tools.length > 0"
															class="flex items-center gap-2 flex-wrap"
														>
															<span
																class="text-xs text-muted-foreground flex items-center gap-1"
															>
																<Wrench :size="12" />
																{{ t("architecture.pipeline.toolsLabel") }}
															</span>
															<Badge
																v-for="tool in stage.tools"
																:key="tool"
																variant="outline"
																class="text-xs"
															>
																{{ toolLabel(tool) }}
															</Badge>
														</div>
													</div>
												</CardContent>
											</Card>
										</div>

										<div
											v-if="idx < pipelineStages.length - 1"
											class="flex sm:hidden justify-center py-2 pl-4"
											aria-hidden="true"
										>
											<ArrowDown
												:size="16"
												class="text-muted-foreground"
											/>
										</div>
									</div>
								</div>
							</div>
						</CardContent>
					</Card>
				</TabsContent>

				<TabsContent value="quickstart" class="mt-0">
					<div class="grid gap-6 lg:grid-cols-3">
						<div class="lg:col-span-2 space-y-6">
							<Card>
								<CardHeader>
									<CardTitle class="flex items-center gap-2">
										<BookOpen :size="20" class="text-primary" />
										{{ t("architecture.quickstart.title") }}
									</CardTitle>
									<CardDescription>
										{{ t("architecture.quickstart.description") }}
									</CardDescription>
								</CardHeader>
								<CardContent class="space-y-4">
									<div
										v-for="(step, idx) in quickSteps"
										:key="step.id"
										class="relative"
									>
										<div class="flex gap-4">
											<div class="flex flex-col items-center">
												<div
													class="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-semibold"
												>
													<component :is="step.icon" :size="20" />
												</div>
												<div
													v-if="idx < quickSteps.length - 1"
													class="w-0.5 flex-1 bg-border my-2"
													aria-hidden="true"
												></div>
											</div>
											<Card
												class="flex-1 mb-4 hover:shadow-md transition-shadow"
											>
												<CardContent class="p-4">
													<div class="flex items-start justify-between gap-3 flex-wrap">
														<div class="flex-1">
															<h4 class="font-semibold flex items-center gap-2">
																<span
																	class="text-primary"
																>
																	Step {{ step.id }}:
																</span>
																{{ t(step.titleKey) }}
															</h4>
															<p
																class="text-sm text-muted-foreground mt-1.5"
															>
																{{ t(step.descriptionKey) }}
															</p>
														</div>
													</div>
													<Button
														size="sm"
														variant="ghost"
														class="mt-3 -ml-2"
														@click="navigateTo(step.route)"
													>
														{{ t(step.actionKey) }}
														<ArrowRight
															:size="14"
															class="ml-1.5"
														/>
													</Button>
												</CardContent>
											</Card>
										</div>
									</div>
								</CardContent>
							</Card>
						</div>

						<div class="space-y-6">
							<Card>
								<CardHeader>
									<CardTitle class="flex items-center gap-2 text-base">
										<Terminal :size="18" class="text-primary" />
										{{ t("architecture.quickstart.quickStartTitle") }}
									</CardTitle>
								</CardHeader>
								<CardContent>
									<pre
										class="bg-muted rounded-md p-3 font-mono text-xs overflow-x-auto"
									>
<code># 克隆项目
git clone https://atomgit.com/.../SkyForge.git
cd SkyForge

# 一键启动
sh start.sh

# 访问: http://localhost:5173</code></pre>
								</CardContent>
							</Card>

							<Card>
								<CardHeader>
									<CardTitle class="flex items-center gap-2 text-base">
										<Search :size="18" class="text-primary" />
										{{ t("architecture.quickstart.faqTitle") }}
									</CardTitle>
								</CardHeader>
								<CardContent class="space-y-2">
									<div
										v-for="(item, index) in faqItems"
										:key="item.qKey"
										class="border border-border rounded-lg overflow-hidden"
									>
										<button
											class="w-full p-3 text-left flex items-start justify-between gap-3 hover:bg-muted/50 transition-colors"
											@click="toggleFaq(index)"
										>
											<span class="text-sm font-medium">
												{{ t(item.qKey) }}
											</span>
											<ChevronDown
												:size="16"
												class="shrink-0 text-muted-foreground transition-transform mt-0.5"
												:class="{
													'rotate-180': expandedFaq === index,
												}"
											/>
										</button>
										<div
											v-if="expandedFaq === index"
											class="px-3 pb-3 text-sm text-muted-foreground border-t border-border pt-3"
										>
											{{ t(item.aKey) }}
										</div>
									</div>
								</CardContent>
							</Card>
						</div>
					</div>
				</TabsContent>

				<TabsContent value="standards" class="mt-0">
					<div class="space-y-6">
						<div
							v-for="(std, idx) in codingStandards"
							:key="std.id"
							class="scroll-mt-4"
							:id="std.id"
						>
							<Card
								class="hover:shadow-md transition-shadow duration-200"
							>
								<CardHeader>
									<div class="flex items-start justify-between gap-3 flex-wrap">
										<div>
											<CardTitle
												class="flex items-center gap-2 text-xl"
											>
												<ShieldCheck
													:size="22"
													class="text-primary"
												/>
												{{ t(std.nameKey) }}
											</CardTitle>
											<CardDescription class="mt-1">
												{{ t("architecture.standards.version", { version: std.version }) }}
											</CardDescription>
										</div>
										<Badge variant="secondary">
											{{ idx + 1 }}/{{ codingStandards.length }}
										</Badge>
									</div>
									<p class="text-sm text-muted-foreground mt-3 leading-relaxed">
										{{ t(std.descriptionKey) }}
									</p>
								</CardHeader>
								<CardContent class="space-y-5 pt-0">
									<div
										v-for="cat in std.categories"
										:key="cat.nameKey"
									>
										<h5
											class="text-sm font-semibold text-foreground mb-2 flex items-center gap-2"
										>
											<span
												class="w-1.5 h-1.5 rounded-full bg-primary"
											></span>
											{{ t(cat.nameKey) }}
										</h5>
										<ul class="space-y-1.5 pl-3.5">
											<li
												v-for="(ruleKey, ruleIdx) in cat.ruleKeys"
												:key="ruleIdx"
												class="text-sm text-muted-foreground flex items-start gap-2"
											>
												<CheckCircle2
													:size="14"
													class="text-primary mt-0.5 shrink-0"
												/>
												<span>{{ t(ruleKey) }}</span>
											</li>
										</ul>
									</div>

									<div class="flex flex-wrap gap-4 pt-3 border-t border-border">
										<div>
											<p
												class="text-xs font-medium text-muted-foreground uppercase mb-1.5"
											>
												{{ t("architecture.standards.scenarios") }}
											</p>
											<div class="flex flex-wrap gap-1.5">
												<Badge
													v-for="s in std.scenarioKeys"
													:key="s"
													variant="outline"
													class="text-xs"
												>
													{{ t(s) }}
												</Badge>
											</div>
										</div>
										<div>
											<p
												class="text-xs font-medium text-muted-foreground uppercase mb-1.5"
											>
												{{ t("architecture.standards.references") }}
											</p>
											<ul class="space-y-0.5">
												<li
													v-for="refKey in std.referenceKeys"
													:key="refKey"
													class="text-xs text-muted-foreground"
												>
													• {{ t(refKey) }}
												</li>
											</ul>
										</div>
									</div>
								</CardContent>
							</Card>
						</div>
					</div>
				</TabsContent>
			</Tabs>
		</div>
	</main>
</template>

<style scoped>
.animate-in {
	animation: fadeInUp 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes fadeInUp {
	from {
		opacity: 0;
		transform: translateY(12px);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}

main {
	animation-delay: var(--delay, 0ms);
}

@media (prefers-reduced-motion: reduce) {
	.animate-in,
	.animate-in * {
		animation: none !important;
		transition: none !important;
	}
	main,
	.animate-in {
		opacity: 1 !important;
		transform: none !important;
	}
}
</style>