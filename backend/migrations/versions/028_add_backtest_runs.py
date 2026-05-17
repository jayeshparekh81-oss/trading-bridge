"""``backtest_runs`` + ``backtest_trades`` + ``backtest_metrics`` tables.

DRAFT — NOT to be applied from this branch (Week-2-prep skeleton).
Founder activates with ``alembic upgrade head`` on Day 1 of the
supervised Week 2 sprint.

Three new tables for the async, persisted backtest extension layer:

1. ``backtest_runs`` — one row per backtest invocation. Tracks
   request hash (for idempotency lookup), engine_version, owning
   user, optional strategy_id (NULL for anonymous-config previews),
   status state machine (PENDING → RUNNING → SUCCEEDED|FAILED),
   timestamps + error_json.

2. ``backtest_trades`` — closed-trade audit rows, one per Trade row
   in :class:`BacktestResult.trades`. FK to backtest_runs (CASCADE on
   delete). Indexed by (run_id) for the GET /trades endpoint.

3. ``backtest_metrics`` — one row per SUCCEEDED run carrying the
   summary metrics from :class:`BacktestResult`. PK = run_id (1-to-1
   with backtest_runs). Joined into the GET /{id} response.

Additive only. No ALTER on existing tables. Fully reversible.

Revision ID: 028_add_backtest_runs
Revises: 026_add_strategy_templates
Create Date: 2026-05-17 (DRAFT)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "028_add_backtest_runs"
down_revision: str | None = "026_add_strategy_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_STATUS_VALUES = "'PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED'"
_SIDE_VALUES = "'BUY', 'SELL'"


def upgrade() -> None:
    # ── backtest_runs ────────────────────────────────────────────────
    op.create_table(
        "backtest_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "strategy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("strategies.id", ondelete="SET NULL"),
            nullable=True,
            comment=(
                "NULL for anonymous-config preview backtests "
                "(Strategy Builder pre-save + template gallery preview)."
            ),
        ),
        sa.Column(
            "request_hash",
            sa.String(length=64),
            nullable=False,
            comment="SHA-256 hex of canonical request payload + engine_version.",
        ),
        sa.Column(
            "engine_version",
            sa.String(length=16),
            nullable=False,
            comment="MAJOR.MINOR string from app/strategy_engine/backtest/_version.py.",
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "request_payload",
            postgresql.JSONB,
            nullable=False,
            comment="Original BacktestEnqueueRequest as stored JSON.",
        ),
        sa.Column(
            "error_json",
            postgresql.JSONB,
            nullable=True,
            comment="Populated on FAILED — {type, message, traceback_first_line}.",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            f"status IN ({_STATUS_VALUES})",
            name="backtest_runs_status_check",
        ),
        sa.CheckConstraint(
            "(status IN ('SUCCEEDED', 'FAILED')) = (completed_at IS NOT NULL)",
            name="backtest_runs_completed_at_consistency",
        ),
        sa.CheckConstraint(
            "(status = 'FAILED') = (error_json IS NOT NULL)",
            name="backtest_runs_error_consistency",
        ),
    )
    op.create_index(
        "ix_backtest_runs_user_id_request_hash",
        "backtest_runs",
        ["user_id", "request_hash"],
    )
    op.create_index(
        "ix_backtest_runs_strategy_id",
        "backtest_runs",
        ["strategy_id"],
        postgresql_where=sa.text("strategy_id IS NOT NULL"),
    )
    op.create_index(
        "ix_backtest_runs_status_started_at",
        "backtest_runs",
        ["status", "started_at"],
    )
    # Partial unique on (user_id, request_hash) WHERE status = SUCCEEDED:
    # idempotency cache lookups are user-scoped + SUCCEEDED-only, and we
    # want the DB to reject a concurrent double-success-insert.
    op.create_index(
        "ix_backtest_runs_user_id_hash_succeeded_uniq",
        "backtest_runs",
        ["user_id", "request_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'SUCCEEDED'"),
    )

    # ── backtest_trades ──────────────────────────────────────────────
    op.create_table(
        "backtest_trades",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trade_index",
            sa.Integer,
            nullable=False,
            comment="0-based ordinal within the run's trade list. Preserves order.",
        ),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("entry_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("exit_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("pnl", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("exit_reason", sa.String(length=128), nullable=False),
        sa.Column(
            "entry_reasons",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="List of strings from Trade.entry_reasons.",
        ),
        sa.CheckConstraint(
            f"side IN ({_SIDE_VALUES})",
            name="backtest_trades_side_check",
        ),
        sa.CheckConstraint(
            "entry_price > 0 AND exit_price > 0 AND quantity > 0",
            name="backtest_trades_positive_amounts",
        ),
        sa.UniqueConstraint(
            "run_id", "trade_index", name="uq_backtest_trades_run_index"
        ),
    )
    op.create_index(
        "ix_backtest_trades_run_id",
        "backtest_trades",
        ["run_id"],
    )

    # ── backtest_metrics ─────────────────────────────────────────────
    op.create_table(
        "backtest_metrics",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_runs.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("total_pnl", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column(
            "total_return_percent", sa.Numeric(precision=12, scale=6), nullable=False
        ),
        sa.Column(
            "win_rate", sa.Numeric(precision=6, scale=4), nullable=False
        ),
        sa.Column(
            "loss_rate", sa.Numeric(precision=6, scale=4), nullable=False
        ),
        sa.Column("total_trades", sa.Integer, nullable=False),
        sa.Column("average_win", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("average_loss", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("largest_win", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("largest_loss", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column(
            "max_drawdown", sa.Numeric(precision=6, scale=4), nullable=False
        ),
        sa.Column(
            "profit_factor",
            sa.Numeric(precision=18, scale=6),
            nullable=True,
            comment=(
                "NULL when wins-only deck (Python math.inf doesn't store cleanly). "
                "Consumers treat NULL as +inf for ranking."
            ),
        ),
        sa.Column("expectancy", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column(
            "warnings",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.CheckConstraint(
            "win_rate >= 0 AND win_rate <= 1",
            name="backtest_metrics_win_rate_range",
        ),
        sa.CheckConstraint(
            "loss_rate >= 0 AND loss_rate <= 1",
            name="backtest_metrics_loss_rate_range",
        ),
        sa.CheckConstraint(
            "max_drawdown >= 0 AND max_drawdown <= 1",
            name="backtest_metrics_max_dd_range",
        ),
        sa.CheckConstraint(
            "total_trades >= 0",
            name="backtest_metrics_trade_count_nonneg",
        ),
    )


def downgrade() -> None:
    # Drop in reverse FK order so cascades don't surprise the operator.
    op.drop_table("backtest_metrics")
    op.drop_index(
        "ix_backtest_trades_run_id", table_name="backtest_trades"
    )
    op.drop_table("backtest_trades")
    op.drop_index(
        "ix_backtest_runs_user_id_hash_succeeded_uniq",
        table_name="backtest_runs",
    )
    op.drop_index(
        "ix_backtest_runs_status_started_at", table_name="backtest_runs"
    )
    op.drop_index(
        "ix_backtest_runs_strategy_id", table_name="backtest_runs"
    )
    op.drop_index(
        "ix_backtest_runs_user_id_request_hash", table_name="backtest_runs"
    )
    op.drop_table("backtest_runs")
