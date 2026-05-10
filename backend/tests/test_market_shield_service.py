"""Tests for :mod:`app.services.market_shield_service`.

Covers the design proposal's six paths:
* default OFF short-circuits everything (no Redis I/O, no compute)
* cold-start (any index OHLC missing in Redis) = pass-through
* breadth weak (<3 of 4 bullish) = pass-through
* breadth strong + position not falling = HELD (Redis record written)
* held EXIT released on ATR-override (drop ≥ 1×ATR)
* held EXIT released on timeout (≥30 min wallclock)
* prior-hold collision: ``has_active_hold`` short-circuits a 2nd EXIT
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio

from app.core import config as app_config
from app.core import redis_client
from app.services import market_shield_service as svc


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture(autouse=True)
async def _patch_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[fake_aioredis.FakeRedis]:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    app_config.get_settings.cache_clear()
    yield
    app_config.get_settings.cache_clear()


def _enable_shield(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARKET_SHIELD_ENABLED", "true")
    app_config.get_settings.cache_clear()


def _bullish_ohlc(*, ltp: float = 105.0) -> dict[str, Any]:
    """OHLC that passes all 4 bullish sub-checks comfortably."""
    return {
        "ltp": ltp,
        "open": 100.0,
        "high": ltp,
        "low": 99.0,
        "prev_close": 99.5,
    }


def _bearish_ohlc() -> dict[str, Any]:
    """OHLC where every bullish sub-check fails."""
    return {
        "ltp": 95.0,
        "open": 100.0,
        "high": 100.5,
        "low": 94.5,
        "prev_close": 100.0,
    }


async def _populate_breadth(
    bullish_count: int = 4, *, ttl: int = 60
) -> None:
    """Write OHLC for the requested number of bullish indices, the
    rest bearish. All 4 indices always present (so cold_start=False)."""
    for i, key in enumerate(svc.INDEX_KEYS):
        ohlc = _bullish_ohlc() if i < bullish_count else _bearish_ohlc()
        await svc._set_index_ohlc_for_test(key, ohlc, ttl_seconds=ttl)


def _make_position(
    *,
    side: str = "buy",
    avg_entry_price: float = 100.0,
    remaining_quantity: int = 375,
    current_atr: float = 1.0,
) -> SimpleNamespace:
    """Position stand-in. ``get_open_position`` is mocked to return this."""
    return SimpleNamespace(
        side=side,
        avg_entry_price=Decimal(str(avg_entry_price)),
        remaining_quantity=remaining_quantity,
        current_atr=Decimal(str(current_atr)),
    )


def _make_signal(
    *,
    side: str = "long",
    price: float = 100.0,
    atr: float = 1.0,
    symbol: str = "BSELTD",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        symbol=symbol,
        raw_payload={
            "side": side,
            "price": price,
            "indicators": {"ATR": atr},
        },
    )


# ═══════════════════════════════════════════════════════════════════════
# Default OFF
# ═══════════════════════════════════════════════════════════════════════


class TestDefaultOff:
    async def test_is_enabled_false_by_default(self) -> None:
        assert svc.is_enabled() is False

    async def test_has_active_hold_false_when_disabled(self) -> None:
        assert await svc.has_active_hold(uuid4()) is False

    async def test_try_release_noop_when_disabled(
        self, _patch_redis: fake_aioredis.FakeRedis
    ) -> None:
        # Even with a record in Redis, disabled = no release.
        sid = uuid4()
        await _patch_redis.set(svc._hold_key(sid), '{"signal_id":"abc"}')
        result = await svc.try_release(strategy_id=sid, current_price=100.0)
        assert result.released is False

    async def test_maybe_hold_returns_disabled(self) -> None:
        session = AsyncMock()
        sig = _make_signal()
        decision = await svc.maybe_hold_exit(
            session, strategy_id=uuid4(), signal=sig,
        )
        assert decision.held is False
        assert decision.reason == "disabled"


# ═══════════════════════════════════════════════════════════════════════
# Per-index bullish classification
# ═══════════════════════════════════════════════════════════════════════


class TestIndexClassification:
    def test_all_four_checks_pass_marks_bullish(self) -> None:
        result = svc._evaluate_index("NIFTY50", _bullish_ohlc())
        assert result.is_bullish is True

    def test_all_four_checks_fail_marks_bearish(self) -> None:
        result = svc._evaluate_index("NIFTY50", _bearish_ohlc())
        assert result.is_bullish is False

    def test_three_of_four_passes(self) -> None:
        # Pass: VWAP, above-open, upper-60%. Fail: above-prev_close
        # (gap-down day that recovers intraday).
        ohlc = {
            "ltp": 104.0,
            "open": 100.0,        # 104 > 100  → pass above-open
            "high": 105.0,
            "low": 99.0,           # range 6; (104-99)/6=0.83 ≥ 0.40 → pass range
            "prev_close": 110.0,   # 104 < 110 → fail above-prev
        }
        # vwap = (105+99+104)/3 = 102.67; ltp 104 > vwap → pass
        result = svc._evaluate_index("NIFTY50", ohlc)
        assert result.is_bullish is True

    def test_two_of_four_fails(self) -> None:
        # LTP > prev_close + > VWAP only. Below open + bottom of range.
        ohlc = {
            "ltp": 99.5,
            "open": 100.0,        # 99.5 < 100 → fail above-open
            "high": 100.0,
            "low": 99.0,           # range 1; (99.5-99)/1 = 0.5 → pass range (>=0.4)
            "prev_close": 99.0,    # 99.5 > 99 → pass above-prev
        }
        # vwap = (100+99+99.5)/3 = 99.5; ltp=99.5 NOT > vwap → fail
        result = svc._evaluate_index("NIFTY50", ohlc)
        assert result.is_bullish is False

    def test_missing_ohlc_returns_error(self) -> None:
        result = svc._evaluate_index("NIFTY50", {"ltp": 0, "open": 0})
        assert result.is_bullish is False
        assert result.error == "missing_ohlc"


# ═══════════════════════════════════════════════════════════════════════
# Breadth — Redis cold-start vs populated
# ═══════════════════════════════════════════════════════════════════════


class TestBreadth:
    async def test_cold_start_when_redis_empty(self) -> None:
        result = await svc.evaluate_breadth()
        assert result.cold_start is True
        assert result.shield_active is False
        assert result.bullish_count == 0

    async def test_cold_start_when_one_index_missing(self) -> None:
        # Populate 3 of 4 indices, leave BSE_MIDCAP empty.
        for key in svc.INDEX_KEYS[:3]:
            await svc._set_index_ohlc_for_test(key, _bullish_ohlc())
        result = await svc.evaluate_breadth()
        assert result.cold_start is True
        assert result.shield_active is False

    async def test_active_when_all_four_bullish(self) -> None:
        await _populate_breadth(bullish_count=4)
        result = await svc.evaluate_breadth()
        assert result.cold_start is False
        assert result.bullish_count == 4
        assert result.shield_active is True

    async def test_active_when_three_of_four_bullish(self) -> None:
        await _populate_breadth(bullish_count=3)
        result = await svc.evaluate_breadth()
        assert result.cold_start is False
        assert result.bullish_count == 3
        assert result.shield_active is True

    async def test_inactive_when_two_of_four_bullish(self) -> None:
        await _populate_breadth(bullish_count=2)
        result = await svc.evaluate_breadth()
        assert result.cold_start is False
        assert result.bullish_count == 2
        assert result.shield_active is False


# ═══════════════════════════════════════════════════════════════════════
# maybe_hold_exit — decision matrix
# ═══════════════════════════════════════════════════════════════════════


class TestMaybeHoldExit:
    async def test_holds_when_breadth_strong_and_no_active_fall(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_shield(monkeypatch)
        await _populate_breadth(bullish_count=4)

        sid = uuid4()
        sig = _make_signal(side="long", price=100.5, atr=1.0)
        position = _make_position(side="buy", avg_entry_price=100.0)

        with patch(
            "app.services.direct_exit.get_open_position",
            AsyncMock(return_value=position),
        ):
            decision = await svc.maybe_hold_exit(
                AsyncMock(), strategy_id=sid, signal=sig,
            )

        assert decision.held is True
        assert decision.release_at_iso is not None
        # Redis record should now exist.
        assert await svc.has_active_hold(sid) is True

    async def test_no_hold_on_cold_start(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_shield(monkeypatch)
        # Redis empty → cold start
        sig = _make_signal(side="long", price=100.5, atr=1.0)
        position = _make_position(side="buy", avg_entry_price=100.0)

        with patch(
            "app.services.direct_exit.get_open_position",
            AsyncMock(return_value=position),
        ):
            decision = await svc.maybe_hold_exit(
                AsyncMock(), strategy_id=uuid4(), signal=sig,
            )

        assert decision.held is False
        assert decision.reason == "cold_start_index_data"

    async def test_no_hold_on_weak_breadth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_shield(monkeypatch)
        await _populate_breadth(bullish_count=2)
        sig = _make_signal(side="long", price=100.5, atr=1.0)
        position = _make_position(side="buy", avg_entry_price=100.0)

        with patch(
            "app.services.direct_exit.get_open_position",
            AsyncMock(return_value=position),
        ):
            decision = await svc.maybe_hold_exit(
                AsyncMock(), strategy_id=uuid4(), signal=sig,
            )

        assert decision.held is False
        assert "breadth_weak" in decision.reason

    async def test_no_hold_when_already_falling(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LONG position down 1.2×ATR — let exit through, don't hold."""
        _enable_shield(monkeypatch)
        await _populate_breadth(bullish_count=4)
        sig = _make_signal(side="long", price=98.8, atr=1.0)  # 1.2 ATR drop
        position = _make_position(side="buy", avg_entry_price=100.0)

        with patch(
            "app.services.direct_exit.get_open_position",
            AsyncMock(return_value=position),
        ):
            decision = await svc.maybe_hold_exit(
                AsyncMock(), strategy_id=uuid4(), signal=sig,
            )

        assert decision.held is False
        assert "atr_override_at_hold" in decision.reason

    async def test_no_hold_when_no_open_position(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_shield(monkeypatch)
        await _populate_breadth(bullish_count=4)
        sig = _make_signal(side="long", price=100.5, atr=1.0)

        with patch(
            "app.services.direct_exit.get_open_position",
            AsyncMock(return_value=None),
        ):
            decision = await svc.maybe_hold_exit(
                AsyncMock(), strategy_id=uuid4(), signal=sig,
            )

        assert decision.held is False
        assert decision.reason == "no_open_position"

    async def test_no_hold_when_atr_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_shield(monkeypatch)
        await _populate_breadth(bullish_count=4)
        sig = _make_signal(side="long", price=100.5, atr=0.0)
        position = _make_position(side="buy", current_atr=0.0)

        with patch(
            "app.services.direct_exit.get_open_position",
            AsyncMock(return_value=position),
        ):
            decision = await svc.maybe_hold_exit(
                AsyncMock(), strategy_id=uuid4(), signal=sig,
            )

        assert decision.held is False
        assert decision.reason == "insufficient_data_at_hold"


# ═══════════════════════════════════════════════════════════════════════
# try_release — release matrix
# ═══════════════════════════════════════════════════════════════════════


class TestTryRelease:
    async def test_no_release_when_no_record(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_shield(monkeypatch)
        result = await svc.try_release(
            strategy_id=uuid4(), current_price=100.0,
        )
        assert result.released is False

    async def test_no_release_before_timeout_or_atr(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Hold just placed, price unchanged → keep holding."""
        _enable_shield(monkeypatch)
        await _populate_breadth(bullish_count=4)
        sid = uuid4()
        sig = _make_signal(side="long", price=100.5, atr=1.0)
        position = _make_position(side="buy", avg_entry_price=100.0)

        with patch(
            "app.services.direct_exit.get_open_position",
            AsyncMock(return_value=position),
        ):
            await svc.maybe_hold_exit(
                AsyncMock(), strategy_id=sid, signal=sig,
            )

        result = await svc.try_release(strategy_id=sid, current_price=100.5)
        assert result.released is False
        assert await svc.has_active_hold(sid) is True

    async def test_release_on_atr_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Long held @ entry=100, atr=1.0. Price drops to 98.8 → 1.2 ATR
        loss → release with reason='atr_override'."""
        _enable_shield(monkeypatch)
        await _populate_breadth(bullish_count=4)
        sid = uuid4()
        sig = _make_signal(side="long", price=100.5, atr=1.0)
        position = _make_position(side="buy", avg_entry_price=100.0)

        with patch(
            "app.services.direct_exit.get_open_position",
            AsyncMock(return_value=position),
        ):
            await svc.maybe_hold_exit(
                AsyncMock(), strategy_id=sid, signal=sig,
            )

        # Now LTP drops 1.2 ATR below entry.
        result = await svc.try_release(strategy_id=sid, current_price=98.8)
        assert result.released is True
        assert result.reason == "atr_override"
        assert result.signal_id == str(sig.id)
        # Hold record should be consumed.
        assert await svc.has_active_hold(sid) is False

    async def test_release_on_timeout(
        self,
        monkeypatch: pytest.MonkeyPatch,
        _patch_redis: fake_aioredis.FakeRedis,
    ) -> None:
        """Manually plant an expired hold (release_at_iso in the past)."""
        _enable_shield(monkeypatch)
        sid = uuid4()
        held_at = datetime.now(UTC) - timedelta(minutes=45)
        release_at = held_at + timedelta(minutes=30)  # 15 min ago
        record = {
            "signal_id": str(uuid4()),
            "strategy_id": str(sid),
            "side": "long",
            "symbol": "BSELTD",
            "entry_price": 100.0,
            "atr_at_hold": 1.0,
            "held_at_iso": held_at.isoformat(),
            "release_at_iso": release_at.isoformat(),
            "breadth_bullish_count": 4,
            "reason_at_hold": "test",
        }
        await redis_client.cache_set_json(
            svc._hold_key(sid), record, ttl_seconds=60,
        )

        result = await svc.try_release(strategy_id=sid, current_price=100.0)
        assert result.released is True
        assert result.reason == "timeout"
        assert await svc.has_active_hold(sid) is False

    async def test_short_side_atr_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """For SHORT, adverse move = price RISES above entry."""
        _enable_shield(monkeypatch)
        await _populate_breadth(bullish_count=4)
        sid = uuid4()
        sig = _make_signal(side="short", price=99.5, atr=1.0)
        position = _make_position(side="sell", avg_entry_price=100.0)

        with patch(
            "app.services.direct_exit.get_open_position",
            AsyncMock(return_value=position),
        ):
            await svc.maybe_hold_exit(
                AsyncMock(), strategy_id=sid, signal=sig,
            )

        # Price rises 1.2 ATR above entry (adverse for SHORT).
        result = await svc.try_release(strategy_id=sid, current_price=101.2)
        assert result.released is True
        assert result.reason == "atr_override"


# ═══════════════════════════════════════════════════════════════════════
# Prior-hold collision
# ═══════════════════════════════════════════════════════════════════════


class TestPriorHoldCollision:
    async def test_has_active_hold_after_hold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_shield(monkeypatch)
        await _populate_breadth(bullish_count=4)
        sid = uuid4()
        sig = _make_signal(side="long", price=100.5, atr=1.0)
        position = _make_position(side="buy", avg_entry_price=100.0)

        assert await svc.has_active_hold(sid) is False

        with patch(
            "app.services.direct_exit.get_open_position",
            AsyncMock(return_value=position),
        ):
            await svc.maybe_hold_exit(
                AsyncMock(), strategy_id=sid, signal=sig,
            )

        assert await svc.has_active_hold(sid) is True
