<script setup lang="ts">
/**
 * ConfirmDialog - 全局确认/提示弹窗组件
 *
 * 配合 useConfirm composable 使用，挂载在 App.vue 顶层。
 * - confirm 模式：显示「取消」+「确定」两个按钮
 * - alert 模式：仅显示「知道了」按钮
 *
 * 使用 reka-ui 的 Dialog 组件实现可访问性（焦点陷阱 / ESC 关闭 / 点击遮罩关闭）。
 */
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { useConfirm } from "@/composables/useConfirm";

const { confirmState, handleConfirm, handleCancel } = useConfirm();

/** ESC / 点击遮罩关闭时按"取消"处理（与 window.confirm 行为一致） */
function onInteractOutside(event: Event) {
	event.preventDefault();
	handleCancel();
}

function onEscapeKeyDown(event: KeyboardEvent) {
	event.preventDefault();
	handleCancel();
}
</script>

<template>
  <Dialog :open="confirmState.open" @update:open="(v: boolean) => { if (!v) handleCancel(); }">
    <DialogContent
      class="max-w-md"
      @interact-outside="onInteractOutside"
      @escape-key-down="onEscapeKeyDown"
    >
      <DialogHeader>
        <DialogTitle>{{ confirmState.title }}</DialogTitle>
        <DialogDescription class="whitespace-pre-wrap text-foreground/80">
          {{ confirmState.message }}
        </DialogDescription>
      </DialogHeader>
      <DialogFooter class="gap-2 sm:gap-2">
        <Button
          v-if="!confirmState.alertMode"
          variant="outline"
          @click="handleCancel"
        >
          {{ confirmState.cancelText }}
        </Button>
        <Button
          :variant="confirmState.alertMode ? 'default' : confirmState.variant"
          @click="handleConfirm"
        >
          {{ confirmState.confirmText }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
