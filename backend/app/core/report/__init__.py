"""DO-178C 合规报告生成器子包：追溯矩阵 + 目标符合性 + HTML 报告。"""

from .report_generator import generate_report
from .traceability_matrix import TraceEntry, build_matrix
from .do178_objectives import ObjectiveResult, check_objectives

__all__ = [
    "generate_report",
    "TraceEntry",
    "build_matrix",
    "ObjectiveResult",
    "check_objectives",
]
