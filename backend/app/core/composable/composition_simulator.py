"""组合仿真验证：复用 Day 3 SimulationEngine 验证组合后契约是否满足。

参考设计文档第 6.5 节"可组合性验证"。
组件组合后，需通过数字孪生仿真验证组合契约是否在实际运行中保持满足。

工作流：
  1. 用 SimulationEngine.run_simulation 运行组合后代码 + 组合后契约
  2. 解析仿真结果：是否通过、契约违约位置
  3. 若契约违约，提取违约位置（failed_step）和断言消息
"""

from dataclasses import dataclass, field
from typing import Any

from app.core.digital_twin.simulation_engine import (
    SimulationEngine,
    SimulationResult,
)
from app.utils.log_util import logger


@dataclass
class CompositionSimulationResult:
    """组合仿真验证结果。

    Attributes:
        passed: 组合仿真是否通过（契约满足 + 进程正常退出）。
        total_steps: 仿真步数。
        contract_satisfied: 组合契约是否满足（无违约）。
        violation_location: 契约违约位置（步号），无违约为 None。
        violation_message: 违约消息，无违约为空字符串。
        output_waveform: 输出波形（list[float]）。
        statistics: 仿真统计信息。
        terminal_log: 终端日志（用于前端展示）。
        simulation_result: 原始 SimulationResult.to_dict()（含完整信息）。
    """

    passed: bool = False
    total_steps: int = 0
    contract_satisfied: bool = False
    violation_location: int | None = None
    violation_message: str = ""
    output_waveform: list[float] = field(default_factory=list)
    statistics: dict[str, float] = field(default_factory=dict)
    terminal_log: str = ""
    simulation_result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "total_steps": self.total_steps,
            "contract_satisfied": self.contract_satisfied,
            "violation_location": self.violation_location,
            "violation_message": self.violation_message,
            "output_waveform": self.output_waveform,
            "statistics": self.statistics,
            "terminal_log": self.terminal_log,
            "simulation_result": self.simulation_result,
        }


class CompositionSimulator:
    """组合仿真器：复用 SimulationEngine 验证组合后契约。

    使用方式：
        simulator = CompositionSimulator()
        result = simulator.simulate(composed_code, composed_contract, steps=200)
    """

    def __init__(self) -> None:
        self.engine = SimulationEngine()

    def simulate(
        self,
        composed_code: str,
        composed_contract: str,
        steps: int = 200,
    ) -> CompositionSimulationResult:
        """运行组合后仿真，验证组合契约是否满足。

        Args:
            composed_code: 组合后的 C 代码字符串（含 double filter(double) 函数）。
            composed_contract: 组合后的 .contract YAML 字符串。
            steps: 仿真步数（默认 200）。

        Returns:
            CompositionSimulationResult。
        """
        logger.info(
            f"CompositionSimulator:开始 composed_code={len(composed_code)}B "
            f"steps={steps}"
        )

        # 复用 Day 3 SimulationEngine
        sim_result: SimulationResult = self.engine.run_simulation(
            code=composed_code,
            contract_yaml=composed_contract,
            fault_type=None,
            fault_params=None,
            steps=steps,
        )

        # 提取违约位置
        violation = sim_result.contract_violation
        violation_location: int | None = None
        violation_message = ""
        if violation:
            violation_location = violation.get("failed_step")
            violation_message = violation.get("assertion_message", "")

        # 契约满足 = 无违约
        contract_satisfied = violation is None

        logger.info(
            f"CompositionSimulator:完成 passed={sim_result.passed} "
            f"contract_satisfied={contract_satisfied} "
            f"violation_loc={violation_location}"
        )

        return CompositionSimulationResult(
            passed=sim_result.passed,
            total_steps=sim_result.total_steps,
            contract_satisfied=contract_satisfied,
            violation_location=violation_location,
            violation_message=violation_message,
            output_waveform=sim_result.output_waveform,
            statistics=sim_result.statistics,
            terminal_log=sim_result.terminal_log,
            simulation_result=sim_result.to_dict(),
        )


# ====================================================================== #
# 模块级便捷函数
# ====================================================================== #
def simulate_composition(
    composed_code: str,
    composed_contract: str,
    steps: int = 200,
) -> CompositionSimulationResult:
    """组合仿真模块级入口（便捷封装）。

    Args:
        composed_code: 组合后的 C 代码字符串。
        composed_contract: 组合后的 .contract YAML 字符串。
        steps: 仿真步数。

    Returns:
        CompositionSimulationResult。
    """
    simulator = CompositionSimulator()
    return simulator.simulate(composed_code, composed_contract, steps)
