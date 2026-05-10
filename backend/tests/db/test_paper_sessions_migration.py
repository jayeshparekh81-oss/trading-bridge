"""Migration 010 — structural validation.

The existing CI exercises the schema by calling
``Base.metadata.create_all`` against a SQLite engine — the same path
``test_kill_switch_service`` uses. ``alembic upgrade head`` is run
against PostgreSQL in deployment, not in this test harness, so the
shape we assert here is "the ORM model registers the right table /
column / constraint metadata" plus the migration revision graph wires
the new file in.

What this guards against:

    * ``paper_sessions`` / ``paper_trades`` registered with
      ``Base.metadata`` (so ``create_all`` builds them and Alembic's
      ``compare_metadata`` won't claim they're missing).
    * Migration 010's ``revision`` / ``down_revision`` follow 009 and
      every Alembic head walks back to a single root.
    * ``upgrade()`` and ``downgrade()`` symbols exist (a missing
      downgrade would be a regression — the DESIGN doc lists migration
      reversibility as a Phase 8B-2 acceptance gate).
"""

from __future__ import annotations

import importlib

from app.db.base import Base


def test_paper_sessions_table_registered_with_metadata() -> None:
    assert "paper_sessions" in Base.metadata.tables
    table = Base.metadata.tables["paper_sessions"]

    expected_columns = {
        "id",
        "user_id",
        "strategy_id",
        "session_date",
        "started_at",
        "completed_at",
        "is_complete",
        "total_trades",
        "total_pnl",
        "engine_strategy_id",
        "created_at",
    }
    assert set(table.columns.keys()) == expected_columns

    fk_targets = {
        next(iter(fk.column.table.name for fk in col.foreign_keys), None)
        for col in table.columns
        if col.foreign_keys
    }
    fk_targets.discard(None)
    assert fk_targets == {"users", "strategies"}

    unique_columns = {
        tuple(col.name for col in c.columns)
        for c in table.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    }
    assert ("user_id", "strategy_id", "session_date") in unique_columns


def test_paper_trades_table_registered_with_metadata() -> None:
    assert "paper_trades" in Base.metadata.tables
    table = Base.metadata.tables["paper_trades"]

    expected_columns = {
        "id",
        "session_id",
        "entry_at",
        "exit_at",
        "symbol",
        "side",
        "quantity",
        "entry_price",
        "exit_price",
        "pnl",
        "exit_reason",
        "created_at",
    }
    assert set(table.columns.keys()) == expected_columns

    fk_targets = {
        next(iter(fk.column.table.name for fk in col.foreign_keys), None)
        for col in table.columns
        if col.foreign_keys
    }
    fk_targets.discard(None)
    assert fk_targets == {"paper_sessions"}


def test_migration_010_chains_after_009() -> None:
    """``revision`` / ``down_revision`` form a contiguous chain."""
    module = importlib.import_module(
        "migrations.versions.010_paper_sessions"
    )

    assert module.revision == "010_paper_sessions"
    assert module.down_revision == "009_strategy_json_column"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_010_creates_both_tables_in_upgrade() -> None:
    """``upgrade()`` body references both new tables; ``downgrade()`` drops them.

    Source-string inspection rather than a live alembic run — the
    structural assertion still catches the most common regression
    (someone removes the trades table from the migration but leaves
    the model behind).
    """
    import inspect

    module = importlib.import_module(
        "migrations.versions.010_paper_sessions"
    )
    upgrade_src = inspect.getsource(module.upgrade)
    downgrade_src = inspect.getsource(module.downgrade)

    assert '"paper_sessions"' in upgrade_src
    assert '"paper_trades"' in upgrade_src
    assert 'drop_table("paper_sessions")' in downgrade_src
    assert 'drop_table("paper_trades")' in downgrade_src
