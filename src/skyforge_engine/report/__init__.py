# SkyForge Engine: report
# DO-178C 合规报告 + 证据收集

from skyforge_engine.report.report_generator import generate_report
from skyforge_engine.report.traceability_matrix import (
    TraceEntry,
    build_matrix,
    build_reverse_matrix,
    export_to_reqif,
    export_to_pdf,
)
from skyforge_engine.report.coverage_analyzer import (
    analyze_code_coverage,
    get_coverage_summary,
)
from skyforge_engine.report.do178_objectives import (
    ObjectiveResult,
    check_objectives,
)
from skyforge_engine.report.psac_generator import (
    PSACDocument,
    generate_psac,
)
from skyforge_engine.report.evidence_collector import (
    EvidenceCollector,
    EvidenceItem,
    EvidenceSession,
    get_collector,
)

__all__ = [
    # Reports
    "generate_report",
    "TraceEntry",
    "build_matrix",
    "build_reverse_matrix",
    "export_to_reqif",
    "export_to_pdf",
    "analyze_code_coverage",
    "get_coverage_summary",
    "ObjectiveResult",
    "check_objectives",
    "PSACDocument",
    "generate_psac",
    # Evidence
    "EvidenceCollector",
    "EvidenceItem",
    "EvidenceSession",
    "get_collector",
]
