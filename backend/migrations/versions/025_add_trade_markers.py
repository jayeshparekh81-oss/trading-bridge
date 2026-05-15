"""``trade_markers`` table — Phase A persistent marker layer.

Adds a single new table with:
    * Two composite read indexes: (strategy_id, timestamp_utc) and
      (user_id, symbol, mode).
    * Six CHECK constraints — three enum-vocabulary gates plus three
      co-axis correctness gates (exit_reason/pnl only on EXIT rows,
      price + quantity positive).
    * One partial unique index on
      ``(strategy_id, side, price, FLOOR(EXTRACT(EPOCH FROM timestamp_utc AT TIME ZONE 'UTC'))::bigint)``
      enforcing the 1-second idempotency dedup window.

Additive only: no ALTER, no DROP, no changes to existing tables. Fully
reversible via ``downgrade()``.

Revision ID: 025_add_trade_markers
Revises: 024_indicator_approval_queue
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "025_add_trade_markers"
down_revision: str | None = "024_indicator_approval_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SIDE_VALUES = "'LONG_ENTRY', 'LONG_EXIT', 'SHORT_ENTRY', 'SHORT_EXIT'"
_MODE_VALUES = "'BACKTEST', 'PAPER', 'LIVE'"
_EXIT_REASON_VALUES = (
    "'SIGNAL', 'STOP_LOSS', 'TAKE_PROFIT', "
    "'MANUAL', 'SQUARE_OFF', 'EXPIRY'"
)


def upgrade() -> None:
    op.create_table(
        "trade_markers",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "strategy_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("strategies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("exchange", sa.String(16), nullable=False),
        sa.Column("side", sa.String(16), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "timestamp_utc",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column(
            "linked_marker_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("trade_markers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("pnl", sa.Numeric(20, 8), nullable=True),
        sa.Column("exit_reason", sa.String(16), nullable=True),
        sa.Column(
            "signal_metadata",
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── CHECK constraints (enum vocabularies + co-axis rules) ──
    op.create_check_constraint(
        "side_valid",
        "trade_markers",
        f"side IN ({_SIDE_VALUES})",
    )
    op.create_check_constraint(
        "mode_valid",
        "trade_markers",
        f"mode IN ({_MODE_VALUES})",
    )
    op.create_check_constraint(
        "exit_reason_valid",
        "trade_markers",
        (
            "exit_reason IS NULL OR exit_reason IN ("
            f"{_EXIT_REASON_VALUES})"
        ),
    )
    op.create_check_constraint(
        "exit_reason_only_on_exit",
        "trade_markers",
        (
            "(exit_reason IS NULL) OR "
            "(side IN ('LONG_EXIT', 'SHORT_EXIT'))"
        ),
    )
    op.create_check_constraint(
        "pnl_only_on_exit",
        "trade_markers",
        "(pnl IS NULL) OR (side IN ('LONG_EXIT', 'SHORT_EXIT'))",
    )
    op.create_check_constraint(
        "quantity_positive",
        "trade_markers",
        "quantity > 0",
    )
    op.create_check_constraint(
        "price_positive",
        "trade_markers",
        "price > 0",
    )

    # ── Single-column indexes (echoes ORM ``index=True``) ──
    op.create_index(
        "ix_trade_markers_strategy_id",
        "trade_markers",
        ["strategy_id"],
    )
    op.create_index(
        "ix_trade_markers_user_id",
        "trade_markers",
        ["user_id"],
    )
    op.create_index(
        "ix_trade_markers_symbol",
        "trade_markers",
        ["symbol"],
    )
    op.create_index(
        "ix_trade_markers_timestamp_utc",
        "trade_markers",
        ["timestamp_utc"],
    )

    # ── Composite read indexes ──
    op.create_index(
        "ix_trade_markers_strategy_id_timestamp_utc",
        "trade_markers",
        ["strategy_id", "timestamp_utc"],
    )
    op.create_index(
        "ix_trade_markers_user_id_symbol_mode",
        "trade_markers",
        ["user_id", "symbol", "mode"],
    )

    # ── Idempotency dedup index (Postgres-only expression) ──
    # AT TIME ZONE 'UTC' makes the conversion deterministic (literal
    # zone), so EXTRACT(EPOCH FROM timestamptz) is IMMUTABLE and
    # acceptable in a unique index expression. Without the explicit
    # zone, EXTRACT(EPOCH FROM timestamp WITHOUT TIME ZONE) is only
    # STABLE — it depends on the session TimeZone setting — and
    # PostgreSQL rejects it. FLOOR(...)::bigint floor-truncates to
    # whole seconds since epoch, giving the same 1-second dedup
    # window as the original ``date_trunc('second', timestamp_utc)``
    # semantic. On test (SQLite) the expression is not available; we
    # conditionally create the index only when the bind dialect is
    # postgresql.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE UNIQUE INDEX uq_trade_markers_idempotent_second "
            "ON trade_markers ("
            "strategy_id, side, price, "
            "(FLOOR(EXTRACT(EPOCH FROM timestamp_utc AT TIME ZONE 'UTC'))::bigint)"
            ")"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP INDEX IF EXISTS uq_trade_markers_idempotent_second"
        )

    op.drop_index(
        "ix_trade_markers_user_id_symbol_mode",
        table_name="trade_markers",
    )
    op.drop_index(
        "ix_trade_markers_strategy_id_timestamp_utc",
        table_name="trade_markers",
    )
    op.drop_index(
        "ix_trade_markers_timestamp_utc",
        table_name="trade_markers",
    )
    op.drop_index(
        "ix_trade_markers_symbol",
        table_name="trade_markers",
    )
    op.drop_index(
        "ix_trade_markers_user_id",
        table_name="trade_markers",
    )
    op.drop_index(
        "ix_trade_markers_strategy_id",
        table_name="trade_markers",
    )

    op.drop_constraint(
        "ck_trade_markers_price_positive",
        "trade_markers",
        type_="check",
    )
    op.drop_constraint(
        "ck_trade_markers_quantity_positive",
        "trade_markers",
        type_="check",
    )
    op.drop_constraint(
        "ck_trade_markers_pnl_only_on_exit",
        "trade_markers",
        type_="check",
    )
    op.drop_constraint(
        "ck_trade_markers_exit_reason_only_on_exit",
        "trade_markers",
        type_="check",
    )
    op.drop_constraint(
        "ck_trade_markers_exit_reason_valid",
        "trade_markers",
        type_="check",
    )
    op.drop_constraint(
        "ck_trade_markers_mode_valid",
        "trade_markers",
        type_="check",
    )
    op.drop_constraint(
        "ck_trade_markers_side_valid",
        "trade_markers",
        type_="check",
    )

    op.drop_table("trade_markers")
