"""StreamManager：管理 WebSocket 连接池，支持广播和定向推送。

用于 Patch 4 Agent 思考流式推送：
- register(websocket)：注册新连接（已 accept），返回唯一 ID
- unregister(websocket_id)：注销连接
- broadcast(message)：广播 JSON 消息到所有活跃连接
- send_to(websocket_id, message)：定向推送到单个连接

支持多个前端同时连接（如多标签页 / 多用户观察同一 pipeline）。
对断开的连接自动清理，避免阻塞广播。
"""

import asyncio
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.utils.log_util import logger


class StreamManager:
    """WebSocket 连接池管理器。

    Attributes:
        _connections: websocket_id -> WebSocket 的映射。
        _lock: 保护 _connections 的异步锁。
    """

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def register(self, websocket: WebSocket) -> str:
        """注册一个新的 WebSocket 连接。

        调用方应在调用本方法前先 await websocket.accept()，
        或由本方法负责 accept（默认行为：本方法不重复 accept）。

        Args:
            websocket: 已 accept 的 WebSocket 实例。

        Returns:
            该连接的唯一 ID（uuid4 hex）。
        """
        ws_id = uuid.uuid4().hex
        async with self._lock:
            self._connections[ws_id] = websocket
        logger.info(
            f"StreamManager:注册连接 {ws_id}，当前活跃 {len(self._connections)} 个"
        )
        return ws_id

    async def unregister(self, websocket_id: str) -> None:
        """注销指定 ID 的连接。

        Args:
            websocket_id: register() 返回的连接 ID。
        """
        async with self._lock:
            removed = self._connections.pop(websocket_id, None)
        if removed is not None:
            logger.info(
                f"StreamManager:注销连接 {websocket_id}，"
                f"当前活跃 {len(self._connections)} 个"
            )

    async def send_to(self, websocket_id: str, message: dict[str, Any]) -> bool:
        """向指定连接推送 JSON 消息。

        Args:
            websocket_id: 目标连接 ID。
            message: 待推送的 JSON 可序列化字典。

        Returns:
            True 表示推送成功；False 表示连接不存在或已断开（已自动清理）。
        """
        async with self._lock:
            websocket = self._connections.get(websocket_id)
        if websocket is None:
            return False
        try:
            await websocket.send_json(message)
            return True
        except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
            logger.warning(f"StreamManager:推送失败，清理连接 {websocket_id}: {e}")
            await self.unregister(websocket_id)
            return False

    async def broadcast(self, message: dict[str, Any]) -> int:
        """广播 JSON 消息到所有活跃连接。

        Args:
            message: 待广播的 JSON 可序列化字典。

        Returns:
            成功推送的连接数。
        """
        async with self._lock:
            items = list(self._connections.items())
        success = 0
        dead_ids: list[str] = []
        for ws_id, ws in items:
            try:
                await ws.send_json(message)
                success += 1
            except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
                logger.warning(f"StreamManager:广播失败，标记清理 {ws_id}: {e}")
                dead_ids.append(ws_id)
        # 清理已断开的连接
        for ws_id in dead_ids:
            await self.unregister(ws_id)
        return success

    def count(self) -> int:
        """返回当前活跃连接数。"""
        return len(self._connections)


# 全局单例
_stream_manager: StreamManager | None = None


def get_stream_manager() -> StreamManager:
    """获取 StreamManager 全局单例。"""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager()
    return _stream_manager
