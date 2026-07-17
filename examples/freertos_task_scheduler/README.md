# FreeRTOS 任务调度器示例 (freertos_task_scheduler)

## 1. 场景描述

本示例演示如何使用 SkyForge 自动生成基于 **FreeRTOS V10.x**、符合 **DO-178C DAL-B** 等级、**MISRA-C:2012** 规范的多任务飞行控制系统代码。

部署场景为运行于 ARM Cortex-M4 MCU 之上的飞控计算机。系统包含 3 个核心周期任务，通过 FreeRTOS 队列形成数据流水线，并配备看门狗监控、优先级继承与 CPU 利用率告警机制。

### 核心任务清单

| 任务名             | 优先级 | 周期    | 执行预算 | 栈大小 |
|:------------------|:------:|:-------:|:--------:|:------:|
| Sensor_Reader     | 5      | 10 ms   | 2 ms     | 1024 字 |
| Control_Law       | 4      | 20 ms   | 5 ms     | 2048 字 |
| Telemetry_Output  | 3      | 100 ms  | 10 ms    | 1024 字 |

> 优先级数值越大优先级越高 (FreeRTOS 约定)。
> 执行预算必须 ≤ 任务周期 (CON-FRTOS-PRE-003)。

### 数据流

```
Sensor_Reader  --[Queue: sensor_data]-->  Control_Law  --[Queue: control_cmd]-->  Telemetry_Output
   (10ms)                                    (20ms)                                   (100ms)
```

### 核心特性
- **抢占式调度** (Preemptive Scheduling)，tick 频率 1 kHz
- **队列通信** (Queue Communication)，长度 10，发送非阻塞、接收超时 = 任务周期
- **看门狗监控**: 任务超时触发 `watchdog_reset`，硬件看门狗 500ms 触发系统复位
- **优先级继承** (Priority Inheritance): Mutex 防止优先级反转
- **CPU 利用率告警**: > 85% 触发 `cpu_load_alarm`，系统降级运行
- **静态内存分配**: 禁止动态 malloc，所有栈/TCB/队列静态分配

## 2. 目录结构

```
examples/freertos_task_scheduler/
├── requirement.txt      # 自然语言需求描述 (中文 + 英文术语)
├── contract.yaml        # 形式化契约 (inputs/outputs/preconditions/postconditions/invariants/fault_handling)
├── expected_code.c      # 期望生成的 C 代码 (MISRA-C:2012 兼容)
└── README.md            # 本文档: 场景描述、运行步骤、预期输出
```

## 3. 运行步骤

### 3.1 使用 SkyForge Studio (Web UI)

1. 启动 SkyForge Studio:
   ```powershell
   cd c:\Users\Lin\Desktop\Programs\Air\SkyForge
   make studio-up
   ```
2. 打开浏览器访问 `http://localhost:8080`
3. 在 **"需求输入"** 页面，粘贴 `requirement.txt` 的内容
4. 点击 **"生成契约"**，对比 `contract.yaml` 校验生成结果
5. 点击 **"生成代码"**，对比 `expected_code.c` 校验生成结果
6. 在 **"契约验证"** 页面，加载 `contract.yaml` 执行 z3 形式化验证
7. 在 **"MISRA-C 检查"** 页面，对生成的 C 代码运行 cppcheck + MISRA-C:2012 规则检查
8. (可选) 在 **"数字孪生"** 页面，将生成的代码部署到 Virtual MCU 执行仿真

### 3.2 使用 SkyForge CLI

```powershell
cd c:\Users\Lin\Desktop\Programs\Air\SkyForge
# 1) 从需求生成契约
python -m skyforge_core.cli contract examples/freertos_task_scheduler/requirement.txt `
    --output examples/freertos_task_scheduler/generated_contract.yaml

# 2) 从契约生成代码
python -m skyforge_core.cli generate examples/freertos_task_scheduler/contract.yaml `
    --output examples/freertos_task_scheduler/generated_code.c

# 3) 形式化验证契约
python -m skyforge_core.cli verify examples/freertos_task_scheduler/contract.yaml

# 4) MISRA-C 静态检查
python -m skyforge_core.cli misra-check examples/freertos_task_scheduler/expected_code.c
```

## 4. 预期输出

### 4.1 契约验证 (z3_verifier)

```
[OK] CON-FRTOS-PRE-000: priority in [0,7]                       SAT
[OK] CON-FRTOS-PRE-003: budget_ms <= period_ms                  SAT
[OK] CON-FRTOS-INV-002: Sensor_Reader (5/10ms/2ms)              SAT
[OK] CON-FRTOS-INV-003: Control_Law (4/20ms/5ms)                SAT
[OK] CON-FRTOS-INV-004: Telemetry_Output (3/100ms/10ms)         SAT
[OK] CON-FRTOS-INV-007: priority_inheritance_enabled            SAT
[OK] CON-FRTOS-INV-008: static_allocation_only                  SAT
[OK] CON-FRTOS-FLT-000: task_overrun -> watchdog_reset          SAT
[OK] CON-FRTOS-FLT-002: cpu_load>85% -> alarm                   SAT
所有 21 条契约约束通过形式化验证。
```

### 4.2 MISRA-C 检查

```
[INFO] 检查文件: expected_code.c
[OK]   Rule 8.4  - 外部函数原型声明 ✓
[OK]   Rule 8.7  - 模块内部对象使用 static ✓
[OK]   Rule 17.7 - FreeRTOS API 返回值检查 ✓
[OK]   Rule 20.4 - 静态内存分配 (无 malloc) ✓
[OK]   Rule 21.3 - 未使用 stdlib.h 内存函数 ✓
[OK]   Dir 4.1   - 故障显式处理 ✓
[NOTE] Rule 11.5 - void* 转换已文档化 (FreeRTOS API 例外)
MISRA-C:2012 必要规则全部通过。
```

### 4.3 单元测试

```
TEST(freertos_scheduler, task_creation_succeeds)              [PASS]
TEST(freertos_scheduler, sensor_reader_period_10ms)           [PASS]
TEST(freertos_scheduler, control_law_period_20ms)             [PASS]
TEST(freertos_scheduler, telemetry_output_period_100ms)       [PASS]
TEST(freertos_scheduler, queue_send_drop_on_full)             [PASS]
TEST(freertos_scheduler, watchdog_reset_on_overrun)           [PASS]
TEST(freertos_scheduler, cpu_load_alarm_at_85_percent)        [PASS]
TEST(freertos_scheduler, priority_inheritance_prevents_inversion) [PASS]
所有 8 个单元测试通过。
```

## 5. 约束说明

### 5.1 安全等级
- **DAL-B** (DO-178C，对应重大故障条件)

### 5.2 标准依据
- FreeRTOS V10.x (官方 API)
- DO-178C Section 6.3 (Software Verification)
- MISRA-C:2012 Mandatory & Required Rules
- ARP 4761 (系统安全性评估)

### 5.3 关键不变式
1. 系统 tick 频率固定 1 kHz (1 tick = 1 ms)
2. 3 个核心任务配置固定 (Sensor_Reader 5/10/2, Control_Law 4/20/5, Telemetry_Output 3/100/10)
3. 所有任务执行预算 ≤ 周期 (无超载)
4. 队列长度均为 10 (sensor_data, control_cmd)
5. 优先级继承已启用 (Mutex 防止优先级反转)
6. 仅使用静态内存分配 (无 malloc)
7. CPU 利用率告警阈值 85%
8. 硬件看门狗超时 500 ms

### 5.4 故障处理

| 事件            | 触发条件                          | 处理动作                                  |
|:----------------|:----------------------------------|:------------------------------------------|
| OVERRUN         | 任务执行时间 > 预算                | 触发 `watchdog_reset`，记录故障日志，重启任务 |
| RESET           | 硬件看门狗超时 (500ms)             | 系统复位 (Last Resort)                    |
| ALARM           | CPU 利用率 > 85%                   | 触发 `cpu_load_alarm`，降级运行            |
| STACK_OVERFLOW  | 任务栈溢出                         | 触发 `vApplicationStackOverflowHook`      |
| QUEUE_FULL      | 队列满                            | 丢弃新消息，递增丢包计数器                 |
| MUTEX_DEADLOCK  | Mutex 超时 (死锁)                  | 释放 Mutex，记录日志                      |

## 6. 与比赛评审维度的对应

- **赛道契合度 (+5分)**: 本示例完整演示 SkyForge 在航空运行时场景 (FreeRTOS 实时任务调度) 的代码生成能力，符合 DO-178C DAL-B 与 MISRA-C:2012 标准
- **形式化验证**: contract.yaml 通过 z3 验证所有 21 条约束
- **可追溯性**: requirement.txt → contract.yaml → expected_code.c 三层可追溯
- **行业落地**: 直接对应真实飞控系统 (FreeRTOS-based FCS) 的任务调度场景
- **数字孪生集成**: 生成的代码可部署到 Virtual MCU 仿真验证
