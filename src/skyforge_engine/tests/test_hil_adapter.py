"""测试 HIL 适配器抽象基类。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest

from skyforge_engine.digital_twin.hil_adapter_base import (
    HILAdapter,
    HILConfig,
    HILMode,
    HILResult,
)


# ---------------------------------------------------------------------------
# 抽象基类约束
# ---------------------------------------------------------------------------


def test_base_class_is_abstract():
    """HILAdapter 不能直接实例化。"""
    config = HILConfig()
    with pytest.raises(TypeError):
        HILAdapter(config)


def test_subclass_must_implement_all_methods():
    """子类若缺少任一抽象方法，实例化时应抛出 TypeError。"""

    class PartialAdapter(HILAdapter):
        def connect(self):
            return True

        def flash(self, firmware_path):
            return HILResult()

        def run(self, input_vector):
            return HILResult()

        # 故意缺少 disconnect

    config = HILConfig()
    with pytest.raises(TypeError, match="disconnect"):
        PartialAdapter(config)


def test_subclass_with_all_methods_can_be_instantiated():
    """子类实现全部抽象方法后即可正常实例化。"""

    class DummyAdapter(HILAdapter):
        def connect(self):
            return True

        def flash(self, firmware_path):
            return HILResult(status="success", method="dummy_flash")

        def run(self, input_vector):
            return HILResult(status="success", method="dummy_run")

        def disconnect(self):
            return True

    config = HILConfig()
    adapter = DummyAdapter(config)
    assert adapter.config == config
    assert adapter._connected is False


# ---------------------------------------------------------------------------
# HILConfig 默认值
# ---------------------------------------------------------------------------


def test_hil_config_defaults():
    """HILConfig 在未传入参数时应具备预期的默认值。"""
    cfg = HILConfig()
    assert cfg.mode == HILMode.VIRTUAL
    assert cfg.serial_port == "COM3"
    assert cfg.baud_rate == 115200
    assert cfg.serial_timeout == 5.0
    assert cfg.jtag_device == "STLINK"
    assert cfg.jtag_target == "STM32F407"
    assert cfg.flash_timeout == 30.0
    assert cfg.run_timeout == 30.0
    assert cfg.connect_timeout == 10.0


def test_hil_config_override():
    """HILConfig 支持显式覆盖默认值。"""
    cfg = HILConfig(
        mode=HILMode.SERIAL,
        serial_port="/dev/ttyUSB0",
        baud_rate=9600,
        connect_timeout=5.0,
    )
    assert cfg.mode == HILMode.SERIAL
    assert cfg.serial_port == "/dev/ttyUSB0"
    assert cfg.baud_rate == 9600
    assert cfg.connect_timeout == 5.0
    # 未覆盖的字段保持默认
    assert cfg.jtag_target == "STM32F407"


# ---------------------------------------------------------------------------
# HILResult 基本行为
# ---------------------------------------------------------------------------


def test_hil_result_defaults():
    """HILResult 在未传入参数时应具备预期的默认值。"""
    result = HILResult()
    assert result.status == "success"
    assert result.output_waveform is None
    assert result.message == ""
    assert result.method == ""


def test_hil_result_custom_values():
    """HILResult 支持自定义字段值。"""
    result = HILResult(
        status="timeout",
        output_waveform=[0.0, 1.0, 2.0],
        message="connection lost",
        method="serial",
    )
    assert result.status == "timeout"
    assert result.output_waveform == [0.0, 1.0, 2.0]
    assert result.message == "connection lost"
    assert result.method == "serial"
