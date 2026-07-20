"""Round-trip execution cost model (Module R6) — G2's actual gate is "PF >= 1.5 AFTER
COSTS", and nothing computed net R until this. Costs are modelled on the EXECUTION
instrument (a weekly ATM NIFTY/BANKNIFTY option), itemised, every rate a registered knob
(see TAPE_NOTES "Cost model — registered rates"). No magic numbers.

THE CONVERSION (the part that matters): the sim works in FUTURE points and R; costs are in
OPTION points. option_move ≈ future_move × delta, so a cost of C option-points needs the
future to move C/delta points to cover it. DELTA IS SOURCED FROM THE RECORDED GREEKS
(intraday-T), NOT a hardcoded 0.5 — hardcoding it would be the lot-size anti-pattern again.
``atm_option_delta`` reads it from the chain snapshot; the 0.5 fallback is used ONLY when
greeks are unavailable and is FLAGGED (delta_source='fallback').

Costs are a FIXED per-round-trip drag → net_r = gross_r − cost_r, the SAME cost_r whether the
trade wins or loses. That inverts the payoff asymmetry: a +0.85R win shrinks, a −1R loss
deepens PAST −1R. Both gross and net are reported side by side — net never replaces gross.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

# --- registered rate knobs (defaults measured/sourced 2026-07; see TAPE_NOTES) --------
# RATES ARE ASSUMPTIONS AS OF 2026-07 — verify against a live Dhan contract note.
DEFAULTS = {
    # brokerage: Dhan F&O is a flat ₹20 per executed order (ASSUMPTION — Dhan published
    # rate; confirm on the account). Round trip = 2 orders.
    "brokerage_per_order_inr": 20.0,
    # STT: options SELL side only, 0.1% of the sell premium (Finance Act 2024 raised it
    # from 0.0625%). Basis = sell premium turnover.
    "stt_rate_sell": 0.001,
    # NSE exchange transaction charge on options premium turnover, BOTH legs (~₹35.03/lakh).
    "exchange_txn_rate": 0.0003503,
    # SEBI turnover fee ₹10/crore = 0.0001%, both legs.
    "sebi_turnover_rate": 0.000001,
    # stamp duty 0.003% on the BUY premium only.
    "stamp_duty_rate_buy": 0.00003,
    # GST 18% on (brokerage + exchange txn + SEBI).
    "gst_rate": 0.18,
    # SPREAD — the DOMINANT term, ~1.0 option pt MEASURED (round-trip: cross bid/ask on
    # entry AND exit). A PARAMETER, not a constant: it varies by time-of-day, moneyness and
    # expiry proximity. Default = measured; override per trade (spread_override).
    "spread_option_pts": 1.0,
    # SLIPPAGE — execution beyond top-of-book (market impact / partial fills), SEPARATE from
    # the bid/ask spread. Default 0 for normal exits; stop-outs eat more (pass a higher
    # value on adverse exits). The FUTURE-side stop slippage is modelled separately in the
    # exit sim (stop_slippage_ticks); this is the OPTION-side execution slippage.
    "slippage_option_pts": 0.0,
    # FALLBACK delta — used ONLY when recorded greeks are unavailable, and FLAGGED.
    "fallback_delta": 0.5,
    # STRESS knob (2026-07-20): multiplies the FRICTION terms (spread + slippage option
    # pts) so the harness can run e.g. 1.5x execution-stress without a code change.
    # Statutory ₹ charges (brokerage/STT/txn/SEBI/stamp/GST) are NOT scaled — they are
    # rates, not execution quality. Default 1.0 = byte-identical to before.
    "slippage_multiplier": 1.0,
}


@dataclass(frozen=True)
class CostConfig:
    brokerage_per_order_inr: float = DEFAULTS["brokerage_per_order_inr"]
    stt_rate_sell: float = DEFAULTS["stt_rate_sell"]
    exchange_txn_rate: float = DEFAULTS["exchange_txn_rate"]
    sebi_turnover_rate: float = DEFAULTS["sebi_turnover_rate"]
    stamp_duty_rate_buy: float = DEFAULTS["stamp_duty_rate_buy"]
    gst_rate: float = DEFAULTS["gst_rate"]
    spread_option_pts: float = DEFAULTS["spread_option_pts"]
    slippage_option_pts: float = DEFAULTS["slippage_option_pts"]
    fallback_delta: float = DEFAULTS["fallback_delta"]
    slippage_multiplier: float = DEFAULTS["slippage_multiplier"]

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "CostConfig":
        d = d or {}
        return cls(**{k: float(d.get(k, DEFAULTS[k])) for k in DEFAULTS})


@dataclass(frozen=True)
class CostBreakdown:
    # ₹ components (per round trip, per `lots` lots)
    brokerage_inr: float
    stt_inr: float
    exchange_txn_inr: float
    sebi_inr: float
    stamp_duty_inr: float
    gst_inr: float
    charges_inr_total: float
    # option-point components (per unit)
    charges_option_pts: float          # the ₹ charges ÷ (lot_size × lots)
    spread_option_pts: float
    slippage_option_pts: float
    total_option_pts: float
    # the conversion
    delta: float
    delta_source: str                  # 'recorded' | 'fallback'
    total_future_pts: float            # option pts ÷ delta
    r_unit_pts: float
    cost_r: float                      # future-point cost ÷ R-unit


def round_trip_cost(*, entry_premium: float, lot_size: int, delta: float, delta_source: str,
                    r_unit_pts: float, cfg: CostConfig, lots: int = 1,
                    exit_premium: Optional[float] = None,
                    spread_override: Optional[float] = None,
                    slippage_override: Optional[float] = None) -> CostBreakdown:
    """Itemised round-trip cost, expressed finally as ``cost_r`` (cost in R-multiples).

    ₹ charges use premium turnover (buy + sell legs); ``exit_premium`` defaults to
    ``entry_premium`` (the premium-dependent charges are a small share, so the exit-leg
    approximation is negligible). Spread + slippage are already in option points.
    """
    if delta <= 0 or lot_size <= 0 or r_unit_pts <= 0:
        raise ValueError("delta, lot_size, r_unit_pts must be > 0")
    exit_premium = entry_premium if exit_premium is None else exit_premium
    qty = lot_size * lots
    buy_turnover = entry_premium * qty
    sell_turnover = exit_premium * qty

    brokerage = cfg.brokerage_per_order_inr * 2                    # two orders
    stt = cfg.stt_rate_sell * sell_turnover                        # sell side only
    txn = cfg.exchange_txn_rate * (buy_turnover + sell_turnover)   # both legs
    sebi = cfg.sebi_turnover_rate * (buy_turnover + sell_turnover)
    stamp = cfg.stamp_duty_rate_buy * buy_turnover                 # buy side only
    gst = cfg.gst_rate * (brokerage + txn + sebi)
    charges_inr = brokerage + stt + txn + sebi + stamp + gst

    charges_pts = charges_inr / qty                               # ₹ per unit = option points
    # friction terms scaled by the stress knob (default 1.0 = unchanged); ₹ charges are not.
    spread = (cfg.spread_option_pts if spread_override is None else spread_override) \
        * cfg.slippage_multiplier
    slippage = (cfg.slippage_option_pts if slippage_override is None else slippage_override) \
        * cfg.slippage_multiplier
    total_option_pts = charges_pts + spread + slippage

    total_future_pts = total_option_pts / delta                  # THE CONVERSION
    cost_r = total_future_pts / r_unit_pts
    return CostBreakdown(
        brokerage_inr=brokerage, stt_inr=stt, exchange_txn_inr=txn, sebi_inr=sebi,
        stamp_duty_inr=stamp, gst_inr=gst, charges_inr_total=charges_inr,
        charges_option_pts=charges_pts, spread_option_pts=spread, slippage_option_pts=slippage,
        total_option_pts=total_option_pts, delta=delta, delta_source=delta_source,
        total_future_pts=total_future_pts, r_unit_pts=r_unit_pts, cost_r=cost_r)


def net_r(gross_r: float, cost_r: float) -> float:
    """ADDITIVE: costs are a fixed drag independent of outcome. A winner shrinks, a −1R
    loser deepens past −1R — the asymmetry inversion."""
    return gross_r - cost_r


def trade_net_r(*, realized_r: float, r_unit_pts: float, entry_premium: float, delta: float,
                delta_source: str, lot_size: int, cfg: CostConfig,
                spread_override: Optional[float] = None,
                slippage_override: Optional[float] = None
                ) -> tuple[float, float, CostBreakdown]:
    """Per-trade glue used by the engine at close: derive the exit premium from the trade's
    own outcome (option move = future move × delta) so the sell-leg turnover is honest, then
    return (net_r, cost_r, breakdown). Both gross (the caller's realized_r) and net survive."""
    exit_premium = entry_premium + realized_r * r_unit_pts * delta
    b = round_trip_cost(entry_premium=entry_premium, exit_premium=exit_premium,
                        lot_size=lot_size, delta=delta, delta_source=delta_source,
                        r_unit_pts=r_unit_pts, cfg=cfg, spread_override=spread_override,
                        slippage_override=slippage_override)
    return net_r(realized_r, b.cost_r), b.cost_r, b


# --- delta sourcing from recorded greeks (NOT hardcoded) ------------------------------
def atm_option_delta(chain_rows: Sequence[dict], ts_ns: int, spot: float, side: str,
                     cfg: CostConfig) -> tuple[float, str]:
    """|delta| of the ATM option (CE for long, PE for short) at/just before ``ts_ns``,
    from the recorded chain snapshots. Returns (delta, 'recorded'); falls back to
    (cfg.fallback_delta, 'fallback') when greeks are unavailable — FLAGGED, never silent.

    ``chain_rows`` = per-strike-per-snapshot rows (chain_<index>.parquet or engine.rows)."""
    right = "CE" if side == "long" else "PE"
    snaps = sorted({int(r["snapshot_ts_ns"]) for r in chain_rows})
    prior = [s for s in snaps if s <= ts_ns]
    read_ts = prior[-1] if prior else (snaps[0] if snaps else None)   # last-known, no look-ahead
    if read_ts is None:
        return cfg.fallback_delta, "fallback"
    cands = [r for r in chain_rows if int(r["snapshot_ts_ns"]) == read_ts
             and r.get("right") == right and r.get("delta") is not None]
    if not cands:
        return cfg.fallback_delta, "fallback"
    atm = min(cands, key=lambda r: abs(float(r["strike"]) - spot))
    d = abs(float(atm["delta"]))
    return (d, "recorded") if d > 0 else (cfg.fallback_delta, "fallback")


def atm_option_premium(chain_rows: Sequence[dict], ts_ns: int, spot: float,
                       side: str) -> Optional[float]:
    """ltp of the ATM option at/just before ``ts_ns`` — the premium turnover basis."""
    right = "CE" if side == "long" else "PE"
    snaps = sorted({int(r["snapshot_ts_ns"]) for r in chain_rows})
    prior = [s for s in snaps if s <= ts_ns]
    read_ts = prior[-1] if prior else (snaps[0] if snaps else None)
    if read_ts is None:
        return None
    cands = [r for r in chain_rows if int(r["snapshot_ts_ns"]) == read_ts
             and r.get("right") == right and r.get("ltp")]
    if not cands:
        return None
    return float(min(cands, key=lambda r: abs(float(r["strike"]) - spot))["ltp"])
