import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MonacoCodeEditor from "../MonacoCodeEditor.vue";

const mockEditorModel = {
	getLineContent: vi.fn(() => ""),
	getLineMaxColumn: vi.fn(() => 100),
	getLineCount: vi.fn(() => 10),
	setValue: vi.fn(),
	getValue: vi.fn(() => "int main() { return 0; }"),
};

const mockEditor = {
	onDidChangeModelContent: vi.fn(),
	onMouseDown: vi.fn(),
	getModel: vi.fn(() => mockEditorModel),
	getValue: vi.fn(() => "int main() { return 0; }"),
	deltaDecorations: vi.fn(() => []),
};

vi.mock("monaco-editor", () => ({
	default: {
		editor: {
			create: vi.fn(() => mockEditor),
			defineTheme: vi.fn(),
			OverviewRulerLane: { Left: 1 },
		},
		Range: vi.fn(
			(
				startLine: number,
				startCol: number,
				endLine: number,
				endCol: number,
			) => ({
				startLine,
				startCol,
				endLine,
				endCol,
			}),
		),
	},
	editor: {
		create: vi.fn(() => mockEditor),
		defineTheme: vi.fn(),
		OverviewRulerLane: { Left: 1 },
	},
	Range: vi.fn(
		(startLine: number, startCol: number, endLine: number, endCol: number) => ({
			startLine,
			startCol,
			endLine,
			endCol,
		}),
	),
}));

vi.mock("@/utils/tagParser", () => ({
	parseInlineTags: vi.fn((text: string) => {
		const tokens: Array<{ type: string; value: string }> = [];
		const regex = /\[(REQ-\d+)\]/g;
		let lastIdx = 0;
		let match;
		while ((match = regex.exec(text)) !== null) {
			if (match.index > lastIdx) {
				tokens.push({
					type: "text",
					value: text.slice(lastIdx, match.index),
				});
			}
			tokens.push({ type: "req", value: match[1] });
			lastIdx = match.index + match[0].length;
		}
		if (lastIdx < text.length) {
			tokens.push({ type: "text", value: text.slice(lastIdx) });
		}
		return tokens;
	}),
}));

describe("MonacoCodeEditor", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders editor wrapper container", () => {
		const wrapper = mount(MonacoCodeEditor, {
			props: { code: "int main() { return 0; }" },
		});
		expect(wrapper.find(".monaco-editor-wrapper").exists()).toBe(true);
		expect(wrapper.find(".editor-container").exists()).toBe(true);
	});

	it("initializes monaco editor on mount via dynamic import", async () => {
		mount(MonacoCodeEditor, {
			props: { code: "int main() {}", language: "c" },
		});
		await flushPromises();
		const monaco = await import("monaco-editor");
		expect(
			(
				monaco as unknown as ReturnType<typeof vi.fn> & {
					editor: { create: ReturnType<typeof vi.fn> };
				}
			).editor.create,
		).toHaveBeenCalled();
	});

	it("creates editor with default language c", async () => {
		mount(MonacoCodeEditor, {
			props: { code: "test code" },
		});
		await flushPromises();
		const monaco = await import("monaco-editor");
		expect(
			(
				monaco as unknown as ReturnType<typeof vi.fn> & {
					editor: { create: ReturnType<typeof vi.fn> };
				}
			).editor.create,
		).toHaveBeenCalledWith(
			expect.anything(),
			expect.objectContaining({
				value: "test code",
				language: "c",
				readOnly: true,
			}),
		);
	});

	it("creates editor with custom language", async () => {
		mount(MonacoCodeEditor, {
			props: { code: "x = 1", language: "python" },
		});
		await flushPromises();
		const monaco = await import("monaco-editor");
		expect(
			(
				monaco as unknown as ReturnType<typeof vi.fn> & {
					editor: { create: ReturnType<typeof vi.fn> };
				}
			).editor.create,
		).toHaveBeenCalledWith(
			expect.anything(),
			expect.objectContaining({ language: "python" }),
		);
	});

	it("creates editor in read-only mode by default", async () => {
		mount(MonacoCodeEditor, { props: { code: "test" } });
		await flushPromises();
		const monaco = await import("monaco-editor");
		expect(
			(
				monaco as unknown as ReturnType<typeof vi.fn> & {
					editor: { create: ReturnType<typeof vi.fn> };
				}
			).editor.create,
		).toHaveBeenCalledWith(
			expect.anything(),
			expect.objectContaining({ readOnly: true }),
		);
	});

	it("creates editor in editable mode when readOnly=false", async () => {
		mount(MonacoCodeEditor, {
			props: { code: "test", readOnly: false },
		});
		await flushPromises();
		const monaco = await import("monaco-editor");
		expect(
			(
				monaco as unknown as ReturnType<typeof vi.fn> & {
					editor: { create: ReturnType<typeof vi.fn> };
				}
			).editor.create,
		).toHaveBeenCalledWith(
			expect.anything(),
			expect.objectContaining({ readOnly: false }),
		);
	});

	it("registers skyforge-dark theme", async () => {
		mount(MonacoCodeEditor, { props: { code: "" } });
		await flushPromises();
		const monaco = await import("monaco-editor");
		expect(
			(
				monaco as unknown as ReturnType<typeof vi.fn> & {
					editor: { defineTheme: ReturnType<typeof vi.fn> };
				}
			).editor.defineTheme,
		).toHaveBeenCalledWith(
			"skyforge-dark",
			expect.objectContaining({ base: "vs-dark" }),
		);
	});

	it("registers content change listener", async () => {
		mount(MonacoCodeEditor, { props: { code: "" } });
		await flushPromises();
		expect(mockEditor.onDidChangeModelContent).toHaveBeenCalled();
	});

	it("registers mouse down listener for REQ tag click", async () => {
		mount(MonacoCodeEditor, { props: { code: "" } });
		await flushPromises();
		expect(mockEditor.onMouseDown).toHaveBeenCalled();
	});

	it("watches code prop and updates editor model", async () => {
		const wrapper = mount(MonacoCodeEditor, {
			props: { code: "initial code" },
		});
		await flushPromises();
		await wrapper.setProps({ code: "updated code" });
		expect(mockEditorModel.setValue).toHaveBeenCalledWith("updated code");
	});

	it("does not update model when code matches current value", async () => {
		mockEditorModel.getValue = vi.fn(() => "same code");
		const wrapper = mount(MonacoCodeEditor, {
			props: { code: "same code" },
		});
		await flushPromises();
		await wrapper.setProps({ code: "same code" });
		expect(mockEditorModel.setValue).not.toHaveBeenCalled();
	});

	it("cleans up editor on unmount", async () => {
		const wrapper = mount(MonacoCodeEditor, {
			props: { code: "test" },
		});
		await flushPromises();
		wrapper.unmount();
	});
});
