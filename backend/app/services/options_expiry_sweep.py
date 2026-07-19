"""Expired-option square-off sweep — Options Brick #4, slice ②. NEW · flag-gated.

Audit gap: an open option PAPER position survived expiry forever (no beat job;
``OptionsConfig.expiry_day_force_close`` declared but consumed by nothing).
This sweep finds OPEN/PARTIAL option-leg positions (``%-CE`` / ``%-PE`` — a
futures ``%-FUT`` or cash row can never match) whose expiry has passed the
15:30 IST expiry-day cutoff and paper-closes them, ``exit_reason='expired'``.

Expiry derivation — MASTER-FIRST, PARSE-FALLBACK:
  1. ``scrip_master.expiry_for(symbol, 'NSE_FNO')`` — the REAL
     ``SEM_EXPIRY_DATE``, the same source the entry mapper used (and the R4
     futures-expiry fix reads). Authoritative while the contract is listed.
  2. Fallback: a ``DDMONYYYY`` token parsed from the stored symbol — an
     EXPIRED contract drops out of a refreshed master (the BSE-MAY2026
     delisting lesson), which is exactly when this sweep still needs a date.
  3. Neither → log + skip that row; the sweep continues (never crashes).

Honesty: NO settlement premium is fabricated. The close records qty/status/
history only; ``final_pnl`` stays whatever the position accrued. Real
settlement pricing arrives with the premium-join slice (recorder parquet).

Scoping: owner AND subscriber rows both sweep (an expired option is expired
for everyone; each row closes independently — a subscriber row's failure
cannot block the owner's). Rows whose strategy is NOT paper are defensively
skipped + logged (impossible today — the options executor refuses live — but
this sweep must never silently paper-close a live position).

Gated by ``options_execution_enabled`` (default False → dormant no-op).
Idempotent: closed rows no longer match the status filter.
"""

from __future__ import annotations

import re
import uuid as _uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import or_, select
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("app.services.options_expiry_sweep")

#: IST = UTC+5:30. Expiry-day square-off cutoff: 15:30 IST (exchange close —
#: the premium stops trading; after this the leg is settled, not tradeable).
_IST_OFFSET = timedelta(hours=5, minutes=30)
_EXPIRY_SQUAREOFF_IST = time(15, 30)

#: ``DDMONYYYY`` token embedded in a leg symbol (e.g. ``BSE-16JUL2026-2400-CE``).
#: A futures symbol (``BSE-JUL2026-FUT``) has no leading day digits → no match.
_DATE_TOKEN = re.compile(r"(\d{1,2})([A-Z]{3})(\d{4})")
_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def derive_option_expiry(
    symbol: str,
    *,
    scrip_master: Any | None = None,
    segment: str = "NSE_FNO",
) -> date | None:
    """Expiry date for a stored option-leg symbol, or ``None`` (caller skips).

    Master-first (authoritative SEM_EXPIRY_DATE), symbol-parse fallback (for
    contracts already delisted from a refreshed master). Never raises.
    """
    if scrip_master is not None:
        try:
            expiry = scrip_master.expiry_for(symbol, segment)
        except Exception:  # broad by design — a master hiccup must not kill the sweep
            expiry = None
        if expiry is not None:
            return expiry

    m = _DATE_TOKEN.search(symbol.upper())
    if m:
        day, mon, year = m.groups()
        month = _MONTHS.get(mon)
        if month is not None:
            try:
                return date(int(year), month, int(day))
            except ValueError:  # e.g. 31FEB — treat as unparseable
                return None
    return None


def _past_squareoff_cutoff(expiry: date, now_utc: datetime) -> bool:
    """True once ``now`` is past 15:30 IST on the expiry day (or any day after)."""
    ist = now_utc + _IST_OFFSET
    if ist.date() > expiry:
        return True
    return ist.date() == expiry and ist.time() >= _EXPIRY_SQUAREOFF_IST


def _close_expired(position: StrategyPosition, now_utc: datetime) -> None:
    """Paper-close one expired leg — mirrors the kill-switch paper close shape
    (state mutation only, no broker, no fabricated price/PnL)."""
    closed_qty = position.remaining_quantity
    position.remaining_quantity = 0
    position.status = "closed"
    position.closed_at = now_utc
    position.exit_reason = "expired"
    position.last_action = "expiry_sweep"
    position.last_action_at = now_utc
    history = list(position.action_history or [])
    history.append(
        {
            "action": "expiry_sweep",
            "qty": closed_qty,
            "ts": now_utc.isoformat(),
            "broker_order_id": f"PAPER-EXPIRY-{_uuid.uuid4()}",
            "broker_status": "complete",
            "broker_message": (
                "expired option leg squared off (paper) — settlement premium "
                "NOT fabricated; real settlement lands with the premium-join "
                "slice"
            ),
            "paper_mode": True,
        }
    )
    position.action_history = history
    flag_modified(position, "action_history")


async def sweep_expired_options(
    session: AsyncSession,
    *,
    scrip_master: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Square off every open option-leg position past its expiry cutoff.

    Returns counters; safe to run repeatedly (idempotent — closed rows no
    longer match). ``now`` is injectable for tests.
    """
    result: dict[str, Any] = {
        "status": "dormant", "checked": 0, "closed": 0,
        "skipped_not_expired": 0, "skipped_unparseable": 0, "skipped_live": 0,
    }
    if not get_settings().options_execution_enabled:
        return result
    result["status"] = "swept"

    now_utc = now or datetime.now(UTC)

    stmt = select(StrategyPosition).where(
        StrategyPosition.status.in_(("open", "partial")),
        or_(
            StrategyPosition.symbol.like("%-CE"),
            StrategyPosition.symbol.like("%-PE"),
        ),
    )
    rows = list((await session.execute(stmt)).scalars().all())
    result["checked"] = len(rows)

    strat_cache: dict[Any, Strategy | None] = {}
    for pos in rows:
        expiry = derive_option_expiry(pos.symbol, scrip_master=scrip_master)
        if expiry is None:
            result["skipped_unparseable"] += 1
            logger.warning(
                "options_expiry_sweep.unparseable_symbol",
                position_id=str(pos.id), symbol=pos.symbol,
            )
            continue
        if not _past_squareoff_cutoff(expiry, now_utc):
            result["skipped_not_expired"] += 1
            continue

        if pos.strategy_id not in strat_cache:
            strat_cache[pos.strategy_id] = await session.get(
                Strategy, pos.strategy_id
            )
        strat = strat_cache[pos.strategy_id]
        if strat is None or strat.is_paper is not True:
            # Defensive: never silently paper-close a LIVE position (cannot
            # happen today — the options executor refuses live strategies).
            result["skipped_live"] += 1
            logger.warning(
                "options_expiry_sweep.live_row_skipped",
                position_id=str(pos.id), symbol=pos.symbol,
                strategy_id=str(pos.strategy_id),
            )
            continue

        _close_expired(pos, now_utc)
        result["closed"] += 1
        logger.info(
            "options_expiry_sweep.position_expired_closed",
            position_id=str(pos.id), symbol=pos.symbol, expiry=str(expiry),
            subscription_id=(
                str(pos.subscription_id) if pos.subscription_id else None
            ),
        )

    if result["closed"]:
        await session.commit()

    logger.info("options_expiry_sweep.done", **{
        k: v for k, v in result.items() if k != "status"
    })
    return result


__all__ = ["derive_option_expiry", "sweep_expired_options"]
