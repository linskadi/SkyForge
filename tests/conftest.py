"""Repository-wide test safety defaults.

Tests must never spend a configured cloud API balance unless a dedicated test
explicitly replaces these values with a fake transport.
"""

import pytest


@pytest.fixture(autouse=True)
def disable_paid_llm_by_default(monkeypatch):
    monkeypatch.setenv("SKYFORGE_LLM_MODE", "mock")
    monkeypatch.setenv("USE_LLM", "false")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    from skyforge_engine.config import settings

    monkeypatch.setattr(settings, "SKYFORGE_LLM_MODE", "mock")
    monkeypatch.setattr(settings, "SKYFORGE_LLM_PROVIDER", None)
    monkeypatch.setattr(settings, "LLM_API_KEY", None)
    monkeypatch.setattr(settings, "USE_LLM", False)
