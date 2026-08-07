import { createRouter, createWebHistory } from "vue-router";
import { i18n } from "@/i18n";
import { type LocaleModuleKey, loadLocaleModule } from "@/i18n/loader";
import { currentLocale } from "@/i18n/useLocale";

const routes: {
	path: string;
	name?: string;
	component: () => Promise<unknown>;
	props?: boolean;
	meta?: { locale?: LocaleModuleKey; title?: string };
}[] = [
	{
		path: "/",
		component: () => import("@/pages/dashboard/index.vue"),
		meta: { locale: "dashboard", title: "dashboard" },
	},
	{
		path: "/generate",
		component: () => import("@/views/Generate.vue"),
		meta: { locale: "generate", title: "generate" },
	},
	{
		path: "/records",
		component: () => import("@/views/RunRecords.vue"),
		meta: { locale: "records", title: "records" },
	},
	{
		path: "/records/:taskId",
		component: () => import("@/views/Generate.vue"),
		props: true,
		meta: { locale: "generate", title: "generate" },
	},
	{
		path: "/lab",
		component: () => import("@/views/CapabilityLab.vue"),
		meta: { locale: "lab", title: "lab" },
	},
	{
		path: "/settings",
		component: () => import("@/views/SystemSettings.vue"),
		meta: { locale: "settings", title: "settings" },
	},
	{
		path: "/compose",
		component: () => import("@/views/Compose.vue"),
		meta: { locale: "compose", title: "compose" },
	},
	{
		path: "/misra",
		component: () => import("@/pages/misra/index.vue"),
		meta: { locale: "misra", title: "misra" },
	},
	{
		path: "/hitl",
		component: () => import("@/views/HITLPage.vue"),
		meta: { locale: "hitl", title: "hitl" },
	},
	{
		path: "/anchor",
		component: () => import("@/views/ChainAnchor.vue"),
		meta: { locale: "anchor", title: "anchor" },
	},
	{
		path: "/architecture",
		name: "Architecture",
		component: () => import("@/views/ArchitectureView.vue"),
		meta: { locale: "architecture", title: "architecture" },
	},
	{
		path: "/compliance",
		component: () => import("@/views/ComplianceAudit.vue"),
		meta: { locale: "compliance", title: "compliance" },
	},
];

/** 创建路由实例 */
const router = createRouter({
	history: createWebHistory(),
	routes,
});

router.afterEach((to) => {
	const localeModule = to.meta.locale as LocaleModuleKey | undefined;
	if (localeModule) {
		void loadLocaleModule(currentLocale.value, localeModule);
	}
	const titleKey = to.meta.title as string | undefined;
	if (titleKey) {
		const title = i18n.global.t(`routes.${titleKey}`);
		if (title && title !== `routes.${titleKey}`) {
			document.title = title;
		}
	}
});

export default router;
