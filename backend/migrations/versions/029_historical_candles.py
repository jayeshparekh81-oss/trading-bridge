"""``historical_candles`` table — Queue CCC Phase 2 skeleton.

Persistent OHLC store for backtest realism. Same OHLC for every user;
``fetched_by_user_id`` is attribution-only, NOT access control. See
``backend/app/db/models/historical_candle.py`` (F1) for the ORM mapper
and ``docs/QUEUE_CCC_REAL_DHAN_DESIGN_v2.md`` §2.2 for the
shared-infrastructure rationale.

Schema highlights (mirror the F1 ORM verbatim — constraint names and
``Numeric(18, 4)`` precision are load-bearing for round-trip parity
across schema_bridge):

* Composite PK ``(symbol, exchange, timeframe, timestamp)`` enables
  idempotent ``INSERT … ON CONFLICT DO NOTHING`` upserts without uuid
  bloat (F4 ``repository.upsert_batch`` depends on this).
* ``ck_hc_timeframe_enum`` allows only the 5 supported timeframes
  (``1m, 5m, 15m, 1h, 1d``). Future additions (``30m``, ``4h``,
  ``1w``) will require an ALTER on this CHECK — acknowledged tradeoff
  per founder note 2026-06-03.
* FK ``fk_hc_fetched_by_user`` uses ``ON DELETE SET NULL`` because the
  candle is a shared-infrastructure row that must outlive the user who
  originally fetched it.
* ``idx_hc_lookup (symbol, exchange, timeframe, timestamp DESC)``
  serves the dominant query (Phase 3 backtest window reads, latest
  bars first).
* ``idx_hc_freshness (timeframe, fetched_at) WHERE timeframe IN
  ('1m','5m','15m')`` is a partial index — only intraday timeframes
  need the freshness sweep that the Phase 3 rate_limit_guard / refresh
  scheduler will use; 1h/1d rows fall outside it to keep the index
  small.

Additive only — no ALTER on existing tables, fully reversible.

Revision ID: 029_historical_candles
Revises: 028_add_backtest_runs
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "029_historical_candles"
down_revision: str | None = "028_add_backtest_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "historical_candles",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("exchange", sa.Text(), nullable=False),
        sa.Column("timeframe", sa.Text(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("open", sa.Numeric(18, 4), nullable=False),
        sa.Column("high", sa.Numeric(18, 4), nullable=False),
        sa.Column("low", sa.Numeric(18, 4), nullable=False),
        sa.Column("close", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "volume",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("dhan_security_id", sa.Text(), nullable=False),
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'dhan_v2_historical'"),
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "fetched_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="SET NULL",
                name="fk_hc_fetched_by_user",
            ),
            nullable=True,
        ),
        sa.Column("quality_score", sa.Numeric(5, 2), nullable=True),
        sa.PrimaryKeyConstraint(
            "symbol",
            "exchange",
            "timeframe",
            "timestamp",
            name="pk_historical_candles",
        ),
        sa.CheckConstraint("low <= high", name="ck_hc_low_le_high"),
        sa.CheckConstraint(
            "open BETWEEN low AND high",
            name="ck_hc_open_in_range",
        ),
        sa.CheckConstraint(
            "close BETWEEN low AND high",
            name="ck_hc_close_in_range",
        ),
        sa.CheckConstraint("volume >= 0", name="ck_hc_volume_nonneg"),
        sa.CheckConstraint(
            "timeframe IN ('1m','5m','15m','1h','1d')",
            name="ck_hc_timeframe_enum",
        ),
    )

    op.create_index(
        "idx_hc_lookup",
        "historical_candles",
        ["symbol", "exchange", "timeframe", sa.text("timestamp DESC")],
    )

    op.create_index(
        "idx_hc_freshness",
        "historical_candles",
        ["timeframe", "fetched_at"],
        postgresql_where=sa.text("timeframe IN ('1m','5m','15m')"),
    )


def downgrade() -> None:
    op.drop_index(
        "idx_hc_freshness",
        table_name="historical_candles",
    )
    op.drop_index(
        "idx_hc_lookup",
        table_name="historical_candles",
    )
    op.drop_table("historical_candles")
