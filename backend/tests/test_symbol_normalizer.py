"""Tests for the D1 symbol normalizer (stable underlying → Dhan contract).

Pine now sends a stable underlying ("BSE") + instrument_type +
expiry_preference; the normalizer resolves it to the current/next-month
Dhan futures contract via the (public) scrip master, with automatic expiry
rollover. Legacy full-contract symbols pass through unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.brokers.dhan import ScripMeta, _ScripMaster
from app.core.exceptions import BrokerInvalidSymbolError
from app.schemas.broker import Exchange
from app.services import symbol_normalizer
from app.services.pine_mapper import PineMapperError, resolve_normalized_symbol

pytestmark = pytest.mark.asyncio


def _fut(symbol: str, secid: str, expiry, lot: int = 375) -> ScripMeta:
    return ScripMeta(
        security_id=secid,
        symbol=symbol,
        segment="NSE_FNO",
        instrument="FUTSTK",
        lot_size=lot,
        option_type=None,
        strike_price=None,
        expiry_date=expiry,
    )


def _loaded_scrip(*metas: ScripMeta) -> _ScripMaster:
    sm = _ScripMaster()
    for m in metas:
        sm._meta[m.security_id] = m
    sm._loaded_at = datetime.now(UTC)  # mark loaded → _ensure_scrip_loaded no-ops
    return sm


@pytest.fixture
def inject_scrip(monkeypatch: pytest.MonkeyPatch):
    def _inject(*metas: ScripMeta) -> _ScripMaster:
        sm = _loaded_scrip(*metas)
        monkeypatch.setattr(symbol_normalizer, "_scrip", sm)
        return sm

    return _inject


class TestResolveFutures:
    async def test_current_month(self, inject_scrip) -> None:
        today = datetime.now(UTC).date()
        inject_scrip(
            _fut("BSE-MAY2026-FUT", "66109", today + timedelta(days=4)),
            _fut("BSE-JUN2026-FUT", "66110", today + timedelta(days=34)),
        )
        r = await symbol_normalizer.resolve_futures_symbol("BSE", "current_month", Exchange.NFO)
        assert r["dhan_symbol"] == "BSE-MAY2026-FUT"
        assert r["security_id"] == "66109"
        assert r["lot_size"] == 375

    async def test_next_month(self, inject_scrip) -> None:
        today = datetime.now(UTC).date()
        inject_scrip(
            _fut("BSE-MAY2026-FUT", "66109", today + timedelta(days=4)),
            _fut("BSE-JUN2026-FUT", "66110", today + timedelta(days=34)),
        )
        r = await symbol_normalizer.resolve_futures_symbol("BSE", "next_month", Exchange.NFO)
        assert r["dhan_symbol"] == "BSE-JUN2026-FUT"
        assert r["security_id"] == "66110"

    async def test_expired_current_rolls_to_next(self, inject_scrip) -> None:
        today = datetime.now(UTC).date()
        inject_scrip(
            _fut("BSE-APR2026-FUT", "66108", today - timedelta(days=2)),  # expired
            _fut("BSE-MAY2026-FUT", "66109", today + timedelta(days=4)),  # live
        )
        r = await symbol_normalizer.resolve_futures_symbol("BSE", "current_month", Exchange.NFO)
        assert r["dhan_symbol"] == "BSE-MAY2026-FUT"  # rolled past expired APR

    async def test_unknown_underlying_raises(self, inject_scrip) -> None:
        today = datetime.now(UTC).date()
        inject_scrip(_fut("BSE-MAY2026-FUT", "66109", today + timedelta(days=4)))
        with pytest.raises(BrokerInvalidSymbolError, match="No live futures contract"):
            await symbol_normalizer.resolve_futures_symbol(
                "RELIANCE", "current_month", Exchange.NFO
            )

    async def test_options_not_implemented(self, inject_scrip) -> None:
        inject_scrip()
        with pytest.raises(NotImplementedError, match="Phase 3"):
            await symbol_normalizer.resolve_symbol("BSE", "options", "current_month", Exchange.NFO)


class TestPineMapperHook:
    async def test_full_contract_passthrough(self) -> None:
        # No instrument_type/expiry_preference → symbol returned unchanged.
        out = await resolve_normalized_symbol({"symbol": "BSE-MAY2026-FUT"})
        assert out == "BSE-MAY2026-FUT"

    async def test_short_form_resolves(self, inject_scrip) -> None:
        today = datetime.now(UTC).date()
        inject_scrip(_fut("BSE-MAY2026-FUT", "66109", today + timedelta(days=4)))
        out = await resolve_normalized_symbol(
            {
                "symbol": "BSE",
                "instrument_type": "futures",
                "expiry_preference": "current_month",
                "exchange": "NFO",
            }
        )
        assert out == "BSE-MAY2026-FUT"

    async def test_options_short_form_raises_pinemappererror(self, inject_scrip) -> None:
        inject_scrip()
        with pytest.raises(PineMapperError):
            await resolve_normalized_symbol(
                {
                    "symbol": "BSE",
                    "instrument_type": "options",
                    "expiry_preference": "current_month",
                }
            )


class TestScripMasterFuturesParse:
    def test_futures_expiry_now_parsed(self) -> None:
        """The additive parser change: FUT rows now carry expiry_date
        (was None pre-fix)."""
        csv_text = (
            "SEM_SMST_SECURITY_ID,SEM_TRADING_SYMBOL,SEM_INSTRUMENT_NAME,"
            "SEM_EXM_EXCH_ID,SEM_SEGMENT,SEM_LOT_UNITS,SEM_OPTION_TYPE,"
            "SEM_STRIKE_PRICE,SEM_EXPIRY_DATE\n"
            "66109,BSE-MAY2026-FUT,FUTSTK,NSE,D,375.0,,0,2026-05-28\n"
        )
        sm = _ScripMaster()
        sm.load_from_text(csv_text)
        meta = sm.meta("66109")
        assert meta is not None
        assert meta.expiry_date is not None
        assert meta.instrument == "FUTSTK"
        found = sm.futures_for_underlying("BSE", "NSE_FNO")
        assert len(found) == 1
        assert found[0].symbol == "BSE-MAY2026-FUT"


class TestCache:
    async def test_cache_hit_no_download(self, monkeypatch: pytest.MonkeyPatch) -> None:
        today = datetime.now(UTC).date()
        sm = _loaded_scrip(_fut("BSE-MAY2026-FUT", "66109", today + timedelta(days=4)))
        monkeypatch.setattr(symbol_normalizer, "_scrip", sm)

        def _boom(*a, **k):
            raise AssertionError("must not download when cache is warm")

        monkeypatch.setattr("httpx.AsyncClient", _boom)
        r = await symbol_normalizer.resolve_futures_symbol("BSE", "current_month")
        assert r["security_id"] == "66109"

    def test_ttl_expiry(self) -> None:
        sm = _ScripMaster()
        sm._loaded_at = datetime.now(UTC) - timedelta(hours=25)
        assert sm.is_loaded() is False
        sm._loaded_at = datetime.now(UTC)
        assert sm.is_loaded() is True
