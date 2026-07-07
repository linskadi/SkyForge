<script setup lang="ts">
/**
 * FaultInjectPanel 故障注入面板（Day 3 数字孪生）
 *
 * 5 类故障注入控件（参考文档第 6 章数字孪生沙盒）：
 * 1. 传感器偏置（Bias）：滑块设置偏置值
 * 2. 信号丢失（Signal Loss）：开关 + 持续时间滑块
 * 3. 高频噪声（Noise）：开关 + 噪声幅度滑块
 * 4. 卡死故障（Stuck）：开关 + 卡死值输入
 * 5. 阶跃突变（Step）：开关 + 突变时间 + 突变值
 *
 * 同一时刻只能启用一种故障类型（互斥开关）。
 * 点击"注入故障"按钮后触发回调，并显示"已注入"状态徽章。
 */
import { computed, ref } from "vue";
import { Zap, RotateCcw, Gauge, SignalZero, Waves, Lock, TrendingUp } from "lucide-vue-next";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { FaultType, FaultParams } from "@/services/mockApi";

/** 组件 emit 事件 */
const emit = defineEmits<{
  /** 注入故障：传递故障类型和参数 */
  (e: "inject", faultType: FaultType, params: FaultParams): void;
}>();

/** 当前选中的故障类型（互斥，null 表示无选中） */
const activeFault = ref<FaultType | null>(null);

/** 是否已注入（显示状态徽章） */
const injected = ref(false);

// ===== 各故障类型的参数 =====

/** 偏置值（bias） */
const biasValue = ref(20000);
/** 信号丢失持续时间（步） */
const lossDuration = ref(30);
/** 噪声幅度 */
const noiseAmplitude = ref(5000);
/** 卡死值 */
const stuckValue = ref(40000);
/** 阶跃突变时间步 */
const stepTime = ref(80);
/** 阶跃突变值 */
const stepValue = ref(60000);

/** 故障类型配置列表 */
const faultConfigs = computed(() => [
  {
    type: "bias" as FaultType,
    icon: Gauge,
    title: "传感器偏置",
    enTitle: "Bias",
    desc: "输入叠加固定偏置值，模拟传感器零点漂移",
    color: "#1e6fb8",
  },
  {
    type: "signal_loss" as FaultType,
    icon: SignalZero,
    title: "信号丢失",
    enTitle: "Signal Loss",
    desc: "指定区间内输入强制为 0，模拟传感器断线",
    color: "#ea580c",
  },
  {
    type: "noise" as FaultType,
    icon: Waves,
    title: "高频噪声",
    enTitle: "Noise",
    desc: "输入叠加随机噪声，模拟电磁干扰",
    color: "#7c3aed",
  },
  {
    type: "stuck" as FaultType,
    icon: Lock,
    title: "卡死故障",
    enTitle: "Stuck",
    desc: "输入卡在固定值，模拟传感器机械卡死",
    color: "#dc2626",
  },
  {
    type: "step" as FaultType,
    icon: TrendingUp,
    title: "阶跃突变",
    enTitle: "Step",
    desc: "指定时间步输入突变，模拟工况切换",
    color: "#0891b2",
  },
]);

/** 切换故障类型开关（互斥） */
const toggleFault = (faultType: FaultType) => {
  if (activeFault.value === faultType) {
    activeFault.value = null;
  } else {
    activeFault.value = faultType;
  }
  injected.value = false;
};

/** 点击"注入故障"按钮 */
const onInject = () => {
  if (!activeFault.value) return;
  const params: FaultParams = {};
  switch (activeFault.value) {
    case "bias":
      params.bias_value = biasValue.value;
      break;
    case "signal_loss":
      params.loss_duration = lossDuration.value;
      break;
    case "noise":
      params.noise_amplitude = noiseAmplitude.value;
      break;
    case "stuck":
      params.stuck_value = stuckValue.value;
      break;
    case "step":
      params.step_time = stepTime.value;
      params.step_value = stepValue.value;
      break;
  }
  injected.value = true;
  emit("inject", activeFault.value, params);
};

/** 重置所有参数 */
const onReset = () => {
  activeFault.value = null;
  injected.value = false;
  biasValue.value = 20000;
  lossDuration.value = 30;
  noiseAmplitude.value = 5000;
  stuckValue.value = 40000;
  stepTime.value = 80;
  stepValue.value = 60000;
};
</script>

<template>
  <Card class="fault-panel">
    <CardHeader>
      <CardTitle class="panel-title">
        🎛️ 故障注入面板
        <span class="title-hint">（数字孪生沙盒，参考文档 6.5/6.6）</span>
      </CardTitle>
    </CardHeader>
    <CardContent>
      <!-- 5 类故障卡片 -->
      <div class="fault-grid">
        <div
          v-for="cfg in faultConfigs"
          :key="cfg.type"
          class="fault-card"
          :class="{ active: activeFault === cfg.type }"
          :style="activeFault === cfg.type ? { borderColor: cfg.color } : {}"
        >
          <!-- 卡片头部：图标 + 标题 + 开关 -->
          <div class="card-header">
            <div class="card-title-row">
              <component :is="cfg.icon" class="card-icon" :style="{ color: cfg.color }" />
              <div class="card-text">
                <div class="card-title-cn">{{ cfg.title }}</div>
                <div class="card-title-en">{{ cfg.enTitle }}</div>
              </div>
            </div>
            <Switch
              :model-value="activeFault === cfg.type"
              @update:model-value="(val: boolean) => val ? toggleFault(cfg.type) : (activeFault = null)"
            />
          </div>
          <div class="card-desc">{{ cfg.desc }}</div>

          <!-- 参数控件（仅当该故障被选中时显示） -->
          <div v-if="activeFault === cfg.type" class="card-params">
            <!-- Bias: 偏置值滑块 -->
            <template v-if="cfg.type === 'bias'">
              <div class="param-row">
                <Label class="param-label">偏置值</Label>
                <input
                  type="range"
                  class="param-slider"
                  min="1000"
                  max="50000"
                  step="1000"
                  v-model.number="biasValue"
                  :style="{ accentColor: cfg.color }"
                />
                <span class="param-value">+{{ biasValue }}</span>
              </div>
            </template>

            <!-- Signal Loss: 持续时间滑块 -->
            <template v-else-if="cfg.type === 'signal_loss'">
              <div class="param-row">
                <Label class="param-label">持续时间</Label>
                <input
                  type="range"
                  class="param-slider"
                  min="5"
                  max="100"
                  step="5"
                  v-model.number="lossDuration"
                  :style="{ accentColor: cfg.color }"
                />
                <span class="param-value">{{ lossDuration }} 步</span>
              </div>
            </template>

            <!-- Noise: 噪声幅度滑块 -->
            <template v-else-if="cfg.type === 'noise'">
              <div class="param-row">
                <Label class="param-label">噪声幅度</Label>
                <input
                  type="range"
                  class="param-slider"
                  min="500"
                  max="15000"
                  step="500"
                  v-model.number="noiseAmplitude"
                  :style="{ accentColor: cfg.color }"
                />
                <span class="param-value">±{{ noiseAmplitude }}</span>
              </div>
            </template>

            <!-- Stuck: 卡死值输入 -->
            <template v-else-if="cfg.type === 'stuck'">
              <div class="param-row">
                <Label class="param-label">卡死值</Label>
                <Input
                  type="number"
                  class="param-input"
                  min="0"
                  max="65535"
                  v-model.number="stuckValue"
                />
                <span class="param-value">uint16</span>
              </div>
            </template>

            <!-- Step: 突变时间 + 突变值 -->
            <template v-else-if="cfg.type === 'step'">
              <div class="param-row">
                <Label class="param-label">突变时间步</Label>
                <Input
                  type="number"
                  class="param-input"
                  min="0"
                  max="199"
                  v-model.number="stepTime"
                />
                <span class="param-value">step</span>
              </div>
              <div class="param-row">
                <Label class="param-label">突变值</Label>
                <Input
                  type="number"
                  class="param-input"
                  min="0"
                  max="65535"
                  v-model.number="stepValue"
                />
                <span class="param-value">uint16</span>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- 底部操作栏 -->
      <div class="action-bar">
        <Button
          :disabled="!activeFault"
          @click="onInject"
        >
          <Zap class="w-4 h-4" />
          注入故障
        </Button>
        <Button variant="outline" @click="onReset">
          <RotateCcw class="w-4 h-4" />
          重置参数
        </Button>
        <!-- 已注入状态徽章 -->
        <span v-if="injected && activeFault" class="injected-badge">
          ✅ 已注入：{{ faultConfigs.find(f => f.type === activeFault)?.title }}
        </span>
        <span v-else-if="!activeFault" class="hint-text">
          请选择一种故障类型
        </span>
      </div>
    </CardContent>
  </Card>
</template>

<style scoped>
.fault-panel {
  border-left: 3px solid #7c3aed;
}

.panel-title {
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

/* 5 个故障卡片网格 */
.fault-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.fault-card {
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
  padding: 12px;
  background: var(--background, #fff);
  transition: all 0.2s;
  cursor: default;
}

.fault-card.active {
  border-width: 2px;
  background: var(--secondary, #f9fafb);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.card-text {
  display: flex;
  flex-direction: column;
}

.card-title-cn {
  font-size: 14px;
  font-weight: 600;
  color: var(--foreground, #1f2937);
}

.card-title-en {
  font-size: 11px;
  color: var(--muted-foreground, #9ca3af);
  font-family: 'Consolas', monospace;
}

.card-desc {
  font-size: 12px;
  color: var(--muted-foreground, #6b7280);
  margin-top: 8px;
  line-height: 1.5;
}

/* 参数控件区 */
.card-params {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border, #e5e7eb);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.param-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.param-label {
  font-size: 12px;
  font-weight: 500;
  min-width: 70px;
  color: var(--foreground, #374151);
}

.param-slider {
  flex: 1;
  height: 6px;
  cursor: pointer;
}

.param-value {
  font-size: 12px;
  font-family: 'Consolas', monospace;
  font-weight: 600;
  color: var(--foreground, #1f2937);
  min-width: 60px;
  text-align: right;
}

.param-input {
  flex: 1;
  max-width: 120px;
}

/* 底部操作栏 */
.action-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border, #e5e7eb);
}

.injected-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  font-size: 13px;
  font-weight: 600;
  border-radius: 16px;
  background: #dcfce7;
  color: #15803d;
  border: 1px solid #86efac;
}

.hint-text {
  font-size: 13px;
  color: var(--muted-foreground, #9ca3af);
}
</style>
