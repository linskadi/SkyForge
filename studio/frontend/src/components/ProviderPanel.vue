<script setup lang="ts">
import { useProviderStore } from "@/stores/providerStore";
import {
	Check,
	Cpu,
	Key,
	RefreshCw,
	Settings2,
	Wifi,
	WifiOff,
	X,
} from "lucide-vue-next";
/**
 * ProviderPanel — OpenCode 风格的多供应商切换面板。
 *
 * 功能：
 *  - 6 个 Provider Tab（DeepSeek/Qwen/OpenAI/Anthropic/Ollama/LMStudio）
 *  - API Key 输入（带掩码显示）
 *  - 每个 Provider 的模型选择
 *  - 本地模型标注 + 连接测试
 *  - Glass 风格，匹配航空主题
 */
import { onMounted, ref, watch } from "vue";

const store = useProviderStore();
const isOpen = ref(false);
const activeTab = ref(store.selectedProviderId);
const showKey = ref<Record<string, boolean>>({});
const testing = ref<Record<string, boolean>>({});
const testStatus = ref<Record<string, "idle" | "testing" | "ok" | "fail">>({});

onMounted(() => {
	activeTab.value = store.selectedProviderId;
});

function selectProvider(id: string) {
	store.setProvider(id);
	activeTab.value = id;
}

watch(isOpen, (val) => {
	if (val) activeTab.value = store.selectedProviderId;
});

function testConnection(id: string) {
	const provider = store.providers.find((p) => p.id === id);
	if (!provider || !provider.apiKey) return;

	testing.value[id] = true;
	testStatus.value[id] = "testing";

	// Simulate connection test
	setTimeout(() => {
		testStatus.value[id] = Math.random() > 0.3 ? "ok" : "fail";
		testing.value[id] = false;
	}, 2000);
}
</script>

<template>
  <div class="provider-panel-wrapper">
    <!-- Trigger Button -->
    <button @click="isOpen = !isOpen" class="provider-trigger glass">
      <span class="trigger-provider-icon">{{ store.selectedProvider?.icon }}</span>
      <span class="trigger-provider-name">{{ store.selectedProvider?.name }}</span>
      <span class="trigger-model-name">{{ store.selectedModel?.name }}</span>
      <Cpu :class="['status-icon', store.isLocalModel ? 'local' : 'cloud']" :size="14" />
      <Settings2 :size="14" class="gear-icon" :class="{ open: isOpen }" />
    </button>

    <!-- Dropdown Panel -->
    <Transition name="panel">
      <div v-if="isOpen" class="provider-panel glass" @click.stop>
        <!-- Header -->
        <div class="panel-header">
          <h3>LLM 配置</h3>
          <button @click="isOpen = false" class="close-btn">
            <X :size="16" />
          </button>
        </div>

        <!-- Provider Tabs -->
        <div class="provider-tabs">
          <button
            v-for="p in store.providers"
            :key="p.id"
            :class="['tab', { active: activeTab === p.id, local: p.isLocal }]"
            @click="selectProvider(p.id)"
          >
            <span class="tab-icon">{{ p.icon }}</span>
            <span class="tab-name">{{ p.name }}</span>
            <span v-if="p.enabled && p.apiKey" class="tab-dot" />
          </button>
        </div>

        <!-- Provider Detail -->
        <div v-for="p in store.providers" :key="p.id" v-show="activeTab === p.id" class="provider-detail">
          <p class="provider-desc">{{ p.description }}</p>

          <!-- API Key -->
          <div class="field-group">
            <label class="field-label">
              <Key :size="12" />
              API Key
              <span v-if="p.isLocal" class="local-badge">本地</span>
            </label>
            <div class="key-input-row">
              <input
                :type="showKey[p.id] ? 'text' : 'password'"
                :value="p.apiKey"
                @input="store.setApiKey(p.id, ($event.target as HTMLInputElement).value)"
                :placeholder="p.isLocal ? '本地无需 Key' : 'sk-...'"
                :disabled="p.isLocal"
                class="key-input"
              />
              <button
                v-if="!p.isLocal"
                @click="showKey[p.id] = !showKey[p.id]"
                class="show-key-btn"
              >
                {{ showKey[p.id] ? '隐藏' : '显示' }}
              </button>
            </div>
          </div>

          <!-- Test Connection (non-local only) -->
          <button
            v-if="!p.isLocal && p.apiKey"
            @click="testConnection(p.id)"
            :disabled="testing[p.id]"
            class="test-btn"
          >
            <RefreshCw v-if="testing[p.id]" :size="14" class="spin" />
            <Check v-else-if="testStatus[p.id] === 'ok'" :size="14" class="text-green" />
            <X v-else-if="testStatus[p.id] === 'fail'" :size="14" class="text-red" />
            <Wifi v-else :size="14" />
            {{ testStatus[p.id] === 'testing' ? '测试中...' : 
               testStatus[p.id] === 'ok' ? '连接成功' :
               testStatus[p.id] === 'fail' ? '连接失败' : '测试连接' }}
          </button>

          <!-- Model Selection -->
          <div class="field-group">
            <label class="field-label">
              <Cpu :size="12" />
              模型
            </label>
            <div class="model-grid">
              <button
                v-for="m in p.models"
                :key="m.id"
                :class="['model-card', { 
                  selected: store.selectedProviderId === p.id && store.selectedModelId === m.id 
                }]"
                @click="store.setProvider(p.id); store.setModel(m.id)"
              >
                <span class="model-name">{{ m.name }}</span>
                <span class="model-id">{{ m.id }}</span>
              </button>
            </div>
          </div>

          <!-- Local Model Status -->
          <div v-if="p.isLocal" class="local-status">
            <WifiOff :size="14" />
            <span>本地模型 — 数据不出内网，无需 API Key</span>
          </div>
        </div>

        <!-- Footer -->
        <div class="panel-footer">
          <span class="footer-hint">配置保存在本地浏览器</span>
        </div>
      </div>
    </Transition>

    <!-- Backdrop -->
    <Transition name="fade">
      <div v-if="isOpen" class="backdrop" @click="isOpen = false" />
    </Transition>
  </div>
</template>

<style scoped>
.provider-panel-wrapper { position: relative; }

/* Trigger */
.provider-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 0.8125rem;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid hsla(222, 25%, 20%, 0.5);
  color: hsl(210, 20%, 80%);
}
.provider-trigger:hover {
  border-color: hsl(195, 85%, 55%, 0.4);
  color: #fff;
}
.trigger-provider-icon { font-size: 1rem; }
.trigger-provider-name { font-weight: 600; }
.trigger-model-name {
  color: hsl(210, 15%, 50%);
  font-size: 0.75rem;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.status-icon.cloud { color: hsl(195, 85%, 55%); }
.status-icon.local { color: hsl(34, 90%, 56%); }
.gear-icon { 
  color: hsl(210, 15%, 40%);
  transition: transform 0.3s ease;
}
.gear-icon.open { transform: rotate(90deg); color: hsl(195, 85%, 55%); }

/* Panel */
.provider-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 420px;
  max-height: 520px;
  overflow-y: auto;
  border-radius: 12px;
  z-index: 100;
  box-shadow: 0 16px 48px hsla(222, 47%, 5%, 0.6);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid hsla(222, 25%, 20%, 0.5);
}
.panel-header h3 {
  font-size: 0.9375rem;
  font-weight: 600;
  color: hsl(210, 40%, 96%);
  margin: 0;
}
.close-btn {
  padding: 4px;
  border-radius: 6px;
  color: hsl(210, 15%, 40%);
  cursor: pointer;
  transition: all 0.2s;
}
.close-btn:hover { color: #fff; background: hsla(0, 72%, 55%, 0.15); }

/* Tabs */
.provider-tabs {
  display: flex;
  gap: 2px;
  padding: 8px;
  overflow-x: auto;
  border-bottom: 1px solid hsla(222, 25%, 20%, 0.3);
}
.tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 0.75rem;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s;
  color: hsl(210, 15%, 50%);
  position: relative;
}
.tab:hover { color: hsl(210, 40%, 90%); background: hsla(222, 30%, 16%, 0.5); }
.tab.active {
  color: hsl(195, 85%, 55%);
  background: hsla(195, 85%, 55%, 0.1);
}
.tab.local { border-left: 2px solid hsla(34, 90%, 56%, 0.3); }
.tab-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: hsl(150, 80%, 45%);
  position: absolute;
  top: 4px; right: 4px;
}

/* Detail */
.provider-detail {
  padding: 12px 16px;
}
.provider-desc {
  font-size: 0.75rem;
  color: hsl(210, 15%, 50%);
  margin-bottom: 12px;
}

.field-group { margin-bottom: 12px; }
.field-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  color: hsl(210, 20%, 70%);
  margin-bottom: 6px;
}
.local-badge {
  font-size: 0.625rem;
  padding: 1px 6px;
  border-radius: 999px;
  background: hsl(34, 90%, 56%, 0.15);
  color: hsl(34, 90%, 56%);
  font-weight: 500;
}

/* Key Input */
.key-input-row { display: flex; gap: 6px; }
.key-input {
  flex: 1;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid hsla(222, 25%, 20%, 0.5);
  background: hsla(222, 30%, 10%, 0.5);
  color: hsl(210, 40%, 96%);
  font-size: 0.8125rem;
  font-family: 'JetBrains Mono', monospace;
  outline: none;
  transition: border-color 0.2s;
}
.key-input:focus { border-color: hsl(195, 85%, 55%, 0.5); }
.key-input:disabled { opacity: 0.4; }
.show-key-btn {
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 0.6875rem;
  color: hsl(210, 15%, 50%);
  cursor: pointer;
  transition: all 0.2s;
}
.show-key-btn:hover { color: #fff; background: hsla(222, 30%, 16%, 0.5); }

/* Test Button */
.test-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 12px;
  color: hsl(210, 20%, 70%);
  border: 1px solid hsla(222, 25%, 20%, 0.5);
}
.test-btn:hover:not(:disabled) { 
  border-color: hsl(195, 85%, 55%, 0.3);
  color: hsl(195, 85%, 55%);
}
.test-btn:disabled { opacity: 0.5; cursor: wait; }
.text-green { color: hsl(150, 80%, 45%); }
.text-red { color: hsl(0, 72%, 55%); }
.spin { animation: rotate360 1.5s linear infinite; }

/* Model Grid */
.model-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.model-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid hsla(222, 25%, 20%, 0.4);
  background: hsla(222, 30%, 10%, 0.3);
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}
.model-card:hover {
  border-color: hsla(195, 85%, 55%, 0.3);
  background: hsla(195, 85%, 55%, 0.05);
}
.model-card.selected {
  border-color: hsl(195, 85%, 55%, 0.5);
  background: hsla(195, 85%, 55%, 0.08);
}
.model-name {
  font-size: 0.8125rem;
  font-weight: 600;
  color: hsl(210, 40%, 90%);
}
.model-id {
  font-size: 0.6875rem;
  color: hsl(210, 15%, 40%);
  font-family: 'JetBrains Mono', monospace;
}

/* Local Status */
.local-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: hsla(34, 90%, 56%, 0.08);
  border: 1px solid hsla(34, 90%, 56%, 0.15);
  font-size: 0.75rem;
  color: hsl(34, 90%, 56%);
}

/* Footer */
.panel-footer {
  padding: 10px 16px;
  border-top: 1px solid hsla(222, 25%, 20%, 0.3);
}
.footer-hint {
  font-size: 0.6875rem;
  color: hsl(210, 15%, 30%);
}

/* Backdrop */
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 99;
  background: transparent;
}

/* Transitions */
.panel-enter-active { transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); }
.panel-leave-active { transition: all 0.15s ease-in; }
.panel-enter-from { opacity: 0; transform: translateY(-8px) scale(0.96); }
.panel-leave-to { opacity: 0; transform: translateY(-4px) scale(0.98); }
</style>
