import { describe, it, expect } from "vitest";
import { escapeHtml, buildReport } from "./reportGenerator";
import type { GenerateResult } from "@/types/domain";

describe("escapeHtml", () => {
  it("escapes ampersand", () => {
    expect(escapeHtml("a&b")).toBe("a&amp;b");
  });

  it("escapes angle brackets", () => {
    expect(escapeHtml("<script>")).toBe("&lt;script&gt;");
  });

  it("escapes quotes", () => {
    expect(escapeHtml('"hello"')).toBe("&quot;hello&quot;");
    expect(escapeHtml("'hello'")).toBe("&#039;hello&#039;");
  });

  it("handles empty string", () => {
    expect(escapeHtml("")).toBe("");
  });

  it("prevents XSS by escaping HTML tags", () => {
    const malicious = '<img src=x onerror="alert(1)">';
    const escaped = escapeHtml(malicious);
    expect(escaped).not.toContain("<img");
    expect(escaped).toContain("&lt;img");
  });
});

describe("buildReport", () => {
  const mockResult: GenerateResult = {
    code: "double filter(double input) { return input; }",
    traceability: { "REQ-001": [1, 2, 3] },
    violations: [],
    repair_history: [],
    contract: {
      component: "test_filter",
      description: "测试滤波器组件",
      inputs: {},
      outputs: {},
      preconditions: [],
      postconditions: [],
      invariants: [],
      fault_handling: [],
    },
    contract_check_result: {
      component: "test_filter",
      overall_passed: true,
      total_count: 3,
      passed_count: 3,
      sections: [
        {
          title: "前置条件",
          key: "preconditions",
          items: [
            { id: "PRE-1", expression: "input != NULL", passed: true, assert_code: "" },
          ],
        },
        {
          title: "后置条件",
          key: "postconditions",
          items: [
            { id: "POST-1", expression: "output >= 0", passed: true, assert_code: "" },
            { id: "POST-2", expression: "output <= 20000", passed: true, assert_code: "" },
          ],
        },
      ],
      generated_assert_code: "",
    },
    simulation_result: {
      passed: true,
      total_steps: 200,
      fault_type: null,
      fault_params: {},
      input_waveform: [],
      output_waveform: [],
      fault_range: null,
      contract_violation: null,
      statistics: {
        total_steps: 200,
        input_range: [0, 65535],
        output_range: [0, 65535],
        output_max: 65535,
        output_min: 0,
        output_mean: 32768,
      },
      logs: [],
    },
  };

  it("returns reportId, summary, and html", () => {
    const { reportId, summary, html } = buildReport(mockResult);
    expect(reportId).toMatch(/^DO178C-REPORT-/);
    expect(summary.title).toContain("test_filter");
    expect(html).toContain("<!DOCTYPE html>");
  });

  it("summary has correct traceability count", () => {
    const { summary } = buildReport(mockResult);
    expect(summary.traceability_entries).toBe(1);
  });

  it("summary has 0 MISRA violations when none", () => {
    const { summary } = buildReport(mockResult);
    expect(summary.misra_violations).toBe(0);
  });

  it("html escapes user content in component name", () => {
    const result = {
      ...mockResult,
      contract: { ...mockResult.contract, component: 'xss<script>alert(1)</script>' },
    };
    const { html } = buildReport(result);
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("passed simulation produces success summary", () => {
    const { summary } = buildReport(mockResult);
    expect(summary.simulation_summary).toContain("通过");
  });

  it("failed simulation produces failure summary", () => {
    const result = {
      ...mockResult,
      simulation_result: { ...mockResult.simulation_result, passed: false },
    };
    const { summary } = buildReport(result);
    expect(summary.simulation_summary).toContain("违约");
  });
});
