import { ref } from "vue";
import {
	type AppLocale,
	DEFAULT_LOCALE,
	detectLocale,
	i18n,
	LOCALE_STORAGE_KEY,
} from "./index";
import { loadCommon, loadLocaleModule } from "./loader";

export const currentLocale = ref<AppLocale>(detectLocale());

function applyLocale(locale: AppLocale) {
	currentLocale.value = locale;
	(i18n.global.locale as { value: AppLocale }).value = locale;
	document.documentElement.lang = locale;
	localStorage.setItem(LOCALE_STORAGE_KEY, locale);
	const title = i18n.global.t("appTitle") as string;
	if (title) document.title = title;
}

export function initLocale(): void {
	applyLocale(currentLocale.value);
	void Promise.all([
		loadCommon(currentLocale.value),
		loadLocaleModule(currentLocale.value, "data"),
	]);
}

export async function setLocale(
	locale: AppLocale,
	module?: Parameters<typeof loadLocaleModule>[1],
): Promise<void> {
	if (locale === currentLocale.value) return;
	// 先加载目标语言模块（common/data + 当前页模块），再切换激活语言，
	// 避免切换瞬间目标语言模块尚未就绪而闪现原始 key 文本。
	await Promise.all([loadCommon(locale), loadLocaleModule(locale, "data")]);
	if (module) await loadLocaleModule(locale, module);
	applyLocale(locale);
}

export function toggleLocale(
	module?: Parameters<typeof loadLocaleModule>[1],
): Promise<void> {
	return setLocale(currentLocale.value === "zh-CN" ? "en" : "zh-CN", module);
}

export function useLocale() {
	return {
		locale: currentLocale,
		isZh: () => currentLocale.value === "zh-CN",
		setLocale,
		toggleLocale,
	};
}

export { DEFAULT_LOCALE };
