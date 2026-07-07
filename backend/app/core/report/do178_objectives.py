"""DO-178C Level C 关键目标符合性检查器：依据 pipeline_result 自动评估 10+ 项
DO-178C 目标的满足状态（"满足" / "部分满足" / "未满足"）。

覆盖目标（参考 DO-178C Table A-2 ~ A-7 Level C 关键项）：
  OBJ-1  需求可追溯性（追溯矩阵完整性）
  OBJ-2  契约式设计验证（契约校验结果）
  OBJ-3  源代码合规性（MISRA-C 扫描结果）
  OBJ-4  静态分析（Cppcheck 是否执行）
  OBJ-5  仿真测试覆盖（仿真步数 >= 100）
  OBJ-6  故障注入测试（是否执行故障注入）
  OBJ-7  代码审查（修复历史是否完整）
  OBJ-8  配置管理（版本号是否存在）
  OBJ-9  问题报告（违规是否被记录）
  OBJ-10 独立性（AI 生成 + 自动化验证）
  OBJ-11 编译验证（GCC 编译是否通过）
  OBJ-12 契约违约处理（断言失败被检测）
"""

from dataclasses import asdict, dataclass
from typing import Any

from app.utils.log_util import logger

# 目标状态常量
STATUS_PASS = "满足"
STATUS_PARTIAL = "部分满足"
STATUS_FAIL = "未满足"


@dataclass
class ObjectiveResult:
    """DO-178C 单项目标符合性检查结果。

    Attributes:
        obj_id: 目标 ID（如 OBJ-1）。
        name: 目标名称。
        description: 目标描述。
        status: 符合状态，"满足" / "部分满足" / "未满足"。
        evidence: 证据说明（pipeline_result 中的具体来源）。
    """

    obj_id: str
    name: str
    description: str
    status: str
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return asdict(self)


def check_objectives(pipeline_result: dict[str, Any]) -> list[ObjectiveResult]:
    """对 pipeline_result 执行 DO-178C Level C 12 项关键目标符合性检查。

    Args:
        pipeline_result: 全流程结果字典。

    Returns:
        list[ObjectiveResult]：每项目标的检查结果。
    """
    # 延迟导入，避免循环依赖
    from .traceability_matrix import build_matrix

    results: list[ObjectiveResult] = []

    # ---- OBJ-1 需求可追溯性 ----
    try:
        matrix = build_matrix(pipeline_result)
        complete_count = sum(
            1
            for e in matrix
            if e.req_id and e.contract_id and e.code_line and e.test_id
        )
        total = max(len(matrix), 1)
        ratio = complete_count / total
        if ratio >= 0.9 and matrix:
            status = STATUS_PASS
            evidence = f"追溯矩阵 {len(matrix)} 行，完整 {complete_count} 行（{ratio * 100:.0f}%）"
        elif ratio >= 0.5:
            status = STATUS_PARTIAL
            evidence = f"追溯矩阵 {len(matrix)} 行，完整 {complete_count} 行（{ratio * 100:.0f}%）"
        else:
            status = STATUS_FAIL
            evidence = f"追溯矩阵 {len(matrix)} 行，完整 {complete_count} 行（{ratio * 100:.0f}%）"
    except Exception as e:
        status = STATUS_FAIL
        evidence = f"追溯矩阵构建失败: {e}"
    results.append(
        ObjectiveResult(
            obj_id="OBJ-1",
            name="需求可追溯性",
            description="高级需求到低级需求、代码、测试的可追溯链完整（DO-178C Table A-7.6）",
            status=status,
            evidence=evidence,
        )
    )

    # ---- OBJ-2 契约式设计验证 ----
    ccr = pipeline_result.get("contract_check_result")
    if isinstance(ccr, dict):
        passed = bool(ccr.get("passed", False))
        pre = ccr.get("preconditions", []) or []
        post = ccr.get("postconditions", []) or []
        inv = ccr.get("invariants", []) or []
        fh = ccr.get("fault_handling", []) or []
        total_items = len(pre) + len(post) + len(inv) + len(fh)
        passed_items = sum(
            1
            for sec in (pre, post, inv, fh)
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
    results.append(
        ObjectiveResult(
            obj_id="OBJ-2",
            name="契约式设计验证",
            description="前置/后置/不变式/故障处理契约均被验证（DO-178C Table A-3.1）",
            status=status,
            evidence=evidence,
        )
    )

    # ---- OBJ-3 源代码合规性 ----
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
    results.append(
        ObjectiveResult(
            obj_id="OBJ-3",
            name="源代码合规性",
            description="MISRA-C:2012 强制规则无残留违规（DO-178C Table A-5.1）",
            status=status,
            evidence=evidence,
        )
    )

    # ---- OBJ-4 静态分析 ----
    cppcheck_result = pipeline_result.get("cppcheck_result", []) or []
    if isinstance(cppcheck_result, list) and cppcheck_result:
        # cppcheck_result 是 list[Violation] 或 list[dict]，存在说明扫描已执行
        status = STATUS_PASS
        evidence = f"Cppcheck 已执行，扫描出 {len(cppcheck_result)} 条违规（修复后 {len(final_violations)} 条）"
    elif isinstance(cppcheck_result, list) and not cppcheck_result:
        # 空列表：可能未执行，也可能执行后无违规
        status = STATUS_PARTIAL
        evidence = "Cppcheck 扫描结果为空（可能未执行或无违规）"
    else:
        status = STATUS_FAIL
        evidence = "cppcheck_result 字段缺失"
    results.append(
        ObjectiveResult(
            obj_id="OBJ-4",
            name="静态分析",
            description="Cppcheck --addon=misra 已执行（DO-178C Table A-5.2）",
            status=status,
            evidence=evidence,
        )
    )

    # ---- OBJ-5 仿真测试覆盖 ----
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
    results.append(
        ObjectiveResult(
            obj_id="OBJ-5",
            name="仿真测试覆盖",
            description="数字孪生仿真步数 >= 100（DO-178C Table A-6.2）",
            status=status,
            evidence=evidence,
        )
    )

    # ---- OBJ-6 故障注入测试 ----
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
    results.append(
        ObjectiveResult(
            obj_id="OBJ-6",
            name="故障注入测试",
            description="数字孪生仿真含故障注入场景（DO-178C Table A-6.6）",
            status=status,
            evidence=evidence,
        )
    )

    # ---- OBJ-7 代码审查 ----
    repair_history = pipeline_result.get("repair_history", []) or []
    if isinstance(repair_history, list) and repair_history:
        total_actions = sum(
            len(entry.get("actions", [])) if isinstance(entry, dict) else 0
            for entry in repair_history
        )
        if total_actions > 0:
            status = STATUS_PASS
            evidence = f"修复历史 {len(repair_history)} 轮，共 {total_actions} 处修复"
        else:
            status = STATUS_PARTIAL
            evidence = f"修复历史 {len(repair_history)} 轮，但无 actions 记录"
    elif isinstance(repair_history, list) and not repair_history:
        # 空历史 + 无残留违规 = 干净代码，仍视为满足
        if not final_violations:
            status = STATUS_PASS
            evidence = "无违规，无需修复（修复历史为空且 final_violations=0）"
        else:
            status = STATUS_PARTIAL
            evidence = "修复历史为空，但仍有残留违规"
    else:
        status = STATUS_FAIL
        evidence = "repair_history 字段缺失"
    results.append(
        ObjectiveResult(
            obj_id="OBJ-7",
            name="代码审查",
            description="代码修复历史完整，每处违规均有修复动作（DO-178C Table A-7.1）",
            status=status,
            evidence=evidence,
        )
    )

    # ---- OBJ-8 配置管理 ----
    contract_yaml: str = pipeline_result.get("contract", "") or ""
    has_version = "version:" in contract_yaml.lower()
    if has_version:
        status = STATUS_PASS
        evidence = "契约 YAML 含 version 字段"
    else:
        status = STATUS_PARTIAL
        evidence = "契约 YAML 未明确 version 字段"
    results.append(
        ObjectiveResult(
            obj_id="OBJ-8",
            name="配置管理",
            description="软件版本号可追溯（DO-178C Table A-8.1）",
            status=status,
            evidence=evidence,
        )
    )

    # ---- OBJ-9 问题报告 ----
    violations_reported = (
        len(final_violations) if isinstance(final_violations, list) else 0
    ) + (
        len(
            [
                v
                for v in (cppcheck_result or [])
                if isinstance(v, dict) or hasattr(v, "rule_id")
            ]
        )
    )
    repair_recorded = len(repair_history) if isinstance(repair_history, list) else 0
    if violations_reported > 0 or repair_recorded > 0:
        status = STATUS_PASS
        evidence = f"已记录 {violations_reported} 条违规 + {repair_recorded} 轮修复历史"
    else:
        status = STATUS_PARTIAL
        evidence = "未发现违规记录（可能无违规，或未报告）"
    results.append(
        ObjectiveResult(
            obj_id="OBJ-9",
            name="问题报告",
            description="违规与修复历史均被记录可查（DO-178C Table A-8.3）",
            status=status,
            evidence=evidence,
        )
    )

    # ---- OBJ-10 独立性 ----
    # AI 生成（需求解析/契约/代码 Agent）+ 自动化验证（Cppcheck/契约校验/数字孪生）
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
    results.append(
        ObjectiveResult(
            obj_id="OBJ-10",
            name="独立性",
            description="AI 生成 + 自动化验证双重独立（DO-178C Table A-9.1）",
            status=status,
            evidence=evidence,
        )
    )

    # ---- OBJ-11 编译验证 ----
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
    results.append(
        ObjectiveResult(
            obj_id="OBJ-11",
            name="编译验证",
            description="C 代码经 GCC 真实编译通过（DO-178C Table A-5.3）",
            status=status,
            evidence=evidence,
        )
    )

    # ---- OBJ-12 契约违约处理 ----
    if isinstance(sim, dict):
        cv = sim.get("contract_violation")
        sim_passed = bool(sim.get("passed", False))
        if sim_passed and cv is None:
            status = STATUS_PASS
            evidence = "仿真通过且无契约违约"
        elif cv is not None:
            status = STATUS_PARTIAL
            evidence = f"检测到契约违约: {cv.get('contract_id', '')} step={cv.get('failed_step', '?')}"
        else:
            status = STATUS_FAIL
            evidence = "仿真失败但未检测到契约违约"
    else:
        status = STATUS_FAIL
        evidence = "未执行仿真"
    results.append(
        ObjectiveResult(
            obj_id="OBJ-12",
            name="契约违约处理",
            description="数字孪生仿真契约断言被注入并可触发违约检测",
            status=status,
            evidence=evidence,
        )
    )

    logger.info(
        f"DO178Objectives:检查完成: {len(results)} 项 "
        f"满足 {sum(1 for r in results if r.status == STATUS_PASS)} "
        f"部分 {sum(1 for r in results if r.status == STATUS_PARTIAL)} "
        f"未满足 {sum(1 for r in results if r.status == STATUS_FAIL)}"
    )
    return results
