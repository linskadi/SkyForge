import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Dashboard from "@/pages/dashboard/index.vue";
import { useExecutionStore } from "@/stores/executionStore";

const mockPush = vi.fn();
vi.mock("vue-router", () => ({ useRouter: () => ({ push: mockPush }) }));
const mountDashboard = () =>
	mount(Dashboard, {
		global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
	});

describe("Competition Dashboard", () => {
	beforeEach(() => {
		localStorage.clear();
		setActivePinia(createPinia());
		mockPush.mockReset();
		vi.clearAllMocks();
	});

	it("renders the single three-minute primary entry", () => {
		const wrapper = mountDashboard();
		expect(wrapper.text()).toContain("开始 3 分钟演示");
		expect(wrapper.findAll(".primary-cta")).toHaveLength(1);
	});

	it("shows exactly four judge-facing outcomes", () => {
		const wrapper = mountDashboard();
		expect(wrapper.findAll(".value-card")).toHaveLength(4);
		for (const title of ["端到端闭环", "MISRA 修复", "数字孪生", "全链路追溯"])
			expect(wrapper.text()).toContain(title);
	});

	it("labels the offline demonstration as simulated", () => {
		const wrapper = mountDashboard();
		expect(wrapper.find(".source-badge.simulated").text()).toBe("模拟数据");
		expect(wrapper.text()).toContain("不冒充真实工具证据");
	});

	it("displays verified recordings with real demo data", () => {
		const wrapper = mountDashboard();
		expect(wrapper.text()).toContain("云端 DeepSeek-V4 低通滤波器运行");
		expect(wrapper.text()).toContain("本地 Ollama qwen3:8b 低通滤波器运行");
		expect(wrapper.findAll(".recording-card")).toHaveLength(2);
	});

	it("primary entry selects demo and navigates to the workbench", async () => {
		const store = useExecutionStore();
		store.setProfile("cloud");
		const wrapper = mountDashboard();
		await wrapper.find(".primary-cta").trigger("click");
		expect(store.profileId).toBe("demo");
		expect(mockPush).toHaveBeenCalledWith("/demo");
	});

	it("explains the deterministic tool division", () => {
		const wrapper = mountDashboard();
		expect(wrapper.text()).toContain("多 Agent 负责理解与生成");
		expect(wrapper.text()).toContain("确定性工具负责扫描、编译和验证");
	});
});
