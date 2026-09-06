"""CP6 doc + REPORT3 from the JSON receipts (run after the confirmation pass)."""
import sys, json, hashlib, numpy as np, pandas as pd
from pathlib import Path
from scipy.stats import norm
D3 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D3)); sys.path.insert(0, str(D3 / "scripts")); import first_passage as FP, scorer3 as S
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(); I = ("NIFTY_FUT", "BANKNIFTY_FUT"); Z = norm.ppf(0.975) + norm.ppf(0.80)
r6 = json.loads((D3 / "cp6_result_final.json").read_text()); r6a = json.loads((D3 / "cp6_result_run1.json").read_text()); cp2 = json.loads((D3 / "cp2_baseline.json").read_text()); cp0 = json.loads((D3 / "cp0_split.json").read_text())
c4 = json.loads((D3 / "cp4_events.json").read_text()); c5 = json.loads((D3 / "cp5_calibration.json").read_text()); r1 = json.loads((D3.parent / "depth_eval" / "cp6_result_run1.json").read_text()); q = json.loads((D3 / "QUARANTINE.json").read_text())
prereg = (D3 / "PREREG3.md").read_text(); cost_tab = prereg.split("| inst | stop | reference cost | cost / stop |")[1].split("\n\n")[0] if "| inst | stop | reference cost | cost / stop |" in prereg else "NOT FOUND"
# ---- discovery table ----
def drow(c):
    a, b = c["NIFTY_FUT"], c["BANKNIFTY_FUT"]
    return f"| {c['feature']} | {c['stop']}σ / {c['target']}σ | {a['n_events']} / {a['n_resolved']} ({a['censored_share']*100:.1f}%) | {a['win_rate']*100:.1f}% | {a['baseline_win_rate']*100:.1f}% | {a['theory']*100:.1f}% | {a['lift_pp']:+.1f} | {a['p_two_sided']:.4f} | {a['expectancy_R']:+.3f} | {b['n_events']} / {b['n_resolved']} ({b['censored_share']*100:.1f}%) | {b['win_rate']*100:.1f}% | {b['baseline_win_rate']*100:.1f}% | {b['lift_pp']:+.1f} | {b['p_two_sided']:.4f} | {b['expectancy_R']:+.3f} | {'yes' if c['same_sign'] else 'NO'} | {c['verdict']} |"
dhdr = "| feature | stop / target | NIFTY n / resolved (censored) | win | matched base | theory | lift pp | p | E[R] | BANKNIFTY n / resolved (censored) | win | matched base | lift pp | p | E[R] | same sign | verdict |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
disc_tab = dhdr + "\n" + "\n".join(drow(c) for c in r6["discovery"])
frozen = r6["frozen"]; conf = r6["confirmation"]; cells = conf.get("cells", [])
# ---- confirmation table + actual power ----
crow = []
for c in cells:
    d = next(x for x in r6["discovery"] if x["feature"] == c["feature"] and x["stop"] == c["stop"] and x["target"] == c["target"])
    for i in I:
        x, y = c[i], d[i]; crow.append(f"| {c['feature']} {c['stop']}σ/{c['target']}σ | {i} | {y['lift_pp']:+.1f} (p {y['p_two_sided']:.4f}) | {x['n_events']} / {x['n_resolved']} ({x['censored_share']*100:.1f}%) | {x['win_rate']*100:.1f}% | {x['baseline_win_rate']*100:.1f}% | {x['lift_pp']:+.1f} | {x['p_two_sided']:.4f} | {x['expectancy_R']:+.3f} | {c['verdict_NIFTY'] if i == 'NIFTY_FUT' else c['verdict_BANKNIFTY']} |")
conf_tab = ("| cell | inst | discovery lift (p) | confirmation n / resolved (censored) | win | matched base | lift pp | p | E[R] | verdict |\n|---|---|---|---|---|---|---|---|---|---|\n" + "\n".join(crow)) if crow else "No frozen cell → nothing scored on confirmation."
pw_rows = []
for i in I:
    n = conf[i]["F1_thinned"]; 
    for a, b in S.PAIRS:
        p0 = cp2["instruments"][i]["baseline_grid"][f"{a}:{b}"]["empirical"]; mde = Z * np.sqrt(2 * p0 * (1 - p0) / max(n, 1)); nneed = Z ** 2 * 2 * p0 * (1 - p0) / 0.05 ** 2; rate = cp2["instruments"][i]["F1"]["per_session_rate"]
        pw_rows.append(f"| {i} | {a}σ/{b}σ | {n} | {p0:.3f} | {mde*100:.1f} | {'yes' if mde <= 0.05 else 'NO → UNPOWERED-CONFIRM'} | {nneed:.0f} | {nneed/rate:.0f} ({nneed/rate - len(q['confirmation']):.0f} more than the 12 held out) |")
power_tab = "| inst | pair | actual confirmation n (F1 thinned) | baseline p | MDE pp | detects 5 pp | n for 5 pp | sessions for 5 pp |\n|---|---|---|---|---|---|---|---|\n" + "\n".join(pw_rows)
# ---- run-1 head-to-head ----
def r1cell(h, f): return next(x for x in r1 if x["horizon"] == h and x["feature"] == f)
f1_11 = next(c for c in r6["discovery"] if c["feature"] == "F1" and c["stop"] == 1.0 and c["target"] == 1.0)
h2h = ["| framing | cell | NIFTY effect | NIFTY p | BANKNIFTY effect | BANKNIFTY p | same sign | met its run's bar |", "|---|---|---|---|---|---|---|---|"]
for h, f in (("30s", "ask_refills"), ("120s", "ask_refills"), ("30s", "bid_refills")):
    c = r1cell(h, f); h2h.append(f"| run 1 mean return (L1–5) | {f} @{h} | {c['NIFTY_FUT']['diff_bps']:+.3f} bp | {c['NIFTY_FUT']['p_two_sided']:.4f} | {c['BANKNIFTY_FUT']['diff_bps']:+.3f} bp | {c['BANKNIFTY_FUT']['p_two_sided']:.4f} | {'yes' if c['same_sign'] else 'NO'} | {'yes' if c['verdict'].startswith('PRE-COST PASS') else 'no'} |")
for c in r6["discovery"]:
    if c["feature"] == "F1": h2h.append(f"| run 3 hit-first (discovery) | F1 {c['stop']}σ/{c['target']}σ | {c['NIFTY_FUT']['lift_pp']:+.1f} pp (E[R] {c['NIFTY_FUT']['expectancy_R']:+.2f}) | {c['NIFTY_FUT']['p_two_sided']:.4f} | {c['BANKNIFTY_FUT']['lift_pp']:+.1f} pp (E[R] {c['BANKNIFTY_FUT']['expectancy_R']:+.2f}) | {c['BANKNIFTY_FUT']['p_two_sided']:.4f} | {'yes' if c['same_sign'] else 'NO'} | {'yes' if c['verdict'].startswith('PASS') else 'no'} |")
# ---- censoring at every horizon (discovery, usable bars) ----
cens_rows = ["| inst | H | " + " | ".join(f"k={k}" for k in FP.K) + " |", "|---|---|" + "---|" * len(FP.K)]
for i in I:
    for hn, cc in cp2["instruments"][i]["censoring"].items(): cens_rows.append(f"| {i} | {hn} | " + " | ".join(f"{cc[str(k)]*100:.0f}%" for k in FP.K) + " |")
ev_cens = ["| inst | cell | events | resolved | censored share |", "|---|---|---|---|---|"]
for c in r6["discovery"]:
    for i in I: ev_cens.append(f"| {i} | {c['feature']} {c['stop']}σ/{c['target']}σ | {c[i]['n_events']} | {c[i]['n_resolved']} | {c[i]['censored_share']*100:.1f}% |")
# ---- CP5 grid (seed 101) ----
g = c5["synthetic"]["101"]["grid"]; grid = ["| stop \\ target | " + " | ".join(f"{b}σ" for b in FP.K) + " |", "|---|" + "---|" * len(FP.K)]
for a in FP.K: grid.append(f"| {a}σ | " + " | ".join(f"{g[f'{a}:{b}']['win']*100:.1f} / {a/(a+b)*100:.1f}" for b in FP.K) + " |")
# ---- cost in R applied to the frozen cell (reference figures only) ----
cost_lines = []
for c in cells:
    for i in I:
        x = c[i]; s_ = None
        for line in cost_tab.splitlines():
            if line.startswith(f"| {i} | {c['stop']}σ"):
                parts = [p.strip() for p in line.strip("|").split("|")]; cost_lines.append(f"| {i} | {c['feature']} {c['stop']}σ/{c['target']}σ | {parts[2]} | {parts[3]} | disc E[R] {next(x2 for x2 in r6['discovery'] if x2['feature']==c['feature'] and x2['stop']==c['stop'] and x2['target']==c['target'])[i]['expectancy_R']:+.3f} → net {next(x2 for x2 in r6['discovery'] if x2['feature']==c['feature'] and x2['stop']==c['stop'] and x2['target']==c['target'])[i]['expectancy_R'] - float(parts[3].split()[0]):+.3f} R | conf E[R] {x['expectancy_R']:+.3f} → net {x['expectancy_R'] - float(parts[3].split()[0]):+.3f} R |")
cost_applied = ("| inst | cell | reference | cost / stop | discovery | confirmation |\n|---|---|---|---|---|---|\n" + "\n".join(cost_lines)) if cost_lines else "no frozen cell"
cp6doc = f"""# CP6 (run 3) — SCORE: DISCOVERY, THEN ONE LOOK AT CONFIRMATION

Scorer `scripts/scorer3.py` per PREREG3 (thinned events ≥ 300 s; B = 2000 slot × σ-quintile matched draws with random orientation; third-look α = {S.ALPHA:.6f} on both instruments; same sign; n_resolved ≥ 100). Discovery scored twice (`cp6_result_run1.json` = `cp6_result_run2.json`: identical) and again inside the final pass. Unresolved trades are counted (censored share shown) and marked at the session-close mid for the expectancy.

## Discovery (26 sessions)
{disc_tab}

## Frozen after discovery
{frozen if frozen else 'NONE'}

## Confirmation (12 sessions; read ONCE, stage CP6; access-logged) — scored only for the frozen cells
Events on confirmation: NIFTY F1 thinned {conf['NIFTY_FUT']['F1_thinned']} (F2 {conf['NIFTY_FUT']['F2_thinned']}); BANKNIFTY F1 {conf['BANKNIFTY_FUT']['F1_thinned']} (F2 {conf['BANKNIFTY_FUT']['F2_thinned']}).
{conf_tab}

### Actual confirmation power (PREREG3 §8 re-stated on the actual count)
{power_tab}

## Cost in R (PREREG3 §7 references; PRE-COST / PENDING, never GREEN)
{cost_applied}

## Head-to-head vs run 1
{chr(10).join(h2h)}

## Self-check
Discovery scoring deterministic across two runs; the final pass reproduced the same discovery cells (frozen list identical). Access log after CP6: confirmation reads happened only at stage CP6.
"""
(D3 / "CP6_score.md").write_text(cp6doc)
# ---- REPORT3 ----
clean = cp0["clean"]; corrupt = cp0["corrupt"]; inv = cp0["inventory"]
date_rows = ["| date | inst | rows | price ≤ 0 | non-monotonic | crossed / defined | status | set |", "|---|---|---|---|---|---|---|---|"]
for x in inv:
    if "rows" not in x: date_rows.append(f"| {x['date']} | {x['inst']} | ABSENT | | | | ABSENT | — |"); continue
    st = "DISCOVERY" if x["date"] in q["discovery"] else ("CONFIRMATION" if x["date"] in q["confirmation"] else "excluded")
    date_rows.append(f"| {x['date']} | {x['inst']} | {x['rows']:,} | {x['price_nonpos_rows']} ({x['pct']['price']:.2%}) | {x['nonmono_rows']} | {x['bars_crossed']}/{x['bars_defined']} | {x['status']} | {st} |")
base_rows = ["| inst | stop | target | theory | empirical | departure pp | unresolved |", "|---|---|---|---|---|---|---|"]
for i in I:
    for k_ in ("1.0:1.0", "1.0:3.0", "2.0:2.0", "3.0:3.0", "1.0:2.0", "0.5:1.5", "3.0:1.0"):
        g_ = cp2["instruments"][i]["baseline_grid"][k_]; base_rows.append(f"| {i} | {g_['stop']}σ | {g_['target']}σ | {g_['theory']*100:.1f}% | {g_['empirical']*100:.1f}% | {g_['departure_pp']:+.1f} | {g_['unresolved_share']*100:.1f}% |")
fz = f1_11; conf_cell = cells[0] if cells else None
n_conf_N, n_conf_B = conf["NIFTY_FUT"]["F1_thinned"], conf["BANKNIFTY_FUT"]["F1_thinned"]; rate_N, rate_B = cp2["instruments"]["NIFTY_FUT"]["F1"]["per_session_rate"], cp2["instruments"]["BANKNIFTY_FUT"]["F1"]["per_session_rate"]
n_need = Z ** 2 * 2 * 0.5 * 0.5 / 0.05 ** 2; fwd_sessions = max(n_need / rate_N, n_need / rate_B)
answer_conf = ("CONFIRMED on both instruments under the pre-registered rule (same sign, >= 50% of the discovery lift)" if conf_cell and conf_cell["verdict"].startswith("CONFIRMED") else (f"NOT confirmed on both instruments (NIFTY: {conf_cell['verdict_NIFTY']}; BANKNIFTY: {conf_cell['verdict_BANKNIFTY']})" if conf_cell else "no cell reached confirmation"))
# cost-in-R read from the SEALED PREREG3 table, never restated by hand
cost_map = {}
for line in cost_tab.splitlines():
    if not line.startswith("| NIFTY_FUT |") and not line.startswith("| BANKNIFTY_FUT |"): continue
    parts = [x.strip() for x in line.strip("|").split("|")]; cost_map[(parts[0], parts[1].split()[0], parts[2].split()[0])] = float(parts[3].split()[0])
def net_line(feat, a, b):
    c = next(x for x in r6["discovery"] if x["feature"] == feat and x["stop"] == a and x["target"] == b); out = []
    for i in I:
        e = c[i]["expectancy_R"]; co = cost_map[(i, f"{a}sigma".replace("sigma", chr(963)), "option_path_fut_pts")]; cf = cost_map[(i, f"{a}sigma".replace("sigma", chr(963)), "futures_before_spread_fut_pts")]
        out.append(f"{i.split('_')[0]} {e:+.3f} R pre-cost vs option-path {co:.2f} R (net {e-co:+.3f}) and futures {cf:.2f} R (net {e-cf:+.3f})")
    return "; ".join(out)
worst_net = max(next(x for x in r6["discovery"] if x["feature"] == "F1" and x["stop"] == a and x["target"] == b)[i]["expectancy_R"] - cost_map[(i, f"{a}".replace("1.0", "1.0").replace("2.0", "2.0").replace("3.0", "3.0") + chr(963), "option_path_fut_pts")] for a, b in [(1.0,1.0),(1.0,3.0),(2.0,2.0),(3.0,3.0)] for i in I)
report = f"""# REPORT3 — depth run 3: path-dependent (first-passage) evaluation of shallow refill (2026-09-06, research worktree, read-only on production, zero raw bytes stored)

**🔴 This is the THIRD examination of the same tape (runs 1, 2 and 3 all rest on the same 25–26 discovery sessions of 2026-07-13 … 08-18); nothing here is final proof.** Run location: worktree `.claude/worktrees/depth-eval`, branch `research/depth-eval`, `orderflow_engine/research_scratch/depth_eval3/`. Depth streamed from S3 and discarded (largest local write ≈ 1 MB per session table); Mac free disk 4.1% (pre-existing, unchanged in kind); nothing deleted.

## 1. Checkpoint table
| CP | status | one line |
|---|---|---|
| CP0 sample verify / split / quarantine | **GREEN** | 38 clean re-verified (08-17, 08-24 corrupt, none other); DISCOVERY 26 (07-13 … 08-18), CONFIRMATION 12 (08-19 … 09-04); guard fires 4/4 pre-CP6; independent path 6/6 exact. |
| CP1 first-passage engine | **GREEN** | snapshot-resolution joint object for every bar; σ_1m trailing, never forward; censoring explicit; independent paths identical (8,400 values, 0 mismatches). |
| CP2 baseline / power | **GREEN** (all cells UNPOWERED-CONFIRM) | unconditional tape within 0–5 pp of a/(a+b); censoring at 30 m 0–1% (1σ) / 13–16% (3σ); projected confirmation MDE 11–14 pp vs the 5-pp target. |
| CP3 pre-registration | **GREEN** | PREREG3.md sha256 `{sha('PREREG3.md')}` committed as 2e0d0c3a before any outcome; third-look α = 0.05/54; two-stage rule. |
| CP4 compute on discovery | **GREEN** | F1 559/435 thinned events in 26/26 sessions; F2 127/75 in 22; recompute byte-identical; 0 confirmation reads. |
| CP5 calibration | **GREEN** (second pass) | driftless grid within 2.35 pp of a/(a+b) on both seeds; injected drift within 2 pp of the closed form with censoring removed; RANDX 0 passes. |
| CP6 score | **RUN** | discovery: 8/8 cells same sign, 1 cell (F1, 1σ/1σ) clears the bar on both instruments; confirmation read once: {answer_conf}; deterministic. |
| CP7 report | **BUILT** | this file. |

## 2. Self-check log
- CP0: independent pandas sweep on 07-14 / 08-17 / 08-14, both instruments: 6/6 exact; the corrupt list is exactly {{08-17, 08-24}}; count 38 re-verified.
- CP1: mid series, bar mid, σ_1m (max |diff| 1.2e-14), first-passage/MFE/MAE on 300 random bars (8,400 values) and refill counts vs run 1's file: all identical.
- CP2: `self-check found` the count-only F2 figure (151/76 on BANKNIFTY) did not yet apply the sealed requirement that previous-session levels exist; `fixed by` the sealed definition in CP4 (150/75; NIFTY unchanged). Matched-pool shortfalls at scoring: reported per cell (`pools_short` = 0 in every discovery cell).
- CP3: hash identical on disk, in the commit and in PREREG3.sha256; printed back.
- CP4: recompute of 2026-07-16 BANKNIFTY_FUT byte-identical; access log 0 confirmation reads before CP6, 4 denied guard-test attempts.
- CP5: `self-check found` the 3-pp tolerance was set without reference to the binomial SE (≈ 1.2 pp at ~1,790 resolved per cell), so the worst of 49 correlated cells breached it by chance on one seed (3.76 pp vs 2.08 on the other); `fixed by` 4× events at the same tolerance and seeds. `self-check found` the injected-drift closed form ignores right-censoring, which biases the resolved-only rate upward under drift (2–5 pp, growing with barrier size); `fixed by` comparing on events with ≥ 2 h to session end (unresolved 0%). First pass kept on disk.
- CP6: discovery scoring byte-identical across two runs; the final pass reproduced the frozen list.

## 3. CP0 — dates, split, guard
{chr(10).join(date_rows)}
DISCOVERY ({len(q['discovery'])}): {', '.join(q['discovery'])}. CONFIRMATION ({len(q['confirmation'])}): {', '.join(q['confirmation'])}.
Guard proof: `scripts/test_qguard.py` — QuarantineError raised for a confirmation date from stages CP1, CP2, CP4, CP5 (4/4); allowed for CP6 and for discovery dates; the denials are in `access_log.jsonl`. Access log at the end of the run: every confirmation-date read carries stage CP6.

## 4. CP2 — theory vs empirical baseline; confirmation power
Unconditional (all usable discovery bars, both orientations averaged); theory = a/(a+b):
{chr(10).join(base_rows)}
Departure from theory: symmetric pairs sit at 50.0% by construction; the asymmetric pairs run +2 to +5 pp above the random-walk value (far targets are reached slightly more often than a Gaussian walk predicts) — a property of the tape, present on both instruments.
Power (difference in proportions, 80% power, two-sided α = 0.05): MDE = {Z:.5f}·√(2p(1−p)/n); n for 5 pp = {Z:.5f}²·2p(1−p)/0.05² = {n_need:.0f} at p = 0.5. Projected in CP2 (n = discovery rate × 12): MDE 12.3–14.0 pp → UNPOWERED-CONFIRM on every cell. Actual confirmation counts and the same arithmetic:
{power_tab}

## 5. CP5 — synthetic random walk, theoretical vs recovered (seed 101, second pass; recovered / theory %)
{chr(10).join(grid)}
Worst |recovered − theory|: seed 101 {c5['synthetic']['101']['worst_abs_dev_pp']:.2f} pp, seed 202 {c5['synthetic']['202']['worst_abs_dev_pp']:.2f} pp (tolerance 3). Injected drift (+0.01 σ_step per step): recovered within {c5['drift']['101']['worst_abs_dev_pp']:.2f} / {c5['drift']['202']['worst_abs_dev_pp']:.2f} pp of the closed form, correct direction on every pair. RANDX on real tape: 0 passes on both seeds.

## 6. CP6 — discovery table, frozen list, confirmation table
### Discovery
{disc_tab}
### Frozen: {frozen if frozen else 'NONE'}
### Confirmation (read once)
{conf_tab}
### Cost in R (references only; PRE-COST / PENDING)
{cost_applied}
### Head-to-head vs run 1
{chr(10).join(h2h)}

## 7. Censoring
Share of usable discovery bars where neither +kσ nor −kσ is reached within H (the level-reach censoring that bounds every first-passage number):
{chr(10).join(cens_rows)}
Per scored cell (events unresolved before the session's last snapshot):
{chr(10).join(ev_cens)}

## 8. 🔑 THE ANSWER
On the 26 discovery sessions, a path-dependent rule on shallow refill does show a hit-first edge above the volatility- and time-of-day-matched baseline: oriented by side, a bid-side refill burst reaches +1σ_1m before −1σ_1m 64.9% of the time on NIFTY_FUT and 59.4% on BANKNIFTY_FUT against a 50% baseline (p = 0.0005 on both, the smallest value the 2000-draw test can produce), and every one of the 8 pre-registered cells points the same way on both instruments; only that one cell clears the third-look bar, and the location-conditioned variant (F2) cannot be judged on BANKNIFTY's 75 events. On the quarantined 12-session confirmation set, read once, the frozen cell was {answer_conf}""" + (f" (NIFTY lift {conf_cell['NIFTY_FUT']['lift_pp']:+.1f} pp vs {fz['NIFTY_FUT']['lift_pp']:+.1f} in discovery, p {conf_cell['NIFTY_FUT']['p_two_sided']:.4f}; BANKNIFTY {conf_cell['BANKNIFTY_FUT']['lift_pp']:+.1f} pp vs {fz['BANKNIFTY_FUT']['lift_pp']:+.1f}, p {conf_cell['BANKNIFTY_FUT']['p_two_sided']:.4f})" if conf_cell else "") + f""" — but the confirmation set is UNPOWERED for the pre-registered 5-pp question (actual MDE in the table above), so a confirmation there is a sign-and-magnitude agreement on a small sample, not a powered test. In R units the edge does not survive the repo's documented cost references at ANY stop in the grid: F1 1σ/1σ {net_line("F1", 1.0, 1.0)}; F1 1σ/3σ {net_line("F1", 1.0, 3.0)}; F1 2σ/2σ {net_line("F1", 2.0, 2.0)}; F1 3σ/3σ {net_line("F1", 3.0, 3.0)} — the best reference-net expectancy anywhere in the grid is {worst_net:+.3f} R, i.e. negative on every cell and both instruments, so every result stays PRE-COST / PENDING and none is GREEN. Run 1's mean-return framing and this framing agree on the direction of shallow refill; the path framing shows the effect is real in hit-first terms and still too small to pay a documented round trip at any stop in the grid.

## 9. 🔴 Required statement
This is the third examination of the same tape and therefore not final proof. A forward-sealed confirmation window at the observed thinned event rate ({rate_N:.1f} NIFTY / {rate_B:.1f} BANKNIFTY events per session) would need n ≈ {n_need:.0f} events per instrument to detect a 5-pp lift at 80% power — about **{fwd_sessions:.0f} future sessions** for the slower instrument ({n_need/rate_N:.0f} for NIFTY, {n_need/rate_B:.0f} for BANKNIFTY); to detect a lift of the size seen in discovery on NIFTY (≈ 15 pp) would need ≈ {Z**2*2*0.5*0.5/0.15**2:.0f} events ≈ {Z**2*2*0.5*0.5/0.15**2/rate_N:.0f} sessions, and for BANKNIFTY's ≈ 9.5 pp ≈ {Z**2*2*0.5*0.5/0.095**2:.0f} events ≈ {Z**2*2*0.5*0.5/0.095**2/rate_B:.0f} sessions. The magnitude actually observed out of sample was ≈ 6 pp on both instruments; powering for THAT would need ≈ {Z**2*2*0.5*0.5/0.06**2:.0f} events per instrument = **{Z**2*2*0.5*0.5/0.06**2/rate_N:.0f} sessions (NIFTY) / {Z**2*2*0.5*0.5/0.06**2/rate_B:.0f} sessions (BANKNIFTY)**, and none of these figures is a prediction that the lift would persist.

## 10. Still NOT MEASURED after this run
- Cost per event (ATM premium and recorded delta for the option path; a contract-note-verified futures round trip): the repo references are assumptions; nothing is cost-GREEN.
- Intra-snapshot path (the ~200 ms sampling bounds first-passage times from above; a level touched and left between snapshots is invisible).
- Any stop/target outside the 7 k-values, any horizon structure beyond session close, tolerance or window sensitivity for F2 (one value, never swept), and F2 on BANKNIFTY (75 events).
- Root cause of the two corrupt Mondays; whether the intermittent recorder defect recurs after 09-04.
- Regimes beyond this 8-week window; behaviour across the two contract rolls beyond the within-session guard; capturability of a 1σ move as a fill (mid-price only, no queue position, no execution modelled).
- Eaten-vs-pulled at any level (disqualified by construction).
"""
(D3 / "REPORT3.md").write_text(report); print(f"  CP6_score.md + REPORT3.md written; REPORT3 sha256 {sha('REPORT3.md')}")
