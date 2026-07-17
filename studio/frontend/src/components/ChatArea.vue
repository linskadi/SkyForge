<script setup lang="ts">
/**
 * ChatArea 聊天区域组件（虚拟滚动）
 */
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Message } from "@/utils/response";
import { useVirtualizer } from "@tanstack/vue-virtual";
import { Send } from "lucide-vue-next";
import { nextTick, ref, watch } from "vue";
import Bubble from "./Bubble.vue";
import SystemMessage from "./SystemMessage.vue";

const props = defineProps<{ messages: Message[] }>();

const inputValue = ref("");
const inputRef = ref<HTMLInputElement | null>(null);
const scrollRef = ref<HTMLDivElement | null>(null);

/** 虚拟滚动 */
const virtualizer = useVirtualizer({
	count: props.messages.length,
	getScrollElement: () => scrollRef.value,
	estimateSize: () => 80,
	overscan: 10,
});

watch(
	() => props.messages,
	() => {
		nextTick(() => {
			virtualizer.value.setOptions({
				...virtualizer.value.options,
				count: props.messages.length,
			});
			if (props.messages.length > 0) {
				virtualizer.value.scrollToIndex(props.messages.length - 1, {
					align: "end",
				});
			}
		});
	},
);

const sendMessage = () => {
	if (!inputValue.value.trim()) return;
	inputValue.value = "";
	inputRef.value?.focus();
};
</script>

<template>
  <div class="chat-area">
    <div ref="scrollRef" class="chat-messages">
      <div
        :style="{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }"
      >
        <div
          v-for="virtualRow in virtualizer.getVirtualItems()"
          :key="String(virtualRow.key)"
          class="message-wrapper"
          :style="{
            position: 'absolute',
            top: `${virtualRow.start}px`,
            left: 0,
            right: 0,
          }"
        >
          <Bubble
            v-if="messages[virtualRow.index].msg_type === 'user'"
            type="user"
            :content="messages[virtualRow.index].content || ''"
          />
          <Bubble
            v-else-if="messages[virtualRow.index].msg_type === 'agent'"
            type="agent"
            :agentType="('agent_type' in messages[virtualRow.index] ? (messages[virtualRow.index] as any).agent_type : 'SYSTEM') as any"
            :content="messages[virtualRow.index].content || ''"
          />
          <SystemMessage
            v-else-if="messages[virtualRow.index].msg_type === 'system'"
            :content="messages[virtualRow.index].content || ''"
            :type="'type' in messages[virtualRow.index] ? (messages[virtualRow.index] as any).type : undefined"
          />
        </div>
      </div>
    </div>
    <form class="chat-input" @submit.prevent="sendMessage">
      <Input ref="inputRef" v-model="inputValue" type="text" placeholder="请输入消息..." class="flex-1" autocomplete="off" />
      <Button type="submit" :disabled="!inputValue.trim()">
        <Send />
      </Button>
    </form>
  </div>
</template>

<style scoped>
.chat-area {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 12px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
}

.chat-messages::-webkit-scrollbar { width: 4px; }
.chat-messages::-webkit-scrollbar-track { background: transparent; }
.chat-messages::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 9999px; }
.chat-messages::-webkit-scrollbar-thumb:hover { background: #9ca3af; }

.message-wrapper {
  padding-bottom: 12px;
}

.chat-input {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 16px;
  max-width: 42rem;
  margin: 0 auto;
  width: 100%;
}
</style>
