import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DemoTaskGateway } from "./taskGateway";

const input = {
	requirement: "实现低通滤波器",
	language: "c" as const,
	profile_id: "demo" as const,
	idempotency_key: "gateway-idempotency-key",
};

describe("DemoTaskGateway", () => {
	beforeEach(() => {
		vi.useFakeTimers();
		DemoTaskGateway.clearPersisted();
	});
	afterEach(() => vi.useRealTimers());

	it("runs without any network request", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch");
		const gateway = new DemoTaskGateway();
		await gateway.createTask(input);
		await vi.advanceTimersByTimeAsync(5000);
		expect(fetchSpy).not.toHaveBeenCalled();
		fetchSpy.mockRestore();
	});

	it("returns one task for a repeated idempotency key", async () => {
		const gateway = new DemoTaskGateway();
		const first = await gateway.createTask(input);
		const second = await gateway.createTask(input);
		expect(second.id).toBe(first.id);
		expect(await gateway.listTasks()).toHaveLength(1);
	});

	it("marks every demo event and tool result simulated", async () => {
		const gateway = new DemoTaskGateway();
		const task = await gateway.createTask(input);
		const events: string[] = [];
		gateway.subscribe(task.id, 0, (event) =>
			events.push(event.evidence_status),
		);
		await vi.advanceTimersByTimeAsync(5000);
		const detail = await gateway.getTask(task.id);
		expect(events.length).toBeGreaterThan(5);
		expect(events.every((status) => status === "simulated")).toBe(true);
		expect(detail.source).toBe("simulated");
		expect(detail.provenance?.report_label).toBe("模拟演示报告");
	});

	it("supports replay from an event sequence", async () => {
		const gateway = new DemoTaskGateway();
		const task = await gateway.createTask(input);
		await vi.advanceTimersByTimeAsync(2000);
		const received: number[] = [];
		gateway.subscribe(task.id, 3, (event) => received.push(event.seq));
		expect(received.every((seq) => seq > 3)).toBe(true);
	});

	it("cancels pending timers", async () => {
		const gateway = new DemoTaskGateway();
		const task = await gateway.createTask(input);
		await gateway.cancelTask(task.id);
		await vi.advanceTimersByTimeAsync(5000);
		expect((await gateway.getTask(task.id)).status).toBe("cancelled");
	});
});
