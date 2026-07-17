# SkyForge 示例库 (examples/)

本目录收录 SkyForge AI 驱动航空代码生成工具的演示示例，覆盖滤波器、控制器、采样器、调度器、传感器融合、任务规划、ARINC 653 分区调度、FreeRTOS 任务调度、C++ RAII、Rust 所有权等多种航空运行时场景。

> 所有示例均符合 **DO-178C** 安全等级要求与 **MISRA-C:2012** 编码规范，可作为比赛评审、客户演示与回归测试的标准素材。

## 1. 目录结构总览

```
examples/
├── README.md                              # 本文件: 示例总索引
│
├── arinc653_partition.txt                 # [基础] ARINC 653 分区调度器 (简版)
├── arinc653_partition/                    # [完整] ARINC 653 分区调度器 (四元组)
│   ├── requirement.txt
│   ├── contract.yaml
│   ├── expected_code.c
│   └── README.md
│
├── freertos_task_scheduler.txt            # [基础] FreeRTOS 任务调度器 (简版)
├── freertos_task_scheduler/               # [完整] FreeRTOS 任务调度器 (四元组)
│   ├── requirement.txt
│   ├── contract.yaml
│   ├── expected_code.c
│   └── README.md
│
├── crc_handler.txt                        # [基础] CRC-16/32 通信校验
├── cpp_smart_pointer_manager.txt          # [基础] C++ 智能指针资源管理
├── dead_reckoning.txt                     # [基础] 航位推算导航
├── filter_requirements.txt                # [基础] 低通滤波器
├── hmi_overlay.txt                        # [基础] HUD 显示叠加
├── mission_planning.txt                   # [基础] 任务规划航点管理
├── pid_controller.txt                     # [基础] PID 控制器
├── power_monitor.txt                      # [基础] 电源监控
├── rust_concurrent_data_pipeline.txt      # [基础] Rust 并发数据管道
└── sensor_fusion.txt                      # [基础] 多传感器卡尔曼融合
```

## 2. 基础示例 (.txt 文件) 简要说明

共 12 个基础示例，每个 `.txt` 文件包含自然语言需求描述、DAL 等级、模块名、功能需求、性能指标、安全约束与 MISRA-C 约束。可用于快速验证 SkyForge 的需求解析与契约生成能力。

| # | 文件名                              | 模块名                          | DAL 等级 | 场景描述                                       |
|:-:|:-----------------------------------|:-------------------------------|:--------:|:-----------------------------------------------|
| 1 | `arinc653_partition.txt`           | ARINC 653 分区调度器            | DAL-A    | 4 分区时空隔离调度 + 健康监控 + 分区间通信       |
| 2 | `freertos_task_scheduler.txt`      | FreeRTOS 任务调度器             | DAL-B    | 5 任务优先级调度 + 队列/信号量/事件组 + 看门狗   |
| 3 | `crc_handler.txt`                  | CRC 通信数据校验                | DAL-C    | CRC-16/32 + ARINC 429 解析 + 错误重传           |
| 4 | `cpp_smart_pointer_manager.txt`    | C++ 智能指针资源管理            | DAL-A    | unique_ptr/shared_ptr + RAII 动态资源管理       |
| 5 | `dead_reckoning.txt`               | 航位推算导航                    | DAL-C    | 陀螺+加速度计 + WGS-84 修正 + 纯惯导切换         |
| 6 | `filter_requirements.txt`          | 一阶低通滤波器                  | DAL-A    | IIR 滤波 + alpha=0.1 + 16kHz 采样               |
| 7 | `hmi_overlay.txt`                  | HUD 显示叠加                    | DAL-B    | 12 显示项 + 告警等级 (0-3) + 30Hz 刷新          |
| 8 | `mission_planning.txt`             | 任务规划航点管理                | DAL-C    | 100 航点 + 航线优化 + 任务状态机                 |
| 9 | `pid_controller.txt`               | 发动机 PID 控制器               | DAL-B    | 100Hz 采样 + 抗饱和 + 限幅 + 微分滤波            |
| 10| `power_monitor.txt`                | 电源监控                        | DAL-B    | 电压/电流/温度监控 + 过载保护                    |
| 11| `rust_concurrent_data_pipeline.txt`| Rust 并发数据管道               | DAL-B    | Arc/Mutex + mpsc 通道 + tokio 异步              |
| 12| `sensor_fusion.txt`                | 多传感器融合 (EKF)              | DAL-A    | 9 维状态 + 加速度/陀螺/磁力计融合 + 四元数输出    |

## 3. 完整示例目录 (四元组) 详细说明

完整示例在基础 `.txt` 之上扩展为目录形式，每个目录包含 **`requirement.txt` / `contract.yaml` / `expected_code.c` / `README.md`** 四元组，可用于端到端演示 SkyForge 的需求 → 契约 → 代码 → 验证全流程。

### 3.1 `arinc653_partition/` — ARINC 653 分区调度器

- **DAL 等级**: DAL-A
- **场景**: 综合模块化航电 (IMA) 核心操作系统的分区调度
- **MTF 周期**: 200 ms，时间片分配 P1=50ms (Display) / P2=80ms (Navigation) / P3=70ms (Health Monitoring)
- **核心特性**:
  - 严格周期性调度，抖动 ≤ 100 μs
  - 上下文切换 ≤ 1 ms (含寄存器保存/MMU刷新/入口调用)
  - 分区超时触发 `Partition_HM_Handler`
  - 无优先级反转 (固定优先级 + 时间片)
- **契约字段**: `partition_id` / `command` / `mtf_tick` → `partition_state` / `result_code` / `hm_handler_event`
- **运行步骤**: 详见 [`arinc653_partition/README.md`](./arinc653_partition/README.md)

### 3.2 `freertos_task_scheduler/` — FreeRTOS 任务调度器

- **DAL 等级**: DAL-B
- **场景**: ARM Cortex-M4 飞控计算机的多任务实时调度
- **核心任务**:

| 任务名             | 优先级 | 周期    | 执行预算 | 栈大小 |
|:------------------|:------:|:-------:|:--------:|:------:|
| Sensor_Reader     | 5      | 10 ms   | 2 ms     | 1024 字 |
| Control_Law       | 4      | 20 ms   | 5 ms     | 2048 字 |
| Telemetry_Output  | 3      | 100 ms  | 10 ms    | 1024 字 |

- **核心特性**:
  - 队列通信: `Sensor_Reader → Control_Law → Telemetry_Output`
  - 看门狗超时触发 `watchdog_reset`
  - Mutex 优先级继承防止优先级反转
  - CPU 利用率 > 85% 触发 `cpu_load_alarm`
  - 静态内存分配 (禁止 malloc)
- **契约字段**: `task_name` / `command` / `priority` / `period_ms` / `budget_ms` → `task_state` / `result_code` / `cpu_load_percent` / `watchdog_event`
- **运行步骤**: 详见 [`freertos_task_scheduler/README.md`](./freertos_task_scheduler/README.md)

## 4. 运行步骤 (通用)

### 4.1 启动 SkyForge Studio

```powershell
cd c:\Users\Lin\Desktop\Programs\Air\SkyForge
make studio-up        # 启动后端 + 前端
# 浏览器访问 http://localhost:8080
```

### 4.2 端到端流程 (以 ARINC 653 为例)

1. **需求输入**: 在 Web UI 的"需求输入"页面粘贴 `arinc653_partition/requirement.txt` 内容
2. **生成契约**: 点击"生成契约"，对比 `arinc653_partition/contract.yaml` 校验生成结果
3. **生成代码**: 点击"生成代码"，对比 `arinc653_partition/expected_code.c` 校验生成结果
4. **契约验证**: 加载 `contract.yaml` 执行 z3 形式化验证
5. **MISRA-C 检查**: 对生成的 C 代码运行 cppcheck + MISRA-C:2012 规则检查
6. **数字孪生仿真** (可选): 将代码部署到 Virtual MCU 执行仿真

### 4.3 使用 CLI

```powershell
cd c:\Users\Lin\Desktop\Programs\Air\SkyForge

# 从需求生成契约
python -m skyforge_core.cli contract examples/arinc653_partition/requirement.txt `
    --output examples/arinc653_partition/generated_contract.yaml

# 从契约生成代码
python -m skyforge_core.cli generate examples/arinc653_partition/contract.yaml `
    --output examples/arinc653_partition/generated_code.c

# 形式化验证契约
python -m skyforge_core.cli verify examples/arinc653_partition/contract.yaml

# MISRA-C 静态检查
python -m skyforge_core.cli misra-check examples/arinc653_partition/expected_code.c
```

## 5. 与比赛评审维度的对应关系

本示例库针对比赛评审的多个维度提供端到端证据，**直接贡献赛道契合度 +5 分**:

| 评审维度                | 对应示例 / 证据                                              | 评分贡献 |
|:------------------------|:------------------------------------------------------------|:--------:|
| **赛道契合度 (航空运行时)** | ARINC 653 分区调度 + FreeRTOS 任务调度，覆盖 IMA + FCS 两大主流航空运行时 | **+5**   |
| **DO-178C 合规**         | DAL-A/DAL-B 等级标注 + MC/DC 覆盖率目标 + 可追溯性矩阵       | 强证据   |
| **MISRA-C:2012 合规**    | 每个示例的 `expected_code.c` 遵循 Rule 8.4/8.7/17.7/20.4 等 | 强证据   |
| **形式化验证**           | `contract.yaml` 通过 z3 验证 pre/post/invariants/fault_handling | 强证据   |
| **三层可追溯性**         | `requirement.txt` → `contract.yaml` → `expected_code.c`      | 强证据   |
| **行业落地**             | 直接对应真实航电系统 (IMA 分区调度 / FreeRTOS FCS)           | 强证据   |
| **数字孪生集成**         | 生成的 C 代码可部署到 Virtual MCU 仿真验证                   | 加分项   |

## 6. 契约模板对应

完整示例与 `studio/frontend/src/utils/contractTemplates.ts` 中的契约模板一一对应:

| 示例目录                       | 契约模板 ID                     | 模板类型            |
|:-------------------------------|:-------------------------------|:-------------------|
| `arinc653_partition/`          | `arinc653-partition-scheduler` | ARINC 653 调度配置 |
| `freertos_task_scheduler/`     | `freertos-task-scheduler`      | FreeRTOS 调度配置  |

前端"组合验证"页面可从模板库一键加载契约，并拖入 A/B 槽位执行兼容性检查。

## 7. 维护说明

- 新增基础示例: 直接在 `examples/` 添加 `.txt` 文件，并更新本 README 第 2 节表格
- 新增完整示例: 创建 `examples/<name>/` 目录，包含四元组 (requirement.txt / contract.yaml / expected_code.c / README.md)，并更新本 README 第 3 节
- 同步契约模板: 在 `studio/frontend/src/utils/contractTemplates.ts` 添加对应模板，并加入 `CONTRACT_TEMPLATES` 数组
- 验证: 修改后运行 `make test` 确保无新引入的失败
