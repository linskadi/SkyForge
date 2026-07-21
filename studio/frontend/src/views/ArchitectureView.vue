<script setup lang="ts">
/**
 * 六层架构 · SkyForge Engine
 * ====================================================================
 * 比赛展示用架构总览：L0 基础设施协议 → L1 LLM 客户端 → L2 HIL 适配器
 * → L3 验证工具链 → L4 Agent 策略 → L5 编排层（依赖方向自下而上）。
 *
 * - 6 个层级卡片，垂直网格布局
 * - 卡片间箭头表示依赖方向（向下依赖）
 * - 配色：深蓝 → 浅蓝 渐变
 * - 悬停显示该层 3-5 个关键文件路径
 * - 底部"返回主页"按钮
 */

import { ArrowDown, ArrowLeft, FileCode, Layers } from "@lucide/vue";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

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
		nameZh: "HIL 适配器层",
		nameEn: "HIL Adapter",
		responsibility:
			"Hardware-in-the-Loop 与数字孪生适配，支持 QEMU、串口、ARINC653 注入。",
		entry: "digital_twin/hil_adapter.py",
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

function backToHome() {
	router.push("/");
}
</script>

<template>
  <main class="arch-page">
    <header class="arch-header" :class="{ 'animate-in': isMounted }">
      <div class="title-block">
        <span class="kicker"><Layers :size="13"/> ARCHITECTURE OVERVIEW</span>
        <h1>六层架构 · SkyForge Engine</h1>
        <p>依赖方向自上而下：编排层 <em>L5</em> 调度各层能力，最终落到 L0 协议与基础设施。</p>
      </div>
      <button class="back-btn" type="button" @click="backToHome">
        <ArrowLeft :size="15"/>返回主页
      </button>
    </header>

    <section class="arch-stack" aria-label="六层架构卡片">
      <template v-for="(layer, idx) in layers" :key="layer.level">
        <article
          class="layer-card"
          :class="{ 'animate-in': isMounted }"
          :style="{ background: layer.gradient, '--delay': `${idx * 80}ms` }"
        >
          <div class="layer-card-head">
            <span class="level-chip">
              <span class="chip-glow" aria-hidden="true"></span>
              {{ layer.level }}
            </span>
            <div class="layer-titles">
              <h2>{{ layer.nameZh }}</h2>
              <small>{{ layer.nameEn }}</small>
            </div>
            <span class="file-count" :title="`该层 ${layer.files} 个文件`">
              <FileCode :size="13"/> {{ layer.files }} files
            </span>
          </div>

          <p class="responsibility">{{ layer.responsibility }}</p>

          <div class="entry-file">
            <span>主入口</span>
            <code>skyforge_engine/{{ layer.entry }}</code>
          </div>

          <div class="key-files" :aria-label="`${layer.nameZh} 关键文件`">
            <span class="key-label">关键文件</span>
            <ul>
              <li v-for="f in layer.keyFiles" :key="f">
                <code>skyforge_engine/{{ f }}</code>
              </li>
            </ul>
          </div>

        </article>
        <div v-if="idx < layers.length - 1" class="layer-arrow-container" :class="{ 'animate-in': isMounted }" :style="{ '--delay': `${idx * 80 + 40}ms` }" aria-hidden="true">
          <div class="layer-arrow pulse">
            <ArrowDown :size="16"/>
          </div>
        </div>
      </template>
    </section>
  </main>
</template>

<style scoped>
.arch-page {
  min-height: calc(100vh - 64px);
  padding: 36px clamp(20px, 5vw, 80px) 60px;
  color: #10243a;
  background: radial-gradient(circle at 80% 8%, rgba(32, 151, 222, 0.1), transparent 28%),
    linear-gradient(135deg, #f4faff 0%, #ffffff 50%, #edf6fb 100%);
}
.arch-header {
  max-width: 1200px;
  margin: 0 auto 28px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  opacity: 0;
  transform: translateY(-12px);
  transition: opacity 0.6s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}
.arch-header.animate-in {
  opacity: 1;
  transform: translateY(0);
}
.kicker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #0d79ca;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.14em;
}
.title-block h1 {
  margin: 6px 0 6px;
  font-size: clamp(26px, 3vw, 34px);
  line-height: 1.15;
}
.title-block p {
  margin: 0;
  color: #4d6377;
  font-size: 14px;
  line-height: 1.6;
}
.title-block em {
  color: #0b6cb8;
  font-style: normal;
  font-weight: 800;
}
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 14px;
  border: 1px solid #b9cedd;
  border-radius: 8px;
  background: #fff;
  color: #153149;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: border-color 0.22s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.22s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.15s cubic-bezier(0.22, 1, 0.36, 1);
}
.back-btn:hover {
  border-color: #1687e8;
  box-shadow: 0 8px 22px rgba(22, 135, 232, 0.22);
  transform: translateY(-1px);
}
.back-btn:active {
  transform: translateY(0);
  box-shadow: 0 4px 12px rgba(22, 135, 232, 0.18);
}
.arch-stack {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.layer-card {
  position: relative;
  padding: 22px 24px 20px;
  border-radius: 14px;
  border: 2px solid #d4e4f0;
  color: #0b2137;
  box-shadow: 0 6px 20px rgba(5, 24, 49, 0.08);
  overflow: hidden;
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.6s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.6s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.3s cubic-bezier(0.22, 1, 0.36, 1);
  transition-delay: var(--delay, 0ms);
}
.layer-card.animate-in {
  opacity: 1;
  transform: translateY(0);
}
.layer-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 14px 36px rgba(5, 24, 49, 0.14),
    0 0 0 1px rgba(22, 135, 232, 0.08);
  border-color: #5aaae6;
}
.layer-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #1170b3, #1a8bdd, #63d4ff);
  border-radius: 14px 14px 0 0;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s ease;
}
.layer-card:hover::before {
  opacity: 1;
}
.layer-card-head {
  display: flex;
  align-items: center;
  gap: 14px;
}
.level-chip {
  position: relative;
  display: inline-grid;
  place-items: center;
  min-width: 44px;
  height: 44px;
  padding: 0 10px;
  border-radius: 10px;
  background: linear-gradient(135deg, #1170b3 0%, #1a8bdd 100%);
  color: #fff;
  font-size: 18px;
  font-weight: 900;
  letter-spacing: 0.04em;
  z-index: 1;
}
.chip-glow {
  position: absolute;
  inset: -4px;
  border-radius: 14px;
  background: radial-gradient(circle at center, rgba(26, 139, 221, 0.35), transparent 70%);
  filter: blur(8px);
  opacity: 0;
  transition: opacity 0.4s ease;
  z-index: -1;
}
.layer-card:hover .chip-glow {
  opacity: 1;
}
.layer-titles {
  flex: 1;
  min-width: 0;
}
.layer-titles h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: #0b2137;
  transition: color 0.3s ease;
}
.layer-card:hover .layer-titles h2 {
  color: #084f8b;
}
.layer-titles small {
  display: block;
  color: #5c7a96;
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-top: 2px;
}
.file-count {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 9px;
  border-radius: 99px;
  background: #e8f4ff;
  color: #0c5fa8;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
  transition: background 0.3s ease, transform 0.3s ease;
}
.layer-card:hover .file-count {
  background: #d6ecff;
  transform: scale(1.03);
}
.responsibility {
  margin: 12px 0 10px;
  color: #3d5369;
  font-size: 13px;
  line-height: 1.6;
}
.entry-file {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.entry-file span {
  color: #7a91a8;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.entry-file code {
  font-family: ui-monospace, "JetBrains Mono", "Fira Code", monospace;
  font-size: 12px;
  background: #f0f7ff;
  padding: 3px 8px;
  border-radius: 5px;
  color: #0c5fa8;
  word-break: break-all;
  border: 1px solid #d4e4f0;
  transition: background 0.3s ease, border-color 0.3s ease;
}
.layer-card:hover .entry-file code {
  background: #e6f2ff;
  border-color: #9dcfee;
}
.key-files {
  margin-top: 10px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.key-label {
  flex-shrink: 0;
  padding-top: 4px;
  color: #7a91a8;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.key-files ul {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 5px 7px;
}
.key-files code {
  font-family: ui-monospace, "JetBrains Mono", "Fira Code", monospace;
  font-size: 11px;
  background: #f0f7ff;
  padding: 3px 7px;
  border-radius: 5px;
  color: #0c5fa8;
  white-space: nowrap;
  border: 1px solid #d4e4f0;
  transition: all 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}
.key-files li:hover code {
  background: #dceeff;
  border-color: #7fbde8;
  transform: translateY(-1px);
}
.layer-arrow-container {
  display: flex;
  justify-content: center;
  padding: 8px 0;
  opacity: 0;
  transform: scale(0.8);
  transition: opacity 0.5s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.5s cubic-bezier(0.22, 1, 0.36, 1);
  transition-delay: var(--delay, 0ms);
}
.layer-arrow-container.animate-in {
  opacity: 1;
  transform: scale(1);
}
.layer-arrow {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #fff;
  color: #1170b3;
  box-shadow: 0 4px 12px rgba(5, 24, 49, 0.12);
  border: 1px solid #d4e4f0;
}
.layer-arrow.pulse {
  animation: arrowPulse 2.2s ease-in-out infinite;
}
@keyframes arrowPulse {
  0%, 100% {
    transform: translateY(0);
    box-shadow: 0 4px 12px rgba(5, 24, 49, 0.12),
      0 0 0 0 rgba(26, 139, 221, 0.4);
  }
  50% {
    transform: translateY(3px);
    box-shadow: 0 6px 16px rgba(5, 24, 49, 0.16),
      0 0 0 6px rgba(26, 139, 221, 0);
  }
}
@media (max-width: 720px) {
  .arch-header {
    flex-direction: column;
    align-items: flex-start;
  }
  .layer-card {
    padding: 18px 16px 16px;
  }
  .layer-card-head {
    flex-wrap: wrap;
  }
  .entry-file {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  .key-files {
    flex-direction: column;
  }
}
@media (prefers-reduced-motion: reduce) {
  .arch-header,
  .layer-card,
  .layer-arrow-container,
  .layer-card:hover,
  .layer-card:hover::before,
  .layer-card:hover .chip-glow,
  .layer-card:hover .layer-titles h2,
  .layer-card:hover .file-count,
  .layer-card:hover .entry-file code,
  .key-files li:hover code,
  .back-btn:hover,
  .back-btn:active {
    transition: none !important;
    animation: none !important;
    transform: none !important;
  }
  .arch-header,
  .layer-card,
  .layer-arrow-container {
    opacity: 1 !important;
  }
  .layer-arrow.pulse {
    animation: none !important;
  }
}
</style>
