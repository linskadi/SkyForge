"""测试 skyforge_engine.core.standards 编码标准协议层实现。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))


from skyforge_engine.core.protocols import CodingStandardProtocol, Violation
from skyforge_engine.core.standards import (
    MISRACStandard,
    MISRA_CPPStandard,
    PythonSafetyStandard,
    CodingStandardRegistry,
    get_registry,
)


class TestProtocolCompliance:
    """测试各标准类对 CodingStandardProtocol 的合规性。"""

    def test_misra_c_standard_protocol(self):
        std = MISRACStandard()
        assert isinstance(std, CodingStandardProtocol)
        assert std.standard_name == "MISRA-C:2012"
        assert std.language == "c"

    def test_misra_cpp_standard_protocol(self):
        std = MISRA_CPPStandard()
        assert isinstance(std, CodingStandardProtocol)
        assert std.standard_name == "MISRA-C++/JSF AV C++/CERT C++"
        assert std.language == "cpp"

    def test_python_safety_standard_protocol(self):
        std = PythonSafetyStandard()
        assert isinstance(std, CodingStandardProtocol)
        assert std.standard_name == "军工软件Python编程规范 (T/ZASDI 0002-2023)"
        assert std.language == "python"


class TestMockScanPatterns:
    """测试 Mock 扫描模式返回正确结构。"""

    def test_misra_c_patterns_non_empty(self):
        std = MISRACStandard()
        patterns = std.get_mock_scan_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        for pat in patterns:
            assert "pattern" in pat
            assert "rule_id" in pat
            assert "severity" in pat
            assert "message" in pat

    def test_misra_cpp_patterns_non_empty(self):
        std = MISRA_CPPStandard()
        patterns = std.get_mock_scan_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        for pat in patterns:
            assert "pattern" in pat
            assert "rule_id" in pat

    def test_python_safety_patterns_non_empty(self):
        std = PythonSafetyStandard()
        patterns = std.get_mock_scan_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        for pat in patterns:
            assert "pattern" in pat
            assert "rule_id" in pat


class TestScanFunctionality:
    """测试 scan 方法能够正确检测违规。"""

    def test_misra_c_detects_malloc(self):
        std = MISRACStandard()
        code = "void f() { int* p = malloc(10); }"
        violations = std.scan(code)
        assert len(violations) >= 1
        assert any(v.rule_id == "misra-c2012-20.4" for v in violations)

    def test_misra_c_detects_printf(self):
        std = MISRACStandard()
        code = 'printf("hello\\n");'
        violations = std.scan(code)
        assert any(v.rule_id == "misra-c2012-21.6" for v in violations)

    def test_misra_c_no_false_positive_static(self):
        std = MISRACStandard()
        code = "static int x = 0;"
        violations = std.scan(code)
        # static 开头的变量声明不应触发 Rule 8.7
        assert not any(v.rule_id == "misra-c2012-8.7" for v in violations)

    def test_misra_cpp_detects_new(self):
        std = MISRA_CPPStandard()
        code = "int* p = new int[10];"
        violations = std.scan(code)
        assert any(v.rule_id == "jsf-av-cpp-18-4-1" for v in violations)

    def test_misra_cpp_detects_goto(self):
        std = MISRA_CPPStandard()
        code = "goto error;"
        violations = std.scan(code)
        assert any(v.rule_id == "jsf-av-cpp-6-6-1" for v in violations)

    def test_python_safety_detects_eval(self):
        std = PythonSafetyStandard()
        code = "result = eval(user_input)"
        violations = std.scan(code)
        assert any(v.rule_id == "python-P-01" for v in violations)

    def test_python_safety_detects_global(self):
        std = PythonSafetyStandard()
        code = "global x"
        violations = std.scan(code)
        assert any(v.rule_id == "python-P-02" for v in violations)

    def test_python_safety_no_violation_clean_code(self):
        std = PythonSafetyStandard()
        code = "x = 1 + 2\nprint(x)\n"
        violations = std.scan(code)
        assert violations == []

    def test_violation_structure(self):
        std = PythonSafetyStandard()
        code = "eval('1+1')"
        violations = std.scan(code)
        assert len(violations) > 0
        v = violations[0]
        assert isinstance(v, Violation)
        assert v.line == 1
        assert v.severity == "error"
        assert v.message != ""


class TestCodingStandardRegistry:
    """测试 CodingStandardRegistry 注册与查找功能。"""

    def test_register_and_get(self):
        registry = CodingStandardRegistry()
        std = MISRACStandard()
        registry.register(std)
        retrieved = registry.get(std.standard_name)
        assert retrieved is std

    def test_unregister(self):
        registry = CodingStandardRegistry()
        std = MISRACStandard()
        registry.register(std)
        registry.unregister(std.standard_name)
        assert registry.get(std.standard_name) is None

    def test_get_for_language(self):
        registry = CodingStandardRegistry()
        registry.register(MISRACStandard())
        registry.register(MISRA_CPPStandard())
        registry.register(PythonSafetyStandard())

        c_standards = registry.get_for_language("c")
        assert len(c_standards) == 1
        assert c_standards[0].standard_name == "MISRA-C:2012"

        cpp_standards = registry.get_for_language("cpp")
        assert len(cpp_standards) == 1
        assert cpp_standards[0].standard_name == "MISRA-C++/JSF AV C++/CERT C++"

        py_standards = registry.get_for_language("python")
        assert len(py_standards) == 1
        assert "Python" in py_standards[0].standard_name

    def test_get_all(self):
        registry = CodingStandardRegistry()
        registry.register(MISRACStandard())
        registry.register(PythonSafetyStandard())
        all_std = registry.get_all()
        assert len(all_std) == 2

    def test_get_mock_scan_patterns_merge(self):
        registry = CodingStandardRegistry()
        registry.register(MISRACStandard())
        registry.register(MISRA_CPPStandard())

        c_patterns = registry.get_mock_scan_patterns("c")
        assert len(c_patterns) > 0

        cpp_patterns = registry.get_mock_scan_patterns("cpp")
        assert len(cpp_patterns) > 0

    def test_global_registry_singleton(self):
        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2

    def test_registry_ignores_duplicate_register(self):
        registry = CodingStandardRegistry()
        std1 = MISRACStandard()
        std2 = MISRACStandard()
        registry.register(std1)
        registry.register(std2)
        assert registry.get(std1.standard_name) is std2
