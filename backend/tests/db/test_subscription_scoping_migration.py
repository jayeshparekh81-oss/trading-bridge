"""Migration 034 — ``subscription_id`` scoping structural validation.

Same pattern as ``test_users_live_trading_migration``: assert the ORM models
register the new column with ``Base.metadata`` (nullable — additive), the
migration revision graph wires correctly off 033, and ``upgrade()`` adds /
``downgrade()`` drops the columns. ``alembic upgrade`` runs against a real
Postgres in deployment, not in this harness.
"""

from __future__ import annotations

import importlib
import inspect

from app.db.base import Base


def test_strategy_positions_subscription_id_is_nullable_additive() -> None:
    table = Base.metadata.tables["strategy_positions"]
    assert "subscription_id" in table.columns
    col = table.columns["subscription_id"]
    assert col.nullable is True  # additive — owner rows stay NULL
    assert col.server_default is None  # no backfill / no default


def test_strategy_executions_subscription_id_is_nullable_additive() -> None:
    table = Base.metadata.tables["strategy_executions"]
    assert "subscription_id" in table.columns
    col = table.columns["subscription_id"]
    assert col.nullable is True
    assert col.server_default is None


def test_migration_034_chains_after_033() -> None:
    module = importlib.import_module(
        "migrations.versions.034_subscription_position_scoping"
    )
    assert module.revision == "034_subscription_position_scoping"
    assert module.down_revision == "033_strategy_state_audit"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_034_is_additive_and_reversible() -> None:
    module = importlib.import_module(
        "migrations.versions.034_subscription_position_scoping"
    )
    upgrade_src = inspect.getsource(module.upgrade)
    downgrade_src = inspect.getsource(module.downgrade)

    # Additive: add_column on BOTH tables, nullable, no NOT NULL / no backfill.
    assert upgrade_src.count("add_column") == 2  # one per table
    assert '"subscription_id"' in upgrade_src
    assert "nullable=True" in upgrade_src
    assert "nullable=False" not in upgrade_src  # no NOT NULL column added
    assert "op.execute" not in upgrade_src  # no raw data backfill
    assert "update" not in upgrade_src.lower()  # no data backfill

    # The two target tables (referenced via module constants) are the position
    # + execution tables, and nothing else is altered.
    assert module._POSITIONS == "strategy_positions"
    assert module._EXECUTIONS == "strategy_executions"

    # Reversible: downgrade drops the column on BOTH tables.
    assert downgrade_src.count("drop_column") == 2
    assert '"subscription_id"' in downgrade_src
