import { createI18n } from "vue-i18n";

/**
 * 测试用 i18n 实例：直接加载真实 zh-CN locale 文件，
 * 使组件测试无需联网即可断言中文文案。
 */
const zhModules = import.meta.glob("../i18n/locales/zh-CN/*.json", {
	eager: true,
	import: "default",
}) as Record<string, Record<string, unknown>>;

// 与应用一致：模块根键平铺合并。common 最后加载，
// 避免 lab 等其他模块的同名根键（如 waveform）覆盖公共文案。
const orderedPaths = Object.keys(zhModules).sort((a, b) => {
	const aCommon = a.includes("common.json") ? 1 : 0;
	const bCommon = b.includes("common.json") ? 1 : 0;
	return aCommon - bCommon;
});

const zhMessages: Record<string, Record<string, unknown>> = {};
for (const p of orderedPaths) {
	const mod = zhModules[p] as Record<string, unknown>;
	for (const ns of Object.keys(mod)) {
		zhMessages[ns] = mod[ns] as Record<string, unknown>;
	}
}

export function createTestI18n(locale = "zh-CN") {
	return createI18n({
		legacy: false,
		globalInjection: true,
		locale,
		fallbackLocale: "zh-CN",
		messages: { "zh-CN": zhMessages },
	});
}
