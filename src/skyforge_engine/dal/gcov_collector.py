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

import gzip
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    """查找 lcov 并验证版本 >= 2.0。"""
    path = shutil.which("lcov")
    if not path:
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
        ToolNotFoundError: 真实覆盖率被禁用，或 GCC 不可用/版本不足。
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

    # lcov 可选：gcov JSON + gcov-dump 可独立收集覆盖率，无需 lcov
    # lcov 仅在 .info 格式解析时使用，gcov JSON 格式是首选
    lcov_path = _find_lcov()
    return _collect_from_gcov(code, test_inputs or [], lcov_path=lcov_path)


def _parse_gcov_json(gcov_data: dict) -> dict:
    """解析 gcov --json-format 输出的 JSON 数据。

    gcov JSON 格式 (GCC 16.x):
    {
      "format_version": "2",
      "gcc_version": "16.1.0",
      "files": [{
        "file": "...",
        "lines": [
          {"line_number": N, "count": C, "unexecuted_block": bool,
           "conditions": [...], "branches": [...]}
        ],
        "functions": [...]
      }]
    }
    """
    lines_total = 0
    lines_executed = 0
    branches_total = 0
    branches_taken = 0
    conditions_total = 0
    conditions_covered = 0

    for f in gcov_data.get("files", []):
        for line in f.get("lines", []):
            count = line.get("count", 0)
            if isinstance(count, (int, float)):
                lines_total += 1
                if count > 0 and not line.get("unexecuted_block", False):
                    lines_executed += 1
            for branch in line.get("branches", []):
                branches_total += 1
                if branch.get("count", 0) > 0:
                    branches_taken += 1
            # V0.5 Windows MC/DC: gcov JSON 可能含 conditions 数据（GCC 14+）
            for cond in line.get("conditions", []):
                conditions_total += 1
                # condition 包含 count 和 covered 字段
                if isinstance(cond, dict):
                    if cond.get("count", 0) > 0:
                        conditions_covered += 1
                elif isinstance(cond, (int, float)) and cond > 0:
                    conditions_covered += 1

    return {
        "lines_total": max(lines_total, 1),
        "lines_executed": lines_executed,
        "branches_total": max(branches_total, 1),
        "branches_taken": branches_taken,
        "conditions_total": conditions_total,
        "conditions_covered": conditions_covered,
        "functions_total": len(gcov_data.get("files", [{}])[0].get("functions", [])) if gcov_data.get("files") else 0,
        "functions_hit": 0,
    }


def _parse_gcov_dump_mcdc(gcda_path: str) -> dict[str, int]:
    """通过 gcov-dump -l 解析 .gcda 文件提取 MC/DC 条件覆盖率。

    Windows 上 gcov JSON 不含 MC/DC 数据，lcov 因 Perl 依赖不可用。
    本函数解析 ``gcov-dump -l`` 的 ``COUNTERS conditions`` 段来提取
    条件覆盖信息。

    gcov-dump -l 输出格式::

        01b10000:  16:COUNTERS conditions 2 counts
                          0: 3 3

    其中每个计数器值为掩码（bit 0 = false observed, bit 1 = true observed），
    一个条件『被覆盖』当且仅当掩码值同时设置了 bit 0 和 bit 1（value & 3 == 3）。

    Args:
        gcda_path: .gcda 文件的绝对路径。

    Returns:
        dict: {"conditions_total": int, "conditions_covered": int}
    """
    import shutil as _shutil

    gcov_dump_path = _shutil.which("gcov-dump")
    if not gcov_dump_path:
        # 尝试从 GCC 安装目录查找
        gcc_path = _find_gcc()
        if gcc_path:
            gcov_dump_path = str(Path(gcc_path).parent / ("gcov-dump" + (".exe" if os.name == "nt" else "")))
            if not os.path.isfile(gcov_dump_path):
                gcov_dump_path = None

    if not gcov_dump_path:
        logger.info("GcovCollector: gcov-dump 未找到，MC/DC 数据不可用")
        return {"conditions_total": 0, "conditions_covered": 0}

    try:
        result = subprocess.run(
            [gcov_dump_path, "-l", gcda_path],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10, check=False,
        )
        output = result.stdout or ""
    except Exception as e:
        logger.warning(f"GcovCollector: gcov-dump 执行失败: {e}")
        return {"conditions_total": 0, "conditions_covered": 0}

    conditions_total = 0
    conditions_covered = 0

    # V0.5.1: 从对应 .gcno 文件读取函数名，识别 main 并跳过其条件
    main_func_ident: set[int] = set()
    gcno_path = gcda_path.replace(".gcda", ".gcno")
    if os.path.isfile(gcno_path):
        try:
            gcno_out = subprocess.run(
                [gcov_dump_path, "-l", gcno_path],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=10, check=False,
            )
            for line in (gcno_out.stdout or "").splitlines():
                # .gcno FUNCTION 行格式:
                #   FUNCTION ident=108032747, ..., `main' file.c:line
                if "FUNCTION" in line and "`main'" in line:
                    m = re.search(r"ident=(\d+)", line)
                    if m:
                        main_func_ident.add(int(m.group(1)))
        except Exception:
            pass

    # 跟踪当前函数 ident（从 .gcda FUNCTION 行提取）
    current_ident = 0

    # 解析 COUNTERS conditions 段
    gcda_basename = os.path.basename(gcda_path)
    in_conditions = False
    for line in output.splitlines():
        stripped = line.strip()

        # 提取当前函数 ident
        if "FUNCTION" in stripped:
            m = re.search(r"ident=(\d+)", stripped)
            if m:
                current_ident = int(m.group(1))

        if "COUNTERS conditions" in stripped:
            in_conditions = True
            continue
        if not in_conditions:
            continue

        # V0.5.1: 跳过 main 函数的条件计数器
        if current_ident in main_func_ident:
            in_conditions = False
            continue

        # 移除文件名前缀（含 .gcda 后缀）：Windows 路径含 "C:" 冒号，
        # 不能用简单的 split(":")。定位 ".gcda:" 后进行解析。
        gcda_marker = gcda_basename + ":"
        idx = stripped.find(gcda_marker)
        if idx >= 0:
            after_file = stripped[idx + len(gcda_marker):].lstrip()
        else:
            # 回退: 尝试按 ".gcda:" 定位
            dot_gcda = stripped.find(".gcda:")
            if dot_gcda >= 0:
                after_file = stripped[dot_gcda + 6:].lstrip()
            else:
                after_file = stripped
        # 检测 "0: v1 v2 ..." 计数器行
        if after_file.startswith("0:") or after_file.startswith("0 "):
            try:
                if after_file.startswith("0:"):
                    values_part = after_file.split(":", 1)[1].strip()
                else:
                    values_part = after_file.split(" ", 1)[1].strip()
                values = [int(v) for v in values_part.split()]
                for v in values:
                    conditions_total += 1
                    # 掩码: bit 0 = false observed, bit 1 = true observed
                    # value & 3 == 3 表示 true 和 false 都被观察到
                    if (v & 3) == 3:
                        conditions_covered += 1
                in_conditions = False
                continue
            except (ValueError, IndexError):
                pass
        # 非计数器行：退出条件段
        in_conditions = False

    logger.info(
        f"GcovCollector: gcov-dump MC/DC: "
        f"covered={conditions_covered}/{conditions_total}"
    )
    return {
        "conditions_total": conditions_total,
        "conditions_covered": conditions_covered,
    }


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


def _is_cpp_code(code: str) -> bool:
    """检测代码是否为 C++（而非 C）。

    检查常见的 C++ 特有语法和头文件：
    - namespace 关键字
    - class/struct 带访问修饰符
    - template 关键字
    - C++ 标准库头文件（<array>, <vector>, <string>, <iostream>, <memory>）
    - nullptr 关键字
    - #pragma once（虽然 C 也可能用，但结合其他特征更可能是 C++）
    """
    cpp_indicators = [
        r'\bnamespace\s+\w+\s*\{',
        r'\bclass\s+\w+',
        r'\btemplate\s*<',
        r'#include\s*<(?:array|vector|string|iostream|memory|algorithm|cstdint|cmath)>',
        r'\bnullptr\b',
        r'\bconstexpr\b',
    ]
    score = 0
    for pattern in cpp_indicators:
        score += len(re.findall(pattern, code))
    # 高置信度：3+ 个 C++ 特征
    return score >= 2


def _generate_coverage_harness(code: str, test_inputs: list[float], is_cpp: bool = False) -> str:
    """为任意 C/C++ 函数生成覆盖率收集 harness。

    自动检测用户代码中的函数签名（返回类型、参数列表），
    生成能调用该函数的 test harness 以驱动覆盖率收集。

    支持的函数签名:
    - double func(double)        — 滤波器类
    - void func(void)            — 初始化类
    - RetType func(Type1, Type2) — 通用类（如 ARINC 429 解析器）
    """
    import math

    # 清除本地 #include "xxx.h"（头文件内容已内联，避免编译时找不到文件）
    code = re.sub(r'#include\s+"[^"]+\.h"\s*\n?', '', code)
    code = re.sub(r'#include\s+"[^"]+\.h"', '', code)

    # 1. 检测 init 类函数（无参数无返回值）
    init_match = re.search(r'void\s+(\w+_init)\s*\(\s*void\s*\)', code)
    init_call = f"    {init_match.group(1)}();\n" if init_match else ""

    # 2. 检测 double func(double) 签名（滤波器类）
    double_func_match = re.search(
        r'(?:static\s+)?double\s+(\w+)\s*\(\s*double\s+\w+\s*\)',
        code,
    )

    # 3. 检测通用函数签名（非 main、非 static helper）
    # 匹配: RetType funcName(Type1 param1, Type2 param2, ...)
    generic_func = None
    if not double_func_match:
        # 排除 main、static helper 和标准库函数
        for m in re.finditer(
            r'^[ \t]*(?:(?:static\s+)?(?:\w[\w\s\*]*?)\s+(\w+)\s*\(([^)]*)\))',
            code, re.MULTILINE,
        ):
            fname = m.group(1)
            params = m.group(2).strip()
            if fname in ("main", "printf", "scanf", "malloc", "free"):
                continue
            if fname.startswith("_"):
                continue
            # 跳过 void func(void) — 已经在 init 中处理
            if params == "void" or params == "":
                continue
            generic_func = (fname, params)
            break

    if double_func_match:
        # double func(double) harness — 滤波器类
        user_func = double_func_match.group(1)
        inputs_array = ",\n".join(f"        {v:.17g}" for v in test_inputs)
        harness = (
            "#include <stdio.h>\n"
            "#include <math.h>\n"
            "\n"
            "/* 用户代码 */\n"
            f"{code}\n"
            "\n"
            "int main(void) {\n"
            f"{init_call}"
            "    static const double _inputs[] = {\n"
            f"{inputs_array}\n"
            "    };\n"
            "    int _n = (int)(sizeof(_inputs) / sizeof(_inputs[0]));\n"
            "    int _i;\n"
            "    for (_i = 0; _i < _n; _i++) {\n"
            f"        {user_func}(_inputs[_i]);\n"
            "    }\n"
            "    return 0;\n"
            "}\n"
        )
    elif generic_func:
        # 通用函数 harness — 如 ARINC 429 解析器
        fname, params = generic_func
        # 解析参数列表，生成测试值
        param_list = [p.strip() for p in params.split(",") if p.strip()]
        call_args = []
        for param in param_list:
            # 提取参数类型和名称
            parts = param.rsplit(None, 1)
            if len(parts) == 2:
                ptype, pname = parts
            else:
                ptype, pname = param, "_arg"
            ptype_lower = ptype.lower().replace("const", "").strip()

            if "uint32" in ptype_lower or "int32" in ptype_lower or "uint" in ptype_lower:
                # 整数类型 — 生成多个测试值
                call_args.append("UINT32_VAL")
            elif "int8" in ptype_lower or "uint8" in ptype_lower or "char" in ptype_lower:
                call_args.append("UINT8_VAL")
            elif "int16" in ptype_lower or "uint16" in ptype_lower:
                call_args.append("UINT16_VAL")
            elif "double" in ptype_lower or "float" in ptype_lower:
                call_args.append("DBL_VAL")
            elif "*" in ptype:
                # 指针参数 — 需要声明变量
                call_args.append(f"&{pname}")
            else:
                call_args.append("0")

        # 生成多个测试调用以覆盖不同分支
        # 构造不同输入值来驱动分支覆盖
        test_calls = []
        # 从代码中提取可能的阈值用于边界测试
        hex_values = re.findall(r'0x[0-9A-Fa-f]+', code)
        decimal_values = re.findall(r'\b(\d{3,})\b', code)

        test_values = [0, 1, 0xFFFFFFFF, 0x80000000, 0x7FFFFFFF, 0x100, 255]
        for hv in hex_values[:5]:
            try:
                test_values.append(int(hv, 16))
            except ValueError:
                pass
        for dv in decimal_values[:5]:
            try:
                v = int(dv)
                if v <= 0xFFFFFFFF:
                    test_values.append(v)
            except ValueError:
                pass
        test_values = list(set(test_values))[:20]  # 去重，最多 20 个

        # 构造调用代码
        calls = []
        for val in test_values:
            args = []
            need_ptr_decl = []
            for i, (param, arg) in enumerate(zip(param_list, call_args)):
                parts = param.rsplit(None, 1)
                ptype = parts[0] if len(parts) == 2 else param
                pname = parts[1] if len(parts) == 2 else f"_arg{i}"
                if arg == "UINT32_VAL":
                    args.append(f"(uint32_t)0x{val:08X}u")
                elif arg == "UINT8_VAL":
                    args.append(f"(uint8_t)0x{val & 0xFF:02X}")
                elif arg == "UINT16_VAL":
                    args.append(f"(uint16_t)0x{val & 0xFFFF:04X}")
                elif arg == "DBL_VAL":
                    args.append(f"{float(val):.6f}")
                elif arg.startswith("&"):
                    need_ptr_decl.append(f"    {ptype} {pname};")
                    args.append(arg)

            decl_lines = "\n".join(need_ptr_decl) if need_ptr_decl else ""
            call_line = f"    {fname}({', '.join(args)});"
            if decl_lines:
                calls.append(decl_lines + "\n" + call_line)
            else:
                calls.append(call_line)

        calls_str = "\n".join(calls)
        if is_cpp:
            c_headers = "#include <cstdio>\n#include <cmath>\n"
        else:
            c_headers = "#include <stdio.h>\n#include <math.h>\n#include <stdint.h>\n#include <stdbool.h>\n"
        harness = (
            c_headers
            +
            "\n"
            "/* 用户代码 */\n"
            f"{code}\n"
            "\n"
            "int main(void) {\n"
            f"{init_call}"
            f"{calls_str}\n"
            "    return 0;\n"
            "}\n"
        )
    else:
        # 回退：仅调用 init 函数
        harness = (
            "#include <stdio.h>\n"
            "#include <math.h>\n"
            "\n"
            "/* 用户代码 */\n"
            f"{code}\n"
            "\n"
            "int main(void) {\n"
            f"{init_call}"
            "    return 0;\n"
            "}\n"
        )

    return harness


def _generate_default_inputs(code: str, n: int = 100) -> list[float]:
    """生成默认测试输入向量以驱动覆盖率收集。

    当未提供 test_inputs 时，利用代码中的信息（若无则用标准波形）
    生成一组能覆盖不同执行路径的输入。
    """
    import math

    inputs: list[float] = []

    # 边界值：覆盖范围检查逻辑（上下界 + 中间值）
    inputs.extend([0.0, 1.0, -1.0, 9999.0, -9999.0, 50.0,
                   21000.0, -0.001, 0.001])

    # 从代码中检测可能的阈值并针对性生成输入
    thresholds = re.findall(r'>\s*(\d+(?:\.\d+)?)', code)
    for t in thresholds:
        val = float(t)
        inputs.append(val - 1.0)
        inputs.append(val + 1.0)
        inputs.append(val)
    thresholds = re.findall(r'<\s*(-?\d+(?:\.\d+)?)', code)
    for t in thresholds:
        val = float(t)
        inputs.append(val - 1.0)
        inputs.append(val + 1.0)
        inputs.append(val)

    # 正弦波：覆盖滤波计算路径
    for i in range(n):
        inputs.append(50.0 * math.sin(2.0 * math.pi * 0.05 * i))

    return inputs


def _collect_from_gcov(code: str, test_inputs: list[float], lcov_path: str | None = None) -> GcovCoverageResult:
    """使用真实 gcov 收集覆盖率。

    流程:
    1. 检测用户函数签名并生成通用 harness
    2. 编译: gcc -fcondition-coverage -fprofile-arcs -ftest-coverage
    3. 执行: 运行测试二进制
    4. 收集: gcov JSON 格式（首选）或 lcov（可选）
    5. MC/DC: gcov-dump -l 解析 .gcda 条件覆盖率

    Raises:
        RuntimeError: GCC 编译失败或覆盖率收集失败。
    """
    if not test_inputs:
        test_inputs = _generate_default_inputs(code)

    # 检测代码语言：C 还是 C++
    is_cpp = _is_cpp_code(code)
    if is_cpp:
        logger.info("GcovCollector: 检测到 C++ 代码，使用 g++ 编译器")

    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / ("test_harness.cpp" if is_cpp else "test_harness.c")
        ext = ".exe" if os.name == "nt" else ""
        binary = Path(tmpdir) / f"test_harness{ext}"
        info_file = Path(tmpdir) / "coverage.info"

        # 检测用户代码中的函数签名（通用匹配）
        harness = _generate_coverage_harness(code, test_inputs, is_cpp=is_cpp)
        src.write_text(harness, encoding="utf-8")

        compiler, std_flag = ("g++", "-std=c++17") if is_cpp else (gcc, "-std=c11")
        compile_result = subprocess.run(
            [
                compiler, std_flag, "-O0", "-g",
                "-fcondition-coverage",  # GCC 14.2+ MC/DC 支持
                "-fprofile-arcs", "-ftest-coverage",
                "-o", str(binary), str(src), "-lm",
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )

        if compile_result.returncode != 0:
            raise RuntimeError(f"GCC 编译失败: {compile_result.stderr}")

        # 执行测试二进制（通过 stdin 传入输入或直接运行）
        subprocess.run(
            [str(binary)],
            input="",
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
        )

        # gcov JSON 解析（跨平台，优于 lcov）
        parsed: dict[str, Any] = {}
        try:
            gcov_path = shutil.which("gcov") or "gcov"
            gcov_result = subprocess.run(
                [gcov_path, "-j", "-b", "-c", "-a", "-u", "-k", "-o", str(binary), str(src)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=15, cwd=tmpdir,
            )
            gcov_json_gz = Path(tmpdir) / f"{src.stem}.gcov.json.gz"
            if not gcov_json_gz.exists():
                gcov_json_gz = Path(tmpdir) / f"{src.stem}.c.gcov.json.gz"
            if not gcov_json_gz.exists():
                gcov_json_gz = Path(tmpdir) / f"{binary.stem}-{src.stem}.c.gcov.json.gz"
            if not gcov_json_gz.exists():
                import glob as _glob
                matches = _glob.glob(str(Path(tmpdir) / "*.gcov.json.gz"))
                if matches:
                    gcov_json_gz = Path(matches[0])
            if gcov_json_gz.exists():
                with gzip.open(gcov_json_gz, "rt", encoding="utf-8") as gf:
                    gcov_data = json.load(gf)
                parsed = _parse_gcov_json(gcov_data)
            elif gcov_result.returncode == 0:
                # 非 gzip JSON 回退 stdout
                parsed = _parse_lcov_info(gcov_result.stdout)
        except Exception as gcov_err:
            raise RuntimeError(f"gcov JSON 收集失败: {gcov_err}") from gcov_err

        if not parsed:
            raise RuntimeError("gcov 无法收集覆盖率")

        lines_total = parsed["lines_total"]
        lines_executed = parsed["lines_executed"]
        branches_total = parsed["branches_total"]
        branches_taken = parsed["branches_taken"]

        # V0.5 Windows MC/DC: gcov JSON 通常不含条件数据，回退 gcov-dump
        conditions_total = parsed.get("conditions_total", 0) or 0
        conditions_covered = parsed.get("conditions_covered", 0) or 0

        if conditions_total == 0:
            # 尝试从 gcov-dump 提取 MC/DC 条件覆盖率
            gcda_pattern = os.path.join(tmpdir, "*.gcda")
            import glob as _glob2
            gcda_files = _glob2.glob(gcda_pattern)
            if not gcda_files:
                # 也检查 test_harness.gcda
                gcda_files = _glob2.glob(os.path.join(tmpdir, f"{binary.stem}*.gcda"))
            mcdc_total = 0
            mcdc_covered = 0
            for gcda_file in gcda_files:
                mcdc = _parse_gcov_dump_mcdc(gcda_file)
                mcdc_total += mcdc["conditions_total"]
                mcdc_covered += mcdc["conditions_covered"]
            if mcdc_total > 0:
                conditions_total = mcdc_total
                conditions_covered = mcdc_covered

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
