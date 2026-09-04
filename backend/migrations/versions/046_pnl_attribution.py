"""strategy_positions: pnl_attribution + pnl_attribution_detail; ledger_snapshots: human_interfered_positions.

WHY. Founder's exit rule (2026-09-04, cutover-26): the founder trades the same
contracts manually in the same Dhan account the bot uses, so a bot trade is
priced from what the ACCOUNT did — it closes when the account goes flat on
the contract by any fill, provided no manual lots predate the bot's entry.
Where lot-matching would be a guess, ``final_pnl`` stays NULL and the record
must SAY why: the position carries a visible "human-interfered — not
attributable" tag instead of a silent NULL.

* ``strategy_positions.pnl_attribution`` — ``bot_only`` | ``account_flat`` |
  ``human_interfered`` | ``unpriceable``; NULL == not yet attributed.
* ``strategy_positions.pnl_attribution_detail`` — the order ids / reason the
  reconciler cited, so the tag is auditable on the row itself.
* ``ledger_snapshots.human_interfered_positions`` — of ``unpriced_positions``,
  how many are human-interfered. Part of ``data_hash`` from the first row
  written after this migration, so the explanation travels on the chain.

There is NO existing chain to migrate: ``ledger_snapshots`` has 0 rows on prod
(pre-flight SELECT in tests/db/test_046_pnl_attribution.py — a HARD STOP if it
is not 0; ``_payload_from_row`` omits the key only for pre-045 rows, which do
not exist either).

ADDITIVE: three nullable columns, no default, no backfill, no data move.
``ADD COLUMN`` with no default is metadata-only on PostgreSQL 11+ — no table
rewrite, no lock beyond the catalog update. ``strategy_positions`` IS a
trading table: the live engine reads/writes it, but SQLAlchemy selects mapped
columns by name, so the running (pre-046) image is unaffected by two extra
nullable columns, and the new image only writes them from the reconciler
(never from the execution path). DOWNGRADE IS REAL: drops the three columns.

Revision ID: 046_pnl_attribution
Revises: 045_ledger_pnl_basis
Create Date: 2026-09-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "046_pnl_attribution"
down_revision: str | None = "045_ledger_pnl_basis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "strategy_positions",
        sa.Column("pnl_attribution", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "strategy_positions",
        sa.Column("pnl_attribution_detail", sa.Text(), nullable=True),
    )
    op.add_column(
        "ledger_snapshots",
        sa.Column("human_interfered_positions", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ledger_snapshots", "human_interfered_positions")
    op.drop_column("strategy_positions", "pnl_attribution_detail")
    op.drop_column("strategy_positions", "pnl_attribution")
