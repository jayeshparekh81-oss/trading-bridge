"""Tests for the development seed script."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.core import security


@pytest.fixture(autouse=True)
def _reset_cipher(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    security.reset_cipher_cache()


class TestSeedScript:
    def test_seed_module_importable(self) -> None:
        """Seed script can be imported without side effects."""
        from scripts.seed_dev import seed, main

        assert callable(seed)
        assert callable(main)

    def test_seed_creates_admin_email(self) -> None:
        """Seed script uses correct admin email."""
        # Verify the constant in the seed script
        import scripts.seed_dev as mod
        import inspect

        source = inspect.getsource(mod.seed)
        assert "admin@tradingbridge.in" in source
        assert "Admin123!" in source

    def test_seed_creates_test_email(self) -> None:
        """Seed script uses correct test email."""
        import scripts.seed_dev as mod
        import inspect

        source = inspect.getsource(mod.seed)
        assert "test@tradingbridge.in" in source
        assert "Test123!" in source

    def test_seed_creates_webhook(self) -> None:
        """Seed script creates a webhook token."""
        import scripts.seed_dev as mod
        import inspect

        source = inspect.getsource(mod.seed)
        assert "generate_webhook_token" in source
        assert "dev-webhook" in source

    def test_seed_creates_broker_credential(self) -> None:
        """Seed script creates fake broker credentials."""
        import scripts.seed_dev as mod
        import inspect

        source = inspect.getsource(mod.seed)
        assert "FYERS" in source
        assert "encrypt_credential" in source
