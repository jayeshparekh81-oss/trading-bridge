"""``historical_backfill_jobs`` table — Queue CCC Phase 3 skeleton.

**FILE-ONLY** — NOT applied on the overnight session of 2026-06-12.
Founder applies via ``alembic upgrade head`` after morning review
(see ``docs/QUEUE_CCC_OVERNIGHT_BRIEF.md`` parked-gate (a)).

Schema mirrors :class:`HistoricalBackfillJob` (see
``backend/app/db/models/historical_backfill_job.py``):

* UUID primary key with server-side ``gen_random_uuid()`` default.
* Status state machine: PENDING → RUNNING → SUCCEEDED|FAILED, enforced
  by CHECK constraint.
* Lifecycle invariants enforced at the DB layer so the Celery task
  can't accidentally land a row in an impossible state:
    - ``started_at`` is NULL iff status='PENDING'.
    - ``completed_at`` is NOT NULL iff status in (SUCCEEDED, FAILED).
    - ``error_json`` is NOT NULL iff status='FAILED'.
* Window invariant: ``from_ts <= to_ts``.
* Timeframe restricted to the same 5 values the
  ``historical_candles.ck_hc_timeframe_enum`` allows.
* FK ``fk_hbj_requested_by_user`` → ``users.id`` ON DELETE SET NULL
  (jobs outlive deleted operators; we keep the audit trail).
* Two indexes:
    - ``ix_hbj_status_requested_at`` — for the pending-queue FIFO scan.
    - ``ix_hbj_symbol_window`` — for "is this window already in
      flight?" idempotency probes the orchestrator may issue before
      enqueueing.

Additive only — no ALTER on existing tables, fully reversible.

Revision ID: 030_historical_backfill_jobs
Revises: 029_historical_candles
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "030_historical_backfill_jobs"
down_revision: str | None = "029_historical_candles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "historical_backfill_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("exchange", sa.Text(), nullable=False),
        sa.Column("timeframe", sa.Text(), nullable=False),
        sa.Column("dhan_security_id", sa.Text(), nullable=False),
        sa.Column("from_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("to_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="SET NULL",
                name="fk_hbj_requested_by_user",
            ),
            nullable=True,
        ),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "candles_inserted",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("error_json", postgresql.JSONB, nullable=True),
        sa.Column("quota_rationale_at_start", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','FAILED')",
            name="ck_hbj_status_enum",
        ),
        sa.CheckConstraint(
            "timeframe IN ('1m','5m','15m','1h','1d')",
            name="ck_hbj_timeframe_enum",
        ),
        sa.CheckConstraint("from_ts <= to_ts", name="ck_hbj_window_ordered"),
        sa.CheckConstraint(
            "(status = 'PENDING') = (started_at IS NULL)",
            name="ck_hbj_started_at_consistency",
        ),
        sa.CheckConstraint(
            "(status IN ('SUCCEEDED', 'FAILED')) = (completed_at IS NOT NULL)",
            name="ck_hbj_completed_at_consistency",
        ),
        sa.CheckConstraint(
            "(status = 'FAILED') = (error_json IS NOT NULL)",
            name="ck_hbj_error_json_consistency",
        ),
    )

    op.create_index(
        "ix_hbj_status_requested_at",
        "historical_backfill_jobs",
        ["status", "requested_at"],
    )

    op.create_index(
        "ix_hbj_symbol_window",
        "historical_backfill_jobs",
        ["symbol", "exchange", "timeframe", "from_ts", "to_ts"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hbj_symbol_window",
        table_name="historical_backfill_jobs",
    )
    op.drop_index(
        "ix_hbj_status_requested_at",
        table_name="historical_backfill_jobs",
    )
    op.drop_table("historical_backfill_jobs")
