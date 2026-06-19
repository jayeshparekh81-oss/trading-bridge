"""``subscription_plans`` table + seed — Phase 2 Billing B1.

Creates the platform subscription-tier catalog and seeds it from the
EXISTING hardcoded mock (Starter / Pro / Premium) so both pricing surfaces
(``/pricing`` + the home page) render byte-identical content, now DB-sourced.

Additive only — new table, no ALTER/DROP on any existing table, no FK to
strategies or any sacred table. Fully reversible (downgrade drops the table).

NOTE: chains off ``030_historical_backfill_jobs`` (current head on main).
``031_alerts`` lives on the unmerged alerts branch and ALSO revises 030 —
if both ever merge, reconcile the 031 ordering (standard alembic multi-head).

Revision ID: 031_subscription_plans
Revises: 030_historical_backfill_jobs
Create Date: 2026-06-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "031_subscription_plans"
down_revision: str | None = "030_historical_backfill_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Seed payload — lifted verbatim from the previous hardcoded pricing JSX:
#   * prices + structured feature flags from frontend/.../pricing/page.tsx
#   * ``bullets`` from the home page's pricing cards
#   * ``popular`` from both.
_SEED = [
    {
        "name": "Starter",
        "tier": "starter",
        "price_monthly_inr": 999,
        "price_yearly_inr": 799,
        "sort_order": 1,
        "feature_limits": {
            "popular": False,
            "brokers": 1,
            "strategies": 5,
            "killSwitch": True,
            "analytics": False,
            "telegram": False,
            "csv": False,
            "ai": False,
            "shadowSl": False,
            "support": "Community",
            "bullets": [
                "1 broker",
                "5 strategies",
                "Kill Switch",
                "Email alerts",
                "Community support",
            ],
        },
    },
    {
        "name": "Pro",
        "tier": "pro",
        "price_monthly_inr": 2499,
        "price_yearly_inr": 1999,
        "sort_order": 2,
        "feature_limits": {
            "popular": True,
            "brokers": 3,
            "strategies": 50,
            "killSwitch": True,
            "analytics": True,
            "telegram": True,
            "csv": True,
            "ai": False,
            "shadowSl": False,
            "support": "Priority",
            "bullets": [
                "3 brokers",
                "50 strategies",
                "Kill Switch + Analytics",
                "Email + Telegram",
                "CSV export",
                "Priority support",
            ],
        },
    },
    {
        "name": "Premium",
        "tier": "premium",
        "price_monthly_inr": 4999,
        "price_yearly_inr": 3999,
        "sort_order": 3,
        "feature_limits": {
            "popular": False,
            "brokers": 6,
            "strategies": 200,
            "killSwitch": True,
            "analytics": True,
            "telegram": True,
            "csv": True,
            "ai": True,
            "shadowSl": True,
            "support": "Dedicated",
            "bullets": [
                "6 brokers",
                "200+ strategies",
                "AI Smart Signals",
                "Shadow Stop-Loss",
                "All channels",
                "Dedicated support",
            ],
        },
    },
]


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False),
        sa.Column(
            "price_monthly_inr",
            sa.Numeric(10, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "price_yearly_inr",
            sa.Numeric(10, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("feature_limits", sa.JSON(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tier", name="uq_subscription_plans_tier"),
    )
    op.create_index(
        "ix_subscription_plans_active_sort",
        "subscription_plans",
        ["is_active", "sort_order"],
    )

    # Seed the tiers. id / created_at / updated_at are omitted so their
    # server defaults apply (gen_random_uuid() + now()).
    seed_table = sa.table(
        "subscription_plans",
        sa.column("name", sa.String),
        sa.column("tier", sa.String),
        sa.column("price_monthly_inr", sa.Numeric),
        sa.column("price_yearly_inr", sa.Numeric),
        sa.column("feature_limits", sa.JSON),
        sa.column("is_active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        seed_table,
        [{**row, "is_active": True} for row in _SEED],
    )


def downgrade() -> None:
    op.drop_index("ix_subscription_plans_active_sort", table_name="subscription_plans")
    op.drop_table("subscription_plans")
