"""Migration 045 — ledger_snapshots.unpriced_positions + pnl_basis (additive, real downgrade)."""

from __future__ import annotations

import importlib
import inspect

mig = importlib.import_module("migrations.versions.045_ledger_pnl_basis")


def test_chain_and_id_length() -> None:
    assert mig.revision == "045_ledger_pnl_basis"
    assert mig.down_revision == "044_paywall_grace"
    assert len(mig.revision) <= 32


def test_upgrade_adds_two_nullable_columns_and_downgrade_drops_both() -> None:
    up = inspect.getsource(mig.upgrade)
    down = inspect.getsource(mig.downgrade)
    assert up.count("op.add_column(") == 2 and up.count('"ledger_snapshots"') == 2
    assert '"unpriced_positions"' in up and "sa.Integer()" in up
    assert '"pnl_basis"' in up and "sa.String(length=48)" in up
    assert up.count("nullable=True") == 2 and "server_default" not in up
    assert down.count("op.drop_column(") == 2
    for src in (up, down):
        assert "UPDATE" not in src and "DELETE" not in src and "INSERT" not in src


def test_model_and_payload_agree_with_the_migration() -> None:
    from sqlalchemy import Integer, String

    from app.db.models.ledger_snapshot import LedgerSnapshot
    from app.strategy_engine.ledger.snapshots import SnapshotPayload

    t = LedgerSnapshot.__table__
    assert isinstance(t.c.unpriced_positions.type, Integer) and t.c.unpriced_positions.nullable
    assert (
        isinstance(t.c.pnl_basis.type, String)
        and t.c.pnl_basis.type.length == 48
        and t.c.pnl_basis.nullable
    )
    assert (
        "unpriced_positions" in SnapshotPayload.model_fields
        and "pnl_basis" in SnapshotPayload.model_fields
    )
    # optional on the payload, so a pre-045 row still verifies
    assert SnapshotPayload.model_fields["pnl_basis"].default is None


PRE_FLIGHT_SQL = """
SELECT count(*) AS snapshots FROM ledger_snapshots;  -- expect 0: there is no chain to migrate
SELECT count(*) AS present FROM information_schema.columns
 WHERE table_name = 'ledger_snapshots' AND column_name IN ('unpriced_positions', 'pnl_basis');  -- 0 before, 2 after
"""


def test_pre_flight_select_documented() -> None:
    assert "ledger_snapshots" in PRE_FLIGHT_SQL and "expect 0" in PRE_FLIGHT_SQL
