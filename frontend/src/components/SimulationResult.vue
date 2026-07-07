<script setup lang="ts">
/**
 * SimulationResult 仿真结果面板（Day 3 数字孪生）
 *
 * - 顶部状态：✅ 仿真通过 / ❌ 契约违约（core dump）
 * - 如果违约：红色高亮显示违约的契约 ID + 断言信息 + 违约时间步
 * - 统计卡片：仿真步数 / 输入范围 / 输出范围 / 最大值 / 最小值 / 均值
 * - 波形图（WaveformChart 组件）
 * - 底部：终端输出日志（复用 AgentTerminal 的 VSCode 终端样式）
 *
 * 参考文档第 6 章数字孪生、6.4.1 契约断言、6.6 沙盒隔离。
 */
import { computed } from "vue";
import { CheckCircle2, XCircle, AlertOctagon, Clock } from "lucide-vue-next";
import WaveformChart from "./WaveformChart.vue";
import type { SimulationResult, AgentType, LogLevel } from "@/services/mockApi";
import { agentColorMap, levelColorMap } from "@/utils/colors";

interface Props {
  /** 仿真结果数据 */
  result: SimulationResult;
  /** 是否正在仿真中（loading 状态） */
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
});



/** Agent 徽章样式 */
const badgeStyle = (agent: AgentType) => {
  const c = agentColorMap[agent];
  return { backgroundColor: c.bg, color: c.fg };
};

/** 日志内容颜色 */
const contentStyle = (level: LogLevel) => ({
  color: levelColorMap[level],
});

/** 统计卡片数据 */
const statCards = computed(() => {
  const s = props.result.statistics;
  return [
    { label: "仿真步数", value: s.total_steps.toString(), unit: "steps", color: "#0284C7", icon: "📊" },
    { label: "输入范围", value: `${s.input_range[0]} ~ ${s.input_range[1]}`, unit: "uint16", color: "#0EA5E9", icon: "📥" },
    { label: "输出范围", value: `${s.output_range[0]} ~ ${s.output_range[1]}`, unit: "uint16", color: "#22c55e", icon: "📤" },
    { label: "输出最大值", value: s.output_max.toString(), unit: "max", color: "#dc2626", icon: "📈" },
    { label: "输出最小值", value: s.output_min.toString(), unit: "min", color: "#06B6D4", icon: "📉" },
    { label: "输出均值", value: s.output_mean.toString(), unit: "mean", color: "#F97316", icon: "Σ" },
  ];
});

/** 故障类型显示名 */
const faultDisplayName = computed(() => {
  const map: Record<string, string> = {
    bias: "传感器偏置 (Bias)",
    signal_loss: "信号丢失 (Signal Loss)",
    noise: "高频噪声 (Noise)",
    stuck: "卡死故障 (Stuck)",
    step: "阶跃突变 (Step)",
  };
  return props.result.fault_type ? map[props.result.fault_type] : null;
});
</script>

<template>
  <div class="simulation-result">
    <!-- 顶部状态条 -->
    <div class="status-bar" :class="{ pass: result.passed, fail: !result.passed }">
      <div class="status-left">
        <component
          :is="loading ? Clock : (result.passed ? CheckCircle2 : XCircle)"
          class="status-icon"
          :class="{ spinning: loading }"
        />
        <div class="status-text">
          <div class="status-title">
            <template v-if="loading">⏳ 仿真运行中...</template>
            <template v-else-if="result.passed">✅ 仿真通过</template>
            <template v-else>❌ 契约违约（core dump）</template>
          </div>
          <div class="status-sub">
            <template v-if="loading">正在执行数字孪生仿真...</template>
            <template v-else>
              {{ result.total_steps }} 步仿真
              <template v-if="faultDisplayName"> · 故障：{{ faultDisplayName }}</template>
            </template>
          </div>
        </div>
      </div>
      <div v-if="!loading && result.passed" class="status-right">
        <span class="status-badge pass">6/6 契约通过</span>
      </div>
      <div v-else-if="!loading && !result.passed" class="status-right">
        <span class="status-badge fail">CORE DUMP</span>
      </div>
    </div>

    <!-- 契约违约详情（仅 passed=false 时显示） -->
    <div v-if="!loading && !result.passed && result.contract_violation" class="violation-card">
      <div class="violation-header">
        <AlertOctagon class="violation-icon" />
        <span class="violation-title">契约违约详情</span>
        <span class="violation-contract-id">{{ result.contract_violation.contract_id }}</span>
      </div>
      <div class="violation-body">
        <div class="violation-row">
          <span class="row-label">违约时间步：</span>
          <code class="row-value">step {{ result.contract_violation.timestep }}</code>
        </div>
        <div class="violation-row">
          <span class="row-label">触发断言：</span>
          <code class="row-value assert-code">{{ result.contract_violation.assertion }}</code>
        </div>
        <div class="violation-row">
          <span class="row-label">实际值：</span>
          <code class="row-value">{{ result.contract_violation.actual_value }}</code>
        </div>
        <div class="violation-message">
          {{ result.contract_violation.message }}
        </div>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div v-if="!loading" class="stats-grid">
      <div
        v-for="stat in statCards"
        :key="stat.label"
        class="stat-card"
        :style="{ borderLeftColor: stat.color }"
      >
        <div class="stat-icon">{{ stat.icon }}</div>
        <div class="stat-info">
          <div class="stat-label">{{ stat.label }}</div>
          <div class="stat-value">{{ stat.value }}</div>
          <div class="stat-unit">{{ stat.unit }}</div>
        </div>
      </div>
    </div>

    <!-- 波形图 -->
    <div v-if="!loading" class="waveform-section">
      <WaveformChart
        :input-data="result.input_waveform"
        :output-data="result.output_waveform"
        :fault-range="result.fault_range"
        :height="300"
      />
    </div>

    <!-- 终端输出日志（复用 AgentTerminal 的 VSCode 终端样式） -->
    <div class="sim-terminal">
      <div class="terminal-header">
        <div class="traffic-lights">
          <span class="light red" />
          <span class="light yellow" />
          <span class="light green" />
        </div>
        <div class="terminal-title">🖥️ 仿真终端输出</div>
        <span v-if="faultDisplayName" class="fault-tag">{{ faultDisplayName }}</span>
      </div>
      <div class="terminal-body">
        <div v-if="!result.logs.length && !loading" class="empty-hint">等待仿真日志...</div>
        <div v-for="(log, i) in result.logs" :key="i" class="log-line">
          <span class="log-badge" :style="badgeStyle(log.agent)">{{ log.agent }}</span>
          <span class="log-content" :style="contentStyle(log.level)">{{ log.thought }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.simulation-result { display: flex; flex-direction: column; gap: 16px; }

.status-bar { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-radius: 10px; border: 2px solid; }
.status-bar.pass { background: linear-gradient(to right, #f0fdf4, #ecfdf5); border-color: #10b981; }
.status-bar.fail { background: linear-gradient(to right, #fef2f2, #fff7ed); border-color: #dc2626; }
.status-left { display: flex; align-items: center; gap: 12px; }
.status-icon { width: 32px; height: 32px; flex-shrink: 0; }
.status-bar.pass .status-icon { color: #10b981; }
.status-bar.fail .status-icon { color: #dc2626; }
.status-icon.spinning { color: #0EA5E9; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.status-title { font-size: 18px; font-weight: 700; color: #1f2937; }
.status-sub { font-size: 12px; color: #6b7280; margin-top: 2px; }
.status-badge { display: inline-flex; align-items: center; padding: 4px 14px; font-size: 13px; font-weight: 700; border-radius: 16px; font-family: 'Consolas', monospace; }
.status-badge.pass { background: #dcfce7; color: #15803d; border: 1px solid #86efac; }
.status-badge.fail { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; text-transform: uppercase; letter-spacing: 1px; }

.violation-card { background: #fef2f2; border: 1px solid #fca5a5; border-left: 4px solid #dc2626; border-radius: 8px; overflow: hidden; }
.violation-header { display: flex; align-items: center; gap: 8px; padding: 10px 14px; background: #fee2e2; border-bottom: 1px solid #fca5a5; }
.violation-icon { width: 18px; height: 18px; color: #dc2626; }
.violation-title { font-size: 14px; font-weight: 700; color: #991b1b; }
.violation-contract-id { font-family: 'Consolas', monospace; font-size: 12px; font-weight: 600; background: #991b1b; color: #fee2e2; padding: 2px 8px; border-radius: 4px; margin-left: auto; }
.violation-body { padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; }
.violation-row { display: flex; align-items: flex-start; gap: 8px; font-size: 13px; }
.row-label { color: #6b7280; flex-shrink: 0; min-width: 90px; }
.row-value { font-family: 'Consolas', monospace; color: #1f2937; word-break: break-all; }
.row-value.assert-code { color: #b91c1c; font-weight: 600; }
.violation-message { margin-top: 4px; padding: 8px 10px; background: #fff; border-radius: 4px; border: 1px solid #fecaca; font-size: 12px; color: #7f1d1d; line-height: 1.5; }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.stat-card { display: flex; align-items: center; gap: 12px; padding: 12px 14px; background: var(--background, #fff); border: 1px solid var(--border, #e5e7eb); border-left: 3px solid; border-radius: 8px; }
.stat-icon { font-size: 22px; flex-shrink: 0; }
.stat-info { display: flex; flex-direction: column; }
.stat-label { font-size: 11px; color: var(--muted-foreground, #6b7280); text-transform: uppercase; letter-spacing: 0.3px; }
.stat-value { font-size: 16px; font-weight: 700; color: var(--foreground, #1f2937); font-family: 'Consolas', monospace; margin-top: 2px; }
.stat-unit { font-size: 10px; color: var(--muted-foreground, #9ca3af); font-family: 'Consolas', monospace; }

.waveform-section { background: var(--background, #fff); border: 1px solid var(--border, #e5e7eb); border-radius: 8px; padding: 12px; }

.sim-terminal { display: flex; flex-direction: column; background: #1e1e1e; border-radius: 8px; overflow: hidden; font-family: 'Consolas', 'Courier New', monospace; color: #d4d4d4; }
.terminal-header { display: flex; align-items: center; padding: 8px 12px; background: #2d2d2d; border-bottom: 1px solid #3c3c3c; user-select: none; }
.traffic-lights { display: flex; gap: 6px; margin-right: 12px; }
.light { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
.light.red { background: #ff5f56; }
.light.yellow { background: #ffbd2e; }
.light.green { background: #27c93f; }
.terminal-title { font-size: 13px; color: #cccccc; font-weight: 500; flex: 1; }
.fault-tag { background: #ea580c; color: #ffedd5; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 3px; letter-spacing: 0.5px; }
.terminal-body { max-height: 280px; overflow-y: auto; padding: 10px 12px; font-size: 13px; line-height: 1.6; }
.terminal-body::-webkit-scrollbar { width: 8px; }
.terminal-body::-webkit-scrollbar-track { background: transparent; }
.terminal-body::-webkit-scrollbar-thumb { background: #3c3c3c; border-radius: 4px; }
.empty-hint { color: #6a6a6a; font-style: italic; }
.log-line { display: flex; align-items: flex-start; gap: 8px; padding: 2px 0; word-break: break-word; }
.log-badge { flex-shrink: 0; font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 3px; letter-spacing: 0.3px; margin-top: 1px; }
.log-content { flex: 1; white-space: pre-wrap; min-width: 0; }
</style>
