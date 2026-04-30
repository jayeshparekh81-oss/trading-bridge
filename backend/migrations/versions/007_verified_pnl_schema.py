"""Verified P&L schema — tables only (logic ships Friday).

Revision ID: 007_verified_pnl_schema
Revises: 006_position_manager_universal
Create Date: 2026-04-30

TRADETRI charges 20% of monthly verified profit. To bill that we need:

    1. customer_capital_snapshots — daily fetched broker balances; the
       ``UNIQUE(user_id, snapshot_date)`` keeps the daily fetch
       idempotent.
    2. monthly_billing_cycles    — one row per (user, calendar month);
       carries the verification hash (chained to the previous cycle so
       prior months can't be silently re-keyed).
    3. audit_log                 — append-only signed log distinct from
       the existing ``audit_logs`` (plural) auth/RBAC log. Singular
       name kept per the spec; both coexist intentionally.

Also widens the existing strategy_executions / strategy_positions tables
with broker-side trade response JSON columns the billing logic will
need on Friday. NO ORM model changes in this migration — the SQLAlchemy
models are part of the Friday work.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007_verified_pnl_schema"
down_revision: str | None = "006_position_manager_universal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. customer_capital_snapshots ─────────────────────────────────
    op.create_table(
        "customer_capital_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "broker_credential_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column(
            "fetch_timestamp", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("total_balance_inr", sa.Numeric(14, 2), nullable=True),
        sa.Column("available_balance_inr", sa.Numeric(14, 2), nullable=True),
        sa.Column("used_margin_inr", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "raw_broker_response",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_customer_capital_snapshots_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["broker_credential_id"],
            ["broker_credentials.id"],
            name="fk_customer_capital_snapshots_broker_credential_id_broker_credentials",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customer_capital_snapshots"),
        sa.UniqueConstraint(
            "user_id",
            "snapshot_date",
            name="uq_customer_capital_snapshots_user_id_snapshot_date",
        ),
    )
    op.create_index(
        "ix_customer_capital_snapshots_user_id",
        "customer_capital_snapshots",
        ["user_id"],
    )
    op.create_index(
        "ix_customer_capital_snapshots_snapshot_date",
        "customer_capital_snapshots",
        ["snapshot_date"],
    )

    # ── 2. monthly_billing_cycles ─────────────────────────────────────
    op.create_table(
        "monthly_billing_cycles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_start_date", sa.Date(), nullable=False),
        sa.Column("cycle_end_date", sa.Date(), nullable=False),
        sa.Column("starting_balance_inr", sa.Numeric(14, 2), nullable=True),
        sa.Column("ending_balance_inr", sa.Numeric(14, 2), nullable=True),
        sa.Column("avg_balance_inr", sa.Numeric(14, 2), nullable=True),
        sa.Column("max_balance_inr", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_tradetri_pnl_inr", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "total_trades_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "winning_trades", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "losing_trades", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("win_rate_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "profit_share_pct",
            sa.Numeric(4, 2),
            nullable=False,
            server_default="20.0",
        ),
        sa.Column("amount_due_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("monthly_roi_pct", sa.Numeric(6, 3), nullable=True),
        sa.Column("verification_hash", sa.String(64), nullable=True),
        sa.Column("previous_cycle_hash", sa.String(64), nullable=True),
        sa.Column(
            "publicly_shareable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("invoice_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_due_date", sa.Date(), nullable=True),
        sa.Column(
            "payment_received_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "payment_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "bot_service_paused",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "locked", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_monthly_billing_cycles_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_monthly_billing_cycles"),
    )
    op.create_index(
        "ix_monthly_billing_cycles_user_id",
        "monthly_billing_cycles",
        ["user_id"],
    )
    op.create_index(
        "ix_monthly_billing_cycles_cycle_start_date",
        "monthly_billing_cycles",
        ["cycle_start_date"],
    )
    op.create_index(
        "ix_monthly_billing_cycles_payment_status",
        "monthly_billing_cycles",
        ["payment_status"],
    )

    # ── 3. audit_log (singular — distinct from existing audit_logs) ───
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column(
            "raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("signature", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_audit_log_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_action_type", "audit_log", ["action_type"])
    op.create_index(
        "ix_audit_log_timestamp", "audit_log", [sa.text("timestamp DESC")]
    )

    # ── 4. broker-trade JSON columns on existing tables ───────────────
    op.add_column(
        "strategy_executions",
        sa.Column(
            "broker_order_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "strategy_executions",
        sa.Column(
            "broker_trade_response",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "strategy_positions",
        sa.Column(
            "broker_exit_response",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("strategy_positions", "broker_exit_response")
    op.drop_column("strategy_executions", "broker_trade_response")
    op.drop_column("strategy_executions", "broker_order_ids")

    op.drop_index("ix_audit_log_timestamp", table_name="audit_log")
    op.drop_index("ix_audit_log_action_type", table_name="audit_log")
    op.drop_index("ix_audit_log_user_id", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index(
        "ix_monthly_billing_cycles_payment_status",
        table_name="monthly_billing_cycles",
    )
    op.drop_index(
        "ix_monthly_billing_cycles_cycle_start_date",
        table_name="monthly_billing_cycles",
    )
    op.drop_index(
        "ix_monthly_billing_cycles_user_id",
        table_name="monthly_billing_cycles",
    )
    op.drop_table("monthly_billing_cycles")

    op.drop_index(
        "ix_customer_capital_snapshots_snapshot_date",
        table_name="customer_capital_snapshots",
    )
    op.drop_index(
        "ix_customer_capital_snapshots_user_id",
        table_name="customer_capital_snapshots",
    )
    op.drop_table("customer_capital_snapshots")
