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
  OBJ-10 独立性                  OBJ-20 数据耦合分析 **
  (* = V3.2 新增)
  (** = V0.5.0 P0 新增 — DO-178C §6.4.4.2.d/e)
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

    # ---- OBJ-20 数据耦合分析 (V0.5.0 P0 新增) ----
    results.append(_check_obj20(pipeline_result, def_map))

    # ---- OBJ-21 控制耦合分析 (V0.5.0 P0 新增) ----
    results.append(_check_obj21(pipeline_result, def_map))

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
    # V0.5.1: 优先检查 tool_evidence 中的 static_analysis 状态
    tool_evidence = pipeline_result.get("tool_evidence", {}) or {}
    static_evidence = tool_evidence.get("static_analysis", {}) or {}
    static_status = static_evidence.get("status", "")

    if static_status == "observed":
        status = STATUS_PASS
        engine = static_evidence.get("engine", "cppcheck")
        version = static_evidence.get("version", "")
        evidence = f"真实 {engine} {version} 已执行静态分析"
    elif static_status == "simulated":
        status = STATUS_PARTIAL
        evidence = "静态分析使用模拟引擎（非真实 Cppcheck）"
    else:
        cppcheck_result = pipeline_result.get("cppcheck_result", []) or []
        final_violations = pipeline_result.get("final_violations", []) or []
        if isinstance(cppcheck_result, list) and cppcheck_result:
            status = STATUS_PASS
            evidence = f"Cppcheck 已执行，扫描出 {len(cppcheck_result)} 条违规（修复后 {len(final_violations)} 条）"
        else:
            status = STATUS_PARTIAL
            evidence = "Cppcheck 扫描结果为空（可能未执行）"
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
    cov = pipeline_result.get("coverage_result", {}) or {}

    # V0.5.1: 多渠道检测故障注入 — sim fault_type、coverage fault_injected、evidence
    has_fault = False
    fault_evidence = ""

    if isinstance(sim, dict):
        fault_type = sim.get("fault_type")
        if fault_type:
            has_fault = True
            fault_evidence = f"已执行故障注入测试 fault_type={fault_type}"

    if not has_fault and cov.get("fault_injected"):
        has_fault = True
        fault_evidence = "已执行故障注入测试（通过覆盖率收集确认）"

    if has_fault:
        status = STATUS_PASS
        evidence = fault_evidence
    elif isinstance(sim, dict):
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

    # V0.5.1: 检查静态分析是否已执行（0 违规也是有效结果）
    tool_evidence = pipeline_result.get("tool_evidence", {}) or {}
    static_status = (tool_evidence.get("static_analysis", {}) or {}).get("status", "")

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
    elif static_status == "observed":
        # 静态分析已执行且确认 0 违规 — 最佳结果
        status = STATUS_PASS
        evidence = "静态分析已执行，确认 0 条违规（无问题即最佳报告）"
    else:
        status = STATUS_PARTIAL
        evidence = "未发现违规记录（可能无违规，或未报告）"
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj10(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-10 独立性。"""
    d = _build_def("OBJ-10", def_map)

    def _valid_human_review(review: dict[str, Any]) -> bool:
        comments = str(review.get("comments", ""))
        reviewer = str(review.get("reviewer") or review.get("reviewer_id") or "")
        return (
            review.get("approved") is True
            and reviewer not in {"", "system"}
            and review.get("status") not in {"skipped", "timeout"}
            and review.get("is_author", False) is False
            and "HIL 已禁用" not in comments
            and "自动通过" not in comments
            and "自动批准" not in comments
        )

    independent_reviews = pipeline_result.get("independent_reviews", []) or []
    valid_human_reviews = []
    valid_tool_reviews = []
    if isinstance(independent_reviews, list):
        valid_human_reviews = [
            r for r in independent_reviews
            if isinstance(r, dict)
            and r.get("reviewer_role") in {"human_reviewer", "ci_system"}
            and _valid_human_review(r)
        ]
        valid_tool_reviews = [
            r for r in independent_reviews
            if isinstance(r, dict)
            and r.get("reviewer_role") in {"automated_tool", "tool"}
            and r.get("approved") is True
            and r.get("is_author", True) is False
        ]

    hil_approvals = pipeline_result.get("hil_approvals", {}) or {}
    valid_hil = []
    if isinstance(hil_approvals, dict):
        valid_hil = [
            a for a in hil_approvals.values()
            if isinstance(a, dict) and _valid_human_review(a)
        ]

    if valid_human_reviews or valid_hil:
        status = STATUS_PASS
        evidence = (
            f"独立人工/CI 审查记录有效 "
            f"({len(valid_human_reviews)} review + {len(valid_hil)} HITL)"
        )
    elif valid_tool_reviews:
        status = STATUS_PARTIAL
        evidence = f"仅有独立工具审查 {len(valid_tool_reviews)} 条，缺少真实人工/CI 独立审查"
    else:
        status = STATUS_FAIL
        evidence = "缺少有效独立性证据：无真实人工/CI 审查，或审批由 system 自动通过"
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

    ccr = pipeline_result.get("contract_check_result")
    if isinstance(ccr, dict) and ccr.get("passed") is False:
        status = STATUS_PARTIAL
        evidence = "契约校验未通过，已检测到违约但缺少解决闭环"
        return ObjectiveResult(status=status, evidence=evidence, **d)

    if pipeline_result.get("breach_resolved"):
        method = pipeline_result.get("breach_resolution_method", "")
        if method and method not in {"no_breach", "verified_no_breach"}:
            status = STATUS_PASS
            evidence = f"契约违约已解决: {method}"
            return ObjectiveResult(status=status, evidence=evidence, **d)
        status = STATUS_PASS
        evidence = "契约校验与仿真均未发现违约"
        return ObjectiveResult(status=status, evidence=evidence, **d)

    if pipeline_result.get("breach_detected"):
        status = STATUS_PARTIAL
        cid = pipeline_result.get("breach_contract_id", "unknown")
        evidence = f"检测到契约违约但未完成解决闭环: {cid}"
        return ObjectiveResult(status=status, evidence=evidence, **d)

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
    method = cov.get("method", "static_analysis")
    stmt_pct = cov.get("statement_coverage", 0)
    if method != "gcov":
        status = STATUS_FAIL
        evidence = (
            f"语句覆盖率 {stmt_pct}%（目标 100%） · 收集方法: {_method_label(method)}；"
            "静态估算不构成 A-7.5 达标证据"
        )
    elif stmt_pct >= 100:
        status = STATUS_PASS
        evidence = f"语句覆盖率 {stmt_pct}%（100%） · 收集方法: {_method_label(method)}"
    elif stmt_pct >= 80:
        status = STATUS_PARTIAL
        evidence = f"语句覆盖率 {stmt_pct}%（目标 100%） · 收集方法: {_method_label(method)}"
    else:
        status = STATUS_FAIL
        evidence = f"语句覆盖率 {stmt_pct}%（目标 100%，差距 {100 - stmt_pct}%） · 收集方法: {_method_label(method)}"
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
    method = cov.get("method", "static_analysis")
    dec_pct = cov.get("decision_coverage", 0)
    if method != "gcov":
        status = STATUS_FAIL
        evidence = (
            f"判定覆盖率 {dec_pct}%（目标 100%） · 收集方法: {_method_label(method)}；"
            "静态估算不构成 A-7.7 达标证据"
        )
    elif dec_pct >= 100:
        status = STATUS_PASS
        evidence = f"判定覆盖率 {dec_pct}%（100%） · 收集方法: {_method_label(method)}"
    elif dec_pct >= 80:
        status = STATUS_PARTIAL
        evidence = f"判定覆盖率 {dec_pct}%（目标 100%） · 收集方法: {_method_label(method)}"
    else:
        status = STATUS_FAIL
        evidence = f"判定覆盖率 {dec_pct}%（目标 100%，差距 {100 - dec_pct}%） · 收集方法: {_method_label(method)}"
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
    method = cov.get("method", "static_analysis")
    mcdc_pct = cov.get("mcdc_coverage", 0)
    method_label = _method_label(method)
    if method != "gcov":
        status = STATUS_FAIL
        evidence = (
            f"MC/DC 覆盖率 {mcdc_pct}%（目标 100%） · 收集方法: {method_label}；"
            "静态估算不构成 A-7.8 达标证据"
        )
    elif mcdc_pct >= 100:
        status = STATUS_PASS
        evidence = f"MC/DC 覆盖率 {mcdc_pct}%（100%） · 收集方法: {method_label}"
    elif mcdc_pct >= 80:
        status = STATUS_PARTIAL
        evidence = f"MC/DC 覆盖率 {mcdc_pct}%（目标 100%） · 收集方法: {method_label}"
    else:
        status = STATUS_FAIL
        evidence = (
            f"MC/DC 覆盖率 {mcdc_pct}%（目标 100%，差距 {100 - mcdc_pct}%）"
            f" · 收集方法: {method_label}"
        )
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _method_label(method: str) -> str:
    """覆盖率收集方法的人类可读标签。"""
    if method == "gcov":
        return "真实 gcov/lcov (GCC 14.2+)"
    return "静态分析回退 (mcdc_calculator)"


def _check_obj16(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-16 HLR/LLR 追溯（适用于 DAL-A/B/C/D）。"""
    d = _build_def("OBJ-16", def_map)
    llr_result = pipeline_result.get("llr_result")
    if not isinstance(llr_result, dict):
        requirement = pipeline_result.get("requirement", {})
        if isinstance(requirement, dict):
            llr_result = requirement.get("llr_result")
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

    # 检查 1: pipeline_result 中的 independent_reviews 列表（证据收集注入）
    independent_reviews = pipeline_result.get("independent_reviews", [])
    if isinstance(independent_reviews, list) and independent_reviews:
        # 分离工具审查和人工审查
        tool_reviews = [r for r in independent_reviews if r.get("reviewer_role") in ("automated_tool", "tool")]
        human_reviews = [r for r in independent_reviews if r.get("reviewer_role") == "human_reviewer"]
        approved_tool_reviews = [r for r in tool_reviews if r.get("approved", False)]
        approved_human_reviews = [r for r in human_reviews if r.get("approved", False)]

        # 独立工具通过 + 独立人工通过 = PASS
        if approved_tool_reviews and approved_human_reviews:
            status = STATUS_PASS
            evidence = (
                f"独立验证完成: {len(approved_tool_reviews)} 个独立工具通过 + "
                f"{len(approved_human_reviews)} 个人工审查通过"
            )
            return ObjectiveResult(status=status, evidence=evidence, **d)
        # 仅工具通过
        elif approved_tool_reviews and not approved_human_reviews:
            status = STATUS_PARTIAL
            evidence = f"独立工具验证通过 ({len(approved_tool_reviews)} 个)，但缺少独立人工审查"
            return ObjectiveResult(status=status, evidence=evidence, **d)

    # 检查 2: HIL 审批记录和独立验证标记（原有逻辑）
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
        valid_prs = [
            pr for pr in pr_list
            if isinstance(pr, dict)
            and pr.get("branch") not in {"", None, "main"}
            and pr.get("status") in {"open", "merged", "closed"}
            and pr.get("pr_id")
        ]
        open_count = sum(1 for pr in valid_prs if pr.get("status") == "open")
        closed_count = sum(1 for pr in valid_prs if pr.get("status") in {"closed", "merged"})
        if valid_prs:
            status = STATUS_PASS
            evidence = f"PR 系统已启用: {len(valid_prs)} 条有效 PR（{open_count} open / {closed_count} closed-or-merged）"
        else:
            status = STATUS_FAIL
            evidence = f"PR 记录存在但无有效分支隔离（共 {len(pr_list)} 条）"
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


# ========== OBJ-20 ~ OBJ-21（V0.5.0 P0 新增：数据耦合 / 控制耦合）==========

def _check_obj20(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-20 数据耦合分析（DO-178C §6.4.4.2.d）。

    验证模块间的数据依赖关系：全局变量读写、参数传递、共享数据异常。
    """
    d = _build_def("OBJ-20", def_map)
    coupling_result = pipeline_result.get("coupling_result", {}) or {}

    if not coupling_result:
        return ObjectiveResult(
            status=STATUS_FAIL,
            evidence="未执行数据耦合分析（coupling_result 缺失）",
            **d,
        )

    data_coupling = coupling_result.get("data_coupling", {}) or {}
    global_access = data_coupling.get("global_variable_access", {})
    anomalies = data_coupling.get("shared_data_anomalies", [])
    warnings = [a for a in anomalies if a.get("severity") == "warning"]

    total_vars = len(global_access)
    if total_vars == 0:
        status = STATUS_PASS
        evidence = "无全局变量依赖，数据耦合简单（纯函数式设计）"
    elif len(warnings) == 0:
        status = STATUS_PASS
        evidence = (
            f"数据耦合分析完成: {total_vars} 个全局变量 "
            f"({len(anomalies)} 个 info 级异常，0 警告)"
        )
    elif len(warnings) <= 3:
        status = STATUS_PARTIAL
        evidence = (
            f"数据耦合分析完成: {total_vars} 个全局变量 "
            f"({len(warnings)} 个警告需关注)"
        )
    else:
        status = STATUS_FAIL
        evidence = (
            f"数据耦合分析: {total_vars} 个全局变量 "
            f"({len(warnings)} 个警告，存在数据竞争风险)"
        )
    return ObjectiveResult(status=status, evidence=evidence, **d)


def _check_obj21(
    pipeline_result: dict[str, Any], def_map: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-21 控制耦合分析（DO-178C §6.4.4.2.e）。

    验证模块间的控制流交互：函数调用图、调用顺序、入口点、孤立函数。
    """
    d = _build_def("OBJ-21", def_map)
    coupling_result = pipeline_result.get("coupling_result", {}) or {}

    if not coupling_result:
        return ObjectiveResult(
            status=STATUS_FAIL,
            evidence="未执行控制耦合分析（coupling_result 缺失）",
            **d,
        )

    control_coupling = coupling_result.get("control_coupling", {}) or {}
    total_funcs = control_coupling.get("total_functions", 0)
    total_edges = control_coupling.get("total_edges", 0)
    isolated = control_coupling.get("isolated_functions", [])
    entry_points = control_coupling.get("entry_points", [])

    if total_funcs == 0:
        status = STATUS_FAIL
        evidence = "未检测到函数定义"
    elif total_funcs == 1:
        status = STATUS_PASS
        evidence = f"单函数模块，控制耦合简单（1 个函数，{total_edges} 条调用边）"
    elif len(isolated) == 0 and len(entry_points) > 0:
        status = STATUS_PASS
        evidence = (
            f"控制耦合分析完成: {total_funcs} 个函数，{total_edges} 条调用边 "
            f"入口点={len(entry_points)}，孤立函数=0"
        )
    elif len(isolated) <= 2:
        status = STATUS_PARTIAL
        evidence = (
            f"控制耦合分析完成: {total_funcs} 个函数，{total_edges} 条调用边 "
            f"孤立函数={len(isolated)}（{', '.join(isolated)}）"
        )
    else:
        status = STATUS_FAIL
        evidence = (
            f"控制耦合分析: {total_funcs} 个函数，{total_edges} 条调用边 "
            f"孤立函数={len(isolated)}（存在控制流断裂风险）"
        )
    return ObjectiveResult(status=status, evidence=evidence, **d)
