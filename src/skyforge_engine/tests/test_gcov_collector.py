"""测试 gcov_collector 严格模式（无优雅降级）。"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest
from skyforge_engine.dal.gcov_collector import (
    ToolNotFoundError,
    GcovCoverageResult,
    _is_real_enabled,
    _find_gcc,
    _find_lcov,
    _parse_lcov_info,
    _parse_version,
    _get_tool_version,
    collect_coverage,
)


# ---------------------------------------------------------------------------
# 版本解析
# ---------------------------------------------------------------------------


def test_parse_version_extracts_semver():
    assert _parse_version("gcc (GCC) 14.2.0") == (14, 2, 0)
    assert _parse_version("lcov: LCOV version 2.0.1") == (2, 0, 1)
    assert _parse_version("no version here") is None


def test_get_tool_version_success():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "gcc (GCC) 14.2.0"
    with patch(
        "skyforge_engine.dal.gcov_collector.subprocess.run", return_value=mock_result
    ):
        assert _get_tool_version("gcc") == (14, 2, 0)


def test_get_tool_version_failure():
    mock_result = MagicMock()
    mock_result.returncode = 1
    with patch(
        "skyforge_engine.dal.gcov_collector.subprocess.run", return_value=mock_result
    ):
        assert _get_tool_version("gcc") is None


# ---------------------------------------------------------------------------
# GCC / lcov 查找与版本检测
# ---------------------------------------------------------------------------


def test_find_gcc_missing():
    with patch("skyforge_engine.dal.gcov_collector.shutil.which", return_value=None):
        assert _find_gcc() is None


def test_find_gcc_version_too_old():
    with patch(
        "skyforge_engine.dal.gcov_collector.shutil.which", return_value="/usr/bin/gcc"
    ), patch(
        "skyforge_engine.dal.gcov_collector._get_tool_version", return_value=(13, 2, 0)
    ):
        assert _find_gcc() is None


def test_find_gcc_version_exact():
    with patch(
        "skyforge_engine.dal.gcov_collector.shutil.which", return_value="/usr/bin/gcc"
    ), patch(
        "skyforge_engine.dal.gcov_collector._get_tool_version", return_value=(14, 2, 0)
    ):
        assert _find_gcc() == "/usr/bin/gcc"


def test_find_gcc_version_newer():
    with patch(
        "skyforge_engine.dal.gcov_collector.shutil.which", return_value="/usr/bin/gcc"
    ), patch(
        "skyforge_engine.dal.gcov_collector._get_tool_version", return_value=(15, 0, 0)
    ):
        assert _find_gcc() == "/usr/bin/gcc"


def test_find_lcov_missing():
    with patch("skyforge_engine.dal.gcov_collector.shutil.which", return_value=None):
        assert _find_lcov() is None


def test_find_lcov_version_too_old():
    with patch(
        "skyforge_engine.dal.gcov_collector.shutil.which", return_value="/usr/bin/lcov"
    ), patch(
        "skyforge_engine.dal.gcov_collector._get_tool_version", return_value=(1, 16, 0)
    ), patch(
        "skyforge_engine.dal.gcov_collector.os.name", "posix"
    ):
        assert _find_lcov() is None


def test_find_lcov_version_exact():
    with patch(
        "skyforge_engine.dal.gcov_collector.shutil.which", return_value="/usr/bin/lcov"
    ), patch(
        "skyforge_engine.dal.gcov_collector._get_tool_version", return_value=(2, 0, 0)
    ), patch(
        "skyforge_engine.dal.gcov_collector.os.name", "posix"
    ):
        assert _find_lcov() == "/usr/bin/lcov"


# ---------------------------------------------------------------------------
# _is_real_enabled
# ---------------------------------------------------------------------------


def test_is_real_enabled_default():
    with patch.dict("os.environ", {}, clear=True):
        assert _is_real_enabled() is True


def test_is_real_enabled_explicit_false():
    with patch.dict("os.environ", {"USE_REAL_COVERAGE": "false"}):
        assert _is_real_enabled() is False


def test_is_real_enabled_explicit_true():
    with patch.dict("os.environ", {"USE_REAL_COVERAGE": "true"}):
        assert _is_real_enabled() is True


# ---------------------------------------------------------------------------
# collect_coverage 严格模式异常
# ---------------------------------------------------------------------------


def test_collect_coverage_raises_when_disabled():
    with patch.dict("os.environ", {"USE_REAL_COVERAGE": "false"}):
        with pytest.raises(ToolNotFoundError, match="显式禁用"):
            collect_coverage("int main() { return 0; }")


def test_collect_coverage_raises_when_gcc_missing():
    with patch.dict("os.environ", {"USE_REAL_COVERAGE": "true"}, clear=True), patch(
        "skyforge_engine.dal.gcov_collector._find_gcc", return_value=None
    ), patch(
        "skyforge_engine.dal.gcov_collector._find_lcov", return_value="/usr/bin/lcov"
    ):
        with pytest.raises(ToolNotFoundError, match="GCC"):
            collect_coverage("int main() { return 0; }")


def test_collect_coverage_raises_when_lcov_missing():
    with patch.dict("os.environ", {"USE_REAL_COVERAGE": "true"}, clear=True), patch(
        "skyforge_engine.dal.gcov_collector._find_gcc", return_value="/usr/bin/gcc"
    ), patch(
        "skyforge_engine.dal.gcov_collector._find_lcov", return_value=None
    ):
        with pytest.raises(ToolNotFoundError, match="lcov"):
            collect_coverage("int main() { return 0; }")


# ---------------------------------------------------------------------------
# _parse_lcov_info
# ---------------------------------------------------------------------------


def test_parse_lcov_info_basic():
    content = """TN:
SF:test.c
FN:1,main
FNDA:1,main
FNF:1
FNH:1
DA:1,1
LF:1
LH:1
BRF:2
BRH:1
MCDC:10,2,t,1,0,a
MCDC:10,2,f,1,0,a
end_of_record
"""
    result = _parse_lcov_info(content)
    assert result["lines_total"] == 1
    assert result["lines_executed"] == 1
    assert result["branches_total"] == 2
    assert result["branches_taken"] == 1
    assert result["conditions_total"] == 1
    assert result["conditions_covered"] == 1


def test_parse_lcov_info_empty():
    result = _parse_lcov_info("")
    assert result["lines_total"] == 0
    assert result["conditions_total"] == 0


# ---------------------------------------------------------------------------
# 集成：模拟完整成功流程
# ---------------------------------------------------------------------------


def test_collect_coverage_success_with_mocked_tools(tmp_path):
    """模拟完整流程：编译、执行、gcov JSON 收集均成功。"""
    import json, gzip

    code = "int main(void) { return 0; }"

    # 创建 mock gcov JSON gz 文件
    gcov_data = {
        "format_version": "2",
        "gcc_version": "16.1.0",
        "files": [{
            "file": "test.c",
            "lines": [
                {"line_number": 1, "count": 1, "unexecuted_block": False,
                 "branches": [], "conditions": []}
            ],
            "functions": [{"name": "main", "start_line": 1}]
        }]
    }
    json_gz = tmp_path / "test_harness.c.gcov.json.gz"
    with gzip.open(json_gz, "wt", encoding="utf-8") as gf:
        json.dump(gcov_data, gf)

    mock_compile = MagicMock()
    mock_compile.returncode = 0
    mock_compile.stderr = ""

    mock_run = MagicMock()
    mock_run.returncode = 0

    mock_gcov = MagicMock()
    mock_gcov.returncode = 0
    mock_gcov.stderr = ""
    mock_gcov.stdout = ""

    import skyforge_engine.dal.gcov_collector as gcov_mod

    with patch.object(gcov_mod, "_find_gcc", return_value="/usr/bin/gcc"), patch.object(
        gcov_mod, "_find_lcov", return_value="/usr/bin/lcov"
    ), patch.object(
        gcov_mod.subprocess, "run", side_effect=[mock_compile, mock_run, mock_gcov]
    ), patch.object(
        gcov_mod.tempfile, "TemporaryDirectory"
    ) as mock_tmpdir:

        class _FakeTmp:
            def __enter__(self):
                return str(tmp_path)

            def __exit__(self, *args):
                return None

        mock_tmpdir.return_value = _FakeTmp()

        result = collect_coverage(code)

    assert isinstance(result, GcovCoverageResult)
    assert result.method == "gcov"
    assert result.tool_available is True
    assert result.lines_executed == 1
    assert result.lines_total == 1
