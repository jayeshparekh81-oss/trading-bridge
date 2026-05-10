"""Migration 012 — cached Trust + Truth scores structural validation.

Same pattern as the prior two migration tests: assert ORM model
metadata + revision-graph linkage + upgrade/downgrade source. Real
Postgres exercise happens in deployment, not in this harness.
"""

from __future__ import annotations

import importlib

from app.db.base import Base


def test_strategies_table_has_cached_score_columns() -> None:
    table = Base.metadata.tables["strategies"]
    for col_name in (
        "last_trust_score",
        "last_truth_score",
        "last_scores_at",
    ):
        assert col_name in table.columns, f"missing column {col_name}"
        assert table.columns[col_name].nullable is True


def test_strategies_last_scores_at_is_indexed() -> None:
    table = Base.metadata.tables["strategies"]
    indexed_columns = {
        tuple(c.name for c in idx.columns) for idx in table.indexes
    }
    assert ("last_scores_at",) in indexed_columns


def test_migration_012_chains_after_011() -> None:
    module = importlib.import_module(
        "migrations.versions.012_strategies_cached_scores"
    )
    assert module.revision == "012_strategies_cached_scores"
    assert module.down_revision == "011_users_live_trading_enabled"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_012_adds_three_columns_and_drops_them() -> None:
    """Source-string inspection for the upgrade/downgrade contracts."""
    import inspect

    module = importlib.import_module(
        "migrations.versions.012_strategies_cached_scores"
    )
    upgrade_src = inspect.getsource(module.upgrade)
    downgrade_src = inspect.getsource(module.downgrade)

    for col_name in ("last_trust_score", "last_truth_score", "last_scores_at"):
        assert f'"{col_name}"' in upgrade_src
        assert f'drop_column("strategies", "{col_name}")' in downgrade_src

    assert "create_index" in upgrade_src
    assert "drop_index" in downgrade_src
