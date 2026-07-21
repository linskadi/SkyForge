"""测试 skyforge_engine.mode_guard 严格模式守卫。

覆盖 Task 4.2：
- require_mode() mock 模式通过
- require_mode() api 模式但配置为 mock 时抛出 LLMBackendUnavailableError
- require_tool() 工具存在时通过
- require_tool() 工具缺失时抛出 ToolNotFoundError
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest
from unittest.mock import patch

from skyforge_engine.mode_guard import (
    get_current_mode,
    LLMMode,
    LLMBackendUnavailableError,
    ToolNotFoundError,
    require_mode,
    require_tool,
)


class TestGetCurrentMode:
    def test_default_returns_mock(self):
        """未设置环境变量时默认返回 LLMMode.MOCK。"""
        assert get_current_mode() == LLMMode.MOCK

    def test_reads_api_from_env(self):
        with patch.dict("os.environ", {"SKYFORGE_LLM_MODE": "api"}):
            assert get_current_mode() == LLMMode.API

    def test_reads_local_from_env(self):
        with patch.dict("os.environ", {"SKYFORGE_LLM_MODE": "local"}):
            assert get_current_mode() == LLMMode.LOCAL

    def test_invalid_value_falls_back_to_mock(self):
        with patch.dict("os.environ", {"SKYFORGE_LLM_MODE": "invalid"}):
            assert get_current_mode() == LLMMode.MOCK


class TestRequireMode:
    def test_mock_mode_passes(self):
        with patch.dict("os.environ", {"SKYFORGE_LLM_MODE": "mock"}):
            require_mode(LLMMode.MOCK)

    def test_api_mode_required_but_mock_configured_raises(self):
        with patch.dict("os.environ", {"SKYFORGE_LLM_MODE": "mock"}):
            with pytest.raises(LLMBackendUnavailableError):
                require_mode(LLMMode.API)

    def test_local_mode_required_but_mock_configured_raises(self):
        with patch.dict("os.environ", {"SKYFORGE_LLM_MODE": "mock"}):
            with pytest.raises(LLMBackendUnavailableError):
                require_mode(LLMMode.LOCAL)


class TestRequireTool:
    def test_existing_tool_returns_version(self):
        result = require_tool("python")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_missing_tool_raises(self):
        with pytest.raises(ToolNotFoundError):
            require_tool("this_tool_definitely_does_not_exist_12345")
