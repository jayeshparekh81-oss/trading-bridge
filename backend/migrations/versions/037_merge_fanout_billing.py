"""Merge the two parallel heads — marketplace fan-out + Razorpay billing.

INTEGRATION (integration/marketplace-billing). Both feature tracks forked off
``033_strategy_state_audit`` and each grew its own chain:

    fan-out:   033 -> 034_subscription_scoping -> 035_subscription_exec_fields
    billing:   033 -> 034_razorpay_billing -> 035_razorpay_marketplace -> 036_billing_past_due

This is a PURE alembic merge revision: it joins those two heads into ONE so
``alembic upgrade head`` is unambiguous. It changes NO schema (empty upgrade /
downgrade) — the chains touch disjoint tables/columns, so they simply coexist.
The one cross-track schema seam (the ``execution_mode`` CHECK needs billing's
``'paper'`` value) is handled by the follow-on ``038_exec_mode_paper`` so this
merge stays a clean, reversible join. (The showcase track adds NO migration.)

Kept <= 32 chars (alembic_version VARCHAR(32)). LOCAL validation only; NOT prod.

Revision ID: 037_merge_fanout_billing
Revises: 035_subscription_exec_fields, 036_billing_past_due
Create Date: 2026-06-24
"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "037_merge_fanout_billing"
down_revision: tuple[str, str] | str | None = (
    "035_subscription_exec_fields",
    "036_billing_past_due",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Pure join — no schema change."""


def downgrade() -> None:
    """Pure join — no schema change (splits back into two heads)."""
