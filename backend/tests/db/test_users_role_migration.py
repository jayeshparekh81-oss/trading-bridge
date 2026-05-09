"""Migration 013 — ``users.role`` structural validation.

Same pattern as the prior migration tests: assert ORM model
metadata + revision-graph linkage + upgrade/downgrade source. Real
Postgres exercises happen in deployment, not in this harness.
"""

from __future__ import annotations

import importlib

from app.db.base import Base


def test_users_table_has_role_column() -> None:
    table = Base.metadata.tables["users"]
    assert "role" in table.columns
    column = table.columns["role"]
    assert column.nullable is False
    # ``server_default="user"`` so existing rows backfill at-rest.
    assert column.server_default is not None


def test_users_role_is_indexed() -> None:
    table = Base.metadata.tables["users"]
    indexed_columns = {
        tuple(c.name for c in idx.columns) for idx in table.indexes
    }
    assert ("role",) in indexed_columns


def test_migration_013_chains_after_012() -> None:
    module = importlib.import_module(
        "migrations.versions.013_users_role"
    )
    assert module.revision == "013_users_role"
    assert module.down_revision == "012_strategies_cached_scores"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_013_upgrade_adds_column_index_and_backfill() -> None:
    """Source-string inspection — pins the column add, backfill UPDATE,
    and the ``ix_users_role`` index that the admin tier-listing
    queries depend on."""
    import inspect

    module = importlib.import_module(
        "migrations.versions.013_users_role"
    )
    upgrade_src = inspect.getsource(module.upgrade)
    downgrade_src = inspect.getsource(module.downgrade)

    # Column add with server_default.
    assert '"role"' in upgrade_src
    assert 'server_default="user"' in upgrade_src
    # Backfill admins from is_admin.
    assert "UPDATE users SET role = 'admin'" in upgrade_src
    assert "is_admin = TRUE" in upgrade_src
    # Index.
    assert 'create_index("ix_users_role"' in upgrade_src
    # Downgrade reverses both.
    assert 'drop_column("users", "role")' in downgrade_src
    assert 'drop_index("ix_users_role"' in downgrade_src
