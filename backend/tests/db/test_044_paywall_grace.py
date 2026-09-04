"""Migration 044 — users.paywall_grace_until (additive, tz-aware, real downgrade)."""

from __future__ import annotations

import importlib
import inspect

mig = importlib.import_module("migrations.versions.044_paywall_grace")


def test_chain_and_id_length() -> None:
    assert mig.revision == "044_paywall_grace"
    assert mig.down_revision == "043_csv_export_real"
    assert len(mig.revision) <= 32


def test_upgrade_adds_exactly_one_tz_aware_nullable_column_and_downgrade_drops_it() -> None:
    up = inspect.getsource(mig.upgrade)
    down = inspect.getsource(mig.downgrade)
    assert up.count("op.add_column(") == 1 and '"users"' in up and '"paywall_grace_until"' in up
    assert "sa.DateTime(timezone=True)" in up and "nullable=True" in up
    assert "server_default" not in up  # metadata-only ADD COLUMN
    assert down.count("op.drop_column(") == 1 and '"paywall_grace_until"' in down
    for src in (up, down):
        assert "UPDATE" not in src and "DELETE" not in src and "INSERT" not in src


def test_model_declares_the_column_tz_aware() -> None:
    from sqlalchemy import DateTime

    from app.db.models.user import User

    col = User.__table__.c.paywall_grace_until
    assert isinstance(col.type, DateTime) and col.type.timezone is True and col.nullable is True


def test_pre_flight_select_documented() -> None:
    """The pre-flight the deploy runs BEFORE alembic: prove the column is absent."""
    assert "SELECT" in PRE_FLIGHT_SQL and "paywall_grace_until" in PRE_FLIGHT_SQL


PRE_FLIGHT_SQL = """
SELECT count(*) AS present FROM information_schema.columns
 WHERE table_name = 'users' AND column_name = 'paywall_grace_until';  -- expect 0 before 044, 1 after
SELECT count(*) AS users_none FROM users WHERE plan_status = 'none';  -- who the grace window protects
"""
