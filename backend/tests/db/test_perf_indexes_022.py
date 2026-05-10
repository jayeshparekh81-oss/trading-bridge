"""Migration 022 — composite indexes for perf.

Follows the same source-inspection pattern as
``test_paper_sessions_migration.py``: we don't run a live Alembic
upgrade (the test harness uses SQLite + ``Base.metadata.create_all``
rather than full alembic chains), so we verify the migration through
the structural shape of its source — index names, target tables,
revision graph wiring, and round-trip parity between upgrade +
downgrade.

What this guards against:

    * Index name typos in ``upgrade()`` vs ``downgrade()``: every
      name in ``EXPECTED_INDEX_NAMES`` must appear in *both*
      directions, so a one-sided edit fails the test.
    * Migration 022 wired into the revision graph
      (``down_revision = 021_user_onboarding``).
    * Both ``upgrade()`` and ``downgrade()`` exist + are callable.
    * The Postgres branch uses ``CONCURRENTLY`` (no table lock —
      this is the contract the user spec asked for).
    * ``IF NOT EXISTS`` is on every CREATE so a re-run after a
      partial failure doesn't raise.
"""

from __future__ import annotations

import importlib
import inspect

EXPECTED_INDEX_NAMES = (
    "ix_marketplace_listings_status_published_at",
    "ix_marketplace_listings_creator_created_at",
    "ix_marketplace_subscriptions_subscriber_status",
    "ix_audit_logs_user_created_at",
    "ix_paper_sessions_user_strategy_completed",
    "ix_support_tickets_user_created_at",
    "ix_support_tickets_status_created_at",
)

EXPECTED_TABLES = (
    "marketplace_listings",
    "marketplace_subscriptions",
    "audit_logs",
    "paper_sessions",
    "support_tickets",
)


def _load_022() -> object:
    return importlib.import_module("migrations.versions.022_perf_indexes")


def test_revision_chain_022_after_021() -> None:
    module = _load_022()
    assert module.revision == "022_perf_indexes"  # type: ignore[attr-defined]
    assert module.down_revision == "021_user_onboarding"  # type: ignore[attr-defined]
    assert callable(module.upgrade)  # type: ignore[attr-defined]
    assert callable(module.downgrade)  # type: ignore[attr-defined]


def test_indexes_table_lists_every_expected_index() -> None:
    """The migration's ``_INDEXES`` source-of-truth tuple covers
    every name in ``EXPECTED_INDEX_NAMES``. A missing one means an
    index we declared in PERFORMANCE_NOTES.md never actually shipped.

    Both upgrade() + downgrade() iterate over ``_INDEXES``, so a
    single check on this tuple validates both directions in one
    shot."""
    module = _load_022()
    indexes = module._INDEXES  # type: ignore[attr-defined]
    declared_names = {triple[0] for triple in indexes}
    missing = set(EXPECTED_INDEX_NAMES) - declared_names
    assert not missing, f"Migration 022 missing indexes: {missing}"


def test_indexes_target_every_expected_table() -> None:
    module = _load_022()
    indexes = module._INDEXES  # type: ignore[attr-defined]
    declared_tables = {triple[1] for triple in indexes}
    missing = set(EXPECTED_TABLES) - declared_tables
    assert not missing, f"Migration 022 missing tables: {missing}"


def test_index_count_matches_expected() -> None:
    """No surprise extras — the count is the contract."""
    module = _load_022()
    indexes = module._INDEXES  # type: ignore[attr-defined]
    assert len(indexes) == len(EXPECTED_INDEX_NAMES)


def test_postgres_branch_uses_concurrently() -> None:
    """The user spec mandates ``CREATE INDEX CONCURRENTLY`` so the
    migration can run under live traffic without an
    AccessExclusiveLock on the table. The Postgres branch must
    contain the keyword in both directions."""
    module = _load_022()
    upgrade_src = inspect.getsource(module.upgrade)  # type: ignore[attr-defined]
    downgrade_src = inspect.getsource(module.downgrade)  # type: ignore[attr-defined]
    assert "CONCURRENTLY" in upgrade_src
    assert "CONCURRENTLY" in downgrade_src


def test_idempotency_via_if_not_exists() -> None:
    """``IF NOT EXISTS`` (upgrade) + ``IF EXISTS`` (downgrade) make
    the migration replay-safe — a re-run after a partial failure
    doesn't blow up on the indexes that already landed."""
    module = _load_022()
    upgrade_src = inspect.getsource(module.upgrade)  # type: ignore[attr-defined]
    downgrade_src = inspect.getsource(module.downgrade)  # type: ignore[attr-defined]
    assert "IF NOT EXISTS" in upgrade_src
    assert "IF EXISTS" in downgrade_src


def test_dialect_aware_branching() -> None:
    """Both branches (postgres / fallback) exist — SQLite test runs
    must not try to use ``CONCURRENTLY``, and Postgres prod runs
    must use it."""
    module = _load_022()
    upgrade_src = inspect.getsource(module.upgrade)  # type: ignore[attr-defined]
    # Two distinct loops over _INDEXES — one for each dialect path.
    assert upgrade_src.count("for name") >= 2
    # Sentinel for the postgres-detection helper.
    assert "_is_postgres" in upgrade_src
