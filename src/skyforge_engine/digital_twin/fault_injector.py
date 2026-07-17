"""故障注入器：封装 VirtualSensor.inject_fault，提供故障类型描述 + 默认参数 + 参数校验。

参考设计文档第 5.4 节"故障注入设计"，5 类故障：
- bias：传感器偏置（data + bias_value）
- signal_loss：信号丢失（指定区间设为 0）
- noise：高频噪声（data + random_noise * amplitude）
- stuck：信号卡死（指定区间设为固定值）
- step：阶跃突变（指定时间点突变）
"""

from typing import Any

import numpy as np

from skyforge_engine.digital_twin.virtual_sensor import VirtualSensor
from skyforge_engine.utils.log_util import logger

# 5 类故障的描述 + 默认参数
FAULT_TYPES_INFO: list[dict[str, Any]] = [
    {
        "type": "bias",
        "name": "传感器偏置",
        "desc": "整体数据加上一个固定偏置值，模拟传感器零点漂移。",
        "default_params": {"bias_value": 50.0},
        "params_schema": {
            "bias_value": {
                "type": "float",
                "desc": "偏置值（正数表示上偏，负数表示下偏）",
                "required": True,
            }
        },
    },
    {
        "type": "signal_loss",
        "name": "信号丢失",
        "desc": "指定区间数据设为 0，模拟传感器信号完全丢失。",
        "default_params": {"start": 0, "end": 100},
        "params_schema": {
            "start": {"type": "int", "desc": "起始步号", "required": True},
            "end": {"type": "int", "desc": "结束步号（不含）", "required": True},
        },
    },
    {
        "type": "noise",
        "name": "高频噪声",
        "desc": "在数据上叠加高斯随机噪声，模拟传感器噪声干扰。",
        "default_params": {"amplitude": 50.0},
        "params_schema": {
            "amplitude": {
                "type": "float",
                "desc": "噪声幅度（标准差）",
                "required": True,
            }
        },
    },
    {
        "type": "stuck",
        "name": "信号卡死",
        "desc": "指定区间数据设为固定值，模拟传感器卡死故障。",
        "default_params": {"start": 0, "end": 100, "stuck_value": 0.0},
        "params_schema": {
            "start": {"type": "int", "desc": "起始步号", "required": True},
            "end": {"type": "int", "desc": "结束步号（不含）", "required": True},
            "stuck_value": {"type": "float", "desc": "卡死值", "required": True},
        },
    },
    {
        "type": "step",
        "name": "阶跃突变",
        "desc": "从指定时间点起整体加上一个突变值，模拟传感器阶跃故障。",
        "default_params": {"step_at": 100, "step_value": 1000.0},
        "params_schema": {
            "step_at": {"type": "int", "desc": "阶跃发生步号", "required": True},
            "step_value": {"type": "float", "desc": "阶跃幅度", "required": True},
        },
    },
]


class FaultInjector:
    """故障注入器：封装 VirtualSensor.inject_fault。

    提供：
    - inject(data, fault_type, params)：注入故障到数据
    - get_fault_types()：返回 5 类故障的描述和默认参数
    - validate_params(fault_type, params)：验证参数合法性
    """

    def __init__(self) -> None:
        self.sensor = VirtualSensor()

    def inject(
        self,
        data: np.ndarray,
        fault_type: str,
        params: dict[str, Any] | None,
    ) -> np.ndarray:
        """注入故障到传感器数据。

        Args:
            data: 原始正常数据数组。
            fault_type: 故障类型（bias/signal_loss/noise/stuck/step）。
            params: 故障参数字典。

        Returns:
            注入故障后的新数组。

        Raises:
            ValueError: 故障类型不支持或参数非法。
        """
        if not self.validate_params(fault_type, params or {}):
            raise ValueError(
                f"故障参数校验失败: fault_type={fault_type} params={params}"
            )
        logger.info(f"FaultInjector:注入故障 type={fault_type} params={params}")
        return self.sensor.inject_fault(data, fault_type, params or {})

    def get_fault_types(self) -> list[dict[str, Any]]:
        """返回 5 类故障的描述和默认参数。

        Returns:
            故障类型信息列表，每项含 type/name/desc/default_params/params_schema。
        """
        return [
            {
                "type": info["type"],
                "name": info["name"],
                "desc": info["desc"],
                "default_params": dict(info["default_params"]),
                "params_schema": dict(info["params_schema"]),
            }
            for info in FAULT_TYPES_INFO
        ]

    def validate_params(self, fault_type: str, params: dict[str, Any]) -> bool:
        """验证故障参数合法性。

        Args:
            fault_type: 故障类型。
            params: 故障参数字典。

        Returns:
            True 表示参数合法。
        """
        info = next((i for i in FAULT_TYPES_INFO if i["type"] == fault_type), None)
        if info is None:
            logger.warning(f"FaultInjector:未知故障类型 {fault_type}")
            return False

        schema = info["params_schema"]
        params = params or {}

        # 检查必填字段
        for key, spec in schema.items():
            if spec.get("required", False) and key not in params:
                logger.warning(
                    f"FaultInjector:缺少必填参数 {key} (fault_type={fault_type})"
                )
                return False

        # 类型检查
        for key, value in params.items():
            if key not in schema:
                # 允许额外字段
                continue
            spec = schema[key]
            t = spec.get("type")
            try:
                if t == "int":
                    int(value)
                elif t == "float":
                    float(value)
            except (ValueError, TypeError):
                logger.warning(f"FaultInjector:参数类型错误 {key}={value} (期望 {t})")
                return False

        # 区间类故障：start <= end
        if fault_type in ("signal_loss", "stuck"):
            start = int(params.get("start", 0))
            end = int(params.get("end", start))
            if start > end:
                logger.warning(f"FaultInjector:区间非法 start={start} > end={end}")
                return False

        # step 类故障：step_at >= 0
        if fault_type == "step":
            step_at = int(params.get("step_at", 0))
            if step_at < 0:
                logger.warning(f"FaultInjector:step_at={step_at} 不能为负")
                return False

        return True
