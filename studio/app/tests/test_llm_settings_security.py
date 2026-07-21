"""Security and provenance regressions for the Web LLM settings flow."""

import pytest
from pydantic import ValidationError

from app.api.routes import settings as settings_route
from app.api.routes.settings import LLMConfigRequest
from skyforge_llm.client import UnifiedLLMClient


def test_llm_config_rejects_control_characters_and_relative_urls():
    with pytest.raises(ValidationError):
        LLMConfigRequest(baseUrl="javascript:alert(1)")
    with pytest.raises(ValidationError):
        LLMConfigRequest(apiKey="secret\nINJECTED=value")


def test_persisted_config_is_atomic_scoped_and_removable(tmp_path, monkeypatch):
    env_file = tmp_path / "config" / ".env"
    env_file.parent.mkdir()
    env_file.write_text("UNRELATED=value\nLLM_API_KEY=old\n", encoding="utf-8")
    monkeypatch.setattr(settings_route, "_PERSISTED_ENV", env_file)

    settings_route._persist_config(
        {"LLM_API_KEY": "new-secret", "SKYFORGE_LLM_MODE": "api"}
    )
    saved = env_file.read_text(encoding="utf-8")
    assert "UNRELATED=value" in saved
    assert "LLM_API_KEY=\"new-secret\"" in saved
    assert settings_route._has_persisted_config() is True
    assert not env_file.with_suffix(".tmp").exists()

    settings_route._persist_config(
        {"LLM_API_KEY": None, "SKYFORGE_LLM_MODE": None}
    )
    removed = env_file.read_text(encoding="utf-8")
    assert "UNRELATED=value" in removed
    assert "new-secret" not in removed
    assert settings_route._has_persisted_config() is False


def test_cloud_status_does_not_masquerade_as_lm_studio():
    client = UnifiedLLMClient()
    client.apply_config(
        "api", "deepseek", "not-a-real-key", "https://api.deepseek.com", "deepseek-chat"
    )

    status = client.get_status()
    assert status["display_backend"] == "deepseek"
    assert status["connection"]["provider"] == "deepseek"
    assert status["lmstudio"]["available"] is False
