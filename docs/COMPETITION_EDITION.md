# SkyForge 比赛版实施说明

## 产品定位

比赛版的目标不是把所有工程能力堆进首屏，而是在三分钟内让评委看清一条可信链路：需求、契约、代码、MISRA 修复、数字孪生、追溯与证据摘要。

主演示使用 `演示模式（模拟）`。它完全在浏览器运行，不访问后端；所有事件、工具结果和报告都标为 `simulated`。云 API 与本地模型的实时任务通过 V1 Task API 执行，失败会显示失败或降级，不会静默替换成模拟成功。

## 三种来源

| Profile | 数据来源 | 现场策略 |
|---|---|---|
| demo | simulated | 主演示，完全离线 |
| cloud | live | 服务端实时执行；真实录制包缺失时显示 unavailable |
| local | live / replay | Ollama / LM Studio 实时执行；可读取已验证本地运行包 |

当前仓库包含一份真实本地 Ollama 日志的清单：`studio/recordings/local-qwen3-8b.manifest.json`。清单核验原始日志 SHA-256，并诚实记录其中仿真降级为 Python simulator。仓库尚无可证明的云 API 完整运行包和 1080p MP4，因此 UI 明确显示不可用；不得用演示数据补位。

## 唯一任务协议

- `POST /api/v1/tasks`：唯一创建入口，使用 `idempotency_key`。
- `GET /api/v1/tasks/{task_id}`：读取状态、完整产物与 provenance。
- `GET /api/v1/tasks`：运行记录。
- `POST /api/v1/tasks/{task_id}/cancel`：取消。
- `WS /api/v1/tasks/{task_id}/events?after_seq=N`：只订阅，支持事件续传，不创建任务。
- `GET /api/v1/execution-profiles` 与 `/preflight/{profile}`：可用性预检。
- `GET /api/v1/recordings` 与 `/recordings/{id}`：核验并读取离线运行包。

旧 `/api/generate` 与 `/ws/agent-stream` 保留兼容，但内部均委托 `TaskService`。任务主键为 `TASK-*`，需求编号 `REQ-*` 只存在于任务产物内。旧 `task_history` 会只读复制为 `legacy` 摘要，不删除原表；服务启动时残留任务会标为 `interrupted`。

## 证据规则

工具证据统一使用 `observed / simulated / unavailable / failed`。只有实际执行的确定性工具才记录版本、命令和退出码。缺失 Cppcheck 不等于零违规；未运行 Z3、覆盖率、ASan 或 HIL 不等于通过。证据包的固定声明为：SkyForge 提供 DO-178C 工程辅助证据，不代表工具已完成适航鉴定。

`HITL` 专指人工审查；`HIL` 专指 Hardware-in-the-Loop。旧 API 路径只为兼容保留。

## 三分钟演示词

1. 0–20 秒：首页说明模拟来源，点击“开始 3 分钟演示”。
2. 20–45 秒：指出 AI Agent 负责生成，确定性工具负责验证。
3. 45–90 秒：完成后直接看 `4 → 0` 修复 Diff，以及契约到代码和测试的关联。
4. 90–130 秒：在“仿真”中切换正常波形和一次卡死故障。
5. 130–165 秒：切换“追溯”，讲清 REQ / LLR / CON / CODE / TST。
6. 165–180 秒：打开“证据”，再到运行记录展示本地已验证包的 SHA-256；说明云包和 MP4 尚待真实采集。

## 验收命令

```powershell
cd studio/frontend
pnpm test
pnpm build

cd ../..
$env:PYTHONPATH="studio;src"
.\.venv\Scripts\python.exe -m pytest studio/app/tests/test_tasks_v1.py
.\.venv\Scripts\python.exe tools/scripts/generate_project_metrics.py --output docs/generated/project_metrics.json
```

浏览器验收已覆盖 1440×810、1366×768、1920×1080。1440×810 完成态中，终端自动收至 38px，五项摘要指标位于首屏；1366×768 中五项摘要仍位于首屏，详细标签内容可继续向下浏览。

## 2026-07-19 验收结果

- 前端 Vitest：14 个测试文件、167 项全部通过。
- `vue-tsc -b && vite build`：生产构建通过；仍有 Monaco 大分块和旧 Browserslist 数据的非阻断警告。
- 后端 `studio/app/tests`：259 项全部通过，另有 14 个 subtests；仅保留 Redis `close()` 弃用警告。
- 浏览器关闭后端实测：首页、HITL 与完整演示均无 `Failed to fetch`；完成态包含 `4 → 0`、100% 追溯和五个证据标签。
- 自动统计写入 `docs/generated/project_metrics.json`，文档不再手工维护 API 与测试定义数量。
