# PREREG — depth-proxy evaluation, sealed before any event-conditional outcome is computed
Written 2026-09-05 (Sat) IST. Never edited after this. Inputs frozen by hash:
- research/depth_proxies.py sha256 638dc38cb821c50780b1018bc4b9827c6f70d96b1db80b69220c5a0a5e16d88b
- cp1_inventory.json sha256 c355f5a6943ec9acbf7f43063f89b1492ff840510e11aea1d1b17112d1b4ecc6 ; cp1_manifest.json sha256 ce1461559f0dd99d671001e407fa9820db9ae3a9145c563ecd7eb0a47448aaf0
- cp2_power.json (event thresholds per slot, n_eff, MDE) sha256 b7d85fdc8d33205e9101b92e4dad38f30a203d1aba7929a8c6402b7f2125ccd7
- features/_summary.json sha256 42ea3ddcd6248a6b52a5877d296f19950ec30f20909055e4211da1c26dc2cac2 ; scripts/features.py sha256 c674c2d0a44a1d2110f36eec727f1aab10945c109fe28050bc8e387f5c44a82d

## 0. Question
Do aggressor-free, depth-only features from research/depth_proxies.py rank forward MID-PRICE movement better than a matched random baseline on the banked NIFTY_FUT and BANKNIFTY_FUT depth tape? Nothing else.

## 1. Powered feature list (from CP2; a cell is scored only if powered on BOTH instruments)
- +5 s: bid_refills, ask_refills, bid_refills_w, ask_refills_w
- +30 s: bid_refills, ask_refills, bid_refill_ratio, ask_refill_ratio, bid_refills_w, ask_refills_w
- +120 s: bid_refills, ask_refills, bid_refill_ratio, ask_refill_ratio, bid_refills_w, ask_refills_w
- session close: NONE (UNPOWERED on every feature; reported as such, never scored)
Total scored cells: 16 (feature × horizon), each on 2 instruments = 32 tests.
Feature definitions: exactly CP0 rows 1–4 as computed by the unmodified `DepthProxyEngine` (levels=5, k_refill=5, near_ticks=2.0, tick=0.05, gap_guard 5 s), trade tape never fed; 5-second bars ending 09:15:05 … 15:30:00 IST (4,500 per session), refill events binned by bar_start < ts ≤ bar_end, `_w` = trailing 10-bar sum, `_ratio` = Σrestored/Σremoved per bar (undefined when no refill).

## 2. Outcome — mid-price from the depth rows, no trade tape, no aggressor assumption
mid(t) = (bid1 + ask1)/2 where bid1 = price_1 of the LAST side-0 (bid; recorder/depth_schema.py SIDE_BID=0) snapshot with ts_recv_ns ≤ t and ask1 = price_1 of the LAST side-1 snapshot with ts_recv_ns ≤ t, each no older than 2.0 s; otherwise mid(t) is undefined. t = bar end. Alignment verified on every usable session (0 ordering violations; bid1 < ask1 at all but 0–1 bar ends).
Forward return R_h(t) = mid(t+h) − mid(t) in index POINTS (bps = R_h / mid(t) × 10⁴ reported alongside), same session only (never across the 07-28→07-29 contract roll or across days).

## 3. Horizons (fixed)
+5 s (1 bar), +30 s (6 bars), +120 s (24 bars), session close (last defined mid at or before 15:30:00). No other horizon may be added.

## 4. Trigger thresholds
Per instrument, per 15-minute time-of-day slot (25 slots from 09:15), pooled across the usable sessions: T_slot = 0.99 quantile of the feature's own values (ratio: over defined bars); event iff value > T_slot. The numeric thresholds are the ones in cp2_power.json (hash above); they are not recomputed at scoring.

## 5. The null — matched random baseline
Primary test uses the THINNED event set n_eff(h) (events ≥ h apart within a session, greedy, as in CP2). For each (instrument, feature, horizon): draw B = 1000 matched samples; each sample takes, for every kept event, one NON-event bar from the same slot (any usable session) with a defined R_h, without replacement within a sample; seed 20260905 (+ draw index). Baseline mean = mean over the 1000 sample means. Two-sided empirical p = (1 + #samples with |mean_sample − mean_all_baseline| ≥ |mean_event − mean_all_baseline|) / (B + 1). Dispersion reported: std of R_h over event bars and over non-event bars. Raw-n (unthinned) means are reported as descriptive only.

## 6. Cross-instrument gate
sign(mean_event − baseline_mean) must be identical on NIFTY_FUT and BANKNIFTY_FUT for the cell. A sign flip = FAIL regardless of p on either instrument.

## 7. Pass bar (fixed now)
A cell PASSES (PRE-COST) iff: same sign on both instruments (§6) AND empirical p ≤ 0.05/16 = 0.003125 on BOTH instruments AND the n_eff used is ≥ 100 on both. Anything else = FAIL (or NOT SCORED if unpowered). No cell can be marked GREEN in this run because cost is not applied (§8): the strongest possible label is PRE-COST PASS / PENDING.

## 8. Cost model — found in the repo, printed verbatim, NOT applicable to this outcome
File: `orderflow_engine/signals/costs.py` lines 23–142 (registered rates + round_trip_cost):
```python
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
```
File: `orderflow_engine/tape_config.yaml` lines 214–220:
```yaml
  # --- cost model (2026-07-20) — REPORTING ONLY, never gates/scores ----------
  # Rates live in signals/costs.py DEFAULTS (registered knobs); keys here override.
  # slippage_multiplier scales the FRICTION terms (spread + slippage option pts) so the
  # harness can run e.g. 1.5x execution-stress without a code change; statutory charges
  # are NOT scaled. Default 1.0 = numbers unchanged (INERT).
  cost_model:
    slippage_multiplier: 1.0
```
The model prices a weekly ATM option round trip and converts to future points through the recorded delta; it requires an ATM premium and a recorded delta per trade, neither of which this run measures. It is therefore NOT applied and no cost figure is invented: every result is labelled **PRE-COST / PENDING**. For readability only, the repo's own documented 2026-07-17 reference (TAPE_NOTES.md lines 710–713, verbatim) is reproduced — it is NOT used to pass or fail anything:
```
- **Future round-trip cost ≈ ₹471/lot NIFTY (STT ₹314 alone), ₹517 BANKNIFTY (STT ₹348)** — STT
  (0.02% sell, on notional) dominates → **7.24 future-pts (NIFTY) / 17.2 (BANKNIFTY) of cost BEFORE
  spread**, fixed regardless of R.
- **Option round-trip cost ≈ ₹64/lot (charges) + spread**, /delta → **2.62 future-pts (NIFTY) / 7.96
```

## 9. Calibration design (CP5), fixed now
- RANDX: replace the event indicator by uniformly random bars at each feature's own event rate (per slot), score exactly as §5–§7 → expected: no cell passes; p-values not concentrated below 0.05.
- INJ+ / INJ−: keep the real thinned events, add δ = +3·MDE_h (resp. −3·MDE_h) of that instrument/feature/horizon to R_h at event bars only → expected: recovered (mean_event − baseline) ≈ δ with the correct sign, within 2 standard errors (SE = σ_h·√(2/n_eff)).
- Each run twice with seeds 1 and 2 (in addition to the scoring seed).

## 10. Data
Usable sessions (25): 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17, 2026-07-20, 2026-07-21, 2026-07-22, 2026-07-23, 2026-07-24, 2026-07-27, 2026-07-28, 2026-07-29, 2026-07-30, 2026-07-31, 2026-08-03, 2026-08-04, 2026-08-05, 2026-08-06, 2026-08-07, 2026-08-10, 2026-08-11, 2026-08-12, 2026-08-13, 2026-08-14. Excluded: 2026-08-17 (ask-side prices negative; CP1). Source objects: the 52 keys in cp1_manifest.json; streamed, never stored.

## 11. Order of operations (attested)
Before this file was written: CP0 audit; CP1 inventory; feature computation (no forward returns); CP2 counts and UNCONDITIONAL σ_h / median|move|_h over all bars (needed for the MDE arithmetic). No event-conditional forward return, no baseline draw and no score was computed before this file's hash was recorded.
