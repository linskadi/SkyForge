import { type AppLocale, i18n } from "./index";

export type LocaleModuleKey =
	| "common"
	| "dashboard"
	| "generate"
	| "records"
	| "lab"
	| "compose"
	| "misra"
	| "hitl"
	| "anchor"
	| "architecture"
	| "compliance"
	| "settings"
	| "data";

// common 已在 index.ts 中静态打包（zh-CN 与 en），从动态 glob 中排除，
// 避免同一模块被同时静态与动态导入（INEFFECTIVE_DYNAMIC_IMPORT）。
const modules = import.meta.glob<Record<string, unknown>>([
	"./locales/**/*.json",
	"!./locales/**/common.json",
]);

const loaded = new Set<string>();

export async function loadLocaleModule(
	locale: AppLocale,
	module: LocaleModuleKey,
): Promise<void> {
	const key = `${module}:${locale}`;
	if (loaded.has(key)) return;
	const path = `./locales/${locale}/${module}.json`;
	const loader = modules[path];
	if (!loader) {
		if (import.meta.env.DEV) {
			console.warn(`[i18n] locale module not found: ${path}`);
		}
		return;
	}
	const messages = await loader();
	loaded.add(key);
	i18n.global.setLocaleMessage(locale, {
		...(i18n.global.getLocaleMessage(locale) as Record<string, unknown>),
		...messages,
	} as never);
}

/**
 * 公共模块（common）已在 index.ts 中静态打包（zh-CN 与 en 各预置基础消息），
 * 无需再通过动态 import 加载，此处仅保留调用约定以兼容 useLocale。
 */
export function loadCommon(_locale: AppLocale): Promise<void> {
	return Promise.resolve();
}
