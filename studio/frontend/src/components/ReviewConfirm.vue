<script setup lang="ts">
import { Check, MessageSquare, X } from "@lucide/vue";
import { ref } from "vue";
import { Badge } from "@/components/ui/badge";
/**
 * ReviewConfirm - 人工审核确认组件
 *
 * 在Agent执行完成后显示审核确认按钮
 * 记录审核决策和评论
 */
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

interface Props {
	stage: string;
	content: string;
}

defineProps<Props>();

const emit = defineEmits<{
	(e: "approve", comment: string): void;
	(e: "reject", comment: string): void;
}>();

const comment = ref("");
const reviewed = ref(false);
const decision = ref<"approved" | "rejected" | null>(null);

const handleApprove = () => {
	reviewed.value = true;
	decision.value = "approved";
	emit("approve", comment.value);
};

const handleReject = () => {
	reviewed.value = true;
	decision.value = "rejected";
	emit("reject", comment.value);
};
</script>

<template>
	<Card class="w-full border-2 border-dashed border-blue-200 bg-blue-50">
		<CardHeader>
			<CardTitle class="flex items-center gap-2 text-lg text-blue-700">
				<MessageSquare class="h-5 w-5" />
				人工审核确认
			</CardTitle>
		</CardHeader>
		<CardContent>
			<!-- Stage Info -->
			<div class="mb-4">
				<Badge variant="outline" class="mb-2">{{ stage }}</Badge>
				<div class="text-sm text-gray-600">{{ content }}</div>
			</div>
			
			<!-- Comment Input -->
			<div class="mb-4">
				<label class="text-sm font-medium text-gray-700 mb-2 block">审核意见（可选）</label>
				<Textarea
					v-model="comment"
					placeholder="请输入审核意见..."
					class="min-h-[80px]"
				/>
			</div>
			
			<!-- Action Buttons -->
			<div class="flex gap-3">
				<Button 
					variant="outline" 
					class="flex-1"
					@click="handleReject"
					:disabled="reviewed"
				>
					<X class="h-4 w-4 mr-2" />
					拒绝
				</Button>
				<Button 
					class="flex-1 bg-green-600 hover:bg-green-700"
					@click="handleApprove"
					:disabled="reviewed"
				>
					<Check class="h-4 w-4 mr-2" />
					通过
				</Button>
			</div>
			
			<!-- Review Status -->
			<div v-if="reviewed" class="mt-4 p-3 rounded" :class="decision === 'approved' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'">
				{{ decision === 'approved' ? '✅ 已通过审核' : '❌ 已拒绝' }}
			</div>
		</CardContent>
	</Card>
</template>
