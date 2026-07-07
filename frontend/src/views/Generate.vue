<script setup lang="ts">
/**
 * Generate.vue - 需求输入页面（Day 2 修复闭环 + 契约校验 / Day 3 数字孪生）
 *
 * - 顶部：大文本框输入自然语言需求
 * - 中部：示例需求按钮（4 个预设需求，点击填充）
 * - 底部：生成按钮（一键全流程：生成→修复→校验→仿真）
 * - 生成中：显示 loading + AgentTerminal 组件（跨 Tab 可见）
 * - 生成完成：四 tab 切换 [生成结果] [修复历史] [契约校验] [数字孪生]
 * - 顶部右上角：高亮追溯开关按钮（Patch 3）
 *
 * Day 4+ 扩展：
 * - 顶部添加 LLMStatus 组件
 * - 添加 SCADE 上传入口（折叠面板）
 * - 在结果区添加"下载报告"按钮
 * - 如果 HIL_ENABLED，显示 HILPanel
 */
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { Loader2, Play, RotateCcw, Sparkles, ChevronDown, ChevronRight, FileCode, FileText, Copy, Check, Download, BookOpen } from "lucide-vue-next";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AgentTerminal from "@/components/AgentTerminal.vue";
import CodeViewer from "@/components/CodeViewer.vue";
import ContractViewer from "@/components/ContractViewer.vue";
import RepairTimeline from "@/components/RepairTimeline.vue";
import ContractCheckResult from "@/components/ContractCheckResult.vue";
import FaultInjectPanel from "@/components/FaultInjectPanel.vue";
import SimulationResultView from "@/components/SimulationResult.vue";
import LLMStatus from "@/components/LLMStatus.vue";
import ScadeUpload from "@/components/ScadeUpload.vue";
import HILPanel from "@/components/HILPanel.vue";
import ReportDownload from "@/components/ReportDownload.vue";
import MisraSearch from "@/components/MisraSearch.vue";
import {
  EXAMPLE_REQUIREMENTS,
  type GenerateResult,
  type ContractCondition,
  type MisraViolation,
  type SimulationResult,
  type FaultType,
  type FaultParams,
} from "@/services/mockApi";
import { getApi } from "@/services/apiSwitcher";

/** 路由实例（用于读取 query 参数，例如从 SCADE 上传跳转回来） */
const route = useRoute();

/** HIL 启用开关（可在 Generate.vue 侧边栏显示） */
const HIL_ENABLED = true;

/** 需求文本 */
const requirement = ref<string>("");

/** 状态机：idle / generating / done / error */
const status = ref<"idle" | "generating" | "done" | "error">("idle");

/** 生成结果 */
const result = ref<GenerateResult | null>(null);

/** 错误信息 */
const errorMsg = ref<string>("");

/** 高亮追溯开关（Patch 3） */
const highlightEnabled = ref<boolean>(true);

/** 当前激活的 tab：result / repair / contract / simulation / report */
const activeTab = ref<"result" | "repair" | "contract" | "simulation" | "report">("result");

/** 聚焦面板：null=三栏均显示，'code'/'contract'/'misra'=聚焦某一个 */
const focusedPanel = ref<"code" | "contract" | "misra" | null>(null);

function toggleFocus(panel: "code" | "contract" | "misra") {
  focusedPanel.value = focusedPanel.value === panel ? null : panel;
}

/** 数字孪生仿真结果（默认用 mockGenerate 返回的，故障注入后更新） */
const simResult = ref<SimulationResult | null>(null);
/** 是否正在执行故障仿真 */
const simulating = ref<boolean>(false);

/** 当前 AgentTerminal 组件引用 */
const terminalRef = ref<InstanceType<typeof AgentTerminal> | null>(null);

/** 是否展开 SCADE 上传面板 */
const scadeExpanded = ref<boolean>(false);

/** 是否展开 HIL 侧边栏 */
const hilExpanded = ref<boolean>(HIL_ENABLED);

/** 是否展开 MISRA 规则搜索面板 */
const misraExpanded = ref<boolean>(false);

/** 是否可点击生成 */
const canGenerate = computed(
  () => requirement.value.trim().length > 0 && status.value !== "generating",
);

/** 点击示例需求 */
const fillExample = (text: string) => {
  requirement.value = text;
};

/** 切换 SCADE 上传面板展开 */
const toggleScade = () => {
  scadeExpanded.value = !scadeExpanded.value;
};

/** 切换 MISRA 搜索面板展开 */
const toggleMisra = () => {
  misraExpanded.value = !misraExpanded.value;
};

/** 切换 HIL 面板展开 */
const toggleHIL = () => {
  hilExpanded.value = !hilExpanded.value;
};

/** 点击生成按钮（一键全流程：生成 + 修复 + 校验） */
const onGenerate = async () => {
  if (!canGenerate.value) return;

  status.value = "generating";
  result.value = null;
  errorMsg.value = "";
  activeTab.value = "result";

  // 启动 AgentTerminal（mock 模式自动启动）
  terminalRef.value?.start?.();

  try {
    // 通过 apiSwitcher 调用生成（mock 或真实 API）
    const res = await getApi().generate(requirement.value);
    result.value = res;
    // 初始化默认仿真结果（无故障的正常仿真）
    simResult.value = res.simulation_result;
    status.value = "done";
  } catch (err) {
    console.error("[Generate] 生成失败：", err);
    errorMsg.value = err instanceof Error ? err.message : "未知错误";
    status.value = "error";
  }
};

/** 重置 */
const onReset = () => {
  status.value = "idle";
  result.value = null;
  errorMsg.value = "";
  activeTab.value = "result";
  simResult.value = null;
  simulating.value = false;
  terminalRef.value?.stop?.();
  terminalRef.value?.clear?.();
};

/** 故障注入：通过 apiSwitcher 调用 simulate 重新仿真（支持多故障叠加） */
const onInjectFault = async (faults: { type: FaultType; params: FaultParams }[]) => {
  simulating.value = true;
  try {
    const code = result.value?.code ?? "";
    const contractYaml = result.value ? contractToYaml(result.value.contract) : "";
    // 逐个故障依次注入，最后一个的结果作为最终仿真结果
    let res;
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

/** 违规等级样式 */
const violationClass = (v: MisraViolation): string => {
  return `violation-${v.severity}`;
};

/** 类别标签颜色 */
const categoryClass = (cat: MisraViolation["category"]): string => {
  return `cat-${cat.toLowerCase()}`;
};

/** 跳转到报告 Tab */
const goToReport = () => {
  activeTab.value = "report";
};

/** 复制按钮反馈状态 */
const copiedCode = ref<boolean>(false);
const copiedContract = ref<boolean>(false);

/** 将 Contract 对象序列化为 YAML 字符串（无 js-yaml 依赖时手动转换） */
const contractToYaml = (contract: GenerateResult["contract"]): string => {
  const lines: string[] = [];
  lines.push(`component: "${contract.component}"`);
  lines.push(`description: "${contract.description}"`);
  lines.push("inputs:");
  for (const [k, v] of Object.entries(contract.inputs)) {
    lines.push(`  ${k}: ${v}`);
  }
  lines.push("outputs:");
  for (const [k, v] of Object.entries(contract.outputs)) {
    lines.push(`  ${k}: ${v}`);
  }
  const emitSection = (key: string, items: ContractCondition[]) => {
    lines.push(`${key}:`);
    for (const c of items) {
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

/** 复制文本到剪贴板（带 2s 按钮反馈） */
const copyToClipboard = async (text: string, feedback: "code" | "contract"): Promise<void> => {
  try {
    await navigator.clipboard.writeText(text);
    if (feedback === "code") {
      copiedCode.value = true;
      setTimeout(() => (copiedCode.value = false), 2000);
    } else {
      copiedContract.value = true;
      setTimeout(() => (copiedContract.value = false), 2000);
    }
  } catch (err) {
    console.error("[Generate] 复制失败：", err);
  }
};

/** 下载文本文件工具函数 */
const downloadTextFile = (filename: string, content: string, mime = "text/plain") => {
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
  const name = (result.value.contract.component || "generated").replace(/[^A-Za-z0-9_]/g, "_");
  downloadTextFile(`${name}.c`, result.value.code, "text/x-c");
};

/** 下载契约 YAML 文件 */
const onDownloadContractYaml = () => {
  if (!result.value) return;
  const name = (result.value.contract.component || "contract").replace(/[^A-Za-z0-9_]/g, "_");
  downloadTextFile(`${name}.yaml`, contractToYaml(result.value.contract), "application/x-yaml");
};

// 挂载时检查路由 query，若来自 SCADE 上传则自动填充需求
onMounted(() => {
  const query = route.query;
  if (query.requirement && typeof query.requirement === "string") {
    requirement.value = query.requirement;
  }
  if (query.from === "scade") {
    // 自动展开 SCADE 面板，让用户知道来源
    scadeExpanded.value = false;
  }
});
</script>
<template>
  <div class="generate-page">
    <header class="page-header">
      <div class="title-area">
        <h1 class="page-title">
          <Sparkles class="icon" />
          SkyForge · 代码生成
        </h1>
        <p class="subtitle">
          自然语言需求 → 契约 + C 代码 + MISRA-C 合规 + 修复闭环 + 契约校验 + 数字孪生仿真
        </p>
      </div>
    </header>

    <!-- 顶部 LLM 状态面板 -->
    <LLMStatus />

    <!-- MISRA 规则搜索入口（折叠面板） -->
    <Card class="misra-collapse-card">
      <CardHeader>
        <CardTitle class="card-title collapsible" @click="toggleMisra">
          <BookOpen class="icon" />
          MISRA-C 规则检索
          <span class="title-hint">（查询规则详情与示例代码）</span>
          <component
            :is="misraExpanded ? ChevronDown : ChevronRight"
            class="collapse-icon"
          />
        </CardTitle>
      </CardHeader>
      <CardContent v-show="misraExpanded" class="collapse-panel">
        <MisraSearch />
      </CardContent>
    </Card>

    <!-- SCADE 上传入口（折叠面板） -->
    <Card class="scade-collapse-card">
      <CardHeader>
        <CardTitle class="card-title collapsible" @click="toggleScade">
          <FileCode class="icon" />
          SCADE 模型上传
          <span class="title-hint">（从 SCADE .lus 文件解析需求与契约）</span>
          <component
            :is="scadeExpanded ? ChevronDown : ChevronRight"
            class="collapse-icon"
          />
        </CardTitle>
      </CardHeader>
      <CardContent v-show="scadeExpanded" class="collapse-panel">
        <ScadeUpload />
      </CardContent>
    </Card>

    <Card class="input-card">
      <CardHeader>
        <CardTitle class="card-title">📝 需求描述</CardTitle>
      </CardHeader>
      <CardContent>
        <textarea
          v-model="requirement"
          class="req-textarea"
          placeholder="例如：实现一个低通滤波器，截止频率 10Hz，用于滤除传感器高频噪声..."
          :disabled="status === 'generating'"
          rows="5"
        />
        <div class="examples">
          <span class="examples-label">💡 示例需求：</span>
          <button
            v-for="(ex, idx) in EXAMPLE_REQUIREMENTS"
            :key="idx"
            type="button"
            class="example-btn"
            :disabled="status === 'generating'"
            @click="fillExample(ex)"
          >{{ ex.length > 28 ? ex.slice(0, 28) + "..." : ex }}</button>
        </div>
        <div class="actions">
          <Button :disabled="!canGenerate" @click="onGenerate">
            <Loader2 v-if="status === 'generating'" class="animate-spin" />
            <Play v-else />
            一键全流程（生成→修复→校验→仿真）
          </Button>
          <Button v-if="status !== 'idle'" variant="outline" @click="onReset">
            <RotateCcw />
            重置
          </Button>
          <Button v-if="status === 'done' && result" variant="outline" @click="goToReport">
            <FileText />
            下载报告
          </Button>
          <span v-if="status === 'generating'" class="status-text generating">Agent 正在思考中...</span>
          <span v-else-if="status === 'done'" class="status-text done">✅ 生成完成</span>
          <span v-else-if="status === 'error'" class="status-text error">❌ {{ errorMsg }}</span>
        </div>
      </CardContent>
    </Card>

    <Card v-if="status !== 'idle'" class="terminal-card">
      <CardHeader>
        <CardTitle class="card-title">
          🤖 Agent 思考流
          <span class="title-hint">（实时展示 Agent 推理过程）</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div class="terminal-wrapper">
          <AgentTerminal ref="terminalRef" :use-mock="true" />
        </div>
      </CardContent>
    </Card>

    <div v-if="status === 'done' && result" class="results-section">
      <Tabs v-model="activeTab" class="result-tabs">
        <TabsList class="tabs-list">
          <TabsTrigger value="result">📦 生成结果</TabsTrigger>
          <TabsTrigger value="repair">
            🔧 修复历史
            <span class="tab-badge">{{ result.repair_history.length }}</span>
          </TabsTrigger>
          <TabsTrigger value="contract">
            📐 契约校验
            <span
              class="tab-badge"
              :class="{ pass: result.contract_check_result.overall_passed, fail: !result.contract_check_result.overall_passed }"
            >{{ result.contract_check_result.passed_count }}/{{ result.contract_check_result.total_count }}</span>
          </TabsTrigger>
          <TabsTrigger value="simulation">
            🧪 数字孪生
            <span
              v-if="simResult"
              class="tab-badge"
              :class="{ pass: simResult.passed, fail: !simResult.passed }"
            >{{ simResult.passed ? '✓' : '✗' }}</span>
          </TabsTrigger>
          <TabsTrigger value="report">
            📄 DO-178C 报告
          </TabsTrigger>
        </TabsList>

        <!-- Tab 1: 生成结果（聚焦切换模式） -->
        <TabsContent value="result">
          <div class="focus-layout">
            <!-- 横向子标签栏 -->
            <div class="focus-tabs">
              <button
                class="focus-tab-btn"
                :class="{ active: focusedPanel === 'code' }"
                @click="toggleFocus('code')"
              >
                <span class="focus-tab-icon">💻</span>
                <span class="focus-tab-label">C 代码</span>
              </button>
              <button
                class="focus-tab-btn"
                :class="{ active: focusedPanel === 'contract' }"
                @click="toggleFocus('contract')"
              >
                <span class="focus-tab-icon">📋</span>
                <span class="focus-tab-label">契约</span>
              </button>
              <button
                class="focus-tab-btn"
                :class="{ active: focusedPanel === 'misra' }"
                @click="toggleFocus('misra')"
              >
                <span class="focus-tab-icon">⚠️</span>
                <span class="focus-tab-label">MISRA</span>
                <span
                  v-if="result.violations.length > 0"
                  class="focus-tab-badge fail"
                >{{ result.violations.length }}</span>
              </button>
            </div>

            <!-- 主内容区：聚焦的面板 -->
            <div class="focus-main">
              <!-- 代码面板 -->
              <Card v-show="focusedPanel === 'code' || focusedPanel === null" class="result-card focus-card">
                <CardHeader>
                  <CardTitle class="card-title">
                    💻 C 代码
                    <span class="title-hint">（含 [REQ]/[MISRA-Rule]/[CON] 徽章）</span>
                    <div class="header-actions-inline">
                      <button
                        type="button"
                        class="action-btn"
                        :title="copiedCode ? '已复制' : '复制代码'"
                        @click="onCopyCode"
                      >
                        <Check v-if="copiedCode" class="action-icon ok" />
                        <Copy v-else class="action-icon" />
                      </button>
                      <button
                        type="button"
                        class="action-btn"
                        title="下载 C 文件"
                        @click="onDownloadCFile"
                      >
                        <Download class="action-icon" />
                      </button>
                    </div>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <CodeViewer
                    :code="result.code"
                    :traceability="result.traceability"
                    :highlight-enabled="highlightEnabled"
                  />
                </CardContent>
              </Card>

              <!-- 契约面板 -->
              <Card v-show="focusedPanel === 'contract'" class="result-card focus-card">
                <CardHeader>
                  <CardTitle class="card-title">
                    📋 契约规格
                    <span class="title-hint">（YAML，由 LLM 生成）</span>
                    <button
                      type="button"
                      class="action-btn"
                      title="下载契约 YAML"
                      @click="onDownloadContractYaml"
                    >
                      <Download class="action-icon" />
                    </button>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ContractViewer :contract="result.contract" />
                </CardContent>
              </Card>

              <!-- MISRA 面板 -->
              <Card v-show="focusedPanel === 'misra'" class="result-card focus-card">
                <CardHeader>
                  <CardTitle class="card-title">
                    ⚠ MISRA-C 校验
                    <span class="title-hint">（Cppcheck 静态扫描）</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div class="misra-summary">
                    <span class="badge error">Error ×{{ violationStats.error }}</span>
                    <span class="badge warn">Warn ×{{ violationStats.warn }}</span>
                    <span class="badge total">Total ×{{ violationStats.total }}</span>
                  </div>
                  <ul v-if="result.violations.length > 0" class="violation-list">
                    <li
                      v-for="(v, idx) in result.violations"
                      :key="idx"
                      :class="['violation-item', violationClass(v)]"
                    >
                      <div class="violation-row">
                        <span :class="['cat-tag', categoryClass(v.category)]">{{ v.category }}</span>
                        <span class="rule-tag">{{ v.rule }}</span>
                        <span class="line-tag">@L{{ v.line }}</span>
                      </div>
                      <div class="violation-msg">{{ v.message }}</div>
                    </li>
                  </ul>
                  <div v-else class="empty-tip">✅ 无 MISRA 违规</div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <!-- Tab 2: 修复历史（Patch 1 查改解耦闭环） -->
        <TabsContent value="repair">
          <Card class="result-card">
            <CardHeader>
              <CardTitle class="card-title">
                🔧 MISRA 修复闭环
                <span class="title-hint">（LLM 修复 + Cppcheck 复查，多轮迭代）</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <RepairTimeline :history="result.repair_history" />
            </CardContent>
          </Card>
        </TabsContent>

        <!-- Tab 3: 契约校验（Patch 2 契约转断言） -->
        <TabsContent value="contract">
          <Card class="result-card">
            <CardHeader>
              <CardTitle class="card-title">
                📐 契约校验结果
                <span class="title-hint">（契约 → C 断言自动映射）</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ContractCheckResult :result="result.contract_check_result" />
            </CardContent>
          </Card>
        </TabsContent>

        <!-- Tab 4: 数字孪生 -->
        <TabsContent value="simulation">
          <div class="simulation-tab">
            <FaultInjectPanel @inject="onInjectFault" />
            <Card class="result-card">
              <CardHeader>
                <CardTitle class="card-title">
                  🧪 仿真结果
                  <span class="title-hint">（数字孪生沙盒，契约断言实时校验）</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <SimulationResultView
                  v-if="simResult"
                  :result="simResult"
                  :loading="simulating"
                />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <!-- Tab 5: DO-178C 报告（Day 4+） -->
        <TabsContent value="report">
          <ReportDownload :result="result" />
        </TabsContent>
      </Tabs>
    </div>

    <!-- HIL 人机协作审批侧边栏（可折叠） -->
    <Card v-if="HIL_ENABLED" class="hil-collapse-card">
      <CardHeader>
        <CardTitle class="card-title collapsible" @click="toggleHIL">
          📋 HIL 人机协作审批
          <span class="title-hint">（人工介入审批检查点）</span>
          <component
            :is="hilExpanded ? ChevronDown : ChevronRight"
            class="collapse-icon"
          />
        </CardTitle>
      </CardHeader>
      <CardContent v-show="hilExpanded" class="collapse-panel">
        <HILPanel />
      </CardContent>
    </Card>
  </div>
</template>
<style src="@/assets/styles/generate.css"></style>