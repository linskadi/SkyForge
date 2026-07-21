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
os.environ["LOCAL_LLM_BASE_URL"] = "http://localhost:9999/v1"
os.environ["HIL_ENABLED"] = "false"
os.environ["HIL_TIMEOUT"] = "300"

from app.core.llm import local_llm_client as lmstudio_module  # noqa: E402
from app.core.llm.model_router import reset_model_router  # noqa: E402
from app.core.hil.hil_manager import reset_hil_manager  # noqa: E402
from app.core.streaming import StreamManager, get_stream_manager  # noqa: E402
from app.main import app  # noqa: E402


def _reset_singletons() -> None:
    """重置 HIL / ModelRouter / LMStudio / StreamManager / TaskStreamRegistry 单例。"""
    reset_hil_manager()
    reset_model_router()
    lmstudio_module._unified_client = None
    # 重置 StreamManager 单例，避免测试间连接池污染
    import app.core.streaming.stream_manager as sm_module

    sm_module._stream_manager = None
    # 重置 TaskStreamRegistry 单例，避免测试间 task 状态污染
    import app.core.streaming.task_stream_registry as tsr_module

    tsr_module._task_stream_registry = None


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
                "LLR-Gen",
                "ARCH-Designer",
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


class TestWebSocketSubscribeMode(unittest.TestCase):
    """WebSocket 订阅模式测试：订阅已有运行中的 task，不启动新 pipeline。"""

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

    def test_subscribe_nonexistent_task_returns_error(self) -> None:
        """订阅不存在的 task_id 应推送 error 消息（fallback 路径）。"""
        with self.client.websocket_connect("/ws/agent-stream") as websocket:
            # Phase 5: 旧通道会在 accept 后立即推送一条 deprecation_warning
            # （level=warn），先消费掉这条以保持向后兼容契约。
            first = websocket.receive_json()
            self.assertEqual(first.get("type"), "deprecation_warning")
            websocket.send_json(
                {"task_id": "REQ-nonexistent-9999", "action": "subscribe"}
            )
            # 应该收到一条 error 消息（task 不存在）
            msg = websocket.receive_json()
            self.assertIsInstance(msg, dict)
            self.assertEqual(msg.get("level"), "error")
            self.assertIn("不存在", msg.get("thought", ""))


class TestTaskStreamRegistry(unittest.TestCase):
    """TaskStreamRegistry 单元测试：register / subscribe / broadcast / replay。"""

    def setUp(self) -> None:
        _reset_singletons()

    def tearDown(self) -> None:
        _reset_singletons()

    def test_register_subscribe_broadcast_replay(self) -> None:
        """完整流程：注册 task → 主 WS 广播日志 → 订阅者加入并回放历史。"""
        from app.core.streaming import get_task_stream_registry

        registry = get_task_stream_registry()
        task_id = "REQ-test-001"

        # 1. 注册 task
        asyncio.run(registry.register_task(task_id))
        self.assertTrue(asyncio.run(registry.is_active(task_id)))

        # 2. 主 WS（mock）广播 3 条日志
        ws_main = AsyncMock()
        asyncio.run(registry.add_subscriber(task_id, ws_main))
        for i in range(3):
            asyncio.run(
                registry.broadcast(
                    task_id,
                    {"agent": "SYSTEM", "level": "info", "thought": f"msg-{i}"},
                )
            )
        # 主 WS 应收到 3 条消息
        self.assertEqual(ws_main.send_json.await_count, 3)

        # 3. 订阅者加入：应回放 3 条历史日志
        ws_sub = AsyncMock()
        asyncio.run(registry.add_subscriber(task_id, ws_sub))
        # ws_sub 应收到 3 条回放
        self.assertEqual(ws_sub.send_json.await_count, 3)
        # 校验回放顺序与内容
        for i in range(3):
            args = ws_sub.send_json.await_args_list[i]
            self.assertEqual(args.args[0]["thought"], f"msg-{i}")

        # 4. 后续广播应同时送达主 WS 和订阅者
        asyncio.run(
            registry.broadcast(
                task_id,
                {"agent": "SYSTEM", "level": "complete", "thought": "done"},
            )
        )
        # 主 WS 累计 4 条
        self.assertEqual(ws_main.send_json.await_count, 4)
        # 订阅者累计 4 条（3 回放 + 1 实时）
        self.assertEqual(ws_sub.send_json.await_count, 4)

        # 5. 完成 task，is_active 变 False
        asyncio.run(registry.finish_task(task_id))
        self.assertFalse(asyncio.run(registry.is_active(task_id)))

    def test_broadcast_to_unregistered_task_drops_message(self) -> None:
        """广播到未注册的 task_id 应静默丢弃（不抛异常）。"""
        from app.core.streaming import get_task_stream_registry

        registry = get_task_stream_registry()
        # 不应抛异常
        asyncio.run(
            registry.broadcast("REQ-nonexistent", {"level": "info"})
        )

    def test_cleanup_expired(self) -> None:
        """完成的 task 历史日志超过 TTL 后应被清理。"""
        from app.core.streaming import get_task_stream_registry
        import app.core.streaming.task_stream_registry as tsr_module

        # 临时把 TTL 调小到 0.1s 加速测试
        original_ttl = tsr_module._TASK_HISTORY_TTL_SEC
        tsr_module._TASK_HISTORY_TTL_SEC = 0.1
        try:
            registry = get_task_stream_registry()
            asyncio.run(registry.register_task("REQ-ttl-001"))
            asyncio.run(registry.finish_task("REQ-ttl-001"))
            # 立即清理：不应清理（TTL 未到）
            n = asyncio.run(registry.cleanup_expired())
            self.assertEqual(n, 0)
            # 等待 TTL 过期
            import time as _time

            _time.sleep(0.2)
            n = asyncio.run(registry.cleanup_expired())
            self.assertEqual(n, 1)
        finally:
            tsr_module._TASK_HISTORY_TTL_SEC = original_ttl


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
