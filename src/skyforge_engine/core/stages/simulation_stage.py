"""数字孪生仿真 Stage。"""

from __future__ import annotations

from typing import Any

from skyforge_engine.core.protocols import StageResult
from skyforge_engine.core.stages._utils import _normalize_hook
from skyforge_engine.utils.log_util import logger


class SimulationStage:
    """数字孪生仿真。"""

    def __init__(self, simulate: bool = True) -> None:
        self._simulate = simulate

    @property
    def name(self) -> str:
        return "simulation"

    @property
    def description(self) -> str:
        return "数字孪生仿真"

    async def execute(
        self, artifact: dict[str, Any], context: dict[str, Any] | None = None
    ) -> StageResult:
        from skyforge_engine.digital_twin.simulation_engine import SimulationEngine

        context = context or {}
        hook = _normalize_hook(context.get("log_hook"))
        final_code = artifact.get("final_code") or artifact.get("code", "")
        contract = artifact.get("contract", "")
        execution_context = artifact.get("execution_context")

        simulation_result_dict: dict[str, Any] | None = None
        if self._simulate:
            await hook("SYSTEM", "info", "阶段 3：数字孪生仿真（无故障默认）")
            try:
                engine = SimulationEngine(
                    use_real_gcc=(
                        execution_context.tool_policy.use_real_gcc
                        if execution_context is not None
                        else None
                    )
                )
                sim = await engine.run_simulation_async(
                    code=final_code,
                    contract_yaml=contract,
                    fault_type=None,
                    fault_params=None,
                    steps=200,
                )
                simulation_result_dict = sim.to_dict()
                level = "success" if sim.passed else "error"
                await hook(
                    "SYSTEM",
                    level,
                    f"仿真完成 passed={sim.passed} steps={sim.total_steps}",
                )
            except Exception as e:
                logger.error(f"Pipeline:数字孪生仿真异常: {e}")
                await hook("SYSTEM", "error", f"仿真异常: {e}")

        artifact["simulation_result"] = simulation_result_dict
        return StageResult(artifact=artifact, status="success")
