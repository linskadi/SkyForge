"""SkyForge 报告渲染层。

提供多种输出格式的报告渲染能力：
- HTMLRenderer: 生成 HTML 报告（复用现有 report_generator）
- MarkdownRenderer: 生成 Markdown 报告
- PDFRenderer: 生成 PDF 报告（需安装 weasyprint）
- ReportDataCollector: 统一收集 Pipeline 各阶段产物
"""

from __future__ import annotations

from skyforge_engine.core.renderers.data_collector import ReportDataCollector
from skyforge_engine.core.renderers.html_renderer import HTMLRenderer
from skyforge_engine.core.renderers.markdown_renderer import MarkdownRenderer
from skyforge_engine.core.renderers.pdf_renderer import PDFRenderer

__all__ = [
    "HTMLRenderer",
    "MarkdownRenderer",
    "PDFRenderer",
    "ReportDataCollector",
]
