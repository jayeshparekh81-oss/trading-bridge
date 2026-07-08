"""Standalone read-only credential loader.

Reuses the SAME daily-minted Dhan token the live system uses. That token is
NOT in any env file — ``scripts/auto_login.py`` (03:00 UTC cron) writes it as a
Fernet-encrypted row in the Postgres ``broker_credentials`` table. We read the
active row and decrypt it exactly as the app does (``decrypt_credential``),
WITHOUT importing any app module and WITHOUT any login/TOTP flow.

Required env (from the shared repo .env files, loaded by ``load_env_files``):
  DATABASE_URL      Postgres DSN
  ENCRYPTION_KEY    Fernet key used to encrypt the credential columns
  DEFAULT_USER_ID   owner of the active Dhan credential row

This module performs ONLY a SELECT. It never writes to the DB.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger("recorder.creds")


@dataclass
class DhanCreds:
    client_id: str
    access_token: str
    expires_at: Optional[datetime] = None

    def masked(self) -> str:
        tok = self.access_token or ""
        tail = tok[-4:] if len(tok) >= 4 else "??"
        return f"client_id={self.client_id} token=…{tail} expires={self.expires_at}"


def load_env_files(paths: list[str | Path]) -> None:
    """Populate os.environ from KEY=VALUE .env files without overriding values
    already present in the environment (so Docker env_file / real env wins)."""
    for path in paths:
        p = Path(path)
        if not p.exists():
            continue
        for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def get_dhan_credentials(*, database_url: Optional[str] = None,
                         encryption_key: Optional[str] = None,
                         user_id: Optional[str] = None,
                         broker_name: str = "dhan") -> DhanCreds:
    """Load and decrypt the active Dhan credential row. Raises RuntimeError with
    a clear message on any misconfiguration or if no active row exists."""
    database_url = database_url or os.environ.get("DATABASE_URL")
    encryption_key = encryption_key or os.environ.get("ENCRYPTION_KEY")
    user_id = user_id or os.environ.get("DEFAULT_USER_ID")

    missing = [n for n, v in (("DATABASE_URL", database_url),
                              ("ENCRYPTION_KEY", encryption_key),
                              ("DEFAULT_USER_ID", user_id)) if not v]
    if missing:
        raise RuntimeError(f"missing required env for credential load: {', '.join(missing)}")

    # Imported lazily so unit tests that don't touch the DB don't need the libs.
    import psycopg
    from cryptography.fernet import Fernet

    query = (
        "SELECT client_id_enc, access_token_enc, token_expires_at "
        "FROM broker_credentials "
        "WHERE lower(broker_name) = lower(%s) AND user_id = %s AND is_active = true "
        "ORDER BY created_at DESC LIMIT 1"
    )
    with psycopg.connect(database_url, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (broker_name, user_id))
            row = cur.fetchone()

    if row is None:
        raise RuntimeError(
            f"no active '{broker_name}' credential row for user_id={user_id}; "
            "has auto_login.py run today?"
        )

    client_id_enc, access_token_enc, expires_at = row
    fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)

    def _dec(val) -> str:
        if val is None:
            raise RuntimeError("credential column is NULL")
        if isinstance(val, memoryview):
            val = bytes(val)
        if isinstance(val, str):
            val = val.encode()
        return fernet.decrypt(val).decode()

    creds = DhanCreds(client_id=_dec(client_id_enc),
                      access_token=_dec(access_token_enc),
                      expires_at=expires_at)

    if expires_at is not None:
        now = datetime.now(timezone.utc)
        exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        if exp <= now:
            log.warning("Dhan token already expired at %s (now %s) — recorder may fail auth",
                        exp, now)
    log.info("loaded Dhan credentials: %s", creds.masked())
    return creds
