"""
@file signal_processor.py
@brief 军工软件Python编程规范示例 — 信号处理器

合规标准: T/ZASDI 0002-2023 (军工软件Python语言编程指南)
DO-178C 机载软件代码生成模板

合规规则:
- P-01: 禁止使用 eval/exec
- P-02: 禁止使用全局变量（除必要状态）
- T-01: 所有函数必须有类型标注
- 命名规范: snake_case 函数/变量, PascalCase 类名

@req_id REQ-001
@module signal_processor
@safety_level DAL-B
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


# [{req_id}] P-02: 模块级常量（非全局变量）
MAX_BUFFER_SIZE: int = 1024
DEFAULT_TIMEOUT: float = 5.0


class DataQuality(Enum):
    """数据质量等级。"""
    GOOD = "good"
    SUSPECT = "suspect"
    BAD = "bad"
    MISSING = "missing"


@dataclass
class SensorReading:
    """传感器读数数据类。"""
    sensor_id: int
    value: float
    timestamp: float
    quality: DataQuality = DataQuality.GOOD

    def is_valid(self) -> bool:
        """检查读数是否有效。"""
        return self.quality == DataQuality.GOOD


class SignalProcessor:
    """信号处理器（军工软件Python编程规范示例）。

    实现一阶 IIR 低通滤波器，符合 T/ZASDI 0002-2023 规范。
    """

    def __init__(self, buffer_size: int = 1024) -> None:
        """初始化信号处理器。

        Args:
            buffer_size: 缓冲区大小

        Raises:
            ValueError: 缓冲区大小超出范围
        """
        if buffer_size <= 0 or buffer_size > 1024:
            raise ValueError(f"buffer_size must be in [1, 1024]")
        self._buffer: List[float] = []
        self._buffer_size: int = buffer_size
        self._initialized: bool = True

    def process(self, raw_input: float) -> float:
        """处理输入信号。

        Args:
            raw_input: 原始输入值

        Returns:
            处理后的输出值

        Raises:
            RuntimeError: 未初始化时调用
        """
        if not self._initialized:
            raise RuntimeError("Processor not initialized")

        if not (0.0 <= raw_input <= 20000.0):
            return 0.0

        output: float = 0.385870 * raw_input + (1.0 - 0.385870) * (
            self._buffer[-1] if self._buffer else 0.0
        )

        if len(self._buffer) >= self._buffer_size:
            self._buffer.pop(0)
        self._buffer.append(output)

        return output

    def reset(self) -> None:
        """重置处理器状态。"""
        self._buffer.clear()
        self._initialized = True

    def get_buffer(self) -> List[float]:
        """获取当前缓冲区内容。"""
        return self._buffer.copy()

    def __del__(self) -> None:
        """析构函数。"""
        self._initialized = False


def create_processor(buffer_size: int = 1024) -> SignalProcessor:
    """创建信号处理器实例。"""
    return SignalProcessor(buffer_size=buffer_size)


def validate_input(value: float, min_val: float = 0.0, max_val: float = 20000.0) -> bool:
    """验证输入值是否在有效范围内。"""
    return min_val <= value <= max_val
