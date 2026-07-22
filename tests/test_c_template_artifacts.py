from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_c_template_and_standalone_test_exist():
    source = ROOT / "templates" / "c" / "safety_filter.c"
    header = ROOT / "templates" / "c" / "safety_filter.h"
    test_source = ROOT / "tests" / "c" / "test_safety_filter.c"

    assert source.exists()
    assert header.exists()
    assert test_source.exists()


def test_c_template_contains_traceability_and_contract_guard():
    source = (ROOT / "templates" / "c" / "safety_filter.c").read_text(encoding="utf-8")

    assert "[REQ-C-001]" in source
    assert "[CON-C-001]" in source
    assert "skyforge_contract_guard_safety_filter" in source
    assert "SKYFORGE_INPUT_MIN" in source
    assert "SKYFORGE_OUTPUT_MAX" in source


def test_c_standalone_test_exercises_fault_path():
    test_source = (ROOT / "tests" / "c" / "test_safety_filter.c").read_text(encoding="utf-8")

    assert "test_out_of_range_input_sets_fault" in test_source
    assert "skyforge_safety_filter_step(&filter, 25000.0)" in test_source
    assert "assert(skyforge_safety_filter_faulted(&filter) == true)" in test_source
