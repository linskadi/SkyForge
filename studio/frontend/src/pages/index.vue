<template>
  <div class="landing-bg h-screen overflow-hidden flex flex-col relative">
    <!-- 背景氛围光晕：动态浮动 -->
    <div class="pointer-events-none absolute inset-0 overflow-hidden">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
      <div class="orb orb-4"></div>
    </div>

    <div class="relative flex-1 max-w-[1600px] mx-auto w-full px-14 py-5 flex flex-col gap-4 min-h-0">
      <!-- ============ 上栏：Hero 区 ============ -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch flex-shrink-0">
        <!-- 左侧：文案区 -->
        <div class="lg:col-span-7 flex flex-col min-h-0">
          <!-- DO-178C 标签 -->
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium mb-3 self-start border border-primary/20 animate-fade-in-up stagger-1">
            <Shield class="w-3.5 h-3.5" />
            DO-178C 合规
          </div>

          <!-- 标题 -->
          <h1 class="text-5xl font-bold tracking-tight leading-[1.1] mb-3 animate-fade-in-up stagger-2">
            让 AI 写的机载代码<br />
            <span class="gradient-text animate-text-glow">通过合规审查</span>
          </h1>

          <!-- 副标题 -->
          <p class="text-base text-muted-foreground mb-4 leading-relaxed animate-fade-in-up stagger-3">
            SkyForge 是机载软件安全合规 AI 中台，通过多 Agent 协同，将数月的开发周期压缩至数小时。
          </p>

          <!-- 数据指标条 -->
          <div class="grid grid-cols-4 gap-3 mb-3">
            <div v-for="(metric, i) in metrics" :key="metric.label" class="animate-fade-in-up" :class="`stagger-${i + 3}`">
              <div class="text-2xl font-bold gradient-text leading-none tabular-nums">{{ metric.displayValue }}</div>
              <div class="text-[11px] text-muted-foreground mt-1.5">{{ metric.label }}</div>
              <div class="mt-1.5 h-1 rounded-full bg-muted overflow-hidden">
                <div class="h-full gradient-bg animate-bar-fill" :style="{ width: metric.barWidth, animationDelay: `${0.4 + i * 0.15}s` }"></div>
              </div>
            </div>
          </div>

          <!-- 效率对比 -->
          <div class="rounded-xl border border-border bg-card p-4 shadow-sm mb-3 animate-fade-in-up stagger-6">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <BarChart3 class="w-3.5 h-3.5" />
                效率对比
              </div>
              <div class="flex items-center gap-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                <Zap class="w-3.5 h-3.5" />
                数月 → 数小时
              </div>
            </div>
            <div class="mb-2.5">
              <div class="flex items-center justify-between mb-1">
                <span class="text-[11px] text-muted-foreground">传统开发</span>
                <span class="text-[11px] text-muted-foreground">~6 个月</span>
              </div>
              <div class="h-2 rounded-full bg-muted overflow-hidden">
                <div class="h-full rounded-full bg-gradient-to-r from-slate-400 to-slate-500 dark:from-slate-600 dark:to-slate-500 animate-bar-fill" style="width: 100%; animation-delay: 0.6s"></div>
              </div>
            </div>
            <div>
              <div class="flex items-center justify-between mb-1">
                <span class="text-[11px] font-medium text-primary">SkyForge</span>
                <span class="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">~8 小时</span>
              </div>
              <div class="h-2 rounded-full bg-muted overflow-hidden">
                <div class="h-full rounded-full gradient-bg animate-bar-fill" style="width: 8%; animation-delay: 0.8s"></div>
              </div>
            </div>
          </div>

          <!-- 特性标签条 -->
          <div class="flex flex-wrap gap-2 mt-3">
            <span v-for="(tag, i) in tags" :key="tag.label" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-muted/50 text-xs font-medium border border-border/60 animate-fade-in-up" :class="`stagger-${i + 5}`">
              <component :is="tag.icon" class="w-3.5 h-3.5" :class="tag.color" />
              {{ tag.label }}
            </span>
          </div>
        </div>

        <!-- 右侧：Agent 流程卡片 -->
        <div class="lg:col-span-5 relative min-h-0 flex animate-fade-in-right stagger-3">
          <div class="absolute inset-0 bg-primary/5 rounded-2xl blur-3xl animate-glow-pulse"></div>
          <div class="relative hero-visual rounded-2xl p-4 border border-border shadow-xl shadow-primary/5 w-full flex flex-col">
            <div class="flex items-center justify-between mb-2.5 flex-shrink-0">
              <div class="flex items-center gap-2">
                <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
                <span class="text-xs font-medium text-muted-foreground">Agent 流水线</span>
              </div>
              <span class="text-[10px] font-mono text-muted-foreground/70 tracking-wider">PIPELINE</span>
            </div>

            <!-- Agent 列表 -->
            <div class="relative flex-1 min-h-0">
              <div class="pipeline-line"></div>
              <div class="h-full flex flex-col justify-between gap-2 py-0.5">
                <div v-for="(agent, i) in agents" :key="agent.name" class="relative flex items-center gap-3 agent-row animate-fade-in-left" :class="`stagger-${i + 4}`">
                  <div class="relative z-10 flex-shrink-0 w-10 h-10 rounded-xl gradient-bg flex items-center justify-center shadow-md shadow-primary/20 agent-icon-wrap">
                    <component :is="agent.icon" class="w-4 h-4 text-white" />
                    <span class="absolute -top-1.5 -left-1.5 px-1 h-4 min-w-4 rounded-full bg-card border border-border text-[8px] font-mono font-bold flex items-center justify-center text-primary">{{ agent.num }}</span>
                  </div>
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-semibold">{{ agent.name }}</p>
                    <p class="text-xs text-muted-foreground">{{ agent.desc }}</p>
                  </div>
                  <div class="flex items-center gap-1 text-[10px] font-medium text-emerald-600 dark:text-emerald-400">
                    <Check class="w-3 h-3" />
                    就绪
                  </div>
                </div>
              </div>
            </div>

            <!-- CTA 按钮 -->
            <div class="mt-2.5 flex items-center gap-3 flex-shrink-0">
              <router-link
                to="/generate"
                class="cta-primary flex flex-1 items-center justify-center gap-1.5 py-2.5 px-5 rounded-xl gradient-bg text-white text-sm font-medium transition-all"
              >
                生成代码
                <ArrowRight class="w-3.5 h-3.5" />
              </router-link>
              <router-link
                to="/compose"
                class="cta-secondary flex flex-1 py-2.5 px-5 rounded-xl border border-border bg-card text-card-foreground text-sm font-medium transition-all"
              >
                组合验证
              </router-link>
            </div>
          </div>
        </div>
      </div>

      <!-- ============ 下栏：Bento Grid ============ -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 flex-1 min-h-0 items-stretch">
        <div v-for="(card, i) in bentoCards" :key="card.title" class="bento-card p-4 flex flex-col animate-fade-in-up" :class="[card.bgClass, `stagger-${i + 5}`]">
          <div class="flex items-center justify-between mb-3">
            <div class="w-11 h-11 rounded-2xl flex items-center justify-center shadow-md" :class="card.iconBg">
              <component :is="card.icon" class="w-5 h-5 text-white" />
            </div>
            <span class="text-[10px] font-mono" :class="card.tagColor">{{ card.tag }}</span>
          </div>
          <h3 class="font-semibold text-base mb-1">{{ card.title }}</h3>
          <p class="text-xs text-muted-foreground leading-relaxed mb-3">{{ card.desc }}</p>

          <!-- 中部内容 -->
          <div class="flex-1 py-3 border-y mb-3" :class="card.borderClass">
            <!-- 指标型 -->
            <div v-if="card.metrics" class="grid gap-2" :class="`grid-cols-${card.metrics.length}`">
              <div v-for="m in card.metrics" :key="m.label">
                <div class="text-base font-bold leading-none" :class="card.valueColor">{{ m.value }}</div>
                <div class="text-[10px] text-muted-foreground mt-1">{{ m.label }}</div>
              </div>
            </div>
            <!-- 列表型 -->
            <ul v-else-if="card.list" class="grid grid-cols-2 gap-2">
              <li v-for="item in card.list" :key="item" class="flex items-center gap-1.5 text-[11px] text-foreground/80">
                <span class="w-1.5 h-1.5 rounded-full" :class="card.dotColor"></span> {{ item }}
              </li>
            </ul>
            <!-- 标签型 -->
            <div v-else-if="card.chips" class="flex flex-wrap gap-1.5">
              <span v-for="chip in card.chips" :key="chip" class="px-1.5 py-0.5 rounded text-[10px] font-medium" :class="card.chipClass">{{ chip }}</span>
            </div>
            <!-- 链型 -->
            <div v-else-if="card.chain" class="flex items-center gap-1.5 flex-wrap">
              <span v-for="(step, si) in card.chain" :key="step" class="flex items-center gap-1.5">
                <span class="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold" :class="card.chipClass">{{ step }}</span>
                <ArrowRight v-if="si < card.chain.length - 1" class="w-3 h-3" :class="card.arrowColor" />
              </span>
              <Check class="w-3.5 h-3.5 text-emerald-500 ml-1" />
            </div>
          </div>

          <!-- 底部 -->
          <div class="flex items-center justify-between mt-auto">
            <span class="text-[11px] text-muted-foreground">{{ card.bottomLabel }}</span>
            <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-bold" :class="card.badgeClass">
              <component :is="card.badgeIcon" class="w-3 h-3" /> {{ card.bottomValue }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
	ArrowRight,
	BarChart3,
	Check,
	CheckCircle,
	Code,
	Cpu,
	FileText,
	GitBranch,
	Layers,
	Shield,
	Sparkles,
	Zap,
} from "lucide-vue-next";

const metrics = [
	{ value: 233, displayValue: "233", label: "测试全通过", barWidth: "100%" },
	{ value: 26, displayValue: "26", label: "API 端点", barWidth: "78%" },
	{ value: 4, displayValue: "4", label: "Agent 协同", barWidth: "60%" },
	{ value: 98.5, displayValue: "98.5%", label: "合规率", barWidth: "98.5%" },
];

const tags = [
	{ icon: Shield, label: "本地部署", color: "text-primary" },
	{ icon: Zap, label: "实时编译", color: "text-amber-500" },
	{ icon: GitBranch, label: "双向追溯", color: "text-cyan-500" },
	{ icon: BarChart3, label: "可视化报告", color: "text-violet-500" },
];

const agents = [
	{ num: "01", name: "需求解析 Agent", desc: "结构化需求分析", icon: Shield },
	{ num: "02", name: "契约生成 Agent", desc: "接口契约定义", icon: FileText },
	{ num: "03", name: "代码生成 Agent", desc: "生成合规 C 代码", icon: Code },
	{ num: "04", name: "数字孪生 Agent", desc: "故障注入验证", icon: Cpu },
];

const bentoCards = [
	{
		title: "安全合规",
		desc: "DO-178C / MISRA-C 自动审查，逐条规则静态核验。",
		icon: Shield,
		tag: "COMPLIANCE",
		bgClass:
			"bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200/70 dark:border-emerald-800/40 hover:shadow-xl hover:shadow-emerald-500/15",
		iconBg:
			"bg-gradient-to-br from-emerald-500 to-emerald-600 shadow-emerald-500/25",
		tagColor: "text-emerald-600/70 dark:text-emerald-400/70",
		borderClass: "border-emerald-200/50 dark:border-emerald-800/40",
		valueColor: "text-emerald-600 dark:text-emerald-400",
		metrics: [
			{ value: "200+", label: "规则条款" },
			{ value: "100%", label: "覆盖" },
			{ value: "0", label: "漏报" },
		],
		bottomLabel: "",
		badgeClass: "",
		badgeIcon: null,
		bottomValue: "",
	},
	{
		title: "多 Agent 协同",
		desc: "需求→契约→代码→验证全链路自动化。",
		icon: Sparkles,
		tag: "AGENTS",
		bgClass:
			"bg-violet-50 dark:bg-violet-950/30 border border-violet-200/70 dark:border-violet-800/40 hover:shadow-xl hover:shadow-violet-500/15",
		iconBg:
			"bg-gradient-to-br from-violet-500 to-violet-600 shadow-violet-500/25",
		tagColor: "text-violet-600/70 dark:text-violet-400/70",
		borderClass: "border-violet-200/50 dark:border-violet-800/40",
		dotColor: "bg-violet-500",
		list: ["需求解析", "契约生成", "代码生成", "数字孪生"],
		bottomLabel: "协同效率",
		badgeClass:
			"bg-violet-100 dark:bg-violet-900/50 text-violet-700 dark:text-violet-300",
		badgeIcon: Zap,
		bottomValue: "+300%",
	},
	{
		title: "数字孪生",
		desc: "故障注入 + GCC 沙箱仿真验证。",
		icon: Layers,
		tag: "TWIN",
		bgClass:
			"bg-amber-50 dark:bg-amber-950/30 border border-amber-200/70 dark:border-amber-800/40 hover:shadow-xl hover:shadow-amber-500/15",
		iconBg: "bg-gradient-to-br from-amber-500 to-amber-600 shadow-amber-500/25",
		tagColor: "text-amber-600/70 dark:text-amber-400/70",
		borderClass: "border-amber-200/50 dark:border-amber-800/40",
		chipClass:
			"bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300",
		chips: ["漂移", "噪声", "丢包", "硬件", "时序", "电压"],
		bottomLabel: "故障模式",
		badgeClass:
			"bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300",
		badgeIcon: Layers,
		bottomValue: "16 种",
	},
	{
		title: "全链路追溯",
		desc: "需求↔代码↔测试双向追溯。",
		icon: GitBranch,
		tag: "TRACE",
		bgClass:
			"bg-cyan-50 dark:bg-cyan-950/30 border border-cyan-200/70 dark:border-cyan-800/40 hover:shadow-xl hover:shadow-cyan-500/15",
		iconBg: "bg-gradient-to-br from-cyan-500 to-cyan-600 shadow-cyan-500/25",
		tagColor: "text-cyan-600/70 dark:text-cyan-400/70",
		borderClass: "border-cyan-200/50 dark:border-cyan-800/40",
		chipClass:
			"bg-cyan-100 dark:bg-cyan-900/50 text-cyan-700 dark:text-cyan-300",
		arrowColor: "text-cyan-400",
		chain: ["REQ", "CON", "CODE", "TST"],
		bottomLabel: "可追溯率",
		badgeClass:
			"bg-cyan-100 dark:bg-cyan-900/50 text-cyan-700 dark:text-cyan-300",
		badgeIcon: CheckCircle,
		bottomValue: "100%",
	},
];
</script>

<style scoped>
.landing-bg {
  background-color: hsl(220, 14%, 96%);
  background-image:
    linear-gradient(rgba(34, 102, 184, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 102, 184, 0.03) 1px, transparent 1px);
  background-size: 64px 64px;
}

.dark .landing-bg {
  background-color: hsl(220, 25%, 7%);
  background-image:
    linear-gradient(rgba(34, 102, 184, 0.02) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 102, 184, 0.02) 1px, transparent 1px);
}

/* 动态光晕 */
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.12;
  animation: floatOrb 12s ease-in-out infinite;
}
.orb-1 {
  width: 520px; height: 520px; top: -120px; left: -120px;
  background: hsl(215, 80%, 50%);
  animation-delay: 0s;
}
.orb-2 {
  width: 420px; height: 420px; top: -80px; right: 25%;
  background: hsl(270, 70%, 60%);
  animation-delay: -3s;
}
.orb-3 {
  width: 440px; height: 440px; bottom: 0; left: 33%;
  background: hsl(160, 70%, 45%);
  animation-delay: -6s;
}
.orb-4 {
  width: 360px; height: 360px; bottom: 25%; right: 40px;
  background: hsl(38, 80%, 50%);
  animation-delay: -9s;
}

@keyframes floatOrb {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(20px, -15px) scale(1.05); }
  66% { transform: translate(-15px, 10px) scale(0.95); }
}

/* 渐变文字 */
.gradient-text {
  background: linear-gradient(135deg, hsl(215, 80%, 45%), hsl(200, 85%, 55%));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.gradient-bg {
  background: linear-gradient(135deg, hsl(215, 80%, 45%), hsl(200, 85%, 55%));
}

/* Bento 卡片 */
.bento-card {
  border-radius: 16px;
  transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

.bento-card:hover {
  transform: translateY(-4px) scale(1.01);
}

/* Hero 视觉区 */
.hero-visual {
  background: hsl(0, 0%, 100%);
}

.dark .hero-visual {
  background: hsl(220, 20%, 11%);
}

/* 流水线连接线 */
.pipeline-line {
  position: absolute;
  left: 20px;
  top: 16px;
  bottom: 16px;
  width: 1px;
  background: linear-gradient(to bottom, hsl(215, 80%, 50%, 0.4), hsl(270, 70%, 60%, 0.5), hsl(38, 80%, 50%, 0.5));
}

/* Agent 图标发光 */
.agent-icon-wrap {
  transition: box-shadow 0.3s ease;
}
.agent-row:hover .agent-icon-wrap {
  box-shadow: 0 0 16px hsla(215, 80%, 50%, 0.4);
}

/* CTA 按钮 */
.cta-primary {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.cta-primary:hover {
  opacity: 0.9;
  box-shadow: 0 4px 20px hsla(215, 80%, 50%, 0.35);
  transform: translateY(-1px);
}

.cta-secondary {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.cta-secondary:hover {
  background: hsl(var(--accent));
  color: hsl(var(--accent-foreground));
  border-color: hsl(var(--accent));
  transform: translateY(-1px);
}

/* 响应式 */
@media (max-width: 768px) {
  .landing-bg {
    height: auto;
    min-height: 100vh;
    overflow: auto;
  }
}
</style>
