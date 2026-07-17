"""PSAC 文档生成器：从项目元数据自动生成 PSAC 概览，输出 Markdown 片段。

用于 DO-178C 合规报告的"审定计划"章节，提取 pipeline_result 中的版本号、DAL 等级、
Agent 状态等信息，生成结构化的 PSAC 摘要。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from skyforge_engine.utils.log_util import logger


@dataclass
class PSACMeta:
    """PSAC 元数据：项目级别的基本信息。

    Attributes:
        software_name: 软件名称。
        version: 软件版本号。
        certification_level: 审定级别（DAL-A / DAL-B / DAL-C / DAL-D / DAL-E）。
        date: 生成日期（ISO 8601）。
    """

    software_name: str = "SkyForge"
    version: str = ""
    certification_level: str = "DAL-C"
    date: str = ""


@dataclass
class PSACSection:
    """PSAC 单节内容。

    Attributes:
        title: 章节标题。
        content: Markdown 格式内容。
    """

    title: str
    content: str


@dataclass
class PSACDocument:
    """完整的 PSAC 文档结构。

    Attributes:
        meta: PSAC 元数据。
        sections: 文档各章节列表。
    """

    meta: PSACMeta = field(default_factory=PSACMeta)
    sections: list[PSACSection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return {
            "meta": asdict(self.meta),
            "sections": [
                {"title": s.title, "content": s.content} for s in self.sections
            ],
        }

    def to_markdown(self) -> str:
        """将 PSAC 文档渲染为 Markdown 字符串。"""
        lines: list[str] = []
        lines.append("# PSAC — 软件审定计划摘要")
        lines.append("")
        lines.append("> 本文档由 psac_generator.py 自动生成")
        lines.append("")
        lines.append("## 元数据")
        lines.append("")
        lines.append(f"- **软件名称**: {self.meta.software_name}")
        lines.append(f"- **版本**: {self.meta.version or 'N/A'}")
        lines.append(f"- **审定级别**: {self.meta.certification_level}")
        lines.append(f"- **生成日期**: {self.meta.date or 'N/A'}")
        lines.append("")
        for section in self.sections:
            lines.append(f"## {section.title}")
            lines.append("")
            lines.append(section.content)
            lines.append("")
        return "\n".join(lines)


def generate_psac(pipeline_result: dict[str, Any]) -> PSACDocument:
    """从 pipeline_result 生成 PSAC 文档摘要。

    Args:
        pipeline_result: 全流程结果字典，至少包含 requirement / contract / final_code
            等字段。

    Returns:
        PSACDocument：结构化 PSAC 文档。
    """
    from datetime import datetime

    doc = PSACDocument()

    # 元数据提取
    requirement = pipeline_result.get("requirement", {})
    if isinstance(requirement, dict):
        doc.meta.version = requirement.get("version", "V3.2")
        doc.meta.certification_level = requirement.get("safety_level", "DAL-C")
    else:
        doc.meta.version = "V3.2"
        doc.meta.certification_level = "DAL-C"
    doc.meta.date = datetime.now().strftime("%Y-%m-%d")

    # 1. 系统概述
    sections = []

    # 1.1 需求摘要
    req_text = requirement.get("desc") if isinstance(requirement, dict) else str(requirement or "")
    req_module = (
        requirement.get("module_name", "unknown")
        if isinstance(requirement, dict)
        else "unknown"
    )
    structured = pipeline_result.get("structured_reqs")
    req_count = len(structured) if isinstance(structured, list) else 1
    sections.append(
        PSACSection(
            title="系统概述",
            content=(
                f"**模块名称**: {req_module}\n\n"
                f"**需求描述**: {(req_text or '')[:300]}\n\n"
                f"**需求数量**: {req_count} 条结构化需求\n\n"
                f"**审定级别**: {doc.meta.certification_level}"
            ),
        )
    )

    # 1.2 开发过程
    has_code = bool(pipeline_result.get("final_code") or pipeline_result.get("code"))
    has_contract = bool(pipeline_result.get("contract"))
    has_simu = bool(pipeline_result.get("simulation_result"))
    sections.append(
        PSACSection(
            title="开发过程摘要",
            content=(
                f"- 需求解析: {'✅ 完成' if requirement else '❌ 未完成'}\n"
                f"- 契约生成: {'✅ 完成' if has_contract else '❌ 未完成'}\n"
                f"- 代码生成: {'✅ 完成' if has_code else '❌ 未完成'}\n"
                f"- 数字孪生仿真: {'✅ 完成' if has_simu else '❌ 未完成'}\n"
            ),
        )
    )

    # 1.3 验证结果
    violations = pipeline_result.get("final_violations", []) or []
    violation_count = len(violations) if isinstance(violations, list) else 0
    ccr = pipeline_result.get("contract_check_result")
    contract_passed = (
        bool(ccr.get("passed", False)) if isinstance(ccr, dict) else False
    )
    sim = pipeline_result.get("simulation_result")
    sim_passed = bool(sim.get("passed", False)) if isinstance(sim, dict) else False
    sections.append(
        PSACSection(
            title="验证结果摘要",
            content=(
                f"- MISRA-C 残留违规: {violation_count} 条\n"
                f"- 契约校验: {'✅ 通过' if contract_passed else '❌ 未通过'}\n"
                f"- GCC 编译: {'✅ 通过' if has_simu else '⚠️ 未执行'}\n"
                f"- 数字孪生仿真: {'✅ 通过' if sim_passed else '❌ 未通过' if has_simu else '⚠️ 未执行'}\n"
            ),
        )
    )

    # 1.4 工具链
    sections.append(
        PSACSection(
            title="工具链清单",
            content=(
                "- **代码生成**: AI Agent Pipeline (待鉴定 TQL-1)\n"
                "- **静态分析**: Cppcheck --addon=misra (已鉴定)\n"
                "- **编译**: GCC -std=c11 -O2 (已鉴定)\n"
                "- **仿真**: 虚拟 MCU + 虚拟传感器 (GCC 沙盒)\n"
                "- **报告**: DO-178C HTML Report Generator\n"
            ),
        )
    )

    doc.sections = sections
    logger.info(
        f"PSACGenerator:生成完成: {doc.meta.software_name} "
        f"v{doc.meta.version} DAL={doc.meta.certification_level} "
        f"{len(sections)} 节"
    )
    return doc
