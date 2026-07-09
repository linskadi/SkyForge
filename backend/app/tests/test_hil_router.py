# -*- coding: utf-8 -*-
"""HIL 人机协作 + 多模型路由集成测试（次级功能）。

测试覆盖：
- test_model_router_select：根据任务类型选择模型（简单/复杂任务）
- test_model_router_fallback：超时降级 + 候选未加载时降级到 LM Studio 首个可用模型
- test_model_router_get_model_info：获取模型信息（已加载/未加载）
- test_model_router_list_models：列出 LM Studio 模型
- test_model_router_manual_selection：手动选择模型覆盖自动路由
- test_hil_request_approval：创建审批请求并等待人工批准
- test_hil_approve：批准审批
- test_hil_reject：拒绝审批
- test_hil_timeout：超时自动批准
- test_hil_disabled：HIL_ENABLED=false 时跳过审批
- test_hil_history：审批历史记录
- test_pipeline_hil_integration：HIL_ENABLED=false 时 pipeline 正常完成
"""

import asyncio
import os
import unittest
from unittest.mock import patch

from app.core.hil.hil_manager import HILManager, reset_hil_manager
from app.core.llm import lmstudio_client as lmstudio_module
from app.core.llm.model_router import (
    ModelRouter,
    reset_model_router,
)
from app.core.pipeline import run_pipeline


# --------------------------------------------------------------------------- #
# 测试辅助
# --------------------------------------------------------------------------- #


def _reset_singletons() -> None:
    """重置 HIL 和 ModelRouter 单例（强制下次重新创建）。"""
    reset_hil_manager()
    reset_model_router()
    lmstudio_module._unified_client = None


# --------------------------------------------------------------------------- #
# ModelRouter 测试
# --------------------------------------------------------------------------- #


class TestModelRouter(unittest.TestCase):
    """多模型路由器测试。"""

    def setUp(self) -> None:
        _reset_singletons()
        # 默认不连真实 LM Studio
        os.environ["USE_LLM"] = "false"
        os.environ["LMSTUDIO_BASE_URL"] = "http://localhost:9999/v1"

    def tearDown(self) -> None:
        _reset_singletons()

    def test_model_router_select(self) -> None:
        """根据任务类型选择模型：简单任务→小模型，复杂任务→大模型。"""
        router = ModelRouter()

        # LM Studio 不可用，应返回默认模型（环境变量 LMSTUDIO_MODEL）
        small = router.select_model("requirement_parse")
        large = router.select_model("code_generation")

        # 都应返回有效字符串
        self.assertIsInstance(small, str)
        self.assertTrue(len(small) > 0)
        self.assertIsInstance(large, str)
        self.assertTrue(len(large) > 0)

    def test_model_router_select_with_loaded_models(self) -> None:
        """LM Studio 中有候选模型时，应匹配首选模型。"""
        router = ModelRouter()

        # mock list_available_models 返回小模型
        with patch.object(
            router,
            "list_available_models",
            return_value=[{"id": "qwen/qwen3.5-9b", "size": "9B", "type": "llm"}],
        ):
            model = router.select_model("requirement_parse")
            self.assertEqual(model, "qwen/qwen3.5-9b")

        # mock 返回大模型
        with patch.object(
            router,
            "list_available_models",
            return_value=[{"id": "qwen3-coder-30b", "size": "30B", "type": "llm"}],
        ):
            model = router.select_model("code_generation")
            self.assertEqual(model, "qwen3-coder-30b")

    def test_model_router_fallback(self) -> None:
        """超时降级：首选模型超时后切换到备用模型。"""
        router = ModelRouter(timeout=10)

        # mock 候选模型都加载，但第一个超时
        with patch.object(
            router,
            "list_available_models",
            return_value=[
                {"id": "gemma-3-e4b", "size": "4B", "type": "llm"},
                {"id": "qwen/qwen3.5-9b", "size": "9B", "type": "llm"},
            ],
        ):
            # 模拟 gemma-3-e4b 上次调用耗时 15s（超过阈值 10s）
            router.record_latency("gemma-3-e4b", 15.0)
            # select_with_fallback 应跳过 gemma-3-e4b，选 qwen/qwen3.5-9b
            model = router.select_with_fallback("requirement_parse")
            self.assertEqual(model, "qwen/qwen3.5-9b")

    def test_model_router_fallback_no_loaded(self) -> None:
        """候选模型均未加载时，降级到 LM Studio 第一个可用模型。"""
        router = ModelRouter()

        # mock 返回的模型都不在候选列表中
        with patch.object(
            router,
            "list_available_models",
            return_value=[{"id": "some-other-model", "size": "7B", "type": "llm"}],
        ):
            model = router.select_model("requirement_parse")
            self.assertEqual(model, "some-other-model")

    def test_model_router_get_model_info(self) -> None:
        """get_model_info 返回已加载/未加载模型信息。"""
        router = ModelRouter()

        with patch.object(
            router,
            "list_available_models",
            return_value=[
                {
                    "id": "qwen/qwen3.5-9b",
                    "size": "9B",
                    "type": "llm",
                    "context_length": 32768,
                }
            ],
        ):
            # 已加载模型
            info = router.get_model_info("qwen/qwen3.5-9b")
            self.assertTrue(info["loaded"])
            self.assertEqual(info["size"], "9B")
            self.assertEqual(info["context_length"], 32768)

            # 未加载模型
            info = router.get_model_info("nonexistent-model")
            self.assertFalse(info["loaded"])

    def test_model_router_list_models(self) -> None:
        """list_available_models 返回 LM Studio 模型列表（不可用时为空）。"""
        router = ModelRouter()
        # LM Studio 不可达 → 返回空列表
        models = router.list_available_models()
        self.assertEqual(models, [])

    def test_model_router_manual_selection(self) -> None:
        """手动选择模型覆盖自动路由。"""
        router = ModelRouter()

        router.set_manual_selection("custom-model-id")
        model = router.select_model("requirement_parse")
        self.assertEqual(model, "custom-model-id")

        # 清除手动选择 → 恢复自动路由
        router.set_manual_selection(None)
        # 不应抛异常
        model = router.select_model("requirement_parse")
        self.assertIsInstance(model, str)


# --------------------------------------------------------------------------- #
# HILManager 测试
# --------------------------------------------------------------------------- #


class TestHILManager(unittest.TestCase):
    """HIL 人机协作管理器测试。"""

    def setUp(self) -> None:
        _reset_singletons()
        os.environ["HIL_ENABLED"] = "true"
        os.environ["HIL_TIMEOUT"] = "300"

    def tearDown(self) -> None:
        _reset_singletons()

    def test_hil_request_approval(self) -> None:
        """创建审批请求并等待人工批准。"""
        manager = HILManager(enabled=True, default_timeout=10)

        async def scenario() -> dict:
            # 并发：等待审批 + 1 秒后批准
            async def wait_approval():
                return await manager.request_approval(
                    checkpoint="requirement_review",
                    content="需求 JSON 内容",
                    timeout=5,
                )

            async def approve_later():
                await asyncio.sleep(0.1)
                # 等待 pending 出现
                pending = manager.get_pending_approvals()
                while not pending:
                    await asyncio.sleep(0.05)
                    pending = manager.get_pending_approvals()
                request_id = pending[0]["request_id"]
                return await manager.approve(
                    request_id=request_id,
                    comments="通过",
                    reviewer="alice",
                )

            wait_task = asyncio.create_task(wait_approval())
            approve_task = asyncio.create_task(approve_later())

            approval_result = await wait_task
            await approve_task
            return approval_result

        result = asyncio.run(scenario())
        self.assertTrue(result["approved"])
        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["reviewer"], "alice")
        self.assertEqual(result["comments"], "通过")
        self.assertEqual(result["checkpoint"], "requirement_review")
        self.assertIn("request_id", result)
        self.assertIn("timestamp", result)

    def test_hil_approve(self) -> None:
        """批准审批：approve 后等待方应被唤醒。"""
        manager = HILManager(enabled=True, default_timeout=10)

        async def scenario() -> dict:
            async def wait_approval():
                return await manager.request_approval(
                    checkpoint="contract_review",
                    content="contract YAML",
                    timeout=5,
                )

            async def approve_after_pending():
                # 等待 pending 出现
                for _ in range(50):
                    pending = manager.get_pending_approvals()
                    if pending:
                        break
                    await asyncio.sleep(0.02)
                else:
                    self.fail("等待 pending 出现超时")
                request_id = pending[0]["request_id"]
                return await manager.approve(
                    request_id=request_id,
                    comments="契约 OK",
                    reviewer="bob",
                )

            wait_task = asyncio.create_task(wait_approval())
            approve_task = asyncio.create_task(approve_after_pending())

            approval_result = await wait_task
            approve_result = await approve_task
            return approval_result, approve_result

        approval_result, approve_result = asyncio.run(scenario())
        self.assertTrue(approval_result["approved"])
        self.assertEqual(approve_result["approved"], True)
        self.assertEqual(approve_result["reviewer"], "bob")
        # pending 列表应为空（已处理）
        self.assertEqual(manager.get_pending_approvals(), [])

    def test_hil_reject(self) -> None:
        """拒绝审批：reject 后等待方应收到 approved=False。"""
        manager = HILManager(enabled=True, default_timeout=10)

        async def scenario() -> dict:
            async def wait_approval():
                return await manager.request_approval(
                    checkpoint="code_review",
                    content="int main(){}",
                    timeout=5,
                )

            async def reject_after_pending():
                for _ in range(50):
                    pending = manager.get_pending_approvals()
                    if pending:
                        break
                    await asyncio.sleep(0.02)
                else:
                    self.fail("等待 pending 出现超时")
                request_id = pending[0]["request_id"]
                return await manager.reject(
                    request_id=request_id,
                    comments="代码不合规",
                    reviewer="carol",
                )

            wait_task = asyncio.create_task(wait_approval())
            reject_task = asyncio.create_task(reject_after_pending())

            approval_result = await wait_task
            reject_result = await reject_task
            return approval_result, reject_result

        approval_result, reject_result = asyncio.run(scenario())
        self.assertFalse(approval_result["approved"])
        self.assertEqual(approval_result["status"], "rejected")
        self.assertFalse(reject_result["approved"])
        self.assertEqual(reject_result["reviewer"], "carol")
        self.assertEqual(reject_result["comments"], "代码不合规")

    def test_hil_timeout(self) -> None:
        """超时自动批准：等待 timeout 秒后返回 approved=True。"""
        manager = HILManager(enabled=True, default_timeout=10)

        async def scenario() -> dict:
            # timeout=1 秒，不调用 approve/reject
            return await manager.request_approval(
                checkpoint="requirement_review",
                content="测试超时",
                timeout=1,
            )

        result = asyncio.run(scenario())
        self.assertTrue(result["approved"])
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["reviewer"], "system")
        self.assertIn("超时", result["comments"])

        # 历史记录中应有这条
        history = manager.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "timeout")

    def test_hil_disabled(self) -> None:
        """HIL_ENABLED=false 时跳过审批，直接返回 approved=True。"""
        manager = HILManager(enabled=False)

        async def scenario() -> dict:
            return await manager.request_approval(
                checkpoint="requirement_review",
                content="测试禁用",
                timeout=5,
            )

        result = asyncio.run(scenario())
        self.assertTrue(result["approved"])
        self.assertEqual(result["status"], "skipped")
        # pending 列表应为空（未创建请求）
        self.assertEqual(manager.get_pending_approvals(), [])

    def test_hil_unknown_checkpoint(self) -> None:
        """未知 checkpoint 自动通过（status=skipped）。"""
        manager = HILManager(enabled=True)

        async def scenario() -> dict:
            return await manager.request_approval(
                checkpoint="unknown_checkpoint",
                content="unknown",
                timeout=2,
            )

        result = asyncio.run(scenario())
        self.assertTrue(result["approved"])
        self.assertEqual(result["status"], "skipped")

    def test_hil_history(self) -> None:
        """审批历史：approve/reject/timeout 都应记录到历史。"""
        manager = HILManager(enabled=True, default_timeout=10)

        async def scenario() -> None:
            # 1. 批准
            async def wait1():
                return await manager.request_approval(
                    checkpoint="requirement_review",
                    content="c1",
                    timeout=3,
                )

            async def approve1():
                for _ in range(50):
                    pending = manager.get_pending_approvals()
                    if pending:
                        break
                    await asyncio.sleep(0.02)
                await manager.approve(pending[0]["request_id"])

            t1 = asyncio.create_task(wait1())
            a1 = asyncio.create_task(approve1())
            await t1
            await a1

            # 2. 超时
            await manager.request_approval(
                checkpoint="contract_review",
                content="c2",
                timeout=1,
            )

        asyncio.run(scenario())

        history = manager.get_history()
        self.assertEqual(len(history), 2)
        # 第一条 approved，第二条 timeout
        statuses = [h["status"] for h in history]
        self.assertIn("approved", statuses)
        self.assertIn("timeout", statuses)

    def test_hil_approve_nonexistent(self) -> None:
        """批准不存在的 request_id 应返回 error。"""
        manager = HILManager(enabled=True)

        async def scenario() -> dict:
            return await manager.approve("nonexistent-id")

        result = asyncio.run(scenario())
        self.assertIn("error", result)
        self.assertIn("不存在", result["error"])


# --------------------------------------------------------------------------- #
# Pipeline HIL 集成测试
# --------------------------------------------------------------------------- #


class TestPipelineHILIntegration(unittest.TestCase):
    """Pipeline 与 HIL 集成测试。"""

    def setUp(self) -> None:
        _reset_singletons()
        os.environ["USE_LLM"] = "false"
        os.environ["HIL_ENABLED"] = "false"
        os.environ["HIL_TIMEOUT"] = "300"

    def tearDown(self) -> None:
        _reset_singletons()

    def test_pipeline_hil_disabled(self) -> None:
        """HIL_ENABLED=false 时 pipeline 正常完成（跳过审批）。"""
        result = asyncio.run(run_pipeline("实现一个低通滤波器，截止频率10Hz"))

        # pipeline 应正常完成
        self.assertEqual(result["requirement"]["req_id"], "REQ-001")
        self.assertIn("contract", result)
        self.assertIn("code", result)

        # HIL 审批结果应存在且都为 skipped
        approvals = result.get("hil_approvals", {})
        self.assertGreater(len(approvals), 0, "应至少有 1 个 HIL 检查点记录")
        for checkpoint, approval in approvals.items():
            self.assertTrue(
                approval.get("approved", False),
                f"检查点 {checkpoint} 未通过: {approval}",
            )
            self.assertEqual(approval.get("status"), "skipped")

        # 不应被中止
        self.assertFalse(result.get("aborted", False))


if __name__ == "__main__":
    unittest.main()
