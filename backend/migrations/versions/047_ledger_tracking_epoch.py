"""A chained number records the window it covers.

WHY. On 2026-09-09 the founder set a TRACKING CUT-OFF at 1 Sep 2026 00:00 IST:
the platform's record begins there, everything earlier is archived (hidden from
what is counted and shown, never deleted — these are real broker orders held
for tax and audit).

``ledger_snapshots`` is APPEND-ONLY and HASH-CHAINED. Once sequence #1 exists,
its numbers cannot be corrected without breaking chain verification, and the
showcase page fails verification loudly when a past row changes. So a snapshot
must carry the definition of the window it was computed over — otherwise a
future reader sees ``cumulative_pnl_inr`` with no way to know which trades it
did and did not include, and a later change to the epoch silently changes what
every historical row MEANS while the chain still asserts the old value.

``SnapshotPayload`` (strategy_engine/ledger/snapshots.py) has no field for
this. This adds one column so the window travels with the number.

SAFE TO RUN, and the timing is the point:
  * ``ledger_snapshots`` holds ZERO rows at the time of writing, and the daily
    beat is dormant (``ledger_daily_snapshot_enabled=False``). Snapshot #1 is
    the founder's own manual command and has deliberately NOT been taken yet.
    Running this BEFORE that command is what makes it a schema addition rather
    than an edit to an immutable record.
  * NULLABLE, no server default, no backfill. Nothing is written to any row —
    there are no rows. A NULL means "computed before the cut-off existed",
    which is honest and distinguishable from any real epoch.
  * ``ledger_snapshots`` is NOT a trading table. No position, execution or
    signal is touched. Nothing on the execution path reads this column.

WHY NOT A COLUMN FOR THE CUT-OFF ITSELF. The cut-off is deliberately a SETTING
(``app.core.tracking_epoch``), not a flag on trade rows: it is derivable from
each row's own timestamp, so a column would duplicate a fact and could drift
from it, and backfilling one would mean writing to real broker-order history.
This column is the opposite case — it records, once, which window an IMMUTABLE
number was computed under. That fact is not derivable from anything else, and
after the row is chained it can never be recomputed.

DOWNGRADE IS REAL, NOT A STUB: it drops the column. That is genuinely lossless
here and only here, because the column is new, nullable and — at the time this
migration ships — has no rows to lose. A pre-flight guard refuses to run if
that has stopped being true, rather than assuming it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "047_ledger_tracking_epoch"
down_revision: str | None = "046_pnl_attribution"
branch_labels: str | None = None
depends_on: str | None = None

_TABLE = "ledger_snapshots"
_COLUMN = "tracking_epoch"


def _row_count() -> int:
    """Pre-flight: how many snapshots already exist?"""
    bind = op.get_bind()
    return int(bind.execute(sa.text(f"SELECT count(*) FROM {_TABLE}")).scalar_one())


def upgrade() -> None:
    # PRE-FLIGHT. The safety argument above rests on the chain being empty. If
    # snapshots exist, adding a nullable column is still harmless — but the
    # DOWNGRADE would no longer be lossless, and the operator should know that
    # before running it rather than discovering it on the way back.
    existing = _row_count()
    if existing:
        print(
            f"NOTE: {_TABLE} already holds {existing} chained row(s). The "
            f"column is added NULLABLE so those rows keep a NULL epoch "
            f"(honest: they were computed before the cut-off existed). "
            f"Downgrade would drop that column and its values."
        )

    op.add_column(
        _TABLE,
        sa.Column(
            _COLUMN,
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "The tracking cut-off in force when this snapshot was "
                "computed. NULL = computed before a cut-off existed. Records "
                "which window an append-only number covers, because the row "
                "can never be recomputed."
            ),
        ),
    )


def downgrade() -> None:
    # PRE-FLIGHT on the way back too: refuse to silently destroy recorded
    # windows on rows that can never be recomputed.
    bind = op.get_bind()
    populated = int(
        bind.execute(
            sa.text(f"SELECT count(*) FROM {_TABLE} WHERE {_COLUMN} IS NOT NULL")
        ).scalar_one()
    )
    if populated:
        raise RuntimeError(
            f"REFUSING to downgrade: {populated} chained snapshot(s) record a "
            f"{_COLUMN}. Dropping it would erase which window an immutable "
            f"number covers, and those rows cannot be recomputed. Clear the "
            f"values deliberately first if this is really what you want."
        )
    op.drop_column(_TABLE, _COLUMN)
