<script setup lang="ts">
import { Brain, Code, FileText, Shield } from "@lucide/vue";
import { ref } from "vue";
import { Badge } from "@/components/ui/badge";
/**
 * DecisionTrace - 决策追溯组件
 *
 * 展示每个Agent的：
 * - 输入提示词（Prompt）
 * - LLM思考过程
 * - 决策依据
 * - 输出结果
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface AgentDecision {
	agent: string;
	prompt: string;
	reasoning: string;
	output: string;
	timestamp: number;
}

interface Props {
	decisions: AgentDecision[];
}

defineProps<Props>();
const expandedIndex = ref<number | null>(null);

const toggleExpand = (index: number) => {
	expandedIndex.value = expandedIndex.value === index ? null : index;
};

const getAgentIcon = (agent: string) => {
	if (agent.includes("REQ")) return FileText;
	if (agent.includes("CON") || agent.includes("CODE")) return Code;
	if (agent.includes("REPAIR")) return Shield;
	return Brain;
};

const getAgentColor = (agent: string) => {
	if (agent.includes("REQ")) return "bg-blue-500";
	if (agent.includes("CON")) return "bg-purple-500";
	if (agent.includes("CODE")) return "bg-green-500";
	if (agent.includes("REPAIR")) return "bg-orange-500";
	return "bg-gray-500";
};
</script>

<template>
	<Card class="w-full">
		<CardHeader>
			<CardTitle class="flex items-center gap-2 text-lg">
				<Brain class="h-5 w-5" />
				决策追溯
			</CardTitle>
		</CardHeader>
		<CardContent>
			<div v-if="decisions.length === 0" class="text-center text-gray-500 py-8">
				暂无决策记录
			</div>
			<div v-else class="space-y-3">
				<div
					v-for="(decision, index) in decisions"
					:key="index"
					class="border rounded-lg overflow-hidden"
				>
					<!-- Agent Header -->
					<div
						class="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-50"
						@click="toggleExpand(index)"
					>
						<div class="flex items-center gap-3">
							<div :class="['w-8 h-8 rounded-full flex items-center justify-center text-white', getAgentColor(decision.agent)]">
								<component :is="getAgentIcon(decision.agent)" class="h-4 w-4" />
							</div>
							<div>
								<div class="font-medium">{{ decision.agent }}</div>
								<div class="text-xs text-gray-500">
									{{ new Date(decision.timestamp).toLocaleString() }}
								</div>
							</div>
						</div>
						<Badge variant="outline">
							{{ expandedIndex === index ? '收起' : '展开' }}
						</Badge>
					</div>
					
					<!-- Expanded Content -->
					<div v-if="expandedIndex === index" class="p-4 border-t bg-gray-50">
						<!-- Prompt -->
						<div class="mb-4">
							<div class="text-sm font-medium text-gray-700 mb-2">输入提示词</div>
							<pre class="bg-white p-3 rounded text-xs overflow-auto max-h-40 border">{{ decision.prompt }}</pre>
						</div>
						
						<!-- Reasoning -->
						<div class="mb-4">
							<div class="text-sm font-medium text-gray-700 mb-2">思考过程</div>
							<div class="bg-white p-3 rounded text-sm border whitespace-pre-wrap">{{ decision.reasoning }}</div>
						</div>
						
						<!-- Output -->
						<div>
							<div class="text-sm font-medium text-gray-700 mb-2">输出结果</div>
							<pre class="bg-white p-3 rounded text-xs overflow-auto max-h-60 border">{{ decision.output }}</pre>
						</div>
					</div>
				</div>
			</div>
		</CardContent>
	</Card>
</template>
