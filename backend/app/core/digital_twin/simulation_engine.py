"""仿真引擎编排：串联虚拟传感器→故障注入→契约断言→GCC 编译→运行→解析结果。

参考设计文档第 5.3 节"模块四：仿真运行时引擎"和 6.5 节"数据流对接"。

工作流（run_simulation）：
  1. 生成正常传感器数据（VirtualSensor.generate_normal）
  2. 如果有故障，注入故障（FaultInjector.inject）
  3. 生成契约断言代码（contract_to_assert，Patch 2）
  4. 编译 test_harness + 断言（VirtualMCU.compile）
  5. 运行仿真（VirtualMCU.run）
  6. 解析结果：输出波形 + 契约校验状态 + 统计信息
  7. 返回 SimulationResult
"""

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.core.digital_twin.fault_injector import FaultInjector
from app.core.digital_twin.virtual_mcu import VirtualMCU
from app.core.digital_twin.virtual_sensor import VirtualSensor
from app.core.tools.contract_to_assert import contract_to_assert
from app.utils.log_util import logger


@dataclass
class SimulationResult:
    """仿真结果。

    Attributes:
        passed: 仿真是否通过（契约满足 + 进程正常退出）。
        total_steps: 仿真步数。
        fault_type: 注入的故障类型（无则 None）。
        fault_params: 故障参数字典（无故障则为空字典）。
        input_waveform: 输入波形（list[float]）。
        output_waveform: 输出波形（list[float]）。
        contract_violation: 契约违约信息（无则 None）。
        statistics: 统计信息（min/max/mean/duration_ms）。
        compilation: 编译信息（success/errors/used_mock）。
        terminal_log: 终端日志（为 Patch 4 WebSocket 展示）。
    """

    passed: bool = False
    total_steps: int = 0
    fault_type: str | None = None
    fault_params: dict[str, Any] = field(default_factory=dict)
    input_waveform: list[float] = field(default_factory=list)
    output_waveform: list[float] = field(default_factory=list)
    contract_violation: dict[str, Any] | None = None
    statistics: dict[str, float] = field(default_factory=dict)
    compilation: dict[str, Any] = field(default_factory=dict)
    terminal_log: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典（供 API 返回）。"""
        return {
            "passed": self.passed,
            "total_steps": self.total_steps,
            "fault_type": self.fault_type,
            "fault_params": self.fault_params,
            "input_waveform": self.input_waveform,
            "output_waveform": self.output_waveform,
            "contract_violation": self.contract_violation,
            "statistics": self.statistics,
            "compilation": self.compilation,
            "terminal_log": self.terminal_log,
        }


class SimulationEngine:
    """仿真引擎编排：串联 VirtualSensor + FaultInjector + VirtualMCU。

    使用方式：
        engine = SimulationEngine()
        result = engine.run_simulation(code, contract_yaml, fault_type="bias", ...)
    """

    def __init__(self) -> None:
        self.sensor = VirtualSensor()
        self.fault_injector = FaultInjector()
        self.mcu = VirtualMCU()

    async def run_simulation_async(
        self,
        code: str,
        contract_yaml: str,
        fault_type: str | None = None,
        fault_params: dict[str, Any] | None = None,
        steps: int = 200,
    ) -> SimulationResult:
        """异步版本的 run_simulation()，避免阻塞 FastAPI 事件循环。"""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.run_simulation, code, contract_yaml, fault_type, fault_params, steps
        )

    def run_simulation(
        self,
        code: str,
        contract_yaml: str,
        fault_type: str | None = None,
        fault_params: dict[str, Any] | None = None,
        steps: int = 200,
    ) -> SimulationResult:
        """运行一次完整仿真。

        Args:
            code: AI 生成的 C 代码字符串。
            contract_yaml: .contract YAML 字符串。
            fault_type: 故障类型（None 表示无故障）。
            fault_params: 故障参数字典。
            steps: 仿真步数。

        Returns:
            SimulationResult。
        """
        log_lines: list[str] = []
        log_lines.append("===== 数字孪生仿真开始 =====")
        log_lines.append(
            f"steps={steps} fault_type={fault_type} fault_params={fault_params}"
        )

        # 步骤 1：生成正常传感器数据
        log_lines.append("[1/6] 生成正常传感器数据...")
        input_data = self.sensor.generate_normal(steps=steps)
        log_lines.append(
            f"    输入数据生成完成: "
            f"min={input_data.min():.4f} max={input_data.max():.4f} "
            f"mean={input_data.mean():.4f}"
        )

        # 步骤 2：注入故障（若有）
        if fault_type:
            log_lines.append(f"[2/6] 注入故障: {fault_type}")
            try:
                input_data = self.fault_injector.inject(
                    input_data, fault_type, fault_params or {}
                )
                log_lines.append(
                    f"    故障注入完成: "
                    f"min={input_data.min():.4f} max={input_data.max():.4f}"
                )
            except ValueError as e:
                log_lines.append(f"    故障注入失败: {e}")
                logger.error(f"SimulationEngine:故障注入失败: {e}")
                return self._build_error_result(
                    steps, fault_type, fault_params or {}, input_data, log_lines, str(e)
                )
        else:
            log_lines.append("[2/6] 无故障注入")

        # 步骤 3：生成契约断言代码
        log_lines.append("[3/6] 生成契约断言代码...")
        assert_code = ""
        if contract_yaml and contract_yaml.strip():
            try:
                assert_code = contract_to_assert(contract_yaml, cid="CON-001")
                log_lines.append(
                    f"    契约断言生成完成: {len(assert_code.splitlines())} 行"
                )
            except Exception as e:
                log_lines.append(f"    契约断言生成失败: {e}")
                logger.error(f"SimulationEngine:契约断言生成失败: {e}")
        else:
            log_lines.append("    无契约 YAML，跳过断言注入")

        # 步骤 4：编译
        log_lines.append("[4/6] 编译 test_harness.c + 断言...")
        compile_result = self.mcu.compile(code, assert_code=assert_code)
        compile_info: dict[str, Any] = {
            "success": compile_result.success,
            "errors": compile_result.errors,
            "used_mock": compile_result.used_mock,
        }
        if compile_result.used_mock:
            log_lines.append("    GCC 未安装，使用 Python 模拟")
        elif compile_result.success:
            log_lines.append(f"    GCC 编译成功: {compile_result.executable_path}")
        else:
            log_lines.append(f"    GCC 编译失败:\n{compile_result.errors}")
            # 编译失败：直接返回失败结果
            result = SimulationResult(
                passed=False,
                total_steps=steps,
                fault_type=fault_type,
                fault_params=fault_params or {},
                input_waveform=input_data.tolist(),
                output_waveform=[],
                contract_violation=None,
                statistics=self._compute_stats(input_data, np.array([]), 0.0),
                compilation=compile_info,
                terminal_log="\n".join(log_lines),
            )
            return result

        # 步骤 5：运行仿真
        log_lines.append("[5/6] 运行仿真...")
        run_start = time.time()
        run_result = self.mcu.run(
            compile_result.executable_path,
            input_data,
            timeout=30,
            used_mock=compile_result.used_mock,
        )
        run_duration = time.time() - run_start
        log_lines.append(
            f"    运行完成: success={run_result.success} "
            f"outputs={len(run_result.output_data)}/{steps} "
            f"duration={run_duration:.3f}s"
        )
        if run_result.assertion_failed:
            log_lines.append(f"    ⚠ 检测到断言失败 @ step={run_result.failed_step}")
            log_lines.append(f"    断言消息: {run_result.assertion_message}")

        # 清理编译产物
        if not compile_result.used_mock:
            self.mcu.cleanup(compile_result)

        # 步骤 6：解析结果
        log_lines.append("[6/6] 解析结果...")
        output_data = run_result.output_data
        statistics = self._compute_stats(input_data, output_data, run_duration * 1000)

        # 契约违约信息
        contract_violation: dict[str, Any] | None = None
        if run_result.assertion_failed:
            contract_violation = {
                "contract_id": "CON-001",
                "assertion_message": run_result.assertion_message,
                "failed_step": run_result.failed_step,
                "stderr_output": run_result.stderr[:2000],  # 截断
            }
            log_lines.append(f"    契约违约: {contract_violation['contract_id']}")

        # 仿真是否通过：进程正常退出 + 无断言失败 + 输出数量匹配
        passed = (
            run_result.success
            and (not run_result.assertion_failed)
            and len(output_data) == steps
        )
        log_lines.append(f"    仿真结果: {'PASSED ✓' if passed else 'FAILED ✗'}")
        log_lines.append("===== 数字孪生仿真结束 =====")

        terminal_log = "\n".join(log_lines)
        logger.info(f"SimulationEngine:仿真完成 passed={passed} steps={steps}")

        return SimulationResult(
            passed=passed,
            total_steps=steps,
            fault_type=fault_type,
            fault_params=fault_params or {},
            input_waveform=input_data.tolist(),
            output_waveform=output_data.tolist(),
            contract_violation=contract_violation,
            statistics=statistics,
            compilation=compile_info,
            terminal_log=terminal_log,
        )

    @staticmethod
    def _compute_stats(
        input_data: np.ndarray,
        output_data: np.ndarray,
        duration_ms: float,
    ) -> dict[str, float]:
        """计算统计信息。"""
        stats: dict[str, float] = {
            "input_min": float(np.min(input_data)) if len(input_data) else 0.0,
            "input_max": float(np.max(input_data)) if len(input_data) else 0.0,
            "input_mean": float(np.mean(input_data)) if len(input_data) else 0.0,
            "duration_ms": float(duration_ms),
        }
        if len(output_data) > 0:
            stats["output_min"] = float(np.min(output_data))
            stats["output_max"] = float(np.max(output_data))
            stats["output_mean"] = float(np.mean(output_data))
        else:
            stats["output_min"] = 0.0
            stats["output_max"] = 0.0
            stats["output_mean"] = 0.0
        return stats

    @staticmethod
    def _build_error_result(
        steps: int,
        fault_type: str | None,
        fault_params: dict[str, Any],
        input_data: np.ndarray,
        log_lines: list[str],
        error_msg: str,
    ) -> SimulationResult:
        """构建错误结果（故障注入失败等致命错误）。"""
        log_lines.append(f"===== 仿真异常终止: {error_msg} =====")
        return SimulationResult(
            passed=False,
            total_steps=steps,
            fault_type=fault_type,
            fault_params=fault_params,
            input_waveform=input_data.tolist(),
            output_waveform=[],
            contract_violation=None,
            statistics=SimulationEngine._compute_stats(input_data, np.array([]), 0.0),
            compilation={
                "success": False,
                "errors": error_msg,
                "used_mock": False,
            },
            terminal_log="\n".join(log_lines),
        )
