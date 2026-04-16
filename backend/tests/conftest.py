"""Shared pytest fixtures.

Keeps ``sys.path`` sane so ``app.*`` imports work whether tests are run
from the repo root or from ``backend/``.

Also seeds the env vars that :mod:`app.core.config` and
:mod:`app.core.security` require, so individual test modules don't have
to repeat themselves. Tests that want to assert on the missing-key
RuntimeError can override via ``monkeypatch.delenv``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Deterministic per-process key — generated once, reused everywhere.
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault(
    "JWT_SECRET", "test-jwt-secret-do-not-use-in-production-32bytes"
)
os.environ.setdefault("ENVIRONMENT", "test")
