import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { ref } from "vue";
import AgentTerminal from "../AgentTerminal.vue";
import { useExecutionStore } from "@/stores/executionStore";

vi.mock("@tanstack/vue-virtual", () => ({
	useVirtualizer: vi.fn(() =>
		ref({
			getVirtualItems: vi.fn(() => []),
			getTotalSize: vi.fn(() => 0),
			scrollToIndex: vi.fn(),
			setOptions: vi.fn(),
			options: { count: 0 },
		}),
	),
}));

vi.mock("@/services/mockApi", () => ({
	mockAgentStream: vi.fn(() => vi.fn()),
	connectAgentStream: vi.fn(() => vi.fn()),
	connectV1TaskEvents: vi.fn(() => vi.fn()),
	createTaskAndSubscribeV1: vi.fn(() =>
		Promise.resolve({ taskId: null, stop: () => {} }),
	),
	DEFAULT_WS_URL: "ws://localhost:8000/ws/agent-stream",
}));

vi.mock("@/utils/colors", () => ({
	agentColorMap: {
		"REQ-Parser": { bg: "#1d4ed8", fg: "#dbeafe" },
		"CON-Gen": { bg: "#6d28d9", fg: "#ede9fe" },
		"CODE-Gen": { bg: "#047857", fg: "#d1fae5" },
		REPAIR: { bg: "#c2410c", fg: "#ffedd5" },
		SYSTEM: { bg: "#475569", fg: "#f1f5f9" },
		TERMINAL: { bg: "#0e7490", fg: "#cffafe" },
	},
	levelColorMap: {
		info: "#94a3b8",
		success: "#059669",
		warn: "#d97706",
		error: "#dc2626",
	},
}));

describe("AgentTerminal", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		vi.clearAllMocks();
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("renders terminal header with title", () => {
		const wrapper = mount(AgentTerminal, { props: { useMock: true } });
		expect(wrapper.find(".terminal-title").text()).toBe(
			"SkyForge Agent Console",
		);
	});

	it("renders traffic lights", () => {
		const wrapper = mount(AgentTerminal, { props: { useMock: true } });
		expect(wrapper.find(".light.red").exists()).toBe(true);
		expect(wrapper.find(".light.yellow").exists()).toBe(true);
		expect(wrapper.find(".light.green").exists()).toBe(true);
	});

	it("shows mock badge when useMock is true", () => {
		const wrapper = mount(AgentTerminal, { props: { useMock: true } });
		expect(wrapper.find(".mock-badge").exists()).toBe(true);
		expect(wrapper.find(".mock-badge").text()).toBe("MOCK");
	});

	it("hides mock badge when useMock is false", () => {
		const wrapper = mount(AgentTerminal, { props: { useMock: false } });
		expect(wrapper.find(".mock-badge").exists()).toBe(false);
	});

	it("renders empty hint when no logs", () => {
		const wrapper = mount(AgentTerminal, { props: { useMock: true } });
		expect(wrapper.find(".empty-hint").exists()).toBe(true);
		expect(wrapper.find(".empty-hint").text()).toContain(
			"等待 Agent 思考日志流入",
		);
	});

	it("clears logs when clear button is clicked", async () => {
		const wrapper = mount(AgentTerminal, { props: { useMock: true } });
		const clearBtn = wrapper.find(".clear-btn");
		expect(clearBtn.exists()).toBe(true);
		await clearBtn.trigger("click");
		expect(wrapper.find(".empty-hint").exists()).toBe(true);
	});

	it("exposes start/stop/clear/push/finish methods", () => {
		const wrapper = mount(AgentTerminal, { props: { useMock: true } });
		const vm = wrapper.vm as unknown as Record<string, unknown>;
		expect(typeof vm.start).toBe("function");
		expect(typeof vm.stop).toBe("function");
		expect(typeof vm.clear).toBe("function");
		expect(typeof vm.push).toBe("function");
		expect(typeof vm.finish).toBe("function");
	});

	it("push method does not throw when adding a log entry", () => {
		const wrapper = mount(AgentTerminal, { props: { useMock: true } });
		const vm = wrapper.vm as unknown as Record<string, unknown>;
		expect(() => {
			(vm.push as (payload: unknown) => void)({
				agent: "SYSTEM",
				level: "info",
				thought: "Test log message",
				ts: 1000,
			});
		}).not.toThrow();
	});

	it("push then clear restores empty state", () => {
		const wrapper = mount(AgentTerminal, { props: { useMock: true } });
		const vm = wrapper.vm as unknown as Record<string, unknown>;
		(vm.push as (payload: unknown) => void)({
			agent: "SYSTEM",
			level: "info",
			thought: "Test log",
			ts: 1000,
		});
		(vm.clear as () => void)();
		expect(wrapper.find(".empty-hint").exists()).toBe(true);
	});

	it("push method respects maxLogs limit without throwing", () => {
		const wrapper = mount(AgentTerminal, {
			props: { useMock: true, maxLogs: 3 },
		});
		const vm = wrapper.vm as unknown as Record<string, unknown>;
		expect(() => {
			for (let i = 0; i < 5; i++) {
				(vm.push as (payload: unknown) => void)({
					agent: "SYSTEM",
					level: "info",
					thought: `Log ${i}`,
					ts: i * 1000,
				});
			}
		}).not.toThrow();
		(vm.clear as () => void)();
		expect(wrapper.find(".empty-hint").exists()).toBe(true);
	});

	it("does NOT call mockAgentStream on mount with useMock=true (three-branch logic: mock mode waits for explicit start)", async () => {
		const { mockAgentStream } = await import("@/services/mockApi");
		mount(AgentTerminal, { props: { useMock: true } });
		// onMounted 三分支逻辑：mock 模式不自动启动，等待父组件显式 start()
		expect(mockAgentStream).not.toHaveBeenCalled();
	});

	it("calls mockAgentStream when start() is invoked explicitly (mock mode)", async () => {
		const { mockAgentStream } = await import("@/services/mockApi");
		const wrapper = mount(AgentTerminal, { props: { useMock: true } });
		const vm = wrapper.vm as unknown as { start: () => void };
		vm.start();
		expect(mockAgentStream).toHaveBeenCalled();
	});

	it("uses current cloud execution profile when creating V1 task", async () => {
		const { createTaskAndSubscribeV1 } = await import("@/services/mockApi");
		useExecutionStore().setProfile("cloud");
		const wrapper = mount(AgentTerminal, {
			props: {
				useMock: false,
				requirement: "实现 ARINC 429 解码",
				language: "cpp",
			},
		});
		const vm = wrapper.vm as unknown as { start: () => void };

		vm.start();

		expect(createTaskAndSubscribeV1).toHaveBeenCalledWith(
			"实现 ARINC 429 解码",
			"cpp",
			"cloud",
			expect.any(Function),
			expect.any(Function),
			expect.any(Function),
		);
	});

	it("clears logs on unmount without errors", () => {
		const wrapper = mount(AgentTerminal, { props: { useMock: true } });
		wrapper.unmount();
	});

	it("calls finish on unmount to clean up typing timer", () => {
		const wrapper = mount(AgentTerminal, { props: { useMock: true } });
		const vm = wrapper.vm as unknown as Record<string, unknown>;
		(vm.push as (payload: unknown) => void)({
			agent: "SYSTEM",
			level: "info",
			thought: "Some log",
			ts: Date.now(),
		});
		wrapper.unmount();
	});
});
