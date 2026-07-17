# 仿真模型目录

本目录存放SkyForge数字孪生仿真所需的模型文件。

## 目录结构

```
models/
├── README.md           # 本文件
├── sensors/            # 传感器模型
│   └── ...             # 传感器配置文件
├── mcu/                # MCU模型
│   └── ...             # MCU配置文件
└── faults/             # 故障模型
    └── ...             # 故障注入配置
```

## 支持的模型类型

### 传感器模型
- 温度传感器
- 压力传感器
- 加速度传感器
- 陀螺仪
- GPS模块

### MCU模型
- ARM Cortex-M系列
- RISC-V
- 自定义虚拟MCU

### 故障模型
- 传感器漂移 (bias)
- 信号丢失 (signal_loss)
- 噪声干扰 (noise)
- 信号卡死 (stuck)
- 阶跃突变 (step)

## 使用说明

模型文件由SkyForge数字孪生引擎自动加载，无需手动配置。

```python
from skyforge_engine.digital_twin import VirtualSensor, VirtualMCU

# 加载传感器模型
sensor = VirtualSensor(wave_type="sine", amplitude=100.0)

# 加载MCU模型
mcu = VirtualMCU(gcc_path="/usr/bin/gcc")
```

## 当前形态与后续规划

- **当前用途**：本目录用于存放数字孪生仿真模型配置文件。
- **Mock 模式说明**：由于 SkyForge 主要使用 Mock 模式运行（无需真实硬件即可演示），模型文件目前以 YAML 配置形式存放在 `examples/`（如 `arinc653_partition/contract.yaml`、`freertos_task_scheduler/contract.yaml`）以及 `src/skyforge_engine/digital_twin/`（`fault_injector.py`、`simulation_engine.py`、`virtual_sensor.py`、`virtual_mcu.py`、`arinc653_adapter.py` 等）中。
- **后续补充**：随着真实硬件在环（HIL）联调推进，将补充完整的 `.slx`（Simulink）、`.fmu`（Functional Mock-up Unit）等标准仿真模型文件，以及对应的二进制模型产物。

---

**更新日期**: 2026-07-17
