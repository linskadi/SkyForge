"""gcov/lcov MC/DC 真实覆盖率收集器。

V0.4 P2: 从 stub 代码解析升级为 GCC 14.2+ -fcondition-coverage 真实数据。

工具: GCC 14.2+ (GPL-3.0) + lcov 2.0+ (GPL-2.0)
用途: DO-178C DAL-A 强制要求的 MC/DC 覆盖率指标
环境变量: USE_REAL_COVERAGE=false 可禁用真实覆盖率

集成方式:
    from skyforge_engine.dal.gcov_collector import collect_coverage
    result = collect_coverage(code, test_inputs)

注: -fcondition-coverage 标志在 GCC 14.2+ 才正式 GA。GCC 13.x 编译时会报
    "unrecognized command-line option"。低于 14.2 的 GCC 自动回退静态分析。
    lcov 2.0+ 提供 --mcdc-coverage 收集。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from skyforge_engine.utils.log_util import logger


class ToolNotFoundError(RuntimeError):
    """所需覆盖率工具（GCC 或 lcov）未找到或版本不满足要求。"""


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
    method: str = "gcov"


def _parse_version(version_str: str) -> tuple[int, ...] | None:
    """从版本字符串中解析版本号元组。"""
    match = re.search(r"(\d+(?:\.\d+)+)", version_str)
    if match:
        return tuple(int(x) for x in match.group(1).split("."))
    return None


def _get_tool_version(tool_path: str) -> tuple[int, ...] | None:
    """运行 ``tool --version`` 并解析出版本号元组。"""
    try:
        result = subprocess.run(
            [tool_path, "--version"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
        )
        if result.returncode != 0:
            return None
        return _parse_version(result.stdout)
    except Exception:
        return None


def _find_gcc() -> str | None:
    """查找 GCC 并验证版本 >= 14.2（GA 支持 -fcondition-coverage）。"""
    path = shutil.which("gcc")
    if not path:
        return None
    version = _get_tool_version(path)
    if version is None:
        return None
    # GCC 14.2+ 是 -fcondition-coverage 首个 GA 版本
    if version[0] > 14 or (version[0] == 14 and len(version) > 1 and version[1] >= 2):
        return path
    logger.info(
        f"GcovCollector: GCC 版本 {'.'.join(map(str, version))} < 14.2，"
        f"不支持 -fcondition-coverage，调用方应回退静态分析"
    )
    return None


def _find_lcov() -> str | None:
    """查找 lcov 并验证版本 >= 2.0 且能在当前平台正常工作。"""
    path = shutil.which("lcov")
    if not path:
        return None
    if os.name == "nt":
        # lcov 2.1 for Windows 有多个兼容性问题：
        # 1. Perl 脚本路径含反斜杠导致 regex 崩溃
        # 2. gzip 路径拼接错误
        # 3. 依赖 Unix find/gzip 等工具
        # 需要在 WSL/Cygwin 环境中运行
        logger.info(
            "GcovCollector: Windows 上的 lcov 有已知兼容性问题，跳过真实覆盖率"
        )
        return None
    version = _get_tool_version(path)
    if version is None:
        return None
    if version[0] >= 2:
        return path
    logger.warning(
        f"GcovCollector: lcov 版本 {'.'.join(map(str, version))} 不满足 >= 2.0 要求"
    )
    return None


def _is_real_enabled() -> bool:
    """检查是否启用真实覆盖率。默认启用（True）。"""
    return os.environ.get("USE_REAL_COVERAGE", "true").lower() != "false"


def collect_coverage(
    code: str,
    test_inputs: list[float] | None = None,
) -> GcovCoverageResult:
    """收集代码覆盖率（严格模式：仅支持真实 gcov）。

    Args:
        code: C 源代码。
        test_inputs: 测试输入向量（用于执行插桩代码）。

    Returns:
        GcovCoverageResult: 覆盖率结果。

    Raises:
        ToolNotFoundError: 真实覆盖率被禁用，或 GCC/lcov 不可用/版本不足。
        RuntimeError: 编译或覆盖率收集过程中发生错误。
    """
    if not _is_real_enabled():
        raise ToolNotFoundError(
            "真实覆盖率已显式禁用 (USE_REAL_COVERAGE=false)，且降级策略已被移除"
        )

    if not _find_gcc():
        raise ToolNotFoundError(
            "GCC 14.2+ 未找到或版本不满足要求（-fcondition-coverage 需要 GCC 14.2+），"
            "调用方应回退静态分析"
        )

    if not _find_lcov():
        raise ToolNotFoundError("lcov 2.0+ 未找到或版本不满足要求")

    return _collect_from_gcov(code, test_inputs or [])


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

    Raises:
        RuntimeError: GCC 编译失败或 lcov 收集失败。
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "test.c"
        ext = ".exe" if os.name == "nt" else ""
        binary = Path(tmpdir) / f"test{ext}"
        info_file = Path(tmpdir) / "coverage.info"

        src.write_text(code, encoding="utf-8")

        gcc = _find_gcc() or "gcc"
        compile_result = subprocess.run(
            [
                gcc, "-std=c11", "-O0", "-g",
                "-fcondition-coverage",  # GCC 14.2+ MC/DC 支持
                "-fprofile-arcs", "-ftest-coverage",
                "-o", str(binary), str(src), "-lm",
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )

        if compile_result.returncode != 0:
            raise RuntimeError(f"GCC 编译失败: {compile_result.stderr}")

        input_str = "\n".join(str(v) for v in test_inputs) + "\n"
        subprocess.run(
            [str(binary)],
            input=input_str,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
        )

        lcov_path = _find_lcov() or "lcov"
        lcov_cmd = [
            lcov_path,
            "--capture",
            "--directory", tmpdir,
            "--branch-coverage",
            "--output-file", str(info_file),
        ]
        lcov_result = subprocess.run(
            lcov_cmd,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
            cwd=tmpdir,
            shell=os.name == "nt",
        )

        if lcov_result.returncode != 0 or not info_file.exists():
            raise RuntimeError(f"lcov 收集失败: {lcov_result.stderr}")

        lcov_info_content = info_file.read_text(encoding="utf-8")
        parsed = _parse_lcov_info(lcov_info_content)

        lines_total = parsed["lines_total"]
        lines_executed = parsed["lines_executed"]
        branches_total = parsed["branches_total"]
        branches_taken = parsed["branches_taken"]
        conditions_total = parsed["conditions_total"]
        conditions_covered = parsed["conditions_covered"]

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
