"""SkyForge HIL 适配器分层实现 (Phase 5)。

在核心协议层 (core/adapters) 提供 HILAdapterProtocol 的具体实现，
通过包装现有的 digital_twin 适配器，实现向后兼容的分层架构。
"""

from __future__ import annotations

import asyncio
import shutil
import struct
from typing import Any

import numpy as np

from skyforge_engine.core.protocols import HILAdapterProtocol
from skyforge_engine.digital_twin.hil_adapter_base import HILConfig, HILMode
from skyforge_engine.digital_twin.serial_hil import SerialHILAdapter as _SerialHILAdapter
from skyforge_engine.digital_twin.qemu_adapter import QEMUAdapter as _QEMUAdapter
from skyforge_engine.digital_twin.virtual_mcu import VirtualMCU


class SerialHIL:
    """串口 HIL 适配器 —— 实现 HILAdapterProtocol。"""

    @property
    def adapter_type(self) -> str:
        return "serial"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self._config = HILConfig(
            mode=HILMode.SERIAL,
            serial_port=cfg.get("serial_port", "COM3"),
            baud_rate=cfg.get("baud_rate", 115200),
            serial_timeout=cfg.get("serial_timeout", 5.0),
        )
        self._adapter = _SerialHILAdapter(self._config)

    def is_available(self) -> bool:
        """检查 pyserial 是否已安装。"""
        try:
            import serial as _  # noqa: F401
            return True
        except ImportError:
            return False

    def connect(self) -> None:
        """建立串口连接。

        Raises:
            RuntimeError: 连接失败时抛出。
        """
        result = self._adapter.connect()
        if not result:
            raise RuntimeError("SerialHIL: 串口连接失败")

    def disconnect(self) -> None:
        """断开串口连接并释放资源。"""
        self._adapter.disconnect()

    def send(self, data: bytes) -> None:
        """通过串口发送原始字节数据。

        Raises:
            RuntimeError: 未连接或发送失败时抛出。
        """
        if not self._adapter._connected or self._adapter._serial is None:
            raise RuntimeError("SerialHIL: 未连接")
        try:
            self._adapter._serial.write(data)
        except Exception as exc:
            raise RuntimeError(f"SerialHIL: 发送失败 — {exc}") from exc

    def receive(self, timeout_ms: int = 5000) -> bytes:
        """从串口接收原始字节数据。

        Args:
            timeout_ms: 超时时间（毫秒）。

        Returns:
            接收到的字节数据。

        Raises:
            RuntimeError: 未连接时抛出。
        """
        if not self._adapter._connected or self._adapter._serial is None:
            raise RuntimeError("SerialHIL: 未连接")
        original_timeout = self._adapter._serial.timeout
        try:
            self._adapter._serial.timeout = timeout_ms / 1000.0
            return self._adapter._serial.read(4096)
        except Exception as exc:
            raise RuntimeError(f"SerialHIL: 接收失败 — {exc}") from exc
        finally:
            self._adapter._serial.timeout = original_timeout


class QEMUAdapter:
    """QEMU HIL 适配器 —— 实现 HILAdapterProtocol。"""

    @property
    def adapter_type(self) -> str:
        return "qemu"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self._config = HILConfig(
            mode=HILMode.QEMU,
            jtag_target=cfg.get("jtag_target", "STM32F407"),
        )
        self._adapter = _QEMUAdapter(self._config)

    def is_available(self) -> bool:
        """检查 qemu-system-arm 是否在 PATH 中。"""
        return shutil.which("qemu-system-arm") is not None

    def connect(self) -> None:
        """启动 QEMU 进程。

        Raises:
            RuntimeError: 启动失败时抛出。
        """
        try:
            result = asyncio.run(self._adapter.connect())
        except Exception as exc:
            raise RuntimeError(f"QEMUAdapter: 连接失败 — {exc}") from exc
        if not result:
            raise RuntimeError("QEMUAdapter: QEMU 进程启动失败")

    def disconnect(self) -> None:
        """终止 QEMU 进程并释放资源。"""
        try:
            asyncio.run(self._adapter.disconnect())
        except Exception:
            pass

    def send(self, data: bytes) -> None:
        """向 QEMU 进程 stdin 发送数据。

        Raises:
            RuntimeError: 未连接或发送失败时抛出。
        """
        if (
            self._adapter._process is None
            or self._adapter._process.returncode is not None
        ):
            raise RuntimeError("QEMUAdapter: 未连接")
        try:
            if self._adapter._process.stdin and not self._adapter._process.stdin.is_closing():
                self._adapter._process.stdin.write(data)
                asyncio.run(self._adapter._process.stdin.drain())
        except Exception as exc:
            raise RuntimeError(f"QEMUAdapter: 发送失败 — {exc}") from exc

    def receive(self, timeout_ms: int = 5000) -> bytes:
        """从 QEMU 进程 stdout 接收数据。

        Args:
            timeout_ms: 超时时间（毫秒）。

        Returns:
            接收到的字节数据。

        Raises:
            RuntimeError: 未连接时抛出。
        """
        if (
            self._adapter._process is None
            or self._adapter._process.returncode is not None
        ):
            raise RuntimeError("QEMUAdapter: 未连接")
        if self._adapter._process.stdout is None:
            return b""
        try:
            data = asyncio.run(
                asyncio.wait_for(
                    self._adapter._process.stdout.read(4096),
                    timeout=timeout_ms / 1000.0,
                )
            )
            return data
        except asyncio.TimeoutError:
            return b""
        except Exception as exc:
            raise RuntimeError(f"QEMUAdapter: 接收失败 — {exc}") from exc


class VirtualMCUAdapter:
    """虚拟 MCU HIL 适配器 —— 实现 HILAdapterProtocol。"""

    @property
    def adapter_type(self) -> str:
        return "virtual_mcu"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._mcu = VirtualMCU(
            gcc_path=self._config.get("gcc_path", "gcc"),
            compile_timeout=self._config.get("compile_timeout", 10),
            use_real_gcc=self._config.get("use_real_gcc", False),
        )
        self._connected = False
        self._last_input: np.ndarray | None = None

    def is_available(self) -> bool:
        """虚拟 MCU 适配器始终可用（纯软件）。"""
        return True

    def connect(self) -> None:
        """建立虚拟连接。"""
        self._connected = True

    def disconnect(self) -> None:
        """断开虚拟连接并释放资源。"""
        self._connected = False
        self._last_input = None

    def send(self, data: bytes) -> None:
        """缓存输入数据。

        支持两种编码：
        - 8 字节倍数的二进制数据，按小端 float64 解析
        - 其他情况按 UTF-8 文本 CSV 解析

        Raises:
            RuntimeError: 未连接或解析失败时抛出。
        """
        if not self._connected:
            raise RuntimeError("VirtualMCUAdapter: 未连接")
        try:
            if len(data) % 8 == 0 and len(data) > 0:
                count = len(data) // 8
                values = struct.unpack(f"<{count}d", data)
                self._last_input = np.array(values, dtype=np.float64)
            else:
                text = data.decode("utf-8", errors="replace").strip()
                values = [float(x) for x in text.split(",") if x.strip()]
                if not values and len(data) > 0:
                    raise ValueError("无法将输入数据解析为数值")
                self._last_input = np.array(values, dtype=np.float64)
        except Exception as exc:
            raise RuntimeError(f"VirtualMCUAdapter: 输入数据解析失败 — {exc}") from exc

    def receive(self, timeout_ms: int = 5000) -> bytes:
        """运行 mock 滤波器并返回输出数据。

        Args:
            timeout_ms: 超时时间（毫秒，当前未使用）。

        Returns:
            小端 float64 编码的输出字节数据。

        Raises:
            RuntimeError: 未连接或运行失败时抛出。
        """
        if not self._connected:
            raise RuntimeError("VirtualMCUAdapter: 未连接")
        if self._last_input is None or len(self._last_input) == 0:
            return b""
        result = self._mcu._run_mock(self._last_input)
        if not result.success:
            raise RuntimeError("VirtualMCUAdapter: 运行失败")
        values = result.output_data.tolist()
        return struct.pack(f"<{len(values)}d", *values)


class HILAdapterFactory:
    """HIL 适配器工厂。

    根据配置字符串创建对应的 HILAdapterProtocol 实现。
    """

    _registry: dict[str, type] = {
        "serial": SerialHIL,
        "qemu": QEMUAdapter,
        "virtual_mcu": VirtualMCUAdapter,
    }

    @classmethod
    def create(
        cls, adapter_type: str, config: dict[str, Any] | None = None
    ) -> HILAdapterProtocol:
        """创建适配器实例。

        Args:
            adapter_type: 适配器类型标识（如 "serial", "qemu", "virtual_mcu"）。
            config: 可选的配置字典。

        Returns:
            适配器实例。

        Raises:
            ValueError: 不支持的适配器类型。
        """
        adapter_cls = cls._registry.get(adapter_type)
        if adapter_cls is None:
            raise ValueError(f"不支持的适配器类型: {adapter_type}")
        return adapter_cls(config)

    @classmethod
    def register(cls, adapter_type: str, adapter_cls: type) -> None:
        """注册新的适配器类型。

        Args:
            adapter_type: 类型标识。
            adapter_cls: 实现 HILAdapterProtocol 的类。
        """
        cls._registry[adapter_type] = adapter_cls

    @classmethod
    def list_types(cls) -> list[str]:
        """返回所有已注册的适配器类型列表。"""
        return list(cls._registry.keys())
