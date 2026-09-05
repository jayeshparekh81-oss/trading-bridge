"""Customer-lane test setup.

These tests need the throwaway Postgres on localhost:5433 with the ``cl_scratch``
database migrated to head. Without it the suite previously produced ~60 cryptic
connection errors; a suite that fails until someone remembers a command from a
chat transcript is a trap. This fails ONCE, at collection, and names the script.
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

import pytest

DEFAULT_URL = (
    "postgresql+asyncpg://trading_bridge_test:test_password_do_not_use_in_prod"
    "@localhost:5433/cl_scratch"
)
SETUP = "backend/scripts/cl_test_db.sh"


def _reachable(url: str) -> tuple[bool, str]:
    parsed = urlparse(url.replace("postgresql+asyncpg://", "postgresql://"))
    host, port = parsed.hostname or "localhost", parsed.port or 5432
    try:
        with socket.create_connection((host, port), timeout=2):
            return True, ""
    except OSError as exc:
        return False, f"{host}:{port} — {exc}"


def pytest_collection_modifyitems(config, items):
    """Fail loudly and ONCE with the fix, rather than 60 times with a stack trace."""
    if not any("customer_lane" in str(i.fspath) for i in items):
        return
    url = os.environ.get("CL_SCRATCH_URL", DEFAULT_URL)
    ok, why = _reachable(url)
    if ok:
        return
    raise pytest.UsageError(
        "\n"
        "customer-lane tests need the scratch Postgres and it is not reachable.\n"
        f"  tried : {why}\n"
        "\n"
        "  fix   : docker start trading_bridge_postgres_test\n"
        f"          {SETUP}\n"
        "\n"
        "  then  : CL_SCRATCH_URL=... DATABASE_URL=... pytest tests/customer_lane/\n"
        f"  (the script prints the exact command; see {SETUP})"
    )
