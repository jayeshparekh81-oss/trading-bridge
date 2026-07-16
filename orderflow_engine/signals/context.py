"""SignalContext — a live snapshot of R3/R4/R5 state at one evaluation point.

A plain data container (so tests can construct it directly). The SignalEngine
populates it from the tape/levels/chain engines' live state at each bar close;
components read its fields and return activation in [0, 1], treating missing
inputs (None) as no activation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SignalContext:
    instrument: str
    index: str
    sid: int
    ts_ns: int
    price: float
    session_start_ns: int = 0

    # --- R3 tape ---
    cvd: float = 0.0
    cvd_slope: float = 0.0
    bar_delta: int = 0
    bar_high: Optional[float] = None
    bar_low: Optional[float] = None
    velocity_spike: bool = False
    velocity_ratio: Optional[float] = None
    atr: Optional[float] = None                      # rolling per-bar ATR (stop-floor input)
    recent_big_print_side: Optional[int] = None      # +1 buy / -1 sell within window
    stacked_imbalance_side: Optional[int] = None
    footprint: dict = field(default_factory=dict)

    # --- R4 levels ---
    vwap: Optional[float] = None
    vwap_bands: dict = field(default_factory=dict)   # {"upper_1":.., "lower_1":..}
    poc: Optional[float] = None
    vah: Optional[float] = None
    val: Optional[float] = None
    ib_high: Optional[float] = None
    ib_low: Optional[float] = None
    registry: object = None                          # LevelRegistry (live) for distance queries

    # --- R5 chain / regime inputs ---
    net_gex: Optional[float] = None
    gamma_flip: Optional[float] = None
    pcr_oi: Optional[float] = None
    atm_iv: Optional[float] = None
    max_pain: Optional[float] = None
    buildup_matrix: dict = field(default_factory=dict)
    vix: Optional[float] = None
    ma_slope: Optional[float] = None
    days_to_expiry: Optional[int] = None

    # --- R1 depth (STUB until Monday) ---
    book_ofi: Optional[float] = None                 # None => neutral (stub)
    queue_imbalance: Optional[float] = None

    # populated by the engine after regime computation (used by regime component + gate)
    regime_direction: Optional[str] = None           # bull | bear | neutral
    regime_vol_band: Optional[str] = None            # low | normal | high
