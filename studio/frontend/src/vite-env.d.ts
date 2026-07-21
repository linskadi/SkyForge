/// <reference types="vite/client" />

declare module "*.vue" {
	import type { DefineComponent } from "vue";

	// biome-ignore lint/suspicious/noExplicitAny: Vue 组件类型声明需要 any
	// biome-ignore lint/complexity/noBannedTypes: Vue 组件类型声明需要 {}
	const component: DefineComponent<{}, {}, any>;
	export default component;
}

declare module "*.json" {
	const value: Record<string, unknown>;
	export default value;
}
