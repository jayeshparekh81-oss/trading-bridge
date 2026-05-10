"""Phase 5 — strategies.strategy_json (the user-built DSL blob).

Phase 5's REST surface (POST/PUT /api/strategies) accepts a validated
StrategyJSON document and persists it as the source of truth for the
backtest engine, the reliability/trust-score engine, and (later) the
AI advisor and execution bridge.

The column is nullable: legacy rows from before Phase 5 carry no DSL,
and adding a synthetic ``'{}'::jsonb`` default would mint a value that
does not validate against StrategyJSON. Phase 5 endpoints require the
field on create/update, so any row written by the new path will have
a real value.

Revision ID: 009_strategy_json_column
Revises: 008_direct_exit_support
Create Date: 2026-05-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009_strategy_json_column"
down_revision: str | None = "008_direct_exit_support"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "strategies",
        sa.Column(
            "strategy_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("strategies", "strategy_json")
