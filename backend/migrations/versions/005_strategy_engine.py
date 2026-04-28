"""Strategy execution engine — signals, executions, positions.

Revision ID: 005_strategy_engine
Revises: 004_algomitra_token_usage
Create Date: 2026-04-28

Three new tables:
    * ``strategy_signals``    — every signal received from a webhook source.
    * ``strategy_executions`` — every order placement attempt (4 rows per
      4-leg entry, plus exits / SL hits).
    * ``strategy_positions``  — live position state, lifecycle managed by
      the position-manager loop.

Also extends ``strategies`` with risk/sizing config columns
(``entry_lots``, ``partial_profit_*``, ``trail_*``, ``hard_sl_pct``,
``max_loss_per_day``, ``ai_validation_enabled``). All additive with safe
defaults so existing rows hydrate cleanly.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_strategy_engine"
down_revision: str | None = "004_algomitra_token_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. Extend strategies with risk/sizing config ──────────────────
    op.add_column(
        "strategies",
        sa.Column("entry_lots", sa.Integer(), nullable=False, server_default="4"),
    )
    op.add_column(
        "strategies",
        sa.Column(
            "partial_profit_lots", sa.Integer(), nullable=False, server_default="2"
        ),
    )
    op.add_column(
        "strategies",
        sa.Column("partial_profit_target_pct", sa.Numeric(6, 3), nullable=True),
    )
    op.add_column(
        "strategies",
        sa.Column("trail_lots", sa.Integer(), nullable=False, server_default="2"),
    )
    op.add_column(
        "strategies",
        sa.Column("trail_offset_pct", sa.Numeric(6, 3), nullable=True),
    )
    op.add_column(
        "strategies",
        sa.Column("hard_sl_pct", sa.Numeric(6, 3), nullable=True),
    )
    op.add_column(
        "strategies",
        sa.Column("max_loss_per_day", sa.Integer(), nullable=True),
    )
    op.add_column(
        "strategies",
        sa.Column(
            "ai_validation_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    # ── 2. strategy_signals ────────────────────────────────────────────
    op.create_table(
        "strategy_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("order_type", sa.String(16), nullable=True),
        sa.Column("ai_decision", sa.String(16), nullable=True),
        sa.Column("ai_reasoning", sa.Text(), nullable=True),
        sa.Column("ai_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="received",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_strategy_signals_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["strategy_id"],
            ["strategies.id"],
            name="fk_strategy_signals_strategy_id_strategies",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_strategy_signals"),
    )
    op.create_index(
        "ix_strategy_signals_user_id", "strategy_signals", ["user_id"]
    )
    op.create_index(
        "ix_strategy_signals_strategy_id", "strategy_signals", ["strategy_id"]
    )
    op.create_index(
        "ix_strategy_signals_received_at",
        "strategy_signals",
        [sa.text("received_at DESC")],
    )
    op.create_index(
        "ix_strategy_signals_status", "strategy_signals", ["status"]
    )

    # ── 3. strategy_executions ─────────────────────────────────────────
    op.create_table(
        "strategy_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "broker_credential_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("leg_number", sa.Integer(), nullable=False),
        sa.Column("leg_role", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("order_type", sa.String(16), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=True),
        sa.Column("broker_order_id", sa.String(128), nullable=True),
        sa.Column("broker_status", sa.String(64), nullable=True),
        sa.Column(
            "broker_response",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "placed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["signal_id"],
            ["strategy_signals.id"],
            name="fk_strategy_executions_signal_id_strategy_signals",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["broker_credential_id"],
            ["broker_credentials.id"],
            name="fk_strategy_executions_broker_credential_id_broker_credentials",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_strategy_executions"),
    )
    op.create_index(
        "ix_strategy_executions_signal_id", "strategy_executions", ["signal_id"]
    )
    op.create_index(
        "ix_strategy_executions_broker_credential_id",
        "strategy_executions",
        ["broker_credential_id"],
    )
    op.create_index(
        "ix_strategy_executions_placed_at",
        "strategy_executions",
        [sa.text("placed_at DESC")],
    )

    # ── 4. strategy_positions ──────────────────────────────────────────
    op.create_table(
        "strategy_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "broker_credential_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("total_quantity", sa.Integer(), nullable=False),
        sa.Column("remaining_quantity", sa.Integer(), nullable=False),
        sa.Column("avg_entry_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("target_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("stop_loss_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("trail_offset", sa.Numeric(18, 4), nullable=True),
        sa.Column("highest_price_seen", sa.Numeric(18, 4), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_pnl", sa.Numeric(18, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_strategy_positions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["strategy_id"],
            ["strategies.id"],
            name="fk_strategy_positions_strategy_id_strategies",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["broker_credential_id"],
            ["broker_credentials.id"],
            name="fk_strategy_positions_broker_credential_id_broker_credentials",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["signal_id"],
            ["strategy_signals.id"],
            name="fk_strategy_positions_signal_id_strategy_signals",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_strategy_positions"),
    )
    op.create_index(
        "ix_strategy_positions_user_id", "strategy_positions", ["user_id"]
    )
    op.create_index(
        "ix_strategy_positions_strategy_id",
        "strategy_positions",
        ["strategy_id"],
    )
    op.create_index(
        "ix_strategy_positions_status", "strategy_positions", ["status"]
    )


def downgrade() -> None:
    op.drop_table("strategy_positions")
    op.drop_table("strategy_executions")
    op.drop_table("strategy_signals")

    op.drop_column("strategies", "ai_validation_enabled")
    op.drop_column("strategies", "max_loss_per_day")
    op.drop_column("strategies", "hard_sl_pct")
    op.drop_column("strategies", "trail_offset_pct")
    op.drop_column("strategies", "trail_lots")
    op.drop_column("strategies", "partial_profit_target_pct")
    op.drop_column("strategies", "partial_profit_lots")
    op.drop_column("strategies", "entry_lots")
