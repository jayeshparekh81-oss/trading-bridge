"""Add token usage + cost columns to algomitra_messages (Phase 1B).

Revision ID: 004_algomitra_token_usage
Revises: 003_add_algomitra_messages_table
Create Date: 2026-04-25

Phase 1B replaces the static AlgoMitra chat with real Claude calls. We
log per-message token usage and INR cost on the assistant rows so we
can audit Anthropic spend per user / per day. NULL on all existing
rows (legacy static-flow assistant messages have no token cost).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "004_algomitra_token_usage"
down_revision: Union[str, None] = "003_add_algomitra_messages_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "algomitra_messages",
        sa.Column("input_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "algomitra_messages",
        sa.Column("output_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "algomitra_messages",
        sa.Column("cache_read_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "algomitra_messages",
        sa.Column("cache_creation_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "algomitra_messages",
        sa.Column("cost_inr", sa.Numeric(10, 4), nullable=True),
    )
    op.add_column(
        "algomitra_messages",
        sa.Column("tone", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("algomitra_messages", "tone")
    op.drop_column("algomitra_messages", "cost_inr")
    op.drop_column("algomitra_messages", "cache_creation_tokens")
    op.drop_column("algomitra_messages", "cache_read_tokens")
    op.drop_column("algomitra_messages", "output_tokens")
    op.drop_column("algomitra_messages", "input_tokens")
