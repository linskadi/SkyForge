"""SkyForge Core CLI — 轻量级机载软件代码生成工具。

脱离 Web 浏览器独立运行，适用于机载开发环境、CI/CD 和嵌入式 Linux。

用法:
    python -m skyforge_core generate -r requirements.txt -o output/
    python -m skyforge_core check -c filter.c -t filter.contract
    python -m skyforge_core simulate -c filter.c -t filter.contract --fault bias
    python -m skyforge_core report -p result.json -o report.html
    python -m skyforge_core verify --contract output/contract.json

安装:
    pip install -e .   # 开发安装（最小依赖 6 个包，~50MB）

依赖:
    必需: pyyaml, numpy, loguru, pydantic, pydantic-settings
    可选: httpx, openai (启用 --use-llm 时)
    外部: cppcheck, gcc (全部可选，有 Mock 降级)
    形式化验证: z3-solver (可选，缺失时 Z3 检查自动降级为 SKIPPED)
                cbmc (可选，缺失时 CBMC 检查自动降级为 SKIPPED)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from skyforge_engine.utils.log_util import logger


def cmd_generate(args: argparse.Namespace) -> int:
    """从需求文件生成 DO-178C 合规代码。

    全流程：需求解析 → 契约生成 → 代码生成 → MISRA 扫描 → 修复闭环
    → 数字孪生仿真（可选）→ 合规报告。
    """
    requirement_text = _read_requirement(args.requirement)

    from skyforge_engine.pipeline import run_full_pipeline

    logger.info(f"SkyForge Core: 开始生成，DAL={args.dal}，仿真={args.simulate}")

    result = asyncio.run(
        run_full_pipeline(
            requirement=requirement_text,
            simulate=args.simulate,
        )
    )

    # 输出产物到指定目录
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_if_exists(result, "final_code", output_dir / "output.c")
    _write_if_exists(result, "contract", output_dir / "output.contract.yaml")
    _write_json(output_dir / "pipeline_result.json", _safe_serialize(result))

    # 统计
    violations = result.get("final_violations", []) or []
    logger.info(
        f"SkyForge Core: 生成完成 - "
        f"代码 {_len_str(result.get('final_code'))} 行, "
        f"违规 {len(violations)} 条, "
        f"产物输出至 {output_dir}"
    )

    # 合规摘要
    _print_compliance_summary(result, args.dal)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """校验已有代码的 MISRA-C 合规性和契约一致性。"""
    code = Path(args.code).read_text(encoding="utf-8")
    contract = Path(args.contract).read_text(encoding="utf-8") if args.contract else None

    from skyforge_engine.tools.cppcheck_scanner import scan as cppcheck_scan
    from skyforge_engine.tools.contract_checker import check as contract_check

    logger.info(f"SkyForge Core: 开始校验 {args.code}")

    violations = cppcheck_scan(code)
    contract_result = None
    if contract:
        contract_result = contract_check(code, contract)

    # 输出结果
    print("=== MISRA-C 扫描 ===")
    print(f"违规数: {len(violations)}")
    for v in violations:
        print(f"  [{v.rule_id}] L{v.line}: {v.message}")

    if contract_result:
        passed = contract_result.passed if hasattr(contract_result, 'passed') else contract_result.get("passed", False)
        print("\n=== 契约校验 ===")
        print(f"结果: {'✅ 通过' if passed else '❌ 未通过'}")

    return 0 if len(violations) == 0 else 1


def cmd_simulate(args: argparse.Namespace) -> int:
    """运行数字孪生仿真。"""
    code = Path(args.code).read_text(encoding="utf-8")
    contract = Path(args.contract).read_text(encoding="utf-8") if args.contract else ""

    from skyforge_engine.digital_twin.simulation_engine import SimulationEngine

    logger.info(f"SkyForge Core: 开始仿真，故障={args.fault}，步数={args.steps}")

    engine = SimulationEngine()
    result = engine.run_simulation(
        code=code,
        contract_yaml=contract,
        fault_type=args.fault,
        steps=args.steps,
    )

    # 输出结果
    passed = result.passed if hasattr(result, 'passed') else result.get("passed", False)
    print("=== 数字孪生仿真 ===")
    print(f"结果: {'✅ 通过' if passed else '❌ 未通过'}")
    print(f"步数: {result.total_steps if hasattr(result, 'total_steps') else result.get('total_steps', '?')}")

    stats = result.statistics if hasattr(result, 'statistics') else result.get("statistics", {})
    if stats:
        print(f"统计: input[{stats.get('input_min', '?')}, {stats.get('input_max', '?')}] "
              f"output[{stats.get('output_min', '?')}, {stats.get('output_max', '?')}] "
              f"duration={stats.get('duration_ms', '?')}ms")

    if args.output:
        import numpy as np
        output_path = Path(args.output)
        input_wave = result.input_waveform if hasattr(result, 'input_waveform') else result.get("input_waveform", [])
        output_wave = result.output_waveform if hasattr(result, 'output_waveform') else result.get("output_waveform", [])
        np.savetxt(
            output_path,
            list(zip(input_wave, output_wave)),
            header="input,output",
            delimiter=",",
            comments="",
        )
        print(f"波形数据已保存至 {output_path}")

    return 0 if passed else 1


def cmd_report(args: argparse.Namespace) -> int:
    """生成 DO-178C 合规报告。"""
    with open(args.pipeline_result, "r", encoding="utf-8") as f:
        pipeline_result = json.load(f)

    from skyforge_engine.report.report_generator import generate_report
    from skyforge_engine.report.traceability_matrix import build_matrix
    from skyforge_engine.report.do178_objectives import check_objectives

    logger.info("SkyForge Core: 开始生成报告")

    matrix = build_matrix(pipeline_result)
    objectives = check_objectives(pipeline_result)

    html = generate_report(
        pipeline_result=pipeline_result,
        traceability_matrix=[e.to_dict() for e in matrix],
        objectives=[o.to_dict() for o in objectives],
    )

    output_path = Path(args.output)
    output_path.write_text(html, encoding="utf-8")
    logger.info(f"SkyForge Core: 报告已生成 → {output_path}")

    # 统计
    pass_count = sum(1 for o in objectives if o.status == "满足")
    total = len(objectives)
    print("=== DO-178C 合规报告 ===")
    print(f"目标符合性: {pass_count}/{total} 满足")
    print(f"报告位置: {output_path}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """对契约执行形式化验证（Z3 SMT + CBMC 有界模型检查）。

    将契约约束转换为 Z3 SMT 约束验证一致性，并（可选）调用 CBMC
    对生成的代码进行有界模型检查。Z3/CBMC 缺失时自动降级为 SKIPPED。
    """
    contract_path = Path(args.contract)
    if not contract_path.exists():
        logger.error(f"SkyForge Core: 契约文件不存在: {contract_path}")
        print(f"❌ 契约文件不存在: {contract_path}")
        return 2

    contract_text = contract_path.read_text(encoding="utf-8")

    # 可选代码文件（用于 CBMC 验证）
    code_text: str | None = None
    if args.code:
        code_path = Path(args.code)
        if code_path.exists():
            code_text = code_path.read_text(encoding="utf-8")
        else:
            logger.warning(f"代码文件不存在，跳过 CBMC: {code_path}")

    from skyforge_engine.tools.contract_formal_verifier import verify_contract

    logger.info(f"SkyForge Core: 开始形式化验证 {contract_path}")

    verification = verify_contract(contract_text, code=code_text)
    checks = _build_verification_checks(verification)
    summary = _summarize_checks(checks)
    tool_label = _verification_tool_label(verification)

    # 顶部 banner
    print()
    print("╭─ Formally Verifying Contract ─────────────────╮")
    print(f"│ Contract: {str(contract_path):<36}│")
    print(f"│ Tool: {tool_label:<41}│")
    print("╰───────────────────────────────────────────────╯")
    print()

    # 各检查项
    for chk in checks:
        _print_check_line(chk)

    # 汇总
    print("────────────────────────────────────")
    overall = summary["overall"]
    print(
        f"Result: {overall.upper()} "
        f"({summary['passed']}/{summary['total']} passed, "
        f"{summary['failed']} failed, {summary['skipped']} skipped)"
    )
    print(f"Total time: {summary['total_duration_ms'] / 1000:.3f}s")

    # 失败时返回非 0 退出码（SKIPPED 不算失败）
    return 0 if overall != "failed" else 1


# ---- 形式化验证辅助函数 ----

def _build_verification_checks(verification) -> list[dict]:
    """将底层 VerificationResult 转换为结构化检查项列表。

    映射规则（保持与 verify_contract 接口向后兼容，不修改底层逻辑）：
    - 约束一致性 (Z3): PASS/FAIL/SKIPPED，反例来自 contradictions
    - 边界测试用例生成 (Z3): PASS/SKIPPED
    - 有界模型检查 (CBMC): PASS/FAIL/SKIPPED，反例来自 cbmc_output
    """
    checks: list[dict] = []

    # Check 1: Z3 约束一致性
    if verification.z3_available:
        counter_example = None
        status = "passed"
        if not verification.is_consistent:
            status = "failed"
            counter_example = "; ".join(verification.contradictions) if verification.contradictions else "约束不可同时满足"
        checks.append({
            "name": "Constraint consistency",
            "tool": "Z3",
            "status": status,
            "duration_ms": int(verification.z3_solver_time_ms or 0),
            "counter_example": counter_example,
        })
    else:
        checks.append({
            "name": "Constraint consistency",
            "tool": "Z3",
            "status": "skipped",
            "duration_ms": 0,
            "counter_example": "Z3 不可用（pip install z3-solver 启用）",
        })

    # Check 2: Z3 边界测试用例生成
    if verification.z3_available:
        if verification.test_case_count > 0:
            status = "passed"
            counter_example = None
        elif not verification.is_consistent:
            status = "skipped"
            counter_example = "契约不一致，跳过测试用例生成"
        else:
            status = "skipped"
            counter_example = "无可解析的数值边界条件"
        checks.append({
            "name": "Boundary test case generation",
            "tool": "Z3",
            "status": status,
            "duration_ms": 0,
            "counter_example": counter_example,
        })
    else:
        checks.append({
            "name": "Boundary test case generation",
            "tool": "Z3",
            "status": "skipped",
            "duration_ms": 0,
            "counter_example": "Z3 不可用",
        })

    # Check 3: CBMC 有界模型检查
    if verification.cbmc_available:
        if verification.cbmc_verified:
            status = "passed"
            counter_example = None
        else:
            status = "failed"
            counter_example = verification.cbmc_output[:500] if verification.cbmc_output else "CBMC 验证未通过"
        checks.append({
            "name": "Bounded model checking",
            "tool": "CBMC",
            "status": status,
            "duration_ms": int(verification.cbmc_time_ms or 0),
            "counter_example": counter_example,
        })
    else:
        checks.append({
            "name": "Bounded model checking",
            "tool": "CBMC",
            "status": "skipped",
            "duration_ms": 0,
            "counter_example": "CBMC 不可用（requires CBMC）",
        })

    return checks


def _summarize_checks(checks: list[dict]) -> dict:
    """汇总检查项的通过/失败/跳过统计。"""
    passed = sum(1 for c in checks if c["status"] == "passed")
    failed = sum(1 for c in checks if c["status"] == "failed")
    skipped = sum(1 for c in checks if c["status"] == "skipped")
    total = len(checks)
    overall = "failed" if failed > 0 else ("passed" if passed > 0 else "skipped")
    total_duration_ms = sum(c["duration_ms"] for c in checks)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "overall": overall,
        "total_duration_ms": total_duration_ms,
    }


def _verification_tool_label(verification) -> str:
    """生成顶部 Tool 标签：Z3 / CBMC / Z3+CBMC / Mock。"""
    tools = []
    if verification.z3_available:
        tools.append("Z3")
    if verification.cbmc_available:
        tools.append("CBMC")
    if not tools:
        return "Mock (Z3/CBMC 均不可用)"
    return "+".join(tools) + " SMT Solver"


def _print_check_line(check: dict) -> None:
    """单行打印一个检查项（含反例展开）。"""
    status = check["status"]
    icon = {"passed": "✓", "failed": "✗", "skipped": "-"}.get(status, "?")
    label = status.upper()
    duration = f"{check['duration_ms'] / 1000:.3f}s"
    tool_tag = f"[{check.get('tool', '')}]" if check.get("tool") else ""
    print(f"{icon} {check['name']:<28} [{label}] {tool_tag} ({duration})")
    if check.get("counter_example"):
        for line in str(check["counter_example"]).splitlines() or [str(check["counter_example"])]:
            print(f"  └─ {line}")


# ---- 工具函数 ----

def _read_requirement(source: str) -> str:
    """读取需求：文件路径 或 直接文本。"""
    path = Path(source)
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8")
    return source


def _write_if_exists(result: dict, key: str, path: Path) -> None:
    """如果 result 中存在该 key 且非空，写入文件。"""
    content = result.get(key)
    if content and isinstance(content, str):
        path.write_text(content, encoding="utf-8")


def _write_json(path: Path, data: dict) -> None:
    """写入 JSON 文件。"""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _len_str(s: str | None) -> int:
    """安全获取字符串行数。"""
    if not s:
        return 0
    return len(s.splitlines())


def _print_compliance_summary(result: dict, dal: str) -> None:
    """打印合规摘要。"""
    from skyforge_engine.report.do178_objectives import check_objectives
    from skyforge_engine.schemas.dal_objectives import DAL

    try:
        dal_enum = DAL.from_string(dal)
        objectives = check_objectives(result, dal=dal_enum)
        pass_count = sum(1 for o in objectives if o.status == "满足")
        partial = sum(1 for o in objectives if o.status == "部分满足")
        fail = sum(1 for o in objectives if o.status == "未满足")
        na = sum(1 for o in objectives if o.status == "不适用")
        print(f"\n=== DO-178C {dal_enum.value} 合规摘要 ===")
        print(f"满足: {pass_count} | 部分满足: {partial} | 未满足: {fail} | 不适用: {na}")
    except Exception:
        pass


def _safe_serialize(obj: object) -> dict:
    """安全序列化 pipeline_result 为 JSON 兼容字典。"""
    result: dict = {}
    for key, value in obj.items() if isinstance(obj, dict) else {}:
        try:
            json.dumps({key: value})
            result[key] = value
        except (TypeError, ValueError):
            result[key] = str(value)[:500]
    return result


# ---- 主入口 ----

def main() -> int:
    """CLI 主入口。"""
    parser = argparse.ArgumentParser(
        prog="skyforge",
        description="SkyForge Core — AI 驱动的机载软件轻量化开发工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  skyforge generate -r "设计一个10Hz低通滤波器" -o output/
  skyforge generate -r requirements.txt --dal B --simulate --fault bias
  skyforge check -c filter.c -t filter.contract
  skyforge simulate -c filter.c -t filter.contract --fault noise --steps 200
  skyforge report -p pipeline_result.json -o report.html
  skyforge verify --contract output/contract.json
  skyforge verify --contract output/contract.json --code output/output.c
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ---- generate ----
    gen = subparsers.add_parser("generate", help="从需求生成 DO-178C 合规代码")
    gen.add_argument("-r", "--requirement", required=True,
                     help="需求文本 或 需求文件路径")
    gen.add_argument("-o", "--output", default="./output",
                     help="输出目录（默认 ./output）")
    gen.add_argument("--dal", default="C", choices=["A", "B", "C", "D", "E"],
                     help="安全等级（默认 C）")
    gen.add_argument("--use-llm", action="store_true",
                     help="启用 LLM 增强（默认使用规则引擎）")
    gen.add_argument("--simulate", action="store_true", default=True,
                     help="运行数字孪生仿真（默认开启）")
    gen.add_argument("--no-simulate", action="store_false", dest="simulate",
                     help="跳过数字孪生仿真")
    gen.add_argument("--fault", choices=["bias", "signal_loss", "noise", "stuck", "step"],
                     help="故障注入类型（需 --simulate）")

    # ---- check ----
    chk = subparsers.add_parser("check", help="校验代码 MISRA-C 合规性和契约一致性")
    chk.add_argument("-c", "--code", required=True, help="C 代码文件路径")
    chk.add_argument("-t", "--contract", help="契约 YAML 文件路径（可选）")

    # ---- simulate ----
    sim = subparsers.add_parser("simulate", help="运行数字孪生仿真")
    sim.add_argument("-c", "--code", required=True, help="C 代码文件路径")
    sim.add_argument("-t", "--contract", help="契约 YAML 文件路径")
    sim.add_argument("--fault", choices=["bias", "signal_loss", "noise", "stuck", "step"],
                     help="故障注入类型")
    sim.add_argument("--steps", type=int, default=200, help="仿真步数（默认 200）")
    sim.add_argument("-o", "--output", help="波形 CSV 输出路径")

    # ---- report ----
    rpt = subparsers.add_parser("report", help="生成 DO-178C 合规报告")
    rpt.add_argument("-p", "--pipeline-result", required=True,
                     help="pipeline_result JSON 文件路径")
    rpt.add_argument("-o", "--output", default="report.html",
                     help="报告输出路径（默认 report.html）")

    # ---- verify ----
    vfy = subparsers.add_parser(
        "verify",
        help="对契约执行形式化验证（Z3 SMT + CBMC 有界模型检查）",
    )
    vfy.add_argument(
        "--contract",
        default="./output/contract.json",
        help="契约文件路径（YAML 或 JSON，默认 ./output/contract.json）",
    )
    vfy.add_argument(
        "--code",
        help="可选的 C 代码文件路径（提供后启用 CBMC 有界模型检查）",
    )

    args = parser.parse_args()

    if args.command == "generate":
        return cmd_generate(args)
    elif args.command == "check":
        return cmd_check(args)
    elif args.command == "simulate":
        return cmd_simulate(args)
    elif args.command == "report":
        return cmd_report(args)
    elif args.command == "verify":
        return cmd_verify(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
