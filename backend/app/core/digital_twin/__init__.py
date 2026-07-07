"""数字孪生仿真引擎（Day 3）：虚拟传感器 + 虚拟 MCU（GCC 编译运行）+ 故障注入 + 契约断言 core dump。

参考设计文档第 6 章：
- 6.4.1 契约→C 断言自动映射（Patch 2 已实现 contract_to_assert.py）
- 6.5 虚拟传感器与 C 代码的数据流对接（stdin/stdout 流式交互）
- 6.6 GCC 沙盒（tempfile.TemporaryDirectory 隔离 + timeout 控制）

模块导出：
- VirtualSensor：生成正常传感器数据 + 注入 5 类故障
- VirtualMCU：编译 test_harness.c + 双向通信运行 + 检测 core dump
- FaultInjector：故障注入器（封装 VirtualSensor.inject_fault）
- SimulationEngine：仿真引擎编排（生成数据→注入故障→编译→运行→解析）
- SimulationResult / CompileResult / RunResult：数据结构
"""

from app.core.digital_twin.fault_injector import FaultInjector
from app.core.digital_twin.simulation_engine import (
    SimulationEngine,
    SimulationResult,
)
from app.core.digital_twin.virtual_mcu import (
    CompileResult,
    RunResult,
    VirtualMCU,
)
from app.core.digital_twin.virtual_sensor import VirtualSensor

__all__ = [
    "VirtualSensor",
    "VirtualMCU",
    "CompileResult",
    "RunResult",
    "FaultInjector",
    "SimulationEngine",
    "SimulationResult",
]
