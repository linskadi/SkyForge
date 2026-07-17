# SkyForge Engine: digital_twin
# 数字孪生 + HIL 硬件在环测试

from skyforge_engine.digital_twin.virtual_sensor import VirtualSensor
from skyforge_engine.digital_twin.virtual_mcu import VirtualMCU
from skyforge_engine.digital_twin.fault_injector import FaultInjector
from skyforge_engine.digital_twin.simulation_engine import SimulationEngine
from skyforge_engine.digital_twin.hil_adapter import (
    HilAdapter,
    HilConfig,
    HilResult,
    SerialHilAdapter,
    JtagHilAdapter,
    MockHilAdapter,
    create_hil_adapter,
    get_default_hil_adapter,
)
from skyforge_engine.digital_twin.arinc653_adapter import (
    Arinc653Adapter,
    Partition,
    PartitionState,
    ScheduleEntry,
    ScheduleError,
)

__all__ = [
    # Virtual
    "VirtualSensor",
    "VirtualMCU",
    "FaultInjector",
    "SimulationEngine",
    # HIL
    "HilAdapter",
    "HilConfig",
    "HilResult",
    "SerialHilAdapter",
    "JtagHilAdapter",
    "MockHilAdapter",
    "create_hil_adapter",
    "get_default_hil_adapter",
    # ARINC 653
    "Arinc653Adapter",
    "Partition",
    "PartitionState",
    "ScheduleEntry",
    "ScheduleError",
]
