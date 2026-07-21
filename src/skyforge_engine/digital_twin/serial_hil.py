# -*- coding: utf-8 -*-
"""串口 UART HIL 适配器。

继承自 HILAdapter 基类，实现基于 UART 的硬件在环通信协议：
- 帧格式：HEAD(0xAA 0x55) + SEQ + CMD + LEN(2B) + DATA + CRC16
- 命令码：INIT(0x01), INPUT(0x02), GET_OUTPUT(0x03), RESET(0x04), ACK(0x0F)
- CRC16-CCITT 校验（多项式 0x1021，初始值 0xFFFF）
"""

from __future__ import annotations

import struct
from typing import Any, Optional

from skyforge_engine.digital_twin.hil_adapter_base import (
    HILAdapter,
    HILConfig,
    HILResult,
)
from skyforge_engine.utils.log_util import logger

import types

try:
    import serial
except ImportError:  # pragma: no cover
    serial = types.ModuleType("serial")


class SerialHILAdapter(HILAdapter):
    """串口 UART HIL 适配器。"""

    # 帧常量
    HEAD = bytes([0xAA, 0x55])
    CMD_INIT = 0x01
    CMD_INPUT = 0x02
    CMD_GET_OUTPUT = 0x03
    CMD_RESET = 0x04
    CMD_ACK = 0x0F

    # CRC16-CCITT 参数
    CRC16_POLY = 0x1021
    CRC16_INIT = 0xFFFF

    def __init__(self, config: HILConfig) -> None:
        super().__init__(config)
        self._serial: Any = None
        self._seq: int = 0

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """打开串口连接。"""
        if getattr(serial, "Serial", None) is None:
            logger.error("SerialHIL: pyserial 未安装")
            return False
        try:
            self._serial = serial.Serial(
                port=self.config.serial_port,
                baudrate=self.config.baud_rate,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=self.config.serial_timeout,
            )
            if self._serial.is_open:
                self._connected = True
                self._seq = 0
                logger.info(
                    f"SerialHIL: 串口已连接 {self.config.serial_port} @ {self.config.baud_rate}"
                )
                return True
        except Exception as e:
            logger.error(f"SerialHIL: 串口连接失败 — {e}")
        self._connected = False
        return False

    def flash(self, firmware_path: str) -> HILResult:
        """串口模式不支持直接烧录固件。"""
        logger.warning("SerialHIL: 串口模式不支持直接烧录")
        return HILResult(
            status="error",
            message="serial mode does not support direct flashing",
            method="flash",
        )

    def run(self, input_vector: Any) -> HILResult:
        """运行输入向量并采集输出波形。

        流程：
        1. 发送 RESET 命令
        2. 发送 INPUT 命令（携带输入向量）
        3. 等待 ACK
        4. 发送 GET_OUTPUT 命令
        5. 接收响应帧并解析输出波形
        """
        if not self._connected or self._serial is None:
            return HILResult(
                status="error", message="serial port not connected", method="run"
            )

        try:
            # 1. RESET
            self._send_frame(self.CMD_RESET, b"")
            resp = self._read_frame(timeout=self.config.serial_timeout)
            if resp is None:
                return HILResult(
                    status="timeout", message="no response to RESET", method="run"
                )

            # 2. INPUT
            input_data = self._encode_input_vector(input_vector)
            self._send_frame(self.CMD_INPUT, input_data)

            # 3. 等待 ACK
            ack = self._read_frame(timeout=self.config.serial_timeout)
            if ack is None or ack["cmd"] != self.CMD_ACK:
                return HILResult(
                    status="error", message="ACK not received after INPUT", method="run"
                )

            # 4. GET_OUTPUT
            self._send_frame(self.CMD_GET_OUTPUT, b"")

            # 5. 接收输出
            out_resp = self._read_frame(timeout=self.config.serial_timeout)
            if out_resp is None:
                return HILResult(
                    status="timeout",
                    message="no response to GET_OUTPUT",
                    method="run",
                )

            waveform = self._parse_output_data(out_resp["data"])
            return HILResult(
                status="success",
                output_waveform=waveform,
                method="run",
            )

        except Exception as e:
            logger.exception("SerialHIL: run 异常")
            return HILResult(status="error", message=str(e), method="run")

    def disconnect(self) -> bool:
        """关闭串口连接。"""
        if self._serial is not None:
            try:
                if self._serial.is_open:
                    self._serial.close()
                    logger.info(f"SerialHIL: 串口已断开 {self.config.serial_port}")
            except Exception as e:
                logger.warning(f"SerialHIL: 断开异常 — {e}")
        self._connected = False
        self._serial = None
        return True

    # ------------------------------------------------------------------
    # 帧编码 / 解码
    # ------------------------------------------------------------------

    def _build_frame(self, seq: int, cmd: int, data: bytes) -> bytes:
        """构造一帧数据（不含 HEAD 的 CRC 计算从 HEAD 开始）。"""
        length = len(data)
        if length > 0xFFFF:
            raise ValueError(f"data too long: {length} bytes (max 65535)")

        header = self.HEAD + bytes([seq, cmd]) + struct.pack(">H", length)
        payload = header + data
        crc = self._crc16_ccitt(payload)
        return payload + struct.pack(">H", crc)

    def _send_frame(self, cmd: int, data: bytes) -> None:
        """发送一帧并递增序列号。"""
        self._seq = (self._seq + 1) & 0xFF
        frame = self._build_frame(self._seq, cmd, data)
        self._serial.write(frame)

    def _read_frame(self, timeout: float) -> Optional[dict[str, Any]]:
        """从串口读取并解析一帧。

        Returns:
            dict with keys: seq, cmd, len, data, crc_ok
            or None on timeout / parse failure.
        """
        if self._serial is None:
            return None

        original_timeout = self._serial.timeout
        try:
            self._serial.timeout = timeout

            # 查找帧头
            head_buf = bytearray()
            while True:
                b = self._serial.read(1)
                if not b:
                    return None
                head_buf.extend(b)
                if len(head_buf) > 2:
                    head_buf.pop(0)
                if bytes(head_buf) == self.HEAD:
                    break

            # 读取 SEQ + CMD + LEN(2)
            hdr = self._serial.read(4)
            if len(hdr) != 4:
                return None
            seq = hdr[0]
            cmd = hdr[1]
            length = struct.unpack(">H", hdr[2:4])[0]

            # 读取 DATA
            data = self._serial.read(length)
            if len(data) != length:
                return None

            # 读取 CRC
            crc_bytes = self._serial.read(2)
            if len(crc_bytes) != 2:
                return None
            recv_crc = struct.unpack(">H", crc_bytes)[0]

            # 校验
            payload = self.HEAD + hdr + data
            calc_crc = self._crc16_ccitt(payload)
            crc_ok = calc_crc == recv_crc

            return {
                "seq": seq,
                "cmd": cmd,
                "len": length,
                "data": data,
                "crc_ok": crc_ok,
            }
        finally:
            self._serial.timeout = original_timeout

    @classmethod
    def _crc16_ccitt(cls, data: bytes) -> int:
        """CRC16-CCITT 计算。

        多项式: x^16 + x^12 + x^5 + 1 (0x1021)
        初始值: 0xFFFF
        """
        crc = cls.CRC16_INIT
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ cls.CRC16_POLY) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
        return crc

    # ------------------------------------------------------------------
    # 数据序列化 / 反序列化
    # ------------------------------------------------------------------

    @staticmethod
    def _encode_input_vector(input_vector: Any) -> bytes:
        """将输入向量编码为字节。

        支持 list/tuple of int/float；每个 float 用 4 字节小端表示。
        """
        if input_vector is None:
            return b""
        if isinstance(input_vector, (list, tuple)):
            # 统一编码为 float32 数组
            values = [float(v) for v in input_vector]
            return struct.pack(f"<{len(values)}f", *values)
        if isinstance(input_vector, bytes):
            return input_vector
        # 其他类型转字符串再编码
        return str(input_vector).encode("utf-8")

    @staticmethod
    def _parse_output_data(data: bytes) -> Optional[list[float]]:
        """将响应数据解析为输出波形（float 列表）。

        假设数据为 4 字节小端 float 数组。
        """
        if not data:
            return []
        if len(data) % 4 != 0:
            # 尝试按 UTF-8 文本解析 CSV
            try:
                text = data.decode("utf-8", errors="replace")
                return [float(x) for x in text.strip().split(",") if x.strip()]
            except Exception:
                return None
        count = len(data) // 4
        return list(struct.unpack(f"<{count}f", data))
