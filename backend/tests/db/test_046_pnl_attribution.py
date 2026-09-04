"""Migration 046 — pnl_attribution (+detail) on positions, human_interfered_positions on snapshots."""

from __future__ import annotations

import importlib
import inspect

mig = importlib.import_module("migrations.versions.046_pnl_attribution")


def test_chain_and_id_length() -> None:
    assert mig.revision == "046_pnl_attribution"
    assert mig.down_revision == "045_ledger_pnl_basis"
    assert len(mig.revision) <= 32


def test_upgrade_adds_three_nullable_columns_and_downgrade_drops_them() -> None:
    up = inspect.getsource(mig.upgrade)
    down = inspect.getsource(mig.downgrade)
    assert up.count("op.add_column(") == 3
    assert up.count('"strategy_positions"') == 2 and up.count('"ledger_snapshots"') == 1
    assert '"pnl_attribution"' in up and "sa.String(length=32)" in up
    assert '"pnl_attribution_detail"' in up and "sa.Text()" in up
    assert '"human_interfered_positions"' in up and "sa.Integer()" in up
    assert up.count("nullable=True") == 3 and "server_default" not in up
    assert "alter_column" not in up
    assert down.count("op.drop_column(") == 3
    for src in (up, down):
        assert "UPDATE" not in src and "DELETE" not in src and "INSERT" not in src


def test_model_and_payload_agree_with_the_migration() -> None:
    from sqlalchemy import Integer, String, Text

    from app.db.models.ledger_snapshot import LedgerSnapshot
    from app.db.models.strategy_position import StrategyPosition
    from app.domains.pnl_reconciler.attribution import ATTRIBUTION_TAGS
    from app.strategy_engine.ledger.snapshots import SnapshotPayload

    p = StrategyPosition.__table__
    assert isinstance(p.c.pnl_attribution.type, String) and p.c.pnl_attribution.type.length == 32
    assert p.c.pnl_attribution.nullable
    assert isinstance(p.c.pnl_attribution_detail.type, Text) and p.c.pnl_attribution_detail.nullable
    assert all(len(tag) <= 32 for tag in ATTRIBUTION_TAGS)

    s = LedgerSnapshot.__table__
    assert isinstance(s.c.human_interfered_positions.type, Integer)
    assert s.c.human_interfered_positions.nullable
    assert "human_interfered_positions" in SnapshotPayload.model_fields
    assert SnapshotPayload.model_fields["human_interfered_positions"].default is None


PRE_FLIGHT_SQL = """
SELECT count(*) AS snapshots FROM ledger_snapshots;  -- expect 0: there is no chain to migrate
SELECT count(*) AS present FROM information_schema.columns
 WHERE (table_name = 'strategy_positions' AND column_name IN ('pnl_attribution', 'pnl_attribution_detail'))
    OR (table_name = 'ledger_snapshots' AND column_name = 'human_interfered_positions');  -- 0 before, 3 after
"""


def test_pre_flight_select_documented() -> None:
    assert "ledger_snapshots" in PRE_FLIGHT_SQL and "expect 0" in PRE_FLIGHT_SQL
