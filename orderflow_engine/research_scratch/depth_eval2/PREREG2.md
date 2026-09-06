# PREREG2 — RUN 2 (deep book, levels 6–20), sealed before any event-conditional outcome is computed
Written 2026-09-06 IST. Never edited after this. Inputs frozen by hash:
- deep_book.py sha256 06ae8d9b68f03a394e7cb817e7f4001edb2e2d9e5a2e4736477bed85847f2fe7 ; scripts/features2.py 3a32599b2534c75b2d0b498f89c5a36a25786eb3b5fefd6de82fddbd0694937b ; scripts/cp2_power2.py 8bc6dfbe90be00120ca2168c0ff8bb3333d8beaf39f7e50a20f22e0333a93216 ; scripts/scorer2.py c76650a93a786e014112dc2ddc573633332808c8ec6254b482c3b49f0249a737
- cp0_integrity.json a58c1f14fbd74b92a7eff111a9fe5acaf790b93fb519fc88fd706bee06fc899c ; cp2_power2.json (thresholds per slot, n_eff, MDE) c98af278f5999d8cc340b25e9369dc682b14c1995121a985a15cd62eeb3d4b49 ; features/_summary.json 0f720b3a3d000954e3cd9b0c0e621d8d7f51c9dd9bdfad057e8212d0f3599f37
- run-1 references (read-only, for the head-to-head): ../depth_eval/PREREG.md 8fb956b899c542b87c78be5fa6a23b80b56839ce773b5a2413a3d8471a94007c ; ../depth_eval/cp6_result_run1.json 4649f422421b85d389a1c0fabe8614a5942f0fdacd9be961d425915e31b7d895

## 0. Question
On levels 6–20 of the banked NIFTY_FUT / BANKNIFTY_FUT depth tape, proven clean in CP0, do aggressor-free features rank forward mid-price movement better than a matched random baseline, and does anything beat run 1's sub-cost 5-level refill effect? Deliverable: continue or stop 20-level recording (the decision is the user's; this run reports).

## 1. Powered feature list (CP2; a cell is scored only if powered on BOTH instruments)
- +5 s, +30 s, +120 s: all ten — deep_imb_qty, deep_imb_orders, slope_diff, conc_diff, wall_appear_bid_w, wall_appear_ask_w, wall_disappear_bid_w, wall_disappear_ask_w, deep_refill_bid_w, deep_refill_ask_w
- session close: NONE (UNPOWERED on every feature; reported as such, never scored)
Scored cells: 10 features × 3 horizons = **30**, each on 2 instruments = 60 tests. Feature definitions exactly as CP1_deep_book.md / deep_book.py (hash above): 5-second bars ending 09:15:05 … 15:30:00 IST, sides aligned at bar end (last snapshot per side, age ≤ 2 s), diffs by price, gap guard 5 s, P90 walls, k = 5 deep refills; count features are the trailing 10-bar sums.

## 2. Outcome — mid-price from the depth rows, no trade tape, no aggressor assumption
mid(t) = (bid1 + ask1)/2 with bid1 = price_1 of the last side-0 snapshot ≤ t and ask1 = price_1 of the last side-1 snapshot ≤ t, each no older than 2.0 s (side encoding from recorder/depth_schema.py, verified by the ladder-direction check in CP0). R_h(t) = mid(t+h) − mid(t) in index points, same session only (never across the 07-29 or 08-26 contract rolls). For the four SIGNED features the tested outcome is the ORIENTED return Y = sign(dev)·R_h (dev = feature − slot center), for event bars and for baseline bars alike (each bar oriented by its own deviation); for the six COUNT features the outcome is R_h itself, per side. bps = /mid × 10⁴ reported alongside.

## 3. Horizons (fixed)
+5 s (1 bar), +30 s (6 bars), +120 s (24 bars), session close (last defined mid ≤ 15:30:00). No other horizon.

## 4. Trigger percentiles
Per instrument, per 15-minute slot (25 slots from 09:15), pooled over the 38 usable sessions: signed features — event iff |f − median_slot| > 0.99-quantile of |f − median_slot|; count features — event iff value > 0.99-quantile and > 0. The numeric thresholds are those in cp2_power2.json (hash above); not recomputed at scoring.

## 5. The null — matched random baseline
Primary test on the THINNED event set n_eff(h) (events ≥ h apart within a session, greedy). B = 2000 matched samples per cell; each sample draws, for every kept event, one non-event bar from the same slot (any usable session) with a defined R_h, without replacement within a sample; per-draw seed sequence [20260906, b]. Baseline mean = mean of the 2000 sample means; two-sided empirical p = (1 + #samples with |mean_sample − baseline| ≥ |mean_event − baseline|) / 2001 (minimum attainable 0.0005). Dispersion: std of Y over event bars and over non-event bars.

## 6. Cross-instrument sign gate
sign(mean_event − baseline) must be identical on NIFTY_FUT and BANKNIFTY_FUT; a flip = FAIL regardless of p.

## 7. 🔴 SECOND-LOOK PENALTY (stated explicitly)
This is the SECOND evaluation of the same tape: 25 of the 38 sessions here are the 25 sessions run 1 scored (13 sessions, 08-18 … 09-04 minus 08-24, are new); different columns, same tape, same outcome definition. Hypotheses across BOTH runs: run 1 scored 16 cells, run 2 scores 30 → **46**. Adjustment: Bonferroni over 46 → **α = 0.05/46 = 0.001087 per cell**, required on BOTH instruments individually (run 1's bar was 0.003125). Pass iff same sign on both (§6) AND p ≤ 0.001087 on both AND n_eff ≥ 100 on both. The report records this as a second look, and no cell can be GREEN (§8): the strongest label is PRE-COST PASS / PENDING.

## 8. Cost — repo references printed verbatim, NOT applicable, nothing invented
`orderflow_engine/signals/costs.py` lines 23–56 (registered rates; the full model incl. `round_trip_cost` is reproduced verbatim in run 1's PREREG.md, hash above):
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
```
`orderflow_engine/tape_config.yaml` lines 214–220:
```yaml
  # --- cost model (2026-07-20) — REPORTING ONLY, never gates/scores ----------
  # Rates live in signals/costs.py DEFAULTS (registered knobs); keys here override.
  # slippage_multiplier scales the FRICTION terms (spread + slippage option pts) so the
  # harness can run e.g. 1.5x execution-stress without a code change; statutory charges
  # are NOT scaled. Default 1.0 = numbers unchanged (INERT).
  cost_model:
    slippage_multiplier: 1.0
```
`orderflow_engine/TAPE_NOTES.md` lines 710–713 (documented 2026-07-17 reference, flagged as ASSUMPTIONS in the repo):
```
- **Future round-trip cost ≈ ₹471/lot NIFTY (STT ₹314 alone), ₹517 BANKNIFTY (STT ₹348)** — STT
  (0.02% sell, on notional) dominates → **7.24 future-pts (NIFTY) / 17.2 (BANKNIFTY) of cost BEFORE
  spread**, fixed regardless of R.
- **Option round-trip cost ≈ ₹64/lot (charges) + spread**, /delta → **2.62 future-pts (NIFTY) / 7.96
```
The model needs an ATM option premium and a recorded delta per event; this run measures neither → every result is **PRE-COST / PENDING**; the reference lines are shown for readability only and never pass or fail anything.

## 9. Calibration design (CP5), fixed now — run-1 harness fixes kept
RANDX: uniformly random bars at each feature's own per-slot event count, scored per §5–§7 → expected: no pass, p not concentrated below 0.05. INJ+R / INJ−R: δ = ±3·MDE_h of the cell injected into R_h at RANDOM event bars only (oriented for signed features so the oriented mean shifts by +δ), truth = δ exactly → expected: recovered within 2 SE (σ_h·√(2/n_eff)) with the correct sign. Seeds 11 and 22 via seed sequences [seed, ·] (non-overlapping); pickers seeded by CRC32 (deterministic).

## 10. Head-to-head vs run 1 (fixed now)
Comparison table: for 30 s and 120 s, run 1's shallow `ask_refills` / `bid_refills` cells (from cp6_result_run1.json, hash above; diff in bps per instrument) against run 2's `deep_refill_ask_w` / `deep_refill_bid_w` and the best other deep feature. "Beats run 1" iff the run-2 cell meets §7 AND |diff_bps| exceeds run 1's |diff_bps| on BOTH instruments at the same horizon. Deep vs shallow refill is called stronger / weaker / same by |diff_bps| with the 2-SE bands shown.

## 11. Data
Usable sessions (38): 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17, 2026-07-20, 2026-07-21, 2026-07-22, 2026-07-23, 2026-07-24, 2026-07-27, 2026-07-28, 2026-07-29, 2026-07-30, 2026-07-31, 2026-08-03, 2026-08-04, 2026-08-05, 2026-08-06, 2026-08-07, 2026-08-10, 2026-08-11, 2026-08-12, 2026-08-13, 2026-08-14, 2026-08-18, 2026-08-19, 2026-08-20, 2026-08-21, 2026-08-25, 2026-08-26, 2026-08-27, 2026-08-28, 2026-08-31, 2026-09-01, 2026-09-02, 2026-09-03, 2026-09-04. Excluded: 2026-08-17 and 2026-08-24 (negative ask-side prices, CP0); 07-09 / 07-10 have no depth objects for these instruments. Source: S3 keys in cp0_integrity.json, streamed, zero raw bytes stored.

## 12. Order of operations (attested)
Before this file: CP0 sweep, CP1 build + self-check, feature computation (no forward returns), CP2 counts and UNCONDITIONAL σ_h / median|move|_h over all bars. No event-conditional forward return, no baseline draw, no score computed before this file's hash was recorded.
