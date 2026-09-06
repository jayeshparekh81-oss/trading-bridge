# REPORT4 — depth run 4: volume-profile feasibility + sealed VP/absorption test — HALTED AT CP0

## 🔴 HALT: hard rule 2 (disk pressure), before any evaluation ran
Hard rule 2 states: *"NEVER DELETE ANY DATA. Disk pressure → STOP and report, do not clean up."* The first measurement of this run
found disk pressure materially worse than the premise the task is built on, so the train was stopped at CP0 and **nothing was deleted**.

| measurement | value |
|---|---|
| task's stated premise | "the Mac is at roughly 4.8% free disk" |
| `df` data volume, measured at run-4 start | **3.57 GiB free of 228.3 GiB = 1.56%**, capacity **99%** |
| APFS container free space (`diskutil`) | **3.8 GB** — no large purgeable reserve masking the figure |
| free space at the END of run 3 (measured, same session) | 9.36 GiB = 4.10% |
| drained between run 3's end and run 4's start | **≈ 5.79 GiB** |
| of which written by this session's run-3 artefacts | 125 MB (`depth_eval3`) |
| therefore drained by something outside this work | **≈ 5.7 GiB — source NOT MEASURED** |
| still draining? two `df` samples 20 s apart | 3.567 GiB → 3.567 GiB (delta −0 MiB); **stable at the moment of measurement** |
| total written by all four runs in this session | 190 MB (`depth_eval` 9.2M, `depth_eval2` 31M, `depth_eval3` 125M, `depth_eval4` 12K) |

Why this stops the run rather than being noted in passing: run 4's own artefacts would be of the same order as run 3's (125 MB of
first-passage tables), and CP1 additionally requires reading the trade tape for every session on top of the depth tape. That is not a
2 GB single write — hard rule 3's explicit threshold is not breached — but running a multi-checkpoint write train onto a volume at 99%
capacity is precisely what hard rule 2 guards against. No cleanup was performed and none is proposed here.

## 1. Checkpoint table
| CP | status | one line |
|---|---|---|
| CP0 tape integrity | **RED — HALTED (hard rule 2, disk)** | The integrity sweep was launched and stopped after ~90 s; its output file was never written. Clean-session count for run 4: **NOT MEASURED**. |
| CP1 volume-profile feasibility | **PENDING — never run** | The decisive gate. Attribution loss, profile stability, decimation convergence and cross-instrument sanity: **all NOT MEASURED**. |
| CP2 feature build | **PENDING — never run** | `vp_absorption.py` not written. |
| CP3 first-passage engine | **PENDING — never run** | |
| CP4 baseline and power | **PENDING — never run** | |
| CP5 split and quarantine | **PENDING — never run** | No `QUARANTINE.json` written; no confirmation set was defined, and therefore none was read. |
| CP6 pre-registration | **PENDING — never run** | No `PREREG4.md`; nothing was sealed because nothing was computed. |
| CP7 calibration | **PENDING — never run** | |
| CP8 score | **PENDING — never run** | No discovery scored, no confirmation opened. |
| CP9 final report | **BUILT** | this file. |

## 2. Self-check log
- `self-check found` the disk premise in the task (≈4.8% free) does not match the machine (1.56% free, 99% capacity); `fixed by` halting
  under hard rule 2 and reporting the measured figures rather than proceeding on the stated premise.
- `self-check found` `df` "available" on APFS can be inflated by purgeable space, so a single reading could overstate pressure;
  `fixed by` cross-reading `diskutil` container free space (3.8 GB — consistent with `df`) and sampling `df` twice 20 s apart to test
  whether the drain was ongoing (it was stable at that moment).
- No other checkpoint ran, so there are no further self-checks to record.

## 3. CP1 — volume-profile feasibility
**NOT MEASURED.** No threshold was computed, so none is reported. The four questions (attribution loss, profile stability across the two
construction methods, intra-session decimation convergence, cross-instrument sanity) remain exactly as open as they were before this run.
The longest-standing open item is **not** closed by this run in either direction.

One observation was made before the halt, while discovering the real S3 key layout by listing (read-only, zero bytes stored). It is
recorded because it is a fact about the tape, and explicitly labelled as **not** a CP1 measurement:
- The trade tape lives at `orderflow/r0/{date}/{SYMBOL}_{security_id}.parquet` (top level of the date prefix), distinct from
  `orderflow/r0/{date}/depth/{SYMBOL}_{security_id}.parquet`. Key layout confirmed by listing, not by template.
- Its 42 columns include `ltt, ltp, ltq, atp, volume, total_buy_qty, total_sell_qty, oi` plus five levels of `bid_price_N/bid_qty_N/
  bid_orders_N` and `ask_price_N/ask_qty_N/ask_orders_N`, and a `packet_type` column.
- In the single file inspected (2026-07-14 NIFTY_FUT, security id 61093): 11,845 rows, `packet_type` ∈ {5, 8}, `ltp` non-null on 11,844
  rows with 540 distinct values, `ltq` with **22 distinct values** (min 65, max 1755), `volume` with 3,695 distinct values.
- This is one instrument-day from one file. It does **not** quantify attribution loss, and the CP1 ratio distribution
  (volume advance ÷ `ltq`) was never computed.

## 4. CP4 baseline vs theory; confirmation power
**NOT MEASURED** — CP4 never ran.

## 5. CP7 random-walk grid and derived tolerance
**NOT MEASURED** — CP7 never ran. No tolerance was derived, because no event count existed to derive it from.

## 6. CP8 discovery table, frozen cells, confirmation table
**NOT MEASURED** — CP8 never ran. No cell was frozen. **The confirmation set was never defined and never read**, so no window was burned
by this run.

## 7. Censoring rate at every horizon
**NOT MEASURED** — the first-passage engine (CP3) never ran in this run.

## 8. 🔑 THE ANSWER
This run cannot answer its question. It halted at CP0 under hard rule 2 because the machine's data volume is at 99% capacity with
3.57 GiB free — roughly a third of the ~4.8% the task assumes, with about 5.7 GiB consumed since run 3 finished by something outside this
work whose source is NOT MEASURED. Nothing was deleted and no cleanup was attempted, as the rule requires. Therefore: whether a volume
profile can be constructed from this tape is **NOT MEASURED** and remains the oldest open item; whether VP-state or absorption features
show a hit-first edge over a volatility-matched baseline is **NOT MEASURED**; no cell was scored, so nothing survived or failed
confirmation, and no cost-in-R statement is available. The one thing this run does establish is negative and about the environment, not
the market: the disk premise the task was written on no longer holds.

## 9. 🔴 Required statement
This would have been the fourth examination of the same tape and would not have been final proof. Because CP1 never ran, the event rate
for a VP or absorption rule is **NOT MEASURED**, so the number of future sessions a forward-sealed window would need **cannot be stated
without inventing a number** — and no number is invented here. For reference only, and explicitly not a substitute: run 3 measured
shallow-refill events at 21.5 (NIFTY) / 16.7 (BANKNIFTY) thinned events per session, which put a 5-pp forward-sealed question at
roughly 73 / 94 future sessions. VP and absorption event rates were never measured and may differ in either direction.

## 10. What is still NOT MEASURED after this run
- Everything CP1 through CP8 would have measured: VP constructibility (attribution loss, POC/VAH/VAL stability across construction
  methods, decimation convergence, cross-instrument sanity), the four A1/A2/A3/B1 features, their first-passage behaviour, baseline,
  power, calibration, discovery and confirmation scores, and cost in R.
- Run 4's own clean-session count and corrupt-date list (the CP0 sweep was stopped before writing its output); runs 2 and 3 independently
  established 38 clean sessions with 2026-08-17 and 2026-08-24 corrupt, but that was **not** re-verified in this run.
- The source of the ≈5.7 GiB consumed on this machine since run 3 ended, and whether the drain resumes; the 20-second sample showed it
  stable, which is not evidence about longer horizons.
- Root cause of the two corrupt Mondays; whether the intermittent recorder defect recurs after 2026-09-04.
- Aggressor tagging, delta, CVD and true footprint remain unmeasurable on this feed by construction, unchanged by this run.
