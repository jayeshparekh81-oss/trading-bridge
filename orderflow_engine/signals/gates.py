"""Entry gates (Module R6) — each individually toggleable.

Each gate inspects the candidate context + per-instrument session state and returns
(allow, reason). ``apply_gates`` runs the enabled gates in order and returns the
FIRST rejection (so the glass box logs exactly why a candidate was blocked). A
rejected candidate is still evaluated + logged — only entry is withheld.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from signals.events import Event, active_event

IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class GateState:
    session_start_ns: int
    trades_today: int = 0
    has_open_position: bool = False
    last_signal_ts_ns: Optional[int] = None
    is_expiry_day: bool = False
    events: list = field(default_factory=list)


def _ist_time(ts_ns: int) -> time:
    return datetime.fromtimestamp(ts_ns / 1e9, tz=IST).time()


def _hhmm(s: str) -> time:
    hh, mm = str(s).split(":")
    return time(int(hh), int(mm))


def apply_gates(ctx, state: GateState, cfg) -> tuple[bool, Optional[str]]:
    g = cfg.gates
    # first N minutes
    n = int(g.get("first_minutes_no_entry", 0))
    if n > 0 and ctx.ts_ns - state.session_start_ns < n * 60 * 1_000_000_000:
        return False, f"first_{n}min_no_entry"
    # session cutoff (no fresh entries after)
    cutoff = g.get("session_cutoff")
    if cutoff and _ist_time(ctx.ts_ns) >= _hhmm(cutoff):
        return False, f"after_session_cutoff_{cutoff}"
    # event window
    ev: Optional[Event] = active_event(state.events, ctx.ts_ns)
    if ev is not None:
        return False, f"event_window:{ev.label}"
    # expiry-day theta guard (post-time: momentum-only)
    tg = g.get("expiry_theta_guard", {})
    if tg.get("enabled") and state.is_expiry_day and _ist_time(ctx.ts_ns) >= _hhmm(tg.get("after", "14:00")):
        if not ctx.velocity_spike:                     # momentum-only after the guard time
            return False, "expiry_theta_guard_momentum_only"
    # max trades per day
    mx = int(g.get("max_trades_per_day", 0))
    if mx > 0 and state.trades_today >= mx:
        return False, "max_trades_per_day"
    # one open position
    if g.get("one_open_position") and state.has_open_position:
        return False, "one_open_position"
    # cooldown after last signal
    cd = float(g.get("cooldown_s", 0))
    if cd > 0 and state.last_signal_ts_ns is not None \
            and ctx.ts_ns - state.last_signal_ts_ns < cd * 1_000_000_000:
        return False, "cooldown"
    # liquidity gate (STUB — off while max_spread_ticks == 0)
    liq = g.get("liquidity", {})
    if liq.get("enabled") and int(liq.get("max_spread_ticks", 0)) > 0:
        pass   # real spread/size checks land here once depth data is wired
    return True, None
