# -*- coding: utf-8 -*-
"""TaskStreamRegistry：按 task_id 管理 WebSocket 订阅者集合 + 历史日志缓存。

用途：让 Dashboard 点击 running 任务时，前端能"订阅"已有运行中的 pipeline，
接收实时 Agent 思考流，而不会触发新的 pipeline。

核心 API：
- register_task(task_id)：声明一个 task 开始广播（主 pipeline 路由调用）
- add_subscriber(task_id, websocket)：把订阅者 WS 加入集合，立即回放历史日志
- remove_subscriber(task_id, websocket)：从集合移除（连接断开时调用）
- broadcast(task_id, message)：向该 task 的所有订阅者推送消息，并追加到历史
- finish_task(task_id)：标记 task 完成（保留历史 N 秒供迟到订阅者拉取）
- is_active(task_id)：判断 task 是否仍在运行

线程安全：所有操作在 asyncio.Lock 保护下进行。

L0 适配说明：
- ``WebSocket`` 类型注解改为 ``WebSocketProtocol`` (Protocol)，L0 不硬依赖 fastapi
- ``WebSocketDisconnect`` 可选导入：fastapi 可用时与原行为一致；
  不可用时（L0 独立运行）回退到 ``(RuntimeError, ConnectionError)`` 兜底
"""

import asyncio
import time
from typing import Any, Optional, Protocol, runtime_checkable

from skyforge_engine.utils.log_util import logger

# task 完成后历史日志保留时长（秒）。超过后从内存清除。
# 让迟到的订阅者（例如完成瞬间点击进入）仍能看到完整日志。
_TASK_HISTORY_TTL_SEC = 300

# 单 task 历史日志上限，避免极端长 pipeline 占用过多内存。
_MAX_HISTORY_PER_TASK = 5000


# 运行时尝试导入 fastapi 的 WebSocketDisconnect，不可用时回退到通用异常元组。
# 这样 L0 在有 fastapi 的环境（L3 studio）下与原行为完全一致；在 L0 独立运行
# （无 fastapi）时也能工作 —— 此时 WebSocket 类型本身不会出现，所以也不会
# 抛出 WebSocketDisconnect。
try:  # pragma: no cover - 取决于运行环境
    from fastapi import WebSocketDisconnect as _WebSocketDisconnect

    _WS_SEND_EXCEPTIONS: tuple[type[BaseException], ...] = (
        _WebSocketDisconnect,
        RuntimeError,
        ConnectionError,
    )
except ImportError:  # pragma: no cover - L0 独立运行无 fastapi
    _WS_SEND_EXCEPTIONS = (RuntimeError, ConnectionError)


@runtime_checkable
class WebSocketProtocol(Protocol):
    """WebSocket 最小接口协议（duck typing）。

    L0 不硬依赖 ``fastapi.WebSocket``；任何实现了 ``send_json`` 协程方法
    的对象都满足此协议（``fastapi.WebSocket`` 即满足）。``starlette.WebSocket``
    与测试中常用的 fake WS 对象也满足。
    """

    async def send_json(self, message: dict[str, Any]) -> None: ...


class _TaskState:
    """单个 task 的运行时状态。"""

    __slots__ = ("task_id", "subscribers", "history", "started_at", "finished_at")

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self.subscribers: set[WebSocketProtocol] = set()
        self.history: list[dict[str, Any]] = []
        self.started_at: float = time.time()
        self.finished_at: Optional[float] = None

    def is_active(self) -> bool:
        return self.finished_at is None


class TaskStreamRegistry:
    """task_id → 运行时状态的注册表（全局单例）。"""

    def __init__(self) -> None:
        self._tasks: dict[str, _TaskState] = {}
        self._lock = asyncio.Lock()

    async def register_task(self, task_id: str) -> None:
        """主 pipeline 启动时调用：声明一个 task 开始广播。"""
        async with self._lock:
            if task_id not in self._tasks:
                self._tasks[task_id] = _TaskState(task_id)
                logger.info(
                    f"TaskStreamRegistry: 注册 task {task_id}，"
                    f"当前活跃 task 数 {self._active_count()}"
                )
            else:
                # 同 task_id 重复注册（罕见）：重置 finished_at 以重新激活
                self._tasks[task_id].finished_at = None

    async def add_subscriber(
        self, task_id: str, websocket: WebSocketProtocol, after_seq: int = 0
    ) -> bool:
        """把订阅者 WS 加入 task 的订阅者集合，并回放历史日志。

        Returns:
            True 表示 task 存在（活跃或刚完成），订阅者已加入；
            False 表示 task 不存在（无运行中的 pipeline），调用方应处理 fallback。
        """
        async with self._lock:
            state = self._tasks.get(task_id)
            if state is None:
                return False
            state.subscribers.add(websocket)
            history_snapshot = [
                message
                for message in state.history
                if not isinstance(message.get("seq"), int)
                or int(message["seq"]) > after_seq
            ]
        logger.info(
            f"TaskStreamRegistry: 订阅 task {task_id}，"
            f"回放 {len(history_snapshot)} 条历史日志"
        )
        # 在锁外回放历史日志，避免阻塞其他 task
        for msg in history_snapshot:
            try:
                await websocket.send_json(msg)
            except _WS_SEND_EXCEPTIONS:
                await self.remove_subscriber(task_id, websocket)
                return False
        return True

    async def remove_subscriber(
        self, task_id: str, websocket: WebSocketProtocol
    ) -> None:
        """从 task 的订阅者集合移除 WS（连接断开时调用）。"""
        async with self._lock:
            state = self._tasks.get(task_id)
            if state is None:
                return
            state.subscribers.discard(websocket)

    async def broadcast(self, task_id: str, message: dict[str, Any]) -> None:
        """向 task 的所有订阅者推送消息，并追加到历史日志。

        死连接会被自动清理。
        """
        async with self._lock:
            state = self._tasks.get(task_id)
            if state is None:
                # task 未注册（不应发生）：丢弃消息
                return
            if len(state.history) < _MAX_HISTORY_PER_TASK:
                state.history.append(message)
            subscribers = list(state.subscribers)

        dead: list[WebSocketProtocol] = []
        for ws in subscribers:
            try:
                await ws.send_json(message)
            except _WS_SEND_EXCEPTIONS:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    state.subscribers.discard(ws)

    async def finish_task(self, task_id: str) -> None:
        """主 pipeline 完成时调用：标记完成，保留历史日志 TTL 秒。"""
        async with self._lock:
            state = self._tasks.get(task_id)
            if state is None:
                return
            state.finished_at = time.time()
            logger.info(
                f"TaskStreamRegistry: task {task_id} 完成，"
                f"历史日志保留 {self._history_ttl_remaining(state):.1f}s"
            )

    async def is_active(self, task_id: str) -> bool:
        """判断 task 是否仍在运行（未完成）。"""
        async with self._lock:
            state = self._tasks.get(task_id)
            return state is not None and state.is_active()

    async def cleanup_expired(self) -> int:
        """清理已超期的历史日志（finished_at + TTL 已过）。返回清理数量。"""
        now = time.time()
        expired_ids: list[str] = []
        async with self._lock:
            for tid, state in self._tasks.items():
                if (
                    state.finished_at is not None
                    and now - state.finished_at > _TASK_HISTORY_TTL_SEC
                ):
                    expired_ids.append(tid)
            for tid in expired_ids:
                self._tasks.pop(tid, None)
        if expired_ids:
            logger.info(
                f"TaskStreamRegistry: 清理 {len(expired_ids)} 个超期 task 历史"
            )
        return len(expired_ids)

    def _active_count(self) -> int:
        return sum(1 for s in self._tasks.values() if s.is_active())

    def _history_ttl_remaining(self, state: _TaskState) -> float:
        if state.finished_at is None:
            return float(_TASK_HISTORY_TTL_SEC)
        return max(
            0.0,
            float(_TASK_HISTORY_TTL_SEC) - (time.time() - state.finished_at),
        )


# 全局单例
_task_stream_registry: Optional[TaskStreamRegistry] = None


def get_task_stream_registry() -> TaskStreamRegistry:
    """获取 TaskStreamRegistry 全局单例。"""
    global _task_stream_registry
    if _task_stream_registry is None:
        _task_stream_registry = TaskStreamRegistry()
    return _task_stream_registry


__all__ = [
    "TaskStreamRegistry",
    "WebSocketProtocol",
    "get_task_stream_registry",
]
