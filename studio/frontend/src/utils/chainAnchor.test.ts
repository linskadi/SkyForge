import { describe, expect, it } from "vitest";
import {
	buildAnchorPayload,
	canonicalJson,
	isValidHash,
	normalizeHash,
	toBytes32,
} from "@/utils/chainAnchor";

describe("canonicalJson", () => {
	it("sorts keys recursively", () => {
		const out = canonicalJson({ b: 1, a: { d: 4, c: 3 } });
		expect(out).toBe('{"a":{"c":3,"d":4},"b":1}');
	});

	it("uses compact separators", () => {
		expect(canonicalJson({ x: [1, 2] })).toBe('{"x":[1,2]}');
	});

	it("keeps unicode verbatim", () => {
		expect(canonicalJson({ name: "航空证据" })).toContain("航空证据");
	});

	it("produces identical output regardless of input key order", () => {
		expect(canonicalJson({ a: 1, b: 2 })).toBe(canonicalJson({ b: 2, a: 1 }));
	});
});

describe("buildAnchorPayload", () => {
	it("normalizes missing metrics", () => {
		const payload = buildAnchorPayload({});
		expect(payload.requirements.count).toBe(0);
		expect(payload.code.lines).toBe(0);
		expect(payload.verification.misra_violations).toBe(0);
		expect(payload.verification.contract_passed).toBe(false);
	});

	it("extracts metrics from nested or flat shapes", () => {
		const nested = buildAnchorPayload({
			metrics: { code_lines: 128, misra_violations: 2, contract_passed: true },
		});
		expect(nested.code.lines).toBe(128);
		expect(nested.verification.misra_violations).toBe(2);
		expect(nested.verification.contract_passed).toBe(true);

		const flat = buildAnchorPayload({ coverage: { lines: 64 } });
		expect(flat.code.lines).toBe(64);
	});

	it("is deterministic across key orders", () => {
		const a = buildAnchorPayload({
			language: "C",
			metrics: { code_lines: 10 },
		});
		const b = buildAnchorPayload({
			metrics: { code_lines: 10 },
			language: "C",
		});
		expect(canonicalJson(a)).toBe(canonicalJson(b));
	});
});

describe("hash formatting", () => {
	it("toBytes32 accepts 64-hex without 0x prefix", () => {
		const hex = "a".repeat(64);
		expect(toBytes32(hex)).toBe(`0x${hex}`);
	});

	it("toBytes32 rejects wrong length", () => {
		expect(() => toBytes32("abc")).toThrow();
	});

	it("normalizeHash adds 0x prefix when missing", () => {
		expect(normalizeHash("ABC")).toBe("0xabc");
		expect(normalizeHash("0xABC")).toBe("0xabc");
	});

	it("isValidHash validates format", () => {
		expect(isValidHash(`0x${"a".repeat(64)}`)).toBe(true);
		expect(isValidHash("abc")).toBe(false);
		expect(isValidHash(`0x${"a".repeat(63)}`)).toBe(false);
	});
});
