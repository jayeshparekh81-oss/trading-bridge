"""Composite indexes for hot read paths — performance phase 1.

Each index pairs the column we filter by with the column we ORDER
BY (or filter+filter) so a single index lookup serves the query
without a separate sort step. Verified against actual queries in
:mod:`app.strategy_engine.api.marketplace`,
:mod:`app.strategy_engine.api.support`, and the audit-log /
paper-trading list paths.

Indexes added:

    1. ``ix_marketplace_listings_status_published_at`` —
       browse_listings: ``WHERE status='published' ORDER BY published_at DESC``
    2. ``ix_marketplace_listings_creator_created_at`` —
       list_my_listings: ``WHERE creator_id=? ORDER BY created_at DESC``
    3. ``ix_marketplace_subscriptions_subscriber_status`` —
       list_my_subscriptions: ``WHERE subscriber_id=? AND status=?``
    4. ``ix_audit_logs_user_created_at`` —
       user activity log: ``WHERE user_id=? ORDER BY created_at DESC``
    5. ``ix_paper_sessions_user_strategy_completed`` —
       paper-history queries: ``WHERE user_id=? [AND strategy_id=?]``
       ``ORDER BY completed_at DESC``
    6. ``ix_support_tickets_user_created_at`` —
       my-tickets list: ``WHERE user_id=? ORDER BY created_at DESC``
    7. ``ix_support_tickets_status_created_at`` —
       admin queue: ``WHERE status='open' ORDER BY created_at DESC``

On Postgres these are created with ``CONCURRENTLY`` (no table
lock — safe to run while traffic is live). On SQLite (used in
tests) they fall back to a plain ``CREATE INDEX`` since SQLite
doesn't have the keyword.

Reversible — every index has a matching ``DROP INDEX`` in
``downgrade()``.

Revision ID: 022_perf_indexes
Revises: 021_user_onboarding
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "022_perf_indexes"
down_revision: str | None = "021_user_onboarding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: ``(name, table, columns SQL fragment)`` triples. A single source
#: of truth used by both upgrade() and downgrade() so the two
#: directions can't drift.
_INDEXES: tuple[tuple[str, str, str], ...] = (
    (
        "ix_marketplace_listings_status_published_at",
        "marketplace_listings",
        "(status, published_at DESC)",
    ),
    (
        "ix_marketplace_listings_creator_created_at",
        "marketplace_listings",
        "(creator_id, created_at DESC)",
    ),
    (
        "ix_marketplace_subscriptions_subscriber_status",
        "marketplace_subscriptions",
        "(subscriber_id, status)",
    ),
    (
        "ix_audit_logs_user_created_at",
        "audit_logs",
        "(user_id, created_at DESC)",
    ),
    (
        "ix_paper_sessions_user_strategy_completed",
        "paper_sessions",
        "(user_id, strategy_id, completed_at DESC)",
    ),
    (
        "ix_support_tickets_user_created_at",
        "support_tickets",
        "(user_id, created_at DESC)",
    ),
    (
        "ix_support_tickets_status_created_at",
        "support_tickets",
        "(status, created_at DESC)",
    ),
)


def _is_postgres() -> bool:
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgres():
        # CONCURRENTLY can't run inside a transaction. Alembic wraps
        # each migration in BEGIN/COMMIT by default; the
        # autocommit_block exits that wrap for the indexed-column
        # statements then re-enters it on exit.
        with op.get_context().autocommit_block():
            for name, table, cols in _INDEXES:
                op.execute(
                    f"CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                    f"{name} ON {table} {cols}"
                )
    else:
        # SQLite (tests) doesn't support CONCURRENTLY; drop the
        # keyword and fall back to a normal create. SQLite also
        # ignores ``DESC`` in index definitions but accepts the
        # syntax — which is fine for our use case.
        for name, table, cols in _INDEXES:
            op.execute(
                f"CREATE INDEX IF NOT EXISTS {name} ON {table} {cols}"
            )


def downgrade() -> None:
    # CONCURRENTLY is also valid on DROP INDEX in Postgres and
    # avoids the AccessExclusiveLock that a plain DROP would take.
    if _is_postgres():
        with op.get_context().autocommit_block():
            for name, _table, _cols in _INDEXES:
                op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
    else:
        for name, _table, _cols in _INDEXES:
            op.execute(f"DROP INDEX IF EXISTS {name}")
