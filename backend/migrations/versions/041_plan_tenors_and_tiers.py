"""Plan tenors (child price table) + real tier structure.

TWO CHANGES, one migration:

1. NEW TABLE ``subscription_plan_prices`` — one row per (plan, tenor). This is
   the founder-chosen Option 1 from docs/MIGRATION_041_PLAN_TIERS_TENORS.md,
   taken over adding two more price columns, because Razorpay issues a plan id
   per (tier, billing interval): 4 tenors x 3 tiers = 12 ids, and
   ``subscription_plans.razorpay_plan_id`` holds only ONE per tier. Each row
   here carries its OWN ``razorpay_plan_id`` (NULL for now — no keys yet), and a
   fifth tenor later is a row rather than another migration. A UNIQUE constraint
   on (plan_id, tenor) makes a duplicate tenor impossible.

   The legacy ``price_monthly_inr`` / ``price_yearly_inr`` columns are LEFT IN
   PLACE and still populated, so nothing breaks mid-deploy; dropping them is a
   later migration once every reader uses the price list.

2. DATA UPDATE on the 3 seeded rows — the differentiator becomes SEGMENT +
   STRATEGY COUNT. The old display-only marketing caps (1/3/6 brokers,
   5/50/200 strategies) are REPLACED, not supplemented: leaving both would put
   two contradictory claims on the same card.

DOWNGRADE IS REAL, NOT A STUB: it drops the table and restores each row's
feature_limits to the EXACT JSON that is live today. Note that premium's live
value is 039's version (the "Up to 200 strategy slots" bullet fix), NOT 031's
original seed — restoring 031's would silently undo 039. Verified against prod
before writing.

``feature_limits`` is a ``json`` column (031), so jsonb operators need a
``::jsonb`` cast and the result assigns back via ``::json``.

Revision ID: 041_plan_tenors_tiers
Revises: 040_manual_exec_default
Create Date: 2026-08-26
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision: str = "041_plan_tenors_tiers"
down_revision: str | None = "040_manual_exec_default"
branch_labels: str | None = None
depends_on: str | None = None


TENORS = ("monthly", "quarterly", "halfyearly", "yearly")

#: Per-month price by tier and tenor. Ladder: monthly, -7%, -13%, -20%.
PRICES: dict[str, dict[str, int]] = {
    "starter": {"monthly": 999, "quarterly": 929, "halfyearly": 869, "yearly": 799},
    "pro": {"monthly": 2499, "quarterly": 2324, "halfyearly": 2174, "yearly": 1999},
    "premium": {"monthly": 4999, "quarterly": 4649, "halfyearly": 4349, "yearly": 3999},
}

#: How many months each tenor bills at once (for the "billed X upfront" line).
TENOR_MONTHS = {"monthly": 1, "quarterly": 3, "halfyearly": 6, "yearly": 12}

# ── NEW tier structure ────────────────────────────────────────────────
# Segment + strategy count is the differentiator. `brokers` and the old
# `strategies` caps are removed. Support wording is deliberately plain — no
# "research analyst" claim anywhere.
NEW_FEATURES: dict[str, dict] = {
    "starter": {
        "popular": False,
        "strategies": 1,
        "segments": ["CASH"],
        "directions": ["long"],
        "killSwitch": True,
        "analytics": False,
        "telegram": False,
        "csv": False,
        "ai": False,
        "shadowSl": False,
        "support": "Email",
        "bullets": [
            "1 strategy",
            "CASH only",
            "Long only",
            "Kill Switch",
            "Email support",
        ],
    },
    "pro": {
        "popular": True,
        "strategies": 3,
        "segments": ["CASH", "OPTIONS"],
        "directions": ["long", "short"],
        "killSwitch": True,
        "analytics": True,
        "telegram": True,
        "csv": True,
        "ai": False,
        "shadowSl": False,
        "support": "Priority",
        "bullets": [
            "3 strategies",
            "CASH + OPTIONS",
            "Long + Short",
            "Kill Switch + Analytics",
            "Priority support",
        ],
    },
    "premium": {
        "popular": False,
        "strategies": "all",
        "segments": ["CASH", "OPTIONS", "FUTURES"],
        "directions": ["long", "short"],
        "killSwitch": True,
        "analytics": True,
        "telegram": True,
        "csv": True,
        "ai": True,
        "shadowSl": True,
        "support": "Direct founder support",
        "bullets": [
            "All strategies",
            "CASH + OPTIONS + FUTURES",
            "Long + Short",
            "AI Smart Signals",
            "Direct founder support",
        ],
    },
}

# ── EXACT pre-041 feature_limits, captured from PROD on 2026-08-26 ────
# starter/pro are 031's seed; premium is 039's corrected version. The
# downgrade restores these verbatim.
OLD_FEATURES: dict[str, dict] = {
    "starter": {
        "popular": False, "brokers": 1, "strategies": 5, "killSwitch": True,
        "analytics": False, "telegram": False, "csv": False, "ai": False,
        "shadowSl": False, "support": "Community",
        "bullets": ["1 broker", "5 strategies", "Kill Switch", "Email alerts",
                    "Community support"],
    },
    "pro": {
        "popular": True, "brokers": 3, "strategies": 50, "killSwitch": True,
        "analytics": True, "telegram": True, "csv": True, "ai": False,
        "shadowSl": False, "support": "Priority",
        "bullets": ["3 brokers", "50 strategies", "Kill Switch + Analytics",
                    "Email + Telegram", "CSV export", "Priority support"],
    },
    "premium": {
        "ai": True, "csv": True, "brokers": 6,
        "bullets": ["6 brokers", "Up to 200 strategy slots", "AI Smart Signals",
                    "Shadow Stop-Loss", "All channels", "Dedicated support"],
        "popular": False, "support": "Dedicated", "shadowSl": True,
        "telegram": True, "analytics": True, "killSwitch": True,
        "strategies": 200,
    },
}


def _set_features(tier: str, blob: dict) -> None:
    """Per-tier UPDATE keyed on `tier` — never a blanket rewrite, so a
    hand-edited row cannot be clobbered by an assumption about the others."""
    payload = json.dumps(blob).replace("'", "''")
    op.execute(
        f"UPDATE subscription_plans SET feature_limits = '{payload}'::json, "
        f"updated_at = NOW() WHERE tier = '{tier}'"
    )


def upgrade() -> None:
    # 1. Child price table — one row per sellable (plan, tenor).
    op.create_table(
        "subscription_plan_prices",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("subscription_plans.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("tenor", sa.String(16), nullable=False),
        sa.Column("price_per_month_inr", sa.Numeric(10, 2), nullable=False),
        sa.Column("months_billed", sa.Integer(), nullable=False),
        # One Razorpay plan id PER TENOR — the whole reason for this table.
        sa.Column("razorpay_plan_id", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("plan_id", "tenor", name="uq_plan_tenor"),
        sa.CheckConstraint(
            "tenor IN ('monthly','quarterly','halfyearly','yearly')",
            name="ck_plan_price_tenor",
        ),
    )
    op.create_index("ix_plan_prices_plan_id", "subscription_plan_prices",
                    ["plan_id"])

    # 2. Seed 3 tiers x 4 tenors = 12 rows, joined by tier (no hardcoded uuids).
    for tier, ladder in PRICES.items():
        for order, tenor in enumerate(TENORS, start=1):
            op.execute(
                "INSERT INTO subscription_plan_prices "
                "(plan_id, tenor, price_per_month_inr, months_billed, sort_order) "
                f"SELECT id, '{tenor}', {ladder[tenor]}, "
                f"{TENOR_MONTHS[tenor]}, {order} "
                f"FROM subscription_plans WHERE tier = '{tier}'"
            )

    # 3. Real tier structure replaces the display-only caps.
    for tier, blob in NEW_FEATURES.items():
        _set_features(tier, blob)


def downgrade() -> None:
    # Restore the EXACT pre-041 JSON (premium = 039's version, not 031's).
    for tier, blob in OLD_FEATURES.items():
        _set_features(tier, blob)
    op.drop_index("ix_plan_prices_plan_id", table_name="subscription_plan_prices")
    op.drop_table("subscription_plan_prices")
