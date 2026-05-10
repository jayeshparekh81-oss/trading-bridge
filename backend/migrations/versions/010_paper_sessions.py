"""Paper sessions + paper trades — durable persistence for paper-trading state.

Phase 8B-1 discovery exposed the engine at
``app/strategy_engine/paper_trading/engine.py`` keeps every session in a
module-level ``_RECORDS`` dict — process restart wipes the 7-session
counter the live-orders SafetyChain depends on. This migration adds
two tables so the count survives restarts and is queryable per-user.

Tables:
    * ``paper_sessions`` — one row per (user, strategy, trading day).
      Unique constraint ``(user_id, strategy_id, session_date)`` so the
      "7 completed sessions" gate counts distinct days, not session
      restarts. Composite index ``(user_id, strategy_id, is_complete)``
      for the SafetyChain's hot-path completed-count query.
    * ``paper_trades`` — closed trades, FK to ``paper_sessions`` with
      ``ON DELETE CASCADE``. Index on ``session_id`` for the per-session
      replay used by ``compute_readiness_from_db``.

Note on numbering: revision-id files are 001..009 today. The next
sequential id is **010** even though discovery prose referenced "011" —
keeping the sequence contiguous matches the existing convention.

Revision ID: 010_paper_sessions
Revises: 009_strategy_json_column
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010_paper_sessions"
down_revision: str | None = "009_strategy_json_column"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "strategy_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "is_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "total_trades",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_pnl",
            sa.Numeric(20, 4),
            nullable=False,
            server_default="0",
        ),
        sa.Column("engine_strategy_id", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_paper_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["strategy_id"],
            ["strategies.id"],
            name="fk_paper_sessions_strategy_id_strategies",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_paper_sessions"),
        sa.UniqueConstraint(
            "user_id",
            "strategy_id",
            "session_date",
            name="uq_paper_sessions_user_strategy_date",
        ),
    )
    op.create_index(
        "ix_paper_sessions_user_id", "paper_sessions", ["user_id"]
    )
    op.create_index(
        "ix_paper_sessions_strategy_id", "paper_sessions", ["strategy_id"]
    )
    op.create_index(
        "ix_paper_sessions_user_strategy_complete",
        "paper_sessions",
        ["user_id", "strategy_id", "is_complete"],
    )

    op.create_table(
        "paper_trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "session_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("entry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("entry_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("exit_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("pnl", sa.Numeric(20, 4), nullable=True),
        sa.Column("exit_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["paper_sessions.id"],
            name="fk_paper_trades_session_id_paper_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_paper_trades"),
    )
    op.create_index(
        "ix_paper_trades_session_id", "paper_trades", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_paper_trades_session_id", table_name="paper_trades")
    op.drop_table("paper_trades")
    op.drop_index(
        "ix_paper_sessions_user_strategy_complete",
        table_name="paper_sessions",
    )
    op.drop_index(
        "ix_paper_sessions_strategy_id", table_name="paper_sessions"
    )
    op.drop_index("ix_paper_sessions_user_id", table_name="paper_sessions")
    op.drop_table("paper_sessions")
