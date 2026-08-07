import { createI18n } from "vue-i18n";
import commonEn from "./locales/en/common.json";
import commonZh from "./locales/zh-CN/common.json";

export const LOCALE_STORAGE_KEY = "skyforge-locale";
export type AppLocale = "zh-CN" | "en";
export const SUPPORTED_LOCALES: AppLocale[] = ["zh-CN", "en"];
export const DEFAULT_LOCALE: AppLocale = "zh-CN";

export function detectLocale(): AppLocale {
	const saved = localStorage.getItem(LOCALE_STORAGE_KEY);
	if (saved === "zh-CN" || saved === "en") return saved;
	const nav = navigator.language?.toLowerCase() ?? "";
	return nav.startsWith("zh") ? "zh-CN" : "en";
}

export const i18n = createI18n({
	legacy: false,
	locale: DEFAULT_LOCALE,
	fallbackLocale: DEFAULT_LOCALE,
	globalInjection: true,
	missingWarn: import.meta.env.DEV,
	fallbackWarn: import.meta.env.DEV,
	messages: {
		"zh-CN": commonZh,
		en: commonEn,
	},
});

export default i18n;
