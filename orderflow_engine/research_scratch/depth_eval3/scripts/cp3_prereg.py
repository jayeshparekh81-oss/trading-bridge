"""CP3 (run 3) — writes CP2_baseline.md and PREREG3.md from the CP2 receipts, prints the SHA256. Run after cp2_baseline.py."""
import sys, json, hashlib, numpy as np, pandas as pd
from pathlib import Path
D3 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D3)); import first_passage as FP
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(); I = ("NIFTY_FUT", "BANKNIFTY_FUT")
cp2 = json.loads((D3 / "cp2_baseline.json").read_text()); q = json.loads((D3 / "QUARANTINE.json").read_text()); OE = D3.parents[1]
# ---- event-level sigma medians (count-level info; no outcome) for the cost-in-R table ----
sig_med = {}
for inst in I:
    thr = cp2["instruments"][inst]["thresholds"]; frames = []
    for d in q["discovery"]: f = pd.read_parquet(D3 / "fp_discovery" / f"{d}_{inst}.parquet", columns=["slot", "sigma_1m", "bid_refills", "ask_refills", "censor_s", "mid"]); frames.append(f)
    df = pd.concat(frames, ignore_index=True); bid = df.bid_refills > df.slot.map({int(k): v for k, v in thr["bid"].items()}); ask = df.ask_refills > df.slot.map({int(k): v for k, v in thr["ask"].items()})
    ev = (bid ^ ask) & df.sigma_1m.notna() & df.censor_s.notna(); sig_med[inst] = {"median_sigma_1m_pts": float(df.sigma_1m[ev].median()), "median_mid": float(df.mid[ev].median()), "n_raw_events": int(ev.sum())}
notes = (OE / "TAPE_NOTES.md").read_text().splitlines(); costs = (OE / "signals/costs.py").read_text().splitlines()
REF = {"NIFTY_FUT": {"option_path_fut_pts": 2.62, "futures_before_spread_fut_pts": 7.24}, "BANKNIFTY_FUT": {"option_path_fut_pts": 7.96, "futures_before_spread_fut_pts": 17.2}}   # verbatim figures from TAPE_NOTES.md 710-713, printed below
cost_rows = []
for inst in I:
    s = sig_med[inst]["median_sigma_1m_pts"]
    for a in (1.0, 2.0, 3.0):
        for name, c in REF[inst].items(): cost_rows.append(f"| {inst} | {a}σ = {a*s:.2f} pts (median event σ_1m {s:.2f}) | {name} = {c} pts | {c/(a*s):.2f} R |")
# ---- CP2 doc ----
lines = []
for inst in I:
    d = cp2["instruments"][inst]; lines.append(f"\n### {inst}: discovery bars {d['bars']:,}, usable (σ and path defined) {d['usable_bars']:,}; F1 raw {d['F1']['raw']} (both-sides-in-one-bar dropped {d['F1']['both_sides_dropped']}), thinned ≥ 300 s **{d['F1']['thinned']}** in {d['F1']['sessions_with_events']} sessions (per-session min/med/max {d['F1']['per_session_min_med_max']}); F2 raw {d['F2']['raw']}, thinned {d['F2']['thinned']}; σ_1m quintile edges {[round(e, 3) for e in d['sigma_quintile_edges']]} pts")
    lines.append("| stop | target | theory a/(a+b) | empirical unconditional (resolved) | departure pp | unresolved share |\n|---|---|---|---|---|---|")
    for k_, g in d["baseline_grid"].items(): lines.append(f"| {g['stop']}σ | {g['target']}σ | {g['theory']*100:.1f}% | {g['empirical']*100:.1f}% | {g['departure_pp']:+.1f} | {g['unresolved_share']*100:.1f}% |")
    lines.append("\nCensoring (neither +kσ nor −kσ reached within H; share of usable bars):\n| H | " + " | ".join(f"k={k}" for k in FP.K) + " |\n|---|" + "---|" * len(FP.K))
    for hn, cc in d["censoring"].items(): lines.append(f"| {hn} | " + " | ".join(f"{cc[str(k)]*100:.0f}%" for k in FP.K) + " |")
    lines.append("\nProjected confirmation power (confirmation NOT read; n = discovery thinned-event rate × 12 sessions):\n| pair | baseline p | projected n | MDE (pp) | detects 5 pp? | n for 5 pp | sessions for 5 pp |\n|---|---|---|---|---|---|---|")
    for k_, pw in d["power_confirmation_projected"].items(): lines.append(f"| {k_} | {pw['baseline_p']:.3f} | {pw['n_conf_projected']:.0f} | {pw['mde_pp']:.1f} | {'yes' if pw['detects_5pp'] else 'NO → UNPOWERED-CONFIRM'} | {pw['n_needed_for_5pp']:.0f} | {pw['sessions_needed_for_5pp']:.0f} |")
Z = cp2["z_sum"]
cp2doc = f"""# CP2 (run 3) — BASELINE AND POWER (no event-conditional outcome read)

Joint object computed for every discovery bar (`fp_discovery/`, 52 sessions, guarded loads at stage CP2). Baseline here is UNCONDITIONAL: all usable bars, both orientations averaged (= random orientation in expectation), win = target reached before stop, resolved bars only, unresolved share shown. Matched (time-of-day × σ-quintile) sampling is applied at scoring. Theory: driftless random walk P(hit +b before −a) = a/(a+b).
MDE for a difference in proportions at 80% power, two-sided α = 0.05: MDE = (z₀.₉₇₅ + z₀.₈₀)·√(2p(1−p)/n) = {Z:.5f}·√(2p(1−p)/n); n for 5 pp = {Z:.5f}² · 2p(1−p) / 0.05².
""" + "\n".join(lines) + """

## Self-check
Independent recount of the matched-baseline pools is performed at scoring (`pools_short` = cells whose non-event pool is smaller than the events needing a match; reported per cell). F1 counts: bid xor ask above threshold, recounted by the pandas mapping in cp3_prereg.py (event-σ medians) — see PREREG3 §7 counts.
"""
(D3 / "CP2_baseline.md").write_text(cp2doc)
# ---- PREREG3 ----
pairs = cp2["pairs_scored"]; unp = {inst: [k_ for k_, pw in cp2["instruments"][inst]["power_confirmation_projected"].items() if not pw["detects_5pp"]] for inst in I}
prereg = f"""# PREREG3 — RUN 3 (path-dependent / first-passage evaluation of shallow refill), sealed before any event-conditional outcome
Written 2026-09-06 IST. Never edited after this. Frozen by hash: first_passage.py {sha('first_passage.py')} ; qguard.py {sha('qguard.py')} ; scripts/scorer3.py {sha('scripts/scorer3.py')} ; scripts/cp4_events.py {sha('scripts/cp4_events.py')} ; cp2_baseline.json (F1 thresholds per slot, σ-quintile edges, baseline grid) {sha('cp2_baseline.json')} ; QUARANTINE.json {sha('QUARANTINE.json')} ; cp0_split.json {sha('cp0_split.json')} ; run-1 result file ../depth_eval/cp6_result_run1.json {sha('../depth_eval/cp6_result_run1.json')}.
**This is the THIRD examination of the same tape (runs 1 and 2 used the same 25-of-26 discovery sessions); it is NOT final proof.**

## 1. Features (two families only; nothing swept)
- F1: shallow refill (levels 1–5, unmodified `DepthProxyEngine`): per-bar refill count on a side > the per-slot 99th percentile computed on DISCOVERY bars only (`cp2_baseline.json`), oriented +1 (bid burst → predicted up) / −1 (ask burst → predicted down); bars where both sides fire are dropped. Events thinned to ≥ 300 s apart within a session (greedy) for every test; σ must be defined and the path non-empty.
- F2: F1 conditioned on LOCATION: event bar mid within TOL = 1.0·σ_1m(event) of one of exactly five reference levels — previous clean session's high, low, close (of its 5-s bar-mid series) and the 09:15–09:30 opening-range high/low — eligible after 09:30; undefined on a session with no previous clean session. One tolerance, never swept. No levels 6–20 features.

## 2. (stop, target) grid and horizons
Joint object k ∈ {{0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0}}·σ_1m; horizons {{1m, 5m, 15m, 30m, 60m, 120m, close}} for MFE/MAE (descriptive). SCORED pairs (stop, target) in σ: {pairs} — 4 pairs. Hit-first outcome: resolved if either level is reached before the session's last snapshot; win if the target is reached first; unresolved trades are NOT dropped: the win rate is reported on resolved trades with the censored share alongside, and the expectancy in R (target = b/a R, stop = −1 R) marks unresolved trades at the session-close mid in R. σ_1m: trailing-360-bar realised volatility ending at the previous bar, × √12 (CP1).

## 3. The null — volatility- AND time-of-day-matched random baseline
For each cell: B = 2000 draws; each draw takes, for every thinned event, one non-event usable bar from the same (15-min slot, σ_1m quintile) cell — quintile edges from discovery bars ({{ {', '.join(f'{i}: {[round(e,3) for e in cp2["instruments"][i]["sigma_quintile_edges"]]}' for i in I)} }} pts), without replacement within a draw, with a RANDOM orientation ±1 per baseline bar; seed sequences [20260907, draw] (confirmation: [20260908, draw]). Baseline win rate = mean over draws; two-sided empirical p = (1 + #draws with |WR_draw − baseline| ≥ |lift|)/2001. Theory a/(a+b) printed alongside.

## 4. Cross-instrument sign gate
sign(lift) identical on NIFTY_FUT and BANKNIFTY_FUT for the cell; a flip = FAIL regardless of p.

## 5. 🔴 THIRD-LOOK PENALTY
Hypotheses across all three runs: run 1 = 16, run 2 = 30, run 3 = 2 features × 4 pairs = 8 → **54**. Bonferroni: **α = 0.05/54 = {0.05/54:.6f}** per cell, required on BOTH instruments (run 2's bar was 0.001087, run 1's 0.003125). Plus n_resolved ≥ 100 on both.

## 6. Two-stage rule
A cell passes DISCOVERY iff same sign on both instruments AND p ≤ α on both AND n_resolved ≥ 100 on both. Only passing cells are frozen and carried to CONFIRMATION, which is unlocked in CP6 and read exactly once; a frozen cell is CONFIRMED (PRE-COST / PENDING) iff on each instrument the confirmation lift has the same sign as discovery and |lift_conf| ≥ 0.5·|lift_disc|. Confirmation p-values are reported as information, not as a gate. If no cell passes discovery, confirmation is read once only to count events for the actual-n power statement and nothing is scored.

## 7. Cost in R — repo references printed verbatim, expressed as a fraction of the stop distance
`orderflow_engine/TAPE_NOTES.md` lines 710–713 (verbatim; flagged in the repo as 2026-07 ASSUMPTIONS):
```
{chr(10).join(notes[709:713])}
```
`orderflow_engine/signals/costs.py` lines 23–28 (the registered-rate header; full model verbatim in run 1's PREREG.md):
```python
{chr(10).join(costs[22:28])}
```
Cost as a fraction of the stop distance, using the median σ_1m of DISCOVERY F1 event bars (a count-level quantity: NIFTY {sig_med['NIFTY_FUT']['median_sigma_1m_pts']:.2f} pts over {sig_med['NIFTY_FUT']['n_raw_events']} raw events; BANKNIFTY {sig_med['BANKNIFTY_FUT']['median_sigma_1m_pts']:.2f} pts over {sig_med['BANKNIFTY_FUT']['n_raw_events']}):
| inst | stop | reference cost | cost / stop |
|---|---|---|---|
{chr(10).join(cost_rows)}
The option-path reference needs a per-event premium and delta the run does not measure, and the futures reference is a documented assumption; neither is applied as a gate → every result is **PRE-COST / PENDING**, with expectancy net of each reference shown for readability only.

## 8. Power (from CP2, projected; re-stated on the actual confirmation count in CP6)
Cells whose PROJECTED confirmation n cannot detect a 5-pp lift: NIFTY {unp['NIFTY_FUT'] or 'none'}; BANKNIFTY {unp['BANKNIFTY_FUT'] or 'none'} → those cells are marked UNPOWERED-CONFIRM: a confirmation there cannot be called even if signs agree.

## 9. Calibration (CP5), fixed now
Synthetic driftless Gaussian walk at 5 Hz (σ_step = 0.3 pts, 30 sessions × 60 random events, both orientations random) through the REAL engine (trailing σ + joint object): recovered hit-first win rate must be within ±3 pp of a/(a+b) on the full 7×7 grid; injected drift +0.01·σ_step per step compared with the closed form (1−e^(−2μa/s²))/(1−e^(−2μ(a+b)/s²)), same tolerance; RANDX on real discovery tape (matched random events) must pass no cell. Seeds 101 and 202.

## 10. Data
DISCOVERY (26): {', '.join(q['discovery'])}. CONFIRMATION (12, quarantined until CP6): {', '.join(q['confirmation'])}. Excluded corrupt: 2026-08-17, 2026-08-24. Rolls 07-29 and 08-26 handled within-session.

## 11. Head-to-head vs run 1 (fixed now)
Run 1's cross-instrument-consistent cells (ask_refills at 30 s / 120 s, ask_refills_w at 30 s; mean-return framing, from its hashed result file) are placed beside F1's hit-first cells: agreement = same direction (ask-burst → down / bid-burst → up is a positive oriented lift) and whether the pre-registered bar is met in each framing.

## 12. Order of operations (attested)
Before this file: CP0 sweep/split/guard, CP1 build + self-check, CP2 joint object on discovery + UNCONDITIONAL baseline + counts. No event-conditional hit-first rate, no matched draw, no score was computed before this hash was recorded. The confirmation set has not been read by any stage (access log audited in CP4).
"""
p = D3 / "PREREG3.md"; p.write_text(prereg); h = sha(p); (D3 / "PREREG3.sha256").write_text(h + "  PREREG3.md\n")
print(f"  CP2_baseline.md written; PREREG3.md {len(prereg.encode())} bytes sha256 {h}")
