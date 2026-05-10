"""Cache the latest Trust + Truth scores on each strategy row.

Phase 8B-1 discovery exposed that Trust and Truth are computed during
the backtest pipeline and held only in the response. The live-orders
SafetyChain enforces Trust >= 70 and Truth >= 55 on every place_live_order
call — re-running the full backtest there would double the latency and
the AI / data costs. Instead the backtest endpoint writes the freshly
computed scores onto the strategy row, and the SafetyChain reads them
with a 24h staleness check. Stale or NULL → block with "Run a fresh
backtest first."

Tables touched:
    * ``strategies`` — three new nullable columns:
        * ``last_trust_score`` NUMERIC(5,2)
        * ``last_truth_score`` NUMERIC(5,2)
        * ``last_scores_at``   TIMESTAMP WITH TIME ZONE
      Plus an index on ``last_scores_at`` so the SafetyChain's
      staleness query is cheap.

Backfill:
    Existing rows get ``NULL`` for all three columns. The next backtest
    each strategy runs will populate them. SafetyChain treats NULL as
    "no scores yet" and blocks — same surface as "stale".

Revision ID: 012_strategies_cached_scores
Revises: 011_users_live_trading_enabled
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012_strategies_cached_scores"
down_revision: str | None = "011_users_live_trading_enabled"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "strategies",
        sa.Column("last_trust_score", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "strategies",
        sa.Column("last_truth_score", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "strategies",
        sa.Column(
            "last_scores_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_strategies_last_scores_at",
        "strategies",
        ["last_scores_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_strategies_last_scores_at", table_name="strategies")
    op.drop_column("strategies", "last_scores_at")
    op.drop_column("strategies", "last_truth_score")
    op.drop_column("strategies", "last_trust_score")
