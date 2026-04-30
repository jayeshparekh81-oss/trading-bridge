"""Position-manager universal-cockpit fields (Phase 1).

Revision ID: 006_position_manager_universal
Revises: 005_strategy_engine
Create Date: 2026-04-30

Adds the columns the upgraded position manager and the May-18 Phase-1
launch (Future + Options on TRADETRI cockpit) need:

    strategy_positions
        best_price, current_atr,
        circuit_breaker_triggered, exit_reason
    strategies
        instrument_type, exchange, preferred_broker
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006_position_manager_universal"
down_revision: str | None = "005_strategy_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "strategy_positions",
        sa.Column("best_price", sa.Numeric(12, 4), nullable=True),
    )
    op.add_column(
        "strategy_positions",
        sa.Column("current_atr", sa.Numeric(10, 4), nullable=True),
    )
    op.add_column(
        "strategy_positions",
        sa.Column(
            "circuit_breaker_triggered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "strategy_positions",
        sa.Column("exit_reason", sa.String(50), nullable=True),
    )

    op.add_column(
        "strategies",
        sa.Column(
            "instrument_type",
            sa.String(20),
            nullable=False,
            server_default="futures",
        ),
    )
    op.add_column(
        "strategies",
        sa.Column(
            "exchange",
            sa.String(10),
            nullable=False,
            server_default="NFO",
        ),
    )
    op.add_column(
        "strategies",
        sa.Column("preferred_broker", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("strategies", "preferred_broker")
    op.drop_column("strategies", "exchange")
    op.drop_column("strategies", "instrument_type")

    op.drop_column("strategy_positions", "exit_reason")
    op.drop_column("strategy_positions", "circuit_breaker_triggered")
    op.drop_column("strategy_positions", "current_atr")
    op.drop_column("strategy_positions", "best_price")
