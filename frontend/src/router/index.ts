import { createRouter, createWebHistory } from "vue-router";

/** 路由配置 */
const routes = [
	{
		path: "/",
		component: () => import("@/pages/index.vue"),
	},
	{
		path: "/login",
		component: () => import("@/pages/login/index.vue"),
	},
	{
		path: "/chat",
		component: () => import("@/pages/chat/index.vue"),
	},
	{
		path: "/task/:task_id",
		component: () => import("@/pages/task/index.vue"),
		props: true,
	},
	// AirborneAI - Day 1 需求输入页（Patch 4）
	{
		path: "/generate",
		component: () => import("@/views/Generate.vue"),
	},
	// AirborneAI - 组件组合验证页
	{
		path: "/compose",
		component: () => import("@/views/Compose.vue"),
	},
	// AirborneAI - HIL 人机协作审批页（也可集成在 Generate.vue 侧边栏）
	{
		path: "/hil",
		component: () => import("@/views/HILPage.vue"),
	},
];

/** 创建路由实例 */
const router = createRouter({
	history: createWebHistory(),
	routes,
});

export default router;
