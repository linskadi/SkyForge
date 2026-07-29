<script setup lang="ts">
import {
	ArrowDown,
	ArrowLeft,
	ArrowRight,
	BookOpen,
	CheckCircle2,
	ChevronDown,
	ChevronUp,
	Code2,
	Cog,
	FileCode,
	FileText,
	FlaskConical,
	Gauge,
	Layers,
	PlayCircle,
	Search,
	ShieldCheck,
	Sparkles,
	Terminal,
	Wrench,
} from "@lucide/vue";
import { onMounted, ref } from "vue";
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

const isMounted = ref(false);
onMounted(() => {
	isMounted.value = true;
});

interface LayerCard {
	level: string;
	nameZh: string;
	nameEn: string;
	responsibility: string;
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
		nameZh: "编排层",
		nameEn: "Orchestration",
		responsibility: "串联各层职责，调度 pipeline 全流程并生成可信证据包。",
		entry: "pipeline.py",
		gradient: "#f8fafc",
		borderGradient: "linear-gradient(135deg, #0b3555 0%, #1a8bdd 100%)",
		files: 1,
		keyFiles: ["pipeline.py", "core/orchestrator.py"],
	},
	{
		level: "L4",
		nameZh: "Agent 策略层",
		nameEn: "Agent Strategy",
		responsibility:
			"多 Agent 负责需求解析、LLR / 契约 / 代码生成、修复与 MISRA 适配。",
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
		nameZh: "验证工具链层",
		nameEn: "Verifier Chain",
		responsibility:
			"Z3 / CBMC / Cppcheck / GCC 等形式化与静态分析工具的可插拔链。",
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
		nameZh: "仿真验证层（SIL/PIL/HIL）",
		nameEn: "Simulation & Verification",
		responsibility:
			"覆盖纯软件仿真（SIL）、QEMU 处理器仿真（PIL）与真实硬件在环（HIL），支持故障注入与 ARINC 653 分区调度。",
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
		nameZh: "LLM 客户端层",
		nameEn: "LLM Client",
		responsibility:
			"统一 LLM 接口：Mock / 云 API / 本地 OpenAI 兼容客户端与路由。",
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
		nameZh: "基础设施协议层",
		nameEn: "Protocols",
		responsibility: "协议 / 抽象基类 / 模式守卫与执行契约，定义上层交互面。",
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
	nameZh: string;
	nameEn: string;
	input: string;
	output: string;
	agents: string[];
	tools: string[];
}

const pipelineStages: PipelineStage[] = [
	{
		id: 1,
		nameZh: "需求接收",
		nameEn: "Requirement Reception",
		input: "用户自然语言需求 / SCADE Lustre 模型",
		output: "标准化需求文档",
		agents: ["requirement_parser"],
		tools: ["SCADE 解析器"],
	},
	{
		id: 2,
		nameZh: "需求解析",
		nameEn: "Requirement Parsing",
		input: "标准化需求文档",
		output: "结构化 HLR / LLR 需求",
		agents: ["requirement_parser", "llr_generator"],
		tools: ["RAG 知识库"],
	},
	{
		id: 3,
		nameZh: "架构设计",
		nameEn: "Architecture Design",
		input: "结构化需求",
		output: "模块架构图与接口定义",
		agents: ["architecture_designer"],
		tools: ["组合验证器"],
	},
	{
		id: 4,
		nameZh: "契约生成",
		nameEn: "Contract Generation",
		input: "架构设计 + 需求",
		output: "YAML 契约文件（前置/后置/不变式）",
		agents: ["contract_generator"],
		tools: ["Z3 SMT"],
	},
	{
		id: 5,
		nameZh: "代码生成",
		nameEn: "Code Generation",
		input: "契约 + 架构",
		output: "C/C++/Python 源代码",
		agents: ["code_generator", "code_generator_multi"],
		tools: ["MISRA 规则库"],
	},
	{
		id: 6,
		nameZh: "MISRA 适配",
		nameEn: "MISRA Adaptation",
		input: "生成的源代码",
		output: "符合编码标准的代码",
		agents: ["misra_fixes", "misra_cpp_fixes", "python_fixes"],
		tools: ["Cppcheck", "MISRA addon"],
	},
	{
		id: 7,
		nameZh: "静态分析",
		nameEn: "Static Analysis",
		input: "适配后的代码",
		output: "静态分析报告",
		agents: ["code_repairer"],
		tools: ["Cppcheck", "GCC -Wall"],
	},
	{
		id: 8,
		nameZh: "契约检查",
		nameEn: "Contract Checking",
		input: "代码 + 契约文件",
		output: "契约验证报告",
		agents: [],
		tools: ["contract_checker", "Z3"],
	},
	{
		id: 9,
		nameZh: "仿真验证",
		nameEn: "Simulation",
		input: "验证通过的代码",
		output: "数字孪生仿真结果 + 覆盖率数据",
		agents: [],
		tools: ["QEMU", "VirtualMCU", "FaultInjector"],
	},
	{
		id: 10,
		nameZh: "形式化验证",
		nameEn: "Formal Verification",
		input: "代码 + 契约",
		output: "形式化验证证明",
		agents: [],
		tools: ["CBMC", "Z3 SMT"],
	},
	{
		id: 11,
		nameZh: "HITL 审查",
		nameEn: "Human-in-the-Loop",
		input: "验证产物 + 风险评估",
		output: "人工审批结论",
		agents: [],
		tools: ["HITL 工作台"],
	},
	{
		id: 12,
		nameZh: "证据包生成",
		nameEn: "Evidence Package",
		input: "所有阶段产物",
		output: "DO-178C 合规证据包（PDF/HTML）",
		agents: [],
		tools: ["report_generator", "PSAC 生成器"],
	},
];

interface QuickStep {
	id: number;
	title: string;
	description: string;
	icon: any;
	action: string;
	route: string;
}

const quickSteps: QuickStep[] = [
	{
		id: 1,
		title: "选择运行来源",
		description: "从 cloud（云模型）或 local（本地模型）中选择适合的执行模式。",
		icon: Gauge,
		action: "前往系统设置",
		route: "/settings",
	},
	{
		id: 2,
		title: "配置模型连接",
		description:
			"配置云 API 地址、密钥或本地 Ollama/LM Studio 端点，确保 LLM 服务可用。",
		icon: Cog,
		action: "配置模型",
		route: "/settings",
	},
	{
		id: 3,
		title: "创建第一个代码生成任务",
		description:
			"在代码生成页面输入自然语言需求，选择编程语言，启动全流水线任务。",
		icon: PlayCircle,
		action: "开始生成",
		route: "/generate",
	},
	{
		id: 4,
		title: "查看运行结果",
		description: "在运行记录中查看任务状态、生成的代码、验证报告与覆盖率数据。",
		icon: FileText,
		action: "查看记录",
		route: "/records",
	},
	{
		id: 5,
		title: "理解验证证据",
		description:
			"学习如何阅读 DO-178C 合规报告、追溯矩阵、MISRA 检查结果与形式化验证证明。",
		icon: ShieldCheck,
		action: "了解更多",
		route: "/lab",
	},
];

interface FaqItem {
	q: string;
	a: string;
}

const faqItems: FaqItem[] = [
	{
		q: "SkyForge 支持哪些编程语言？",
		a: "当前支持 C（MISRA-C:2012）、C++（MISRA C++ / JSF AV C++）和 Python（军工安全标准）三种语言的代码生成与验证。",
	},
	{
		q: "什么是两种执行模式 Profile？",
		a: "cloud 模式连接云 LLM 服务，执行真实推理；local 模式使用本地部署的 Ollama/LM Studio，数据不出内网。mock 模式仅在无后端时用于开发调试。",
	},
	{
		q: "MISRA 违规会自动修复吗？",
		a: "会。SkyForge 内置 57 条 MISRA-C 自动修复规则，Cppcheck 扫描发现的违规会由 code_repairer Agent 自动修复并重新验证。",
	},
	{
		q: "形式化验证使用哪些工具？",
		a: "使用 Z3 SMT 求解器进行契约验证，CBMC 进行有界模型检查。两者构成 VerifierChain 可插拔验证链。",
	},
	{
		q: "HITL 人工审查如何工作？",
		a: "在需求、契约和代码三个关键检查点，系统会根据风险评估决定是否需要人工审批。可在系统设置中启用或禁用 HITL。",
	},
];

const expandedFaq = ref<number | null>(null);

function toggleFaq(id: number) {
	expandedFaq.value = expandedFaq.value === id ? null : id;
}

interface CodingStandard {
	id: string;
	name: string;
	version: string;
	description: string;
	categories: { name: string; rules: string[] }[];
	scenarios: string[];
	references: string[];
}

const codingStandards: CodingStandard[] = [
	{
		id: "misra-c",
		name: "MISRA-C",
		version: "2012",
		description:
			"MISRA C 是由汽车工业软件可靠性协会（MISRA）发布的 C 语言编码规范，旨在提高嵌入式系统的安全性和可靠性。SkyForge 实现了 10 条红线规则和 56 个修复器。",
		categories: [
			{
				name: "环境与编译",
				rules: [
					"Rule 1.1: 不使用未定义/未指定/实现定义的行为",
					"Rule 1.2: 不得出现违反标准 C 的代码",
					"Rule 2.1: 项目不得包含无法到达的代码",
				],
			},
			{
				name: "类型安全",
				rules: [
					"Rule 8.13: 指针参数应声明为指向 const 的指针",
					"Rule 10.1: 运算符的操作数值不得有不适当的底层类型",
					"Rule 11.1: 不得进行指针和整数类型之间的转换",
				],
			},
			{
				name: "内存与资源",
				rules: [
					"Rule 17.6: 不得使用 malloc 族的动态内存分配",
					"Rule 21.3: 不得使用标准库的内存管理函数",
				],
			},
			{
				name: "控制流",
				rules: [
					"Rule 14.4: if/else if/else 后必须有 else 分支",
					"Rule 15.1: goto 语句不得使用",
					"Rule 16.3: switch 语句必须有 default 分支",
				],
			},
		],
		scenarios: ["航空电子", "汽车电子", "医疗设备", "工业控制"],
		references: [
			"MISRA-C:2012 官方规范",
			"Cppcheck MISRA addon",
			"ISO 26262 (ASIL D)",
		],
	},
	{
		id: "misra-cpp-jsf",
		name: "MISRA C++ / JSF AV C++",
		version: "2023",
		description:
			"MISRA C++ 是 C++ 语言的安全编码规范，JSF AV C++ 是联合攻击战斗机项目的 C++ 编码标准。SkyForge 实现了 5 条 JSF AV C++ 红线规则。",
		categories: [
			{
				name: "类型安全",
				rules: [
					"AV Rule 4: 所有变量在声明时必须初始化",
					"AV Rule 8: 不使用原生数组，使用 std::array 或 std::vector",
				],
			},
			{
				name: "内存管理",
				rules: [
					"AV Rule 15: 使用 RAII 管理资源",
					"AV Rule 16: 不使用裸 new/delete，使用智能指针",
				],
			},
			{
				name: "异常安全",
				rules: [
					"AV Rule 39: 析构函数不得抛出异常",
					"AV Rule 42: 提供强异常安全保证",
				],
			},
		],
		scenarios: ["航空航天", "国防军工", "高可靠性嵌入式系统"],
		references: [
			"MISRA C++:2023",
			"JSF AV C++ Coding Standards",
			"AUTOSAR C++14",
		],
	},
	{
		id: "python-safety",
		name: "Python 军工安全标准",
		version: "1.0",
		description:
			"面向军工和航空领域的 Python 安全编码标准，确保 Python 代码在安全关键环境中的可靠性。SkyForge 实现了 3 条红线规则和 4 个修复器。",
		categories: [
			{
				name: "类型安全",
				rules: [
					"Rule 1: 所有函数必须添加类型注解",
					"Rule 2: 不使用 eval() 和 exec()",
				],
			},
			{
				name: "安全",
				rules: [
					"Rule 3: 不使用 pickle 进行数据序列化",
					"Rule 4: 所有输入必须经过验证和清理",
				],
			},
			{
				name: "可靠性",
				rules: [
					"Rule 5: 使用 logging 替代 print 输出",
					"Rule 6: 所有资源使用上下文管理器 (with 语句)",
				],
			},
		],
		scenarios: ["军工数据分析", "航空地面系统", "仿真测试脚本"],
		references: ["Python PEP 484 (类型提示)", "OWASP Python 安全指南"],
	},
	{
		id: "do178c",
		name: "DO-178C 合规指南",
		version: "DAL A/B/C/D",
		description:
			"DO-178C 是航空机载软件的适航审定标准，定义了软件从计划到生产的完整生命周期过程要求。SkyForge 提供工程辅助证据，不替代适航鉴定。",
		categories: [
			{
				name: "核心目标 (19 项可判定目标)",
				rules: [
					"OBJ-1 ~ OBJ-5: 需求过程（问题报告、追溯、HLR/LLR）",
					"OBJ-6 ~ OBJ-9: 设计与编码（架构、源代码、低级需求）",
					"OBJ-10 ~ OBJ-14: 验证过程（独立验证、覆盖分析）",
					"OBJ-15 ~ OBJ-19: 配置与质量（配置管理、质量保证、工具鉴定）",
				],
			},
			{
				name: "DAL 等级覆盖要求",
				rules: [
					"DAL A (灾难性): MC/DC 覆盖 + 全部 19 项目标",
					"DAL B (危险): 判定覆盖 + 19 项目标",
					"DAL C (重大): 语句覆盖 + 17 项目标",
					"DAL D (轻微): 基础验证 + 11 项目标",
				],
			},
			{
				name: "证据包内容",
				rules: [
					"PSAC (软件适航计划)",
					"SDP (软件开发计划)",
					"SVP (软件验证计划)",
					"需求追溯矩阵",
					"覆盖率分析报告",
					"MISRA 合规报告",
					"形式化验证证明",
				],
			},
		],
		scenarios: ["机载软件 DAL A/B/C/D", "民用航空适航审定", "军用航空软件合规"],
		references: [
			"RTCA DO-178C / EUROCAE ED-12C",
			"DO-330 (工具鉴定)",
			"AC 20-115D (COTS 指南)",
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
							架构与文档中心
						</h1>
						<p class="text-muted-foreground mt-1 text-sm">
							深入了解 SkyForge 六层引擎架构、12 阶段 Pipeline 与完整文档
						</p>
					</div>
				</div>
				<Button variant="outline" size="sm" @click="backToHome">
					<ArrowLeft :size="16" class="mr-2" />
					返回主页
				</Button>
			</header>

			<Tabs defaultValue="layers" class="w-full">
				<TabsList class="w-full grid grid-cols-2 sm:grid-cols-4 mb-8">
					<TabsTrigger value="layers">
						<Layers :size="16" class="mr-2" />
						六层架构
					</TabsTrigger>
					<TabsTrigger value="pipeline">
						<Gauge :size="16" class="mr-2" />
						Pipeline
					</TabsTrigger>
					<TabsTrigger value="quickstart">
						<PlayCircle :size="16" class="mr-2" />
						快速上手
					</TabsTrigger>
					<TabsTrigger value="standards">
						<ShieldCheck :size="16" class="mr-2" />
						编码标准
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
													{{ layer.nameZh }}
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
												{{ layer.responsibility }}
											</p>

											<div
												v-if="expandedLayer === layer.level"
												class="mt-4 space-y-3 pt-3 border-t border-border"
											>
												<div class="flex items-center gap-2">
													<span
														class="text-xs font-medium text-muted-foreground uppercase"
													>
														主入口
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
														关键文件
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
								12 阶段 Pipeline 流程
							</CardTitle>
							<CardDescription>
								从需求接收至证据包生成的完整流水线，串联六层架构能力
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
																{{ stage.nameZh }}
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
															Stage {{ stage.id }}/12
														</Badge>
													</div>

													<div class="mt-4 grid gap-3 sm:grid-cols-2">
														<div class="space-y-1">
															<p
																class="text-xs font-medium text-muted-foreground uppercase"
															>
																输入
															</p>
															<p class="text-sm">{{ stage.input }}</p>
														</div>
														<div class="space-y-1">
															<p
																class="text-xs font-medium text-muted-foreground uppercase"
															>
																输出
															</p>
															<p class="text-sm">
																{{ stage.output }}
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
																工具:
															</span>
															<Badge
																v-for="tool in stage.tools"
																:key="tool"
																variant="outline"
																class="text-xs"
															>
																{{ tool }}
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
										分步骤指南
									</CardTitle>
									<CardDescription>
										跟随以下 5 个步骤，快速上手 SkyForge 全流程
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
																{{ step.title }}
															</h4>
															<p
																class="text-sm text-muted-foreground mt-1.5"
															>
																{{ step.description }}
															</p>
														</div>
													</div>
													<Button
														size="sm"
														variant="ghost"
														class="mt-3 -ml-2"
														@click="navigateTo(step.route)"
													>
														{{ step.action }}
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
										一键启动命令
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
										常见问题 FAQ
									</CardTitle>
								</CardHeader>
								<CardContent class="space-y-2">
									<div
										v-for="item in faqItems"
										:key="item.q"
										class="border border-border rounded-lg overflow-hidden"
									>
										<button
											class="w-full p-3 text-left flex items-start justify-between gap-3 hover:bg-muted/50 transition-colors"
											@click="toggleFaq(faqItems.indexOf(item))"
										>
											<span class="text-sm font-medium">
												{{ item.q }}
											</span>
											<ChevronDown
												:size="16"
												class="shrink-0 text-muted-foreground transition-transform mt-0.5"
												:class="{
													'rotate-180': expandedFaq === faqItems.indexOf(item),
												}"
											/>
										</button>
										<div
											v-if="expandedFaq === faqItems.indexOf(item)"
											class="px-3 pb-3 text-sm text-muted-foreground border-t border-border pt-3"
										>
											{{ item.a }}
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
												{{ std.name }}
											</CardTitle>
											<CardDescription class="mt-1">
												版本: {{ std.version }}
											</CardDescription>
										</div>
										<Badge variant="secondary">
											{{ idx + 1 }}/{{ codingStandards.length }}
										</Badge>
									</div>
									<p class="text-sm text-muted-foreground mt-3 leading-relaxed">
										{{ std.description }}
									</p>
								</CardHeader>
								<CardContent class="space-y-5 pt-0">
									<div
										v-for="cat in std.categories"
										:key="cat.name"
									>
										<h5
											class="text-sm font-semibold text-foreground mb-2 flex items-center gap-2"
										>
											<span
												class="w-1.5 h-1.5 rounded-full bg-primary"
											></span>
											{{ cat.name }}
										</h5>
										<ul class="space-y-1.5 pl-3.5">
											<li
												v-for="(rule, ruleIdx) in cat.rules"
												:key="ruleIdx"
												class="text-sm text-muted-foreground flex items-start gap-2"
											>
												<CheckCircle2
													:size="14"
													class="text-primary mt-0.5 shrink-0"
												/>
												<span>{{ rule }}</span>
											</li>
										</ul>
									</div>

									<div class="flex flex-wrap gap-4 pt-3 border-t border-border">
										<div>
											<p
												class="text-xs font-medium text-muted-foreground uppercase mb-1.5"
											>
												适用场景
											</p>
											<div class="flex flex-wrap gap-1.5">
												<Badge
													v-for="s in std.scenarios"
													:key="s"
													variant="outline"
													class="text-xs"
												>
													{{ s }}
												</Badge>
											</div>
										</div>
										<div>
											<p
												class="text-xs font-medium text-muted-foreground uppercase mb-1.5"
											>
												参考链接
											</p>
											<ul class="space-y-0.5">
												<li
													v-for="ref in std.references"
													:key="ref"
													class="text-xs text-muted-foreground"
												>
													• {{ ref }}
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
