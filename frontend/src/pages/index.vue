<template>
  <div class="landing-bg min-h-screen">
    <!-- Hero: 左对齐分割布局 -->
    <div class="max-w-7xl mx-auto px-6 pt-24 pb-16">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
        <!-- 左侧：文案 -->
        <div>
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium mb-6">
            <Shield class="w-3.5 h-3.5" />
            DO-178C 合规
          </div>
          <h1 class="text-4xl lg:text-5xl font-bold tracking-tight mb-4">
            让 AI 写的机载代码<br>
            <span class="gradient-text">通过合规审查</span>
          </h1>
          <p class="text-lg text-muted-foreground mb-8 max-w-lg">
            SkyForge 是机载软件安全合规 AI 中台，通过多 Agent 协同，将数月的开发周期压缩至数小时。
          </p>
          <div class="flex items-center gap-4">
            <button
              @click="router.push('/generate')"
              class="px-6 py-3 rounded-xl gradient-bg text-white font-medium hover:opacity-90 transition-opacity"
            >
              立即体验
            </button>
            <button
              @click="router.push('/compose')"
              class="px-6 py-3 rounded-xl border border-border bg-card text-card-foreground font-medium hover:bg-accent transition-colors"
            >
              了解更多
            </button>
          </div>
        </div>
        <!-- 右侧：视觉元素 -->
        <div class="relative">
          <div class="absolute inset-0 gradient-bg/5 rounded-3xl blur-3xl"></div>
          <div class="relative hero-visual rounded-3xl p-8 border border-border">
            <div class="space-y-4">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl gradient-bg flex items-center justify-center">
                  <Shield class="w-5 h-5 text-white" />
                </div>
                <div>
                  <p class="text-sm font-medium">需求解析 Agent</p>
                  <p class="text-xs text-muted-foreground">结构化需求分析</p>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-emerald-600 flex items-center justify-center">
                  <Code class="w-5 h-5 text-white" />
                </div>
                <div>
                  <p class="text-sm font-medium">代码生成 Agent</p>
                  <p class="text-xs text-muted-foreground">生成合规 C 代码</p>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-violet-600 flex items-center justify-center">
                  <Cpu class="w-5 h-5 text-white" />
                </div>
                <div>
                  <p class="text-sm font-medium">数字孪生 Agent</p>
                  <p class="text-xs text-muted-foreground">故障注入验证</p>
                </div>
              </div>
            </div>
            <div class="mt-6 pt-6 border-t border-border">
              <div class="flex items-center justify-between text-sm">
                <span class="text-muted-foreground">合规检查进度</span>
                <span class="font-medium text-emerald-600">98.5%</span>
              </div>
              <div class="mt-2 w-full h-2 bg-muted rounded-full overflow-hidden">
                <div class="h-full gradient-bg rounded-full" style="width: 98.5%"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 核心能力: 不对称 Bento Grid -->
    <div class="max-w-7xl mx-auto px-6 pb-16">
      <div class="mb-8">
        <h2 class="text-2xl font-bold">核心能力</h2>
        <p class="text-muted-foreground mt-1">从需求到代码，全流程自动化合规验证</p>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <!-- 主卡片：安全合规 -->
        <div class="md:col-span-2 bento-card p-8">
          <div class="flex items-start gap-4 mb-6">
            <div class="w-12 h-12 rounded-2xl gradient-bg flex items-center justify-center flex-shrink-0">
              <Shield class="w-6 h-6 text-white" />
            </div>
            <div>
              <h3 class="text-xl font-semibold mb-1">安全合规</h3>
              <p class="text-muted-foreground">AI 生成代码自动通过 DO-178C/MISRA-C 合规审查</p>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="p-4 rounded-xl bg-muted/50">
              <p class="text-2xl font-bold text-primary">DO-178C</p>
              <p class="text-sm text-muted-foreground mt-1">航空软件适航标准</p>
            </div>
            <div class="p-4 rounded-xl bg-muted/50">
              <p class="text-2xl font-bold text-primary">MISRA-C</p>
              <p class="text-sm text-muted-foreground mt-1">安全编程规范</p>
            </div>
          </div>
        </div>

        <!-- 小卡片：技术栈 -->
        <div class="bento-card p-6">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-xl bg-cyan-600 flex items-center justify-center">
              <CheckCircle class="w-5 h-5 text-white" />
            </div>
            <h3 class="font-semibold">技术栈</h3>
          </div>
          <div class="flex flex-wrap gap-2">
            <span v-for="item in techs" :key="item"
              class="px-3 py-1 bg-muted rounded-lg text-xs font-medium">{{ item }}</span>
          </div>
        </div>

        <!-- 小卡片：多 Agent -->
        <div class="bento-card p-6">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-xl bg-violet-600 flex items-center justify-center">
              <Cpu class="w-5 h-5 text-white" />
            </div>
            <h3 class="font-semibold">多 Agent 系统</h3>
          </div>
          <div class="space-y-3">
            <div v-for="item in agents" :key="item.role" class="p-3 rounded-lg bg-muted/50">
              <p class="text-sm font-medium">{{ item.role }}</p>
              <p class="text-xs text-muted-foreground">{{ item.desc }}</p>
            </div>
          </div>
        </div>

        <!-- 中卡片：支持标准 -->
        <div class="md:col-span-2 bento-card p-6">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-xl bg-amber-600 flex items-center justify-center">
              <Calendar class="w-5 h-5 text-white" />
            </div>
            <h3 class="font-semibold">支持标准</h3>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div v-for="item in standards" :key="item" class="flex items-center gap-2 text-sm">
              <Check class="w-4 h-4 text-primary flex-shrink-0" />
              <span>{{ item }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 效率对比 + CTA: 分割布局 -->
    <div class="max-w-7xl mx-auto px-6 pb-16">
      <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <!-- 效率对比：占 3 列 -->
        <div class="lg:col-span-3 bento-card p-8">
          <div class="flex items-center gap-3 mb-6">
            <div class="w-10 h-10 rounded-xl gradient-bg flex items-center justify-center">
              <BarChart2 class="w-5 h-5 text-white" />
            </div>
            <h3 class="text-lg font-semibold">效率提升</h3>
          </div>
          <div class="space-y-6">
            <div>
              <div class="flex justify-between mb-2">
                <span class="text-sm font-medium">传统开发</span>
                <span class="text-sm text-muted-foreground">数月</span>
              </div>
              <div class="w-full bg-muted rounded-full h-3">
                <div class="bg-muted-foreground h-3 rounded-full" style="width: 100%"></div>
              </div>
            </div>
            <div>
              <div class="flex justify-between mb-2">
                <span class="text-sm font-medium">SkyForge</span>
                <span class="text-sm text-primary font-medium">数小时</span>
              </div>
              <div class="w-full bg-muted rounded-full h-3">
                <div class="gradient-bg h-3 rounded-full" style="width: 8%"></div>
              </div>
            </div>
          </div>
          <p class="mt-6 text-sm text-muted-foreground">
            通过多 Agent 协同和自动化验证，将传统的数月开发周期压缩至数小时。
          </p>
        </div>

        <!-- CTA: 占 2 列 -->
        <div class="lg:col-span-2 bento-card cta-card p-8 flex flex-col justify-between">
          <div>
            <h3 class="text-xl font-semibold text-white mb-2">开始使用</h3>
            <p class="text-white/70 mb-6">体验 AI 驱动的机载软件开发</p>
            <div class="space-y-3">
              <button
                @click="router.push('/generate')"
                class="w-full py-3 px-6 rounded-xl bg-white text-foreground font-medium hover:bg-white/90 transition-colors"
              >
                生成代码
              </button>
              <button
                @click="router.push('/compose')"
                class="w-full py-3 px-6 rounded-xl border border-white/20 text-white font-medium hover:bg-white/10 transition-colors"
              >
                组合验证
              </button>
            </div>
          </div>
          <div class="mt-8 pt-6 border-t border-white/10">
            <div class="flex items-center gap-4 text-sm text-white/60">
              <div class="flex items-center gap-1">
                <Check class="w-4 h-4" />
                <span>本地部署</span>
              </div>
              <div class="flex items-center gap-1">
                <Check class="w-4 h-4" />
                <span>数据安全</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="max-w-7xl mx-auto px-6 pb-12">
      <div class="bento-card p-8">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div>
            <h4 class="font-semibold mb-3 gradient-text">关于我们</h4>
            <p class="text-sm text-muted-foreground leading-relaxed">
              机载软件安全合规 AI 中台，专注于 AI 生成代码的安全合规验证。
            </p>
          </div>
          <div>
            <h4 class="font-semibold mb-3 gradient-text">核心功能</h4>
            <p class="text-sm text-muted-foreground leading-relaxed">
              多 Agent 协同、契约式设计、MISRA-C 检查、数字孪生仿真。
            </p>
          </div>
          <div>
            <h4 class="font-semibold mb-3 gradient-text">技术优势</h4>
            <p class="text-sm text-muted-foreground leading-relaxed">
              本地化部署、数据安全、DO-178C 合规、故障注入验证。
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
	BarChart2,
	Calendar,
	Check,
	CheckCircle,
	Code,
	Cpu,
	Shield,
} from "lucide-vue-next";

import { useRouter } from "vue-router";

const router = useRouter();

const agents = [
	{ role: "需求解析 Agent", desc: "结构化需求分析" },
	{ role: "代码生成 Agent", desc: "生成合规 C 代码" },
	{ role: "数字孪生 Agent", desc: "故障注入验证" },
];

const techs = [
	"Python",
	"FastAPI",
	"Vue3",
	"Qwen LLM",
	"GCC",
	"Cppcheck",
	"ECharts",
];

const standards = [
	"DO-178C 航空软件适航标准",
	"MISRA-C:2012 安全编程规范",
	"DAL-A~E 安全等级",
	"ARINC 429 航空总线标准",
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

.gradient-text {
  background: linear-gradient(135deg, hsl(220, 70%, 45%), hsl(215, 80%, 55%));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.gradient-bg {
  background: linear-gradient(135deg, hsl(220, 70%, 45%), hsl(215, 80%, 55%));
}

.bento-card {
  border-radius: 20px;
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  background: hsl(0, 0%, 100%);
  border: 1px solid hsl(220, 13%, 90%);
}

.dark .bento-card {
  background: hsl(220, 20%, 11%);
  border-color: hsl(220, 18%, 16%);
}

.bento-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 40px -8px hsla(220, 70%, 45%, 0.12);
}

.dark .bento-card:hover {
  box-shadow: 0 12px 40px -8px hsla(210, 80%, 55%, 0.12);
}

.hero-visual {
  background: hsl(0, 0%, 100%);
}

.dark .hero-visual {
  background: hsl(220, 20%, 11%);
}

.cta-card {
  background: linear-gradient(135deg, hsl(220, 70%, 40%), hsl(215, 80%, 50%));
  border: none;
}

.cta-card:hover {
  background: linear-gradient(135deg, hsl(220, 70%, 45%), hsl(215, 80%, 55%));
}
</style>
