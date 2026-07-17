"""WebSocket 连接管理模块，支持心跳检测、进度推送和任务事件广播。"""

import asyncio
import logging
import time
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """WebSocket 连接管理器，维护活跃连接并提供消息广播功能。"""

    def __init__(self, heartbeat_interval: float = 30.0):
        self.active_connections: list[WebSocket] = []
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_task: asyncio.Task | None = None
        self._task_connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: str | None = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        if task_id:
            if task_id not in self._task_connections:
                self._task_connections[task_id] = set()
            self._task_connections[task_id].add(websocket)
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def disconnect(self, websocket: WebSocket, task_id: str | None = None):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if task_id and task_id in self._task_connections:
            self._task_connections[task_id].discard(websocket)
            if not self._task_connections[task_id]:
                del self._task_connections[task_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception:
            logger.warning("Failed to send personal message")

    async def send_personal_message_json(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception:
            logger.warning("Failed to send JSON message")

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.active_connections.remove(connection)

    async def send_task_event(self, task_id: str, event_type: str, data: Any = None):
        """Send a structured event to all connections watching a specific task."""
        payload = {
            "type": event_type,
            "task_id": task_id,
            "timestamp": time.time(),
            "data": data,
        }
        connections = self._task_connections.get(task_id, set())
        dead: list[WebSocket] = []
        for ws in list(connections):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            connections.discard(ws)
            if ws in self.active_connections:
                self.active_connections.remove(ws)

    async def send_task_progress(
        self,
        task_id: str,
        stage: str,
        progress: float,
        message: str = "",
    ):
        """Send pipeline progress update (0.0 ~ 1.0)."""
        await self.send_task_event(
            task_id,
            "progress",
            {
                "stage": stage,
                "progress": min(max(progress, 0.0), 1.0),
                "message": message,
            },
        )

    async def send_task_error(self, task_id: str, error: str, stage: str = ""):
        """Send structured error event."""
        await self.send_task_event(
            task_id,
            "error",
            {"error": error, "stage": stage},
        )

    async def _heartbeat_loop(self):
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            dead: list[WebSocket] = []
            for ws in list(self.active_connections):
                try:
                    await ws.send_json({"type": "ping", "ts": time.time()})
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.active_connections.remove(ws)
                for conns in self._task_connections.values():
                    conns.discard(ws)
            if not self.active_connections and self._heartbeat_task:
                self._heartbeat_task.cancel()
                self._heartbeat_task = None
                break


ws_manager = WebSocketManager()
