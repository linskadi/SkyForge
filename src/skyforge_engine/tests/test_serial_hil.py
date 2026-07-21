"""测试串口 UART HIL 适配器 SerialHILAdapter。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest
import struct

from skyforge_engine.digital_twin.hil_adapter_base import HILConfig, HILMode, HILResult
from skyforge_engine.digital_twin.serial_hil import SerialHILAdapter


# ---------------------------------------------------------------------------
# CRC 校验测试
# ---------------------------------------------------------------------------


class TestCrc16Ccitt:
    """CRC16-CCITT 计算测试。"""

    def test_crc_empty(self):
        """空数据 CRC 应为初始值与零字节运算后的结果。"""
        crc = SerialHILAdapter._crc16_ccitt(b"")
        assert crc == 0xFFFF

    def test_crc_known_vectors(self):
        """已知测试向量验证 CRC 正确性。"""
        # CRC16-CCITT (init=0xFFFF, poly=0x1021) 标准测试向量
        assert SerialHILAdapter._crc16_ccitt(b"123456789") == 0x29B1
        assert SerialHILAdapter._crc16_ccitt(b"A") == 0xB915
        assert SerialHILAdapter._crc16_ccitt(b"\x00") == 0xE1F0

    def test_crc_over_frame_header(self):
        """对典型帧头计算 CRC 并验证可检出单比特错误。"""
        data = bytes([0xAA, 0x55, 0x01, 0x02, 0x00, 0x04])
        crc = SerialHILAdapter._crc16_ccitt(data)
        # 篡改 1 bit
        corrupted = bytearray(data)
        corrupted[0] ^= 0x01
        crc_corrupted = SerialHILAdapter._crc16_ccitt(bytes(corrupted))
        assert crc != crc_corrupted


# ---------------------------------------------------------------------------
# 帧编码测试
# ---------------------------------------------------------------------------


class TestFrameEncoding:
    """帧构造与解析测试。"""

    def test_build_frame_basic(self):
        """构造一帧并验证各字段位置。"""
        adapter = SerialHILAdapter(HILConfig())
        frame = adapter._build_frame(seq=0x03, cmd=0x02, data=b"\x01\x02\x03\x04")

        # HEAD
        assert frame[0:2] == bytes([0xAA, 0x55])
        # SEQ
        assert frame[2] == 0x03
        # CMD
        assert frame[3] == 0x02
        # LEN (大端)
        assert struct.unpack(">H", frame[4:6])[0] == 4
        # DATA
        assert frame[6:10] == b"\x01\x02\x03\x04"
        # CRC (2 bytes)
        assert len(frame) == 12

        # 校验 CRC 正确性
        payload = frame[:-2]
        recv_crc = struct.unpack(">H", frame[-2:])[0]
        assert SerialHILAdapter._crc16_ccitt(payload) == recv_crc

    def test_build_frame_empty_data(self):
        """构造数据域为空的一帧。"""
        adapter = SerialHILAdapter(HILConfig())
        frame = adapter._build_frame(seq=0x01, cmd=0x0F, data=b"")
        assert len(frame) == 8  # HEAD(2)+SEQ+CMD+LEN(2)+CRC(2)
        assert struct.unpack(">H", frame[4:6])[0] == 0

    def test_build_frame_too_long(self):
        """数据长度超过 65535 时应抛出 ValueError。"""
        adapter = SerialHILAdapter(HILConfig())
        with pytest.raises(ValueError, match="too long"):
            adapter._build_frame(seq=0x01, cmd=0x02, data=b"x" * 65536)

    def test_read_frame_success(self):
        """_read_frame 成功解析一帧。"""
        adapter = SerialHILAdapter(HILConfig())
        # 预构造一帧
        frame = adapter._build_frame(seq=0x05, cmd=0x03, data=b"\xDE\xAD")

        class FakeSerial:
            def __init__(self, data):
                self._data = bytearray(data)
                self.timeout = 1.0
                self.is_open = True

            def read(self, n):
                chunk = bytes(self._data[:n])
                del self._data[:n]
                return chunk

        adapter._serial = FakeSerial(frame)
        result = adapter._read_frame(timeout=1.0)

        assert result is not None
        assert result["seq"] == 0x05
        assert result["cmd"] == 0x03
        assert result["len"] == 2
        assert result["data"] == b"\xDE\xAD"
        assert result["crc_ok"] is True

    def test_read_frame_crc_mismatch(self):
        """CRC 错误时 crc_ok 应为 False。"""
        adapter = SerialHILAdapter(HILConfig())
        frame = adapter._build_frame(seq=0x01, cmd=0x02, data=b"\x00")
        # 篡改 CRC 最后一个字节
        corrupted = bytearray(frame)
        corrupted[-1] ^= 0xFF

        class FakeSerial:
            def __init__(self, data):
                self._data = bytearray(data)
                self.timeout = 1.0
                self.is_open = True

            def read(self, n):
                chunk = bytes(self._data[:n])
                del self._data[:n]
                return chunk

        adapter._serial = FakeSerial(bytes(corrupted))
        result = adapter._read_frame(timeout=1.0)
        assert result is not None
        assert result["crc_ok"] is False

    def test_read_frame_timeout(self):
        """串口无数据时应返回 None。"""
        adapter = SerialHILAdapter(HILConfig())

        class FakeSerial:
            def __init__(self):
                self.timeout = 1.0
                self.is_open = True

            def read(self, n):
                return b""

        adapter._serial = FakeSerial()
        result = adapter._read_frame(timeout=1.0)
        assert result is None


# ---------------------------------------------------------------------------
# 串口连接测试（mock serial.Serial）
# ---------------------------------------------------------------------------


class TestSerialConnection:
    """串口连接/断开测试。"""

    @patch("skyforge_engine.digital_twin.serial_hil.serial")
    def test_connect_success(self, mock_serial_mod):
        """串口成功打开时 connect() 返回 True。"""
        mock_inst = MagicMock()
        mock_inst.is_open = True
        mock_serial_mod.Serial.return_value = mock_inst

        config = HILConfig(mode=HILMode.SERIAL, serial_port="COM5", baud_rate=9600)
        adapter = SerialHILAdapter(config)
        assert adapter.connect() is True
        assert adapter._connected is True
        mock_serial_mod.Serial.assert_called_once_with(
            port="COM5",
            baudrate=9600,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=5.0,
        )

    @patch("skyforge_engine.digital_twin.serial_hil.serial")
    def test_connect_failure(self, mock_serial_mod):
        """串口打开异常时 connect() 返回 False。"""
        mock_serial_mod.Serial.side_effect = Exception("Port not found")

        adapter = SerialHILAdapter(HILConfig())
        assert adapter.connect() is False
        assert adapter._connected is False

    @patch("skyforge_engine.digital_twin.serial_hil.serial", None)
    def test_connect_import_error(self):
        """pyserial 未安装时 connect() 返回 False。"""
        adapter = SerialHILAdapter(HILConfig())
        assert adapter.connect() is False

    @patch("skyforge_engine.digital_twin.serial_hil.serial")
    def test_disconnect_success(self, mock_serial_mod):
        """disconnect() 正常关闭串口。"""
        mock_inst = MagicMock()
        mock_inst.is_open = True
        mock_serial_mod.Serial.return_value = mock_inst

        adapter = SerialHILAdapter(HILConfig())
        adapter.connect()
        assert adapter.disconnect() is True
        assert adapter._connected is False
        mock_inst.close.assert_called_once()

    def test_disconnect_without_connect(self):
        """未连接时调用 disconnect() 应安全返回 True。"""
        adapter = SerialHILAdapter(HILConfig())
        assert adapter.disconnect() is True


# ---------------------------------------------------------------------------
# flash / run 行为测试
# ---------------------------------------------------------------------------


class TestFlashAndRun:
    """flash 与 run 方法行为测试。"""

    def test_flash_returns_error(self):
        """flash() 应返回不支持烧录的 HILResult。"""
        adapter = SerialHILAdapter(HILConfig())
        result = adapter.flash("firmware.elf")
        assert isinstance(result, HILResult)
        assert result.status == "error"
        assert "does not support direct flashing" in result.message

    def test_run_not_connected(self):
        """未连接时 run() 应返回错误结果。"""
        adapter = SerialHILAdapter(HILConfig())
        result = adapter.run([1.0, 2.0])
        assert result.status == "error"
        assert "not connected" in result.message

    @patch("skyforge_engine.digital_twin.serial_hil.serial")
    def test_run_full_flow(self, mock_serial_mod):
        """run() 完整流程：RESET -> INPUT -> ACK -> GET_OUTPUT -> 解析波形。"""
        adapter = SerialHILAdapter(HILConfig(serial_timeout=1.0))

        # 预构造设备端返回的三帧：RESET 响应、ACK、GET_OUTPUT 响应
        reset_resp = adapter._build_frame(seq=1, cmd=SerialHILAdapter.CMD_ACK, data=b"")
        ack_resp = adapter._build_frame(seq=2, cmd=SerialHILAdapter.CMD_ACK, data=b"")
        # 输出波形：两个 float32 [3.14, 2.718]
        output_bytes = struct.pack("<2f", 3.14, 2.718)
        get_output_resp = adapter._build_frame(
            seq=3, cmd=SerialHILAdapter.CMD_GET_OUTPUT, data=output_bytes
        )

        response_stream = reset_resp + ack_resp + get_output_resp

        class FakeSerial:
            def __init__(self, data):
                self._data = bytearray(data)
                self.timeout = 1.0
                self.is_open = True

            def read(self, n):
                chunk = bytes(self._data[:n])
                del self._data[:n]
                return chunk

            def write(self, data):
                pass

            def reset_input_buffer(self):
                pass

            def close(self):
                self.is_open = False

        mock_serial_mod.Serial.return_value = FakeSerial(response_stream)

        adapter.connect()
        result = adapter.run([1.0, 2.0])

        assert result.status == "success"
        assert result.output_waveform is not None
        assert len(result.output_waveform) == 2
        assert abs(result.output_waveform[0] - 3.14) < 1e-4
        assert abs(result.output_waveform[1] - 2.718) < 1e-4

        adapter.disconnect()

    @patch("skyforge_engine.digital_twin.serial_hil.serial")
    def test_run_no_ack(self, mock_serial_mod):
        """run() 在 INPUT 后未收到 ACK 应返回错误。"""
        adapter = SerialHILAdapter(HILConfig(serial_timeout=1.0))

        # 只返回 RESET 响应，然后超时
        reset_resp = adapter._build_frame(seq=1, cmd=SerialHILAdapter.CMD_ACK, data=b"")

        class FakeSerial:
            def __init__(self, data):
                self._data = bytearray(data)
                self.timeout = 1.0
                self.is_open = True

            def read(self, n):
                chunk = bytes(self._data[:n])
                del self._data[:n]
                return chunk

            def write(self, data):
                pass

            def reset_input_buffer(self):
                pass

            def close(self):
                self.is_open = False

        mock_serial_mod.Serial.return_value = FakeSerial(reset_resp)

        adapter.connect()
        result = adapter.run([1.0])
        assert result.status == "error"
        assert "ACK not received" in result.message

    @patch("skyforge_engine.digital_twin.serial_hil.serial")
    def test_run_text_output_fallback(self, mock_serial_mod):
        """GET_OUTPUT 返回非 4 字节倍数时回退到文本 CSV 解析。"""
        adapter = SerialHILAdapter(HILConfig(serial_timeout=1.0))

        reset_resp = adapter._build_frame(seq=1, cmd=SerialHILAdapter.CMD_ACK, data=b"")
        ack_resp = adapter._build_frame(seq=2, cmd=SerialHILAdapter.CMD_ACK, data=b"")
        # 长度 9，不是 4 的倍数，触发 CSV 回退
        text_data = b"1.5,2.5,3.5"
        get_resp = adapter._build_frame(
            seq=3, cmd=SerialHILAdapter.CMD_GET_OUTPUT, data=text_data
        )

        stream = reset_resp + ack_resp + get_resp

        class FakeSerial:
            def __init__(self, data):
                self._data = bytearray(data)
                self.timeout = 1.0
                self.is_open = True

            def read(self, n):
                chunk = bytes(self._data[:n])
                del self._data[:n]
                return chunk

            def write(self, data):
                pass

            def reset_input_buffer(self):
                pass

            def close(self):
                self.is_open = False

        mock_serial_mod.Serial.return_value = FakeSerial(stream)

        adapter.connect()
        result = adapter.run([1.0])
        assert result.status == "success"
        assert result.output_waveform == [1.5, 2.5, 3.5]


# ---------------------------------------------------------------------------
# 数据编解码测试
# ---------------------------------------------------------------------------


class TestDataEncoding:
    """输入/输出数据编解码测试。"""

    def test_encode_list_of_floats(self):
        """list[float] 编码为 4 字节小端 float 数组。"""
        data = SerialHILAdapter._encode_input_vector([1.0, 2.5, -3.14])
        assert len(data) == 12
        assert struct.unpack("<3f", data) == pytest.approx((1.0, 2.5, -3.14))

    def test_encode_list_of_ints(self):
        """list[int] 自动转为 float 编码。"""
        data = SerialHILAdapter._encode_input_vector([1, 2, 3])
        assert struct.unpack("<3f", data) == pytest.approx((1.0, 2.0, 3.0))

    def test_encode_none(self):
        """None 编码为空字节。"""
        assert SerialHILAdapter._encode_input_vector(None) == b""

    def test_encode_bytes(self):
        """bytes 直接透传。"""
        raw = b"\xAB\xCD"
        assert SerialHILAdapter._encode_input_vector(raw) == raw

    def test_parse_binary_floats(self):
        """4 字节倍数数据解析为 float 列表。"""
        raw = struct.pack("<4f", 0.1, 0.2, 0.3, 0.4)
        waveform = SerialHILAdapter._parse_output_data(raw)
        assert waveform == pytest.approx([0.1, 0.2, 0.3, 0.4])

    def test_parse_empty(self):
        """空数据返回空列表。"""
        assert SerialHILAdapter._parse_output_data(b"") == []

    def test_parse_csv_text(self):
        """非 4 字节倍数时回退 CSV 文本解析。"""
        # 长度 7，不是 4 的倍数，触发 CSV 回退
        waveform = SerialHILAdapter._parse_output_data(b"10,20,3")
        assert waveform == [10.0, 20.0, 3.0]

    def test_parse_invalid_fallback(self):
        """回退解析失败时返回 None。"""
        assert SerialHILAdapter._parse_output_data(b"abc") is None
