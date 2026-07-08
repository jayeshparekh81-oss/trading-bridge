"""Credential-loader unit tests (pure helpers; no DB/network)."""

from __future__ import annotations

import os

import pytest

from recorder import creds


def test_normalize_dsn_strips_sqlalchemy_driver():
    assert creds.normalize_dsn("postgresql+asyncpg://u:p@postgres:5432/db") == \
        "postgresql://u:p@postgres:5432/db"
    assert creds.normalize_dsn("postgres+psycopg://u:p@h/db") == "postgresql://u:p@h/db"


def test_normalize_dsn_leaves_plain_url_untouched():
    plain = "postgresql://u:p@localhost:5432/db"
    assert creds.normalize_dsn(plain) == plain
    assert creds.normalize_dsn("") == ""


def test_load_env_files_does_not_override_existing(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text('DATABASE_URL=fromfile\nNEWVAR="quoted val"\n# comment\n')
    monkeypatch.setenv("DATABASE_URL", "fromenv")
    monkeypatch.delenv("NEWVAR", raising=False)
    creds.load_env_files([f])
    assert os.environ["DATABASE_URL"] == "fromenv"   # existing env wins
    assert os.environ["NEWVAR"] == "quoted val"       # new key loaded + unquoted


def test_get_credentials_missing_env_raises(monkeypatch):
    for k in ("DATABASE_URL", "ENCRYPTION_KEY", "DEFAULT_USER_ID"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError, match="missing required env"):
        creds.get_dhan_credentials()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
