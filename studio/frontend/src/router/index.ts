import { createRouter, createWebHistory } from "vue-router";

/** 路由配置
 *
 * 仅保留比赛演示所需的路由，删除 v1 时代的 /login /chat /task/:task_id 等孤立页面，
 * 以及与 / 重复的 /dashboard 别名。
 */
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
		path: "/demo",
		component: () => import("@/views/CompetitionDemo.vue"),
	},
	{
		path: "/records",
		component: () => import("@/views/RunRecords.vue"),
	},
	{
		// 回放模式：通过运行记录点击进入，加载历史任务详情
		path: "/records/:taskId",
		component: () => import("@/views/CompetitionDemo.vue"),
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
];

/** 创建路由实例 */
const router = createRouter({
	history: createWebHistory(),
	routes,
});

export default router;
