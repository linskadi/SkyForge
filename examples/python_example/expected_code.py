# [REQ-001] 低通滤波器模块实现
# 符合《军工软件Python语言编程指南》(T/ZASDI 0002-2023)
# DO-178C Level A

from typing import Final

# [REQ-001] 常量定义
ALPHA: Final[float] = 0.1
SAMPLE_RATE: Final[float] = 100.0
CUTOFF_FREQ: Final[float] = 10.0


class LowPassFilter:
    """[REQ-001] 低通滤波器类"""
    
    def __init__(self) -> None:
        """[REQ-001] 初始化滤波器"""
        self._prev_output: float = 0.0
        self._fault_detected: bool = False
        self._alpha: float = 0.1
    
    def init(self) -> None:
        """[REQ-001] 重置滤波器状态"""
        self._prev_output = 0.0
        self._fault_detected = False
    
    def apply(self, raw_input: float) -> float:
        """[REQ-001] 应用低通滤波"""
        # [REQ-001] 输入有效性检查
        if raw_input < 0.0 or raw_input > 20000.0:
            self._fault_detected = True
            return 0.0
        
        # [REQ-001] 一阶IIR滤波算法
        output: float = self._alpha * raw_input + (1.0 - self._alpha) * self._prev_output
        
        # [REQ-001] 更新状态变量
        self._prev_output = output
        
        return output
    
    def get_fault(self) -> bool:
        """[REQ-001] 查询故障状态"""
        return self._fault_detected
