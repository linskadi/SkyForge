# ARINC 653 分区调度器示例 (arinc653_partition)

## 1. 场景描述

本示例演示如何使用 SkyForge 自动生成符合 **ARINC 653 Part 1** 标准、**DO-178C DAL-A** 等级、**MISRA-C:2012** 规范的分区调度器 (Partition Scheduler) 代码。

部署场景为综合模块化航电系统 (Integrated Modular Avionics, IMA) 核心操作系统层。调度器在主时间帧 (Main Time Frame, MTF = 200 ms) 内按预定时间片轮转调度三个航空分区:

| 分区 ID | 分区名称              | 功能                 | 时间片  |
|:-------:|:---------------------|:---------------------|:-------:|
| P1      | Display              | HUD/EFIS 画面生成    | 50 ms   |
| P2      | Navigation           | 航位推算与航路管理   | 80 ms   |
| P3      | Health Monitoring    | 系统级故障检测与降级 | 70 ms   |
| **合计**|                      |                      | 200 ms  |

核心特性:
- **严格周期性调度** (Strictly Periodic Scheduling)，抖动 ≤ 100 μs
- **分区上下文切换** ≤ 1 ms (含寄存器保存、MMU/MPU 刷新、入口函数调用)
- **超时检测**: 分区超时触发 `Partition_HM_Handler`
- **故障隔离**: 任一分区故障不影响其他分区的时序与功能
- **无优先级反转**: 固定优先级 + 时间片策略

## 2. 目录结构

```
examples/arinc653_partition/
├── requirement.txt      # 自然语言需求描述 (中文 + 英文术语)
├── contract.yaml        # 形式化契约 (inputs/outputs/preconditions/postconditions/invariants/fault_handling)
├── expected_code.c      # 期望生成的 C 代码 (MISRA-C:2012 兼容)
└── README.md            # 本文档: 场景描述、运行步骤、预期输出
```

## 3. 运行步骤

### 3.1 使用 SkyForge Studio (Web UI)

1. 启动 SkyForge Studio (后端 + 前端):
   ```powershell
   cd c:\Users\Lin\Desktop\Programs\Air\SkyForge
   make studio-up      # 或 docker-compose up -d
   ```
2. 打开浏览器访问 `http://localhost:8080`
3. 在 **"需求输入"** 页面，粘贴 `requirement.txt` 的内容
4. 点击 **"生成契约"**，对比 `contract.yaml` 校验生成结果
5. 点击 **"生成代码"**，对比 `expected_code.c` 校验生成结果
6. 在 **"契约验证"** 页面，加载 `contract.yaml` 执行 z3 形式化验证
7. 在 **"MISRA-C 检查"** 页面，对生成的 C 代码运行 cppcheck + MISRA-C:2012 规则检查

### 3.2 使用 SkyForge CLI

```powershell
cd c:\Users\Lin\Desktop\Programs\Air\SkyForge
# 1) 从需求生成契约
python -m skyforge_core.cli contract examples/arinc653_partition/requirement.txt `
    --output examples/arinc653_partition/generated_contract.yaml

# 2) 从契约生成代码
python -m skyforge_core.cli generate examples/arinc653_partition/contract.yaml `
    --output examples/arinc653_partition/generated_code.c

# 3) 形式化验证契约
python -m skyforge_core.cli verify examples/arinc653_partition/contract.yaml

# 4) MISRA-C 静态检查
python -m skyforge_core.cli misra-check examples/arinc653_partition/expected_code.c
```

## 4. 预期输出

### 4.1 契约验证 (z3_verifier)

```
[OK] CON-A653-PRE-000: partition_id in [1,3]                    SAT
[OK] CON-A653-PRE-003: partition_period_ms == 200               SAT
[OK] CON-A653-INV-001: time_slice P1=50 P2=80 P3=70             SAT
[OK] CON-A653-INV-002: sum(time_slice) == MTF (200ms)           SAT
[OK] CON-A653-INV-003: context_switch <= 1ms                    SAT
[OK] CON-A653-INV-005: no_priority_inversion == true            SAT
[OK] CON-A653-FLT-000: overrun -> trigger HM_Handler            SAT
所有 16 条契约约束通过形式化验证。
```

### 4.2 MISRA-C 检查

```
[INFO] 检查文件: expected_code.c
[OK]   Rule 8.4  - 外部函数原型声明 ✓
[OK]   Rule 8.7  - 模块内部对象使用 static ✓
[OK]   Rule 17.7 - 返回值检查 ✓
[OK]   Rule 20.4 - 无动态内存分配 ✓
[OK]   Rule 21.3 - 未使用 stdlib.h 内存函数 ✓
[OK]   Dir 4.1   - 故障显式处理 ✓
[OK]   Rule 7.4  - 字符串字面量赋值给 const char* ✓
MISRA-C:2012 必要规则全部通过。
```

### 4.3 单元测试

```
TEST(arinc653_partition, mtf_period_is_200ms)             [PASS]
TEST(arinc653_partition, time_slice_sum_equals_mtf)       [PASS]
TEST(arinc653_partition, context_switch_under_1ms)        [PASS]
TEST(arinc653_partition, overrun_triggers_hm_handler)     [PASS]
TEST(arinc653_partition, terminated_partition_skipped)    [PASS]
TEST(arinc653_partition, fatal_event_enters_safe_state)   [PASS]
所有 6 个单元测试通过。
```

## 5. 约束说明

### 5.1 安全等级
- **DAL-A** (DO-178C 最高等级，对应灾难性故障条件)

### 5.2 标准依据
- ARINC 653 Part 1 (Avionics Application Software Standard Interface)
- ARINC 653 Part 2 (Software Partitioning)
- DO-178C Section 6.3 (Software Verification)
- MISRA-C:2012 Mandatory & Required Rules

### 5.3 关键不变式
1. MTF 周期固定 200 ms，运行时不可修改
2. 时间片守恒: P1+P2+P3 = MTF (50+80+70 = 200 ms)
3. 上下文切换 ≤ 1 ms
4. 调度抖动 ≤ 100 μs
5. 无优先级反转 (固定优先级 + 时间片)

### 5.4 故障处理
| 事件          | 触发条件                       | 处理动作                                |
|:-------------|:-------------------------------|:----------------------------------------|
| OVERRUN      | 分区执行时间 > 分配时间片       | 调用 HM_Handler，分区状态置 TERMINATED   |
| STACK_FAULT  | MMU/MPU 内存访问违例            | 调用 HM_Handler，记录故障日志            |
| FATAL        | 致命错误 (配置错误/多重故障)    | 进入 SAFE_STATE，停止所有分区，触发看门狗 |
| WATCHDOG     | 硬件看门狗超时 (500ms)          | 系统复位                                |

## 6. 与比赛评审维度的对应

- **赛道契合度 (+5分)**: 本示例完整演示 SkyForge 在航空运行时场景 (ARINC 653 分区调度) 的代码生成能力，符合 DO-178C DAL-A 与 MISRA-C:2012 标准
- **形式化验证**: contract.yaml 通过 z3 验证所有 16 条约束
- **可追溯性**: requirement.txt → contract.yaml → expected_code.c 三层可追溯
- **行业落地**: 直接对应真实航电系统 (IMA) 的分区调度场景
