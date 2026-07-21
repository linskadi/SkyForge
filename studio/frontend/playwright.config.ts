import { defineConfig } from "@playwright/test";

export default defineConfig({
	testDir: "./e2e",
	timeout: 30_000,
	fullyParallel: true,
	reporter: "list",
	use: {
		baseURL: "http://localhost:5173",
		browserName: "chromium",
		channel: "msedge",
		colorScheme: "light",
		screenshot: "only-on-failure",
		trace: "retain-on-failure",
	},
	webServer: {
		command: "pnpm dev",
		url: "http://localhost:5173",
		reuseExistingServer: true,
		timeout: 30_000,
	},
	projects: [
		{ name: "laptop-150pct", use: { viewport: { width: 1707, height: 950 } } },
		{ name: "projector-1366", use: { viewport: { width: 1366, height: 768 } } },
	],
});
