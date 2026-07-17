# -*- coding: utf-8 -*-
"""LM Studio 集成测试（Patch 4）。

测试覆盖：
- safe_parse_llm_json 三级降级解析（直接 / Markdown / 正则 / 无效）
- Agent 在 USE_LLM=false 时使用 mock
- Agent 在 LM Studio 不可达时降级为 mock
"""

import asyncio
import os
import unittest

from skyforge_engine.agents.requirement_parser import RequirementParserAgent
from app.core.llm import lmstudio_client as lmstudio_module
from app.core.llm.json_parser import safe_parse_llm_json
from app.core.llm.lmstudio_client import get_lmstudio_client


def _reset_lmstudio_singleton() -> None:
    """重置 LM Studio 客户端单例（强制下次重新创建）。"""
    lmstudio_module._unified_client = None


class TestSafeParseJson(unittest.TestCase):
    """safe_parse_llm_json 三级降级解析测试。"""

    def test_safe_parse_json_direct(self) -> None:
        """一级：直接 JSON 解析。"""
        text = '{"type": "filter", "module_name": "lowpass", "cutoff_hz": 10.0}'
        result = safe_parse_llm_json(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "filter")
        self.assertEqual(result["module_name"], "lowpass")
        self.assertEqual(result["cutoff_hz"], 10.0)

    def test_safe_parse_json_markdown(self) -> None:
        """二级：剥离 Markdown 代码块包裹（```json ... ```）。"""
        text = (
            '好的，解析结果如下：\n```json\n'
            '{"type": "comms", "baud": 115200}\n```\n以上。'
        )
        result = safe_parse_llm_json(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "comms")
        self.assertEqual(result["baud"], 115200)

    def test_safe_parse_json_regex(self) -> None:
        """三级：正则提取花括号块（无 Markdown 包裹，纯自然语言前缀）。"""
        text = '解析结果：{"type": "control", "safety_level": "DAL-A"} 完成。'
        result = safe_parse_llm_json(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "control")
        self.assertEqual(result["safety_level"], "DAL-A")

    def test_safe_parse_json_invalid(self) -> None:
        """无效输入返回 None。"""
        self.assertIsNone(safe_parse_llm_json("这根本不是 JSON"))
        self.assertIsNone(safe_parse_llm_json(""))
        self.assertIsNone(safe_parse_llm_json("   "))
        # 只有花括号但内容非法
        self.assertIsNone(safe_parse_llm_json("{invalid json content}"))


class TestAgentWithMock(unittest.TestCase):
    """USE_LLM=false 时 Agent 使用 mock。"""

    def setUp(self) -> None:
        _reset_lmstudio_singleton()
        os.environ["USE_LLM"] = "false"

    def tearDown(self) -> None:
        _reset_lmstudio_singleton()

    def test_agent_with_mock(self) -> None:
        """USE_LLM=false 时需求解析 Agent 使用 mock（正则提取）。"""
        client = get_lmstudio_client()
        self.assertFalse(client.is_available())

        agent = RequirementParserAgent()
        result = asyncio.run(agent.run("实现一个低通滤波器，截止频率10Hz"))

        # mock 结果应包含结构化字段
        self.assertEqual(result["req_id"], "REQ-001")
        self.assertEqual(result["type"], "filter")
        self.assertEqual(result["module_name"], "lowpass_filter_10hz")
        self.assertEqual(result["params"]["cutoff_hz"], 10.0)
        self.assertEqual(result["safety_level"], "DAL-B")
        self.assertIn("WCET <= 1ms", result["constraints"])


class TestAgentLlmUnavailable(unittest.TestCase):
    """LM Studio 不可达时 Agent 降级为 mock。"""

    def setUp(self) -> None:
        # 保存原环境变量
        self._orig_use_llm = os.environ.get("USE_LLM")
        self._orig_base_url = os.environ.get("LMSTUDIO_BASE_URL")
        # 模拟 USE_LLM=true 但 LM Studio 不可达（指向不存在的端口）
        os.environ["USE_LLM"] = "true"
        os.environ["LMSTUDIO_BASE_URL"] = "http://localhost:9999/v1"
        _reset_lmstudio_singleton()

    def tearDown(self) -> None:
        # 恢复环境变量
        if self._orig_use_llm is not None:
            os.environ["USE_LLM"] = self._orig_use_llm
        else:
            os.environ.pop("USE_LLM", None)
        if self._orig_base_url is not None:
            os.environ["LMSTUDIO_BASE_URL"] = self._orig_base_url
        else:
            os.environ.pop("LMSTUDIO_BASE_URL", None)
        _reset_lmstudio_singleton()

    def test_agent_llm_unavailable(self) -> None:
        """LM Studio 不可达时 Agent 优雅降级为 mock。"""
        client = get_lmstudio_client()
        # use_llm=true 但服务不可达
        self.assertTrue(client.use_llm)
        self.assertFalse(client.is_available())

        agent = RequirementParserAgent()
        result = asyncio.run(agent.run("实现一个低通滤波器，截止频率10Hz"))

        # 降级为 mock，结果应与 mock 模式一致
        self.assertEqual(result["req_id"], "REQ-001")
        self.assertEqual(result["type"], "filter")
        self.assertEqual(result["params"]["cutoff_hz"], 10.0)
        self.assertEqual(result["module_name"], "lowpass_filter_10hz")


if __name__ == "__main__":
    unittest.main()
