"""Tests for startup validation checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from app.core import security


@pytest.fixture(autouse=True)
def _reset_cipher(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    security.reset_cipher_cache()


class TestEncryptionKeyCheck:
    def test_valid_key_passes(self) -> None:
        from app.core.config import get_settings
        from app.core.startup_checks import _check_encryption_key

        settings = get_settings()
        # Should not raise
        _check_encryption_key(settings)

    def test_short_key_fails(self) -> None:
        from app.core.startup_checks import StartupCheckError, _check_encryption_key

        settings = MagicMock()
        settings.encryption_key.get_secret_value.return_value = "short"

        with pytest.raises(StartupCheckError, match="ENCRYPTION_KEY"):
            _check_encryption_key(settings)

    def test_empty_key_fails(self) -> None:
        from app.core.startup_checks import StartupCheckError, _check_encryption_key

        settings = MagicMock()
        settings.encryption_key.get_secret_value.return_value = ""

        with pytest.raises(StartupCheckError, match="ENCRYPTION_KEY"):
            _check_encryption_key(settings)

    def test_invalid_fernet_key_fails(self) -> None:
        from app.core.startup_checks import StartupCheckError, _check_encryption_key

        settings = MagicMock()
        settings.encryption_key.get_secret_value.return_value = "x" * 44  # right length, wrong format

        with pytest.raises(StartupCheckError, match="valid Fernet"):
            _check_encryption_key(settings)


class TestJWTSecretCheck:
    def test_valid_secret_passes(self) -> None:
        from app.core.config import get_settings
        from app.core.startup_checks import _check_jwt_secret

        settings = get_settings()
        _check_jwt_secret(settings)

    def test_short_secret_fails(self) -> None:
        from app.core.startup_checks import StartupCheckError, _check_jwt_secret

        settings = MagicMock()
        settings.jwt_secret.get_secret_value.return_value = "short"

        with pytest.raises(StartupCheckError, match="JWT_SECRET"):
            _check_jwt_secret(settings)

    def test_empty_secret_fails(self) -> None:
        from app.core.startup_checks import StartupCheckError, _check_jwt_secret

        settings = MagicMock()
        settings.jwt_secret.get_secret_value.return_value = ""

        with pytest.raises(StartupCheckError, match="JWT_SECRET"):
            _check_jwt_secret(settings)


class TestDatabaseCheck:
    @pytest.mark.asyncio
    async def test_db_unreachable_fails(self) -> None:
        from app.core.startup_checks import StartupCheckError, _check_database

        settings = MagicMock()
        settings.database_url = "postgresql+asyncpg://user:pass@unreachable:5432/db"

        with pytest.raises(StartupCheckError, match="Database not reachable"):
            await _check_database(settings)


class TestRedisCheck:
    @pytest.mark.asyncio
    async def test_redis_unreachable_fails(self) -> None:
        from app.core.startup_checks import StartupCheckError, _check_redis

        settings = MagicMock()
        settings.redis_url = "redis://unreachable-host:6379/0"

        with pytest.raises(StartupCheckError, match="Redis not reachable"):
            await _check_redis(settings)


class TestSystemInfo:
    def test_system_info_returns_dict(self) -> None:
        from app.core.config import get_settings
        from app.core.startup_checks import _system_info

        settings = get_settings()
        info = _system_info(settings)
        assert "python_version" in info
        assert "fastapi_version" in info
        assert "environment" in info

    def test_print_banner(self) -> None:
        from app.core.startup_checks import _print_banner

        # Should not raise
        _print_banner({"python_version": "3.11", "fastapi_version": "0.115", "environment": "test", "platform": "Darwin"})


class TestStartupCheckError:
    def test_is_runtime_error(self) -> None:
        from app.core.startup_checks import StartupCheckError

        err = StartupCheckError("test message")
        assert isinstance(err, RuntimeError)
        assert str(err) == "test message"
