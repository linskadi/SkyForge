"""测试报告渲染层（HTML / Markdown / PDF / DataCollector）。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest

from skyforge_engine.core.protocols import ReportRendererProtocol, ToolNotFoundError
from skyforge_engine.core.renderers import (
    HTMLRenderer,
    MarkdownRenderer,
    PDFRenderer,
    ReportDataCollector,
)


class TestReportDataCollector:
    """测试 ReportDataCollector。"""

    def test_collect_and_get_data(self):
        collector = ReportDataCollector()
        collector.collect("requirement", {"module_name": "test_mod"})
        collector.collect("contract", "component: test")
        data = collector.get_data()
        assert data["requirement"]["module_name"] == "test_mod"
        assert data["contract"] == "component: test"

    def test_get_data_returns_copy(self):
        collector = ReportDataCollector()
        collector.collect("key", "value")
        data1 = collector.get_data()
        data1["key"] = "modified"
        data2 = collector.get_data()
        assert data2["key"] == "value"

    def test_clear(self):
        collector = ReportDataCollector()
        collector.collect("key", "value")
        assert collector.get_data()
        collector.clear()
        assert collector.get_data() == {}


class TestHTMLRenderer:
    """测试 HTMLRenderer。"""

    def test_protocol_compliance(self):
        renderer = HTMLRenderer()
        assert isinstance(renderer, ReportRendererProtocol)

    def test_mime_type_and_format_name(self):
        renderer = HTMLRenderer()
        assert renderer.mime_type == "text/html"
        assert renderer.format_name == "html"

    def test_render_returns_html(self):
        renderer = HTMLRenderer()
        data = {
            "requirement": {"module_name": "test_module", "safety_level": "DAL-C"},
        }
        result = renderer.render(data)
        assert isinstance(result, str)
        assert "<!DOCTYPE html>" in result
        assert "test_module" in result


class TestMarkdownRenderer:
    """测试 MarkdownRenderer。"""

    def test_protocol_compliance(self):
        renderer = MarkdownRenderer()
        assert isinstance(renderer, ReportRendererProtocol)

    def test_mime_type_and_format_name(self):
        renderer = MarkdownRenderer()
        assert renderer.mime_type == "text/markdown"
        assert renderer.format_name == "markdown"

    def test_render_returns_markdown(self):
        renderer = MarkdownRenderer()
        data = {
            "requirement": {"module_name": "test_module", "safety_level": "DAL-C"},
        }
        result = renderer.render(data)
        assert isinstance(result, str)
        assert "# DO-178C 合规报告" in result
        assert "test_module" in result
        assert "## DO-178C 目标符合性表" in result

    def test_render_with_empty_data(self):
        renderer = MarkdownRenderer()
        result = renderer.render({})
        assert isinstance(result, str)
        assert "# DO-178C 合规报告" in result


class TestPDFRenderer:
    """测试 PDFRenderer。"""

    def test_protocol_compliance(self):
        renderer = PDFRenderer()
        assert isinstance(renderer, ReportRendererProtocol)

    def test_mime_type_and_format_name(self):
        renderer = PDFRenderer()
        assert renderer.mime_type == "application/pdf"
        assert renderer.format_name == "pdf"

    def test_render_raises_tool_not_found_when_weasyprint_missing(self):
        renderer = PDFRenderer()
        # 在测试环境中通常未安装 weasyprint，期望抛出 ToolNotFoundError
        with pytest.raises(ToolNotFoundError) as exc_info:
            renderer.render({})
        assert "weasyprint" in str(exc_info.value)


class TestRenderersModuleExports:
    """测试 renderers 模块导出。"""

    def test_all_classes_exported(self):
        from skyforge_engine.core.renderers import __all__

        assert "HTMLRenderer" in __all__
        assert "MarkdownRenderer" in __all__
        assert "PDFRenderer" in __all__
        assert "ReportDataCollector" in __all__
