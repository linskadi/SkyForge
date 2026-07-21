/**
 * useConfirm - 全局确认弹窗 composable
 * ====================================================================
 * 替代 window.confirm / window.alert 的 Promise + Dialog 实现。
 *
 * 设计要点：
 * 1. 单例 reactive state：所有组件共享同一个确认弹窗实例；
 * 2. confirm() 返回 Promise<boolean>，true=确认 / false=取消；
 * 3. ConfirmDialog.vue 组件挂载在 App.vue 顶层，订阅 state 自动显示；
 * 4. 同时提供 alert() 替代 window.alert（无取消按钮，仅"知道了"）。
 *
 * 用法：
 * ```ts
 * import { useConfirm } from "@/composables/useConfirm";
 * const { confirm, alert } = useConfirm();
 * const ok = await confirm("确定要删除吗？");
 * if (!ok) return;
 * await alert("操作完成");
 * ```
 */
import { ref } from "vue";

/** 确认弹窗共享状态 */
interface ConfirmState {
	/** 是否显示弹窗 */
	open: boolean;
	/** 弹窗标题 */
	title: string;
	/** 弹窗正文（支持多行） */
	message: string;
	/** 确认按钮文本 */
	confirmText: string;
	/** 取消按钮文本 */
	cancelText: string;
	/** 是否为 alert 模式（仅显示确认按钮，无取消） */
	alertMode: boolean;
	/** 确认按钮 variant（默认 / destructive） */
	variant: "default" | "destructive";
}

const DEFAULT_STATE: ConfirmState = {
	open: false,
	title: "确认操作",
	message: "",
	confirmText: "确定",
	cancelText: "取消",
	alertMode: false,
	variant: "default",
};

/** 全局单例 state（所有 useConfirm 调用共享） */
const state = ref<ConfirmState>({ ...DEFAULT_STATE });

/** 当前未完成的 Promise resolver（confirm/alert 调用时赋值，按钮点击时调用） */
let resolvePromise: ((value: boolean) => void) | null = null;

/** 关闭弹窗并 resolve Promise */
function closeDialog(result: boolean): void {
	state.value.open = false;
	if (resolvePromise) {
		resolvePromise(result);
		resolvePromise = null;
	}
}

/**
 * 显示确认弹窗，返回 Promise<boolean>
 *
 * @param message 弹窗正文（支持 \n 换行）
 * @param options 可选配置：title / confirmText / cancelText / variant
 * @returns true=点击确认 / false=点击取消或关闭弹窗
 */
function confirm(
	message: string,
	options: {
		title?: string;
		confirmText?: string;
		cancelText?: string;
		variant?: "default" | "destructive";
	} = {},
): Promise<boolean> {
	// 若已有弹窗打开，先关闭并按"取消"resolve 旧 Promise，避免泄漏
	if (state.value.open) {
		closeDialog(false);
	}
	state.value = {
		open: true,
		title: options.title ?? "确认操作",
		message,
		confirmText: options.confirmText ?? "确定",
		cancelText: options.cancelText ?? "取消",
		alertMode: false,
		variant: options.variant ?? "default",
	};
	return new Promise<boolean>((resolve) => {
		resolvePromise = resolve;
	});
}

/**
 * 显示提示弹窗（仅确认按钮），替代 window.alert
 *
 * @param message 提示正文（支持 \n 换行）
 * @param options 可选配置：title / confirmText
 */
function alert(
	message: string,
	options: {
		title?: string;
		confirmText?: string;
	} = {},
): Promise<void> {
	if (state.value.open) {
		closeDialog(false);
	}
	state.value = {
		open: true,
		title: options.title ?? "提示",
		message,
		confirmText: options.confirmText ?? "知道了",
		cancelText: "",
		alertMode: true,
		variant: "default",
	};
	return new Promise<void>((resolve) => {
		resolvePromise = () => resolve();
	});
}

/** ConfirmDialog 组件使用的 API：响应式 state + 按钮回调 */
export function useConfirm() {
	return {
		confirmState: state,
		confirm,
		alert,
		/** 确认按钮点击：resolve(true) */
		handleConfirm: () => closeDialog(true),
		/** 取消按钮 / 关闭弹窗：resolve(false) */
		handleCancel: () => closeDialog(false),
	};
}
