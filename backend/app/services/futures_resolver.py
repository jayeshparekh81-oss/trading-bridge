"""Date-driven continuous-future resolver for the Dhan execution path.

TradingView publishes cash-equity tickers (e.g. ``NSE:BSE``) and a
continuous-future notation (``BSE1!``). Dhan's order API only accepts the
**month-stamped** contract symbol — e.g. ``BSE-MAY2026-FUT`` — and that
symbol changes every month at the NSE F&O monthly expiry (the exchange's
published expiry day; 14:30 IST settlement).

This module owns one job: given a TradingView-style ticker, return the
Dhan trading symbol of the **active monthly futures contract** for that
underlying, auto-rolling without manual intervention.

Algorithm
---------
1. Look up the TV form in :data:`_TV_ROOT_TO_DHAN_ROOT` to get the Dhan
   underlying root (e.g. ``BSE``). Unknown forms pass through unchanged.
2. Enumerate ``<ROOT>-<MMM><YYYY>-FUT`` rows from the in-memory
   :data:`app.brokers.dhan._SCRIP_MASTER` cache — no hardcoded calendar.
3. Read each contract's real expiry from the scrip master
   (``SEM_EXPIRY_DATE`` via :meth:`_ScripMaster.expiry_for`); fall back to
   a computed last-Thursday only if the master omits it.
4. Pick the earliest contract whose expiry is either in the future, or
   today AND ``now`` is before 14:30 IST (intraday on expiry day is
   allowed; after 14:30 the contract has settled and the next month
   takes over).
5. Sanity-bound: never resolve to a contract whose expiry is more than
   60 days out — guards against future bugs in date arithmetic.
6. Cache per ``(root, today_iso)``; natural daily turnover. The result
   is stable for a whole trading day and only flips on the rollover
   boundary.

Expiry source
-------------
Expiry comes from the exchange's published ``SEM_EXPIRY_DATE`` in the
scrip master, so SEBI's expiry-day changes (monthly stock F&O moved to the
last Tuesday) and holiday-induced shifts are tracked automatically — no
hardcoded calendar. The last-Thursday computation survives only as a
defensive fallback for CSV variants that omit the expiry column.

Safety
------
Every failure mode returns the original symbol unchanged. DhanAdapter
then raises a clean :class:`BrokerInvalidSymbolError` downstream rather
than us guessing. Logs at INFO on every resolution and ERROR on every
fallback so a missed roll-forward is loud, not silent.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta
from typing import Final
from zoneinfo import ZoneInfo

import httpx

from app.brokers.dhan import _SCRIP_MASTER
from app.core.config import get_settings
from app.core.logging import get_logger

_logger = get_logger("services.futures_resolver")

_IST: Final = ZoneInfo("Asia/Kolkata")

#: After this IST time on expiry day, the contract has settled — roll
#: forward. Dhan's SEM_EXPIRY_DATE stamps monthly F&O settlement at 14:30
#: IST, so the roll boundary tracks that, not the equity session close.
_EXPIRY_CLOSE: Final = time(14, 30)

#: Hard sanity bound: any resolved contract more than this far out is rejected.
_MAX_DAYS_OUT: Final = 60

_MONTHS: Final[dict[str, int]] = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

#: TradingView ticker forms → Dhan underlying root. Extend here when a
#: new continuous-future symbol needs to flow through this resolver.
_TV_ROOT_TO_DHAN_ROOT: Final[dict[str, str]] = {
    "NSE:BSE": "BSE",
    "BSE:NSE": "BSE",
    "BSE": "BSE",
    "BSE1!": "BSE",
    "NSE:CDSL": "CDSL",
    "CDSL:NSE": "CDSL",
    "CDSL": "CDSL",
    "CDSL1!": "CDSL",
}

#: Per-day cache: (root, today_iso) → resolved Dhan symbol.
_RESOLUTION_CACHE: dict[tuple[str, str], str] = {}
_CACHE_LOCK: asyncio.Lock = asyncio.Lock()
_SCRIP_LOAD_LOCK: asyncio.Lock = asyncio.Lock()


def _last_thursday_of_month(yyyymm: str) -> date:
    month_str = yyyymm[:3].upper()
    year_str = yyyymm[3:]
    if month_str not in _MONTHS or not year_str.isdigit():
        raise ValueError(f"bad month/year token {yyyymm!r}")
    month = _MONTHS[month_str]
    year = int(year_str)
    first_of_next = (
        date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    )
    last_day = first_of_next - timedelta(days=1)
    # weekday(): Mon=0 ... Thu=3
    offset = (last_day.weekday() - 3) % 7
    return last_day - timedelta(days=offset)


def _list_fut_contracts(root: str) -> list[tuple[str, date]]:
    out: list[tuple[str, date]] = []
    prefix = f"{root}-"
    suffix = "-FUT"
    for sym, seg in _SCRIP_MASTER._by_symbol:
        if seg != "NSE_FNO":
            continue
        if not (sym.startswith(prefix) and sym.endswith(suffix)):
            continue
        # Prefer the exchange's published expiry from the scrip master —
        # auto-tracks SEBI's last-Tuesday shift AND holiday-induced moves.
        # Fall back to the computed last-Thursday only for CSV variants
        # lacking SEM_EXPIRY_DATE (also keeps the legacy unit tests green).
        expiry = _SCRIP_MASTER.expiry_for(sym, seg)
        if expiry is None:
            middle = sym[len(prefix) : -len(suffix)]
            try:
                expiry = _last_thursday_of_month(middle)
            except ValueError:
                continue
        out.append((sym, expiry))
    return out


def _pick_active_contract(
    contracts: list[tuple[str, date]], now_ist: datetime
) -> tuple[str, date] | None:
    today = now_ist.date()
    for sym, expiry in sorted(contracts, key=lambda c: c[1]):
        if expiry > today:
            return (sym, expiry)
        if expiry == today and now_ist.time() < _EXPIRY_CLOSE:
            return (sym, expiry)
    return None


async def _ensure_scrip_master_loaded() -> None:
    if _SCRIP_MASTER.is_loaded():
        return
    async with _SCRIP_LOAD_LOCK:
        if _SCRIP_MASTER.is_loaded():
            return
        scrip_url = get_settings().dhan_scrip_master_url
        async with httpx.AsyncClient() as http:
            await _SCRIP_MASTER.ensure_loaded(http, scrip_url)


async def resolve_or_passthrough(
    symbol: str, *, now_ist: datetime | None = None
) -> str:
    """Return the active futures trading symbol, or ``symbol`` unchanged.

    The function never raises. On any failure it logs ERROR and returns
    the input so DhanAdapter surfaces a clean BrokerInvalidSymbolError.
    """
    if not isinstance(symbol, str) or not symbol.strip():
        return symbol
    upper = symbol.strip().upper()
    root = _TV_ROOT_TO_DHAN_ROOT.get(upper)
    if root is None:
        return symbol

    now = now_ist or datetime.now(_IST)
    cache_key = (root, now.date().isoformat())
    cached = _RESOLUTION_CACHE.get(cache_key)
    if cached:
        _logger.info(
            "futures_resolver.cache_hit",
            original=symbol, resolved=cached, root=root,
        )
        return cached

    try:
        await _ensure_scrip_master_loaded()
    except Exception as exc:  # noqa: BLE001
        _logger.error(
            "futures_resolver.scrip_master_load_failed",
            original=symbol, root=root, error=str(exc),
        )
        return symbol

    contracts = _list_fut_contracts(root)
    if not contracts:
        _logger.error(
            "futures_resolver.no_contracts_found",
            original=symbol, root=root,
        )
        return symbol

    picked = _pick_active_contract(contracts, now)
    if picked is None:
        _logger.error(
            "futures_resolver.no_active_contract",
            original=symbol, root=root,
            candidates=[c[0] for c in contracts],
        )
        return symbol

    resolved_sym, expiry = picked
    days_to_expiry = (expiry - now.date()).days
    if days_to_expiry > _MAX_DAYS_OUT:
        _logger.warning(
            "futures_resolver.expiry_out_of_bounds",
            original=symbol, root=root, resolved=resolved_sym,
            expiry=expiry.isoformat(), days_to_expiry=days_to_expiry,
            max_days_out=_MAX_DAYS_OUT,
        )
        return symbol

    async with _CACHE_LOCK:
        _RESOLUTION_CACHE[cache_key] = resolved_sym

    _logger.info(
        "futures_resolver.continuous_future_resolved",
        original=symbol, base=root, resolved=resolved_sym,
        expiry=expiry.isoformat(), days_to_expiry=days_to_expiry,
        picked_from=len(contracts),
    )
    return resolved_sym


__all__ = ["resolve_or_passthrough"]
