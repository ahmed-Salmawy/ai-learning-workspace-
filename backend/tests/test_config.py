import pytest

from app.core.config import Settings


def test_defaults() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.app_name == "ai-learning-workspace"
    assert settings.environment == "dev"
    assert settings.embedding_dimension == 1536
    assert settings.openai_api_key is None


def test_env_prefix_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALW_EMBEDDING_DIMENSION", "768")
    monkeypatch.setenv("ALW_ENVIRONMENT", "test")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.embedding_dimension == 768
    assert settings.environment == "test"


def test_api_key_is_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALW_OPENAI_API_KEY", "sk-test")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.openai_api_key is not None
    assert "sk-test" not in repr(settings.openai_api_key)
    assert settings.openai_api_key.get_secret_value() == "sk-test"
