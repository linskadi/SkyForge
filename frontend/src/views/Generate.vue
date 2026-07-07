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
import { Loader2, Play, RotateCcw, Sparkles, ChevronDown, ChevronRight, FileCode, FileText, Copy, Check, Download, BookOpen, Wifi, WifiOff } from "lucide-vue-next";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
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
import { getApi, USE_REAL_API, setUseRealAPI } from "@/services/apiSwitcher";

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

/** API 模式响应式状态（Mock / 真实 API） */
const { useRealAPI, connected } = USE_REAL_API();

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

/** 切换 API 模式（Mock ↔ 真实 API） */
const onToggleAPI = (val: boolean) => {
  setUseRealAPI(val);
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

/** 故障注入：通过 apiSwitcher 调用 simulate 重新仿真 */
const onInjectFault = async (faultType: FaultType, params: FaultParams) => {
  simulating.value = true;
  try {
    const code = result.value?.code ?? "";
    const contractYaml = result.value ? contractToYaml(result.value.contract) : "";
    const res = await getApi().simulate(code, contractYaml, faultType, params);
    simResult.value = res;
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
          AirborneAI · 代码生成
        </h1>
        <p class="subtitle">
          自然语言需求 → 契约 + C 代码 + MISRA-C 合规 + 修复闭环 + 契约校验 + 数字孪生仿真
        </p>
      </div>
      <div class="header-actions">
        <div class="switch-group api-mode-switch">
          <Switch
            :model-value="useRealAPI"
            @update:model-value="(v: boolean) => onToggleAPI(v)"
            id="api-mode-switch"
          />
          <Label for="api-mode-switch" class="switch-label">
            {{ useRealAPI ? "真实 API" : "Mock 模式" }}
          </Label>
          <span
            class="api-status-dot"
            :class="{ mock: !useRealAPI, real: useRealAPI, connected: connected, disconnected: useRealAPI && !connected }"
            :title="useRealAPI ? (connected ? '真实 API 已连接' : '真实 API 未连接') : '使用 Mock 数据'"
          >
            <component :is="useRealAPI ? (connected ? Wifi : WifiOff) : Wifi" class="api-status-icon" />
          </span>
        </div>
        <div class="switch-group">
          <Switch v-model:checked="highlightEnabled" id="highlight-switch" />
          <Label for="highlight-switch" class="switch-label">
            高亮追溯
            <span class="switch-hint">（Patch 3）</span>
          </Label>
        </div>
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
      <CardContent v-if="misraExpanded">
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
      <CardContent v-if="scadeExpanded">
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
          <span class="title-hint">（打字机效果，Patch 4 亮点）</span>
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

        <!-- Tab 1: 生成结果（三栏：契约 / 代码 / MISRA） -->
        <TabsContent value="result">
          <div class="results-grid">
            <!-- 左栏：契约 -->
            <Card class="result-card contract-card">
              <CardHeader>
                <CardTitle class="card-title">
                  📋 契约
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

            <!-- 中栏：代码 -->
            <Card class="result-card code-card">
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

            <!-- 右栏：MISRA 违规 -->
            <Card class="result-card misra-card">
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

        <!-- Tab 4: 数字孪生（Day 3 数字孪生沙盒） -->
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
      <CardContent v-if="hilExpanded">
        <HILPanel />
      </CardContent>
    </Card>
  </div>
</template>
<style scoped>
/* ===================== 页面整体布局 ===================== */
.generate-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px 32px 64px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ===================== 顶部页头 ===================== */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0 8px;
  border-bottom: 1px solid var(--border, #e4e4e7);
}

.title-area h1 {
  font-size: 22px;
  font-weight: 700;
  margin: 0;
  color: var(--foreground, #18181b);
}

.title-area h1 .accent {
  background: linear-gradient(90deg, #1e6fb8, #7c3aed);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.title-area p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--muted-foreground, #71717a);
}

.switch-group {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 8px;
  background: var(--secondary, #f4f4f5);
}

.switch-label {
  font-size: 13px;
  cursor: pointer;
  user-select: none;
}

.switch-hint {
  color: var(--muted-foreground, #a1a1aa);
  font-size: 12px;
}

/* API 模式切换按钮 + 连接状态指示灯 */
.api-mode-switch {
  border: 1px solid var(--border, #e4e4e7);
}

.api-status-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  margin-left: 4px;
  transition: all 0.2s;
}

.api-status-dot.mock {
  background: #fef3c7;
  color: #b45309;
}

.api-status-dot.real.connected {
  background: #dcfce7;
  color: #15803d;
}

.api-status-dot.real.disconnected {
  background: #fee2e2;
  color: #b91c1c;
}

.api-status-icon {
  width: 12px;
  height: 12px;
}

/* MISRA 搜索卡片 */
.misra-collapse-card {
  border-left: 3px solid #16a34a;
}

.misra-collapse-card .icon {
  width: 18px;
  height: 18px;
  color: #16a34a;
}

/* ===================== 折叠卡片 ===================== */
.scade-collapse-card,
.hil-collapse-card {
  border-left: 3px solid #0891b2;
}

.hil-collapse-card {
  border-left-color: #ea580c;
}

.scade-collapse-card :deep(.card-title),
.hil-collapse-card :deep(.card-title) {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.scade-collapse-card .icon,
.hil-collapse-card .icon {
  width: 18px;
  height: 18px;
  color: #0891b2;
}

.hil-collapse-card .icon {
  color: #ea580c;
}

.collapse-icon {
  width: 16px;
  height: 16px;
  color: var(--muted-foreground, #6b7280);
  margin-left: auto;
}

/* ===================== 输入卡片 ===================== */
.input-card :deep(.card-title),
.result-card :deep(.card-title),
.terminal-card :deep(.card-title) {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--muted-foreground, #a1a1aa);
}

.req-textarea {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--input, #e4e4e7);
  border-radius: 8px;
  font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s;
  background: var(--background, #fff);
  color: var(--foreground, #18181b);
}

.req-textarea:focus {
  border-color: #1e6fb8;
  box-shadow: 0 0 0 3px rgba(30, 111, 184, 0.15);
}

.examples {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.examples-label {
  font-size: 13px;
  color: var(--muted-foreground, #71717a);
}

.example-btn {
  padding: 4px 10px;
  font-size: 12px;
  border: 1px dashed var(--border, #d4d4d8);
  border-radius: 6px;
  background: transparent;
  color: var(--foreground, #3f3f46);
  cursor: pointer;
  transition: all 0.15s;
}

.example-btn:hover:not(:disabled) {
  border-color: #1e6fb8;
  color: #1e6fb8;
  background: rgba(30, 111, 184, 0.06);
}

.example-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}

.status-text {
  font-size: 13px;
  font-weight: 500;
}

.status-text.generating { color: #1e6fb8; }
.status-text.done { color: #15803d; }
.status-text.error { color: #dc2626; }

.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
/* ===================== 终端卡片 ===================== */
.terminal-card {
  border-left: 3px solid #1e6fb8;
}

.terminal-wrapper {
  background: #0b0f17;
  border-radius: 8px;
  padding: 12px;
  max-height: 320px;
  overflow-y: auto;
}

/* ===================== 结果区 / Tab 切换 ===================== */
.results-section {
  margin-top: 8px;
}

.result-tabs {
  width: 100%;
}

.tabs-list {
  display: inline-flex;
  gap: 4px;
  background: var(--secondary, #f4f4f5);
  padding: 4px;
  border-radius: 10px;
  margin-bottom: 16px;
}

.tab-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 18px;
  padding: 0 6px;
  margin-left: 6px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 9px;
  background: var(--muted, #e4e4e7);
  color: var(--foreground, #3f3f46);
}

.tab-badge.pass {
  background: #dcfce7;
  color: #15803d;
}

.tab-badge.fail {
  background: #fee2e2;
  color: #b91c1c;
}

/* ===================== 生成结果三栏布局 ===================== */
.results-grid {
  display: grid;
  grid-template-columns: 1fr 1.4fr 1fr;
  gap: 16px;
  align-items: start;
}

@media (max-width: 1100px) {
  .results-grid {
    grid-template-columns: 1fr;
  }
}

/* ===================== 卡片头部内联操作按钮（复制/下载） ===================== */
.header-actions-inline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--border, #d4d4d8);
  border-radius: 6px;
  background: var(--secondary, #f4f4f5);
  color: var(--foreground, #3f3f46);
  cursor: pointer;
  transition: all 0.15s;
}

.action-btn:hover {
  border-color: #1e6fb8;
  color: #1e6fb8;
  background: rgba(30, 111, 184, 0.08);
}

.action-icon {
  width: 14px;
  height: 14px;
}

.action-icon.ok {
  color: #15803d;
}

/* ===================== 移动端响应式适配 ===================== */
@media (max-width: 768px) {
  .generate-page {
    padding: 12px 12px 32px;
    gap: 12px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .title-area h1 {
    font-size: 18px;
  }

  .title-area p {
    font-size: 12px;
  }

  .actions {
    flex-wrap: wrap;
    gap: 8px;
  }

  .tabs-list {
    display: flex;
    overflow-x: auto;
    flex-wrap: nowrap;
    max-width: 100%;
    -webkit-overflow-scrolling: touch;
  }

  .terminal-wrapper {
    max-height: 220px;
  }

  .req-textarea {
    font-size: 13px;
  }
}

.result-card {
  border: 1px solid var(--border, #e4e4e7);
  border-radius: 10px;
  background: var(--background, #fff);
}

/* ===================== MISRA 违规列表 ===================== */
.misra-summary {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 600;
  border-radius: 12px;
}

.badge.error { background: #fee2e2; color: #b91c1c; }
.badge.warn { background: #fef3c7; color: #b45309; }
.badge.total {
  background: var(--secondary, #f4f4f5);
  color: var(--foreground, #3f3f46);
}

.violation-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.violation-item {
  padding: 10px 12px;
  border-radius: 8px;
  border-left: 3px solid;
  background: var(--secondary, #f9fafb);
  font-size: 13px;
}

.violation-error {
  border-left-color: #dc2626;
  background: #fef2f2;
}

.violation-warn {
  border-left-color: #f59e0b;
  background: #fffbeb;
}

.violation-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.cat-tag,
.rule-tag,
.line-tag {
  font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
}

.cat-tag.cat-required { background: #dbeafe; color: #1d4ed8; }
.cat-tag.cat-mandatory { background: #fee2e2; color: #b91c1c; }
.cat-tag.cat-advisory { background: #fef3c7; color: #b45309; }

.rule-tag {
  background: #1f2937;
  color: #fbbf24;
}

.line-tag {
  background: var(--muted, #e4e4e7);
  color: var(--foreground, #3f3f46);
}

.violation-msg {
  font-size: 12px;
  color: var(--foreground, #3f3f46);
  line-height: 1.5;
}

.empty-tip {
  padding: 16px;
  text-align: center;
  color: #15803d;
  font-size: 14px;
  font-weight: 500;
  background: #f0fdf4;
  border-radius: 8px;
}

/* ===================== 数字孪生 Tab ===================== */
.simulation-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>