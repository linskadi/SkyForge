/// <reference types="vitest" />
import path from "node:path";
import vue from "@vitejs/plugin-vue";
import autoprefixer from "autoprefixer";
import tailwind from "tailwindcss";
import { defineConfig } from "vite";

export default defineConfig({
	css: {
		postcss: {
			plugins: [tailwind(), autoprefixer()],
		},
	},
	plugins: [vue()],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "./src"),
		},
	},
	build: {
		rollupOptions: {
			output: {
				manualChunks: {
					monaco: ["monaco-editor"],
					echarts: ["echarts", "vue-echarts"],
					vendor: ["vue", "vue-router", "pinia"],
				},
			},
		},
		chunkSizeWarningLimit: 1000,
	},
	test: {
		environment: "jsdom",
		globals: true,
		include: ["src/**/*.{test,spec}.{ts,tsx}"],
		alias: {
			"@": path.resolve(__dirname, "./src"),
		},
	},
});
