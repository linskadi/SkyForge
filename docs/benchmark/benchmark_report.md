# SkyForge 性能基准测试报告

> 自动生成于 `tools/benchmark/run_benchmark.py`，请勿手动编辑。

## 1. 概览

| 项目 | 值 |
| --- | --- |
| 测试开始时间 | 2026-07-17 18:01:23 |
| 测试结束时间 | 2026-07-17 18:01:24 |
| 总耗时 | 0.991 秒 |
| 操作系统 | Windows 11 (AMD64) |
| Python 版本 | 3.12.13 |
| psutil 版本 | 7.2.2 |
| 示例数量 | 12 |
| 运行模式 | Mock（USE_LLM=false, HIL=false, GCC/Cppcheck Mock） |

## 2. 响应时间基准

| # | 示例文件 | 耗时 (s) | 状态 |
| --- | --- | --- | --- |
| 1 | arinc653_partition.txt | 0.013 | ✅ 成功 |
| 2 | cpp_smart_pointer_manager.txt | 0.004 | ✅ 成功 |
| 3 | crc_handler.txt | 0.004 | ✅ 成功 |
| 4 | dead_reckoning.txt | 0.007 | ✅ 成功 |
| 5 | filter_requirements.txt | 0.005 | ✅ 成功 |
| 6 | freertos_task_scheduler.txt | 0.004 | ✅ 成功 |
| 7 | hmi_overlay.txt | 0.005 | ✅ 成功 |
| 8 | mission_planning.txt | 0.005 | ✅ 成功 |
| 9 | pid_controller.txt | 0.005 | ✅ 成功 |
| 10 | power_monitor.txt | 0.005 | ✅ 成功 |
| 11 | rust_concurrent_data_pipeline.txt | 0.006 | ✅ 成功 |
| 12 | sensor_fusion.txt | 0.004 | ✅ 成功 |

## 3. 资源消耗

| # | 示例文件 | 内存峰值 (MB) | CPU 使用率 (%) | 生成代码长度 |
| --- | --- | --- | --- | --- |
| 1 | arinc653_partition.txt | 64.19 | 0.0 | 767 |
| 2 | cpp_smart_pointer_manager.txt | 64.21 | 0.0 | 1166 |
| 3 | crc_handler.txt | 64.23 | 0.0 | 767 |
| 4 | dead_reckoning.txt | 64.25 | 0.0 | 3657 |
| 5 | filter_requirements.txt | 64.25 | 0.0 | 1166 |
| 6 | freertos_task_scheduler.txt | 64.25 | 0.0 | 767 |
| 7 | hmi_overlay.txt | 64.26 | 0.0 | 1154 |
| 8 | mission_planning.txt | 64.27 | 0.0 | 1154 |
| 9 | pid_controller.txt | 64.27 | 0.0 | 1166 |
| 10 | power_monitor.txt | 64.27 | 0.0 | 3657 |
| 11 | rust_concurrent_data_pipeline.txt | 64.27 | 0.0 | 5628 |
| 12 | sensor_fusion.txt | 64.29 | 0.0 | 1166 |

## 4. 成功率统计

| 指标 | 值 |
| --- | --- |
| 总示例数 | 12 |
| 成功数 | 12 |
| 失败数 | 0 |
| 成功率 | 100.0% |

## 5. 汇总指标

### 5.1 响应时间 (秒)

| 指标 | 值 |
| --- | --- |
| 平均值 (avg) | 0.006 |
| 中位数 (median) | 0.005 |
| 最小值 (min) | 0.004 |
| 最大值 (max) | 0.013 |
| 标准差 (stdev) | 0.003 |
| P95 | 0.01 |
| P99 | 0.012 |

### 5.2 内存与 CPU

| 指标 | 值 |
| --- | --- |
| 平均内存峰值 (MB) | 64.25 |
| 最高内存峰值 (MB) | 64.29 |
| 平均 CPU 使用率 (%) | 0.0 |

### 5.3 产物统计

| 指标 | 值 |
| --- | --- |
| 生成代码总字符数 | 22215 |
| Cppcheck 违规总数 (Mock) | 20 |

## 6. 结论

在 Mock 模式下对 12 个机载软件需求示例完成基准测试，部署成功率为 **100.0%**（12/12）。 单示例平均响应时间 **0.006s**，中位数 **0.005s**，P95 **0.01s**，全部示例总耗时 **0.99s**。 运行期内存峰值平均 **64.25MB**，最高 **64.29MB**，平均 CPU 使用率 **0.0%**。 数据表明 SkyForge 在无 LLM / 无真实工具链的降级模式下仍可稳定完成需求→契约→代码→静态扫描的完整流水线，满足航空软件工程比赛"落地可行性"维度的量化评估需求。

---
*报告由 `run_benchmark.py` 于 2026-07-17 18:01:24 自动生成。*
