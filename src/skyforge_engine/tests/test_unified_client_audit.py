"""测试 UnifiedLLMClient 的审计日志功能。"""

import sys
import asyncio
from pathlib import Path

# 添加 src 到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from unittest.mock import patch, MagicMock

from skyforge_llm.client import UnifiedLLMClient
from skyforge_llm.security.auditor import get_auditor


def test_audit_recorded_on_chat():
    """chat 调用后应记录审计日志。"""
    auditor = get_auditor()
    initial_count = len(auditor.get_records())

    client = UnifiedLLMClient()
    # mock _resolve_backend 返回 mock
    with patch.object(client, "_resolve_backend", return_value="mock"):
        client.chat("test prompt", "system")

    records = auditor.get_records()
    assert len(records) == initial_count + 1
    latest = records[-1]
    assert latest["provider"] == "mock"
    assert latest["input_len"] == len("test prompt")
    assert latest["duration_ms"] >= 0


def test_audit_disabled_when_flag_off():
    """SECURITY_AUDIT_ENABLED=False 时不记录。"""
    auditor = get_auditor()
    initial_count = len(auditor.get_records())

    with patch(
        "skyforge_engine.config.settings.SECURITY_AUDIT_ENABLED", False
    ):
        client = UnifiedLLMClient()
        with patch.object(client, "_resolve_backend", return_value="mock"):
            client.chat("test prompt")

    assert len(auditor.get_records()) == initial_count


def test_audit_async_recorded():
    """chat_async 调用后应记录审计日志。"""
    auditor = get_auditor()
    initial_count = len(auditor.get_records())

    client = UnifiedLLMClient()
    with patch.object(client, "_resolve_backend", return_value="mock"):
        asyncio.run(client.chat_async("test async prompt"))

    records = auditor.get_records()
    assert len(records) == initial_count + 1
    assert records[-1]["input_len"] == len("test async prompt")


def test_audit_failure_does_not_break_chat():
    """审计逻辑抛异常时不应影响主流程。"""
    client = UnifiedLLMClient()
    with patch.object(client, "_resolve_backend", return_value="mock"):
        # 让 get_auditor 抛异常，验证 try/except 兜底
        with patch(
            "skyforge_llm.security.auditor.get_auditor",
            side_effect=RuntimeError("simulated audit failure"),
        ):
            result = client.chat("test prompt")
    assert result == ""  # mock 后端返回空字符串，审计异常未影响主流程


# ---------------------------------------------------------------------------
# SubTask 11.1: UnifiedLLMClient.is_available() 在不同 mode 下的行为
# ---------------------------------------------------------------------------


def test_is_available_local_unreachable():
    """mode=local + Ollama 端口不可达 → is_available() 返回 False。

    覆盖 Task 2 修复：override 模式下真实探测 LMStudio/Ollama 服务可达性，
    不再与下游 chat_async 的 LMStudioClient.is_available() 状态分裂。
    """
    client = UnifiedLLMClient()
    client.apply_config(
        mode="local",
        base_url="http://127.0.0.1:59999/v1",  # 不可达端口
    )
    # mock 底层 LMStudioClient.is_available 返回 False（模拟 Ollama 不可达），
    # 因为 apply_config 不会传播 base_url 到单例 LMStudioClient
    mock_lmstudio = MagicMock()
    mock_lmstudio.is_available.return_value = False
    with patch.object(client, "_get_lmstudio", return_value=mock_lmstudio):
        result = client.is_available(force_recheck=True)
    assert result is False
    assert client._override_available is False
    # 验证确实调用了底层 LMStudioClient 的 is_available（真实探测）
    mock_lmstudio.is_available.assert_called_once_with(force_recheck=True)


def test_is_available_api_openai_unreachable():
    """mode=api + provider=openai + 无效 base_url → is_available() 返回 False。

    覆盖 Task 2 修复：api 模式下 _ping_openai 真实探测 OpenAI 兼容端点。
    """
    client = UnifiedLLMClient()
    client.apply_config(
        mode="api",
        provider="openai",
        api_key="sk-invalid-key-for-test",
        base_url="http://127.0.0.1:59999/v1",  # 不可达端口
    )
    result = client.is_available(force_recheck=True)
    assert result is False
    assert client._override_available is False


def test_local_apply_config_updates_existing_lmstudio_model(monkeypatch):
    client = UnifiedLLMClient()
    lmstudio = client._get_lmstudio()
    lmstudio.base_url = "https://api.deepseek.com"
    lmstudio.model = "deepseek-v4-flash"
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LMSTUDIO_MODEL", raising=False)

    client.apply_config(mode="local", base_url="http://localhost:11434/v1")
    assert client._get_lmstudio().base_url == "http://localhost:11434/v1"
    assert client._get_lmstudio().model == "qwen3:8b"


def test_is_available_cache_ttl():
    """验证 60s 内重复调用不重复探测（TTL 缓存生效）。"""
    client = UnifiedLLMClient()
    client.apply_config(
        mode="local",
        base_url="http://127.0.0.1:59999/v1",
    )

    # 用 mock 替换 _get_lmstudio().is_available，统计调用次数
    mock_lmstudio = MagicMock()
    mock_lmstudio.is_available.return_value = True
    with patch.object(client, "_get_lmstudio", return_value=mock_lmstudio):
        # 第一次调用：触发真实探测
        result1 = client.is_available(force_recheck=True)
        assert result1 is True
        assert mock_lmstudio.is_available.call_count == 1

        # 第二次调用（不强制刷新）：应命中缓存，不重复探测
        result2 = client.is_available()
        assert result2 is True
        assert mock_lmstudio.is_available.call_count == 1  # 仍只被调用 1 次

        # 第三次调用（不强制刷新）：仍命中缓存
        result3 = client.is_available()
        assert result3 is True
        assert mock_lmstudio.is_available.call_count == 1
