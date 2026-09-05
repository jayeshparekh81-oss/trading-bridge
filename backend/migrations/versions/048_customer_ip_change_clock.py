"""customer_broker_link.last_ip_change_at — the exchange-rule clock.

ADDITIVE: one nullable column. No default, no backfill, no data move, no ALTER of
anything existing.

WHY A SECOND COLUMN. Two different rules govern a customer's mapped static IP and
they are NOT the same clock:

  * Dhan locks a whitelisted IP for 7 DAYS after it is set  -> ip_whitelisted_at
  * the exchange allows at most ONE change per CALENDAR WEEK -> last_ip_change_at

Deriving both from ip_whitelisted_at would collapse them: 7 days after any given
day always lands in a later calendar week, so the week rule would never bind and
would silently do nothing. Modelling the change separately is what makes
"once per calendar week is not once per 7 days" real — a change on Sunday and a
change on Monday are one day apart and in two different weeks.

Revision ID: 048_customer_ip_change_clock
Revises: 047_customer_lane
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "048_customer_ip_change_clock"
down_revision = "047_customer_lane"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customer_broker_link",
        sa.Column("last_ip_change_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customer_broker_link", "last_ip_change_at")
