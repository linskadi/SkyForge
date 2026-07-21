"""测试 RequirementParserAgent 的 generic / redundancy 类型识别。

覆盖 Task 7 修改：
- _detect_type() 默认返回 "generic"（不再返回 "filter"）
- 新增 "redundancy" 关键词类型（余度/冗余/redundancy/双通道/voting/表决）
- _parse_llm_response() 类型校验白名单接受 "generic" 和 "redundancy"
"""

import sys
import asyncio
from pathlib import Path

# 添加 src 到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from unittest.mock import patch

from skyforge_engine.agents.requirement_parser import RequirementParserAgent


def test_detect_type_default_generic():
    """无关键词匹配时返回 "generic"（不再返回 "filter"）。

    覆盖 Task 7 SubTask 7.1：默认返回值从 "filter" 改为 "generic"。
    """
    parser = RequirementParserAgent()
    # 不含任何已知关键词的纯描述性文本
    result = parser._detect_type("实现一个通用的数据处理器")
    assert result == "generic"


def test_detect_type_redundancy_keywords():
    """输入含"余度"/"冗余"/"redundancy"/"双通道"/"voting"/"表决"时返回 "redundancy"。

    覆盖 Task 7 SubTask 7.2：新增 redundancy 关键词识别。
    """
    parser = RequirementParserAgent()

    # 中文关键词
    assert parser._detect_type("实现余度管理器，双通道输入") == "redundancy"
    assert parser._detect_type("冗余计算机配置") == "redundancy"
    assert parser._detect_type("双通道表决系统") == "redundancy"
    assert parser._detect_type("表决算法设计") == "redundancy"

    # 英文关键词
    assert parser._detect_type("Implement redundancy manager") == "redundancy"
    assert parser._detect_type("Dual channel voting system") == "redundancy"


def test_detect_type_filter_keyword_still_works():
    """输入含"滤波器"时仍返回 "filter"。

    回归测试：确保新增 generic 默认值不影响已有 filter 类型识别。
    """
    parser = RequirementParserAgent()
    assert parser._detect_type("实现一个低通滤波器，截止频率10Hz") == "filter"
    assert parser._detect_type("signal filter design") == "filter"


def test_parse_llm_response_accepts_generic():
    """_parse_llm_response 类型校验白名单接受 "generic" 和 "redundancy"。

    覆盖 Task 7：_parse_llm_response 的 type 白名单已扩展，
    LLM 返回 "generic" 或 "redundancy" 时不再被强制改写。
    """
    parser = RequirementParserAgent()

    # LLM 返回 type="generic" → 应被接受（不被 _detect_type 覆盖）
    fake_response = '{"type": "generic", "module_name": "data_proc"}'
    result = parser._parse_llm_response(
        fake_response, "实现一个数据处理器", "REQ-001"
    )
    assert result is not None
    assert result["type"] == "generic"
    assert result["module_name"] == "data_proc"

    # LLM 返回 type="redundancy" → 应被接受
    fake_response = '{"type": "redundancy", "module_name": "redundancy_mgr"}'
    result = parser._parse_llm_response(
        fake_response, "余度管理器", "REQ-002"
    )
    assert result is not None
    assert result["type"] == "redundancy"
    assert result["module_name"] == "redundancy_mgr"


def test_parse_llm_response_rejects_invalid_type():
    """LLM 返回非法 type 时降级为 _detect_type 结果。"""
    parser = RequirementParserAgent()
    # type="unknown_type" 不在白名单 → 调用 _detect_type 兜底
    fake_response = '{"type": "unknown_type", "module_name": "x"}'
    result = parser._parse_llm_response(
        fake_response, "实现一个低通滤波器", "REQ-003"
    )
    assert result is not None
    # "滤波器" 关键词触发 filter 类型
    assert result["type"] == "filter"


def test_run_mock_returns_generic_for_unknown_requirement():
    """run() 在 Mock 模式下对未知需求返回 generic 类型。

    端到端验证：mock 模式直接调用 _mock_run 使用 _detect_type，
    对无关键词的描述性需求返回 generic。
    """
    parser = RequirementParserAgent()
    with patch(
        "skyforge_engine.agents.requirement_parser.settings.SKYFORGE_LLM_MODE",
        "mock",
    ):
        result = asyncio.run(parser.run("实现一个通用数据处理器"))

    assert result["type"] == "generic"
    assert result["req_id"] == "REQ-001"
    assert result["module_name"] == "generic_module"


def test_run_mock_returns_redundancy_for_redundancy_keyword():
    """run() 在 Mock 模式下对"余度"关键词返回 redundancy 类型。"""
    parser = RequirementParserAgent()
    with patch(
        "skyforge_engine.agents.requirement_parser.settings.SKYFORGE_LLM_MODE",
        "mock",
    ):
        result = asyncio.run(parser.run("实现双通道余度管理器"))

    assert result["type"] == "redundancy"
    assert result["module_name"] == "redundancy_manager"


def test_run_local_mode_raises_when_backend_unavailable():
    """local 模式下 LLM 后端不可用时直接抛出异常，不再降级。"""
    import os
    import pytest
    with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "local"}):
        parser = RequirementParserAgent()
        with patch(
            "skyforge_engine.agents.requirement_parser.get_lmstudio_client"
        ) as mock_get_client:
            mock_client = mock_get_client.return_value
            mock_client.chat_async.side_effect = RuntimeError("LLM 后端不可用")
            with pytest.raises(RuntimeError, match="LLM 后端不可用"):
                asyncio.run(parser.run("实现一个通用数据处理器"))


def test_run_api_mode_raises_when_backend_unavailable():
    """api 模式下 LLM 后端不可用时直接抛出异常，不再降级。"""
    import os
    import pytest
    with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "api"}):
        parser = RequirementParserAgent()
        with patch(
            "skyforge_engine.agents.requirement_parser.get_lmstudio_client"
        ) as mock_get_client:
            mock_client = mock_get_client.return_value
            mock_client.chat_async.side_effect = RuntimeError("LLM 后端不可用")
            with pytest.raises(RuntimeError, match="LLM 后端不可用"):
                asyncio.run(parser.run("实现一个通用数据处理器"))
