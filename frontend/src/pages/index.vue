<template>
  <div class="container mx-auto px-4 py-12 max-w-7xl bg-slate-50">
    <!-- Header -->
    <div class="text-center mb-10">
      <h1 class="text-5xl font-custom-bold mb-4">
        <span class="gradient-text">SkyForge (天锻)</span>
      </h1>
      <p class="text-xl text-gray-600 max-w-3xl mx-auto">
        机载软件安全合规 AI 中台 - 让 AI 写的机载代码通过 DO-178C 合规审查
      </p>
    </div>

    <!-- Bento Grid -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
      <!-- Main Card -->
      <div class="bento-card bg-white p-8 shadow-md md:col-span-2 md:row-span-2">
        <h2 class="text-2xl font-semibold mb-4 text-b">核心能力</h2>
        <div class="space-y-6">
          <div class="flex items-start" v-for="(item, idx) in mainPoints" :key="idx">
            <div class="flex-shrink-0 mr-4">
              <div class="w-12 h-12 rounded-full gradient-bg flex items-center justify-center">
                <component :is="item.icon" class="w-6 h-6 text-white" />
              </div>
            </div>
            <div>
              <h3 class="text-xl font-semibold mb-1">{{ item.title }}</h3>
              <p class="text-gray-600">{{ item.desc }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Features Card -->
      <div class="bento-card bg-white p-6 shadow-md md:col-span-2">
        <div class="flex items-center mb-4">
          <Sparkles class="w-6 h-6 text-light-purple mr-2" />
          <h2 class="text-xl font-semibold">功能特性</h2>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div class="flex items-start" v-for="(item, idx) in coreFeatures" :key="idx">
            <component :is="item.icon" class="w-5 h-5 text-deep-purple mr-2 mt-0.5" />
            <p class="text-sm text-gray-600">{{ item.text }}</p>
          </div>
        </div>
      </div>

      <!-- Agents Card -->
      <div class="bento-card bg-white p-6 shadow-md">
        <div class="flex items-center mb-4">
          <Cpu class="w-6 h-6 text-light-purple mr-2" />
          <h2 class="text-xl font-semibold">多 Agent 系统</h2>
        </div>
        <div class="flex flex-col space-y-3">
          <div class="bg-gray-50 p-2 rounded-lg" v-for="(item, idx) in agents" :key="idx">
            <p class="text-sm font-medium">{{ item.role }}</p>
            <p class="text-xs text-gray-500">{{ item.desc }}</p>
          </div>
        </div>
      </div>

      <!-- Tech Card -->
      <div class="bento-card bg-white p-6 shadow-md">
        <div class="flex items-center mb-4">
          <CheckCircle class="w-6 h-6 text-light-purple mr-2" />
          <h2 class="text-xl font-semibold">技术栈</h2>
        </div>
        <div class="flex flex-wrap gap-2">
          <span v-for="(item, idx) in techs" :key="idx"
            class="px-3 py-1 bg-gray-100 rounded-full text-xs font-medium">{{ item }}</span>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
      <!-- Efficiency Card -->
      <div class="bento-card bg-white p-6 shadow-md">
        <div class="flex items-center mb-4">
          <BarChart2 class="w-6 h-6 text-light-purple mr-2" />
          <h2 class="text-xl font-semibold">效率提升</h2>
        </div>
        <div class="space-y-4">
          <div>
            <div class="flex justify-between mb-1">
              <span class="text-sm font-medium">传统开发</span>
              <span class="text-sm font-medium">数月</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-2.5">
              <div class="bg-gray-400 h-2.5 rounded-full" style="width: 100%"></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between mb-1">
              <span class="text-sm font-medium">SkyForge</span>
              <span class="text-sm font-medium">数小时</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-2.5">
              <div class="gradient-bg h-2.5 rounded-full" style="width: 5%"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Standards Card -->
      <div class="bento-card bg-white p-6 shadow-md">
        <div class="flex items-center mb-4">
          <Calendar class="w-6 h-6 text-light-purple mr-2" />
          <h2 class="text-xl font-semibold">支持标准</h2>
        </div>
        <ul class="space-y-2 text-sm text-gray-600">
          <li class="flex items-start" v-for="(item, idx) in standards" :key="idx">
            <Check class="w-4 h-4 text-deep-purple mr-2 mt-0.5" />
            <span>{{ item }}</span>
          </li>
        </ul>
      </div>

      <!-- CTA Card -->
      <div class="bento-card bg-gray-900 p-6 shadow-md text-white">
        <h2 class="text-xl font-semibold mb-4">开始使用</h2>
        <p class="text-gray-300 mb-6">体验 AI 驱动的机载软件开发</p>
        <button class="w-full py-3 px-6 rounded-lg gradient-bg font-medium hover:opacity-90 transition-opacity"
          @click="router.push('/generate')">
          立即体验
        </button>
      </div>
    </div>

    <!-- Footer -->
    <div class="bento-card bg-white p-6 shadow-md">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div>
          <h3 class="text-lg font-semibold mb-2 gradient-text">关于我们</h3>
          <p class="text-sm text-gray-600">
            机载软件安全合规 AI 中台，专注于 AI 生成代码的安全合规验证。
          </p>
        </div>
        <div>
          <h3 class="text-lg font-semibold mb-2 gradient-text">核心功能</h3>
          <p class="text-sm text-gray-600">
            多 Agent 协同、契约式设计、MISRA-C 检查、数字孪生仿真。
          </p>
        </div>
        <div>
          <h3 class="text-lg font-semibold mb-2 gradient-text">技术优势</h3>
          <p class="text-sm text-gray-600">
            本地化部署、数据安全、DO-178C 合规、故障注入验证。
          </p>
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
	Search,
	Shield,
	Sparkles,
} from "lucide-vue-next";

import { useRouter } from "vue-router";

const router = useRouter();

const mainPoints = [
	{
		icon: Shield,
		title: "安全合规",
		desc: "AI 生成代码自动通过 DO-178C/MISRA-C 合规审查",
	},
	{
		icon: Code,
		title: "代码生成",
		desc: "多 Agent 协同生成符合航空标准的 C 代码",
	},
	{
		icon: Cpu,
		title: "数字孪生",
		desc: "虚拟环境故障注入验证，无需真实硬件",
	},
];

const coreFeatures = [
	{ icon: Search, text: "自然语言需求输入" },
	{ icon: Code, text: "MISRA-C 合规检查" },
	{ icon: Shield, text: "契约式设计验证" },
	{ icon: Cpu, text: "数字孪生仿真" },
];

const agents = [
	{ role: "需求解析 Agent", desc: "结构化需求分析" },
	{ role: "代码生成 Agent", desc: "生成合规 C 代码" },
	{ role: "合规检查 Agent", desc: "MISRA-C 违规检测" },
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
.gradient-text {
  background: linear-gradient(to right, #C084FC, #7E22CE);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.gradient-bg {
  background: linear-gradient(to right, #C084FC, #7E22CE);
}

.bento-card {
  border-radius: 20px;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.bento-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}
</style>
