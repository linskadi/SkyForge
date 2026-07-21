"""Markdown 报告渲染器。

实现 ReportRendererProtocol，生成 Markdown 格式报告。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from skyforge_engine.report.do178_objectives import check_objectives
from skyforge_engine.report.psac_generator import generate_psac
from skyforge_engine.utils.log_util import logger


class MarkdownRenderer:
    """Markdown 报告渲染器。

    将 ReportDataCollector 收集的数据渲染为 Markdown 格式报告。
    """

    @property
    def mime_type(self) -> str:
        return "text/markdown"

    @property
    def format_name(self) -> str:
        return "markdown"

    def render(self, data: dict[str, Any]) -> str:
        """渲染 Markdown 报告。

        Args:
            data: 报告数据字典（通常来自 ReportDataCollector.get_data）。

        Returns:
            完整 Markdown 报告字符串。
        """
        lines: list[str] = []

        # ---- 封面 ----
        requirement = data.get("requirement") or {}
        project_name = (
            requirement.get("module_name")
            or requirement.get("module")
            or "skyforge_module"
        )
        version = requirement.get("version", "1.0.0")
        safety_level = requirement.get("safety_level", "DAL-C")
        now = datetime.now()

        lines.append(f"# DO-178C 合规报告 — {project_name}")
        lines.append("")
        lines.append("| 项目 | 值 |")
        lines.append("|------|-----|")
        lines.append(f"| 软件版本 | {version} |")
        lines.append(f"| 安全等级 | {safety_level} |")
        lines.append(f"| 生成日期 | {now.strftime('%Y-%m-%d')} |")
        lines.append(f"| 生成时间 | {now.strftime('%H:%M:%S')} |")
        lines.append("")

        # ---- PSAC 摘要 ----
        try:
            psac = generate_psac(data)
            lines.append(psac.to_markdown())
            lines.append("")
        except Exception as e:
            logger.warning(f"MarkdownRenderer: PSAC 生成失败: {e}")
            lines.append("## PSAC 摘要")
            lines.append("")
            lines.append("PSAC 生成失败。")
            lines.append("")

        # ---- DO-178C 目标符合性 ----
        lines.append("## DO-178C 目标符合性表")
        lines.append("")
        try:
            objectives = check_objectives(data)
            pass_count = sum(1 for o in objectives if o.status == "满足")
            partial_count = sum(1 for o in objectives if o.status == "部分满足")
            fail_count = sum(1 for o in objectives if o.status == "未满足")
            na_count = sum(1 for o in objectives if o.status == "不适用")

            lines.append(
                f"**统计**: 满足 {pass_count} / 部分满足 {partial_count} / "
                f"未满足 {fail_count} / 不适用 {na_count}"
            )
            lines.append("")
            lines.append("| ID | 名称 | 状态 | 证据 |")
            lines.append("|----|------|------|------|")
            for obj in objectives:
                status_icon = {
                    "满足": "✅",
                    "部分满足": "⚠️",
                    "未满足": "❌",
                    "不适用": "➖",
                }.get(obj.status, "❓")
                lines.append(
                    f"| {obj.obj_id} | {obj.name} | {status_icon} {obj.status} | {obj.evidence} |"
                )
            lines.append("")
        except Exception as e:
            logger.warning(f"MarkdownRenderer: 目标检查失败: {e}")
            lines.append("目标检查生成失败。")
            lines.append("")

        # ---- 需求追溯矩阵 ----
        lines.append("## 需求追溯矩阵")
        lines.append("")
        try:
            from skyforge_engine.report.traceability_matrix import build_matrix

            matrix = build_matrix(data)
            if matrix:
                lines.append("| HLR | LLR | 契约 | 代码行 | 测试 | 结果 |")
                lines.append("|-----|-----|------|--------|------|------|")
                for entry in matrix:
                    req_id = entry.req_id or "-"
                    llr_id = entry.llr_id or "-"
                    contract_id = entry.contract_id or "-"
                    code_line = f"L{entry.code_line}" if entry.code_line else "-"
                    test_id = entry.test_id or "-"
                    test_result = entry.test_result or "-"
                    lines.append(
                        f"| {req_id} | {llr_id} | {contract_id} | {code_line} | {test_id} | {test_result} |"
                    )
                lines.append("")
            else:
                lines.append("无追溯数据。")
                lines.append("")
        except Exception as e:
            logger.warning(f"MarkdownRenderer: 追溯矩阵生成失败: {e}")
            lines.append("追溯矩阵生成失败。")
            lines.append("")

        # ---- MISRA-C 合规摘要 ----
        lines.append("## MISRA-C 合规摘要")
        lines.append("")
        cppcheck_result = data.get("cppcheck_result", []) or []
        final_violations = data.get("final_violations", []) or []
        repair_history = data.get("repair_history", []) or []
        lines.append(f"- 初次扫描违规: {len(cppcheck_result)} 条")
        lines.append(f"- 修复轮次: {len(repair_history)} 轮")
        lines.append(f"- 最终残留违规: {len(final_violations)} 条")
        lines.append("")

        # ---- 仿真结果 ----
        lines.append("## 数字孪生仿真结果")
        lines.append("")
        sim = data.get("simulation_result")
        if isinstance(sim, dict):
            steps = sim.get("total_steps", 0)
            passed = sim.get("passed", False)
            lines.append(f"- 仿真步数: {steps}")
            lines.append(f"- 仿真结果: {'通过' if passed else '未通过'}")
            fault = sim.get("fault_type")
            lines.append(f"- 故障注入: {fault or '无'}")
        else:
            lines.append("未执行数字孪生仿真。")
        lines.append("")

        # ---- 签名页 ----
        lines.append("## 签名页")
        lines.append("")
        lines.append("| 角色 | 签名 | 日期 |")
        lines.append("|------|------|------|")
        lines.append("| 开发者 | | ____ / ____ / ________ |")
        lines.append("| 审核者 | | ____ / ____ / ________ |")
        lines.append("| 批准者 | | ____ / ____ / ________ |")
        lines.append("| 质量保证 | | ____ / ____ / ________ |")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(
            f"*本报告由 SkyForge AI 中台流水线自动生成 — {now.strftime('%Y-%m-%d %H:%M:%S')}*"
        )
        lines.append("")

        return "\n".join(lines)
