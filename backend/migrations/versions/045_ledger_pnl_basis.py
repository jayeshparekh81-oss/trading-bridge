"""ledger_snapshots.unpriced_positions + pnl_basis — the ledger says what it publishes.

WHY. The Transparency Ledger payload is re-pointed (docs/LEDGER_PAYLOAD_PROPOSAL.md
§3, founder-approved 2026-09-04) from the dead ``trades`` table and paper
sessions to the P&L reconciler over the strategy's CLOSED positions, priced
from REAL broker fills. Two facts must travel WITH every number on the chain:

* ``unpriced_positions`` — closed positions the platform could NOT price
  (exits taken on the broker's app, phantom/cleanup rows, unfilled entries).
  Published so the coverage gap is on the chain, never hidden. NULL for paper
  listings.
* ``pnl_basis`` — ``reconciled_net_estimated_costs`` (live: NET of MODELLED
  charges — fills are real, brokerage/STT/exchange/SEBI/stamp/GST are our
  estimate at published rates, not the broker's contract note) or
  ``paper_sessions_gross``.

Both fields are part of ``data_hash`` from the first row written after this
migration. There is NO existing chain to migrate: ``ledger_snapshots`` has 0
rows on prod (pre-flight SELECT in tests/db/test_045_ledger_pnl_basis.py), and
the model/verifier treat the columns as optional so any pre-045 row would
still verify.

ADDITIVE: two nullable columns, no backfill, no data move. Touches no trading
table. DOWNGRADE IS REAL: drops both columns; with 0 rows there is nothing to
restore.

Revision ID: 045_ledger_pnl_basis
Revises: 044_paywall_grace
Create Date: 2026-09-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "045_ledger_pnl_basis"
down_revision: str | None = "044_paywall_grace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ledger_snapshots",
        sa.Column("unpriced_positions", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ledger_snapshots",
        sa.Column("pnl_basis", sa.String(length=48), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ledger_snapshots", "pnl_basis")
    op.drop_column("ledger_snapshots", "unpriced_positions")
