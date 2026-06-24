"""Billing lifecycle — add the ``past_due`` status (dunning).

Phase 2 (Razorpay), Module 4. ADDITIVE ONLY (off ``035_razorpay_marketplace``).
Widens two status CHECKs to add ``past_due`` — the dunning state a recurring
subscription enters when a renewal charge fails and Razorpay is still retrying
(``subscription.pending``). A recovered charge (``subscription.charged``) flips
it back to ``active``; exhausted retries (``halted``) expire it.

    * ``users.plan_status``                   += ``past_due``
    * ``marketplace_subscriptions.status``     += ``past_due``

No new columns, no backfill, no data move (existing rows stay valid). Touches no
trading table. Reversible (downgrade restores the prior value sets; it refuses
if any ``past_due`` rows remain — clear them first).

Kept <= 32 chars (alembic_version VARCHAR(32)). Validated locally only; NOT prod.

Revision ID: 036_billing_past_due
Revises: 035_razorpay_marketplace
Create Date: 2026-06-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "036_billing_past_due"
down_revision: str | None = "035_razorpay_marketplace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ── users.plan_status ──
_USER_OLD = ("none", "active", "expired", "cancelled")
_USER_NEW = ("none", "active", "expired", "cancelled", "past_due")
# ── marketplace_subscriptions.status (035 added 'pending') ──
_MKT_OLD = ("pending", "active", "cancelled", "expired")
_MKT_NEW = ("pending", "active", "cancelled", "expired", "past_due")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.drop_constraint("plan_status_valid", "users", type_="check")
    op.create_check_constraint(
        "plan_status_valid", "users", _in("plan_status", _USER_NEW)
    )
    op.drop_constraint("status_valid", "marketplace_subscriptions", type_="check")
    op.create_check_constraint(
        "status_valid", "marketplace_subscriptions", _in("status", _MKT_NEW)
    )


def downgrade() -> None:
    op.drop_constraint("status_valid", "marketplace_subscriptions", type_="check")
    op.create_check_constraint(
        "status_valid", "marketplace_subscriptions", _in("status", _MKT_OLD)
    )
    op.drop_constraint("plan_status_valid", "users", type_="check")
    op.create_check_constraint(
        "plan_status_valid", "users", _in("plan_status", _USER_OLD)
    )
