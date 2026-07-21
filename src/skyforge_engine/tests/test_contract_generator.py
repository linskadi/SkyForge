"""测试 ContractGeneratorAgent 的严格模式行为。

覆盖 Task 4.1：
- mock 模式下正常调用 _mock_run
- api/local 模式下异常直接抛出，不再降级
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest
from unittest.mock import patch

from skyforge_engine.agents.contract_generator import ContractGeneratorAgent


def test_run_mock_mode_returns_contract():
    """mock 模式下正常调用 _mock_run 并返回契约 YAML。"""
    with patch(
        "skyforge_engine.agents.contract_generator.settings.SKYFORGE_LLM_MODE",
        "mock",
    ):
        agent = ContractGeneratorAgent()
        req = {
            "req_id": "REQ-001",
            "desc": "Data handler module",
            "type": "generic",
            "module_name": "data_handler",
        }
        contract = asyncio.run(agent.run(req))

    assert "component:" in contract
    assert "contracts:" in contract
    assert "preconditions:" in contract
    assert "postconditions:" in contract


def test_run_local_mode_raises_when_backend_unavailable():
    """local 模式下 LLM 后端不可用时直接抛出异常，不再降级。"""
    import os
    with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "local"}):
        agent = ContractGeneratorAgent()
        req = {
            "req_id": "REQ-002",
            "desc": "通用数据处理器",
            "type": "generic",
            "module_name": "data_handler",
        }
        with patch(
            "skyforge_engine.agents.contract_generator.get_lmstudio_client"
        ) as mock_get_client:
            mock_client = mock_get_client.return_value
            mock_client.chat_async.side_effect = RuntimeError("LLM 后端不可用")
            with pytest.raises(RuntimeError, match="LLM 后端不可用"):
                asyncio.run(agent.run(req))


def test_run_api_mode_raises_when_backend_unavailable():
    """api 模式下 LLM 后端不可用时直接抛出异常，不再降级。"""
    import os
    with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "api"}):
        agent = ContractGeneratorAgent()
        req = {
            "req_id": "REQ-003",
            "desc": "通用数据处理器",
            "type": "generic",
            "module_name": "data_handler",
        }
        with patch(
            "skyforge_engine.agents.contract_generator.get_lmstudio_client"
        ) as mock_get_client:
            mock_client = mock_get_client.return_value
            mock_client.chat_async.side_effect = RuntimeError("LLM 后端不可用")
            with pytest.raises(RuntimeError, match="LLM 后端不可用"):
                asyncio.run(agent.run(req))
