"""Razorpay marketplace subscriptions — discriminator + handles + pending status.

Phase 2 (Razorpay), Module 2. ADDITIVE ONLY (off this branch's head
``034_razorpay_billing``). Reuses the M1 Razorpay plumbing (client, the
signature-verified idempotent webhook, the ``razorpay_payments`` /
``razorpay_webhook_events`` tables) for MARKETPLACE per-strategy subscriptions:

    * ADD ``razorpay_payments.kind``                        (NOT NULL, default
      ``'platform_plan'``) — discriminates platform-plan vs marketplace events so
      the ONE webhook routes each ``sub_…`` to the right entity.
    * ADD ``razorpay_payments.marketplace_subscription_id`` (nullable FK -> SET
      NULL) — the durable ``sub_… -> marketplace_subscription`` link.
    * ADD ``marketplace_subscriptions.razorpay_subscription_id`` (nullable) — the
      recurring handle stored on the sub.
    * ADD ``marketplace_listings.razorpay_plan_id``         (nullable) — the
      create-if-absent Razorpay Plan per listing price (no duplicate plans).
    * EXPAND the ``marketplace_subscriptions`` status CHECK to add ``'pending'``
      so a subscribe can persist BEFORE payment confirms (the webhook flips it to
      ``'active'``). Purely additive to the allowed set — existing rows stay valid.

Changes NO existing column type, no backfill, no data move. Touches NO trading
table. Payment + subscription-status only. Fully reversible (the downgrade
restores the original 3-value CHECK; it will refuse if any ``'pending'`` rows
remain, which is correct — clear them first).

NOTE: like 034, this forks off 033 in parallel with ``feat/marketplace-fanout``;
a single alembic merge revision joins the heads when both land on main. Kept
<= 32 chars (alembic_version VARCHAR(32)). Validated locally only; NOT on prod.

Revision ID: 035_razorpay_marketplace
Revises: 034_razorpay_billing
Create Date: 2026-06-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic. (<= 32 chars to fit alembic_version.)
revision: str = "035_razorpay_marketplace"
down_revision: str | None = "034_razorpay_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Status vocabularies for the marketplace_subscriptions CHECK. The original
# (migration 018) is the 3-value set; M2 adds 'pending' (awaiting first charge).
_STATUS_OLD = ("active", "cancelled", "expired")
_STATUS_NEW = ("pending", "active", "cancelled", "expired")


def _check_expr(values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"status IN ({quoted})"


def upgrade() -> None:
    # ── razorpay_payments: discriminator + marketplace link ─────────────
    op.add_column(
        "razorpay_payments",
        sa.Column(
            "kind", sa.String(16), nullable=False, server_default="platform_plan"
        ),
    )
    op.add_column(
        "razorpay_payments",
        sa.Column("marketplace_subscription_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_razorpay_payments_marketplace_subscription_id",
        "razorpay_payments",
        "marketplace_subscriptions",
        ["marketplace_subscription_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_razorpay_payments_marketplace_subscription_id",
        "razorpay_payments",
        ["marketplace_subscription_id"],
    )

    # ── marketplace_subscriptions: handle + 'pending' status ────────────
    op.add_column(
        "marketplace_subscriptions",
        sa.Column("razorpay_subscription_id", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_marketplace_subscriptions_razorpay_subscription_id",
        "marketplace_subscriptions",
        ["razorpay_subscription_id"],
    )
    # Drop + recreate the status CHECK to widen the allowed set. The suffix
    # "status_valid" resolves via Base.metadata.naming_convention to the live
    # name ``ck_marketplace_subscriptions_status_valid`` (verified on PG 16).
    op.drop_constraint(
        "status_valid", "marketplace_subscriptions", type_="check"
    )
    op.create_check_constraint(
        "status_valid", "marketplace_subscriptions", _check_expr(_STATUS_NEW)
    )

    # ── marketplace_listings: create-if-absent Razorpay plan per price ──
    op.add_column(
        "marketplace_listings",
        sa.Column("razorpay_plan_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("marketplace_listings", "razorpay_plan_id")

    # Restore the original 3-value CHECK. Fails (correctly) if 'pending' rows
    # remain — resolve them before downgrading.
    op.drop_constraint(
        "status_valid", "marketplace_subscriptions", type_="check"
    )
    op.create_check_constraint(
        "status_valid", "marketplace_subscriptions", _check_expr(_STATUS_OLD)
    )
    op.drop_index(
        "ix_marketplace_subscriptions_razorpay_subscription_id",
        table_name="marketplace_subscriptions",
    )
    op.drop_column("marketplace_subscriptions", "razorpay_subscription_id")

    op.drop_index(
        "ix_razorpay_payments_marketplace_subscription_id",
        table_name="razorpay_payments",
    )
    op.drop_constraint(
        "fk_razorpay_payments_marketplace_subscription_id",
        "razorpay_payments",
        type_="foreignkey",
    )
    op.drop_column("razorpay_payments", "marketplace_subscription_id")
    op.drop_column("razorpay_payments", "kind")
