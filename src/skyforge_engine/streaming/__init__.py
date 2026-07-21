# -*- coding: utf-8 -*-
"""L0 流式推送模块 — TaskStreamRegistry。

按 task_id 管理 WebSocket 订阅者集合 + 历史日志缓存，让 Dashboard 点击
running 任务时前端能"订阅"已有运行中的 pipeline，接收实时 Agent 思考流，
而不会触发新的 pipeline。

本模块原位于 ``studio/app/core/streaming/task_stream_registry.py``（L3），
2026-07 重构后提升到 L0：

- 用 ``WebSocketProtocol`` (Protocol) 替代 ``fastapi.WebSocket`` 类型注解，
  使 L0 不硬依赖 fastapi
- ``WebSocketDisconnect`` 改为可选导入：fastapi 可用时与原行为一致；
  不可用时回退到 ``(RuntimeError, ConnectionError)`` 兜底
- ``logger`` 改为从 ``skyforge_engine.utils.log_util`` 导入（L0 内部）

L3 ``studio/app/core/streaming/task_stream_registry.py`` 改为转发 shim，
保证既有 ``from app.core.streaming.task_stream_registry import ...`` 引用兼容。
"""

from skyforge_engine.streaming.task_stream_registry import (
    TaskStreamRegistry,
    WebSocketProtocol,
    get_task_stream_registry,
)

__all__ = [
    "TaskStreamRegistry",
    "WebSocketProtocol",
    "get_task_stream_registry",
]
