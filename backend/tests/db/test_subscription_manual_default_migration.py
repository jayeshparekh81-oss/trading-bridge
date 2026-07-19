"""Migration 040 — flip ``marketplace_subscriptions.execution_mode`` DEFAULT to MANUAL.

Structural / source validation (the repo convention for migration tests — the
real ``alembic upgrade`` runs against Postgres at deploy, not here). Asserts the
migration chains off the current head (039), is DEFAULT-ONLY (no add/drop column,
no data backfill — existing rows untouched), flips the server-default
'auto' -> 'offline', and the downgrade restores 'auto'.
"""

from __future__ import annotations

import importlib
import inspect

_MODULE = "migrations.versions.040_manual_exec_default"
_TABLE = "marketplace_subscriptions"


def _code_only(fn) -> str:
    """Source of ``fn`` with ``#`` comments stripped — so the forbidden-token
    checks below assert on actual CODE, not on prose in the comments (which
    legitimately mentions ``op.execute`` / UPDATE to explain what it does NOT do).
    Safe here: these migration function bodies contain no string literals with
    a ``#``."""
    lines = []
    for line in inspect.getsource(fn).splitlines():
        code = line.split("#", 1)[0]
        if code.strip():
            lines.append(code)
    return "\n".join(lines)


def test_migration_040_chains_after_039_head() -> None:
    module = importlib.import_module(_MODULE)
    assert module.revision == "040_manual_exec_default"  # <=32 chars
    assert len(module.revision) <= 32
    assert module.down_revision == "039_fix_premium_bullet"  # the prior single head
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_040_is_default_only_no_row_touch() -> None:
    module = importlib.import_module(_MODULE)
    upgrade_code = _code_only(module.upgrade)

    assert module._TABLE == _TABLE  # touches only the subscriber table
    assert module._COLUMN == "execution_mode"

    # DEFAULT-ONLY: exactly one alter_column, no schema churn, no backfill.
    assert upgrade_code.count("alter_column") == 1
    assert "add_column" not in upgrade_code  # adds no column
    assert "drop_column" not in upgrade_code  # drops no column
    assert "create_check_constraint" not in upgrade_code  # CHECK untouched
    assert "op.execute" not in upgrade_code  # no raw SQL / data backfill
    assert "update" not in upgrade_code.lower()  # existing rows NOT rewritten


def test_migration_040_flips_default_to_offline_and_is_reversible() -> None:
    module = importlib.import_module(_MODULE)
    upgrade_code = _code_only(module.upgrade)
    downgrade_code = _code_only(module.downgrade)

    # Upgrade sets the new MANUAL default; downgrade restores the old 'auto'.
    assert module._OLD_DEFAULT == "auto"
    assert module._NEW_DEFAULT == "offline"
    assert "server_default=_NEW_DEFAULT" in upgrade_code
    assert "server_default=_OLD_DEFAULT" in downgrade_code
    assert downgrade_code.count("alter_column") == 1
