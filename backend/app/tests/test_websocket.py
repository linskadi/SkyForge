# -*- coding: utf-8 -*-
"""WebSocket 流式推送测试（Patch 4）。

测试覆盖：
- test_websocket_connection：WebSocket 连接建立与断开
- test_websocket_stream_pipeline：发送需求 → 接收流式消息 → 接收完成消息
- test_stream_manager：StreamManager 注册 / 注销 / 广播 / 定向推送

使用 FastAPI TestClient 的 websocket_connect 进行真实 WebSocket 链路测试。
LM Studio 不可用时使用 Mock 消息（USE_LLM=false），不会发起真实 LLM 调用。
"""

import asyncio
import os
import unittest
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

# ---- 在导入 app 之前设置环境变量，避免触发真实 LM Studio 调用 ----
os.environ["USE_LLM"] = "false"
os.environ["LMSTUDIO_BASE_URL"] = "http://localhost:9999/v1"
os.environ["HIL_ENABLED"] = "false"
os.environ["HIL_TIMEOUT"] = "300"

from app.core.llm import lmstudio_client as lmstudio_module  # noqa: E402
from app.core.llm.model_router import reset_model_router  # noqa: E402
from app.core.hil.hil_manager import reset_hil_manager  # noqa: E402
from app.core.streaming import StreamManager, get_stream_manager  # noqa: E402
from app.main import app  # noqa: E402


def _reset_singletons() -> None:
    """重置 HIL / ModelRouter / LMStudio / StreamManager 单例。"""
    reset_hil_manager()
    reset_model_router()
    lmstudio_module._unified_client = None
    # 重置 StreamManager 单例，避免测试间连接池污染
    import app.core.streaming.stream_manager as sm_module

    sm_module._stream_manager = None


class TestWebSocketConnection(unittest.TestCase):
    """WebSocket 连接建立与断开测试。"""

    @classmethod
    def setUpClass(cls) -> None:
        _reset_singletons()
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def setUp(self) -> None:
        _reset_singletons()

    def tearDown(self) -> None:
        _reset_singletons()

    def test_websocket_connection(self) -> None:
        """WebSocket 连接建立后立即断开，不应抛异常。"""
        with self.client.websocket_connect("/ws/agent-stream"):
            # 连接建立成功；不做任何收发，直接关闭
            pass
        # 退出 with 块后连接应被正常清理，StreamManager 中无残留连接
        sm = get_stream_manager()
        self.assertEqual(sm.count(), 0)


class TestWebSocketStreamPipeline(unittest.TestCase):
    """WebSocket 流式 pipeline 测试：发送需求 → 接收流式消息 → 接收完成消息。"""

    @classmethod
    def setUpClass(cls) -> None:
        _reset_singletons()
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def setUp(self) -> None:
        _reset_singletons()

    def tearDown(self) -> None:
        _reset_singletons()

    def test_websocket_stream_pipeline(self) -> None:
        """发送需求 → 接收多条流式消息 → 末尾收到 level=complete 完成消息。"""
        with self.client.websocket_connect("/ws/agent-stream") as websocket:
            websocket.send_json({"requirement": "实现一个低通滤波器，截止频率 10Hz"})

            messages: list[dict] = []
            # 接收消息直到拿到 complete；设置上限避免无限等待
            for _ in range(200):
                msg = websocket.receive_json()
                self.assertIsInstance(msg, dict, "消息应为 dict")
                # 校验消息格式与前端 AgentTerminal.vue 对齐
                self.assertIn("level", msg, "消息缺少 level 字段")
                self.assertIn("agent", msg, "消息缺少 agent 字段")
                self.assertIn("time", msg, "消息缺少 time 字段")
                messages.append(msg)
                if msg.get("level") == "complete":
                    break

            # 至少应有 1 条流式消息 + 1 条 complete 完成消息
            self.assertGreaterEqual(
                len(messages), 2, "应至少收到 2 条消息（流式 + 完成）"
            )

            # 末尾消息应为 complete
            complete_msg = messages[-1]
            self.assertEqual(complete_msg["level"], "complete")
            self.assertIn("result", complete_msg, "完成消息应携带 result 字段")
            self.assertIsInstance(complete_msg["result"], dict, "result 应为 dict")

            # 流式消息（除末尾 complete 外）的 level 应属于前端 LogLevel 集合
            valid_levels = {"info", "success", "warn", "error", "complete"}
            for m in messages:
                self.assertIn(
                    m["level"],
                    valid_levels,
                    f"非法 level: {m['level']}",
                )

            # 流式消息的 agent 应属于前端 AgentType 集合
            valid_agents = {
                "REQ-Parser",
                "CON-Gen",
                "CODE-Gen",
                "REPAIR",
                "SYSTEM",
                "TERMINAL",
            }
            for m in messages:
                self.assertIn(
                    m["agent"],
                    valid_agents,
                    f"非法 agent: {m['agent']}",
                )

            # result 应包含核心产物字段
            result = complete_msg["result"]
            for key in ("requirement", "contract", "final_code"):
                self.assertIn(key, result, f"result 缺少字段 {key}")

        # 连接断开后 StreamManager 应无残留
        sm = get_stream_manager()
        self.assertEqual(sm.count(), 0)


class TestStreamManager(unittest.TestCase):
    """StreamManager 注册 / 注销 / 广播 / 定向推送测试。"""

    def setUp(self) -> None:
        _reset_singletons()

    def tearDown(self) -> None:
        _reset_singletons()

    def test_stream_manager(self) -> None:
        """注册 → 定向推送 → 广播 → 注销 → 推送失败回退。"""
        sm = StreamManager()
        self.assertEqual(sm.count(), 0)

        # ---- 注册 2 个 mock 连接 ----
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        id1 = asyncio.run(sm.register(ws1))
        id2 = asyncio.run(sm.register(ws2))
        self.assertEqual(sm.count(), 2)
        self.assertNotEqual(id1, id2)
        self.assertEqual(len(id1), 32)  # uuid4 hex 长度

        # ---- 定向推送 ----
        ok = asyncio.run(sm.send_to(id1, {"hello": "ws1"}))
        self.assertTrue(ok)
        ws1.send_json.assert_awaited_once_with({"hello": "ws1"})
        ws2.send_json.assert_not_awaited()

        # 推送到不存在的 id 应返回 False
        ok = asyncio.run(sm.send_to("nonexistent-id", {"x": 1}))
        self.assertFalse(ok)

        # ---- 广播 ----
        n = asyncio.run(sm.broadcast({"event": "ping"}))
        self.assertEqual(n, 2)
        # 两个连接都应收到
        ws1.send_json.assert_awaited_with({"event": "ping"})
        ws2.send_json.assert_awaited_with({"event": "ping"})

        # ---- 注销 ----
        asyncio.run(sm.unregister(id1))
        self.assertEqual(sm.count(), 1)
        # 注销后广播应只送达剩余连接
        n = asyncio.run(sm.broadcast({"event": "pong"}))
        self.assertEqual(n, 1)
        ws2.send_json.assert_awaited_with({"event": "pong"})

        # 再次注销已不存在的 id 不应抛异常
        asyncio.run(sm.unregister(id1))
        self.assertEqual(sm.count(), 1)

        # ---- 自动清理断开的连接 ----
        # ws2 模拟 send_json 抛 RuntimeError
        ws2.send_json.side_effect = RuntimeError("connection closed")
        ok = asyncio.run(sm.send_to(id2, {"will": "fail"}))
        self.assertFalse(ok)
        # 发生异常的连接应被自动清理
        self.assertEqual(sm.count(), 0)

        # 广播时无连接应返回 0
        n = asyncio.run(sm.broadcast({"event": "empty"}))
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
