"""Central config for the trend-engine backtest harness (Module 0).

One dataclass, no scattered magic numbers. Instrument specs (lot/tick) live
here too — every rate/size that could drift is a labelled constant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time


@dataclass(frozen=True)
class InstrumentSpec:
    lot_size: int      # units per lot        # VERIFY current NSE lot size
    tick_size: float   # min price increment  # VERIFY current NSE tick size


@dataclass
class Config:
    capital: float = 1_000_000.0          # starting equity, INR
    lots: int = 1                          # lots per trade (fixed-size smoke test)
    slippage_ticks: int = 1                # ticks of slippage per fill
    brokerage_per_order: float = 20.0      # flat INR/order  # VERIFY broker plan

    # Session (NSE, IST). Intraday only — flat overnight.
    session_start: time = time(9, 15)
    session_end: time = time(15, 30)
    square_off_time: time = time(15, 20)   # force-flat by this time each day

    symbols: tuple[str, ...] = ("NIFTY_FUT", "BANKNIFTY_FUT")

    # Per-symbol contract specs. lot_size matches Dhan scrip master today;
    # tick_size is the standard NSE index-future tick (master reports it in
    # paise). Both flagged VERIFY — they scale INR PnL / slippage directly.
    instruments: dict[str, InstrumentSpec] = field(
        default_factory=lambda: {
            "NIFTY_FUT": InstrumentSpec(lot_size=65, tick_size=0.05),      # VERIFY
            "BANKNIFTY_FUT": InstrumentSpec(lot_size=30, tick_size=0.05),  # VERIFY
            # Cash equity (shares, not lots). "lot_size" = fixed share qty for
            # readable gross INR; equity analysis is GROSS/cost-independent, so
            # the qty only scales magnitude, never the monotonicity call.
            "BSE": InstrumentSpec(lot_size=100, tick_size=0.05),           # VERIFY (equity = shares)
            "CDSL": InstrumentSpec(lot_size=100, tick_size=0.05),          # VERIFY (equity = shares)
        }
    )

    # ── %-normalized (ATR) sizing + walk-forward — kills price-level inflation.
    atr_risk_frac: float = 0.005           # size so 1 ATR ≈ 0.5% of capital per trade
    slippage_bps_per_side: float = 2.0     # equity slippage, bps per fill  # VERIFY
    wf_train_months: int = 18              # walk-forward burn-in (Donchian N is NOT tuned)
    wf_test_months: int = 6                # rolling OOS test window

    # Sharpe/Sortino annualization inputs (5-min bars).
    bars_per_day: int = 75                 # 09:15–15:30 on a 5-min grid
    trading_days_per_year: int = 252
    risk_free_rate: float = 0.0            # per-annum; 0 for a smoke test

    # ── Regime filter (ablation rung 1) — DO NOT TUNE; these are the fixed defaults.
    regime_lookback: int = 75              # bars of history each indicator sees (~1 session)
    atr_period: int = 14                   # ATR smoothing window (bars)
    hurst_thresh: float = 0.55             # trending if Hurst >
    er_thresh: float = 0.35                # trending if Kaufman ER >
    atr_pct_thresh: float = 60.0           # trending if ATR percentile >

    # ── Donchian trend-following entry — two fixed classic breakout lengths.
    donchian_n: int = 20                   # channel lookback (bars); primary
    donchian_lengths: tuple[int, ...] = (20, 55)  # classic breakout lengths (NO tuning)
