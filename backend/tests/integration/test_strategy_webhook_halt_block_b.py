"""WEBHOOK HALT-BLOCK — master-emergency enforcement at the signal-accept path.

A guard at the TOP of ``receive_strategy_signal``: when ``is_platform_halted()``
is True the signal is REJECTED (503) BEFORE any body read / token lookup / DB
write / queue dispatch. When NOT halted (the normal case) the path is
BYTE-IDENTICAL. Scoped to this endpoint only — health/other endpoints unaffected.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy import func, select

from app.db.models.strategy_signal import StrategySignal
from tests.integration.conftest import HMAC_HEADER, _sign
from tests.integration.test_marketplace_fanout_webhook import (
    _entry_payload,
    _run,
    _url,
)


def _post(client, seed):
    body = _entry_payload()
    return client.post(
        _url(seed["token_plain"]),
        content=body,
        headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
    )


def _signal_count(maker, strategy_id):
    async def _load():
        async with maker() as s:
            return (await s.execute(
                select(func.count()).select_from(StrategySignal).where(
                    StrategySignal.strategy_id == strategy_id))).scalar_one()

    return _run(_load())


def test_not_halted_signal_accepted_202(client, seed, monkeypatch):
    """NOT halted (default) → processes + queues exactly as today (byte-identical)."""
    monkeypatch.setattr(
        "app.api.strategy_webhook.is_platform_halted", lambda: False)
    dispatched: list = []
    monkeypatch.setattr(
        "app.api.strategy_webhook.dispatch_signal",
        lambda sid, kind: dispatched.append((sid, kind)))

    resp = _post(client, seed)

    assert resp.status_code == 202, resp.text
    assert len(dispatched) == 1          # owner dispatch fired exactly as today


def test_halted_signal_rejected_503_not_queued_not_persisted(
    client, seed, db_session_maker, monkeypatch
):
    """HALTED → 503, NOT queued, NOT persisted, LOGGED (rejected before any work).

    The 503 STATUS is the client-facing signal. The reject REASON is NOT on the
    wire: the deployed ``SensitiveDataFilterMiddleware`` scrubs every 5xx JSON
    body to a generic ``{"detail": "internal error"}`` — so the halt reason lives
    in the WARNING log + the status code (by design — we don't leak platform
    state to arbitrary webhook callers; that middleware is out of scope here).
    """
    log_spy = MagicMock()
    monkeypatch.setattr("app.api.strategy_webhook.is_platform_halted", lambda: True)
    monkeypatch.setattr("app.api.strategy_webhook.logger", log_spy)
    dispatched: list = []
    monkeypatch.setattr(
        "app.api.strategy_webhook.dispatch_signal",
        lambda sid, kind: dispatched.append((sid, kind)))

    resp = _post(client, seed)

    assert resp.status_code == 503, resp.text          # client-facing signal
    assert dispatched == []                            # NOT queued
    assert _signal_count(db_session_maker, seed["strategy_id"]) == 0   # NOT persisted
    # rejected reason is LOGGED (masked from the wire body by security middleware)
    assert log_spy.warning.call_count == 1
    assert "platform_halted" in log_spy.warning.call_args.args[0]


def test_halt_then_unhalt_resumes(client, seed, monkeypatch):
    """Halt → 503; un-halt → 202. The flag alone gates the path."""
    halted = {"v": True}
    monkeypatch.setattr(
        "app.api.strategy_webhook.is_platform_halted", lambda: halted["v"])
    monkeypatch.setattr(
        "app.api.strategy_webhook.dispatch_signal", lambda sid, kind: None)

    assert _post(client, seed).status_code == 503     # halted
    halted["v"] = False
    assert _post(client, seed).status_code == 202     # resumed


def test_health_endpoint_unaffected_when_halted(client, monkeypatch):
    """The guard is SCOPED to the signal-accept endpoint — a non-signal endpoint
    (health) is unaffected even while halted."""
    monkeypatch.setattr(
        "app.api.strategy_webhook.is_platform_halted", lambda: True)
    resp = client.get("/health")
    assert resp.status_code == 200
