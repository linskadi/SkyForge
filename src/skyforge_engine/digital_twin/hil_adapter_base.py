# -*- coding: utf-8 -*-
"""HIL 适配器抽象基类。

为 Hardware-In-The-Loop（硬件在环）测试提供统一的抽象接口，
支持虚拟模式、串口、JTAG/SWD 以及 QEMU 仿真等多种运行模式。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class HILMode(Enum):
    """HIL 运行模式。"""

    VIRTUAL = "virtual"
    SERIAL = "serial"
    JTAG_SWD = "jtag_swd"
    QEMU = "qemu"


@dataclass
class HILConfig:
    """HIL 适配器配置。"""

    mode: HILMode = HILMode.VIRTUAL
    serial_port: str = "COM3"
    baud_rate: int = 115200
    serial_timeout: float = 5.0

    jtag_device: str = "STLINK"
    jtag_target: str = "STM32F407"
    flash_timeout: float = 30.0
    run_timeout: float = 30.0
    connect_timeout: float = 10.0


@dataclass
class HILResult:
    """HIL 单次运行结果。"""

    status: str = "success"  # "success" | "error" | "timeout"
    output_waveform: Optional[list[float]] = None
    message: str = ""
    method: str = ""


class HILAdapter(abc.ABC):
    """HIL 适配器抽象基类。

    所有具体适配器（串口、JTAG/SWD、QEMU、虚拟）必须实现以下方法：
    - connect():     建立与目标设备/仿真的连接
    - flash():       将固件烧录到目标设备
    - run():         运行输入向量并采集输出
    - disconnect():  断开连接并释放资源
    """

    def __init__(self, config: HILConfig) -> None:
        self.config = config
        self._connected = False

    @abc.abstractmethod
    def connect(self) -> bool:
        """建立连接。"""
        ...

    @abc.abstractmethod
    def flash(self, firmware_path: str) -> HILResult:
        """烧录固件。

        Args:
            firmware_path: 固件文件路径（ELF/BIN/HEX）

        Returns:
            HILResult: 烧录结果
        """
        ...

    @abc.abstractmethod
    def run(self, input_vector: Any) -> HILResult:
        """运行目标程序并采集输出波形。

        Args:
            input_vector: 输入向量（类型由具体适配器决定）

        Returns:
            HILResult: 运行结果，包含 output_waveform
        """
        ...

    @abc.abstractmethod
    def disconnect(self) -> bool:
        """断开连接并释放资源。"""
        ...
