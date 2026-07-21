/**
 * executionStore 单元测试
 * ====================================================================
 * Phase 1 状态管理统一后，验证：
 * 1. profileId 派生：providerStore.derivedMode 由 profileId 唯一决定；
 * 2. setProfile 写入 localStorage：key 必须为 `skyforge-execution-profile`；
 * 3. 页面刷新恢复：localStorage 中已存在的值能正确恢复（且不覆盖）。
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import {
	EXECUTION_PROFILE_STORAGE_KEY,
	useExecutionStore,
} from "@/stores/executionStore";
import { useProviderStore } from "@/stores/providerStore";

describe("executionStore - profileId default and setProfile", () => {
	beforeEach(() => {
		// 每个测试前重置 Pinia 与 localStorage
		setActivePinia(createPinia());
		localStorage.clear();
	});

	it("defaults profileId to 'demo' when no localStorage entry exists", () => {
		const execution = useExecutionStore();
		expect(execution.profileId).toBe("demo");
	});

	it("setProfile('cloud') updates profileId", () => {
		const execution = useExecutionStore();
		execution.setProfile("cloud");
		expect(execution.profileId).toBe("cloud");
	});

	it("setProfile('local') updates profileId", () => {
		const execution = useExecutionStore();
		execution.setProfile("local");
		expect(execution.profileId).toBe("local");
	});

	it("setProfile writes the new value to localStorage with the unified key", () => {
		const execution = useExecutionStore();
		execution.setProfile("local");
		expect(localStorage.getItem(EXECUTION_PROFILE_STORAGE_KEY)).toBe("local");
	});

	it("setProfile('demo') writes the new value to localStorage", () => {
		const execution = useExecutionStore();
		execution.setProfile("cloud");
		execution.setProfile("demo");
		expect(localStorage.getItem(EXECUTION_PROFILE_STORAGE_KEY)).toBe("demo");
	});

	it("profile computed reflects current profileId", () => {
		const execution = useExecutionStore();
		execution.setProfile("cloud");
		expect(execution.profile.id).toBe("cloud");
		expect(execution.profile.label).toBe("云 API · 实时/回放");
		expect(execution.profile.source).toBe("live");

		execution.setProfile("local");
		expect(execution.profile.id).toBe("local");
		expect(execution.profile.source).toBe("live");

		execution.setProfile("demo");
		expect(execution.profile.id).toBe("demo");
		expect(execution.profile.source).toBe("simulated");
	});

	it("profiles list contains all three profile ids", () => {
		const execution = useExecutionStore();
		const ids = execution.profiles.map((p) => p.id).sort();
		expect(ids).toEqual(["cloud", "demo", "local"]);
	});
});

describe("executionStore - localStorage restore on page refresh", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
	});

	it("recovers profileId === 'cloud' from localStorage on next Pinia init", () => {
		// 第一次初始化：写入 localStorage
		const first = useExecutionStore();
		first.setProfile("cloud");
		expect(localStorage.getItem(EXECUTION_PROFILE_STORAGE_KEY)).toBe("cloud");

		// 模拟页面刷新：重建 Pinia 实例（store 重新执行 setup）
		setActivePinia(createPinia());
		const second = useExecutionStore();
		expect(second.profileId).toBe("cloud");
	});

	it("recovers profileId === 'local' from localStorage on next Pinia init", () => {
		const first = useExecutionStore();
		first.setProfile("local");

		setActivePinia(createPinia());
		const second = useExecutionStore();
		expect(second.profileId).toBe("local");
	});

	it("recovers profileId === 'demo' from localStorage on next Pinia init", () => {
		const first = useExecutionStore();
		// 默认值就是 demo，但显式写入
		first.setProfile("cloud");
		first.setProfile("demo");

		setActivePinia(createPinia());
		const second = useExecutionStore();
		expect(second.profileId).toBe("demo");
	});

	it("falls back to 'demo' when localStorage has unknown value (data migration safety)", () => {
		localStorage.setItem(EXECUTION_PROFILE_STORAGE_KEY, "garbage");

		setActivePinia(createPinia());
		const second = useExecutionStore();
		expect(second.profileId).toBe("demo");
	});

	it("does not overwrite localStorage on init (avoid clobbering existing value)", () => {
		localStorage.setItem(EXECUTION_PROFILE_STORAGE_KEY, "cloud");

		setActivePinia(createPinia());
		// 触发 store 初始化
		useExecutionStore();

		// localStorage 中的 'cloud' 仍应保留（不被动写入 'demo'）
		expect(localStorage.getItem(EXECUTION_PROFILE_STORAGE_KEY)).toBe("cloud");
	});
});

describe("executionStore - profileId → providerStore.derivedMode 派生", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
	});

	it("profileId 'demo' 派生为 derivedMode 'mock'", () => {
		const execution = useExecutionStore();
		const provider = useProviderStore();
		execution.setProfile("demo");
		expect(provider.derivedMode).toBe("mock");
	});

	it("profileId 'cloud' 派生为 derivedMode 'api'", () => {
		const execution = useExecutionStore();
		const provider = useProviderStore();
		execution.setProfile("cloud");
		expect(provider.derivedMode).toBe("api");
	});

	it("profileId 'local' 派生为 derivedMode 'local'", () => {
		const execution = useExecutionStore();
		const provider = useProviderStore();
		execution.setProfile("local");
		expect(provider.derivedMode).toBe("local");
	});

	it("providerStore.derivedMode 随 executionStore.setProfile 同步变化", () => {
		const execution = useExecutionStore();
		const provider = useProviderStore();

		execution.setProfile("demo");
		expect(provider.derivedMode).toBe("mock");

		execution.setProfile("cloud");
		expect(provider.derivedMode).toBe("api");

		execution.setProfile("local");
		expect(provider.derivedMode).toBe("local");

		execution.setProfile("demo");
		expect(provider.derivedMode).toBe("mock");
	});

	it("page refresh 后 derivedMode 仍能正确派生", () => {
		const firstExecution = useExecutionStore();
		firstExecution.setProfile("cloud");

		setActivePinia(createPinia());
		const secondExecution = useExecutionStore();
		const secondProvider = useProviderStore();
		expect(secondExecution.profileId).toBe("cloud");
		expect(secondProvider.derivedMode).toBe("api");
	});
});
