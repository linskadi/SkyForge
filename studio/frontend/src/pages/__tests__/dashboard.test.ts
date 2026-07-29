import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Dashboard from "@/pages/dashboard/index.vue";

const mockPush = vi.fn();
vi.mock("vue-router", () => ({ useRouter: () => ({ push: mockPush }) }));

vi.mock("vue-echarts", () => ({
	default: {
		name: "VChart",
		props: ["option", "autoresize"],
		template: '<div class="v-chart-mock"></div>',
	},
}));

const mockGetSystemStatus = vi.fn().mockResolvedValue({
	backend: "online",
	llm: { mode: "mock", provider: null, model: null, available: true },
	tools: { gcc: true, z3: true, cbmc: null },
	persistence: { db_rows: 128, last_write: new Date().toISOString() },
});

const mockGetRecentTasks = vi.fn().mockResolvedValue([
	{
		id: "task-001",
		requirement: "实现一个低通滤波器，截止频率 10Hz",
		language: "c",
		status: "done",
		degraded: false,
		violation_count: 2,
		stage_reached: "done",
		duration_ms: 45000,
		created_at: new Date().toISOString(),
	},
	{
		id: "task-002",
		requirement: "实现 PID 控制器",
		language: "cpp",
		status: "running",
		degraded: false,
		violation_count: 0,
		stage_reached: "code",
		duration_ms: 0,
		created_at: new Date(Date.now() - 120000).toISOString(),
	},
]);

const mockGetDashboardStats = vi.fn().mockResolvedValue({
	today_count: 12,
	today_done: 8,
	total_count: 256,
	avg_compliance_rate: 0.92,
});

const mockGetComplianceTrend = vi.fn().mockResolvedValue([
	{ ts: new Date().toISOString(), mandatory: 0, required: 2, advisory: 1, total: 3 },
	{ ts: new Date().toISOString(), mandatory: 1, required: 1, advisory: 0, total: 2 },
]);

vi.mock("@/services/apiSwitcher", () => ({
	getApi: () => ({
		getSystemStatus: mockGetSystemStatus,
		getRecentTasks: mockGetRecentTasks,
		getDashboardStats: mockGetDashboardStats,
		getComplianceTrend: mockGetComplianceTrend,
	}),
}));

const mountDashboard = () =>
	mount(Dashboard, {
		global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
	});

describe("Professional Dashboard", () => {
	beforeEach(() => {
		localStorage.clear();
		setActivePinia(createPinia());
		mockPush.mockReset();
		vi.clearAllMocks();
	});

	it("renders system status section with three cards", () => {
		const wrapper = mountDashboard();
		expect(wrapper.text()).toContain("系统状态");
		expect(wrapper.text()).toContain("后端服务");
		expect(wrapper.text()).toContain("LLM 引擎");
		expect(wrapper.text()).toContain("工具链");
	});

	it("renders quick action section with three actions", () => {
		const wrapper = mountDashboard();
		expect(wrapper.text()).toContain("新建代码生成任务");
		expect(wrapper.text()).toContain("继续上次任务");
		expect(wrapper.text()).toContain("从 SCADE 导入");
	});

	it("renders recent tasks section with view all link", () => {
		const wrapper = mountDashboard();
		expect(wrapper.text()).toContain("最近任务");
		expect(wrapper.text()).toContain("查看全部");
	});

	it("renders compliance stats section", () => {
		const wrapper = mountDashboard();
		expect(wrapper.text()).toContain("DO-178C 合规率");
		expect(wrapper.text()).toContain("违规数趋势");
		expect(wrapper.text()).toContain("平均合规率");
		expect(wrapper.text()).toContain("今日任务");
		expect(wrapper.text()).toContain("已完成");
		expect(wrapper.text()).toContain("总任务数");
	});

	it("navigates to /generate on new task action", async () => {
		const wrapper = mountDashboard();
		const actionCards = wrapper.findAll(".action-card");
		await actionCards[0].trigger("click");
		expect(mockPush).toHaveBeenCalledWith("/generate");
	});

	it("navigates to last task or records on continue action", async () => {
		const wrapper = mountDashboard();
		const actionCards = wrapper.findAll(".action-card");
		await actionCards[1].trigger("click");
		expect(mockPush).toHaveBeenCalled();
		const callArg = mockPush.mock.calls[0][0];
		expect(callArg === "/records" || callArg.startsWith("/records/")).toBe(true);
	});

	it("navigates to /generate with scade param on import action", async () => {
		const wrapper = mountDashboard();
		const actionCards = wrapper.findAll(".action-card");
		await actionCards[2].trigger("click");
		expect(mockPush).toHaveBeenCalledWith({ path: "/generate", query: { scade: "1" } });
	});

	it("fetches dashboard data on mount", async () => {
		mountDashboard();
		await new Promise((resolve) => setTimeout(resolve, 50));
		expect(mockGetSystemStatus).toHaveBeenCalled();
		expect(mockGetRecentTasks).toHaveBeenCalled();
		expect(mockGetDashboardStats).toHaveBeenCalled();
		expect(mockGetComplianceTrend).toHaveBeenCalled();
	});

	it("handles empty tasks state gracefully", async () => {
		mockGetRecentTasks.mockResolvedValueOnce([]);
		const wrapper = mountDashboard();
		await new Promise((resolve) => setTimeout(resolve, 50));
		expect(wrapper.text()).toContain("暂无任务记录");
	});

	it("displays task language badges correctly", async () => {
		const wrapper = mountDashboard();
		await new Promise((resolve) => setTimeout(resolve, 50));
		expect(wrapper.text()).toContain("C");
		expect(wrapper.text()).toContain("C++");
	});

	it("displays task status badges correctly", async () => {
		const wrapper = mountDashboard();
		await new Promise((resolve) => setTimeout(resolve, 50));
		expect(wrapper.text()).toContain("已完成");
		expect(wrapper.text()).toContain("运行中");
	});
});
