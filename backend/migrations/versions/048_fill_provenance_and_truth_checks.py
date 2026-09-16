"""Provenance survives the log files, and the daily truth check is recorded.

TWO NEW TABLES. ADDITIVE ONLY — no column is dropped, renamed or retyped, and
no existing table is touched. Founder approved exactly that shape (C,
2026-09-16); anything non-additive was to be a RED and stop.

────────────────────────────────────────────────────────────────────────────
1. ``broker_fill_provenance`` — WHY (founder's addition A, 2026-09-16)
────────────────────────────────────────────────────────────────────────────
Whether a fill is the bot's, the founder's, or unidentifiable is decided from
Dhan's ``orderPlatform`` and ``algoOrdNo``, which live ONLY in pine_replica's
WS order-update tape: measured, Dhan's trade book carries neither (27 keys,
none of them these).

Retention of that tape was MEASURED on 2026-09-16 and there is none. No
logrotate rule names it, no cron line deletes it, no cleanup code exists in
``executor/*.py``. The files survive by luck, not by policy — and the box runs
structurally near-full, so the day someone frees space, the record since 1 Sep
silently loses the ability to say who placed what.

So the verdict is written down ONCE, at ingest, and the page never depends on
those files existing later. ``order_platform`` keeps the raw broker field and
``provenance`` keeps the decision, because a future rule change must be able to
re-decide from the original evidence rather than inherit today's answer.

Manual and unidentified fills are recorded here and NOWHERE ELSE. This is not a
customer table — it is the audit of what the account did — so storing them here
never puts a human's trade on a page that says "the bot's record".

────────────────────────────────────────────────────────────────────────────
2. ``truth_check_runs`` — WHY (R3.1)
────────────────────────────────────────────────────────────────────────────
The 15:50 EOD check compares the site against Dhan and must leave evidence: the
"Dhan se verified ✅ <date>" badge may render ONLY when a stored run covers that
position, and must show that run's date. A badge with no stored run behind it
is the same class of claim as a modelled number labelled as billed.

The verdict is stored with the window it covered, so a badge can never outlive
the check that earned it.

SAFE TO RUN: both tables are new and empty. Nothing on the execution path
reads or writes either. No position, execution or signal row is touched.

DOWNGRADE IS REAL: it drops the two tables it created, which is genuinely
lossless because nothing else references them. It does NOT touch anything that
existed before this migration.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "048_fill_provenance_and_truth_checks"
down_revision: str | None = "047_ledger_tracking_epoch"
branch_labels: str | None = None
depends_on: str | None = None

_FILLS = "broker_fill_provenance"
_RUNS = "truth_check_runs"


def upgrade() -> None:
    op.create_table(
        _FILLS,
        # The broker's own order id is the identity. Idempotency of the
        # ingester rests on this being the PRIMARY KEY, not on a uniqueness
        # convention someone can forget: ingesting the same tape twice must
        # add nothing.
        sa.Column("broker_order_id", sa.String(length=64), primary_key=True),
        sa.Column("security_id", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=True),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(20, 4), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        # Dhan's raw field: API | FOVR | FAST | … NULL means the tape did not
        # cover this fill, which is NOT the same as "not manual".
        sa.Column("order_platform", sa.String(length=16), nullable=True),
        # The decision at ingest: bot | manual | unknown. Kept ALONGSIDE the
        # raw field so a later rule change can re-decide from the evidence.
        sa.Column("provenance", sa.String(length=16), nullable=False),
        # algoOrdNo — the parent Forever order, present only on a stop child.
        # This is the hop that attributes an engine stop to its position
        # without ever comparing timestamps.
        sa.Column("parent_order_id", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        # What Dhan BILLED on this fill. NULL means the source did not say —
        # never zero, because a zero would quietly flatter every net.
        sa.Column("billed_charges", sa.Numeric(20, 4), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(f"ix_{_FILLS}_security_filled", _FILLS, ["security_id", "filled_at"])
    op.create_index(f"ix_{_FILLS}_provenance", _FILLS, ["provenance"])

    op.create_table(
        _RUNS,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False),
        # The window the run actually checked. A badge may only claim coverage
        # for a position that closed inside it.
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        # green | red. Stored as text rather than an enum so a new verdict does
        # not need a type change (this migration must stay additive, and so
        # must the next one).
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("fills_checked", sa.Integer(), nullable=False, server_default="0"),
        # What was wrong, in the customer's own words, when the verdict is red.
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(f"ix_{_RUNS}_ran_at", _RUNS, ["ran_at"])


def downgrade() -> None:
    """Drops ONLY what this migration created. Nothing older is touched."""
    op.drop_index(f"ix_{_RUNS}_ran_at", table_name=_RUNS)
    op.drop_table(_RUNS)
    op.drop_index(f"ix_{_FILLS}_provenance", table_name=_FILLS)
    op.drop_index(f"ix_{_FILLS}_security_filled", table_name=_FILLS)
    op.drop_table(_FILLS)
