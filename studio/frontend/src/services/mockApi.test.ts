import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MOCK_AGENT_LOGS } from "@/mock/data";
import {
	MOCK_AGENT_INTERVAL_SEC,
	MOCK_AGENT_TOTAL_DURATION_MS,
	mockGenerate,
} from "./mockApi";

describe("mockApi - MOCK_AGENT 总时长常量", () => {
	it("MOCK_AGENT_INTERVAL_SEC === 1.5", () => {
		expect(MOCK_AGENT_INTERVAL_SEC).toBe(1.5);
	});

	it("MOCK_AGENT_TOTAL_DURATION_MS === INTERVAL_SEC * MOCK_AGENT_LOGS.length * 1000", () => {
		expect(MOCK_AGENT_TOTAL_DURATION_MS).toBe(
			MOCK_AGENT_INTERVAL_SEC * MOCK_AGENT_LOGS.length * 1000,
		);
	});

	it("MOCK_AGENT_TOTAL_DURATION_MS === 19500 (13 logs × 1.5s × 1000)", () => {
		// 13 条 Agent 日志 × 1.5s 间隔 = 19.5s 总时长
		expect(MOCK_AGENT_LOGS.length).toBe(13);
		expect(MOCK_AGENT_TOTAL_DURATION_MS).toBe(19500);
	});
});

describe("mockApi - mockGenerate 等待 mockAgentStream 完成", () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("returns a pending Promise before MOCK_AGENT_TOTAL_DURATION_MS elapses", () => {
		const promise = mockGenerate("需求");
		// 在推进时间前，Promise 应处于 pending 状态
		let resolved = false;
		void promise.then(() => {
			resolved = true;
		});

		// 推进少量时间（小于总时长），Promise 仍未 resolve
		vi.advanceTimersByTime(MOCK_AGENT_TOTAL_DURATION_MS - 1);
		expect(resolved).toBe(false);
	});

	it("resolves only after advancing time by MOCK_AGENT_TOTAL_DURATION_MS", async () => {
		const promise = mockGenerate("需求");

		// 推进到刚好达到 MOCK_AGENT_TOTAL_DURATION_MS，Promise 应 resolve
		await vi.advanceTimersByTimeAsync(MOCK_AGENT_TOTAL_DURATION_MS);

		const result = await promise;
		expect(result).toBeDefined();
		// 验证返回值包含 Spec 要求的关键字段
		expect(result.code).toBeDefined();
		expect(typeof result.code).toBe("string");
		expect(result.contract).toBeDefined();
		expect(result.contract.component).toBe("LowPassFilter");
		expect(Array.isArray(result.violations)).toBe(true);
		expect(result.traceability).toBeDefined();
		expect(Array.isArray(result.repair_history)).toBe(true);
		expect(result.contract_check_result).toBeDefined();
		expect(result.simulation_result).toBeDefined();
	});

	it("does NOT resolve before MOCK_AGENT_TOTAL_DURATION_MS (alignment with mockAgentStream)", async () => {
		const promise = mockGenerate("需求");
		let resolved = false;
		void promise.then(() => {
			resolved = true;
		});

		// 推进到总时长 - 1ms（少 1ms），模拟 Agent 流尚未完成
		await vi.advanceTimersByTimeAsync(MOCK_AGENT_TOTAL_DURATION_MS - 1);
		// 让微任务排空
		await Promise.resolve();
		expect(resolved).toBe(false);

		// 推进最后 1ms，Agent 流结束，mockGenerate 应 resolve
		await vi.advanceTimersByTimeAsync(1);
		await promise;
		expect(resolved).toBe(true);
	});

	it("resolves with full GenerateResult shape (code/contract/violations/traceability/repair_history/contract_check_result/simulation_result)", async () => {
		const promise = mockGenerate("实现一个低通滤波器");
		await vi.advanceTimersByTimeAsync(MOCK_AGENT_TOTAL_DURATION_MS);
		const result = await promise;

		// 完整字段断言（与 GenerateResult 接口对齐）
		expect(result).toMatchObject({
			code: expect.any(String),
			contract: expect.objectContaining({
				component: expect.any(String),
				description: expect.any(String),
				inputs: expect.any(Object),
				outputs: expect.any(Object),
				preconditions: expect.any(Array),
				postconditions: expect.any(Array),
				invariants: expect.any(Array),
				fault_handling: expect.any(Array),
			}),
			violations: expect.any(Array),
			traceability: expect.any(Object),
			repair_history: expect.any(Array),
			contract_check_result: expect.objectContaining({
				component: expect.any(String),
				sections: expect.any(Array),
				passed_count: expect.any(Number),
				total_count: expect.any(Number),
				overall_passed: expect.any(Boolean),
				generated_assert_code: expect.any(String),
			}),
			simulation_result: expect.objectContaining({
				passed: expect.any(Boolean),
				total_steps: expect.any(Number),
			}),
		});
	});

	it("aligns mockGenerate delay with mockAgentStream total duration (no early result)", async () => {
		// Spec 修复 A Task 3: mockGenerate 必须等到 mockAgentStream 全部日志推送完毕后才 resolve，
		// 避免"Agent 还在思考、结果已显示"的时序错乱。
		// 这里通过验证 mockGenerate 的延迟 === MOCK_AGENT_TOTAL_DURATION_MS 来对齐。
		const startTime = Date.now();
		const promise = mockGenerate("需求");

		// 推进总时长 - 1ms：mockGenerate 不应 resolve
		await vi.advanceTimersByTimeAsync(MOCK_AGENT_TOTAL_DURATION_MS - 1);
		let settled = false;
		void promise.then(() => {
			settled = true;
		});
		await Promise.resolve();
		expect(settled).toBe(false);

		// 推进最后 1ms：正好达到 MOCK_AGENT_TOTAL_DURATION_MS
		await vi.advanceTimersByTimeAsync(1);
		await promise;

		const elapsed = Date.now() - startTime;
		expect(elapsed).toBe(MOCK_AGENT_TOTAL_DURATION_MS);
	});
});
