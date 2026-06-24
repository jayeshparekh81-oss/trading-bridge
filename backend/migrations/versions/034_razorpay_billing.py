"""Razorpay billing — payments/orders + webhook-event idempotency + handles.

Phase 2 (Razorpay), Module 1. ADDITIVE ONLY (off main's head 033):
    * NEW ``razorpay_payments``        — user+plan <-> Razorpay sub/order/payment.
    * NEW ``razorpay_webhook_events``  — UNIQUE event_id idempotency ledger.
    * ADD ``users.razorpay_subscription_id``      (nullable) — recurring handle.
    * ADD ``subscription_plans.razorpay_plan_id`` (nullable) — create-if-absent
      plan map (no duplicate Razorpay plans).

Changes NO existing column, no backfill. Reuses the EXISTING entitlement fields
(``users.plan_status`` / ``active_plan_id`` / ``plan_expires_at`` from migration
032) — those are driven by the verified webhook, not added here. Payment-only;
touches no trading table. Fully reversible.

NOTE: both this branch and ``feat/marketplace-fanout`` fork off 033, so each has
a "034". This revision id is ``034_razorpay_billing`` (distinct from the
marketplace ``034_subscription_scoping``); when both land on main, a single
alembic merge revision will join the two heads. Validated locally only; NOT on
prod (prod stays at 033).

Revision ID: 034_razorpay_billing
Revises: 033_strategy_state_audit
Create Date: 2026-06-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic. (<= 32 chars to fit alembic_version.)
revision: str = "034_razorpay_billing"
down_revision: str | None = "033_strategy_state_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── razorpay_payments ───────────────────────────────────────────────
    op.create_table(
        "razorpay_payments",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("plan_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("razorpay_order_id", sa.String(64), nullable=True),
        sa.Column("razorpay_subscription_id", sa.String(64), nullable=True),
        sa.Column("razorpay_payment_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="created"),
        sa.Column("amount_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_razorpay_payments_user_id_users", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["subscription_plans.id"],
            name="fk_razorpay_payments_plan_id", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_razorpay_payments"),
    )
    op.create_index(
        "ix_razorpay_payments_user_id", "razorpay_payments", ["user_id"]
    )
    op.create_index(
        "ix_razorpay_payments_subscription_id",
        "razorpay_payments", ["razorpay_subscription_id"],
    )

    # ── razorpay_webhook_events (idempotency ledger) ────────────────────
    op.create_table(
        "razorpay_webhook_events",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("razorpay_subscription_id", sa.String(64), nullable=True),
        sa.Column("razorpay_payment_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_razorpay_webhook_events"),
        sa.UniqueConstraint("event_id", name="uq_razorpay_webhook_events_event_id"),
    )

    # ── additive handles on existing tables ─────────────────────────────
    op.add_column(
        "users",
        sa.Column("razorpay_subscription_id", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_users_razorpay_subscription_id", "users", ["razorpay_subscription_id"]
    )
    op.add_column(
        "subscription_plans",
        sa.Column("razorpay_plan_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscription_plans", "razorpay_plan_id")
    op.drop_index("ix_users_razorpay_subscription_id", table_name="users")
    op.drop_column("users", "razorpay_subscription_id")
    op.drop_table("razorpay_webhook_events")
    op.drop_index("ix_razorpay_payments_subscription_id", table_name="razorpay_payments")
    op.drop_index("ix_razorpay_payments_user_id", table_name="razorpay_payments")
    op.drop_table("razorpay_payments")
