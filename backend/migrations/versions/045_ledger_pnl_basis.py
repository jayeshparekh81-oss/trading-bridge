"""ledger_snapshots: unpriced_positions, pnl_basis, max_drawdown_inr; max_drawdown_pct nullable.

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

* ``max_drawdown_inr`` — peak-to-trough drawdown of the cumulative NET P&L
  series in rupees. The pre-existing ``max_drawdown_pct`` (NUMERIC(7,4), max
  999.9999) is a "% of the cumulative-P&L peak": on the real BSE series
  (peak +14,283 then -330,199) that is 2,411% — it would overflow the column
  and 500 the very first snapshot, and it is not a number anyone should chain.
  Live listings therefore publish the rupee drawdown and leave the percent
  NULL; paper listings keep publishing both. ``max_drawdown_pct`` becomes
  NULLABLE (the ``>= 0`` CHECK from 019 still applies to non-NULL values).

All three fields are part of ``data_hash`` from the first row written after
this migration. There is NO existing chain to migrate: ``ledger_snapshots``
has 0 rows on prod (pre-flight SELECT in tests/db/test_045_ledger_pnl_basis.py
and in the deploy runbook — a HARD STOP if it is not 0, because the verifier
reconstructs the hash from the row and a pre-045 row would not carry the
new keys; ``_payload_from_row`` omits them when ``pnl_basis`` is NULL so an
old row would still verify, but that path is untested on real data).

ADDITIVE: three nullable columns + one DROP NOT NULL, no backfill, no data
move. Touches no trading table. DOWNGRADE IS REAL: drops the three columns and
restores NOT NULL on ``max_drawdown_pct`` (valid: 0 rows; if rows exist with
NULL pct the downgrade must first be preceded by a manual decision — it will
refuse rather than invent a value).

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
    op.add_column(
        "ledger_snapshots",
        sa.Column("max_drawdown_inr", sa.Numeric(20, 4), nullable=True),
    )
    op.alter_column("ledger_snapshots", "max_drawdown_pct", nullable=True)


def downgrade() -> None:
    # Refuses (NOT NULL violation) rather than inventing a percent for a live
    # row — a manual decision has to precede this on a non-empty chain.
    op.alter_column("ledger_snapshots", "max_drawdown_pct", nullable=False)
    op.drop_column("ledger_snapshots", "max_drawdown_inr")
    op.drop_column("ledger_snapshots", "pnl_basis")
    op.drop_column("ledger_snapshots", "unpriced_positions")
