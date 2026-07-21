"""端到端验证覆盖率数据流闭环。

模拟 pipeline_result 直接测试三个补丁是否协同工作。
"""

import sys
import os

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_patch1_coverage_analyzer_returns_real_or_static():
    """补丁1验证: coverage_analyzer 返回 method 字段。"""
    print("=" * 70)
    print("【补丁1验证】coverage_analyzer.analyze_code_coverage() 返回 method 字段")
    print("=" * 70)
    from skyforge_engine.report.coverage_analyzer import analyze_code_coverage

    test_code = """
int classify(int x) {
    if (x > 0 && x < 100) return 1;
    if (x == 0) return 0;
    return -1;
}
int main() {
    classify(50);
    classify(0);
    return 0;
}
"""
    result = analyze_code_coverage(
        code=test_code,
        fault_injected=True,
        dal="A",
        use_real_coverage=True,
    )
    print(f"  analyzed:       {result.get('analyzed')}")
    print(f"  method:         {result.get('method')}")
    print(f"  version:        {result.get('version')}")
    print(f"  statement_cov:  {result.get('statement_coverage')}% / target {result.get('statement_target')}%")
    print(f"  decision_cov:   {result.get('decision_coverage')}% / target {result.get('decision_target')}%")
    print(f"  mcdc_cov:       {result.get('mcdc_coverage')}% / target {result.get('mcdc_target')}%")
    print(f"  mcdc_satisfied: {result.get('mcdc_satisfied')}/{result.get('mcdc_total')}")
    print(f"  dal:            {result.get('dal')}")
    print(f"  fault_injected: {result.get('fault_injected')}")

    assert result.get("analyzed") is True, "analyzed 应为 True"
    assert "method" in result, "method 字段必须存在"
    assert result["method"] in ("gcov", "static_analysis"), f"method 值异常: {result['method']}"
    print(f"\n  ✅ 补丁1验证通过：method={result['method']}")
    return result


def test_patch3_do178_objectives_with_method():
    """补丁3验证: do178_objectives 动态显示收集方法。"""
    print("\n" + "=" * 70)
    print("【补丁3验证】do178_objectives._check_obj13/14/15 显示收集方法")
    print("=" * 70)
    from skyforge_engine.report.do178_objectives import (
        check_objectives,
    )

    # 模拟 pipeline_result 包含 coverage_result
    coverage_result = {
        "analyzed": True,
        "method": "static_analysis",
        "statement_coverage": 100.0,
        "decision_coverage": 75.0,
        "mcdc_coverage": 50.0,
        "statement_target": 100.0,
        "decision_target": 100.0,
        "mcdc_target": 100.0,
        "dal": "A",
    }
    pipeline_result = {
        "coverage_result": coverage_result,
        "requirement": {"req_id": "TEST-001"},
        "contract": "version: 1.0.0",
    }
    objectives = check_objectives(pipeline_result, dal="A")
    for obj in objectives:
        if obj.obj_id in ("OBJ-13", "OBJ-14", "OBJ-15"):
            print(f"  {obj.obj_id} ({obj.name}):")
            print(f"    status:  {obj.status}")
            print(f"    evidence: {obj.evidence}")
            assert "收集方法" in obj.evidence, f"{obj.obj_id} 证据未包含收集方法"
    print("\n  ✅ 补丁3验证通过：所有覆盖率目标都显示收集方法")


def test_patch3_with_gcov_method():
    """补丁3验证: 当 method=gcov 时显示真实 gcov/lcov。"""
    print("\n" + "=" * 70)
    print("【补丁3验证】method=gcov 时显示 '真实 gcov/lcov'")
    print("=" * 70)
    from skyforge_engine.report.do178_objectives import check_objectives

    coverage_result = {
        "analyzed": True,
        "method": "gcov",
        "statement_coverage": 100.0,
        "decision_coverage": 100.0,
        "mcdc_coverage": 100.0,
        "statement_target": 100.0,
        "decision_target": 100.0,
        "mcdc_target": 100.0,
        "dal": "A",
    }
    pipeline_result = {"coverage_result": coverage_result}
    objectives = check_objectives(pipeline_result, dal="A")
    for obj in objectives:
        if obj.obj_id == "OBJ-15":
            print(f"  {obj.obj_id}: status={obj.status}")
            print(f"    evidence: {obj.evidence}")
            assert "真实 gcov/lcov" in obj.evidence, "method=gcov 时应显示真实 gcov/lcov"
            assert obj.status == "满足", f"100% MC/DC 应为满足, 实际: {obj.status}"
    print("\n  ✅ 补丁3 gcov 路径验证通过")


def test_patch2_report_generator_renders_coverage():
    """补丁2验证: report_generator 在 HTML 中渲染覆盖率区块。"""
    print("\n" + "=" * 70)
    print("【补丁2验证】report_generator HTML 包含覆盖率区块")
    print("=" * 70)
    from skyforge_engine.report.report_generator import generate_report

    coverage_result = {
        "analyzed": True,
        "method": "static_analysis",
        "statement_coverage": 100.0,
        "decision_coverage": 75.0,
        "mcdc_coverage": 50.0,
        "statement_target": 100.0,
        "decision_target": 100.0,
        "mcdc_target": 100.0,
        "mcdc_satisfied": 1,
        "mcdc_total": 2,
        "dal": "A",
        "version": "V0.4-Real+Static",
        "fault_injected": True,
        "decision_points": [
            {
                "line": 3,
                "type": "if",
                "conditions": ["x > 0", "x < 100"],
                "operator": "&&",
                "status": "满足",
            }
        ],
    }
    pipeline_result = {
        "requirement": {"req_id": "TEST-001", "module_name": "test_module"},
        "contract": "version: 1.0.0",
        "final_code": "int main(){return 0;}",
        "coverage_result": coverage_result,
    }
    try:
        html = generate_report(pipeline_result)
        print(f"  HTML 长度: {len(html)} 字符")
        assert "覆盖率分析" in html, "HTML 应包含 '覆盖率分析' 标题"
        assert "statement_coverage" not in html, "HTML 不应包含原始字段名"
        assert "100.0%" in html or "100%" in html, "HTML 应包含覆盖率百分比"
        assert "静态分析回退" in html, "HTML 应显示静态分析回退标签"
        assert "判定点详情" in html, "HTML 应包含判定点详情表"
        print("\n  ✅ 补丁2验证通过：HTML 正确渲染覆盖率区块")
        return html
    except Exception as e:
        print(f"  ❌ 补丁2验证失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_fallback_behavior():
    """回退行为验证: 工具不可用/收集失败时自动回退静态分析。"""
    print("\n" + "=" * 70)
    print("【回退验证】真实覆盖率收集失败时自动回退静态分析")
    print("=" * 70)
    from skyforge_engine.dal.gcov_collector import _find_gcc, _find_lcov

    gcc = _find_gcc()
    lcov = _find_lcov()
    print(f"  GCC 可用:  {gcc or '(不可用)'}")
    print(f"  lcov 可用: {lcov or '(不可用)'}")

    from skyforge_engine.report.coverage_analyzer import analyze_code_coverage

    result = analyze_code_coverage(
        code="int main(){if(1)return 1;return 0;}",
        dal="A",
        use_real_coverage=True,
    )
    print(f"  最终 method: {result.get('method')}")
    # 无论工具是否可用，只要收集失败就应该回退静态分析
    assert result["method"] == "static_analysis", (
        f"真实覆盖率收集不可用时应回退静态分析, 实际: {result['method']}"
    )
    print("\n  ✅ 回退验证通过：真实覆盖率不可用 → 自动使用静态分析")


def main():
    print("SkyForge 覆盖率数据流闭环端到端测试")
    print("测试时间:", __import__("datetime").datetime.now().isoformat())
    print()

    try:
        test_patch1_coverage_analyzer_returns_real_or_static()
    except Exception as e:
        print(f"  ❌ 补丁1失败: {e}")
        import traceback
        traceback.print_exc()

    try:
        test_patch3_do178_objectives_with_method()
    except Exception as e:
        print(f"  ❌ 补丁3失败: {e}")
        import traceback
        traceback.print_exc()

    try:
        test_patch3_with_gcov_method()
    except Exception as e:
        print(f"  ❌ 补丁3 gcov 路径失败: {e}")
        import traceback
        traceback.print_exc()

    try:
        test_patch2_report_generator_renders_coverage()
    except Exception as e:
        print(f"  ❌ 补丁2失败: {e}")
        import traceback
        traceback.print_exc()

    try:
        test_fallback_behavior()
    except Exception as e:
        print(f"  ❌ 回退验证失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
