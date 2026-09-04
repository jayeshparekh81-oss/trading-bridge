"""users.paywall_grace_until — the paywall grace clock (founder's decision, 2026-09-04).

WHY. When ``paywall_enforced`` is flipped True, every existing user is
``plan_status='none'`` (12 of 12 on prod). Without a grace window the flip is an
instant lockout of every customer. This column is the per-user deadline: NULL
until the user's first entitlement check after the flip, then
``now + PAYWALL_GRACE_DAYS`` (setting, default 14), set once and never
extended. Until it passes the user keeps FULL access (no 402, no strategy cap).

ADDITIVE, one nullable TIMESTAMPTZ column, no backfill, no data move, touches
no trading table. ``ADD COLUMN`` with no default is metadata-only on
PostgreSQL 11+. Inert until the flag is True: nothing writes the column while
the flag is False, so applying this migration is behaviour-neutral.

``DateTime(timezone=True)`` is mandatory — asyncpg rejects an aware Python
datetime on a naive column (the cutover-22 Subscribe 500); the structural
guard tests/db/test_all_datetime_columns_are_tz_aware.py pins the model side.

DOWNGRADE IS REAL: drops the column. Nothing else to restore — no row has a
value until the flag is flipped, and a flipped-then-downgraded deployment
simply restarts every clock on the next upgrade (documented, acceptable).

Revision ID: 044_paywall_grace
Revises: 043_csv_export_real
Create Date: 2026-09-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "044_paywall_grace"
down_revision: str | None = "043_csv_export_real"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("paywall_grace_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "paywall_grace_until")
