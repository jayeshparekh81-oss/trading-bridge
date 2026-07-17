"""R8 risk gates + account risk state — the layer absent today (17-Jul founder decisions,
all HYPOTHESIS-NOT-CALIBRATED):

  * D1 — post-win size-down: after ``after_consecutive_wins`` (2) straight wins, the next
    trade is sized at ``sizedown_factor`` (0.5). Discipline against euphoria/streak-chasing.
  * D2 — correlation guard: our tradeables (NIFTY_FUT, BANKNIFTY_FUT) co-move (~1 bet), and
    the existing one_open_position gate is PER-INSTRUMENT, so both could open. D2 is a HARD
    GLOBAL one-position rule across the whole tradeable set.
  * Daily loss limit: halt the day at ``daily_loss_limit_r`` (−3R).
  * Consecutive-loss halt: halt after ``consecutive_loss_halt`` (3) straight losses.

State machine only — no I/O. Day P&L is tracked in R (each trade risks risk_pct, so R sums
are ~risk-normalised). These are risk GATES, not signal components — they don't touch the
closed menu.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RiskConfig:
    starting_capital_inr: float = 500000.0
    daily_loss_limit_r: float = -3.0
    consecutive_loss_halt: int = 3
    d1_enabled: bool = True
    d1_after_consecutive_wins: int = 2
    d1_sizedown_factor: float = 0.5
    d2_global_one_position: bool = True

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "RiskConfig":
        d = d or {}
        d1 = d.get("d1_post_win", {})
        return cls(
            starting_capital_inr=float(d.get("starting_capital_inr", 500000.0)),
            daily_loss_limit_r=float(d.get("daily_loss_limit_r", -3.0)),
            consecutive_loss_halt=int(d.get("consecutive_loss_halt", 3)),
            d1_enabled=bool(d1.get("enabled", True)),
            d1_after_consecutive_wins=int(d1.get("after_consecutive_wins", 2)),
            d1_sizedown_factor=float(d1.get("sizedown_factor", 0.5)),
            d2_global_one_position=bool(d.get("d2_global_one_position", True)))


@dataclass
class RiskState:
    equity_inr: float
    day_pnl_r: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    global_open: bool = False
    halted: bool = False
    halt_reason: str = ""


def d1_size_factor(state: RiskState, cfg: RiskConfig) -> float:
    """D1: the sizedown factor for the NEXT trade (1.0 unless the win streak triggers it)."""
    if cfg.d1_enabled and state.consecutive_wins >= cfg.d1_after_consecutive_wins:
        return cfg.d1_sizedown_factor
    return 1.0


def pre_trade_gate(state: RiskState, cfg: RiskConfig) -> tuple[bool, str]:
    """Run BEFORE sizing/opening. Returns (allow, reason). Order: halt → daily limit → D2."""
    if state.halted:
        return False, f"r8:{state.halt_reason}"
    if state.day_pnl_r <= cfg.daily_loss_limit_r:
        return False, "r8:daily_loss_limit"
    if cfg.d2_global_one_position and state.global_open:
        return False, "r8:d2_global_one_position"
    return True, ""


def on_open(state: RiskState) -> None:
    """A position opened — D2 now blocks any other until it closes."""
    state.global_open = True


def on_close(state: RiskState, cfg: RiskConfig, net_r: float) -> None:
    """Update streaks + day P&L after a trade closes; latch a halt if a limit is hit."""
    state.day_pnl_r += net_r
    if net_r > 0:
        state.consecutive_wins += 1
        state.consecutive_losses = 0
    elif net_r < 0:
        state.consecutive_losses += 1
        state.consecutive_wins = 0
    # a flat (net_r == 0) trade breaks neither streak
    state.global_open = False
    if state.consecutive_losses >= cfg.consecutive_loss_halt:
        state.halted, state.halt_reason = True, "consecutive_loss_halt"
    elif state.day_pnl_r <= cfg.daily_loss_limit_r:
        state.halted, state.halt_reason = True, "daily_loss_limit"
