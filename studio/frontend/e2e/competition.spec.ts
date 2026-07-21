import { expect, test } from "@playwright/test";

test("demo profile stays offline and keeps the primary action visible", async ({
	page,
}) => {
	const apiRequests: string[] = [];
	page.on("request", (request) => {
		if (new URL(request.url()).pathname.startsWith("/api/"))
			apiRequests.push(request.url());
	});
	await page.route("**/api/**", (route) => route.abort("failed"));

	await page.goto("/demo");
	const requirement = page.getByLabel("航空软件需求");
	await requirement.fill(
		`${await requirement.inputValue()} 演示编辑不应触发网络请求。`,
	);
	const start = page.getByRole("button", { name: "开始可信生成" });
	await expect(start).toBeVisible();
	const box = await start.boundingBox();
	expect(box).not.toBeNull();
	expect(box?.y + box?.height).toBeLessThanOrEqual(page.viewportSize()?.height);
	expect(apiRequests).toEqual([]);

	await start.click();
	await expect(page.getByText("评委摘要：证据在首屏完成闭环")).toBeVisible({
		timeout: 10_000,
	});
	for (const tab of ["修复对比", "契约", "仿真", "追溯", "证据"]) {
		await expect(
			page.getByRole("button", { name: tab, exact: true }),
		).toBeVisible();
	}
	expect(apiRequests).toEqual([]);
});

test("model configuration is backend-managed and never refills the stored key", async ({
	page,
}) => {
	await page.goto("/settings");
	await page.getByRole("button", { name: "配置 LLM 连接" }).click();
	await expect(page.getByRole("dialog")).toBeVisible();
	await expect(page.getByText("云 API", { exact: true }).first()).toBeVisible();

	const secretInput = page.locator('input[placeholder*="留空表示不修改"]');
	await expect(secretInput).toBeVisible();
	await expect(secretInput).toHaveValue("");
	await expect(secretInput).toHaveAttribute("type", "password");
});
