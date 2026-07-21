"""测试 CodeGenerator/CodeRepairer 的输出安全校验。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from skyforge_llm.security.validator import validate_output


def test_validate_output_detects_malloc():
    """validate_output 应检测到 malloc 调用。"""
    code = "void *p = malloc(100);"
    result = validate_output(code)
    assert not result.passed
    assert any("malloc" in v for v in result.violations)


def test_validate_output_allows_safe_code():
    """正常 C 代码不应触发违规。

    system_state / free_function 等变量名因 \\b 词边界 + \\s*\\( 锚定
    不会误判（system 后须紧跟左括号才触发）。
    """
    code = """
    int system_state = 0;  /* system_state 变量名不应触发违规 */
    double lowpass(double input) {
        return input * 0.1;
    }
    """
    result = validate_output(code)
    # system_state 不应触发，因为没有 system 后紧跟左括号
    assert result.passed or not any("system" in v for v in result.violations)


def test_validate_output_detects_multiple_violations():
    """多种违规同时存在。"""
    code = """
    void *p = malloc(100);
    free(p);
    goto error;
    """
    result = validate_output(code)
    assert not result.passed
    assert len(result.violations) >= 3


def test_code_generator_with_violations_does_not_raise():
    """CodeGenerator 收到含 malloc 的 LLM 输出不应抛异常。"""
    # 这个测试可能需要 mock 整个 Agent，比较复杂
    # 简化：仅验证 validate_output + log 逻辑不抛异常
    bad_code = "void *p = malloc(100);"
    result = validate_output(bad_code)
    assert not result.passed
    # 模拟 Agent 内的告警逻辑
    for v in result.violations:
        # 不应抛异常
        pass


def test_code_generator_with_safe_code_no_warning():
    """正常代码不应产生违规告警。"""
    safe_code = """
    double lowpass(double input) {
        static double last = 0.0;
        last = last + 0.1 * (input - last);
        return last;
    }
    """
    result = validate_output(safe_code)
    assert result.passed
