"""Unit tests for :mod:`app.core.config`."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from cryptography.fernet import Fernet

from app.core import config


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    """Make sure each test sees fresh env vars, not the cached singleton."""
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


class TestSettings:
    def test_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", key)
        monkeypatch.setenv("JWT_SECRET", "x" * 32)
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")

        settings = config.get_settings()
        assert settings.environment is config.Environment.PRODUCTION
        assert settings.is_production is True
        assert settings.log_level is config.LogLevel.WARNING
        assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/db"
        assert settings.encryption_key.get_secret_value() == key
        assert settings.jwt_secret.get_secret_value() == "x" * 32

    def test_defaults_apply_when_optional_vars_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", key)
        monkeypatch.setenv("JWT_SECRET", "x" * 32)
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("FYERS_APP_ID", raising=False)

        settings = config.get_settings()
        assert settings.redis_url == "redis://localhost:6379/0"
        assert settings.fyers_app_id == ""
        assert settings.jwt_algorithm == "HS256"
        assert settings.jwt_expire_minutes == 1440

    def test_lru_cache_returns_same_instance(self) -> None:
        a = config.get_settings()
        b = config.get_settings()
        assert a is b

    def test_cache_clear_yields_fresh_instance(self) -> None:
        a = config.get_settings()
        config.get_settings.cache_clear()
        b = config.get_settings()
        assert a is not b

    def test_missing_encryption_key_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        # pydantic ValidationError subclasses ValueError.
        with pytest.raises(ValueError, match="encryption_key"):
            config.get_settings()

    def test_short_encryption_key_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", "shortkey")
        with pytest.raises(ValueError, match="too short"):
            config.get_settings()

    def test_environment_enum_values(self) -> None:
        assert config.Environment.DEVELOPMENT.value == "development"
        assert config.Environment.STAGING.value == "staging"
        assert config.Environment.PRODUCTION.value == "production"
        assert config.Environment.TEST.value == "test"

    def test_loglevel_enum_values(self) -> None:
        assert {lv.value for lv in config.LogLevel} == {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }

    def test_is_production_false_for_other_envs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", key)
        monkeypatch.setenv("JWT_SECRET", "x" * 32)
        monkeypatch.setenv("ENVIRONMENT", "development")
        assert config.get_settings().is_production is False
