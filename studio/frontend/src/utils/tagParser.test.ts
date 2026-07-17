import { describe, expect, it, vi } from "vitest";
import { parseConTags, parseInlineTags } from "./tagParser";

vi.mock("@/services/mockApi", () => ({
	MISRA_RULE_DOCS: {
		"MISRA-Rule-8.13": "指针参数应声明为 const",
		"MISRA-Rule-21.3": "不得使用动态内存分配",
	},
}));

describe("parseInlineTags", () => {
	it("returns plain text when no tags present", () => {
		const tokens = parseInlineTags("hello world");
		expect(tokens).toEqual([{ type: "text", value: "hello world" }]);
	});

	it("parses REQ tags", () => {
		const tokens = parseInlineTags("实现 [REQ-001] 功能");
		expect(tokens).toEqual([
			{ type: "text", value: "实现 " },
			{ type: "req", value: "REQ-001" },
			{ type: "text", value: " 功能" },
		]);
	});

	it("parses MISRA-Rule tags with documentation", () => {
		const tokens = parseInlineTags("代码违反 [MISRA-Rule-8.13]");
		expect(tokens).toEqual([
			{ type: "text", value: "代码违反 " },
			{
				type: "misra",
				value: "MISRA-Rule-8.13",
				doc: "指针参数应声明为 const",
			},
		]);
	});

	it("parses CON tags", () => {
		const tokens = parseInlineTags("契约 [CON-001-POST-001] 已满足");
		expect(tokens).toEqual([
			{ type: "text", value: "契约 " },
			{ type: "con", value: "CON-001-POST-001" },
			{ type: "text", value: " 已满足" },
		]);
	});

	it("parses mixed tags in one line", () => {
		const tokens = parseInlineTags("[REQ-001] 对应 [MISRA-Rule-21.3] 规则");
		// REQ-001 + " 对应 " + MISRA-Rule-21.3 + " 规则" = 4 tokens
		expect(tokens.length).toBeGreaterThanOrEqual(3);
		expect(tokens[0]).toEqual({ type: "req", value: "REQ-001" });
		const misraToken = tokens.find((t) => t.type === "misra");
		expect(misraToken).toEqual({
			type: "misra",
			value: "MISRA-Rule-21.3",
			doc: "不得使用动态内存分配",
		});
	});

	it("handles unknown MISRA rules gracefully", () => {
		const tokens = parseInlineTags("[MISRA-Rule-99.99]");
		expect(tokens[0]).toEqual({
			type: "misra",
			value: "MISRA-Rule-99.99",
			doc: "未收录规则说明：MISRA-Rule-99.99",
		});
	});

	it("handles empty string", () => {
		const tokens = parseInlineTags("");
		expect(tokens).toEqual([]);
	});
});

describe("parseConTags", () => {
	it("returns plain text when no CON tags", () => {
		const tokens = parseConTags("hello world");
		expect(tokens).toEqual([{ type: "text", value: "hello world" }]);
	});

	it("parses CON tags", () => {
		const tokens = parseConTags("[CON-001-POST-001] and [CON-002-PRE-000]");
		expect(tokens).toEqual([
			{ type: "con", value: "CON-001-POST-001" },
			{ type: "text", value: " and " },
			{ type: "con", value: "CON-002-PRE-000" },
		]);
	});

	it("ignores REQ and MISRA tags", () => {
		const tokens = parseConTags("[REQ-001] and [MISRA-Rule-8.13]");
		expect(tokens).toEqual([
			{ type: "text", value: "[REQ-001] and [MISRA-Rule-8.13]" },
		]);
	});
});
