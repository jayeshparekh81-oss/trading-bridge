"""Direct-exit architecture support.

Adds fields needed for Pine-driven ENTRY / PARTIAL / EXIT webhook
actions to coexist with the existing internal-exit (autonomous
target/SL/trail) flow.

  1. ``strategies.exit_strategy_type`` — switch between the two models:
       ``internal``    → position_loop autonomously triggers
                         partial/trail/hard SL based on strategy %-config
                         (existing behaviour, unchanged when value is
                         the default).
       ``direct_exit`` → position_loop is a no-op for these positions;
                         exits arrive as Pine-emitted webhook actions
                         (PARTIAL with ``closePct``, EXIT, SL_HIT).
  2. ``strategy_positions.last_action`` /
     ``strategy_positions.last_action_at`` /
     ``strategy_positions.action_history`` — per-position memory the
     direct-exit handler needs to reason about prior PARTIALs (server's
     mem-dict equivalent). ``action_history`` is JSONB so we can
     append-only without rewriting the whole array.

Revision ID: 008_direct_exit_support
Revises: 007_verified_pnl_schema
Create Date: 2026-05-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_direct_exit_support"
down_revision: str | None = "007_verified_pnl_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "strategies",
        sa.Column(
            "exit_strategy_type",
            sa.String(20),
            nullable=False,
            server_default="internal",
        ),
    )
    op.add_column(
        "strategy_positions",
        sa.Column("last_action", sa.String(20), nullable=True),
    )
    op.add_column(
        "strategy_positions",
        sa.Column(
            "last_action_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "strategy_positions",
        sa.Column(
            "action_history",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("strategy_positions", "action_history")
    op.drop_column("strategy_positions", "last_action_at")
    op.drop_column("strategy_positions", "last_action")
    op.drop_column("strategies", "exit_strategy_type")
