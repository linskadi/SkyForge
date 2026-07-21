"""Repository-wide pytest safety defaults."""

from __future__ import annotations

import os

import pytest


def _force_mock_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests from calling a configured real LLM by default."""
    monkeypatch.setenv("SKYFORGE_LLM_MODE", "mock")
    monkeypatch.setenv("USE_LLM", "false")
    monkeypatch.setenv("HIL_ENABLED", "false")
    monkeypatch.delenv("HITL_ENABLED", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    from skyforge_engine.config import settings
    from skyforge_llm.client import get_lmstudio_client

    monkeypatch.setattr(settings, "SKYFORGE_LLM_MODE", "mock")
    monkeypatch.setattr(settings, "SKYFORGE_LLM_PROVIDER", None)
    monkeypatch.setattr(settings, "LLM_API_KEY", None)
    monkeypatch.setattr(settings, "USE_LLM", False)
    monkeypatch.setattr(settings, "HIL_ENABLED", False)
    monkeypatch.setattr(settings, "HITL_ENABLED", False)

    client = get_lmstudio_client()
    client.apply_config("mock", None, None, os.environ.get("LOCAL_LLM_BASE_URL"), None)

    try:
        from app.core.hil.hil_manager import reset_hil_manager
    except Exception:
        return
    reset_hil_manager()


@pytest.fixture(autouse=True)
def disable_paid_llm_by_default(monkeypatch: pytest.MonkeyPatch):
    _force_mock_llm(monkeypatch)
    yield
    _force_mock_llm(monkeypatch)
