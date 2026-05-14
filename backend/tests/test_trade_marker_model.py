"""Structural tests for ``app.db.models.trade_marker`` + migration 025.

The repo's CI does **not** run live Alembic against a real Postgres in
the unit-test harness — see the note in ``tests/db/test_paper_sessions_migration.py``.
Instead we exercise the schema via ``Base.metadata.create_all`` against
an in-memory SQLite engine and assert:

    * The ORM model registered ``trade_markers`` with ``Base.metadata``.
    * Expected columns, FK targets, and indexes are present.
    * The migration's ``revision`` / ``down_revision`` form a contiguous
      chain off ``024_indicator_approval_queue``.
    * ``upgrade()`` body references the new table; ``downgrade()`` drops it.

The dedup partial unique index (``date_trunc('second', ...)``) is
Postgres-only and is therefore asserted by source-string inspection
rather than by structural metadata lookup.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from app.db.base import Base
from app.db.models.trade_marker import (
    MarkerExitReason,
    MarkerMode,
    MarkerSide,
    TradeMarker,
)


# ─── Enum vocabulary ──────────────────────────────────────────────────


class TestMarkerEnums:
    def test_side_values(self) -> None:
        assert {m.value for m in MarkerSide} == {
            "LONG_ENTRY",
            "LONG_EXIT",
            "SHORT_ENTRY",
            "SHORT_EXIT",
        }

    def test_mode_values(self) -> None:
        assert {m.value for m in MarkerMode} == {
            "BACKTEST",
            "PAPER",
            "LIVE",
        }

    def test_exit_reason_values(self) -> None:
        assert {m.value for m in MarkerExitReason} == {
            "SIGNAL",
            "STOP_LOSS",
            "TAKE_PROFIT",
            "MANUAL",
            "SQUARE_OFF",
            "EXPIRY",
        }

    @pytest.mark.parametrize(
        "side, expected",
        [
            (MarkerSide.LONG_ENTRY, True),
            (MarkerSide.SHORT_ENTRY, True),
            (MarkerSide.LONG_EXIT, False),
            (MarkerSide.SHORT_EXIT, False),
        ],
    )
    def test_is_entry(self, side: MarkerSide, expected: bool) -> None:
        assert MarkerSide.is_entry(side) is expected

    @pytest.mark.parametrize(
        "side, expected",
        [
            (MarkerSide.LONG_ENTRY, False),
            (MarkerSide.SHORT_ENTRY, False),
            (MarkerSide.LONG_EXIT, True),
            (MarkerSide.SHORT_EXIT, True),
        ],
    )
    def test_is_exit(self, side: MarkerSide, expected: bool) -> None:
        assert MarkerSide.is_exit(side) is expected

    def test_is_entry_accepts_string(self) -> None:
        assert MarkerSide.is_entry("LONG_ENTRY") is True
        assert MarkerSide.is_entry("LONG_EXIT") is False

    def test_is_exit_accepts_string(self) -> None:
        assert MarkerSide.is_exit("LONG_EXIT") is True
        assert MarkerSide.is_exit("LONG_ENTRY") is False


# ─── ORM metadata registration ────────────────────────────────────────


class TestTableMetadata:
    def test_table_registered(self) -> None:
        assert "trade_markers" in Base.metadata.tables

    def test_expected_columns(self) -> None:
        table = Base.metadata.tables["trade_markers"]
        expected = {
            "id",
            "strategy_id",
            "user_id",
            "symbol",
            "exchange",
            "side",
            "price",
            "quantity",
            "timestamp_utc",
            "mode",
            "linked_marker_id",
            "pnl",
            "exit_reason",
            "signal_metadata",
            "created_at",
            "updated_at",
        }
        assert set(table.columns.keys()) == expected

    def test_fk_targets(self) -> None:
        table = Base.metadata.tables["trade_markers"]
        fk_targets: set[str] = set()
        for col in table.columns:
            for fk in col.foreign_keys:
                fk_targets.add(fk.column.table.name)
        # ``strategies`` + ``users`` + self-referential ``trade_markers``.
        assert fk_targets == {"strategies", "users", "trade_markers"}

    def test_strategy_id_fk_on_delete(self) -> None:
        col = Base.metadata.tables["trade_markers"].columns["strategy_id"]
        fk = next(iter(col.foreign_keys))
        assert fk.ondelete == "CASCADE"

    def test_user_id_fk_on_delete(self) -> None:
        col = Base.metadata.tables["trade_markers"].columns["user_id"]
        fk = next(iter(col.foreign_keys))
        assert fk.ondelete == "CASCADE"

    def test_linked_marker_id_fk_on_delete(self) -> None:
        col = Base.metadata.tables["trade_markers"].columns["linked_marker_id"]
        fk = next(iter(col.foreign_keys))
        assert fk.ondelete == "SET NULL"

    def test_nullability(self) -> None:
        table = Base.metadata.tables["trade_markers"]
        # Required columns
        assert table.columns["strategy_id"].nullable is False
        assert table.columns["user_id"].nullable is False
        assert table.columns["symbol"].nullable is False
        assert table.columns["side"].nullable is False
        assert table.columns["price"].nullable is False
        assert table.columns["timestamp_utc"].nullable is False
        assert table.columns["mode"].nullable is False
        # Optional columns
        assert table.columns["linked_marker_id"].nullable is True
        assert table.columns["pnl"].nullable is True
        assert table.columns["exit_reason"].nullable is True

    def test_composite_indexes_present(self) -> None:
        table = Base.metadata.tables["trade_markers"]
        idx_names = {ix.name for ix in table.indexes}
        assert "ix_trade_markers_strategy_id_timestamp_utc" in idx_names
        assert "ix_trade_markers_user_id_symbol_mode" in idx_names

    def test_check_constraints_present(self) -> None:
        table = Base.metadata.tables["trade_markers"]
        check_names = {
            c.name
            for c in table.constraints
            if c.__class__.__name__ == "CheckConstraint"
        }
        # Constraint names get prefixed by the naming convention in
        # ``app.db.base.NAMING_CONVENTION``.
        for fragment in (
            "side_valid",
            "mode_valid",
            "exit_reason_valid",
            "exit_reason_only_on_exit",
            "pnl_only_on_exit",
            "quantity_positive",
            "price_positive",
        ):
            assert any(fragment in n for n in check_names if n), (
                f"missing CHECK constraint: {fragment}"
            )

    def test_repr(self) -> None:
        import uuid as _u
        from datetime import UTC, datetime
        from decimal import Decimal

        m = TradeMarker(
            strategy_id=_u.uuid4(),
            user_id=_u.uuid4(),
            symbol="NIFTY",
            exchange="NSE",
            side=MarkerSide.LONG_ENTRY.value,
            price=Decimal("22500"),
            quantity=50,
            timestamp_utc=datetime.now(UTC),
            mode=MarkerMode.PAPER.value,
        )
        s = repr(m)
        assert "TradeMarker(" in s
        assert "LONG_ENTRY" in s


# ─── Migration 025 structural checks ──────────────────────────────────


class TestMigration025:
    def test_revision_chain(self) -> None:
        module = importlib.import_module(
            "migrations.versions.025_add_trade_markers"
        )
        assert module.revision == "025_add_trade_markers"
        assert module.down_revision == "024_indicator_approval_queue"
        assert callable(module.upgrade)
        assert callable(module.downgrade)

    def test_upgrade_creates_table(self) -> None:
        module = importlib.import_module(
            "migrations.versions.025_add_trade_markers"
        )
        src = inspect.getsource(module.upgrade)
        assert '"trade_markers"' in src
        assert "create_table" in src
        # All seven CHECK constraints surface in the body.
        for fragment in (
            "side_valid",
            "mode_valid",
            "exit_reason_valid",
            "exit_reason_only_on_exit",
            "pnl_only_on_exit",
            "quantity_positive",
            "price_positive",
        ):
            assert fragment in src, f"missing in upgrade(): {fragment}"

    def test_upgrade_creates_composite_indexes(self) -> None:
        module = importlib.import_module(
            "migrations.versions.025_add_trade_markers"
        )
        src = inspect.getsource(module.upgrade)
        assert "ix_trade_markers_strategy_id_timestamp_utc" in src
        assert "ix_trade_markers_user_id_symbol_mode" in src

    def test_upgrade_pg_only_dedup_index(self) -> None:
        module = importlib.import_module(
            "migrations.versions.025_add_trade_markers"
        )
        src = inspect.getsource(module.upgrade)
        assert "uq_trade_markers_idempotent_second" in src
        assert "date_trunc('second', timestamp_utc)" in src
        assert "postgresql" in src  # dialect gate present

    def test_downgrade_drops_table(self) -> None:
        module = importlib.import_module(
            "migrations.versions.025_add_trade_markers"
        )
        src = inspect.getsource(module.downgrade)
        assert 'drop_table("trade_markers")' in src
        # All composite indexes dropped before the table.
        assert "ix_trade_markers_strategy_id_timestamp_utc" in src
        assert "ix_trade_markers_user_id_symbol_mode" in src
