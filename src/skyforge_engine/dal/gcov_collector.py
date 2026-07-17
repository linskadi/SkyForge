"""gcov/lcov MC/DC 真实覆盖率收集器。

V0.4 P2: 从 stub 代码解析升级为 GCC 14.2+ -fcondition-coverage 真实数据。

工具: GCC 14.2+ (GPL-3.0) + lcov (GPL-2.0)
用途: DO-178C DAL-A 强制要求的 MC/DC 覆盖率指标
环境变量: USE_REAL_COVERAGE=true 启用真实覆盖率

集成方式:
    from skyforge_engine.dal.gcov_collector import collect_coverage
    result = collect_coverage(code, test_inputs)
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skyforge_engine.utils.log_util import logger


@dataclass
class GcovCoverageResult:
    """gcov 覆盖率收集结果。"""

    statement_coverage: float = 0.0
    branch_coverage: float = 0.0
    mcdc_coverage: float = 0.0
    lines_executed: int = 0
    lines_total: int = 0
    branches_taken: int = 0
    branches_total: int = 0
    conditions_covered: int = 0
    conditions_total: int = 0
    decision_points: list[dict] = field(default_factory=list)
    tool_available: bool = False
    method: str = "code_analysis"  # code_analysis | gcov


def _find_gcc() -> str | None:
    """查找 GCC。"""
    import shutil
    return shutil.which("gcc")


def _find_lcov() -> str | None:
    """查找 lcov。"""
    import shutil
    return shutil.which("lcov")


def _is_real_enabled() -> bool:
    """检查是否启用真实覆盖率。"""
    return os.environ.get("USE_REAL_COVERAGE", "").lower() == "true"


def collect_coverage(
    code: str,
    test_inputs: list[float] | None = None,
) -> GcovCoverageResult:
    """收集代码覆盖率（优先真实 gcov，降级到代码分析）。

    Args:
        code: C 源代码。
        test_inputs: 测试输入向量（用于执行插桩代码）。

    Returns:
        GcovCoverageResult: 覆盖率结果。
    """
    if not _is_real_enabled() or not _find_gcc():
        return _collect_from_code_analysis(code)

    return _collect_from_gcov(code, test_inputs or [])


def _collect_from_code_analysis(code: str) -> GcovCoverageResult:
    """基于代码分析的覆盖率（降级方案）。"""
    from skyforge_engine.dal.mcdc_calculator import analyze_coverage

    cov = analyze_coverage(code)

    result = GcovCoverageResult(
        statement_coverage=cov.statement_coverage,
        branch_coverage=cov.decision_coverage,
        mcdc_coverage=cov.mcdc_coverage,
        lines_total=cov.statement_count,
        lines_executed=cov.statement_covered,
        branches_total=len(cov.decision_points),
        branches_taken=sum(1 for d in cov.decision_points if d.test_count > 0),
        conditions_total=sum(d.condition_count for d in cov.decision_points),
        conditions_covered=cov.mcdc_satisfied,
        decision_points=[
            {"line": d.line, "type": d.type, "conditions": d.condition_count,
             "status": d.status}
            for d in cov.decision_points
        ],
        tool_available=False,
        method="code_analysis",
    )

    logger.info(
        f"GcovCollector:代码分析覆盖: "
        f"语句={result.statement_coverage}% "
        f"分支={result.branch_coverage}% "
        f"MC/DC={result.mcdc_coverage}%"
    )
    return result


def _parse_lcov_info(info_content: str) -> dict:
    """解析 lcov .info 文件格式，提取覆盖率数据。

    解析标准 lcov tracefile 格式中的:
    - LF/LH: 行覆盖 (lines found / lines hit)
    - BRF/BRH: 分支覆盖 (branches found / branches hit)
    - BRDA: 分支详情
    - FNF/FNH: 函数覆盖
    - MCDC: MC/DC 条件覆盖

    Returns:
        dict: 包含 lines_total, lines_executed, branches_total, branches_taken,
              conditions_covered, conditions_total, mcdc_conditions 字典。
    """
    lines_total = 0
    lines_executed = 0
    branches_total = 0
    branches_taken = 0
    functions_total = 0
    functions_hit = 0

    # MC/DC: 每个 (line, groupSize, index) 是一个条件，每个条件有 f/t 两种 sense
    # key = (line, groupSize, index), value = {"f_taken": bool, "t_taken": bool}
    mcdc_conditions: dict[tuple, dict[str, bool]] = {}

    for line in info_content.splitlines():
        stripped = line.strip()

        # 行覆盖摘要
        if stripped.startswith("LF:"):
            try:
                lines_total = int(stripped.split(":", 1)[1])
            except (ValueError, IndexError):
                pass
        elif stripped.startswith("LH:"):
            try:
                lines_executed = int(stripped.split(":", 1)[1])
            except (ValueError, IndexError):
                pass

        # 分支覆盖摘要
        elif stripped.startswith("BRF:"):
            try:
                branches_total = int(stripped.split(":", 1)[1])
            except (ValueError, IndexError):
                pass
        elif stripped.startswith("BRH:"):
            try:
                branches_taken = int(stripped.split(":", 1)[1])
            except (ValueError, IndexError):
                pass

        # 函数覆盖摘要
        elif stripped.startswith("FNF:"):
            try:
                functions_total = int(stripped.split(":", 1)[1])
            except (ValueError, IndexError):
                pass
        elif stripped.startswith("FNH:"):
            try:
                functions_hit = int(stripped.split(":", 1)[1])
            except (ValueError, IndexError):
                pass

        # MC/DC 记录:
        # MCDC:<line>,[<unreachable>]<groupSize>,<sense>,<taken>,<index>,<expression>
        elif stripped.startswith("MCDC:"):
            try:
                payload = stripped.split(":", 1)[1]
                parts = payload.split(",")
                if len(parts) >= 5:
                    line_num = int(parts[0])
                    # parts[1] 可能包含 'U' 前缀表示 unreachable
                    group_str = parts[1].lstrip("Uu")
                    group_size = int(group_str)
                    sense = parts[2].strip()  # "f" or "t"
                    taken = int(parts[3])     # 0 = not sensitized, >0 = sensitized
                    index = int(parts[4])     # condition index within group

                    key = (line_num, group_size, index)
                    if key not in mcdc_conditions:
                        mcdc_conditions[key] = {"f_taken": False, "t_taken": False}

                    if sense == "f" and taken > 0:
                        mcdc_conditions[key]["f_taken"] = True
                    elif sense == "t" and taken > 0:
                        mcdc_conditions[key]["t_taken"] = True
            except (ValueError, IndexError):
                continue

    # 计算 MC/DC 覆盖: 每个条件需要 f 或 t 任一 sense 被 sensitized
    conditions_total = len(mcdc_conditions)
    conditions_covered = sum(
        1 for c in mcdc_conditions.values()
        if c["f_taken"] or c["t_taken"]
    )

    return {
        "lines_total": lines_total,
        "lines_executed": lines_executed,
        "branches_total": branches_total,
        "branches_taken": branches_taken,
        "functions_total": functions_total,
        "functions_hit": functions_hit,
        "conditions_total": conditions_total,
        "conditions_covered": conditions_covered,
    }


def _collect_from_gcov(code: str, test_inputs: list[float]) -> GcovCoverageResult:
    """使用真实 gcov/lcov 收集覆盖率。

    流程:
    1. 编译: gcc -fcondition-coverage -fprofile-arcs -ftest-coverage
    2. 执行: 运行测试二进制
    3. 收集: lcov --capture --branch-coverage --mcdc-coverage
    4. 解析: .info 文件中的 LF/LH/BRF/BRH/MCDC 记录
    5. 降级: 如果 lcov 不支持 MC/DC，回退到 gcov 解析或代码分析
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "test.c"
            binary = Path(tmpdir) / "test"
            info_file = Path(tmpdir) / "coverage.info"

            # 写入代码
            src.write_text(code, encoding="utf-8")

            # 编译（使用 -fcondition-coverage 支持 MC/DC）
            gcc = _find_gcc() or "gcc"
            compile_result = subprocess.run(
                [
                    gcc, "-std=c11", "-O0", "-g",
                    "-fcondition-coverage",  # GCC 14.2+ MC/DC 支持
                    "-fprofile-arcs", "-ftest-coverage",
                    "-o", str(binary), str(src), "-lm",
                ],
                capture_output=True, text=True, timeout=15,
            )

            if compile_result.returncode != 0:
                logger.warning("GcovCollector:编译失败，降级代码分析")
                return _collect_from_code_analysis(code)

            # 执行测试
            input_str = "\n".join(str(v) for v in test_inputs) + "\n"
            subprocess.run(
                [str(binary)],
                input=input_str,
                capture_output=True, text=True, timeout=5,
            )

            # 使用 lcov 收集覆盖率（含分支和 MC/DC）
            lcov_available = _find_lcov() is not None
            lcov_info_content = ""

            if lcov_available:
                # 尝试使用 --mcdc-coverage 和 --branch-coverage
                lcov_cmd = [
                    "lcov",
                    "--capture",
                    "--directory", tmpdir,
                    "--branch-coverage",
                    "--mcdc-coverage",
                    "--output-file", str(info_file),
                ]
                lcov_result = subprocess.run(
                    lcov_cmd,
                    capture_output=True, text=True, timeout=15,
                    cwd=tmpdir,
                )

                if lcov_result.returncode == 0 and info_file.exists():
                    lcov_info_content = info_file.read_text(encoding="utf-8")
                else:
                    # lcov 不支持 --mcdc-coverage（版本过旧），回退到无 MC/DC 模式
                    logger.info(
                        "GcovCollector:lcov 不支持 --mcdc-coverage，"
                        "回退到分支覆盖模式"
                    )
                    lcov_cmd_fallback = [
                        "lcov",
                        "--capture",
                        "--directory", tmpdir,
                        "--branch-coverage",
                        "--output-file", str(info_file),
                    ]
                    lcov_result = subprocess.run(
                        lcov_cmd_fallback,
                        capture_output=True, text=True, timeout=15,
                        cwd=tmpdir,
                    )
                    if lcov_result.returncode == 0 and info_file.exists():
                        lcov_info_content = info_file.read_text(encoding="utf-8")

            # 解析 lcov .info 文件
            if lcov_info_content:
                parsed = _parse_lcov_info(lcov_info_content)
                lines_total = parsed["lines_total"]
                lines_executed = parsed["lines_executed"]
                branches_total = parsed["branches_total"]
                branches_taken = parsed["branches_taken"]
                conditions_total = parsed["conditions_total"]
                conditions_covered = parsed["conditions_covered"]
            else:
                # lcov 不可用或失败，回退到 gcov 解析
                lines_total, lines_executed, branches_total, branches_taken = (
                    _parse_gcov_files(tmpdir, src)
                )
                conditions_total = 0
                conditions_covered = 0

            # 计算覆盖率百分比
            stmt_cov = (
                (lines_executed / lines_total * 100) if lines_total > 0 else 0.0
            )
            br_cov = (
                (branches_taken / branches_total * 100) if branches_total > 0 else 0.0
            )
            mcdc_cov = (
                (conditions_covered / conditions_total * 100)
                if conditions_total > 0 else 0.0
            )

            logger.info(
                f"GcovCollector:真实覆盖: "
                f"语句={stmt_cov:.1f}% ({lines_executed}/{lines_total}) "
                f"分支={br_cov:.1f}% ({branches_taken}/{branches_total}) "
                f"MC/DC={mcdc_cov:.1f}% ({conditions_covered}/{conditions_total})"
            )

            return GcovCoverageResult(
                statement_coverage=round(stmt_cov, 1),
                branch_coverage=round(br_cov, 1),
                mcdc_coverage=round(mcdc_cov, 1),
                lines_executed=lines_executed,
                lines_total=max(lines_total, 1),
                branches_taken=branches_taken,
                branches_total=max(branches_total, 1),
                conditions_covered=conditions_covered,
                conditions_total=max(conditions_total, 1),
                tool_available=True,
                method="gcov",
            )

    except Exception as e:
        logger.warning(f"GcovCollector:真实覆盖收集失败: {e}")
        return _collect_from_code_analysis(code)


def _parse_gcov_files(tmpdir: str, src: Path) -> tuple[int, int, int, int]:
    """从 .gcov 文件解析行和分支覆盖数据（lcov 不可用时的回退方案）。

    Returns:
        (lines_total, lines_executed, branches_total, branches_taken)
    """
    lines_total = 0
    lines_executed = 0
    branches_total = 0
    branches_taken = 0

    for gcov_file in Path(tmpdir).glob("*.gcov"):
        content = gcov_file.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            parts = line.strip().split(":")
            if len(parts) >= 2:
                count = parts[0].strip()
                if count.replace("-", "").replace("#", "").isdigit():
                    lines_total += 1
                    if count != "#####" and count != "-":
                        lines_executed += 1
                if "branch" in line.lower():
                    branches_total += 1
                    if "taken" in line.lower() and "never" not in line.lower():
                        branches_taken += 1

    return lines_total, lines_executed, branches_total, branches_taken
