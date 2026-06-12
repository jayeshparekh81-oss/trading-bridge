"""Decide how much of the Dhan per-token quota the backfill worker
may consume at any given moment.

Dhan v2 historical caps at 5 req/s per access-token. That budget has to
be shared between **live** users (chart history endpoint, indicator
recompute, ad-hoc backtest pre-flight) and **backfill** (the Phase 3
overnight catch-up job + the 22-symbol Phase 3 seed). The rules below
encode Q4A + the off-market window decision from
``docs/QUEUE_CCC_REAL_DHAN_DESIGN_v2.md`` §4:

* **Off-market window — 16:00 IST through 09:00 IST next morning** (NSE
  close → next open, with a 15-min buffer). Backfill takes 80% of the
  budget; the 20% reserve absorbs late-arriving chart-page requests
  from operators reviewing the day's session.
* **Market window — 09:00 IST through 16:00 IST.** Backfill takes 20%
  of the budget so live consumers stay snappy.
* **Kill-switch state ``paused_live_strategy``.** Independent override
  irrespective of the clock — when live trading is paused, there are
  no real-time orders consuming quota, so backfill behaves as if it
  were off-market and gets the 80% slice. Catches the
  paused-from-incident scenario where backfill SHOULD aggressively
  catch up.

The module is **pure** — no DB, no Redis. The orchestrator passes in
the current ``now_utc`` and the boolean kill-switch state it has
already read from its own context. Easy to unit-test with a frozen
clock; easy to wire into a Celery beat schedule that reads kill-switch
state at task-start time.

Future tweaks (Phase 3+):
* Friday post-close window (16:00 Fri → 09:00 Mon) could grant 100%
  to backfill since no live consumer is active. Not in scope tonight.
* Per-user backfill caps (a single operator shouldn't drain all 80%).
  Phase 3+ tier-1 follow-up.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")
_MARKET_OPEN_IST = time(hour=9, minute=0)
_MARKET_CLOSE_IST = time(hour=16, minute=0)

# Fractional shares of the 5 req/s Dhan budget that backfill is allowed
# to take. Live users get the complement.
_OFF_MARKET_BACKFILL_SHARE = 0.80
_LIVE_MARKET_BACKFILL_SHARE = 0.20

# The Dhan-side per-token rate ceiling (req/s). Centralised here so the
# orchestrator does not duplicate the constant.
DHAN_HISTORICAL_BUDGET_RPS: float = 5.0


@dataclass(frozen=True)
class BackfillQuota:
    """Resolved rate budget for the backfill worker at a single instant.

    Attributes:
        backfill_rps: Req/s the worker may issue against Dhan.
        share: Fractional share of the global budget (0.0–1.0).
        rationale: One of ``"off_market"``, ``"market_hours_live"``,
            ``"kill_switch_paused_live_strategy"``. Used for the
            structured log line + jobs-table audit trail.
    """

    backfill_rps: float
    share: float
    rationale: str


def is_off_market_window_ist(now_utc: datetime) -> bool:
    """True when the IST clock is in the off-market window (16:00–09:00).

    Args:
        now_utc: Timezone-aware UTC datetime. Naive input raises
            ``ValueError`` — the chart module's TZ-discipline applies.

    The window is left-closed / right-open per the standard NSE
    session boundary: 16:00:00 IST is OFF, 09:00:00 IST is ON. This
    matters at the exact second the bell rings; weekends are always
    off-market regardless of the clock-time check (Saturday 12:00 is
    off-market because the market is closed, even though 12:00 IST is
    inside the [09:00, 16:00) interval). Phase 3+ will add a calendar
    lookup; the skeleton treats Sat/Sun specially without it.
    """
    if now_utc.tzinfo is None:
        raise ValueError(
            "now_utc must be timezone-aware (UTC). Naive datetimes are "
            "ambiguous and forbidden in the chart module."
        )
    ist_now = now_utc.astimezone(_IST)

    # Weekends → always off-market (Phase 3+ holiday calendar handles
    # weekday market holidays).
    if ist_now.weekday() >= 5:  # 5=Sat, 6=Sun
        return True

    ist_clock = ist_now.time()
    in_market_hours = _MARKET_OPEN_IST <= ist_clock < _MARKET_CLOSE_IST
    return not in_market_hours


def compute_backfill_quota(
    *,
    now_utc: datetime,
    kill_switch_paused_live: bool = False,
    total_budget_rps: float = DHAN_HISTORICAL_BUDGET_RPS,
) -> BackfillQuota:
    """Resolve the backfill rps + rationale for the current moment.

    Args:
        now_utc: TZ-aware current time (orchestrator typically passes
            ``datetime.now(UTC)``; tests pass a frozen instant).
        kill_switch_paused_live: True when the live-trading kill switch
            is in the ``paused_live_strategy`` state. Orchestrator
            reads this from the ``kill_switch_configs`` row (or its
            cache) before calling.
        total_budget_rps: Override for non-prod environments where the
            Dhan ceiling differs. Defaults to the documented Dhan v2
            cap (5 req/s).

    Returns:
        :class:`BackfillQuota` carrying ``backfill_rps``, the share
        fraction, and a human-readable rationale token.
    """
    if total_budget_rps <= 0:
        raise ValueError(
            f"total_budget_rps must be > 0, got {total_budget_rps!r}."
        )

    if kill_switch_paused_live:
        share = _OFF_MARKET_BACKFILL_SHARE
        rationale = "kill_switch_paused_live_strategy"
    elif is_off_market_window_ist(now_utc):
        share = _OFF_MARKET_BACKFILL_SHARE
        rationale = "off_market"
    else:
        share = _LIVE_MARKET_BACKFILL_SHARE
        rationale = "market_hours_live"

    return BackfillQuota(
        backfill_rps=total_budget_rps * share,
        share=share,
        rationale=rationale,
    )


__all__ = [
    "BackfillQuota",
    "DHAN_HISTORICAL_BUDGET_RPS",
    "compute_backfill_quota",
    "is_off_market_window_ist",
]
