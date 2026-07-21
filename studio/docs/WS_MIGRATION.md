# WebSocket 通道迁移指南 (Phase 5)

> 适用版本：SkyForge V1.x → V2.0
> 状态：旧通道已标记 deprecated；V1 通道成为唯一推荐的实时事件通道

## 背景

SkyForge 此前同时存在两个 WebSocket 通道，功能重叠且消息格式不统一：

| 通道 | 路径 | 用途 |
| --- | --- | --- |
| **旧（legacy）** | `WS /ws/agent-stream` | 单一 socket 同时创建任务 + 推送事件流 |
| **新（V1，推荐）** | `POST /api/v1/tasks` + `WS /api/v1/tasks/{task_id}/events` | 一个 HTTP 创建 + 一个只读 WS 订阅 |

Phase 5 的目标：

- 保留旧通道 **一个发布周期** 的兼容窗口，立即向客户端发送 deprecation 警告。
- 把 V1 通道作为**唯一推荐**的实时事件通道（也是未来 V2.0 的唯一通道）。
- 前端默认走 V1；V1 失败时自动回退到旧通道，确保不破坏现有用户。

## 旧通道何时被删除？

**V2.0 正式发布时** 移除 `WS /ws/agent-stream`：

- 在 V1.x 期间：旧通道仍然可用，但客户端在连接时立即收到一条
  `type: "deprecation_warning"` 消息，包含迁移提示和目标 URL。
- 在 V2.0 起：删除 `studio/app/api/routes/generate.py` 中的 `@router.websocket("/ws/agent-stream")`
  端点及其相关前端入口（`connectAgentStream` 的生成模式路径）。
- 计划日期：V2.0 GA（见 `docs/ROADMAP.md`）。

## 后端改动概览

文件：`studio/app/api/routes/generate.py`

- 模块顶部 docstring 已标记为 DEPRECATED。
- 新增常量 `DEPRECATION_MIGRATION_URL = "/api/v1/tasks/{task_id}/events"`。
- `agent_stream` 端点 `accept()` 后立即发送一条 deprecation 警告消息：

  ```json
  {
    "type": "deprecation_warning",
    "level": "warn",
    "agent": "SYSTEM",
    "message": "/ws/agent-stream is deprecated, use /api/v1/tasks/{task_id}/events instead",
    "migration": "/api/v1/tasks/{task_id}/events"
  }
  ```

  警告发送后，旧 socket 仍按原行为运行（创建 task + 复用 TaskService 执行 +
  共享 `TaskStreamRegistry` 推送事件），确保一次性兼容。

## 前端改动概览

### 1. 新增 V1 客户端入口

文件：`studio/frontend/src/services/mockApi.ts`

- 新增 `connectV1TaskEvents(taskId, onLog, onDone, afterSeq, wsBaseOverride?)`：
  订阅 `WS /api/v1/tasks/{task_id}/events?after_seq=...`，统一推送 AgentLog。
- 新增 `createTaskAndSubscribeV1(requirement, language, profileId, onLog, onDone?)`：
  推荐入口，POST `/api/v1/tasks` 后自动订阅 events，返回 `{ taskId, stop }`。
- `DEFAULT_WS_URL` 保留为旧通道 URL（fallback 路径），但 docstring 已标记 DEPRECATED。

### 2. AgentTerminal 通道选择

文件：`studio/frontend/src/components/AgentTerminal.vue`

新增 props：

```ts
channelMode?: "v1" | "legacy";  // 默认 "v1"
```

行为：

- `subscribeTaskId` 已设置时：直接走 V1 events 通道（只订阅，不创建）。
- 显式 `channelMode="legacy"`：直接走旧 `/ws/agent-stream` 通道。
- 默认 `channelMode="v1"` + 无 `subscribeTaskId`：
  1. POST `/api/v1/tasks` 创建 task。
  2. 连接 V1 events 通道。
  3. 5 秒内未收到任何事件或 POST 失败 → 自动回退到旧通道。
- `stopAll()` 会阻止延迟回退，避免重置/卸载后还触发 fallback。

### 3. Generate.vue 切换到 V1

文件：`studio/frontend/src/views/Generate.vue`

- 显式给 AgentTerminal 传 `channel-mode="v1"`，确保新生成任务走 V1。
- 旧通道作为 AgentTerminal 内部 fallback；UI 无需感知。

## 客户端迁移清单

如果你在外部脚本或第三方客户端使用旧通道，按以下步骤迁移：

| 旧调用 | 新调用 |
| --- | --- |
| `new WebSocket("ws://host/ws/agent-stream")` 然后 `send({requirement, language})` | 先 `fetch("POST /api/v1/tasks", {body: {requirement, language, profile_id, idempotency_key}})`，再 `new WebSocket("ws://host/api/v1/tasks/{task_id}/events")` |
| `send({action: "subscribe", task_id})` | 直接 `new WebSocket("ws://host/api/v1/tasks/{task_id}/events")`（订阅是默认行为） |

事件消息格式变化（V1 通道）：

```json
{
  "seq": 1,
  "stage": "requirement",
  "level": "info",
  "agent": "REQ-Parser",
  "message": "...",
  "evidence_status": "simulated",
  "created_at": "2026-07-20T08:00:00Z"
}
```

不再使用旧通道中的 `agent/agent_name` 兼容字段（`connectV1TaskEvents` 已统一映射）。

## 兼容性策略

- **V1.x 客户端**：旧通道收到 deprecation 警告后，可选择立即升级或继续使用。
- **V1.x 浏览器自动回退**：AgentTerminal 5s 内无 V1 输出或 POST 失败时自动
  连接旧通道，**对用户无感**。
- **V2.0 客户端**：必须迁移到 V1 通道；旧通道返回 404。

## 测试覆盖

- 后端：现有 `studio/app/tests/test_websocket.py` 继续通过（deprecation 警告是
  一条 JSON 消息，不破坏既有断言）。
- 前端：`studio/frontend/src/components/__tests__/AgentTerminal.test.ts` 已更新
  模拟 `connectV1TaskEvents` 和 `createTaskAndSubscribeV1`。

## 联系

如有问题或需要延长兼容窗口，请联系 SkyForge 维护团队，并在工单中引用
"Phase 5: WebSocket Channel Unification"。
