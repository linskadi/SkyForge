"""DO-178C DAL 自适应目标符合性检查器。

依据 pipeline_result 和 DAL 等级自动评估 DO-178C 目标的满足状态。
支持 DAL-A~E 五个等级，根据不同等级返回不同目标清单。

V3.2 重构:
  - 从硬编码 Level C 改为 DAL 自适应（19 项目标）
  - 新增 OBJ-13~OBJ-19（语句/判定/MC/DC 覆盖、HLR/LLR 追溯、独立验证、正式 PR、工具鉴定）
  - 新增 dal 参数；无参数默认 DAL-C（保持向后兼容）
  - 新增 STATUS_NA = "不适用" 状态（目标不适用于当前 DAL）

覆盖目标:
  OBJ-1  需求可追溯性            OBJ-11 编译验证
  OBJ-2  契约式设计验证          OBJ-12 契约违约处理
  OBJ-3  源代码合规性            OBJ-13 语句覆盖率 *
  OBJ-4  静态分析                OBJ-14 判定覆盖率 *
  OBJ-5  仿真测试覆盖            OBJ-15 MC/DC 覆盖率 *
  OBJ-6  故障注入测试            OBJ-16 HLR/LLR 追溯 *
  OBJ-7  代码审查                OBJ-17 独立验证 *
  OBJ-8  配置管理                OBJ-18 正式 PR 系统 *
  OBJ-9  问题报告                OBJ-19 工具鉴定 *
  OBJ-10 独立性
  (* = V3.2 新增)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from skyforge_engine.schemas.dal_objectives import (
    DAL,
    DAL_OBJECTIVE_IDS,
    get_objectives_for_dal,
)
from skyforge_engine.utils.log_util import logger

# 目标状态常量
STATUS_PASS = "满足"
STATUS_PARTIAL = "部分满足"
STATUS_FAIL = "未满足"
STATUS_NA = "不适用"  # 目标不适用于当前 DAL 等级


@dataclass
class ObjectiveResult:
    """DO-178C 单项目标符合性检查结果。

    Attributes:
        obj_id: 目标 ID（如 OBJ-1）。
        name: 目标名称。
        description: 目标描述。
        status: 符合状态，"满足" / "部分满足" / "未满足" / "不适用"。
        evidence: 证据说明（pipeline_result 中的具体来源）。
        do178_table: DO-178C 表引用。
    """

    obj_id: str
    name: str
    description: str
    status: str
    evidence: str = ""
    do178_table: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return asdict(self)


def check_objectives(
    pipeline_result: dict[str, Any],
    dal: DAL | str | None = None,
) -> list[ObjectiveResult]:
    """对 pipeline_result 执行 DO-178C DAL 自适应目标符合性检查。

    Args:
        pipeline_result: 全流程结果字典。
        dal: 软件安全等级。支持 DAL 枚举 / "DAL-A" 字符串 / None（默认 DAL-C）。
             若 pipeline_result 中 requirement.safety_level 存在且 dal 参数未指定，
             则从 pipeline_result 自动推断。

    Returns:
        list[ObjectiveResult]：当前 DAL 等级适用的所有目标检查结果。
    """
    # 延迟导入，避免循环依赖
    from .traceability_matrix import build_matrix

    # ---- 推断 DAL 等级 ----
    resolved_dal = _resolve_dal(dal, pipeline_result)
    logger.info(
        f"DO178Objectives:检查 DAL={resolved_dal.value} "
        f"（目标 {resolved_dal.objective_count} 项）"
    )

    # 获取当前 DAL 适用的目标 ID 集合（快速查找）
    applicable_ids = set(DAL_OBJECTIVE_IDS.get(resolved_dal, []))

    # 获取目标定义列表（保持顺序）
    all_defs = get_objectives_for_dal(resolved_dal)
    def_map = {d.obj_id: d for d in all_defs}

    results: list[ObjectiveResult] = []

    # ---- OBJ-1 需求可追溯性 ----
    results.append(_check_obj1(pipeline_result, def_map))

    # ---- OBJ-2 契约式设计验证 ----
    results.append(_check_obj2(pipeline_result, def_map))

    # ---- OBJ-3 源代码合规性 ----
    results.append(_check_obj3(pipeline_result, def_map))

    # ---- OBJ-4 静态分析 ----
    results.append(_check_obj4(pipeline_result, def_map))

    # ---- OBJ-5 仿真测试覆盖 ----
    results.append(_check_obj5(pipeline_result, def_map))

    # ---- OBJ-6 故障注入测试 ----
    results.append(_check_obj6(pipeline_result, def_map))

    # ---- OBJ-7 代码审查 ----
    results.append(_check_obj7(pipeline_result, def_map))

    # ---- OBJ-8 配置管理 ----
    results.append(_check_obj8(pipeline_result, def_map))

    # ---- OBJ-9 问题报告 ----
    results.append(_check_obj9(pipeline_result, def_map))

    # ---- OBJ-10 独立性 ----
    results.append(_check_obj10(pipeline_result, def_map))

    # ---- OBJ-11 编译验证 ----
    results.append(_check_obj11(pipeline_result, def_map))

    # ---- OBJ-12 契约违约处理 ----
    results.append(_check_obj12(pipeline_result, def_map))

    # ---- OBJ-13 语句覆盖率 (V3.2 新增) ----
    results.append(_check_obj13(pipeline_result, def_map, resolved_dal))

    # ---- OBJ-14 判定覆盖率 (V3.2 新增) ----
    results.append(_check_obj14(pipeline_result, def_map, resolved_dal))

    # ---- OBJ-15 MC/DC 覆盖率 (V3.2 新增) ----
    results.append(_check_obj15(pipeline_result, def_map, resolved_dal))

    # ---- OBJ-16 HLR/LLR 追溯 (V3.2 新增) ----
    results.append(_check_obj16(pipeline_result, def_map))

    # ---- OBJ-17 独立验证 (V3.2 新增) ----
    results.append(_check_obj17(pipeline_result, def_map, resolved_dal))

    # ---- OBJ-18 正式 PR 系统 (V3.2 新增) ----
    results.append(_check_obj18(pipeline_result, def_map))

    # ---- OBJ-19 工具鉴定 (V3.2 新增) ----
    results.append(_check_obj19(pipeline_result, def_map))

    # 按 applicable_ids 过滤：不适用当前 DAL 的目标设为 STATUS_NA
    final_results: list[ObjectiveResult] = []
    for r in results:
        if r.obj_id not in applicable_ids:
            r.status = STATUS_NA
            r.evidence = f"目标 {r.obj_id} 不适用于 {resolved_dal.value} 等级"
        final_results.append(r)

    pass_count = sum(1 for r in final_results if r.status == STATUS_PASS)
    partial_count = sum(1 for r in final_results if r.status == STATUS_PARTIAL)
    fail_count = sum(1 for r in final_results if r.status == STATUS_FAIL)
    na_count = sum(1 for r in final_results if r.status == STATUS_NA)
    logger.info(
        f"DO178Objectives:检查完成: {len(final_results)} 项 "
        f"满足 {pass_count} "
        f"部分 {partial_count} "
        f"未满足 {fail_count} "
        f"不适用 {na_count} "
        f"DAL={resolved_dal.value}"
    )
    return final_results


def _resolve_dal(
    dal: DAL | str | None,
    pipeline_result: dict[str, Any],
) -> DAL:
    """推断 DAL 等级：优先参数 > pipeline_result > 默认 DAL-C。"""
    if dal is not None:
        if isinstance(dal, DAL):
            return dal
        return DAL.from_string(str(dal))

    requirement = pipeline_result.get("requirement", {})
    if isinstance(requirement, dict):
        safety_level = requirement.get("safety_level", "")
        if safety_level:
            return DAL.from_string(str(safety_level))

    return DAL.C


def _build_def(obj_id: str, def_map: dict[str, Any]) -> dict[str, Any]:
    """从目标定义字典构建 ObjectiveResult 的基础字段。"""
    d = def_map.get(obj_id)
    if d is None:
        return {
            "obj_id": obj_id,
            "name": obj_id,
            "description": "",
            "do178_table": "",
        }
    return {
        "obj_id": d.obj_id,
        "name": d.name,
        "description": d.description,
        "do178_table": d.do178_table,
    }


# ========== OBJ-1 ~ OBJ-12（原有 12 项 + DAL 自适应）==========

def _check_obj1(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-1 需求可追溯性。"""
    d = _build_def("OBJ-1", def_map)
    try:
        from .traceability_matrix import build_matrix
        matrix = build_matrix(pipeline_result)
        complete_count = sum(
            1 for e in matrix
            if e.req_id and e.contract_id and e.code_line and e.test_id
        )
        total = max(len(matrix), 1)
        ratio = complete_count / total
        pct = f"{ratio * 100:.0f}%"
        ev = f"追溯矩阵 {len(matrix)} 行，完整 {complete_count} 行（{pct}）"
        if ratio >= 0.9 and matrix:
            status = STATUS_PASS
        elif ratio >= 0.5:
            status = STATUS_PARTIAL
        else:
            status = STATUS_FAIL
    except Exception as e:
        status = STATUS_FAIL
        ev = f"追溯矩阵构建失败: {e}"
    return ObjectiveResult(status=status, evidence=ev, **d)


def _check_obj2(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-2 契约式设计验证。"""
    d = _build_def("OBJ-2", def_map)
    ccr = pipeline_result.get("contract_check_result")
    if isinstance(ccr, dict):
        passed = bool(ccr.get("passed", False))
        pre = ccr.get("preconditions", []) or []
        post = ccr.get("postconditions", []) or []
        inv = ccr.get("invariants", []) or []
        fh = ccr.get("fault_handling", []) or []
        total_items = len(pre) + len(post) + len(inv) + len(fh)
        passed_items = sum(
            1 for sec in (pre, post, inv, fh)
            for it in sec
            if isinstance(it, dict) and it.get("passed")
        )
        if passed and total_items > 0:
            status = STATUS_PASS
        elif passed_items > 0:
            status = STATUS_PARTIAL
        else:
            status = STATUS_FAIL
        evidence = (
            f"契约校验整体 passed={passed}，"
            f"通过 {passed_items}/{total_items} 项"
            f"（pre={len(pre)} post={len(post)} inv={len(inv)} fh={len(fh)}）"
        )
    else:
        status = STATUS_FAIL
        evidence = "未执行契约校验（contract_check_result 缺失）"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj3(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-3 源代码合规性。"""
    d = _build_def("OBJ-3", def_map)
    final_violations = pipeline_result.get("final_violations", []) or []
    if isinstance(final_violations, list):
        v_count = len(final_violations)
        if v_count == 0:
            status = STATUS_PASS
            evidence = "无 MISRA-C 残留违规"
        elif v_count <= 3:
            status = STATUS_PARTIAL
            evidence = f"MISRA-C 残留违规 {v_count} 条"
        else:
            status = STATUS_FAIL
            evidence = f"MISRA-C 残留违规 {v_count} 条（>3）"
    else:
        status = STATUS_FAIL
        evidence = "final_violations 字段缺失或非列表"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj4(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-4 静态分析。"""
    d = _build_def("OBJ-4", def_map)
    cppcheck_result = pipeline_result.get("cppcheck_result", []) or []
    final_violations = pipeline_result.get("final_violations", []) or []
    if isinstance(cppcheck_result, list) and cppcheck_result:
        status = STATUS_PASS
        n_scan = len(cppcheck_result)
        n_fixed = len(final_violations)
        evidence = (
            f"Cppcheck 已执行，扫描出 {n_scan} 条违规"
            f"（修复后 {n_fixed} 条）"
        )
    elif isinstance(cppcheck_result, list) and not cppcheck_result:
        status = STATUS_PARTIAL
        evidence = "Cppcheck 扫描结果为空（可能未执行或无违规）"
    else:
        status = STATUS_FAIL
        evidence = "cppcheck_result 字段缺失"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj5(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-5 仿真测试覆盖。"""
    d = _build_def("OBJ-5", def_map)
    sim = pipeline_result.get("simulation_result")
    if isinstance(sim, dict):
        steps = int(sim.get("total_steps", 0))
        if steps >= 100:
            status = STATUS_PASS
            evidence = f"数字孪生仿真步数 {steps}（>=100）"
        elif steps > 0:
            status = STATUS_PARTIAL
            evidence = f"数字孪生仿真步数 {steps}（<100）"
        else:
            status = STATUS_FAIL
            evidence = "数字孪生仿真步数为 0"
    else:
        status = STATUS_FAIL
        evidence = "未执行数字孪生仿真（simulation_result 缺失）"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj6(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-6 故障注入测试。"""
    d = _build_def("OBJ-6", def_map)
    sim = pipeline_result.get("simulation_result")
    if isinstance(sim, dict):
        fault_type = sim.get("fault_type")
        if fault_type:
            status = STATUS_PASS
            fault_params = sim.get("fault_params", {})
            evidence = (
                f"已执行故障注入测试 fault_type={fault_type} params={fault_params}"
            )
        else:
            status = STATUS_PARTIAL
            evidence = "数字孪生仿真未注入故障（仅正常运行）"
    else:
        status = STATUS_FAIL
        evidence = "未执行数字孪生仿真"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj7(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-7 代码审查。"""
    d = _build_def("OBJ-7", def_map)
    final_violations = pipeline_result.get("final_violations", []) or []
    repair_history = pipeline_result.get("repair_history", []) or []
    if isinstance(repair_history, list) and repair_history:
        total_actions = 0
        for entry in repair_history:
            if isinstance(entry, dict):
                actions = entry.get("actions", [])
                if isinstance(actions, list):
                    total_actions += len(actions)
                elif isinstance(actions, int):
                    total_actions += actions
        if total_actions > 0:
            status = STATUS_PASS
            evidence = f"修复历史 {len(repair_history)} 轮，共 {total_actions} 处修复"
        else:
            status = STATUS_PARTIAL
            evidence = f"修复历史 {len(repair_history)} 轮，但无 actions 记录"
    elif isinstance(repair_history, list) and not repair_history:
        if not final_violations:
            status = STATUS_PASS
            evidence = "无违规，无需修复（修复历史为空且 final_violations=0）"
        else:
            status = STATUS_PARTIAL
            evidence = "修复历史为空，但仍有残留违规"
    else:
        status = STATUS_FAIL
        evidence = "repair_history 字段缺失"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj8(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-8 配置管理。"""
    d = _build_def("OBJ-8", def_map)
    contract_yaml: str = pipeline_result.get("contract", "") or ""
    has_version = "version:" in contract_yaml.lower()
    if has_version:
        status = STATUS_PASS
        evidence = "契约 YAML 含 version 字段"
    else:
        status = STATUS_PARTIAL
        evidence = "契约 YAML 未明确 version 字段"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj9(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-9 问题报告。"""
    d = _build_def("OBJ-9", def_map)
    final_violations = pipeline_result.get("final_violations", []) or []
    cppcheck_result = pipeline_result.get("cppcheck_result", []) or []
    repair_history = pipeline_result.get("repair_history", []) or []
    violations_reported = (
        len(final_violations) if isinstance(final_violations, list) else 0
    ) + (
        len([
            v for v in (cppcheck_result or [])
            if isinstance(v, dict) or hasattr(v, "rule_id")
        ])
    )
    repair_recorded = len(repair_history) if isinstance(repair_history, list) else 0
    if violations_reported > 0 or repair_recorded > 0:
        status = STATUS_PASS
        evidence = f"已记录 {violations_reported} 条违规 + {repair_recorded} 轮修复历史"
    else:
        status = STATUS_PARTIAL
        evidence = "未发现违规记录（可能无违规，或未报告）"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj10(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-10 独立性。"""
    d = _build_def("OBJ-10", def_map)
    ccr = pipeline_result.get("contract_check_result")
    sim = pipeline_result.get("simulation_result")
    has_ai_gen = (
        bool(pipeline_result.get("requirement"))
        and bool(pipeline_result.get("contract"))
        and bool(pipeline_result.get("final_code") or pipeline_result.get("code"))
    )
    has_auto_verify = isinstance(ccr, dict) or isinstance(sim, dict)
    if has_ai_gen and has_auto_verify:
        status = STATUS_PASS
        evidence = "AI 生成 3 阶段产物完整 + 自动化验证（契约校验/仿真）已执行"
    elif has_ai_gen or has_auto_verify:
        status = STATUS_PARTIAL
        evidence = f"AI 生成完整={has_ai_gen}，自动化验证={has_auto_verify}"
    else:
        status = STATUS_FAIL
        evidence = "AI 生成 + 自动化验证均缺失"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj11(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-11 编译验证。"""
    d = _build_def("OBJ-11", def_map)
    sim = pipeline_result.get("simulation_result")
    if isinstance(sim, dict):
        compilation = sim.get("compilation", {}) or {}
        compile_success = bool(compilation.get("success", False))
        used_mock = bool(compilation.get("used_mock", False))
        if compile_success and not used_mock:
            status = STATUS_PASS
            evidence = "GCC 真实编译通过"
        elif compile_success and used_mock:
            status = STATUS_PARTIAL
            evidence = "GCC 不可用，使用 Python 模拟（mock 模式）"
        else:
            status = STATUS_FAIL
            evidence = f"编译失败: {compilation.get('errors', '')[:200]}"
    else:
        status = STATUS_FAIL
        evidence = "未执行仿真，无法验证编译"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj12(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-12 契约违约处理。"""
    d = _build_def("OBJ-12", def_map)
    sim = pipeline_result.get("simulation_result")
    if isinstance(sim, dict):
        cv = sim.get("contract_violation")
        sim_passed = bool(sim.get("passed", False))
        if sim_passed and cv is None:
            status = STATUS_PASS
            evidence = "仿真通过且无契约违约"
        elif cv is not None:
            status = STATUS_PARTIAL
            cid = cv.get("contract_id", "")
            step = cv.get("failed_step", "?")
            evidence = f"检测到契约违约: {cid} step={step}"
        else:
            status = STATUS_FAIL
            evidence = "仿真失败但未检测到契约违约"
    else:
        status = STATUS_FAIL
        evidence = "未执行仿真"
    return ObjectiveResult(status=status, evidence=evidence, **d)


# ========== OBJ-13 ~ OBJ-19（V3.2 新增 7 项目标）==========

def _check_obj13(
    pipeline_result: dict[str, Any],
    def_map: dict[str, Any],
    dal: DAL,
) -> ObjectiveResult:
    """OBJ-13 语句覆盖率（适用于 DAL-A/B/C/D）。"""
    d = _build_def("OBJ-13", def_map)
    if not dal.requires_statement_coverage:
        return ObjectiveResult(status=STATUS_NA, evidence="", **d)

    cov = pipeline_result.get("coverage_result", {}) or {}
    stmt_pct = cov.get("statement_coverage", 0)
    if stmt_pct >= 100:
        status = STATUS_PASS
        evidence = f"语句覆盖率 {stmt_pct}%（100%）"
    elif stmt_pct >= 80:
        status = STATUS_PARTIAL
        evidence = f"语句覆盖率 {stmt_pct}%（目标 100%）"
    else:
        status = STATUS_FAIL
        evidence = f"语句覆盖率 {stmt_pct}%（目标 100%，差距 {100 - stmt_pct}%）"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj14(
    pipeline_result: dict[str, Any],
    def_map: dict[str, Any],
    dal: DAL,
) -> ObjectiveResult:
    """OBJ-14 判定覆盖率（适用于 DAL-A/B）。"""
    d = _build_def("OBJ-14", def_map)
    if not dal.requires_decision_coverage:
        return ObjectiveResult(status=STATUS_NA, evidence="", **d)

    cov = pipeline_result.get("coverage_result", {}) or {}
    dec_pct = cov.get("decision_coverage", 0)
    if dec_pct >= 100:
        status = STATUS_PASS
        evidence = f"判定覆盖率 {dec_pct}%（100%）"
    elif dec_pct >= 80:
        status = STATUS_PARTIAL
        evidence = f"判定覆盖率 {dec_pct}%（目标 100%）"
    else:
        status = STATUS_FAIL
        evidence = f"判定覆盖率 {dec_pct}%（目标 100%，差距 {100 - dec_pct}%）"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj15(
    pipeline_result: dict[str, Any],
    def_map: dict[str, Any],
    dal: DAL,
) -> ObjectiveResult:
    """OBJ-15 MC/DC 覆盖率（仅适用于 DAL-A）。"""
    d = _build_def("OBJ-15", def_map)
    if not dal.requires_mcdc:
        return ObjectiveResult(status=STATUS_NA, evidence="", **d)

    cov = pipeline_result.get("coverage_result", {}) or {}
    mcdc_pct = cov.get("mcdc_coverage", 0)
    if mcdc_pct >= 100:
        status = STATUS_PASS
        evidence = f"MC/DC 覆盖率 {mcdc_pct}%（100%）"
    elif mcdc_pct >= 80:
        status = STATUS_PARTIAL
        evidence = f"MC/DC 覆盖率 {mcdc_pct}%（目标 100%）"
    else:
        status = STATUS_FAIL
        evidence = (
            f"MC/DC 覆盖率 {mcdc_pct}%（目标 100%，差距 {100 - mcdc_pct}%）"
            " — MC/DC 分析为 Phase 3 MVP 版本"
        )
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj16(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-16 HLR/LLR 追溯（适用于 DAL-A/B/C/D）。"""
    d = _build_def("OBJ-16", def_map)
    llr_result = pipeline_result.get("llr_result")
    if isinstance(llr_result, dict):
        hlr_count = llr_result.get("hlr_count", 0)
        llr_count = llr_result.get("llr_count", 0)
        if llr_count > 0 and hlr_count > 0:
            status = STATUS_PASS
            evidence = f"HLR {hlr_count} 条 → LLR {llr_count} 条，追溯链完整"
        else:
            status = STATUS_PARTIAL
            evidence = f"HLR {hlr_count} 条 → LLR {llr_count} 条（追溯不完整）"
    else:
        # 检查旧格式：requirement 直接存在
        requirement = pipeline_result.get("requirement")
        if isinstance(requirement, dict) and requirement:
            status = STATUS_PARTIAL
            evidence = "仅有扁平需求（HLR），未生成 LLR（低层需求）"
        else:
            status = STATUS_FAIL
            evidence = "需求数据缺失"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj17(
    pipeline_result: dict[str, Any],
    def_map: dict[str, Any],
    dal: DAL,
) -> ObjectiveResult:
    """OBJ-17 独立验证（适用于 DAL-A/B）。"""
    d = _build_def("OBJ-17", def_map)
    if not dal.requires_independent_verification:
        return ObjectiveResult(status=STATUS_NA, evidence="", **d)

    # 检查 HIL 审批记录和独立验证标记
    hil_history = pipeline_result.get("hil_history", []) or []
    ccr = pipeline_result.get("contract_check_result")
    has_hil = len(hil_history) > 0 if isinstance(hil_history, list) else False
    has_independent = isinstance(ccr, dict) and ccr.get("independent_verification", False)

    if has_hil and has_independent:
        status = STATUS_PASS
        evidence = "HIL 人工审批 + 独立验证标记均存在"
    elif has_hil or has_independent:
        status = STATUS_PARTIAL
        evidence = f"HIL 审批={'有' if has_hil else '无'}，独立验证标记={'有' if has_independent else '无'}"
    else:
        status = STATUS_FAIL
        evidence = "缺少独立验证：无 HIL 审批记录且无独立验证标记"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj18(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-18 正式 PR 系统（适用于 DAL-A/B/C/D）。"""
    d = _build_def("OBJ-18", def_map)
    pr_list = pipeline_result.get("problem_reports", []) or []
    if isinstance(pr_list, list) and pr_list:
        open_count = sum(1 for pr in pr_list if isinstance(pr, dict) and pr.get("status") == "open")
        closed_count = sum(1 for pr in pr_list if isinstance(pr, dict) and pr.get("status") == "closed")
        status = STATUS_PASS
        evidence = f"PR 系统已启用: {len(pr_list)} 条报告（{open_count} open / {closed_count} closed）"
    else:
        # 检查是否有旧格式的违规记录（向后兼容）
        violations = pipeline_result.get("final_violations", []) or []
        if violations:
            status = STATUS_PARTIAL
            evidence = f"未启用正式 PR 系统，但有 {len(violations)} 条违规记录（旧格式）"
        else:
            status = STATUS_PARTIAL
            evidence = "PR 系统未启用，且无违规记录（可能无违规）"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj19(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-19 工具鉴定（适用于 DAL-A/B/C/D）。"""
    d = _build_def("OBJ-19", def_map)
    tqp = pipeline_result.get("tool_qualification", {}) or {}
    has_tqp = bool(tqp.get("tqp_exists", False))
    has_tor = bool(tqp.get("tor_exists", False))
    chain_validated = bool(tqp.get("chain_validated", False))

    if has_tqp and has_tor and chain_validated:
        status = STATUS_PASS
        evidence = "TQP/TOR 文档完整 + 工具链验证通过"
    elif has_tqp or has_tor:
        status = STATUS_PARTIAL
        evidence = (
            f"TQP={'有' if has_tqp else '无'}，"
            f"TOR={'有' if has_tor else '无'}，"
            f"工具链验证={'通过' if chain_validated else '未完成'}"
        )
    else:
        status = STATUS_FAIL
        evidence = "工具鉴定文档（TQP/TOR）缺失"
    return ObjectiveResult(status=status, evidence=evidence, **d)
