/// <reference types="vitest" />
import path from "node:path";
import vue from "@vitejs/plugin-vue";
import autoprefixer from "autoprefixer";
import tailwind from "tailwindcss";
import { defineConfig } from "vitest/config";

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
				manualChunks(id) {
					if (id.includes("monaco-editor")) return "monaco";
					if (id.includes("echarts") || id.includes("vue-echarts"))
						return "echarts";
					if (
						id.includes("node_modules/vue") ||
						id.includes("node_modules/vue-router") ||
						id.includes("node_modules/pinia")
					) {
						return "vendor";
					}
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
