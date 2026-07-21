"""模式守卫模块单元测试。

覆盖：
- get_current_mode 默认值与解析
- require_mode 匹配与不匹配场景
- require_tool 存在与缺失场景
"""

import importlib.util
import os
import sys
import unittest
from unittest.mock import patch

# 直接从文件路径加载 mode_guard，避免触发 app.core.llm.__init__ 中的副作用导入
_MODULE_PATH = os.path.join(os.path.dirname(__file__), "..", "core", "llm", "mode_guard.py")
spec = importlib.util.spec_from_file_location("mode_guard", _MODULE_PATH)
mode_guard = importlib.util.module_from_spec(spec)
sys.modules["mode_guard"] = mode_guard
spec.loader.exec_module(mode_guard)

LLMBackendUnavailableError = mode_guard.LLMBackendUnavailableError
LLMMode = mode_guard.LLMMode
ToolNotFoundError = mode_guard.ToolNotFoundError
get_current_mode = mode_guard.get_current_mode
require_mode = mode_guard.require_mode
require_tool = mode_guard.require_tool


class TestGetCurrentMode(unittest.TestCase):
    """测试 get_current_mode 函数。"""

    def test_default_returns_mock(self):
        """未设置环境变量时，默认返回 MOCK 模式。"""
        with patch.dict(os.environ, {}, clear=True):
            mode = get_current_mode()
            self.assertEqual(mode, LLMMode.MOCK)

    def test_reads_api_from_env(self):
        """环境变量设置为 api 时返回 API 模式。"""
        with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "api"}):
            self.assertEqual(get_current_mode(), LLMMode.API)

    def test_reads_local_from_env(self):
        """环境变量设置为 local 时返回 LOCAL 模式。"""
        with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "local"}):
            self.assertEqual(get_current_mode(), LLMMode.LOCAL)

    def test_invalid_value_falls_back_to_mock(self):
        """非法值回退到 MOCK 模式。"""
        with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "unknown"}):
            self.assertEqual(get_current_mode(), LLMMode.MOCK)


class TestRequireMode(unittest.TestCase):
    """测试 require_mode 守卫函数。"""

    def test_mock_mode_passes(self):
        """当前为 mock 模式时，要求 mock 应通过。"""
        with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "mock"}):
            # 不应抛出异常
            require_mode(LLMMode.MOCK)

    def test_api_mode_required_but_mock_configured_raises(self):
        """配置为 mock 但要求 api 时，应抛出 LLMBackendUnavailableError。"""
        with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "mock"}):
            with self.assertRaises(LLMBackendUnavailableError) as ctx:
                require_mode(LLMMode.API)

            exc = ctx.exception
            self.assertEqual(exc.backend, "mock")
            self.assertIn("MOCK", exc.message)
            self.assertIn("API", exc.message)


class TestRequireTool(unittest.TestCase):
    """测试 require_tool 工具检查函数。"""

    def test_existing_tool_returns_version(self):
        """工具存在时应返回版本信息（或路径）。"""
        # 使用当前解释器本身作为必定存在的工具
        result = require_tool("python")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_missing_tool_raises(self):
        """工具缺失时应抛出 ToolNotFoundError。"""
        fake_tool = "skyforge_nonexistent_tool_12345"
        with self.assertRaises(ToolNotFoundError) as ctx:
            require_tool(fake_tool)

        exc = ctx.exception
        self.assertEqual(exc.tool_name, fake_tool)
        self.assertIn(fake_tool, exc.message)


if __name__ == "__main__":
    unittest.main()
