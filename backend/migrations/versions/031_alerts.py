"""``alerts`` table — Queue HHH M10 (storage only, no evaluation engine).

Additive — net-new table, no ALTER on existing tables, fully reversible.

Revision ID: 031_alerts
Revises: 030_historical_backfill_jobs
Create Date: 2026-06-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "031_alerts"
down_revision: str | None = "030_historical_backfill_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alerts",
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
            sa.ForeignKey(
                "users.id",
                ondelete="CASCADE",
                name="fk_alerts_user",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("condition_kind", sa.Text(), nullable=False),
        sa.Column("threshold", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "last_triggered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
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
        sa.CheckConstraint(
            "condition_kind IN ('price_above', 'price_below')",
            name="ck_alerts_condition_kind_enum",
        ),
    )
    op.create_index(
        "ix_alerts_user_active",
        "alerts",
        ["user_id", "is_active"],
    )
    op.create_index(
        "ix_alerts_symbol_active",
        "alerts",
        ["symbol", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_symbol_active", table_name="alerts")
    op.drop_index("ix_alerts_user_active", table_name="alerts")
    op.drop_table("alerts")
