"""Date-driven continuous-future resolver for the Dhan execution path.

TradingView publishes cash-equity tickers (e.g. ``NSE:BSE``) and a
continuous-future notation (``BSE1!``). Dhan's order API only accepts the
**month-stamped** contract symbol — e.g. ``BSE-MAY2026-FUT`` — and that
symbol changes every month at the NSE F&O monthly expiry (the exchange's
published expiry day; 14:30 IST settlement).

This module owns one job: given a TradingView-style ticker, return the
Dhan trading symbol of the **entry vehicle** for that underlying —
auto-rolling without manual intervention, and rolling ENTRIES to the
next month N days *before* expiry (EXPIRY_ROLLOVER_SPEC.md, N=5).

THE GOVERNING SENTENCE (EXPIRY_ROLLOVER_SPEC.md): the N-rule governs
ENTRY SELECTION ONLY. Exits and partials always follow the position they
belong to — the stored ``open_position.symbol``, pinned downstream in
``position_lookup`` / ``strategy_webhook`` — on both sides of every
switch, forever. This resolver is only reached for entry-class symbols.

Algorithm
---------
1. Look up the TV form in :data:`_TV_ROOT_TO_DHAN_ROOT` to get the Dhan
   underlying root (e.g. ``BSE``). Unknown forms pass through unchanged —
   except an explicit canonical contract (``<ROOT>-<MMM><YYYY>-FUT``)
   whose own expiry is already past, which is re-resolved through the
   same entry policy instead of being sent to Dhan as a dead contract.
2. UNIVERSE: enumerate ``<ROOT>-<MMM><YYYY>-FUT`` rows from the
   in-memory :data:`app.brokers.dhan._SCRIP_MASTER` cache
   (:func:`_contracts_for_root`) — no hardcoded calendar.
3. Read each contract's real expiry from the scrip master
   (``SEM_EXPIRY_DATE`` via :meth:`_ScripMaster.expiry_for`); fall back to
   a computed last-Thursday only if the master omits it.
4. SELECTION POLICY (:func:`_entry_vehicle_policy`): earliest contract
   with ``(expiry - today).days > N`` — EXCLUSIVE boundary, CALENDAR
   days, date subtraction, never sessions. N=5: for an expiry on
   Tue 25 Aug the last front-month entry day is 19 Aug (T-6); entries
   from 20 Aug (T-5) get the next month. If NO contract satisfies N the
   policy returns None and the resolver passes the symbol through —
   Dhan rejects loudly. Falling back to the dying front month is
   explicitly forbidden (spec amendment, 9 Aug 2026).
5. SETTLEMENT GUARD (:func:`_past_settlement`, separate from the
   policy): never serve a contract at/past its own 14:30 IST
   settlement. With N=5 the policy alone can never pick one; the guard
   protects against N-misconfiguration and is asserted independently.
6. Sanity-bound: never resolve to a contract whose expiry is more than
   60 days out — guards against future bugs in date arithmetic.
7. Cache per ``(root, today_iso)``; natural daily turnover. The result
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
import re
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

#: N — the entry-roll boundary in CALENDAR days, EXCLUSIVE (spec:
#: EXPIRY_ROLLOVER_SPEC.md). New entries require ``(expiry - today).days
#: > _ENTRY_ROLL_DAYS``; anything at or inside the boundary is redirected
#: to the next month. Chosen to retro-cover all 41 historical straddles
#: (any N>=3 does) and to keep new entries clear of the delivery-margin
#: ramp (E-4 10% -> expiry 100%). The pending SEP depth reading can tune
#: this constant (5 vs 3); it cannot invalidate the structure.
_ENTRY_ROLL_DAYS: Final = 5

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
    "NSE:ANGELONE": "ANGELONE",
    "ANGELONE:NSE": "ANGELONE",
    "ANGELONE": "ANGELONE",
    "ANGELONE1!": "ANGELONE",
}

#: Canonical month-stamped FUT pattern (e.g. ``BSE-MAY2026-FUT``); group 1
#: captures the underlying root. Used to roll an explicitly-named contract
#: that has already expired through the entry policy (inherits N).
_CANONICAL_FUT_RE: Final = re.compile(r"^([A-Z][A-Z0-9]*)-[A-Z]{3}\d{4}-FUT$")

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


def _contracts_for_root(root: str) -> list[tuple[str, date]]:
    """CONTRACT UNIVERSE for one underlying — every listed FUT + expiry.

    Pure enumeration, no selection. Selection is a POLICY over this
    universe (:func:`_entry_vehicle_policy` today; an options vehicle
    policy plugs the same seam later — EXPIRY_ROLLOVER_SPEC structural
    hold).
    """
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


def _entry_vehicle_policy(
    contracts: list[tuple[str, date]],
    now_ist: datetime,
    *,
    min_days_to_expiry: int = _ENTRY_ROLL_DAYS,
) -> tuple[str, date] | None:
    """SELECTION POLICY for new entries: the N-rule over the universe.

    Earliest contract with ``(expiry - today).days > min_days_to_expiry``
    — EXCLUSIVE boundary, CALENDAR days, plain date subtraction (never
    sessions: expiry is a calendar date). Returns ``None`` when nothing
    qualifies; the caller passes the symbol through so Dhan rejects
    loudly. NEVER falls back to the dying front month — that is the
    failure this rule exists to prevent (spec amendment, 9 Aug 2026).
    """
    today = now_ist.date()
    for sym, expiry in sorted(contracts, key=lambda c: c[1]):
        if (expiry - today).days > min_days_to_expiry:
            return (sym, expiry)
    return None


def _past_settlement(expiry: date, now_ist: datetime) -> bool:
    """SETTLEMENT GUARD, separate from the policy: contract already dead?

    True once ``now`` is past the contract's own settlement (expiry date
    before today, or expiry today at/after 14:30 IST). The policy can
    never pick such a contract while N > 0; this guard is asserted
    independently so an N-misconfiguration still cannot serve a dying
    contract (EXPIRY_ROLLOVER_SPEC: the same-day/14:30 rule remains a
    SEPARATE, separately-asserted guard).
    """
    today = now_ist.date()
    return expiry < today or (
        expiry == today and now_ist.time() >= _EXPIRY_CLOSE
    )


async def _ensure_scrip_master_loaded() -> None:
    if _SCRIP_MASTER.is_loaded():
        return
    async with _SCRIP_LOAD_LOCK:
        if _SCRIP_MASTER.is_loaded():
            return
        scrip_url = get_settings().dhan_scrip_master_url
        async with httpx.AsyncClient() as http:
            await _SCRIP_MASTER.ensure_loaded(http, scrip_url)


async def _expired_canonical_root(symbol_upper: str, now: datetime) -> str | None:
    """Root to re-resolve when an explicit canonical FUT has expired.

    Returns the underlying root iff ``symbol_upper`` is a canonical
    month-stamped contract (``<ROOT>-<MMM><YYYY>-FUT``) whose OWN expiry
    — per the scrip master's real ``SEM_EXPIRY_DATE`` — is already past,
    so a stale explicit contract re-resolves through the entry policy
    (inheriting the N-rule) instead of being rejected by Dhan. Live/future contracts, symbols the
    master doesn't know, and non-FUT inputs return ``None`` (pass through
    unchanged), preserving deliberate selection of a still-valid contract.
    """
    match = _CANONICAL_FUT_RE.match(symbol_upper)
    if match is None:
        return None
    root = match.group(1)
    try:
        await _ensure_scrip_master_loaded()
    except Exception as exc:  # noqa: BLE001
        _logger.error(
            "futures_resolver.scrip_master_load_failed",
            original=symbol_upper, error=str(exc),
        )
        return None
    own_expiry = _SCRIP_MASTER.expiry_for(symbol_upper, "NSE_FNO")
    if own_expiry is None:
        return None
    expired = own_expiry < now.date() or (
        own_expiry == now.date() and now.time() >= _EXPIRY_CLOSE
    )
    if not expired:
        return None
    _logger.info(
        "futures_resolver.expired_canonical_rollforward",
        original=symbol_upper, root=root, own_expiry=own_expiry.isoformat(),
    )
    return root


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
    now = now_ist or datetime.now(_IST)
    root = _TV_ROOT_TO_DHAN_ROOT.get(upper)
    if root is None:
        # Not a known TradingView form. If it's an explicit canonical
        # contract that has already expired, re-resolve its underlying
        # through the entry policy; otherwise pass through unchanged.
        root = await _expired_canonical_root(upper, now)
        if root is None:
            return symbol

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

    contracts = _contracts_for_root(root)
    if not contracts:
        _logger.error(
            "futures_resolver.no_contracts_found",
            original=symbol, root=root,
        )
        return symbol

    picked = _entry_vehicle_policy(contracts, now)
    if picked is None:
        # Spec amendment (9 Aug 2026): no contract satisfies N → pass
        # through and let Dhan reject loudly. Never the dying front.
        _logger.error(
            "futures_resolver.no_contract_satisfies_entry_roll",
            original=symbol, root=root,
            min_days_to_expiry=_ENTRY_ROLL_DAYS,
            candidates=[c[0] for c in contracts],
        )
        return symbol

    resolved_sym, expiry = picked
    if _past_settlement(expiry, now):
        # Unreachable while N > 0 — this is the independent guard against
        # N-misconfiguration ever serving a settled contract.
        _logger.error(
            "futures_resolver.settled_contract_blocked",
            original=symbol, root=root, resolved=resolved_sym,
            expiry=expiry.isoformat(),
            min_days_to_expiry=_ENTRY_ROLL_DAYS,
        )
        return symbol
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
