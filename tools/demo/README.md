# SkyForge 离线演示脚本

## 目的
确保决赛演示成功，不受网络和LLM服务影响。包含所有预置数据，可完全离线运行。

## 功能特点
- 预置5个完整Demo示例（需求、契约、代码、仿真结果）
- 支持离线模式演示（不依赖LLM）
- 生成演示报告（JSON格式）
- 支持一键演示所有功能
- 支持命令行参数选择演示内容

## 包含模块
1. **crc_handler** - CRC通信数据校验 (DAL-C)
2. **dead_reckoning** - 航位推算算法 (DAL-B)
3. **pid_controller** - PID控制器 (DAL-A)
4. **power_monitor** - 电源监控模块 (DAL-C)
5. **filter_requirements** - 数字滤波器 (DAL-B)

## 使用方法

### 列出所有可用模块
```bash
python offline_demo.py --list
```

### 运行单个模块演示
```bash
python offline_demo.py --module crc_handler
python offline_demo.py --module dead_reckoning
python offline_demo.py --module pid_controller
python offline_demo.py --module power_monitor
python offline_demo.py --module filter_requirements
```

### 运行所有模块演示
```bash
python offline_demo.py --all
```

### 指定输出目录
```bash
python offline_demo.py --all --output my_demo_output
```

## 演示流程
每个模块的演示包含6个步骤：
1. **需求解析** - 自然语言需求转结构化JSON
2. **契约生成** - 生成DO-178C合规契约YAML
3. **代码生成** - 生成MISRA-C风格C代码
4. **合规检查** - Cppcheck MISRA-C扫描 + 契约校验
5. **数字孪生仿真** - 虚拟传感器/MCU + 故障注入测试
6. **报告生成** - DO-178C合规报告 (JSON)

## 输出文件
演示完成后会在输出目录生成以下文件：
- `{module}_requirement.json` - 结构化需求
- `{module}_contract.yaml` - DO-178C合规契约
- `{module}.c` - MISRA-C代码
- `{module}_simulation.json` - 仿真结果
- `{module}_report.json` - 合规报告
- `demo_summary.json` - 汇总报告

## 快速演示
```bash
# 一键演示所有功能
python offline_demo.py --all

# 或仅演示CRC模块
python offline_demo.py -m crc_handler
```

## 注意事项
- 本脚本完全离线运行，不依赖任何网络服务
- 所有数据均为预置，确保演示稳定性
- 输出目录会自动创建
- 支持多次运行，文件会覆盖

## 决赛演示建议
1. 提前运行一次完整演示，确认输出正常
2. 准备演示时，可按模块逐一展示
3. 重点展示需求解析→契约生成→代码生成的全流程
4. 强调MISRA-C合规和DO-178C报告生成能力
5. 展示数字孪生仿真结果，证明代码质量

## 文件结构
```
demo/
├── offline_demo.py      # 离线演示脚本
├── README.md           # 说明文档
└── demo_output/        # 演示输出目录（运行时创建）
    ├── crc_handler_requirement.json
    ├── crc_handler_contract.yaml
    ├── crc_handler.c
    ├── crc_handler_simulation.json
    ├── crc_handler_report.json
    └── demo_summary.json
```
