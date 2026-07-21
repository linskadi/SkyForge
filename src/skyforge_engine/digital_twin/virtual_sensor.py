"""虚拟传感器（信号模拟器）：生成正常传感器数据 + 注入 12 类故障。

参考设计文档第 6.5 节"虚拟传感器与 C 代码的数据流对接"。

支持 5 种正常波形：
- sine：正弦波（默认）
- ramp：斜坡
- step：阶跃
- constant：常量
- noise：高斯噪声

支持 12 类故障注入（与 FaultInjector.FAULT_TYPES_INFO 对齐）：
基础 5 类：
- bias：传感器偏置（data + bias_value）
- signal_loss：信号丢失（指定区间设为 0）
- noise：高频噪声（data + random_noise * amplitude）
- stuck：信号卡死（指定区间设为固定值）
- step：阶跃突变（指定时间点突变）
扩展 7 类：
- saturation：饱和截断（超出阈值截断）
- intermittent：间歇性故障（周期性丢值）
- drift：渐变漂移（线性漂移）
- timeout：丢帧/延迟（数据置零）
- glitch：跳变毛刺（瞬时跳变）
- stuck_zero：零输出（指定区间强制归零）
- polarity：符号反转（乘 -1）
"""

from typing import Any

import numpy as np

from skyforge_engine.utils.log_util import logger

# 默认传感器配置（200 步正弦波，幅度 100，频率 0.05，无噪声）
DEFAULT_CONFIG: dict[str, Any] = {
    "wave_type": "sine",
    "amplitude": 100.0,
    "frequency": 0.05,
    "offset": 0.0,
    "noise_level": 0.0,
    "dt": 0.01,
}

# 支持的波形类型
WAVE_TYPES = ("sine", "ramp", "step", "constant", "noise")

# 支持的故障类型（12 类，与 FaultInjector.FAULT_TYPES_INFO 对齐）
FAULT_TYPES = (
    # 基础 5 类
    "bias",
    "signal_loss",
    "noise",
    "stuck",
    "step",
    # 扩展 7 类
    "saturation",
    "intermittent",
    "drift",
    "timeout",
    "glitch",
    "stuck_zero",
    "polarity",
)


class VirtualSensor:
    """虚拟传感器：生成正常传感器数据 + 注入 12 类故障。

    所有方法均无副作用（不修改输入数组），返回新数组。
    """

    def generate_normal(
        self, steps: int = 200, config: dict[str, Any] | None = None
    ) -> np.ndarray:
        """生成正常传感器数据。

        Args:
            steps: 仿真步数。
            config: 配置字典，可含字段：
                - wave_type: 波形类型（sine/ramp/step/constant/noise）
                - amplitude: 幅度（默认 100.0）
                - frequency: 频率（默认 0.05，单位 Hz）
                - offset: 直流偏置（默认 0.0）
                - noise_level: 噪声标准差（默认 0.0，无噪声）
                - dt: 时间步长（默认 0.01s）

        Returns:
            长度为 steps 的 numpy 数组（float64）。

        Raises:
            ValueError: steps <= 0 或 wave_type 不支持。
        """
        if steps <= 0:
            raise ValueError(f"steps 必须 > 0，当前 {steps}")

        cfg = {**DEFAULT_CONFIG, **(config or {})}
        wave_type = cfg["wave_type"]
        amplitude = float(cfg["amplitude"])
        frequency = float(cfg["frequency"])
        offset = float(cfg["offset"])
        noise_level = float(cfg["noise_level"])
        dt = float(cfg["dt"])

        if wave_type not in WAVE_TYPES:
            raise ValueError(f"不支持的 wave_type={wave_type}，可选: {WAVE_TYPES}")

        # 时间轴：t = i * dt
        t = np.arange(steps, dtype=np.float64) * dt

        if wave_type == "sine":
            data = amplitude * np.sin(2.0 * np.pi * frequency * t)
        elif wave_type == "ramp":
            # 斜坡：从 0 线性增长到 amplitude
            data = amplitude * (t / max(t[-1], dt)) if steps > 1 else np.zeros(steps)
            data = np.minimum(data, amplitude)
        elif wave_type == "step":
            # 阶跃：前半段为 0，后半段为 amplitude
            data = np.where(t >= t[steps // 2], amplitude, 0.0)
        elif wave_type == "constant":
            data = np.full(steps, amplitude, dtype=np.float64)
        else:  # noise
            rng = np.random.default_rng(seed=42)
            data = rng.normal(0.0, amplitude, size=steps)

        # 加直流偏置
        data = data + offset

        # 叠加高斯噪声（若 noise_level > 0）
        if noise_level > 0:
            rng = np.random.default_rng(seed=42)
            data = data + rng.normal(0.0, noise_level, size=steps)

        logger.info(
            f"VirtualSensor:generate_normal:steps={steps} "
            f"wave={wave_type} amp={amplitude} freq={frequency}"
        )
        return data.astype(np.float64)

    def inject_fault(
        self, data: np.ndarray, fault_type: str, params: dict[str, Any]
    ) -> np.ndarray:
        """注入故障到传感器数据（返回新数组，不修改输入）。

        Args:
            data: 原始正常数据数组。
            fault_type: 故障类型（12 类之一，见 FAULT_TYPES）。
            params: 故障参数字典：
                - bias: {"bias_value": float}
                - signal_loss: {"start": int, "end": int}
                - noise: {"amplitude": float}
                - stuck: {"start": int, "end": int, "stuck_value": float}
                - step: {"step_at": int, "step_value": float}
                - saturation: {"min_val": float, "max_val": float}
                - intermittent: {"probability": float (0-1)}
                - drift: {"drift_rate": float (per step)}
                - timeout: {"start": int, "end": int}
                - glitch: {"glitch_at": int, "glitch_value": float}
                - stuck_zero: {"start": int, "end": int}
                - polarity: {}（无参数）

        Returns:
            注入故障后的新数组（float64）。

        Raises:
            ValueError: fault_type 不支持或参数非法。
        """
        if fault_type not in FAULT_TYPES:
            raise ValueError(f"不支持的 fault_type={fault_type}，可选: {FAULT_TYPES}")

        out = np.array(data, dtype=np.float64, copy=True)
        params = params or {}

        if fault_type == "bias":
            bias_value = float(params.get("bias_value", 50.0))
            out = out + bias_value
            logger.info(f"VirtualSensor:inject bias={bias_value}")

        elif fault_type == "signal_loss":
            start = int(params.get("start", 0))
            end = int(params.get("end", len(out)))
            start, end = self._clamp_range(start, end, len(out))
            out[start:end] = 0.0
            logger.info(f"VirtualSensor:inject signal_loss=[{start},{end})")

        elif fault_type == "noise":
            amplitude = float(params.get("amplitude", 50.0))
            rng = np.random.default_rng(seed=123)
            out = out + rng.normal(0.0, amplitude, size=len(out))
            logger.info(f"VirtualSensor:inject noise amp={amplitude}")

        elif fault_type == "stuck":
            start = int(params.get("start", 0))
            end = int(params.get("end", len(out)))
            stuck_value = float(params.get("stuck_value", 0.0))
            start, end = self._clamp_range(start, end, len(out))
            out[start:end] = stuck_value
            logger.info(
                f"VirtualSensor:inject stuck=[{start},{end}) value={stuck_value}"
            )

        elif fault_type == "step":
            step_at = int(params.get("step_at", len(out) // 2))
            step_value = float(params.get("step_value", 1000.0))
            step_at = max(0, min(step_at, len(out)))
            out[step_at:] = out[step_at:] + step_value
            logger.info(f"VirtualSensor:inject step at={step_at} value={step_value}")

        # ===== 扩展 7 类故障 =====
        elif fault_type == "saturation":
            min_val = float(params.get("min_val", -1000.0))
            max_val = float(params.get("max_val", 1000.0))
            out = np.clip(out, min_val, max_val)
            logger.info(
                f"VirtualSensor:inject saturation=[{min_val},{max_val}]"
            )

        elif fault_type == "intermittent":
            probability = float(params.get("probability", 0.1))
            probability = max(0.0, min(probability, 1.0))
            rng = np.random.default_rng(seed=456)
            mask = rng.random(size=len(out)) < probability
            out[mask] = 0.0
            logger.info(
                f"VirtualSensor:inject intermittent prob={probability} lost={int(mask.sum())}"
            )

        elif fault_type == "drift":
            drift_rate = float(params.get("drift_rate", 0.5))
            ramp = np.arange(len(out), dtype=np.float64) * drift_rate
            out = out + ramp
            logger.info(f"VirtualSensor:inject drift rate={drift_rate}")

        elif fault_type == "timeout":
            start = int(params.get("start", 0))
            end = int(params.get("end", len(out)))
            start, end = self._clamp_range(start, end, len(out))
            out[start:end] = 0.0
            logger.info(f"VirtualSensor:inject timeout=[{start},{end})")

        elif fault_type == "glitch":
            glitch_at = int(params.get("glitch_at", len(out) // 2))
            glitch_value = float(params.get("glitch_value", 5000.0))
            glitch_at = max(0, min(glitch_at, len(out) - 1))
            out[glitch_at] = out[glitch_at] + glitch_value
            logger.info(
                f"VirtualSensor:inject glitch at={glitch_at} value={glitch_value}"
            )

        elif fault_type == "stuck_zero":
            start = int(params.get("start", 0))
            end = int(params.get("end", len(out)))
            start, end = self._clamp_range(start, end, len(out))
            out[start:end] = 0.0
            logger.info(f"VirtualSensor:inject stuck_zero=[{start},{end})")

        elif fault_type == "polarity":
            out = -out
            logger.info("VirtualSensor:inject polarity (sign-reversed)")

        return out

    def to_csv(self, data: np.ndarray) -> str:
        """将数组转为 CSV 字符串（每行一个 double，用于 stdin 输入）。

        Args:
            data: 一维数组。

        Returns:
            多行字符串，每行一个浮点数（%.15g 精度）。
        """
        arr = np.asarray(data, dtype=np.float64).ravel()
        lines = [f"{v:.15g}" for v in arr]
        return "\n".join(lines)

    @staticmethod
    def _clamp_range(start: int, end: int, length: int) -> tuple[int, int]:
        """将 [start, end) 范围裁剪到 [0, length) 内。"""
        start = max(0, min(start, length))
        end = max(0, min(end, length))
        if end < start:
            start, end = end, start
        return start, end
