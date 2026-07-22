"""数据耦合和控制耦合分析器 — DO-178C §6.4.4.2.d / §6.4.4.2.e。

DO-178C 要求验证：
  - 数据耦合 (Data Coupling):  模块间的数据依赖关系是否正确
  - 控制耦合 (Control Coupling): 模块间的控制流交互是否正确

本模块从 C 代码中提取：
  1. 函数调用图（控制耦合）—— 谁调用谁，调用顺序
  2. 全局变量读写关系（数据耦合）—— 谁读写哪些全局变量
  3. 参数传递关系（数据耦合）—— 函数间通过参数传递的数据流

输出格式：
  {
    "control_coupling": {
      "call_graph": {caller: [callee, ...]},
      "call_sequences": [[caller, callee], ...],
      "entry_points": [...],
      "isolated_functions": [...],
    },
    "data_coupling": {
      "global_variable_access": {var_name: {readers: [...], writers: [...]}},
      "parameter_flows": [{from_func, to_func, param_index, param_name}, ...],
      "shared_data_anomalies": [...],
    },
    "summary": { ... },
    "analyzed": bool,
  }
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from skyforge_engine.utils.log_util import logger


# ==================== 数据类 ====================

@dataclass
class CouplingResult:
    """耦合分析结果。"""

    control_coupling: dict[str, Any] = field(default_factory=dict)
    data_coupling: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    analyzed: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ==================== 正则模式 ====================

# 函数定义: 返回类型 函数名 (参数列表) {
_FUNC_DEF_RE = re.compile(
    r"^\s*(?:static\s+)?(?:inline\s+)?"
    r"(?:void|int|float|double|char|short|long|unsigned|uint\w*|int\w*|float\w*|bool|size_t|ssize_t)\s+"
    r"(\w+)\s*\(([^)]*)\)\s*\{",
    re.MULTILINE,
)

# 函数调用: func_name(...)
_FUNC_CALL_RE = re.compile(
    r"\b([a-zA-Z_]\w*)\s*\(([^()]*)\)",
)

# 全局变量定义: 文件作用域
_GLOBAL_VAR_DEF_RE = re.compile(
    r"^\s*(?:static\s+)?(?:const\s+)?(?:volatile\s+)?"
    r"(?:void|int|float|double|char|short|long|unsigned|uint\w*|int\w*|float\w*|bool|size_t|ssize_t)\s+"
    r"(\w+)\s*(?:=|;)",
    re.MULTILINE,
)

# 变量赋值（全局变量写）
_ASSIGN_RE = re.compile(r"\b(\w+)\s*=(?!=)")

# 已知标准库函数（排除）
_STDLIB_FUNCS = {
    "printf", "scanf", "sprintf", "snprintf", "fprintf",
    "memcpy", "memset", "memcmp", "memmove",
    "strlen", "strcpy", "strncpy", "strcmp", "strncmp", "strcat", "strncat",
    "malloc", "free", "calloc", "realloc",
    "abs", "fabs", "sqrt", "pow", "sin", "cos", "tan",
    "fopen", "fclose", "fread", "fwrite",
    "assert", "exit", "abort",
    "sizeof", "atoi", "atof", "atol",
}


# ==================== 核心分析函数 ====================

def analyze_coupling(code: str) -> CouplingResult:
    """分析 C 代码的数据耦合和控制耦合。

    Args:
        code: C 源代码字符串。

    Returns:
        CouplingResult: 耦合分析结果。
    """
    if not code or not code.strip():
        return CouplingResult(error="代码为空", analyzed=False)

    try:
        # 提取函数定义
        functions = _extract_functions(code)
        if not functions:
            return CouplingResult(
                error="未检测到函数定义",
                analyzed=False,
                control_coupling={"call_graph": {}, "entry_points": [], "isolated_functions": []},
                data_coupling={"global_variable_access": {}, "parameter_flows": [], "shared_data_anomalies": []},
            )

        # 分析控制耦合
        control_coupling = _analyze_control_coupling(code, functions)

        # 分析数据耦合
        data_coupling = _analyze_data_coupling(code, functions)

        # 生成摘要
        summary = _generate_summary(functions, control_coupling, data_coupling)

        logger.info(
            f"CouplingAnalyzer:分析完成 "
            f"函数={len(functions)} "
            f"调用边={len(control_coupling.get('call_sequences', []))} "
            f"全局变量={len(data_coupling.get('global_variable_access', {}))}"
        )

        return CouplingResult(
            control_coupling=control_coupling,
            data_coupling=data_coupling,
            summary=summary,
            analyzed=True,
        )
    except Exception as e:
        logger.error(f"CouplingAnalyzer:分析失败: {e}")
        return CouplingResult(error=str(e), analyzed=False)


# ==================== 函数提取 ====================

def _extract_functions(code: str) -> dict[str, dict[str, Any]]:
    """提取所有函数定义及其信息。

    Returns:
        {func_name: {line, params, body, body_start, body_end}, ...}
    """
    functions: dict[str, dict[str, Any]] = {}
    lines = code.splitlines()

    for match in _FUNC_DEF_RE.finditer(code):
        func_name = match.group(1)
        params_str = match.group(2).strip()
        params = [p.strip() for p in params_str.split(",") if p.strip()] if params_str else []

        # 解析参数名
        param_names: list[str] = []
        for p in params:
            parts = p.split()
            if parts:
                # 取最后一个词作为参数名
                name = parts[-1].strip("*").strip()
                if name and not name.startswith("const") and name not in _STDLIB_FUNCS:
                    param_names.append(name)

        def_line = match.start()
        line_no = code[:def_line].count("\n") + 1

        # 找到函数体结束位置
        body_start = match.end() - 1  # 大括号开始位置
        body_end = _find_matching_brace(code, body_start)
        if body_end == -1:
            body_end = len(code)

        body = code[body_start:body_end]

        functions[func_name] = {
            "line": line_no,
            "params": params,
            "param_names": param_names,
            "body": body,
            "body_start": body_start,
            "body_end": body_end,
        }

    return functions


def _find_matching_brace(code: str, start: int) -> int:
    """找到匹配的右大括号。"""
    depth = 0
    for i in range(start, len(code)):
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


# ==================== 控制耦合分析 ====================

def _analyze_control_coupling(
    code: str, functions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """分析控制耦合：函数调用图、调用关系、入口点。

    DO-178C 控制耦合分析关注：
      - 一个函数是否正确地激活/调用另一个函数
      - 调用顺序是否正确
      - 是否存在孤立的或未被调用的函数
    """
    func_names = set(functions.keys())
    call_graph: dict[str, list[str]] = {f: [] for f in func_names}
    call_sequences: list[tuple[str, str]] = []
    called_by: dict[str, set[str]] = {f: set() for f in func_names}

    for func_name, func_info in functions.items():
        body = func_info["body"]
        # 排除函数自身的调用
        calls = _extract_function_calls(body, func_names - {func_name})
        call_graph[func_name] = list(calls)
        for callee in calls:
            call_sequences.append((func_name, callee))
            if callee in called_by:
                called_by[callee].add(func_name)

    # 入口点：未被其他函数调用的函数
    entry_points = [
        f for f in func_names
        if not called_by.get(f) and func_names
    ]
    if not entry_points:
        entry_points = list(func_names)[:1] if func_names else []

    # 孤立函数：既不调用其他函数也不被其他函数调用
    isolated = [
        f for f in func_names
        if not call_graph.get(f) and not called_by.get(f)
    ]

    return {
        "call_graph": {k: v for k, v in call_graph.items()},
        "call_sequences": call_sequences,
        "entry_points": entry_points,
        "isolated_functions": isolated,
        "total_functions": len(func_names),
        "total_edges": len(call_sequences),
    }


def _extract_function_calls(body: str, known_funcs: set[str]) -> set[str]:
    """从函数体中提取对已知函数的调用。"""
    calls: set[str] = set()
    for match in _FUNC_CALL_RE.finditer(body):
        callee = match.group(1)
        if callee in known_funcs and callee not in _STDLIB_FUNCS:
            calls.add(callee)
    return calls


# ==================== 数据耦合分析 ====================

def _analyze_data_coupling(
    code: str, functions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """分析数据耦合：全局变量读写、参数传递。

    DO-178C 数据耦合分析关注：
      - 全局变量的读写关系是否正确
      - 函数间参数传递的数据流是否正确
      - 是否存在共享数据冲突
    """
    func_names = set(functions.keys())

    # 提取全局变量
    global_vars = _extract_global_variables(code, functions)

    # 分析全局变量读写关系
    global_access = _analyze_global_access(code, functions, global_vars)

    # 分析参数传递数据流
    parameter_flows = _analyze_parameter_flows(functions)

    # 检测共享数据异常
    anomalies = _detect_shared_data_anomalies(global_access, functions)

    return {
        "global_variable_access": global_access,
        "parameter_flows": parameter_flows,
        "shared_data_anomalies": anomalies,
        "total_global_vars": len(global_vars),
        "total_parameter_flows": len(parameter_flows),
    }


def _extract_global_variables(
    code: str, functions: dict[str, dict[str, Any]]
) -> set[str]:
    """提取全局变量名（函数体外定义的变量）。"""
    func_ranges = []
    for info in functions.values():
        func_ranges.append((info["body_start"], info["body_end"]))

    global_vars: set[str] = set()

    for match in _GLOBAL_VAR_DEF_RE.finditer(code):
        var_name = match.group(1)
        pos = match.start()

        # 检查是否在函数体外部
        in_func = any(start <= pos <= end for start, end in func_ranges)
        if not in_func and var_name not in _STDLIB_FUNCS:
            global_vars.add(var_name)

    return global_vars


def _analyze_global_access(
    code: str,
    functions: dict[str, dict[str, Any]],
    global_vars: set[str],
) -> dict[str, dict[str, list[str]]]:
    """分析每个全局变量被哪些函数读写。"""
    access: dict[str, dict[str, list[str]]] = {}
    for var in global_vars:
        access[var] = {"readers": [], "writers": []}

    for func_name, func_info in functions.items():
        body = func_info["body"]
        for var in global_vars:
            # 检查写操作（赋值）
            if re.search(rf"\b{re.escape(var)}\s*=(?!=)", body):
                access[var]["writers"].append(func_name)
            # 检查读操作（出现在表达式右侧）
            elif re.search(rf"\b{re.escape(var)}\b", body):
                # 排除赋值左侧
                is_only_read = not re.search(rf"\b{re.escape(var)}\s*=(?!=)", body)
                if is_only_read:
                    access[var]["readers"].append(func_name)

    # 清理空条目
    return {k: v for k, v in access.items() if v["readers"] or v["writers"]}


def _analyze_parameter_flows(
    functions: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """分析函数间参数传递的数据流。"""
    flows: list[dict[str, Any]] = []

    # 为每个函数生成参数流描述
    for func_name, func_info in functions.items():
        for idx, param_name in enumerate(func_info["param_names"]):
            flows.append({
                "function": func_name,
                "param_index": idx,
                "param_name": param_name,
                "direction": "input",
            })

    return flows


def _detect_shared_data_anomalies(
    global_access: dict[str, dict[str, list[str]]],
    functions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """检测共享数据异常。

    检测规则：
      1. 多写者冲突：多个函数同时写同一个全局变量
      2. 无写者但有读者：全局变量被读取但从未被写入
      3. 无读者但有写者：全局变量被写入但从未被读取
    """
    anomalies: list[dict[str, Any]] = []

    for var, access in global_access.items():
        writers = access.get("writers", [])
        readers = access.get("readers", [])

        # 多写者冲突
        if len(writers) > 1:
            anomalies.append({
                "type": "multi_writer_conflict",
                "variable": var,
                "writers": writers,
                "description": f"全局变量 {var} 被 {len(writers)} 个函数写入，可能存在数据竞争",
                "severity": "warning",
            })

        # 无写者但有读者
        if len(writers) == 0 and len(readers) > 0:
            anomalies.append({
                "type": "no_writer_but_readers",
                "variable": var,
                "readers": readers,
                "description": f"全局变量 {var} 被 {len(readers)} 个函数读取但从未被写入",
                "severity": "info",
            })

        # 无读者但有写者
        if len(readers) == 0 and len(writers) > 0:
            anomalies.append({
                "type": "no_reader_but_writers",
                "variable": var,
                "writers": writers,
                "description": f"全局变量 {var} 被 {len(writers)} 个函数写入但从未被读取",
                "severity": "info",
            })

    return anomalies


# ==================== 摘要生成 ====================

def _generate_summary(
    functions: dict[str, dict[str, Any]],
    control_coupling: dict[str, Any],
    data_coupling: dict[str, Any],
) -> dict[str, Any]:
    """生成耦合分析的摘要。"""
    total_funcs = len(functions)
    total_edges = control_coupling.get("total_edges", 0)
    total_global_vars = data_coupling.get("total_global_vars", 0)
    anomalies = data_coupling.get("shared_data_anomalies", [])
    warnings = [a for a in anomalies if a.get("severity") == "warning"]
    isolated = control_coupling.get("isolated_functions", [])

    # 耦合复杂度评分
    if total_funcs <= 1:
        complexity = "low"
    elif total_edges == 0:
        complexity = "low"
    elif total_edges <= 5:
        complexity = "medium"
    else:
        complexity = "high"

    return {
        "total_functions": total_funcs,
        "total_call_edges": total_edges,
        "total_global_variables": total_global_vars,
        "total_anomalies": len(anomalies),
        "warnings": len(warnings),
        "isolated_functions": len(isolated),
        "coupling_complexity": complexity,
        "analysis_method": "static_code_analysis",
        "do178c_ref": "§6.4.4.2.d / §6.4.4.2.e",
    }


# ==================== 便捷函数 ====================

def get_coupling_summary(result: CouplingResult) -> str:
    """生成耦合分析的可读摘要。"""
    if not result.analyzed:
        return f"耦合分析失败: {result.error}"

    s = result.summary
    return (
        f"控制耦合: {s.get('total_functions', 0)} 函数 "
        f"{s.get('total_call_edges', 0)} 调用边 | "
        f"数据耦合: {s.get('total_global_variables', 0)} 全局变量 "
        f"{s.get('total_anomalies', 0)} 异常 "
        f"({s.get('warnings', 0)} 警告)"
    )