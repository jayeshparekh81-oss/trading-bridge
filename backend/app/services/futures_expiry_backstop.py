"""Futures T-2 expiry backstop — EXPIRY_ROLLOVER_SPEC.md row 13. NEW · flag-gated.

THE GAP THIS CLOSES. The N=5 entry policy (``futures_resolver._entry_vehicle_policy``)
stops a NEW position opening into a dying contract. It says nothing about a position
already open. The unobserved tail is an entry at <= T-6 held >= 6 calendar days: the
entry was legal, no rollover applies to it, and the contract expires underneath it.
Backtested over 6.5 years this fired ZERO times (spec lines 36-37) — which is exactly
why it needs a test and an alarm rather than confidence.

═══════════════════════════════════════════════════════════════════════════════
TWO COUNTING CONVENTIONS LIVE IN THIS FEATURE. THAT IS DELIBERATE.
═══════════════════════════════════════════════════════════════════════════════
    ENTRY roll (N=5)   → CALENDAR days   (futures_resolver._ENTRY_ROLL_DAYS)
    EXIT backstop (T-2) → TRADING SESSIONS (this module)

They differ because they answer different questions, and reading one as an
inconsistency with the other would be a misreading:

  * The N=5 entry rule is a MARGIN and liquidity rule. Dhan's delivery-margin ramp
    (E-4 10% → E-3 25% → E-2 45% → E-1 70% → expiry 100%) runs on calendar proximity
    to expiry, and the exchange's expiry-day carry-forward ban is a calendar fact.
    Five CALENDAR days clears the whole ramp regardless of how many of those days
    happen to be sessions. Counting sessions there would make the rule LOOSER over a
    holiday week — permitting an entry deeper into the ramp — which is backwards.

  * The T-2 backstop is an OPPORTUNITY-TO-EXIT rule. What it must guarantee is that
    the position can still be closed on the exchange before the contract dies. A
    holiday is not a day you can exit on; it removes an opportunity. Counting calendar
    days there would OVERSTATE the remaining chances to get out, which is the one
    direction that costs real money (an unclosed futures position going to delivery).

  So: the entry rule counts calendar days because MARGIN accrues on the calendar, and
  the exit rule counts sessions because EXITS only happen on sessions. Each convention
  is the conservative one for its own question. Neither is a copy of the other.

═══════════════════════════════════════════════════════════════════════════════
WHERE THE SESSION CALENDAR COMES FROM — derived, never invented
═══════════════════════════════════════════════════════════════════════════════
No holiday list is hardcoded anywhere in this module, and none is imported from a
third-party calendar package. Sessions are derived from exchange data the repo
already holds, in two layers:

  LAYER 1 — weekends. ``strategy_engine.trading_calendar`` (pure, stdlib-only,
  already in the repo and written for exactly this use: its docstring anticipates
  "roll when trading_days_between(today, expiry) <= 2").

  LAYER 2 — holidays, derived from REAL STORED DAILY CANDLES
  (``historical_candles``, ``timeframe='1d'``). The exchange prints a daily bar on a
  session and on no other day, so within a window that has coverage:

      weekday with NO daily bar anywhere in the table ⇒ NON-SESSION

  The query is deliberately symbol-agnostic (``DISTINCT date(timestamp)`` across the
  whole table for the window): a session is a property of the exchange, not of one
  instrument, so this cannot be skewed by a single symbol's listing gaps. The rows are
  real Dhan v2 historical bars the platform already fetched and stored — not a list
  anyone typed, and not a third-party calendar package.

  COVERAGE GUARD. If the window has NO daily bars at all, the table simply has not
  been backfilled there; that is "unknown", not "every day was a holiday". The
  derivation returns ``None`` in that case and the caller degrades to Layer 1 rather
  than inventing a calendar out of missing data — the same doctrine as the store
  watchdog treating a missing store as stale rather than fresh.

  LAYER 3 (corroboration only) — ``derive_holidays_from_expiry`` reads a
  holiday-shifted ``SEM_EXPIRY_DATE``: when the exchange publishes an expiry EARLIER
  than the nominal last Thursday, the skipped weekdays were not sessions. It is kept
  because it is free and exchange-published, but note its STRUCTURAL LIMIT: the
  holidays it can see lie BETWEEN the real and nominal expiry, i.e. always AFTER the
  real expiry — so they never fall inside the ``(today, expiry]`` counting window and
  can never change a session count. It is evidence about the calendar, not an input to
  the count. Anything that must affect the count comes from Layer 2 or from an
  injected ``holidays=`` set.

CONSERVATIVE DIRECTION. Where the session count is uncertain, this module fires
EARLIER, never later. An early forced exit costs opportunity; a late one leaves a live
futures position facing physical delivery. Those are not symmetric, so the tie is not
split — it is broken toward the exit.

RECORDING. A fire is a first-class recorded action, never a silent mutation:
``exit_reason="T_2_BACKSTOP"`` (the EVENT reason — founder condition, so that no
ordinary exit or stop can be mistaken for this) and ``decided_by="expiry-backstop-T2"``
in the action-history record (the POLICY name, per spec line 80). Both are asserted by
the row-13 test.

Gated by ``futures_expiry_backstop_enabled`` (default False → dormant no-op).
Idempotent: closed rows no longer match the status filter.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.db.models.strategy_position import StrategyPosition
from app.services.futures_resolver import _last_thursday_of_month
from app.strategy_engine.trading_calendar import trading_days_between

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

_IST_OFFSET = timedelta(hours=5, minutes=30)

#: Fire when the open contract has THIS MANY OR FEWER trading sessions left.
#: Sessions, not calendar days — see the module docstring.
_BACKSTOP_SESSIONS: int = 2

#: The EVENT reason stamped on the position. Deliberately distinct from every
#: ordinary exit reason so a backstop fire is unmistakable in the record.
BACKSTOP_EXIT_REASON = "T_2_BACKSTOP"

#: The POLICY name recorded in action_history (EXPIRY_ROLLOVER_SPEC line 80).
BACKSTOP_DECIDED_BY = "expiry-backstop-T2"


def derive_holidays_from_expiry(symbol: str, real_expiry: date) -> set[date]:
    """Non-session weekdays implied by a holiday-shifted exchange expiry.

    ``symbol`` is a canonical FUT form (``BSE-AUG2026-FUT``); ``real_expiry`` is the
    exchange-published ``SEM_EXPIRY_DATE``. If the exchange moved the expiry earlier
    than the nominal last Thursday, the skipped weekdays are non-sessions — that move
    is the exchange telling us so. Returns an empty set when nothing was shifted.

    Derived from published data only: no hardcoded dates, no holiday list.
    """
    try:
        month_token = symbol.split("-")[1]
        nominal = _last_thursday_of_month(month_token)
    except (IndexError, ValueError):
        return set()

    if real_expiry >= nominal:
        return set()

    out: set[date] = set()
    day = real_expiry + timedelta(days=1)
    while day <= nominal:
        if day.weekday() < 5:  # Mon-Fri; weekends are Layer 1's job
            out.add(day)
        day += timedelta(days=1)
    return out


async def derive_holidays_from_candles(
    session: AsyncSession, start: date, end: date
) -> set[date] | None:
    """Non-session weekdays in ``(start, end]``, from real stored daily bars.

    Returns ``None`` when the window has NO daily coverage — "unknown", never "all
    holidays". The caller degrades to weekend-only rather than inventing a calendar
    out of an empty table.
    """
    from app.db.models.historical_candle import HistoricalCandle

    lo = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    hi = datetime.combine(
        end + timedelta(days=1), datetime.min.time(), tzinfo=UTC
    )
    stmt = (
        select(HistoricalCandle.timestamp)
        .where(
            HistoricalCandle.timeframe == "1d",
            HistoricalCandle.timestamp >= lo,
            HistoricalCandle.timestamp < hi,
        )
        .distinct()
    )
    rows = list((await session.execute(stmt)).scalars().all())
    if not rows:
        return None  # no coverage → unknown, not "every day is a holiday"

    traded = {
        (ts if ts.tzinfo else ts.replace(tzinfo=UTC)).astimezone(UTC).date()
        for ts in rows
    }
    out: set[date] = set()
    day = start + timedelta(days=1)
    while day <= end:
        if day.weekday() < 5 and day not in traded:
            out.add(day)
        day += timedelta(days=1)
    return out


def sessions_to_expiry(
    today: date,
    expiry: date,
    *,
    symbol: str | None = None,
    holidays: set[date] | None = None,
) -> int:
    """Trading sessions remaining from ``today`` (exclusive) to ``expiry`` (inclusive).

    Uses the repo's existing ``trading_days_between`` so the half-open convention is
    defined in exactly one place. ``holidays`` overrides the derived set when a caller
    has a richer real session feed; otherwise holidays are derived from ``symbol``'s
    published expiry shift.
    """
    if holidays is None:
        holidays = (
            derive_holidays_from_expiry(symbol, expiry) if symbol else set()
        )
    return trading_days_between(today, expiry, holidays=holidays)


def backstop_due(
    today: date,
    expiry: date,
    *,
    symbol: str | None = None,
    holidays: set[date] | None = None,
    threshold: int = _BACKSTOP_SESSIONS,
) -> bool:
    """True when the contract has ``threshold`` or fewer sessions left.

    ``_conservative``: because a session count can only ever be OVERSTATED by an
    undetected holiday (a missed holiday makes the remaining count look larger), the
    comparison is ``<=``. An overstated count is the dangerous direction, so any
    uncertainty resolves toward firing sooner.
    """
    if today > expiry:
        return True  # already past its own expiry — unambiguously due
    return sessions_to_expiry(
        today, expiry, symbol=symbol, holidays=holidays
    ) <= threshold


def _force_exit(position: StrategyPosition, now_utc: datetime, sessions: int) -> None:
    """Record the forced exit. State mutation only — no fabricated price or PnL."""
    closed_qty = position.remaining_quantity
    position.remaining_quantity = 0
    position.status = "closed"
    position.closed_at = now_utc
    position.exit_reason = BACKSTOP_EXIT_REASON
    position.last_action = "expiry_backstop"
    position.last_action_at = now_utc
    history = list(position.action_history or [])
    history.append(
        {
            "action": "expiry_backstop",
            "qty": closed_qty,
            "ts": now_utc.isoformat(),
            "decided_by": BACKSTOP_DECIDED_BY,
            "sessions_to_expiry": sessions,
            "broker_order_id": f"PAPER-BACKSTOP-{_uuid.uuid4()}",
            "broker_status": "complete",
            "broker_message": (
                "T-2 expiry backstop: contract had "
                f"{sessions} trading session(s) left; forced exit so the "
                "position cannot reach physical delivery. No settlement price "
                "fabricated."
            ),
            "paper_mode": True,
        }
    )
    position.action_history = history
    flag_modified(position, "action_history")


async def _alert(position: StrategyPosition, sessions: int, expiry: date) -> None:
    """Loud operator ping through the EXISTING notification seam.

    This has never fired in 6.5 years of history. A fire is therefore an ANOMALY, not
    routine housekeeping, and must reach a phone rather than only a log. Wrapped so an
    alerting fault can never abort the sweep — an unsent alert must not become an
    unclosed position.
    """
    try:
        from app.services import telegram_alerts as _alerts

        await _alerts.send_alert(
            _alerts.AlertLevel.CRITICAL,
            (
                "🚨 *T-2 EXPIRY BACKSTOP FIRED*\n"
                f"`{position.symbol}` expiry `{expiry}` — "
                f"{sessions} trading session(s) remained.\n"
                f"position `{position.id}` force-closed, recorded as "
                f"`{BACKSTOP_EXIT_REASON}`.\n\n"
                "This backstop fired ZERO times across 6.5 years of history — a "
                "fire is an ANOMALY, not routine. Check why the N=5 entry roll "
                "did not already cover this position."
            ),
        )
    except Exception as exc:
        logger.warning(
            "futures_expiry_backstop.alert_failed",
            error=str(exc), position_id=str(position.id),
        )


async def sweep_expiry_backstop(
    session: AsyncSession,
    *,
    scrip_master: Any | None = None,
    now: datetime | None = None,
    holidays: set[date] | None = None,
) -> dict[str, Any]:
    """Force-exit every open FUTURES position at or inside the T-2 session boundary.

    Returns counters; safe to run repeatedly. ``now``/``holidays``/``scrip_master``
    are injectable so the row-13 test drives the REAL policy rather than a stub.
    """
    result: dict[str, Any] = {
        "status": "dormant", "checked": 0, "fired": 0,
        "skipped_not_due": 0, "skipped_no_expiry": 0,
    }
    if not get_settings().futures_expiry_backstop_enabled:
        return result
    result["status"] = "swept"

    now_utc = now or datetime.now(UTC)
    today_ist = (now_utc + _IST_OFFSET).date()

    stmt = select(StrategyPosition).where(
        StrategyPosition.status.in_(("open", "partial")),
        StrategyPosition.symbol.like("%-FUT"),
    )
    rows = list((await session.execute(stmt)).scalars().all())
    result["checked"] = len(rows)

    for pos in rows:
        expiry = _expiry_for(pos.symbol, scrip_master)
        if expiry is None:
            result["skipped_no_expiry"] += 1
            logger.warning(
                "futures_expiry_backstop.no_expiry",
                position_id=str(pos.id), symbol=pos.symbol,
            )
            continue

        # Session calendar for THIS position's window. Injected set wins (a caller
        # with a real feed); otherwise derive from stored daily bars; otherwise
        # weekend-only. Never a hardcoded list — see the module docstring.
        window = holidays
        if window is None and expiry > today_ist:
            window = await derive_holidays_from_candles(
                session, today_ist, expiry
            )
        if window is None:
            window = set()
            result["session_source"] = "weekends-only (no daily coverage)"
        else:
            result.setdefault("session_source", "derived")

        if not backstop_due(
            today_ist, expiry, symbol=pos.symbol, holidays=window
        ):
            result["skipped_not_due"] += 1
            continue

        sessions = sessions_to_expiry(
            today_ist, expiry, symbol=pos.symbol, holidays=window
        )
        _force_exit(pos, now_utc, sessions)
        result["fired"] += 1
        logger.error(  # ERROR on purpose: a fire is an anomaly, not information
            "futures_expiry_backstop.FIRED",
            position_id=str(pos.id), symbol=pos.symbol,
            expiry=str(expiry), sessions_to_expiry=sessions,
            decided_by=BACKSTOP_DECIDED_BY,
        )
        await _alert(pos, sessions, expiry)

    if result["fired"]:
        await session.commit()

    logger.info("futures_expiry_backstop.done", **{
        k: v for k, v in result.items() if k != "status"
    })
    return result


def _expiry_for(symbol: str, scrip_master: Any | None) -> date | None:
    """MASTER-FIRST expiry, mirroring options_expiry_sweep's derivation order."""
    if scrip_master is not None:
        got = scrip_master.expiry_for(symbol, "NSE_FNO")
        if got is not None:
            return got
    try:
        return _last_thursday_of_month(symbol.split("-")[1])
    except (IndexError, ValueError):
        return None


__all__ = [
    "BACKSTOP_DECIDED_BY",
    "BACKSTOP_EXIT_REASON",
    "backstop_due",
    "derive_holidays_from_expiry",
    "sessions_to_expiry",
    "sweep_expiry_backstop",
]
