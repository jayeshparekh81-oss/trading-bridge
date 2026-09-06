# PREREG3 — RUN 3 (path-dependent / first-passage evaluation of shallow refill), sealed before any event-conditional outcome
Written 2026-09-06 IST. Never edited after this. Frozen by hash: first_passage.py fcd7b41630df4cbb09f67f57f202902e346288c973db72d338d738315cef75f7 ; qguard.py 3cfcabbff65af8d3c5861f157b0ec4fd6ec6966780165f7be6adc93a1843d0ff ; scripts/scorer3.py 72f6fc54157bc2792f1479dde24a80468e406b08262661a2405760df2b0b3a4f ; scripts/cp4_events.py de94f17919eacbc69c08f7d9ef362a585ba775d858861bd42951c4c563759edd ; cp2_baseline.json (F1 thresholds per slot, σ-quintile edges, baseline grid) 18645904a8c5c0ec4fe2797c37f729e8286f88a848311ffc231945387e0a76c3 ; QUARANTINE.json 434b39b1fd04485a195eda8965734863f67e0cf84e961bab80d93efb74df0cb5 ; cp0_split.json 9efe6c5f7b4718a9fc9cb2d100032dcc9728c7a978b695267909a6081efd89e7 ; run-1 result file ../depth_eval/cp6_result_run1.json 4649f422421b85d389a1c0fabe8614a5942f0fdacd9be961d425915e31b7d895.
**This is the THIRD examination of the same tape (runs 1 and 2 used the same 25-of-26 discovery sessions); it is NOT final proof.**

## 1. Features (two families only; nothing swept)
- F1: shallow refill (levels 1–5, unmodified `DepthProxyEngine`): per-bar refill count on a side > the per-slot 99th percentile computed on DISCOVERY bars only (`cp2_baseline.json`), oriented +1 (bid burst → predicted up) / −1 (ask burst → predicted down); bars where both sides fire are dropped. Events thinned to ≥ 300 s apart within a session (greedy) for every test; σ must be defined and the path non-empty.
- F2: F1 conditioned on LOCATION: event bar mid within TOL = 1.0·σ_1m(event) of one of exactly five reference levels — previous clean session's high, low, close (of its 5-s bar-mid series) and the 09:15–09:30 opening-range high/low — eligible after 09:30; undefined on a session with no previous clean session. One tolerance, never swept. No levels 6–20 features.

## 2. (stop, target) grid and horizons
Joint object k ∈ {0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0}·σ_1m; horizons {1m, 5m, 15m, 30m, 60m, 120m, close} for MFE/MAE (descriptive). SCORED pairs (stop, target) in σ: [[1.0, 1.0], [1.0, 3.0], [2.0, 2.0], [3.0, 3.0]] — 4 pairs. Hit-first outcome: resolved if either level is reached before the session's last snapshot; win if the target is reached first; unresolved trades are NOT dropped: the win rate is reported on resolved trades with the censored share alongside, and the expectancy in R (target = b/a R, stop = −1 R) marks unresolved trades at the session-close mid in R. σ_1m: trailing-360-bar realised volatility ending at the previous bar, × √12 (CP1).

## 3. The null — volatility- AND time-of-day-matched random baseline
For each cell: B = 2000 draws; each draw takes, for every thinned event, one non-event usable bar from the same (15-min slot, σ_1m quintile) cell — quintile edges from discovery bars ({ NIFTY_FUT: [3.789, 4.624, 5.397, 6.453], BANKNIFTY_FUT: [10.308, 12.343, 14.793, 18.18] } pts), without replacement within a draw, with a RANDOM orientation ±1 per baseline bar; seed sequences [20260907, draw] (confirmation: [20260908, draw]). Baseline win rate = mean over draws; two-sided empirical p = (1 + #draws with |WR_draw − baseline| ≥ |lift|)/2001. Theory a/(a+b) printed alongside.

## 4. Cross-instrument sign gate
sign(lift) identical on NIFTY_FUT and BANKNIFTY_FUT for the cell; a flip = FAIL regardless of p.

## 5. 🔴 THIRD-LOOK PENALTY
Hypotheses across all three runs: run 1 = 16, run 2 = 30, run 3 = 2 features × 4 pairs = 8 → **54**. Bonferroni: **α = 0.05/54 = 0.000926** per cell, required on BOTH instruments (run 2's bar was 0.001087, run 1's 0.003125). Plus n_resolved ≥ 100 on both.

## 6. Two-stage rule
A cell passes DISCOVERY iff same sign on both instruments AND p ≤ α on both AND n_resolved ≥ 100 on both. Only passing cells are frozen and carried to CONFIRMATION, which is unlocked in CP6 and read exactly once; a frozen cell is CONFIRMED (PRE-COST / PENDING) iff on each instrument the confirmation lift has the same sign as discovery and |lift_conf| ≥ 0.5·|lift_disc|. Confirmation p-values are reported as information, not as a gate. If no cell passes discovery, confirmation is read once only to count events for the actual-n power statement and nothing is scored.

## 7. Cost in R — repo references printed verbatim, expressed as a fraction of the stop distance
`orderflow_engine/TAPE_NOTES.md` lines 710–713 (verbatim; flagged in the repo as 2026-07 ASSUMPTIONS):
```
- **Future round-trip cost ≈ ₹471/lot NIFTY (STT ₹314 alone), ₹517 BANKNIFTY (STT ₹348)** — STT
  (0.02% sell, on notional) dominates → **7.24 future-pts (NIFTY) / 17.2 (BANKNIFTY) of cost BEFORE
  spread**, fixed regardless of R.
- **Option round-trip cost ≈ ₹64/lot (charges) + spread**, /delta → **2.62 future-pts (NIFTY) / 7.96
```
`orderflow_engine/signals/costs.py` lines 23–28 (the registered-rate header; full model verbatim in run 1's PREREG.md):
```python
# --- registered rate knobs (defaults measured/sourced 2026-07; see TAPE_NOTES) --------
# RATES ARE ASSUMPTIONS AS OF 2026-07 — verify against a live Dhan contract note.
DEFAULTS = {
    # brokerage: Dhan F&O is a flat ₹20 per executed order (ASSUMPTION — Dhan published
    # rate; confirm on the account). Round trip = 2 orders.
    "brokerage_per_order_inr": 20.0,
```
Cost as a fraction of the stop distance, using the median σ_1m of DISCOVERY F1 event bars (a count-level quantity: NIFTY 4.81 pts over 1593 raw events; BANKNIFTY 14.07 pts over 930):
| inst | stop | reference cost | cost / stop |
|---|---|---|---|
| NIFTY_FUT | 1.0σ = 4.81 pts (median event σ_1m 4.81) | option_path_fut_pts = 2.62 pts | 0.54 R |
| NIFTY_FUT | 1.0σ = 4.81 pts (median event σ_1m 4.81) | futures_before_spread_fut_pts = 7.24 pts | 1.50 R |
| NIFTY_FUT | 2.0σ = 9.63 pts (median event σ_1m 4.81) | option_path_fut_pts = 2.62 pts | 0.27 R |
| NIFTY_FUT | 2.0σ = 9.63 pts (median event σ_1m 4.81) | futures_before_spread_fut_pts = 7.24 pts | 0.75 R |
| NIFTY_FUT | 3.0σ = 14.44 pts (median event σ_1m 4.81) | option_path_fut_pts = 2.62 pts | 0.18 R |
| NIFTY_FUT | 3.0σ = 14.44 pts (median event σ_1m 4.81) | futures_before_spread_fut_pts = 7.24 pts | 0.50 R |
| BANKNIFTY_FUT | 1.0σ = 14.07 pts (median event σ_1m 14.07) | option_path_fut_pts = 7.96 pts | 0.57 R |
| BANKNIFTY_FUT | 1.0σ = 14.07 pts (median event σ_1m 14.07) | futures_before_spread_fut_pts = 17.2 pts | 1.22 R |
| BANKNIFTY_FUT | 2.0σ = 28.14 pts (median event σ_1m 14.07) | option_path_fut_pts = 7.96 pts | 0.28 R |
| BANKNIFTY_FUT | 2.0σ = 28.14 pts (median event σ_1m 14.07) | futures_before_spread_fut_pts = 17.2 pts | 0.61 R |
| BANKNIFTY_FUT | 3.0σ = 42.21 pts (median event σ_1m 14.07) | option_path_fut_pts = 7.96 pts | 0.19 R |
| BANKNIFTY_FUT | 3.0σ = 42.21 pts (median event σ_1m 14.07) | futures_before_spread_fut_pts = 17.2 pts | 0.41 R |
The option-path reference needs a per-event premium and delta the run does not measure, and the futures reference is a documented assumption; neither is applied as a gate → every result is **PRE-COST / PENDING**, with expectancy net of each reference shown for readability only.

## 8. Power (from CP2, projected; re-stated on the actual confirmation count in CP6)
Cells whose PROJECTED confirmation n cannot detect a 5-pp lift: NIFTY ['1.0:1.0', '1.0:3.0', '2.0:2.0', '3.0:3.0']; BANKNIFTY ['1.0:1.0', '1.0:3.0', '2.0:2.0', '3.0:3.0'] → those cells are marked UNPOWERED-CONFIRM: a confirmation there cannot be called even if signs agree.

## 9. Calibration (CP5), fixed now
Synthetic driftless Gaussian walk at 5 Hz (σ_step = 0.3 pts, 30 sessions × 60 random events, both orientations random) through the REAL engine (trailing σ + joint object): recovered hit-first win rate must be within ±3 pp of a/(a+b) on the full 7×7 grid; injected drift +0.01·σ_step per step compared with the closed form (1−e^(−2μa/s²))/(1−e^(−2μ(a+b)/s²)), same tolerance; RANDX on real discovery tape (matched random events) must pass no cell. Seeds 101 and 202.

## 10. Data
DISCOVERY (26): 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17, 2026-07-20, 2026-07-21, 2026-07-22, 2026-07-23, 2026-07-24, 2026-07-27, 2026-07-28, 2026-07-29, 2026-07-30, 2026-07-31, 2026-08-03, 2026-08-04, 2026-08-05, 2026-08-06, 2026-08-07, 2026-08-10, 2026-08-11, 2026-08-12, 2026-08-13, 2026-08-14, 2026-08-18. CONFIRMATION (12, quarantined until CP6): 2026-08-19, 2026-08-20, 2026-08-21, 2026-08-25, 2026-08-26, 2026-08-27, 2026-08-28, 2026-08-31, 2026-09-01, 2026-09-02, 2026-09-03, 2026-09-04. Excluded corrupt: 2026-08-17, 2026-08-24. Rolls 07-29 and 08-26 handled within-session.

## 11. Head-to-head vs run 1 (fixed now)
Run 1's cross-instrument-consistent cells (ask_refills at 30 s / 120 s, ask_refills_w at 30 s; mean-return framing, from its hashed result file) are placed beside F1's hit-first cells: agreement = same direction (ask-burst → down / bid-burst → up is a positive oriented lift) and whether the pre-registered bar is met in each framing.

## 12. Order of operations (attested)
Before this file: CP0 sweep/split/guard, CP1 build + self-check, CP2 joint object on discovery + UNCONDITIONAL baseline + counts. No event-conditional hit-first rate, no matched draw, no score was computed before this hash was recorded. The confirmation set has not been read by any stage (access log audited in CP4).
