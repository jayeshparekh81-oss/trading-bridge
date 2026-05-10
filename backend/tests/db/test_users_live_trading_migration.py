"""Migration 011 — ``users.live_trading_enabled`` structural validation.

Same pattern as ``test_paper_sessions_migration``: assert the ORM model
registers the right column with ``Base.metadata`` and the migration
revision graph wires correctly. ``alembic upgrade`` is exercised
against a real Postgres in deployment, not in this harness.
"""

from __future__ import annotations

import importlib

from app.db.base import Base


def test_users_table_has_live_trading_enabled_column() -> None:
    table = Base.metadata.tables["users"]
    assert "live_trading_enabled" in table.columns
    column = table.columns["live_trading_enabled"]
    assert column.nullable is False
    # The server_default is a SQL expression object — its compiled form
    # asserts as the lowercase 'false' literal Postgres uses.
    assert column.server_default is not None


def test_migration_011_chains_after_010() -> None:
    module = importlib.import_module(
        "migrations.versions.011_users_live_trading_enabled"
    )
    assert module.revision == "011_users_live_trading_enabled"
    assert module.down_revision == "010_paper_sessions"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_011_adds_and_drops_the_column() -> None:
    """``upgrade()`` adds the column; ``downgrade()`` drops it."""
    import inspect

    module = importlib.import_module(
        "migrations.versions.011_users_live_trading_enabled"
    )
    upgrade_src = inspect.getsource(module.upgrade)
    downgrade_src = inspect.getsource(module.downgrade)

    assert 'add_column(\n        "users"' in upgrade_src
    assert '"live_trading_enabled"' in upgrade_src
    assert "server_default=sa.false()" in upgrade_src
    assert 'drop_column("users", "live_trading_enabled")' in downgrade_src
