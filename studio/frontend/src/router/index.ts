import { createRouter, createWebHistory } from "vue-router";

const routes = [
	{
		path: "/",
		component: () => import("@/pages/dashboard/index.vue"),
	},
	{
		path: "/generate",
		component: () => import("@/views/Generate.vue"),
	},
	{
		path: "/records",
		component: () => import("@/views/RunRecords.vue"),
	},
	{
		path: "/records/:taskId",
		component: () => import("@/views/Generate.vue"),
		props: true,
	},
	{
		path: "/lab",
		component: () => import("@/views/CapabilityLab.vue"),
	},
	{
		path: "/settings",
		component: () => import("@/views/SystemSettings.vue"),
	},
	{
		path: "/compose",
		component: () => import("@/views/Compose.vue"),
	},
	{
		path: "/misra",
		component: () => import("@/pages/misra/index.vue"),
	},
	{
		path: "/hitl",
		component: () => import("@/views/HITLPage.vue"),
	},
	{
		path: "/architecture",
		name: "Architecture",
		component: () => import("@/views/ArchitectureView.vue"),
		meta: { title: "六层架构" },
	},
	{
		path: "/compliance",
		component: () => import("@/views/ComplianceAudit.vue"),
	},
];

/** 创建路由实例 */
const router = createRouter({
	history: createWebHistory(),
	routes,
});

export default router;
