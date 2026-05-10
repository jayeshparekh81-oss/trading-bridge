"""Per-user live-trading opt-in column.

Phase 8B-1 discovery exposed that ``LIVE_TRADING_ENABLED`` is a *global*
feature flag — flipping it would enable real-money orders for every
user simultaneously. The launch plan requires manual per-user approval
(7 paper sessions + Trust >= 70 + Truth >= 55 + admin sign-off), so the
gate must be per-user.

This migration adds a boolean column ``users.live_trading_enabled``,
default ``FALSE``. The live-orders SafetyChain will require BOTH this
column AND the global flag to be ``TRUE``; the global flag stays as a
master kill-switch ("turn live trading off for everyone right now")
while the per-user column carries the day-to-day approval state.

Backfill:
    Existing rows get ``FALSE`` automatically via the column-level
    ``server_default``. No data backfill is needed — the safe default
    preserves the launch plan's "explicit admin approval" property.

Revision ID: 011_users_live_trading_enabled
Revises: 010_paper_sessions
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011_users_live_trading_enabled"
down_revision: str | None = "010_paper_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "live_trading_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "live_trading_enabled")
