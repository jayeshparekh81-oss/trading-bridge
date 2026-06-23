"""Migration 035 — per-subscriber execution fields structural validation.

Asserts the ORM model registers the five NEW columns on
``marketplace_subscriptions`` (additive — nullable, or NOT NULL with a safe
server-default), the revision graph chains off 034, and ``upgrade()`` only adds
columns while ``downgrade()`` drops them. ``alembic upgrade`` runs against a real
Postgres in deployment, not in this harness.
"""

from __future__ import annotations

import importlib
import inspect

from app.db.base import Base

_TABLE = "marketplace_subscriptions"


def test_subscription_table_has_new_execution_columns() -> None:
    cols = Base.metadata.tables[_TABLE].columns

    # Nullable additions (no default needed).
    assert cols["lots_override"].nullable is True
    assert cols["broker_credential_id"].nullable is True

    # NOT NULL but with a SAFE server-default -> existing rows fill automatically.
    for name in ("execution_mode", "is_paper", "direction_filter"):
        assert cols[name].nullable is False, name
        assert cols[name].server_default is not None, name


def test_migration_035_chains_after_034() -> None:
    module = importlib.import_module(
        "migrations.versions.035_subscription_execution_fields"
    )
    assert module.revision == "035_subscription_execution_fields"
    assert module.down_revision == "034_subscription_position_scoping"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_035_is_additive_and_reversible() -> None:
    module = importlib.import_module(
        "migrations.versions.035_subscription_execution_fields"
    )
    upgrade_src = inspect.getsource(module.upgrade)
    downgrade_src = inspect.getsource(module.downgrade)

    # Additive: only the subscriber table, only add_column (one per new column).
    assert module._TABLE == "marketplace_subscriptions"
    assert upgrade_src.count("add_column") == 5
    assert "op.execute" not in upgrade_src  # no raw data backfill
    assert "update" not in upgrade_src.lower()  # no data backfill
    assert "drop_column" not in upgrade_src  # touches no existing column

    # The three NOT-NULL columns ship a safe server_default.
    assert 'server_default="auto"' in upgrade_src
    assert "server_default=sa.true()" in upgrade_src
    assert 'server_default="all"' in upgrade_src

    # Reversible: downgrade drops all five columns.
    assert downgrade_src.count("drop_column") == 5
