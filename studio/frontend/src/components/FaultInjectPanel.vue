<script setup lang="ts">
import {
	AlertTriangle,
	ArrowUpDown,
	CircleDot,
	Clock,
	Gauge,
	Lock,
	RotateCcw,
	SignalZero,
	Siren,
	ToggleLeft,
	TrendingUp,
	Waves,
	Zap,
} from "@lucide/vue";
/**
 * FaultInjectPanel 故障注入面板（数字孪生沙盒）
 *
 * 覆盖嵌入式/航空电子常见故障类型：
 *  1. 传感器偏置（Bias）         — 零点漂移
 *  2. 信号丢失（Signal Loss）    — 断线/开路
 *  3. 高频噪声（Noise）          — 电磁干扰
 *  4. 卡死故障（Stuck）          — 机械卡死
 *  5. 阶跃突变（Step）           — 工况切换
 *  6. 饱和截断（Saturation）     — 超量程限幅
 *  7. 间歇性故障（Intermittent） — 接触不良
 *  8. 漂移（Drift）              — 元器件老化渐变
 *  9. 丢帧/延迟（Timeout）       — 总线通信超时
 * 10. 跳变毛刺（Glitch）         — 瞬时尖峰脉冲
 * 11. 零输出（Stuck-at-Zero）    — 传感器无响应
 * 12. 反接/符号反转（Polarity）   — 线缆接反
 *
 * 支持同时启用多种故障（多选）。
 * 点击"注入故障"后依次叠加所有选中的故障。
 */
import { computed, reactive } from "vue";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { FaultParams, FaultType } from "@/services/mockApi";

/** 扩展故障类型（兼容后端已有类型 + 新增类型） */
type ExtFaultType =
	| FaultType
	| "saturation"
	| "intermittent"
	| "drift"
	| "timeout"
	| "glitch"
	| "stuck_zero"
	| "polarity";

/** 单个故障的完整状态 */
interface FaultState {
	enabled: boolean;
	params: Record<string, number>;
}

/** 组件 emit 事件 */
const emit = defineEmits<{
	/** 注入故障：传递所有已启用的故障列表 */
	inject: [faults: { type: FaultType; params: FaultParams }[]];
}>();

/** 各故障类型的启用状态和参数（多选） */
const faults = reactive<Record<ExtFaultType, FaultState>>({
	bias: { enabled: false, params: { bias_value: 20000 } },
	signal_loss: { enabled: false, params: { loss_duration: 30 } },
	noise: { enabled: false, params: { noise_amplitude: 5000 } },
	stuck: { enabled: false, params: { stuck_value: 40000 } },
	step: { enabled: false, params: { step_time: 80, step_value: 60000 } },
	saturation: {
		enabled: false,
		params: { upper_limit: 60000, lower_limit: 5000 },
	},
	intermittent: { enabled: false, params: { interval: 20, duration: 5 } },
	drift: { enabled: false, params: { drift_rate: 500 } },
	timeout: { enabled: false, params: { timeout_start: 50 } },
	glitch: {
		enabled: false,
		params: { glitch_magnitude: 30000, glitch_count: 5 },
	},
	stuck_zero: { enabled: false, params: { stuck_start: 40 } },
	polarity: { enabled: false, params: {} },
});

/** 已启用的故障数量 */
const enabledCount = computed(
	() =>
		(Object.keys(faults) as ExtFaultType[]).filter((t) => faults[t].enabled)
			.length,
);

/** 故障类型配置列表 */
const faultConfigs = computed(() => [
	// ===== 基础故障 =====
	{
		type: "bias" as ExtFaultType,
		icon: Gauge,
		title: "传感器偏置",
		enTitle: "Bias",
		desc: "输入叠加固定偏置值，模拟传感器零点漂移",
		color: "#0EA5E9",
		group: "传感器",
	},
	{
		type: "signal_loss" as ExtFaultType,
		icon: SignalZero,
		title: "信号丢失",
		enTitle: "Signal Loss",
		desc: "指定区间内输入强制为 0，模拟断线/开路",
		color: "#ea580c",
		group: "传感器",
	},
	{
		type: "noise" as ExtFaultType,
		icon: Waves,
		title: "高频噪声",
		enTitle: "Noise",
		desc: "输入叠加随机噪声，模拟电磁干扰 (EMI)",
		color: "#8B5CF6",
		group: "信号质量",
	},
	{
		type: "stuck" as ExtFaultType,
		icon: Lock,
		title: "卡死故障",
		enTitle: "Stuck-at",
		desc: "输入卡在固定值，模拟传感器机械卡死",
		color: "#dc2626",
		group: "传感器",
	},
	{
		type: "step" as ExtFaultType,
		icon: TrendingUp,
		title: "阶跃突变",
		enTitle: "Step Change",
		desc: "指定时间步输入突变，模拟工况快速切换",
		color: "#0891b2",
		group: "信号质量",
	},
	// ===== 信号质量故障 =====
	{
		type: "saturation" as ExtFaultType,
		icon: ArrowUpDown,
		title: "饱和截断",
		enTitle: "Saturation",
		desc: "超出上下限的值被截断，模拟 ADC 量程限幅",
		color: "#b45309",
		group: "信号质量",
	},
	{
		type: "glitch" as ExtFaultType,
		icon: Siren,
		title: "跳变毛刺",
		enTitle: "Glitch",
		desc: "随机时刻出现瞬时尖峰脉冲，模拟闩锁效应",
		color: "#e11d48",
		group: "信号质量",
	},
	// ===== 通信/时序故障 =====
	{
		type: "intermittent" as ExtFaultType,
		icon: ToggleLeft,
		title: "间歇性故障",
		enTitle: "Intermittent",
		desc: "周期性输出正常/异常值，模拟接触不良",
		color: "#059669",
		group: "通信时序",
	},
	{
		type: "timeout" as ExtFaultType,
		icon: Clock,
		title: "丢帧 / 延迟",
		enTitle: "Timeout",
		desc: "指定时间点后信号冻结，模拟总线超时丢帧",
		color: "#7c2d12",
		group: "通信时序",
	},
	// ===== 偏移/退化故障 =====
	{
		type: "drift" as ExtFaultType,
		icon: AlertTriangle,
		title: "渐变漂移",
		enTitle: "Drift",
		desc: "信号随时间线性偏移，模拟元器件老化退化",
		color: "#9333ea",
		group: "退化",
	},
	{
		type: "stuck_zero" as ExtFaultType,
		icon: CircleDot,
		title: "零输出",
		enTitle: "Stuck-at-Zero",
		desc: "指定时间点后输出恒为 0，模拟传感器完全失效",
		color: "#64748b",
		group: "退化",
	},
	{
		type: "polarity" as ExtFaultType,
		icon: ToggleLeft,
		title: "符号反转",
		enTitle: "Polarity Reversal",
		desc: "信号取反，模拟线缆接反或极性错误",
		color: "#0d9488",
		group: "退化",
	},
]);

/** 按分组排列 */
const groupedFaults = computed(() => {
	const groups: Record<string, typeof faultConfigs.value> = {};
	for (const cfg of faultConfigs.value) {
		if (!groups[cfg.group]) groups[cfg.group] = [];
		groups[cfg.group].push(cfg);
	}
	return groups;
});

/** 切换故障启用状态 */
const toggleFault = (faultType: ExtFaultType) => {
	faults[faultType].enabled = !faults[faultType].enabled;
};

/** 点击"注入故障"按钮 */
const onInject = () => {
	const activeList = (Object.keys(faults) as ExtFaultType[])
		.filter((t) => faults[t].enabled)
		.map((t) => ({
			type: t as FaultType,
			params: { ...faults[t].params } as FaultParams,
		}));
	if (activeList.length === 0) return;
	emit("inject", activeList);
};

/** 重置所有参数和状态 */
const onReset = () => {
	for (const t of Object.keys(faults) as ExtFaultType[]) {
		faults[t].enabled = false;
	}
	faults.bias.params = { bias_value: 20000 };
	faults.signal_loss.params = { loss_duration: 30 };
	faults.noise.params = { noise_amplitude: 5000 };
	faults.stuck.params = { stuck_value: 40000 };
	faults.step.params = { step_time: 80, step_value: 60000 };
	faults.saturation.params = { upper_limit: 60000, lower_limit: 5000 };
	faults.intermittent.params = { interval: 20, duration: 5 };
	faults.drift.params = { drift_rate: 500 };
	faults.timeout.params = { timeout_start: 50 };
	faults.glitch.params = { glitch_magnitude: 30000, glitch_count: 5 };
	faults.stuck_zero.params = { stuck_start: 40 };
	faults.polarity.params = {};
};
</script>

<template>
  <Card class="fault-panel">
    <CardHeader>
      <CardTitle class="panel-title">🎛️ 故障注入面板</CardTitle>
    </CardHeader>
    <CardContent>
      <!-- 按分组显示故障卡片 -->
      <div v-for="(items, group) in groupedFaults" :key="group" class="fault-group">
        <div class="group-label">{{ group }}</div>
        <div class="fault-grid">
          <div
            v-for="cfg in items"
            :key="cfg.type"
            class="fault-card"
            :class="{ active: faults[cfg.type].enabled }"
            :style="faults[cfg.type].enabled ? { borderColor: cfg.color } : {}"
          >
            <!-- 卡片头部 -->
            <div class="card-header">
              <div class="card-title-row">
                <component :is="cfg.icon" class="card-icon" :style="{ color: cfg.color }" />
                <div class="card-text">
                  <div class="card-title-cn">{{ cfg.title }}</div>
                  <div class="card-title-en">{{ cfg.enTitle }}</div>
                </div>
              </div>
              <Switch
                :model-value="faults[cfg.type].enabled"
                @update:model-value="() => toggleFault(cfg.type)"
              />
            </div>
            <div class="card-desc">{{ cfg.desc }}</div>

            <!-- 参数控件 -->
            <div v-if="faults[cfg.type].enabled" class="card-params">
              <!-- Bias -->
              <template v-if="cfg.type === 'bias'">
                <div class="param-row">
                  <Label class="param-label">偏置值</Label>
                  <input type="range" class="param-slider" min="1000" max="50000" step="1000"
                    v-model.number="faults.bias.params.bias_value" :style="{ accentColor: cfg.color }" />
                  <span class="param-value">+{{ faults.bias.params.bias_value }}</span>
                </div>
              </template>

              <!-- Signal Loss -->
              <template v-else-if="cfg.type === 'signal_loss'">
                <div class="param-row">
                  <Label class="param-label">持续时间</Label>
                  <input type="range" class="param-slider" min="5" max="100" step="5"
                    v-model.number="faults.signal_loss.params.loss_duration" :style="{ accentColor: cfg.color }" />
                  <span class="param-value">{{ faults.signal_loss.params.loss_duration }} 步</span>
                </div>
              </template>

              <!-- Noise -->
              <template v-else-if="cfg.type === 'noise'">
                <div class="param-row">
                  <Label class="param-label">噪声幅度</Label>
                  <input type="range" class="param-slider" min="500" max="15000" step="500"
                    v-model.number="faults.noise.params.noise_amplitude" :style="{ accentColor: cfg.color }" />
                  <span class="param-value">±{{ faults.noise.params.noise_amplitude }}</span>
                </div>
              </template>

              <!-- Stuck -->
              <template v-else-if="cfg.type === 'stuck'">
                <div class="param-row">
                  <Label class="param-label">卡死值</Label>
                  <Input type="number" class="param-input" min="0" max="65535"
                    v-model.number="faults.stuck.params.stuck_value" />
                  <span class="param-value">uint16</span>
                </div>
              </template>

              <!-- Step -->
              <template v-else-if="cfg.type === 'step'">
                <div class="param-row">
                  <Label class="param-label">突变时间步</Label>
                  <Input type="number" class="param-input" min="0" max="199"
                    v-model.number="faults.step.params.step_time" />
                  <span class="param-value">step</span>
                </div>
                <div class="param-row">
                  <Label class="param-label">突变值</Label>
                  <Input type="number" class="param-input" min="0" max="65535"
                    v-model.number="faults.step.params.step_value" />
                  <span class="param-value">uint16</span>
                </div>
              </template>

              <!-- Saturation -->
              <template v-else-if="cfg.type === 'saturation'">
                <div class="param-row">
                  <Label class="param-label">上限</Label>
                  <Input type="number" class="param-input" min="0" max="65535"
                    v-model.number="faults.saturation.params.upper_limit" />
                  <span class="param-value">uint16</span>
                </div>
                <div class="param-row">
                  <Label class="param-label">下限</Label>
                  <Input type="number" class="param-input" min="0" max="65535"
                    v-model.number="faults.saturation.params.lower_limit" />
                  <span class="param-value">uint16</span>
                </div>
              </template>

              <!-- Intermittent -->
              <template v-else-if="cfg.type === 'intermittent'">
                <div class="param-row">
                  <Label class="param-label">故障周期</Label>
                  <input type="range" class="param-slider" min="5" max="60" step="5"
                    v-model.number="faults.intermittent.params.interval" :style="{ accentColor: cfg.color }" />
                  <span class="param-value">{{ faults.intermittent.params.interval }} 步</span>
                </div>
                <div class="param-row">
                  <Label class="param-label">故障持续</Label>
                  <input type="range" class="param-slider" min="1" max="20" step="1"
                    v-model.number="faults.intermittent.params.duration" :style="{ accentColor: cfg.color }" />
                  <span class="param-value">{{ faults.intermittent.params.duration }} 步</span>
                </div>
              </template>

              <!-- Drift -->
              <template v-else-if="cfg.type === 'drift'">
                <div class="param-row">
                  <Label class="param-label">漂移速率</Label>
                  <input type="range" class="param-slider" min="100" max="3000" step="100"
                    v-model.number="faults.drift.params.drift_rate" :style="{ accentColor: cfg.color }" />
                  <span class="param-value">+{{ faults.drift.params.drift_rate }}/步</span>
                </div>
              </template>

              <!-- Timeout -->
              <template v-else-if="cfg.type === 'timeout'">
                <div class="param-row">
                  <Label class="param-label">冻结起始步</Label>
                  <input type="range" class="param-slider" min="10" max="190" step="10"
                    v-model.number="faults.timeout.params.timeout_start" :style="{ accentColor: cfg.color }" />
                  <span class="param-value">step {{ faults.timeout.params.timeout_start }}</span>
                </div>
              </template>

              <!-- Glitch -->
              <template v-else-if="cfg.type === 'glitch'">
                <div class="param-row">
                  <Label class="param-label">毛刺幅度</Label>
                  <input type="range" class="param-slider" min="5000" max="60000" step="1000"
                    v-model.number="faults.glitch.params.glitch_magnitude" :style="{ accentColor: cfg.color }" />
                  <span class="param-value">±{{ faults.glitch.params.glitch_magnitude }}</span>
                </div>
                <div class="param-row">
                  <Label class="param-label">毛刺次数</Label>
                  <input type="range" class="param-slider" min="1" max="20" step="1"
                    v-model.number="faults.glitch.params.glitch_count" :style="{ accentColor: cfg.color }" />
                  <span class="param-value">×{{ faults.glitch.params.glitch_count }}</span>
                </div>
              </template>

              <!-- Stuck-at-Zero -->
              <template v-else-if="cfg.type === 'stuck_zero'">
                <div class="param-row">
                  <Label class="param-label">失效起始步</Label>
                  <input type="range" class="param-slider" min="10" max="190" step="10"
                    v-model.number="faults.stuck_zero.params.stuck_start" :style="{ accentColor: cfg.color }" />
                  <span class="param-value">step {{ faults.stuck_zero.params.stuck_start }}</span>
                </div>
              </template>

              <!-- Polarity — 无参数 -->
              <template v-else-if="cfg.type === 'polarity'">
                <div class="no-params">启用后信号自动取反（× -1）</div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部操作栏 -->
      <div class="action-bar">
        <Button :disabled="enabledCount === 0" @click="onInject">
          <Zap class="w-4 h-4" />
          注入故障
          <span v-if="enabledCount > 1" class="inject-count">×{{ enabledCount }}</span>
        </Button>
        <Button variant="outline" @click="onReset">
          <RotateCcw class="w-4 h-4" />
          重置参数
        </Button>
        <span v-if="enabledCount > 0" class="hint-text">
          已选择 {{ enabledCount }} 种故障
        </span>
        <span v-else class="hint-text">
          可同时选择多种故障类型
        </span>
      </div>
    </CardContent>
  </Card>
</template>

<style scoped>
.fault-panel {
  border-left: 3px solid #8B5CF6;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 分组 */
.fault-group {
  margin-bottom: 16px;
}

.fault-group:last-of-type {
  margin-bottom: 0;
}

.group-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: hsl(var(--muted-foreground));
  margin-bottom: 8px;
  padding-left: 2px;
}

/* 卡片网格 */
.fault-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 10px;
}

.fault-card {
  border: 1px solid hsl(var(--border));
  border-radius: 8px;
  padding: 12px;
  background: hsl(var(--background));
  transition: all 0.2s;
}

.fault-card.active {
  border-width: 2px;
  background: hsl(var(--secondary));
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
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.card-text {
  display: flex;
  flex-direction: column;
}

.card-title-cn {
  font-size: 13px;
  font-weight: 600;
  color: hsl(var(--foreground));
}

.card-title-en {
  font-size: 10px;
  color: hsl(var(--muted-foreground));
  font-family: 'Consolas', monospace;
}

.card-desc {
  font-size: 11px;
  color: hsl(var(--muted-foreground));
  margin-top: 6px;
  line-height: 1.5;
}

/* 参数控件区 */
.card-params {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed hsl(var(--border));
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.param-label {
  font-size: 11px;
  font-weight: 500;
  min-width: 72px;
  color: hsl(var(--foreground));
}

.param-slider {
  flex: 1;
  height: 6px;
  cursor: pointer;
}

.param-value {
  font-size: 11px;
  font-family: 'Consolas', monospace;
  font-weight: 600;
  color: hsl(var(--foreground));
  min-width: 56px;
  text-align: right;
}

.param-input {
  flex: 1;
  max-width: 110px;
  font-size: 12px;
}

.no-params {
  font-size: 12px;
  color: hsl(var(--muted-foreground));
  font-style: italic;
  padding: 2px 0;
}

/* 底部操作栏 */
.action-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 12px;
  margin-top: 12px;
  border-top: 1px solid hsl(var(--border));
}

.inject-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 18px;
  padding: 0 5px;
  margin-left: 4px;
  font-size: 11px;
  font-weight: 700;
  border-radius: 9px;
  background: rgba(255,255,255,0.3);
}

.hint-text {
  font-size: 13px;
  color: hsl(var(--muted-foreground));
}
</style>
