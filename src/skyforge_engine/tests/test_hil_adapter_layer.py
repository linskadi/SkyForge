"""测试 HIL 适配器分层实现 (Phase 5)。"""

import builtins
import struct
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest

from skyforge_engine.core.adapters import (
    HILAdapterFactory,
    QEMUAdapter,
    SerialHIL,
    VirtualMCUAdapter,
)
from skyforge_engine.core.protocols import HILAdapterProtocol


# ---------------------------------------------------------------------------
# 协议合规性
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """验证所有适配器均实现 HILAdapterProtocol。"""

    def test_serial_hil_implements_protocol(self):
        adapter = SerialHIL()
        assert isinstance(adapter, HILAdapterProtocol)
        assert adapter.adapter_type == "serial"

    def test_qemu_adapter_implements_protocol(self):
        adapter = QEMUAdapter()
        assert isinstance(adapter, HILAdapterProtocol)
        assert adapter.adapter_type == "qemu"

    def test_virtual_mcu_adapter_implements_protocol(self):
        adapter = VirtualMCUAdapter()
        assert isinstance(adapter, HILAdapterProtocol)
        assert adapter.adapter_type == "virtual_mcu"


# ---------------------------------------------------------------------------
# SerialHIL
# ---------------------------------------------------------------------------


class TestSerialHIL:
    """SerialHIL 测试。"""

    def test_is_available_without_pyserial(self):
        """pyserial 未安装时 is_available() 返回 False。"""
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "serial":
                raise ModuleNotFoundError("No module named 'serial'")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", fake_import):
            adapter = SerialHIL()
            assert adapter.is_available() is False

    def test_connect_failure_raises_runtime_error(self):
        """connect() 失败时应抛出 RuntimeError。"""
        adapter = SerialHIL({"serial_port": "COM99"})
        with patch.object(adapter._adapter, "connect", return_value=False):
            with pytest.raises(RuntimeError, match="串口连接失败"):
                adapter.connect()

    def test_connect_success(self):
        """connect() 成功时不应抛出异常。"""
        adapter = SerialHIL({"serial_port": "COM5"})
        with patch.object(adapter._adapter, "connect", return_value=True):
            adapter.connect()

    def test_disconnect_without_connect(self):
        """未连接时 disconnect() 应安全执行。"""
        adapter = SerialHIL()
        adapter.disconnect()

    def test_send_without_connect_raises(self):
        """未连接时 send() 应抛出 RuntimeError。"""
        adapter = SerialHIL()
        with pytest.raises(RuntimeError, match="未连接"):
            adapter.send(b"test")

    def test_receive_without_connect_raises(self):
        """未连接时 receive() 应抛出 RuntimeError。"""
        adapter = SerialHIL()
        with pytest.raises(RuntimeError, match="未连接"):
            adapter.receive()

    def test_send_and_receive(self):
        """连接后 send/receive 应正常工作。"""
        adapter = SerialHIL({"serial_port": "COM5"})
        fake_serial = MagicMock()
        fake_serial.is_open = True
        fake_serial.timeout = 1.0
        fake_serial.read.return_value = b"response"

        with patch.object(adapter._adapter, "connect", return_value=True):
            adapter.connect()
            adapter._adapter._serial = fake_serial
            adapter._adapter._connected = True

            adapter.send(b"hello")
            fake_serial.write.assert_called_once_with(b"hello")

            data = adapter.receive(timeout_ms=1000)
            assert data == b"response"


# ---------------------------------------------------------------------------
# QEMUAdapter
# ---------------------------------------------------------------------------


class TestQEMUAdapterLayer:
    """QEMUAdapter 分层测试。"""

    def test_is_available_without_qemu(self):
        """QEMU 未安装时 is_available() 返回 False。"""
        with patch(
            "skyforge_engine.core.adapters.hil_adapter.shutil.which",
            return_value=None,
        ):
            adapter = QEMUAdapter()
            assert adapter.is_available() is False

    def test_is_available_with_qemu(self):
        """QEMU 已安装时 is_available() 返回 True。"""
        with patch(
            "skyforge_engine.core.adapters.hil_adapter.shutil.which",
            return_value="/usr/bin/qemu-system-arm",
        ):
            adapter = QEMUAdapter()
            assert adapter.is_available() is True

    def test_connect_failure_raises_runtime_error(self):
        """connect() 失败时应抛出 RuntimeError。"""
        adapter = QEMUAdapter()
        with patch.object(adapter._adapter, "connect", return_value=False):
            with pytest.raises(RuntimeError, match="QEMU 进程启动失败"):
                adapter.connect()

    def test_disconnect_without_connect(self):
        """未连接时 disconnect() 应安全执行。"""
        adapter = QEMUAdapter()
        adapter.disconnect()

    def test_send_without_connect_raises(self):
        """未连接时 send() 应抛出 RuntimeError。"""
        adapter = QEMUAdapter()
        with pytest.raises(RuntimeError, match="未连接"):
            adapter.send(b"test")

    def test_receive_without_connect_raises(self):
        """未连接时 receive() 应抛出 RuntimeError。"""
        adapter = QEMUAdapter()
        with pytest.raises(RuntimeError, match="未连接"):
            adapter.receive()


# ---------------------------------------------------------------------------
# VirtualMCUAdapter
# ---------------------------------------------------------------------------


class TestVirtualMCUAdapter:
    """VirtualMCUAdapter 测试。"""

    def test_is_available(self):
        """虚拟 MCU 适配器始终可用。"""
        adapter = VirtualMCUAdapter()
        assert adapter.is_available() is True

    def test_connect_disconnect(self):
        """connect / disconnect 应正确管理状态。"""
        adapter = VirtualMCUAdapter()
        assert not adapter._connected
        adapter.connect()
        assert adapter._connected
        adapter.disconnect()
        assert not adapter._connected

    def test_send_without_connect_raises(self):
        """未连接时 send() 应抛出 RuntimeError。"""
        adapter = VirtualMCUAdapter()
        with pytest.raises(RuntimeError, match="未连接"):
            adapter.send(b"1.0,2.0")

    def test_receive_without_connect_raises(self):
        """未连接时 receive() 应抛出 RuntimeError。"""
        adapter = VirtualMCUAdapter()
        with pytest.raises(RuntimeError, match="未连接"):
            adapter.receive()

    def test_send_receive_binary(self):
        """二进制 float64 输入输出。"""
        adapter = VirtualMCUAdapter()
        adapter.connect()
        input_bytes = struct.pack("<3d", 1.0, 2.0, 3.0)
        adapter.send(input_bytes)
        output_bytes = adapter.receive()
        assert len(output_bytes) == 3 * 8
        outputs = struct.unpack("<3d", output_bytes)
        # mock 模式：一阶低通滤波 y = 0.9*y_prev + 0.1*x
        assert outputs[0] == pytest.approx(0.1)
        assert outputs[1] == pytest.approx(0.29)
        assert outputs[2] == pytest.approx(0.561)

    def test_send_receive_text(self):
        """文本 CSV 输入输出。"""
        adapter = VirtualMCUAdapter()
        adapter.connect()
        adapter.send(b"1.0,2.0,3.0")
        output_bytes = adapter.receive()
        outputs = struct.unpack("<3d", output_bytes)
        assert outputs[0] == pytest.approx(0.1)

    def test_receive_without_send(self):
        """未发送数据时 receive() 返回空字节。"""
        adapter = VirtualMCUAdapter()
        adapter.connect()
        assert adapter.receive() == b""


# ---------------------------------------------------------------------------
# 工厂类
# ---------------------------------------------------------------------------


class TestHILAdapterFactory:
    """HILAdapterFactory 测试。"""

    def test_create_serial(self):
        adapter = HILAdapterFactory.create("serial")
        assert isinstance(adapter, SerialHIL)

    def test_create_qemu(self):
        adapter = HILAdapterFactory.create("qemu")
        assert isinstance(adapter, QEMUAdapter)

    def test_create_virtual_mcu(self):
        adapter = HILAdapterFactory.create("virtual_mcu")
        assert isinstance(adapter, VirtualMCUAdapter)

    def test_create_unknown_raises(self):
        with pytest.raises(ValueError, match="不支持的适配器类型"):
            HILAdapterFactory.create("unknown")

    def test_list_types(self):
        types = HILAdapterFactory.list_types()
        assert sorted(types) == ["qemu", "serial", "virtual_mcu"]

    def test_register_custom_adapter(self):
        class CustomAdapter:
            def __init__(self, config=None):
                pass

            @property
            def adapter_type(self):
                return "custom"

            def is_available(self):
                return True

            def connect(self):
                pass

            def disconnect(self):
                pass

            def send(self, data):
                pass

            def receive(self, timeout_ms=5000):
                return b""

        HILAdapterFactory.register("custom", CustomAdapter)
        adapter = HILAdapterFactory.create("custom")
        assert isinstance(adapter, CustomAdapter)
        # 清理
        del HILAdapterFactory._registry["custom"]


# ---------------------------------------------------------------------------
# 向后兼容
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """验证旧导入路径仍然有效。"""

    def test_old_serial_hil_import(self):
        from skyforge_engine.digital_twin.serial_hil import SerialHILAdapter

        assert SerialHILAdapter is not None

    def test_old_qemu_adapter_import(self):
        from skyforge_engine.digital_twin.qemu_adapter import QEMUAdapter

        assert QEMUAdapter is not None

    def test_old_virtual_mcu_import(self):
        from skyforge_engine.digital_twin.virtual_mcu import VirtualMCU

        assert VirtualMCU is not None

    def test_old_base_import(self):
        from skyforge_engine.digital_twin.hil_adapter_base import HILAdapter, HILConfig

        assert HILAdapter is not None
        assert HILConfig is not None
