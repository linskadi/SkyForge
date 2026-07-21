"""PDF 报告渲染器。

实现 ReportRendererProtocol，依赖 weasyprint 将 HTML 转为 PDF。
"""

from __future__ import annotations

from typing import Any

from skyforge_engine.core.protocols import ToolNotFoundError


class PDFRenderer:
    """PDF 报告渲染器。

    将 ReportDataCollector 收集的数据渲染为 PDF 格式报告。
    需要安装 weasyprint 方可使用，否则 render() 抛出 ToolNotFoundError。
    """

    @property
    def mime_type(self) -> str:
        return "application/pdf"

    @property
    def format_name(self) -> str:
        return "pdf"

    def render(self, data: dict[str, Any]) -> bytes:
        """渲染 PDF 报告。

        Args:
            data: 报告数据字典（通常来自 ReportDataCollector.get_data）。

        Returns:
            PDF 文件内容的 bytes。

        Raises:
            ToolNotFoundError: weasyprint 未安装时抛出。
        """
        try:
            import weasyprint
        except ImportError as exc:
            raise ToolNotFoundError(
                "weasyprint",
                "weasyprint 未安装，无法生成 PDF。请执行: pip install weasyprint",
            ) from exc

        from skyforge_engine.core.renderers.html_renderer import HTMLRenderer

        html = HTMLRenderer().render(data)
        return weasyprint.HTML(string=html).write_pdf()
