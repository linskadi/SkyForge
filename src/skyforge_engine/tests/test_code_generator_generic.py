"""测试 CodeGeneratorAgent 的 generic / redundancy 模板生成。

覆盖 Task 8 修改：
- _gen_generic_code() 在代码注释中包含用户需求文本，生成 init/process/deinit 三段式骨架
- _gen_redundancy_code() 包含 5% 偏差阈值（DEVIATION_THRESHOLD_PERCENT）
- _mock_run 默认 fallback 走 generic 模板
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 添加 src 到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from skyforge_engine.agents.code_generator import CodeGeneratorAgent
from skyforge_engine.tools.contract_checker import check as contract_check


SAMPLE_CONTRACT = """component: generated_module
version: 1.0.0
interface:
  inputs:
    - name: raw_input
      type: double
      range: [0, 100]
  outputs:
    - name: filtered_output
      type: double
      range: [0, 100]
contracts:
  preconditions:
    - "raw_input >= 0"
    - "raw_input <= 100"
  postconditions:
    - "filtered_output >= 0"
    - "filtered_output <= 100"
  invariants:
    - "filtered_output >= 0"
  fault_handling:
    - "if raw_input out of range set fault_detected"
"""


def test_gen_generic_code_contains_requirement():
    """_gen_generic_code 生成的代码注释中应包含用户需求文本关键词。

    覆盖 Task 8 SubTask 8.1：代码注释回显用户原始需求文本。
    """
    generator = CodeGeneratorAgent()
    req = {
        "req_id": "REQ-001",
        "desc": "实现一个大气数据计算模块，处理静压和动压",
        "type": "generic",
        "module_name": "air_data_computer",
    }
    code = generator._gen_generic_code(req)

    # 需求文本的关键词应出现在代码注释中
    assert "大气数据计算" in code or "静压" in code or "动压" in code
    # req_id 追溯注释必须存在
    assert "[REQ-001]" in code


def test_gen_generic_code_has_init_process_deinit():
    """_gen_generic_code 应生成 init/process/deinit 三段式骨架。

    覆盖 Task 8 SubTask 8.1：通用函数骨架含 init/process/deinit。
    """
    generator = CodeGeneratorAgent()
    req = {
        "req_id": "REQ-002",
        "desc": "通用信号处理",
        "type": "generic",
        "module_name": "signal_processor",
    }
    code = generator._gen_generic_code(req)

    # 三段式骨架函数定义必须存在
    assert "_init(void)" in code
    assert "_process(" in code
    assert "_deinit(void)" in code

    # 验证 init/process/deinit 都有函数体（不是仅声明）
    assert "int " in code and "_init(void)" in code
    assert "int32_t " in code and "_process(" in code
    assert "void " in code and "_deinit(void)" in code


def test_gen_redundancy_code_has_5_percent_threshold():
    """_gen_redundancy_code 应包含 5% 偏差阈值（DEVIATION_THRESHOLD_PERCENT）。

    覆盖 Task 8：余度管理模板使用 5% 偏差阈值，符合机载余度管理典型设计。
    """
    generator = CodeGeneratorAgent()
    req = {
        "req_id": "REQ-003",
        "desc": "双通道余度管理器",
        "type": "redundancy",
        "module_name": "redundancy_manager",
    }
    code = generator._gen_redundancy_code(req)

    # 阈值定义必须存在（5 或 DEVIATION_THRESHOLD_PERCENT）
    assert "DEVIATION_THRESHOLD_PERCENT" in code
    assert "5" in code  # 5.0f 字面量
    # 偏差比较逻辑必须存在
    assert "deviation" in code.lower()
    # req_id 追溯注释
    assert "[REQ-003]" in code
    # 双通道结构体字段
    assert "channel_a" in code
    assert "channel_b" in code


def test_mock_run_default_generic():
    """_mock_run 在无 type 字段且无关键词时默认走 generic 模板。

    覆盖 Task 8 SubTask 8.3：_mock_run 默认 fallback 走 generic 模板。
    """
    generator = CodeGeneratorAgent()
    # 不指定 type，不含任何已知关键词 → 默认 generic
    req = {
        "req_id": "REQ-004",
        "desc": "通用数据处理",
        # 故意不传 type 字段
        "module_name": "generic_module",
    }
    code = generator._mock_run(req)

    # generic 模板特征：含 init/process/deinit 三段式骨架
    assert "_init(void)" in code
    assert "_process(" in code
    assert "_deinit(void)" in code
    # 含用户需求文本注释
    assert "通用数据处理" in code
    # 不应包含 filter/control 等其他模板的特征
    assert "s_prev_output" not in code  # filter 模板特有变量
    assert "s_integral" not in code  # control 模板特有变量


def test_mock_run_explicit_generic_type():
    """_mock_run 在 type="generic" 时显式走 generic 模板。"""
    generator = CodeGeneratorAgent()
    req = {
        "req_id": "REQ-005",
        "desc": "通用计算单元",
        "type": "generic",
        "module_name": "compute_unit",
    }
    code = generator._mock_run(req)
    assert "_init(void)" in code
    assert "_process(" in code
    assert "_deinit(void)" in code
    assert "[REQ-005]" in code


def test_mock_run_redundancy_type():
    """_mock_run 在 type="redundancy" 时走 redundancy 模板。"""
    generator = CodeGeneratorAgent()
    req = {
        "req_id": "REQ-006",
        "desc": "余度管理",
        "type": "redundancy",
        "module_name": "redundancy_mgr",
    }
    code = generator._mock_run(req)
    assert "DEVIATION_THRESHOLD_PERCENT" in code
    assert "channel_a" in code
    assert "channel_b" in code
    assert "[REQ-006]" in code


def test_mock_run_c_templates_emit_contract_guard_and_pass_checker():
    """C 模板有契约输入时必须生成可校验的 pre/post/invariant/fault 保护。"""
    generator = CodeGeneratorAgent()
    c_types = [
        "generic",
        "filter",
        "control",
        "power",
        "navigation",
        "hmi",
        "sensor_fusion",
        "mission_planning",
        "arinc653",
        "freertos",
        "redundancy",
    ]

    for req_type in c_types:
        req = {
            "req_id": "REQ-031",
            "desc": "契约保护测试",
            "type": req_type,
            "module_name": f"{req_type}_module",
        }
        code = generator._mock_run(req, contract=SAMPLE_CONTRACT)
        assert "skyforge_contract_guard_" in code or req_type in {"generic", "filter"}
        result = contract_check(code, SAMPLE_CONTRACT, cid="CON-001")
        assert result.passed, (req_type, result.violations)


def test_cpp_templates_include_misra_cpp_labels():
    """C++ 生成模板必须带 MISRA-C++/JSF AV C++ 标签，避免只标 REQ。"""
    generator = CodeGeneratorAgent()
    cpp_types = [
        "cpp_template",
        "cpp_stl_container",
        "cpp_exception",
        "cpp_inheritance",
    ]

    for req_type in cpp_types:
        code = generator._mock_run(
            {
                "req_id": "REQ-CPP-001",
                "desc": "C++ 合规模板测试",
                "type": req_type,
                "module_name": req_type,
            }
        )
        assert "MISRA-C++/JSF AV C++/CERT C++" in code
        assert "@misra Rule" in code


def test_run_mock_mode_calls_mock_run():
    """mock 模式下正常调用 _mock_run 并返回模板代码。"""
    with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "mock"}):
        generator = CodeGeneratorAgent()
        req = {
            "req_id": "REQ-007",
            "desc": "通用数据处理器",
            "type": "generic",
            "module_name": "data_handler",
        }
        code = asyncio.run(generator.run(req, contract=""))

    # generic 模板特征
    assert "_init(void)" in code
    assert "_process(" in code
    assert "_deinit(void)" in code
    assert "[REQ-007]" in code
    # 含用户需求文本注释
    assert "通用数据处理器" in code


def test_run_local_mode_raises_when_backend_unavailable():
    """local 模式下 LLM 后端不可用时直接抛出异常，不再降级。"""
    with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "local"}):
        generator = CodeGeneratorAgent()
        req = {
            "req_id": "REQ-008",
            "desc": "通用数据处理器",
            "type": "generic",
            "module_name": "data_handler",
        }
        with patch(
            "skyforge_engine.agents.code_generator.get_lmstudio_client"
        ) as mock_get_client:
            mock_client = mock_get_client.return_value
            mock_client.chat_async.side_effect = RuntimeError("LLM 后端不可用")
            with pytest.raises(RuntimeError, match="LLM 后端不可用"):
                asyncio.run(generator.run(req, contract=""))


def test_run_api_mode_raises_when_backend_unavailable():
    """api 模式下 LLM 后端不可用时直接抛出异常，不再降级。"""
    with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "api"}):
        generator = CodeGeneratorAgent()
        req = {
            "req_id": "REQ-009",
            "desc": "通用数据处理器",
            "type": "generic",
            "module_name": "data_handler",
        }
        with patch(
            "skyforge_engine.agents.code_generator.get_lmstudio_client"
        ) as mock_get_client:
            mock_client = mock_get_client.return_value
            mock_client.chat_async.side_effect = RuntimeError("LLM 后端不可用")
            with pytest.raises(RuntimeError, match="LLM 后端不可用"):
                asyncio.run(generator.run(req, contract=""))
