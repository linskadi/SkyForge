"""Configuration files must not depend on the process working directory."""

from pathlib import Path

from skyforge_engine.config import _env_files


def test_env_files_are_repository_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    config_env, root_env, profile_env = map(Path, _env_files("dev"))

    assert config_env.is_absolute()
    assert config_env.name == ".env"
    assert config_env.parent.name == "config"
    assert root_env.parent == config_env.parent.parent
    assert profile_env == root_env.parent / ".env.dev"
