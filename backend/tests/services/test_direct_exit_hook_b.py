"""FAN-OUT Module B+ — PIECE 1 (unit): the direct_exit → fan_out_exit hook.

Tests ``direct_exit._maybe_fan_out_exit`` in isolation — the gating (flag OFF /
no subscribers → no-op) and the GUARD (a fan-out error is swallowed, so it can
NEVER break the owner's own exit). No DB, no broker.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.direct_exit as de


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _fake_maker():
    return _FakeSession()


def _patch(monkeypatch, *, enabled, subs=None, foe=None):
    monkeypatch.setattr("app.services.marketplace_fanout.fanout_enabled",
                        MagicMock(return_value=enabled))
    ras = AsyncMock(return_value=subs if subs is not None else [])
    monkeypatch.setattr(
        "app.services.marketplace_fanout.resolve_active_subscriptions", ras)
    foe = foe or AsyncMock(return_value=[])
    monkeypatch.setattr("app.services.marketplace_fanout.fan_out_exit", foe)
    monkeypatch.setattr("app.db.session.get_sessionmaker", lambda: _fake_maker)
    return ras, foe


@pytest.mark.asyncio
async def test_hook_flag_off_is_pure_noop(monkeypatch):
    ras, foe = _patch(monkeypatch, enabled=False)
    await de._maybe_fan_out_exit(
        signal=MagicMock(), strategy=MagicMock(id=uuid.uuid4()),
        action_kind="exit")
    ras.assert_not_called()          # flag OFF → never even resolves subs
    foe.assert_not_called()


@pytest.mark.asyncio
async def test_hook_no_subscribers_is_noop(monkeypatch):
    ras, foe = _patch(monkeypatch, enabled=True, subs=[])
    await de._maybe_fan_out_exit(
        signal=MagicMock(), strategy=MagicMock(id=uuid.uuid4()),
        action_kind="exit")
    ras.assert_called_once()
    foe.assert_not_called()          # no subs → fan_out_exit never called


@pytest.mark.asyncio
async def test_hook_with_subscribers_calls_fan_out_exit(monkeypatch):
    subs = [MagicMock(), MagicMock()]
    _, foe = _patch(monkeypatch, enabled=True, subs=subs)
    sig, strat = MagicMock(), MagicMock(id=uuid.uuid4())
    await de._maybe_fan_out_exit(signal=sig, strategy=strat, action_kind="sl_hit")
    foe.assert_awaited_once()
    kw = foe.call_args.kwargs
    assert kw["action_kind"] == "sl_hit"
    assert kw["subscribers"] is subs
    assert kw["signal"] is sig and kw["strategy"] is strat


@pytest.mark.asyncio
async def test_hook_swallows_fan_out_error(monkeypatch):
    """A fan-out failure MUST NOT propagate — the owner's own exit is sacred."""
    _patch(monkeypatch, enabled=True, subs=[MagicMock()],
           foe=AsyncMock(side_effect=RuntimeError("boom")))
    # Must return normally (no exception) despite fan_out_exit raising.
    await de._maybe_fan_out_exit(
        signal=MagicMock(), strategy=MagicMock(id=uuid.uuid4()),
        action_kind="exit")
