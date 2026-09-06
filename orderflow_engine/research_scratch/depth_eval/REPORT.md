# REPORT — depth-proxy evaluation, staged train CP0→CP7 (2026-09-05, research clone, read-only on production)

Run location: git worktree `.claude/worktrees/depth-eval` (branch `research/depth-eval`), directory `orderflow_engine/research_scratch/depth_eval/`. Raw tape streamed from S3, never stored; live recorder, live config, EC2, cron, `data/`, `config.yaml` untouched; nothing deleted.

## 1. Checkpoint table
| CP | status | one line |
|---|---|---|
| CP0 feature audit | **GREEN** | 8 computed metrics classified: refill family ELIGIBLE (6 columns); cancel and wall families DISQUALIFIED (trade-tape attribution). AST self-check: all 15 definitions covered. P6 JSON outputs: NOT FOUND on this machine or in S3. |
| CP1 data inventory | **GREEN** (disk state flagged) | 26 dates, both instruments on all; 66 cols / L20 on all 52 objects; 25 usable (2026-08-17 excluded: negative ask prices); 0 bytes pulled; Mac free disk 4.80% BEFORE the run, 4.50% after (pre-existing, reported, not softened). |
| CP2 power check | **GREEN** (powered subset) | all 6 features powered at 30 s and 120 s on both instruments, 4 at 5 s; session close UNPOWERED for every feature (n_eff = sessions). 16 cells carried. |
| CP3 pre-registration | **GREEN** | PREREG.md sha256 `8fb956b899c542b87c78be5fa6a23b80b56839ce773b5a2413a3d8471a94007c` committed as 03dbcb36 before any event-conditional outcome; disk/commit/record hashes match. Cost model FOUND, printed verbatim, NOT applicable → PRE-COST. |
| CP4 feature computation | **GREEN** | 50 usable sessions recomputed from scratch: byte-identical 50/50; no SINGLE-EPISODE feature (min 15 sessions); two concentration flags (BANKNIFTY bid-side on 07-20). |
| CP5 calibration | **GREEN** (after two self-check fixes) | RANDX 0 passes; clean injection recovered within 2 SE 64/64, sign 64/64; sealed INJ residual proven to be the real effect. |
| CP6 score | **RUN** (no gate) | 3 of 16 cells PRE-COST PASS / PENDING (ask-side refill bursts, 30–120 s, negative on both instruments); 2 sign flips (ratio features); 11 FAIL; run twice, byte-identical. |
| CP7 report | **BUILT** | this file. |

## 2. Self-check log
- CP0: `self-check found` nothing missing — 15 AST definitions all appear in the table; file byte-identical to the shared checkout.
- CP1: `self-check found` the task's key layout `{date}/depth/{INSTRUMENT}.parquet` does not exist (keys carry a security-id suffix; depth feed rolled 61093/61088 → 58072/58067 on 07-29); `fixed by` enumerating the real keys. `self-check found` the re-list compared the wrong path segment and re-listed 0; `fixed by` indexing the date segment → 52/52, 0 size mismatch. `self-check found` 2026-08-17 has negative ask prices (NIFTY price_1..6 < 0 on 70,193/86,095 ask rows; BANKNIFTY price_1 < 0 on 86,517/86,517) although its schema is fine; `fixed by` excluding it with the direct counts recorded.
- CP2: `self-check found` the tick check printed 3.6e-12 (float noise from averaging two prices); `fixed by` a 1e-6 floor → 0.025 pts on both instruments. Independent recount matched all 12 feature counts exactly.
- CP3: PREREG hash identical on disk, in the commit and in PREREG.sha256; printed back from disk.
- CP4: all 50 usable sessions recomputed from scratch → byte-identical and row-identical 50/50.
- CP5: `self-check found` seeds 1 and 2 gave identical numbers (per-draw streams `seed + b` overlap 999/1000) and the RANDX picker used a per-process `hash()`; `fixed by` seed sequences `[seed, b]` and CRC32. `self-check found` the sealed INJ design (δ on real events) cannot separate instrument error from a real effect; `fixed by` adding INJ±R (δ on random events, truth = δ) — scoring rule unchanged.
- CP6: end-to-end re-run byte-identical.
- Judgment recorded for the user: the 15% disk line was already breached on this Mac before the run (4.80% free); the run stored no raw data (outputs 4.4 MB features + JSON/MD) and deleted nothing.

## 3. CP0 tables
ELIGIBLE (depth-only, `price_1..5`, `qty_1..5`, `side`, `ts_recv_ns`): refill events → `bid_refills`, `ask_refills`, `bid_refill_ratio`, `ask_refill_ratio`, `bid_refills_w`, `ask_refills_w` (the file reads only 5 levels; levels 6–20 are never touched by it).
DISQUALIFIED: `cancel` events and `bid/ask_cancel_qty`, `_cancel_qty_w` — `cancel_qty = max(removed − traded_at(p), 0)` subtracts trade-tape volume (eaten-vs-pulled attribution); `wall` events and `bid/ask_walls`, `_walls_w` — the vanishing-wall call requires `traded_at(p) < 0.2·qty` (traded-fraction attribution). Full table: `CP0_feature_audit.md`.

## 4. CP1 truth — sessions and rows used (25 dates × 2 instruments; 2026-08-17 excluded)
| date | inst | rows | bid span (IST) | security id |
|---|---|---|---|---|
| 2026-07-13 | NIFTY_FUT | 163,246 | 09:07:57.442–14:33:04.245 | 61093 |
| 2026-07-13 | BANKNIFTY_FUT | 162,660 | 09:07:57.442–14:33:04.245 | 61088 |
| 2026-07-14 | NIFTY_FUT | 185,696 | 09:05:06.637–15:33:17.900 | 61093 |
| 2026-07-14 | BANKNIFTY_FUT | 187,652 | 09:05:03.633–15:33:16.710 | 61088 |
| 2026-07-15 | NIFTY_FUT | 187,856 | 09:07:34.755–15:33:04.288 | 61093 |
| 2026-07-15 | BANKNIFTY_FUT | 187,220 | 09:15:00.491–15:33:04.288 | 61088 |
| 2026-07-16 | NIFTY_FUT | 187,616 | 09:07:46.401–15:33:01.181 | 61093 |
| 2026-07-16 | BANKNIFTY_FUT | 187,262 | 09:07:46.401–15:32:59.603 | 61088 |
| 2026-07-17 | NIFTY_FUT | 187,496 | 09:07:48.459–15:32:56.061 | 61093 |
| 2026-07-17 | BANKNIFTY_FUT | 187,024 | 09:06:46.081–15:32:56.061 | 61088 |
| 2026-07-20 | NIFTY_FUT | 187,548 | 09:07:03.786–15:33:17.001 | 61093 |
| 2026-07-20 | BANKNIFTY_FUT | 187,164 | 09:15:00.396–15:33:15.377 | 61088 |
| 2026-07-21 | NIFTY_FUT | 187,752 | 09:15:00.288–15:33:05.086 | 61093 |
| 2026-07-21 | BANKNIFTY_FUT | 187,438 | 09:10:40.909–15:33:05.086 | 61088 |
| 2026-07-22 | NIFTY_FUT | 182,346 | 09:25:15.212–15:33:23.192 | 61093 |
| 2026-07-22 | BANKNIFTY_FUT | 182,400 | 09:25:15.212–15:33:23.192 | 61088 |
| 2026-07-23 | NIFTY_FUT | 187,666 | 09:07:06.786–15:34:15.796 | 61093 |
| 2026-07-23 | BANKNIFTY_FUT | 187,646 | 09:09:38.123–15:34:14.587 | 61088 |
| 2026-07-24 | NIFTY_FUT | 187,210 | 09:15:00.379–15:33:16.379 | 61093 |
| 2026-07-24 | BANKNIFTY_FUT | 187,408 | 09:07:52.451–15:33:16.379 | 61088 |
| 2026-07-27 | NIFTY_FUT | 187,466 | 09:15:00.286–15:32:59.467 | 61093 |
| 2026-07-27 | BANKNIFTY_FUT | 187,652 | 09:10:32.549–15:32:59.467 | 61088 |
| 2026-07-28 | NIFTY_FUT | 186,912 | 09:07:24.551–15:33:10.153 | 61093 |
| 2026-07-28 | BANKNIFTY_FUT | 187,202 | 09:07:24.376–15:33:10.153 | 61088 |
| 2026-07-29 | NIFTY_FUT | 149,838 | 09:07:55.580–14:14:16.586 | 58072 |
| 2026-07-29 | BANKNIFTY_FUT | 149,468 | 09:07:55.580–14:14:16.586 | 58067 |
| 2026-07-30 | NIFTY_FUT | 188,334 | 09:07:42.522–15:33:07.381 | 58072 |
| 2026-07-30 | BANKNIFTY_FUT | 187,984 | 09:15:00.180–15:33:07.381 | 58067 |
| 2026-07-31 | NIFTY_FUT | 199,406 | 09:07:55.459–15:33:06.460 | 58072 |
| 2026-07-31 | BANKNIFTY_FUT | 198,966 | 09:07:55.459–15:33:06.460 | 58067 |
| 2026-08-03 | NIFTY_FUT | 222,904 | 09:07:16.434–15:35:04.434 | 58072 |
| 2026-08-03 | BANKNIFTY_FUT | 223,018 | 09:07:16.434–15:35:04.434 | 58067 |
| 2026-08-04 | NIFTY_FUT | 189,824 | 09:07:10.535–15:35:02.399 | 58072 |
| 2026-08-04 | BANKNIFTY_FUT | 189,754 | 09:07:10.535–15:35:02.399 | 58067 |
| 2026-08-05 | NIFTY_FUT | 190,756 | 09:07:14.502–15:35:04.702 | 58072 |
| 2026-08-05 | BANKNIFTY_FUT | 190,622 | 09:07:14.502–15:35:04.702 | 58067 |
| 2026-08-06 | NIFTY_FUT | 190,402 | 09:07:45.627–15:35:01.209 | 58072 |
| 2026-08-06 | BANKNIFTY_FUT | 190,078 | 09:07:45.627–15:35:01.209 | 58067 |
| 2026-08-07 | NIFTY_FUT | 225,640 | 09:07:58.384–15:35:00.583 | 58072 |
| 2026-08-07 | BANKNIFTY_FUT | 225,350 | 09:07:58.384–15:35:00.583 | 58067 |
| 2026-08-10 | NIFTY_FUT | 219,428 | 09:07:42.470–15:35:00.074 | 58072 |
| 2026-08-10 | BANKNIFTY_FUT | 218,914 | 09:07:42.470–15:35:00.074 | 58067 |
| 2026-08-11 | NIFTY_FUT | 196,766 | 09:07:38.595–15:35:01.004 | 58072 |
| 2026-08-11 | BANKNIFTY_FUT | 196,454 | 09:07:38.595–15:35:01.004 | 58067 |
| 2026-08-12 | NIFTY_FUT | 190,682 | 09:07:07.598–15:35:00.198 | 58072 |
| 2026-08-12 | BANKNIFTY_FUT | 190,252 | 09:07:07.598–15:35:00.198 | 58067 |
| 2026-08-13 | NIFTY_FUT | 190,762 | 09:07:59.422–15:35:01.026 | 58072 |
| 2026-08-13 | BANKNIFTY_FUT | 190,502 | 09:07:59.422–15:35:01.026 | 58067 |
| 2026-08-14 | NIFTY_FUT | 189,876 | 09:15:00.382–15:35:01.580 | 58072 |
| 2026-08-14 | BANKNIFTY_FUT | 189,738 | 09:07:29.774–15:35:01.580 | 58067 |
Total rows used: 9,523,256. Bars per session: 4,500 (5 s, 09:15–15:30). Excluded 2026-08-17: NIFTY_FUT 172,190 rows / BANKNIFTY_FUT 173,034 rows with negative ask-side prices.

## 5. CP2 power — MDE per feature (points and bps)
MDE_h = (z₀.₉₇₅ + z₀.₈₀)·σ_h·√(2/n_eff) = 2.80159·σ_h·√(2/n_eff); σ_h = unconditional std of the h-second forward mid change over all bars; bps = MDE / mean mid (NIFTY 24,305.01, BANKNIFTY 57,616.27) × 10⁴; UNPOWERED if MDE > unconditional median |move| at that horizon. Example: NIFTY ask_refills @30 s: 2.80159 × 3.654 × √(2/538) = 0.624 pts.
| inst | feature | h | n_raw | n_eff | σ_h pts | MDE pts | MDE bps | median |move| pts | verdict |
|---|---|---|---|---|---|---|---|---|---|
| NIFTY_FUT | bid_refills | 5s | 820 | 820 | 1.580 | 0.219 | 0.09 | 0.450 | POWERED |
| NIFTY_FUT | bid_refills | 30s | 820 | 621 | 3.654 | 0.581 | 0.24 | 1.750 | POWERED |
| NIFTY_FUT | bid_refills | 120s | 820 | 445 | 7.348 | 1.380 | 0.57 | 3.950 | POWERED |
| NIFTY_FUT | bid_refills | close | 820 | 24 | 55.098 | 44.560 | 18.33 | 29.950 | UNPOWERED |
| NIFTY_FUT | ask_refills | 5s | 754 | 754 | 1.580 | 0.228 | 0.09 | 0.450 | POWERED |
| NIFTY_FUT | ask_refills | 30s | 754 | 539 | 3.654 | 0.624 | 0.26 | 1.750 | POWERED |
| NIFTY_FUT | ask_refills | 120s | 754 | 390 | 7.348 | 1.474 | 0.61 | 3.950 | POWERED |
| NIFTY_FUT | ask_refills | close | 754 | 23 | 55.098 | 45.519 | 18.73 | 29.950 | UNPOWERED |
| NIFTY_FUT | bid_refill_ratio | 5s | 264 | 264 | 1.580 | 0.385 | 0.16 | 0.450 | POWERED |
| NIFTY_FUT | bid_refill_ratio | 30s | 264 | 251 | 3.654 | 0.914 | 0.38 | 1.750 | POWERED |
| NIFTY_FUT | bid_refill_ratio | 120s | 264 | 229 | 7.348 | 1.924 | 0.79 | 3.950 | POWERED |
| NIFTY_FUT | bid_refill_ratio | close | 264 | 25 | 55.098 | 43.660 | 17.96 | 29.950 | UNPOWERED |
| NIFTY_FUT | ask_refill_ratio | 5s | 181 | 181 | 1.580 | 0.465 | 0.19 | 0.450 | UNPOWERED |
| NIFTY_FUT | ask_refill_ratio | 30s | 181 | 173 | 3.654 | 1.101 | 0.45 | 1.750 | POWERED |
| NIFTY_FUT | ask_refill_ratio | 120s | 181 | 157 | 7.348 | 2.323 | 0.96 | 3.950 | POWERED |
| NIFTY_FUT | ask_refill_ratio | close | 181 | 24 | 55.098 | 44.560 | 18.33 | 29.950 | UNPOWERED |
| NIFTY_FUT | bid_refills_w | 5s | 1017 | 1017 | 1.580 | 0.196 | 0.08 | 0.450 | POWERED |
| NIFTY_FUT | bid_refills_w | 30s | 1017 | 276 | 3.654 | 0.871 | 0.36 | 1.750 | POWERED |
| NIFTY_FUT | bid_refills_w | 120s | 1017 | 171 | 7.348 | 2.226 | 0.92 | 3.950 | POWERED |
| NIFTY_FUT | bid_refills_w | close | 1017 | 15 | 55.098 | 56.365 | 23.19 | 29.950 | UNPOWERED |
| NIFTY_FUT | ask_refills_w | 5s | 978 | 978 | 1.580 | 0.200 | 0.08 | 0.450 | POWERED |
| NIFTY_FUT | ask_refills_w | 30s | 978 | 256 | 3.654 | 0.905 | 0.37 | 1.750 | POWERED |
| NIFTY_FUT | ask_refills_w | 120s | 978 | 144 | 7.348 | 2.426 | 1.00 | 3.950 | POWERED |
| NIFTY_FUT | ask_refills_w | close | 978 | 17 | 55.098 | 52.946 | 21.78 | 29.950 | UNPOWERED |
| BANKNIFTY_FUT | bid_refills | 5s | 575 | 575 | 4.507 | 0.745 | 0.13 | 1.000 | POWERED |
| BANKNIFTY_FUT | bid_refills | 30s | 575 | 418 | 10.812 | 2.095 | 0.36 | 4.700 | POWERED |
| BANKNIFTY_FUT | bid_refills | 120s | 575 | 319 | 22.528 | 4.998 | 0.87 | 10.800 | POWERED |
| BANKNIFTY_FUT | bid_refills | close | 575 | 24 | 180.380 | 145.882 | 25.32 | 76.200 | UNPOWERED |
| BANKNIFTY_FUT | ask_refills | 5s | 363 | 363 | 4.507 | 0.937 | 0.16 | 1.000 | POWERED |
| BANKNIFTY_FUT | ask_refills | 30s | 363 | 331 | 10.812 | 2.355 | 0.41 | 4.700 | POWERED |
| BANKNIFTY_FUT | ask_refills | 120s | 363 | 261 | 22.528 | 5.525 | 0.96 | 10.800 | POWERED |
| BANKNIFTY_FUT | ask_refills | close | 363 | 25 | 180.380 | 142.935 | 24.81 | 76.200 | UNPOWERED |
| BANKNIFTY_FUT | bid_refill_ratio | 5s | 107 | 107 | 4.507 | 1.726 | 0.30 | 1.000 | UNPOWERED |
| BANKNIFTY_FUT | bid_refill_ratio | 30s | 107 | 106 | 10.812 | 4.161 | 0.72 | 4.700 | POWERED |
| BANKNIFTY_FUT | bid_refill_ratio | 120s | 107 | 100 | 22.528 | 8.926 | 1.55 | 10.800 | POWERED |
| BANKNIFTY_FUT | bid_refill_ratio | close | 107 | 23 | 180.380 | 149.020 | 25.86 | 76.200 | UNPOWERED |
| BANKNIFTY_FUT | ask_refill_ratio | 5s | 98 | 98 | 4.507 | 1.804 | 0.31 | 1.000 | UNPOWERED |
| BANKNIFTY_FUT | ask_refill_ratio | 30s | 98 | 94 | 10.812 | 4.418 | 0.77 | 4.700 | POWERED |
| BANKNIFTY_FUT | ask_refill_ratio | 120s | 98 | 85 | 22.528 | 9.681 | 1.68 | 10.800 | POWERED |
| BANKNIFTY_FUT | ask_refill_ratio | close | 98 | 23 | 180.380 | 149.020 | 25.86 | 76.200 | UNPOWERED |
| BANKNIFTY_FUT | bid_refills_w | 5s | 911 | 911 | 4.507 | 0.592 | 0.10 | 1.000 | POWERED |
| BANKNIFTY_FUT | bid_refills_w | 30s | 911 | 224 | 10.812 | 2.862 | 0.50 | 4.700 | POWERED |
| BANKNIFTY_FUT | bid_refills_w | 120s | 911 | 129 | 22.528 | 7.859 | 1.36 | 10.800 | POWERED |
| BANKNIFTY_FUT | bid_refills_w | close | 911 | 19 | 180.380 | 163.957 | 28.46 | 76.200 | UNPOWERED |
| BANKNIFTY_FUT | ask_refills_w | 5s | 866 | 866 | 4.507 | 0.607 | 0.11 | 1.000 | POWERED |
| BANKNIFTY_FUT | ask_refills_w | 30s | 866 | 238 | 10.812 | 2.777 | 0.48 | 4.700 | POWERED |
| BANKNIFTY_FUT | ask_refills_w | 120s | 866 | 145 | 22.528 | 7.412 | 1.29 | 10.800 | POWERED |
| BANKNIFTY_FUT | ask_refills_w | close | 866 | 24 | 180.380 | 145.882 | 25.32 | 76.200 | UNPOWERED |

## 6. CP5 calibration — injected vs recovered
| exam | size | recovery | sign | note |
|---|---|---|---|---|
| RANDX | 32 cells × 2 inst | passes 0 | p<0.05 on 1/64 (≈3.2 expected) | min p 0.050, median 0.551 |
| INJ+ | 32 cells × 2 inst | within 2 SE 36/64 | correct sign 64/64 | residual = real effect (identical INJ+/INJ− 64/64) |
| INJ- | 32 cells × 2 inst | within 2 SE 36/64 | correct sign 64/64 | residual = real effect (identical INJ+/INJ− 64/64) |
| INJ+R | 32 cells × 2 inst | within 2 SE 64/64 | correct sign 64/64 | truth = δ exactly (random events) |
| INJ-R | 32 cells × 2 inst | within 2 SE 64/64 | correct sign 64/64 | truth = δ exactly (random events) |
Examples (INJ±R, seed 1, 5 s):
| h | feature | inst | injected pts | recovered pts | SE pts |
|---|---|---|---|---|---|
| 5s | bid_refills | NIFTY_FUT | +0.656 | +0.574 | 0.079 |
| 5s | bid_refills | BANKNIFTY_FUT | +2.234 | +2.348 | 0.269 |
| 5s | ask_refills | NIFTY_FUT | +0.684 | +0.711 | 0.082 |
| 5s | ask_refills | BANKNIFTY_FUT | +2.812 | +2.599 | 0.339 |
| 5s | bid_refills_w | NIFTY_FUT | +0.589 | +0.580 | 0.070 |
| 5s | bid_refills_w | BANKNIFTY_FUT | +1.775 | +1.883 | 0.213 |
| 5s | bid_refills | NIFTY_FUT | -0.656 | -0.737 | 0.079 |
| 5s | bid_refills | BANKNIFTY_FUT | -2.234 | -2.120 | 0.269 |
| 5s | ask_refills | NIFTY_FUT | -0.684 | -0.657 | 0.082 |
| 5s | ask_refills | BANKNIFTY_FUT | -2.812 | -3.024 | 0.339 |
| 5s | bid_refills_w | NIFTY_FUT | -0.589 | -0.598 | 0.070 |
| 5s | bid_refills_w | BANKNIFTY_FUT | -1.775 | -1.666 | 0.213 |

## 7. CP6 result table (cross-instrument sign column visible)
| h | feature | NIFTY n_eff | NIFTY diff pts | NIFTY diff bps | NIFTY p | BANKNIFTY n_eff | BANKNIFTY diff pts | BANKNIFTY diff bps | BANKNIFTY p | same sign | verdict | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5s | bid_refills | 820 | +0.222 | +0.091 | 0.001 | 575 | +0.401 | +0.070 | 0.024 | yes | FAIL | PRE-COST / PENDING |
| 5s | ask_refills | 754 | -0.296 | -0.122 | 0.001 | 363 | -0.693 | -0.120 | 0.005 | yes | FAIL | PRE-COST / PENDING |
| 5s | bid_refills_w | 1017 | +0.130 | +0.054 | 0.009 | 911 | +0.444 | +0.077 | 0.003 | yes | FAIL | PRE-COST / PENDING |
| 5s | ask_refills_w | 978 | -0.176 | -0.073 | 0.002 | 866 | -0.379 | -0.066 | 0.007 | yes | FAIL | PRE-COST / PENDING |
| 30s | bid_refills | 619 | +0.925 | +0.381 | 0.001 | 417 | +1.120 | +0.194 | 0.022 | yes | FAIL | PRE-COST / PENDING |
| 30s | ask_refills | 538 | -1.275 | -0.525 | 0.001 | 331 | -2.939 | -0.510 | 0.001 | yes | PRE-COST PASS / PENDING | PRE-COST / PENDING |
| 30s | bid_refill_ratio | 250 | +0.190 | +0.078 | 0.425 | 106 | -0.673 | -0.117 | 0.519 | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | ask_refill_ratio | 171 | -0.132 | -0.054 | 0.629 | 94 | -1.429 | -0.248 | 0.221 | yes | FAIL | PRE-COST / PENDING |
| 30s | bid_refills_w | 275 | +0.646 | +0.266 | 0.005 | 224 | +1.755 | +0.305 | 0.014 | yes | FAIL | PRE-COST / PENDING |
| 30s | ask_refills_w | 256 | -0.942 | -0.388 | 0.001 | 238 | -2.293 | -0.398 | 0.003 | yes | PRE-COST PASS / PENDING | PRE-COST / PENDING |
| 120s | bid_refills | 438 | +0.932 | +0.384 | 0.004 | 317 | +2.064 | +0.358 | 0.075 | yes | FAIL | PRE-COST / PENDING |
| 120s | ask_refills | 385 | -1.646 | -0.677 | 0.001 | 261 | -4.831 | -0.838 | 0.001 | yes | PRE-COST PASS / PENDING | PRE-COST / PENDING |
| 120s | bid_refill_ratio | 228 | -0.237 | -0.097 | 0.609 | 100 | -1.835 | -0.318 | 0.423 | yes | FAIL | PRE-COST / PENDING |
| 120s | ask_refill_ratio | 155 | +0.287 | +0.118 | 0.632 | 85 | -0.860 | -0.149 | 0.720 | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 120s | bid_refills_w | 169 | +1.314 | +0.541 | 0.024 | 129 | +2.571 | +0.446 | 0.201 | yes | FAIL | PRE-COST / PENDING |
| 120s | ask_refills_w | 144 | -1.981 | -0.815 | 0.003 | 145 | -3.853 | -0.669 | 0.042 | yes | FAIL | PRE-COST / PENDING |
| close | bid_refills | 820 | -12.359 | -5.085 | 0.001 | 575 | +34.811 | +6.042 | 0.001 | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | ask_refills | 754 | -0.041 | -0.017 | 0.983 | 363 | +33.962 | +5.895 | 0.001 | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | bid_refill_ratio | 264 | -2.047 | -0.842 | 0.544 | 107 | -2.326 | -0.404 | 0.904 | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | ask_refill_ratio | 181 | +6.845 | +2.816 | 0.095 | 98 | +36.676 | +6.366 | 0.060 | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | bid_refills_w | 1017 | -16.499 | -6.788 | 0.001 | 911 | +25.946 | +4.503 | 0.001 | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | ask_refills_w | 978 | +2.288 | +0.941 | 0.200 | 866 | +53.599 | +9.303 | 0.001 | yes | UNPOWERED — not scored | PRE-COST / PENDING |
Pass bar (PREREG §7): same sign on both, p ≤ 0.003125 on both, n_eff ≥ 100 on both. Cost model not applicable → no cell is GREEN.

## 8. THE ANSWER
On the 25 usable sessions (2026-07-13 → 2026-08-14) the banked 5-level slice of the 20-level book does carry a readable, aggressor-free signal at the 30–120 second horizon, and the sample is large enough to see it there: bursts of ask-side refills (top 1% of the time-of-day-normalised count) are followed by a lower mid-price on both NIFTY_FUT and BANKNIFTY_FUT, passing the pre-registered bar on three cells that are really one feature (ask_refills at 30 s and 120 s, and its rolling sum at 30 s), with the bid-side mirror pointing the same way on both instruments but not clearing the Bonferroni bar on BANKNIFTY; the effect is small — about 0.5 bps of mid at 30 s and 0.7–0.8 bps at 120 s (NIFTY −1.3 to −1.6 points, BANKNIFTY −2.9 to −4.8 points), below the repo's own documented round-trip cost references, and it is PRE-COST / PENDING because the repo's cost model cannot be applied without per-event option premium and delta. The ratio features carry nothing (sign flips, p ≥ 0.2). For the session-close horizon the honest answer is that the sample cannot tell: with 15–25 independent sessions the minimum detectable effect is 44–56 NIFTY points / 143–164 BANKNIFTY points, and the close-horizon numbers flip sign between instruments. Nothing about eaten-vs-pulled, cancellation pressure or vanishing walls was evaluated, because those features are unmeasurable on this feed by construction.

## 9. Still NOT MEASURED after this run
- Anything in levels 6–20: `depth_proxies.py` reads only 5 levels; no 20-level feature exists in the file to evaluate.
- The contents, key structure and value ranges of the P6 JSON outputs (`analysis/2026-07-14/`, `analysis/2026-07-20/…`, `research_scratch/joinroot/2026-07-20/`): not on this machine, not in S3.
- Cost per event: the repo model needs an ATM option premium and a recorded delta per event; not computed. Every result stays PRE-COST / PENDING.
- Eaten-vs-pulled, cancel pressure, vanishing walls: DISQUALIFIED, not measured (feed cannot support them).
- The root cause of the 2026-08-17 negative ask-side prices (and whether any date after 08-17 — 16 more date prefixes exist in the bucket, outside this run's window — shares it).
- Persistence beyond 120 s and to session close (unpowered); stability across market regimes (25 sessions, one five-week window, one contract roll); whether the mid-price move is capturable as a fill (mid-price only, no execution modelled).
- Sensitivity to the engine's parameters (levels, k_refill, near_ticks, bar length, window) and to the trigger quantile: one pre-registered configuration only.
