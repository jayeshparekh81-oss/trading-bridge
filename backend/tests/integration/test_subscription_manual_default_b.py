"""New-subscriber MANUAL default — model + migration 040 pairing (Module B+).

Founder decision: a NEW marketplace subscriber starts MANUAL
(``execution_mode='offline'``) and self-enables AUTO later. Migration 040 flips
the DB column default; this file proves the COMPANION model change actually
delivers it — the ORM's Python-side ``default=`` is what new app-created rows
receive (both creation sites omit ``execution_mode``, and a client-side default
bypasses the DB ``server_default`` entirely).

DEFAULT-ONLY semantics proven both ways in one DB: a pre-existing row with an
EXPLICIT mode keeps it (the paper harness's AUTO subscriber 'sub B' is exactly
such a row), while a NEW insert that omits the column lands 'offline'.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.db.models.marketplace_subscription import MarketplaceSubscription
from tests.integration.test_marketplace_fanout_webhook import _run


async def _insert_sub(maker, **overrides):
    """Insert a subscription the way BOTH app creation sites do — omitting
    ``execution_mode`` unless a test passes it explicitly."""
    async with maker() as s:
        sub = MarketplaceSubscription(
            listing_id=uuid.uuid4(),
            subscriber_id=uuid.uuid4(),
            subscribed_at=datetime.now(UTC),
            status="active",
            amount_paid_inr=Decimal("0"),
            **overrides,
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return sub.id


def _mode_of(maker, sub_id):
    async def _load():
        async with maker() as s:
            row = (
                await s.execute(
                    select(MarketplaceSubscription).where(
                        MarketplaceSubscription.id == sub_id
                    )
                )
            ).scalar_one()
            return row.execution_mode

    return _run(_load())


def test_new_subscription_defaults_to_offline_manual(db_session_maker):
    """DELIVERY PROOF: a new ORM-created subscription that omits
    ``execution_mode`` (as both app creation sites do) lands MANUAL."""
    sub_id = _run(_insert_sub(db_session_maker))
    assert _mode_of(db_session_maker, sub_id) == "offline"


def test_explicit_mode_still_respected_default_only(db_session_maker):
    """DEFAULT-ONLY both ways: an EXPLICIT 'auto' (harness sub B shape / the
    self-enable-AUTO path) is honoured — the default never overrides an
    explicit value — and a row created BEFORE new inserts keeps its mode
    unchanged while new omitting inserts get 'offline'."""
    # 'Existing' row with explicit auto (what harness sub B is on prod).
    auto_id = _run(_insert_sub(db_session_maker, execution_mode="auto"))
    # 'Existing' row with explicit offline (harness sub A shape).
    offline_id = _run(_insert_sub(db_session_maker, execution_mode="offline"))
    # NEW subscriber after the flip — omits the column.
    new_id = _run(_insert_sub(db_session_maker))

    assert _mode_of(db_session_maker, auto_id) == "auto"        # sub B stays AUTO
    assert _mode_of(db_session_maker, offline_id) == "offline"  # sub A unchanged
    assert _mode_of(db_session_maker, new_id) == "offline"      # new => MANUAL


def test_model_and_migration_040_defaults_agree():
    """The ORM model's server_default/default and migration 040's new DB default
    are the SAME value — no model/DB divergence after deploy."""
    import importlib

    col = MarketplaceSubscription.__table__.columns["execution_mode"]
    m040 = importlib.import_module("migrations.versions.040_manual_exec_default")

    assert col.default.arg == "offline"               # Python-side (ORM inserts)
    assert col.server_default.arg == "offline"        # DDL-side (raw SQL inserts)
    assert m040._NEW_DEFAULT == "offline"             # DB migration target
    assert col.server_default.arg == m040._NEW_DEFAULT
