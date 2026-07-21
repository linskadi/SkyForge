"""报告数据收集器。

统一收集 Pipeline 各阶段产物，为渲染层提供标准化的数据输入。
"""

from __future__ import annotations

from typing import Any

from skyforge_engine.utils.log_util import logger


class ReportDataCollector:
    """统一收集 Pipeline 各阶段产物。

    使用方式：
        collector = ReportDataCollector()
        collector.collect("requirement", req_json)
        collector.collect("contract", contract_yaml)
        collector.collect("final_code", code)
        data = collector.get_data()
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def collect(self, stage_name: str, artifact: Any) -> None:
        """收集单个阶段的产物。

        Args:
            stage_name: 阶段名称（如 "requirement", "contract", "final_code"）。
            artifact: 阶段产物（任意类型）。
        """
        self._data[stage_name] = artifact
        logger.debug(f"ReportDataCollector: 收集阶段 {stage_name}")

    def get_data(self) -> dict[str, Any]:
        """返回完整数据字典的副本。

        Returns:
            包含所有已收集阶段产物的字典。
        """
        return self._data.copy()

    def clear(self) -> None:
        """清空已收集的数据。"""
        self._data.clear()
