"""SkyForge 核心适配器层 (Phase 5)。"""

from skyforge_engine.core.adapters.hil_adapter import (
    HILAdapterFactory,
    QEMUAdapter,
    SerialHIL,
    VirtualMCUAdapter,
)

__all__ = [
    "HILAdapterFactory",
    "QEMUAdapter",
    "SerialHIL",
    "VirtualMCUAdapter",
]
