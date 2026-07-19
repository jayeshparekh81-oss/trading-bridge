"""OPTIONS BRICK #4 — SLICE ① FIX 2: options-strategy entry fan-out is BLOCKED.

Audit finding: the webhook entry fan-out has no instrument gate, so an AUTO
subscriber of an OPTIONS strategy would get a mirror position on the
UNDERLYING (futures-resolved symbol) — wrong instrument, wrong size, and (no
options exit hook) a permanent orphan. Until proper option-leg mirroring lands
(a later slice), options-strategy fan-out is skipped with a log:
``dispatch_subscriber_executions`` gates on ``resolve_instrument_type(strategy)
== OPTIONS`` and returns no results — no mirror row, no execution row.

Futures fan-out is UNAFFECTED (contrast test here + the whole existing fanout
suite). The sacred webhook file is untouched — the gate lives in
marketplace_fanout.py.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from tests.integration.conftest import HMAC_HEADER, _sign
from tests.integration.test_marketplace_fanout_webhook import (
    _entry_payload,
    _run,
    _seed_listing_and_subs,
    _url,
)

_NRML_OPTIONS = {
    "option_type": "auto",
    "strike_selection": {"method": "ATM", "offset": 0},
    "expiry": "current_week",
    "product_type": "NRML",
}


def _post_entry(client, seed):
    body = _entry_payload()
    return client.post(
        _url(seed["token_plain"]), content=body,
        headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"})


async def _make_options_strategy(maker, strategy_id):
    async with maker() as s:
        strat = await s.get(Strategy, strategy_id)
        strat.strategy_json = {"options": _NRML_OPTIONS}
        await s.commit()


def _subscriber_position_count(maker, strategy_id):
    async def _load():
        async with maker() as s:
            return (await s.execute(
                select(func.count()).select_from(StrategyPosition).where(
                    StrategyPosition.strategy_id == strategy_id,
                    StrategyPosition.subscription_id.is_not(None)))).scalar_one()

    return _run(_load())


def test_options_strategy_entry_fanout_blocked(
    client, seed, db_session_maker, monkeypatch
):
    """OPTIONS strategy + AUTO subscriber + flag ON → NO mirror row created."""
    monkeypatch.setattr(get_settings(), "marketplace_fanout_enabled", True)
    monkeypatch.setattr(
        "app.api.strategy_webhook.dispatch_signal", lambda sid, kind: None)
    _run(_make_options_strategy(db_session_maker, seed["strategy_id"]))
    _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0))

    resp = _post_entry(client, seed)

    assert resp.status_code == 202, resp.text          # webhook path unaffected
    assert _subscriber_position_count(db_session_maker, seed["strategy_id"]) == 0


def test_futures_strategy_entry_fanout_unaffected(
    client, seed, db_session_maker, monkeypatch
):
    """Contrast: the SAME scene WITHOUT options config (futures default,
    strategy_json untouched) still creates the AUTO subscriber's mirror."""
    monkeypatch.setattr(get_settings(), "marketplace_fanout_enabled", True)
    monkeypatch.setattr(
        "app.api.strategy_webhook.dispatch_signal", lambda sid, kind: None)
    _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0))

    resp = _post_entry(client, seed)

    assert resp.status_code == 202, resp.text
    assert _subscriber_position_count(db_session_maker, seed["strategy_id"]) == 1


def test_flag_off_options_strategy_no_fanout_no_error(
    client, seed, db_session_maker, monkeypatch
):
    """Flag OFF (default) + options strategy → byte-identical no-fan-out path."""
    assert get_settings().marketplace_fanout_enabled is False
    monkeypatch.setattr(
        "app.api.strategy_webhook.dispatch_signal", lambda sid, kind: None)
    _run(_make_options_strategy(db_session_maker, seed["strategy_id"]))

    resp = _post_entry(client, seed)

    assert resp.status_code == 202, resp.text
    assert _subscriber_position_count(db_session_maker, seed["strategy_id"]) == 0
