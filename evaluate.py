#!/usr/bin/env python3
"""远程评测脚本：自动运行 SkyForge 全流程并生成评测报告。

使用方式：
    python evaluate.py --input requirements.txt --output report.json

评测流程：
1. 需求解析（RequirementParserAgent）
2. 契约生成（ContractGeneratorAgent）
3. 代码生成（CodeGeneratorAgent）
4. MISRA-C 合规检查（Cppcheck）
5. 自动修复（CodeRepairerAgent）
6. 数字孪生仿真（SimulationEngine）
7. 生成评测报告
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))


async def run_evaluation(input_file: str, output_file: str) -> dict:
    """运行完整评测流程。"""
    report = {
        "tool": "SkyForge",
        "version": "0.1.0",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "input_file": input_file,
        "stages": {},
        "summary": {},
    }

    # 读取需求
    with open(input_file, "r", encoding="utf-8") as f:
        requirements = f.read().strip()

    print(f"[评测] 输入需求: {requirements[:100]}...")

    # 阶段1: 需求解析
    print("\n[阶段1] 需求解析...")
    t0 = time.time()
    try:
        from app.core.agents.requirement_parser_agent import RequirementParserAgent

        parser = RequirementParserAgent()
        req_json = await parser.run(requirements)
        report["stages"]["requirement_parsing"] = {
            "status": "success",
            "duration_s": round(time.time() - t0, 2),
            "output": req_json,
        }
        print(f"  ✓ 需求解析完成 ({time.time() - t0:.2f}s)")
    except Exception as e:
        report["stages"]["requirement_parsing"] = {
            "status": "error",
            "error": str(e),
            "duration_s": round(time.time() - t0, 2),
        }
        print(f"  ✗ 需求解析失败: {e}")
        req_json = {}

    # 阶段2: 契约生成
    print("\n[阶段2] 契约生成...")
    t0 = time.time()
    try:
        from app.core.agents.contract_generator_agent import ContractGeneratorAgent

        contract_gen = ContractGeneratorAgent()
        contract = await contract_gen.run(req_json)
        report["stages"]["contract_generation"] = {
            "status": "success",
            "duration_s": round(time.time() - t0, 2),
            "output": contract[:500] if contract else "",
        }
        print(f"  ✓ 契约生成完成 ({time.time() - t0:.2f}s)")
    except Exception as e:
        report["stages"]["contract_generation"] = {
            "status": "error",
            "error": str(e),
            "duration_s": round(time.time() - t0, 2),
        }
        print(f"  ✗ 契约生成失败: {e}")
        contract = ""

    # 阶段3: 代码生成
    print("\n[阶段3] 代码生成...")
    t0 = time.time()
    try:
        from app.core.agents.code_generator_agent import CodeGeneratorAgent

        code_gen = CodeGeneratorAgent()
        code = await code_gen.run(req_json, contract)
        report["stages"]["code_generation"] = {
            "status": "success",
            "duration_s": round(time.time() - t0, 2),
            "output_lines": len(code.splitlines()) if code else 0,
            "output": code[:1000] if code else "",
        }
        print(f"  ✓ 代码生成完成 ({time.time() - t0:.2f}s, {len(code.splitlines()) if code else 0} 行)")
    except Exception as e:
        report["stages"]["code_generation"] = {
            "status": "error",
            "error": str(e),
            "duration_s": round(time.time() - t0, 2),
        }
        print(f"  ✗ 代码生成失败: {e}")
        code = ""

    # 阶段4: MISRA-C 扫描
    print("\n[阶段4] MISRA-C 合规检查...")
    t0 = time.time()
    violations = []
    try:
        from app.core.tools.cppcheck_scanner import scan as cppcheck_scan

        if code:
            violations = cppcheck_scan(code)
        report["stages"]["misra_scan"] = {
            "status": "success",
            "duration_s": round(time.time() - t0, 2),
            "violations_count": len(violations),
            "unique_rules": list(set(v.rule_id for v in violations)),
        }
        print(f"  ✓ MISRA扫描完成 ({len(violations)} 违规)")
    except Exception as e:
        report["stages"]["misra_scan"] = {
            "status": "error",
            "error": str(e),
            "duration_s": round(time.time() - t0, 2),
        }
        print(f"  ✗ MISRA扫描失败: {e}")

    # 阶段5: 自动修复
    print("\n[阶段5] 自动修复...")
    t0 = time.time()
    repairs = []
    try:
        from app.core.agents.code_repairer_agent import CodeRepairerAgent

        if code and violations:
            repairer = CodeRepairerAgent()
            code, repairs = await repairer.run(code, violations)
        report["stages"]["auto_repair"] = {
            "status": "success",
            "duration_s": round(time.time() - t0, 2),
            "repairs_count": len(repairs),
            "repaired_rules": list(set(r.rule_id for r in repairs)),
        }
        print(f"  ✓ 自动修复完成 ({len(repairs)} 处修复)")
    except Exception as e:
        report["stages"]["auto_repair"] = {
            "status": "error",
            "error": str(e),
            "duration_s": round(time.time() - t0, 2),
        }
        print(f"  ✗ 自动修复失败: {e}")

    # 阶段6: 数字孪生仿真
    print("\n[阶段6] 数字孪生仿真...")
    t0 = time.time()
    try:
        from app.core.digital_twin.simulation_engine import SimulationEngine

        engine = SimulationEngine()
        sim_result = await engine.run(req_json, code)
        report["stages"]["simulation"] = {
            "status": "success",
            "duration_s": round(time.time() - t0, 2),
            "passed": sim_result.get("passed", False) if isinstance(sim_result, dict) else False,
        }
        print(f"  ✓ 仿真完成 ({time.time() - t0:.2f}s)")
    except Exception as e:
        report["stages"]["simulation"] = {
            "status": "error",
            "error": str(e),
            "duration_s": round(time.time() - t0, 2),
        }
        print(f"  ✗ 仿真失败: {e}")

    # 汇总
    total_violations = report["stages"].get("misra_scan", {}).get("violations_count", 0)
    repaired = report["stages"].get("auto_repair", {}).get("repairs_count", 0)
    remaining = max(0, total_violations - repaired)

    report["summary"] = {
        "total_stages": 6,
        "successful_stages": sum(
            1
            for s in report["stages"].values()
            if s.get("status") == "success"
        ),
        "total_misra_violations": total_violations,
        "repaired_violations": repaired,
        "remaining_violations": remaining,
        "fix_rate": f"{repaired / total_violations * 100:.1f}%" if total_violations > 0 else "N/A",
        "rules_supported": 57,
    }

    # 写入报告
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 50}")
    print(f"评测完成！报告已保存到: {output_file}")
    print(f"  MISRA 违规: {total_violations} 处")
    print(f"  自动修复: {repaired} 处")
    print(f"  剩余违规: {remaining} 处")
    print(f"  修复率: {report['summary']['fix_rate']}")
    print(f"  支持规则: {report['summary']['rules_supported']} 条")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="SkyForge 远程评测脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python evaluate.py --input examples/filter_requirements.txt --output report.json
  python evaluate.py -i requirements.txt -o result.json
        """,
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="输入需求文件路径（.txt 或 .md）",
    )
    parser.add_argument(
        "-o", "--output",
        default="evaluation_report.json",
        help="输出评测报告路径（默认: evaluation_report.json）",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误: 输入文件不存在: {args.input}")
        sys.exit(1)

    asyncio.run(run_evaluation(args.input, args.output))


if __name__ == "__main__":
    main()
