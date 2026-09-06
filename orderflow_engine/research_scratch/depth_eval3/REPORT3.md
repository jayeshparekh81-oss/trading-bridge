# REPORT3 — depth run 3: path-dependent (first-passage) evaluation of shallow refill (2026-09-06, research worktree, read-only on production, zero raw bytes stored)

**🔴 This is the THIRD examination of the same tape (runs 1, 2 and 3 all rest on the same 25–26 discovery sessions of 2026-07-13 … 08-18); nothing here is final proof.** Run location: worktree `.claude/worktrees/depth-eval`, branch `research/depth-eval`, `orderflow_engine/research_scratch/depth_eval3/`. Depth streamed from S3 and discarded (largest local write ≈ 1 MB per session table); Mac free disk 4.1% (pre-existing, unchanged in kind); nothing deleted.

## 1. Checkpoint table
| CP | status | one line |
|---|---|---|
| CP0 sample verify / split / quarantine | **GREEN** | 38 clean re-verified (08-17, 08-24 corrupt, none other); DISCOVERY 26 (07-13 … 08-18), CONFIRMATION 12 (08-19 … 09-04); guard fires 4/4 pre-CP6; independent path 6/6 exact. |
| CP1 first-passage engine | **GREEN** | snapshot-resolution joint object for every bar; σ_1m trailing, never forward; censoring explicit; independent paths identical (8,400 values, 0 mismatches). |
| CP2 baseline / power | **GREEN** (all cells UNPOWERED-CONFIRM) | unconditional tape within 0–5 pp of a/(a+b); censoring at 30 m 0–1% (1σ) / 13–16% (3σ); projected confirmation MDE 11–14 pp vs the 5-pp target. |
| CP3 pre-registration | **GREEN** | PREREG3.md sha256 `03b606a98481509332bb306756b99abe9e9a54eaf33def8ba079c8a78a3098a8` committed as 2e0d0c3a before any outcome; third-look α = 0.05/54; two-stage rule. |
| CP4 compute on discovery | **GREEN** | F1 559/435 thinned events in 26/26 sessions; F2 127/75 in 22; recompute byte-identical; 0 confirmation reads. |
| CP5 calibration | **GREEN** (second pass) | driftless grid within 2.35 pp of a/(a+b) on both seeds; injected drift within 2 pp of the closed form with censoring removed; RANDX 0 passes. |
| CP6 score | **RUN** | discovery: 8/8 cells same sign, 1 cell (F1, 1σ/1σ) clears the bar on both instruments; confirmation read once: NOT confirmed on both instruments (NIFTY: FAIL confirmation (magnitude < 50% of discovery); BANKNIFTY: CONFIRMED (PRE-COST / PENDING)); deterministic. |
| CP7 report | **BUILT** | this file. |

## 2. Self-check log
- CP0: independent pandas sweep on 07-14 / 08-17 / 08-14, both instruments: 6/6 exact; the corrupt list is exactly {08-17, 08-24}; count 38 re-verified.
- CP1: mid series, bar mid, σ_1m (max |diff| 1.2e-14), first-passage/MFE/MAE on 300 random bars (8,400 values) and refill counts vs run 1's file: all identical.
- CP2: `self-check found` the count-only F2 figure (151/76 on BANKNIFTY) did not yet apply the sealed requirement that previous-session levels exist; `fixed by` the sealed definition in CP4 (150/75; NIFTY unchanged). Matched-pool shortfalls at scoring: reported per cell (`pools_short` = 0 in every discovery cell).
- CP3: hash identical on disk, in the commit and in PREREG3.sha256; printed back.
- CP4: recompute of 2026-07-16 BANKNIFTY_FUT byte-identical; access log 0 confirmation reads before CP6, 4 denied guard-test attempts.
- CP5: `self-check found` the 3-pp tolerance was set without reference to the binomial SE (≈ 1.2 pp at ~1,790 resolved per cell), so the worst of 49 correlated cells breached it by chance on one seed (3.76 pp vs 2.08 on the other); `fixed by` 4× events at the same tolerance and seeds. `self-check found` the injected-drift closed form ignores right-censoring, which biases the resolved-only rate upward under drift (2–5 pp, growing with barrier size); `fixed by` comparing on events with ≥ 2 h to session end (unresolved 0%). First pass kept on disk.
- CP6: discovery scoring byte-identical across two runs; the final pass reproduced the frozen list.

## 3. CP0 — dates, split, guard
| date | inst | rows | price ≤ 0 | non-monotonic | crossed / defined | status | set |
|---|---|---|---|---|---|---|---|
| 2026-07-09 | NIFTY_FUT | ABSENT | | | | ABSENT | — |
| 2026-07-09 | BANKNIFTY_FUT | ABSENT | | | | ABSENT | — |
| 2026-07-10 | NIFTY_FUT | ABSENT | | | | ABSENT | — |
| 2026-07-10 | BANKNIFTY_FUT | ABSENT | | | | ABSENT | — |
| 2026-07-13 | NIFTY_FUT | 163,246 | 0 (0.00%) | 0 | 0/3815 | USABLE | DISCOVERY |
| 2026-07-13 | BANKNIFTY_FUT | 162,660 | 0 (0.00%) | 0 | 1/3814 | USABLE | DISCOVERY |
| 2026-07-14 | NIFTY_FUT | 185,696 | 92 (0.05%) | 0 | 0/4487 | USABLE | DISCOVERY |
| 2026-07-14 | BANKNIFTY_FUT | 187,652 | 40 (0.02%) | 2 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-15 | NIFTY_FUT | 187,856 | 7 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-15 | BANKNIFTY_FUT | 187,220 | 8 (0.00%) | 0 | 1/4500 | USABLE | DISCOVERY |
| 2026-07-16 | NIFTY_FUT | 187,616 | 10 (0.01%) | 1 | 1/4500 | USABLE | DISCOVERY |
| 2026-07-16 | BANKNIFTY_FUT | 187,262 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-17 | NIFTY_FUT | 187,496 | 2 (0.00%) | 1 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-17 | BANKNIFTY_FUT | 187,024 | 14 (0.01%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-20 | NIFTY_FUT | 187,548 | 9 (0.00%) | 0 | 1/4500 | USABLE | DISCOVERY |
| 2026-07-20 | BANKNIFTY_FUT | 187,164 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-21 | NIFTY_FUT | 187,752 | 2 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-21 | BANKNIFTY_FUT | 187,438 | 8 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-22 | NIFTY_FUT | 182,346 | 0 (0.00%) | 1 | 0/4377 | USABLE | DISCOVERY |
| 2026-07-22 | BANKNIFTY_FUT | 182,400 | 2 (0.00%) | 0 | 0/4377 | USABLE | DISCOVERY |
| 2026-07-23 | NIFTY_FUT | 187,666 | 12 (0.01%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-23 | BANKNIFTY_FUT | 187,646 | 4 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-24 | NIFTY_FUT | 187,210 | 6 (0.00%) | 0 | 0/4499 | USABLE | DISCOVERY |
| 2026-07-24 | BANKNIFTY_FUT | 187,408 | 10 (0.01%) | 0 | 0/4499 | USABLE | DISCOVERY |
| 2026-07-27 | NIFTY_FUT | 187,466 | 0 (0.00%) | 1 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-27 | BANKNIFTY_FUT | 187,652 | 2 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-28 | NIFTY_FUT | 186,912 | 6 (0.00%) | 0 | 0/4499 | USABLE | DISCOVERY |
| 2026-07-28 | BANKNIFTY_FUT | 187,202 | 9 (0.00%) | 1 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-29 | NIFTY_FUT | 149,838 | 0 (0.00%) | 0 | 0/3590 | USABLE | DISCOVERY |
| 2026-07-29 | BANKNIFTY_FUT | 149,468 | 0 (0.00%) | 0 | 1/3590 | USABLE | DISCOVERY |
| 2026-07-30 | NIFTY_FUT | 188,334 | 2 (0.00%) | 0 | 1/4500 | USABLE | DISCOVERY |
| 2026-07-30 | BANKNIFTY_FUT | 187,984 | 4 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-31 | NIFTY_FUT | 199,406 | 2 (0.00%) | 1 | 0/4500 | USABLE | DISCOVERY |
| 2026-07-31 | BANKNIFTY_FUT | 198,966 | 2 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-03 | NIFTY_FUT | 222,904 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-03 | BANKNIFTY_FUT | 223,018 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-04 | NIFTY_FUT | 189,824 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-04 | BANKNIFTY_FUT | 189,754 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-05 | NIFTY_FUT | 190,756 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-05 | BANKNIFTY_FUT | 190,622 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-06 | NIFTY_FUT | 190,402 | 0 (0.00%) | 1 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-06 | BANKNIFTY_FUT | 190,078 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-07 | NIFTY_FUT | 225,640 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-07 | BANKNIFTY_FUT | 225,350 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-10 | NIFTY_FUT | 219,428 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-10 | BANKNIFTY_FUT | 218,914 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-11 | NIFTY_FUT | 196,766 | 0 (0.00%) | 0 | 0/4498 | USABLE | DISCOVERY |
| 2026-08-11 | BANKNIFTY_FUT | 196,454 | 0 (0.00%) | 0 | 0/4498 | USABLE | DISCOVERY |
| 2026-08-12 | NIFTY_FUT | 190,682 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-12 | BANKNIFTY_FUT | 190,252 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-13 | NIFTY_FUT | 190,762 | 0 (0.00%) | 1 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-13 | BANKNIFTY_FUT | 190,502 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-14 | NIFTY_FUT | 189,876 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-14 | BANKNIFTY_FUT | 189,738 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-17 | NIFTY_FUT | 172,190 | 70193 (40.76%) | 1 | 0/703 | UNUSABLE | excluded |
| 2026-08-17 | BANKNIFTY_FUT | 173,034 | 86517 (50.00%) | 0 | 0/0 | UNUSABLE | excluded |
| 2026-08-18 | NIFTY_FUT | 189,508 | 0 (0.00%) | 0 | 0/4500 | USABLE | DISCOVERY |
| 2026-08-18 | BANKNIFTY_FUT | 189,154 | 0 (0.00%) | 0 | 1/4500 | USABLE | DISCOVERY |
| 2026-08-19 | NIFTY_FUT | 192,660 | 0 (0.00%) | 0 | 0/4500 | USABLE | CONFIRMATION |
| 2026-08-19 | BANKNIFTY_FUT | 192,642 | 0 (0.00%) | 0 | 0/4500 | USABLE | CONFIRMATION |
| 2026-08-20 | NIFTY_FUT | 189,606 | 0 (0.00%) | 0 | 0/4500 | USABLE | CONFIRMATION |
| 2026-08-20 | BANKNIFTY_FUT | 189,930 | 0 (0.00%) | 0 | 0/4500 | USABLE | CONFIRMATION |
| 2026-08-21 | NIFTY_FUT | 190,174 | 0 (0.00%) | 0 | 0/4500 | USABLE | CONFIRMATION |
| 2026-08-21 | BANKNIFTY_FUT | 190,160 | 0 (0.00%) | 0 | 0/4500 | USABLE | CONFIRMATION |
| 2026-08-24 | NIFTY_FUT | 174,498 | 5098 (2.92%) | 0 | 0/3823 | UNUSABLE | excluded |
| 2026-08-24 | BANKNIFTY_FUT | 188,784 | 2053 (1.09%) | 0 | 0/4314 | UNUSABLE | excluded |
| 2026-08-25 | NIFTY_FUT | 192,392 | 0 (0.00%) | 0 | 0/4500 | USABLE | CONFIRMATION |
| 2026-08-25 | BANKNIFTY_FUT | 191,782 | 0 (0.00%) | 0 | 0/4500 | USABLE | CONFIRMATION |
| 2026-08-26 | NIFTY_FUT | 195,742 | 0 (0.00%) | 0 | 0/4498 | USABLE | CONFIRMATION |
| 2026-08-26 | BANKNIFTY_FUT | 195,356 | 0 (0.00%) | 0 | 0/4498 | USABLE | CONFIRMATION |
| 2026-08-27 | NIFTY_FUT | 189,834 | 0 (0.00%) | 0 | 0/4498 | USABLE | CONFIRMATION |
| 2026-08-27 | BANKNIFTY_FUT | 189,496 | 0 (0.00%) | 1 | 0/4498 | USABLE | CONFIRMATION |
| 2026-08-28 | NIFTY_FUT | 192,536 | 0 (0.00%) | 0 | 0/4500 | USABLE | CONFIRMATION |
| 2026-08-28 | BANKNIFTY_FUT | 192,294 | 4 (0.00%) | 0 | 0/4500 | USABLE | CONFIRMATION |
| 2026-08-31 | NIFTY_FUT | 195,078 | 0 (0.00%) | 1 | 0/4500 | USABLE | CONFIRMATION |
| 2026-08-31 | BANKNIFTY_FUT | 194,690 | 0 (0.00%) | 0 | 0/4500 | USABLE | CONFIRMATION |
| 2026-09-01 | NIFTY_FUT | 200,708 | 0 (0.00%) | 0 | 0/4493 | USABLE | CONFIRMATION |
| 2026-09-01 | BANKNIFTY_FUT | 200,564 | 0 (0.00%) | 2 | 0/4493 | USABLE | CONFIRMATION |
| 2026-09-02 | NIFTY_FUT | 196,988 | 0 (0.00%) | 1 | 0/4499 | USABLE | CONFIRMATION |
| 2026-09-02 | BANKNIFTY_FUT | 196,364 | 0 (0.00%) | 0 | 0/4499 | USABLE | CONFIRMATION |
| 2026-09-03 | NIFTY_FUT | 188,690 | 0 (0.00%) | 0 | 0/4466 | USABLE | CONFIRMATION |
| 2026-09-03 | BANKNIFTY_FUT | 188,184 | 0 (0.00%) | 0 | 0/4466 | USABLE | CONFIRMATION |
| 2026-09-04 | NIFTY_FUT | 186,740 | 0 (0.00%) | 1 | 2/4415 | USABLE | CONFIRMATION |
| 2026-09-04 | BANKNIFTY_FUT | 186,258 | 0 (0.00%) | 0 | 1/4415 | USABLE | CONFIRMATION |
DISCOVERY (26): 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17, 2026-07-20, 2026-07-21, 2026-07-22, 2026-07-23, 2026-07-24, 2026-07-27, 2026-07-28, 2026-07-29, 2026-07-30, 2026-07-31, 2026-08-03, 2026-08-04, 2026-08-05, 2026-08-06, 2026-08-07, 2026-08-10, 2026-08-11, 2026-08-12, 2026-08-13, 2026-08-14, 2026-08-18. CONFIRMATION (12): 2026-08-19, 2026-08-20, 2026-08-21, 2026-08-25, 2026-08-26, 2026-08-27, 2026-08-28, 2026-08-31, 2026-09-01, 2026-09-02, 2026-09-03, 2026-09-04.
Guard proof: `scripts/test_qguard.py` — QuarantineError raised for a confirmation date from stages CP1, CP2, CP4, CP5 (4/4); allowed for CP6 and for discovery dates; the denials are in `access_log.jsonl`. Access log at the end of the run: every confirmation-date read carries stage CP6.

## 4. CP2 — theory vs empirical baseline; confirmation power
Unconditional (all usable discovery bars, both orientations averaged); theory = a/(a+b):
| inst | stop | target | theory | empirical | departure pp | unresolved |
|---|---|---|---|---|---|---|
| NIFTY_FUT | 1.0σ | 1.0σ | 50.0% | 50.0% | +0.0 | 0.5% |
| NIFTY_FUT | 1.0σ | 3.0σ | 25.0% | 27.1% | +2.1 | 1.6% |
| NIFTY_FUT | 2.0σ | 2.0σ | 50.0% | 50.0% | +0.0 | 2.1% |
| NIFTY_FUT | 3.0σ | 3.0σ | 50.0% | 50.0% | +0.0 | 3.8% |
| NIFTY_FUT | 1.0σ | 2.0σ | 33.3% | 35.1% | +1.8 | 1.1% |
| NIFTY_FUT | 0.5σ | 1.5σ | 25.0% | 28.5% | +3.5 | 0.3% |
| NIFTY_FUT | 3.0σ | 1.0σ | 75.0% | 72.9% | -2.1 | 1.6% |
| BANKNIFTY_FUT | 1.0σ | 1.0σ | 50.0% | 50.0% | +0.0 | 0.6% |
| BANKNIFTY_FUT | 1.0σ | 3.0σ | 25.0% | 27.3% | +2.3 | 2.0% |
| BANKNIFTY_FUT | 2.0σ | 2.0σ | 50.0% | 50.0% | +0.0 | 2.6% |
| BANKNIFTY_FUT | 3.0σ | 3.0σ | 50.0% | 50.0% | +0.0 | 5.3% |
| BANKNIFTY_FUT | 1.0σ | 2.0σ | 33.3% | 35.6% | +2.3 | 1.3% |
| BANKNIFTY_FUT | 0.5σ | 1.5σ | 25.0% | 29.9% | +4.9 | 0.5% |
| BANKNIFTY_FUT | 3.0σ | 1.0σ | 75.0% | 72.7% | -2.3 | 2.0% |
Departure from theory: symmetric pairs sit at 50.0% by construction; the asymmetric pairs run +2 to +5 pp above the random-walk value (far targets are reached slightly more often than a Gaussian walk predicts) — a property of the tape, present on both instruments.
Power (difference in proportions, 80% power, two-sided α = 0.05): MDE = 2.80159·√(2p(1−p)/n); n for 5 pp = 2.80159²·2p(1−p)/0.05² = 1570 at p = 0.5. Projected in CP2 (n = discovery rate × 12): MDE 12.3–14.0 pp → UNPOWERED-CONFIRM on every cell. Actual confirmation counts and the same arithmetic:
| inst | pair | actual confirmation n (F1 thinned) | baseline p | MDE pp | detects 5 pp | n for 5 pp | sessions for 5 pp |
|---|---|---|---|---|---|---|---|
| NIFTY_FUT | 1.0σ/1.0σ | 209 | 0.500 | 13.7 | NO → UNPOWERED-CONFIRM | 1570 | 73 (61 more than the 12 held out) |
| NIFTY_FUT | 1.0σ/3.0σ | 209 | 0.271 | 12.2 | NO → UNPOWERED-CONFIRM | 1241 | 58 (46 more than the 12 held out) |
| NIFTY_FUT | 2.0σ/2.0σ | 209 | 0.500 | 13.7 | NO → UNPOWERED-CONFIRM | 1570 | 73 (61 more than the 12 held out) |
| NIFTY_FUT | 3.0σ/3.0σ | 209 | 0.500 | 13.7 | NO → UNPOWERED-CONFIRM | 1570 | 73 (61 more than the 12 held out) |
| BANKNIFTY_FUT | 1.0σ/1.0σ | 161 | 0.500 | 15.6 | NO → UNPOWERED-CONFIRM | 1570 | 94 (82 more than the 12 held out) |
| BANKNIFTY_FUT | 1.0σ/3.0σ | 161 | 0.273 | 13.9 | NO → UNPOWERED-CONFIRM | 1246 | 74 (62 more than the 12 held out) |
| BANKNIFTY_FUT | 2.0σ/2.0σ | 161 | 0.500 | 15.6 | NO → UNPOWERED-CONFIRM | 1570 | 94 (82 more than the 12 held out) |
| BANKNIFTY_FUT | 3.0σ/3.0σ | 161 | 0.500 | 15.6 | NO → UNPOWERED-CONFIRM | 1570 | 94 (82 more than the 12 held out) |

## 5. CP5 — synthetic random walk, theoretical vs recovered (seed 101, second pass; recovered / theory %)
| stop \ target | 0.25σ | 0.5σ | 0.75σ | 1.0σ | 1.5σ | 2.0σ | 3.0σ |
|---|---|---|---|---|---|---|---|
| 0.25σ | 49.6 / 50.0 | 34.7 / 33.3 | 26.3 / 25.0 | 21.8 / 20.0 | 15.8 / 14.3 | 12.6 / 11.1 | 8.9 / 7.7 |
| 0.5σ | 64.9 / 66.7 | 49.9 / 50.0 | 40.8 / 40.0 | 34.7 / 33.3 | 26.5 / 25.0 | 21.6 / 20.0 | 15.6 / 14.3 |
| 0.75σ | 72.8 / 75.0 | 59.1 / 60.0 | 49.9 / 50.0 | 43.3 / 42.9 | 33.9 / 33.3 | 28.4 / 27.3 | 21.0 / 20.0 |
| 1.0σ | 77.9 / 80.0 | 65.3 / 66.7 | 56.6 / 57.1 | 49.9 / 50.0 | 40.3 / 40.0 | 34.2 / 33.3 | 25.9 / 25.0 |
| 1.5σ | 84.1 / 85.7 | 73.7 / 75.0 | 65.8 / 66.7 | 59.6 / 60.0 | 50.0 / 50.0 | 43.5 / 42.9 | 34.4 / 33.3 |
| 2.0σ | 87.5 / 88.9 | 78.8 / 80.0 | 71.8 / 72.7 | 66.1 / 66.7 | 57.3 / 57.1 | 50.7 / 50.0 | 41.2 / 40.0 |
| 3.0σ | 91.2 / 92.3 | 84.5 / 85.7 | 79.0 / 80.0 | 74.1 / 75.0 | 66.6 / 66.7 | 60.7 / 60.0 | 50.9 / 50.0 |
Worst |recovered − theory|: seed 101 2.23 pp, seed 202 2.35 pp (tolerance 3). Injected drift (+0.01 σ_step per step): recovered within 1.98 / 1.22 pp of the closed form, correct direction on every pair. RANDX on real tape: 0 passes on both seeds.

## 6. CP6 — discovery table, frozen list, confirmation table
### Discovery
| feature | stop / target | NIFTY n / resolved (censored) | win | matched base | theory | lift pp | p | E[R] | BANKNIFTY n / resolved (censored) | win | matched base | lift pp | p | E[R] | same sign | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 | 1.0σ / 1.0σ | 559 / 553 (1.1%) | 64.9% | 50.1% | 50.0% | +14.8 | 0.0005 | +0.294 | 435 / 434 (0.2%) | 59.4% | 49.9% | +9.5 | 0.0005 | +0.188 | yes | PASS DISCOVERY (PRE-COST) |
| F1 | 1.0σ / 3.0σ | 559 / 546 (2.3%) | 35.9% | 27.1% | 25.0% | +8.8 | 0.0010 | +0.438 | 435 / 428 (1.6%) | 35.7% | 27.2% | +8.5 | 0.0005 | +0.429 | yes | FAIL |
| F1 | 2.0σ / 2.0σ | 559 / 542 (3.0%) | 59.0% | 50.0% | 50.0% | +9.0 | 0.0005 | +0.173 | 435 / 427 (1.8%) | 56.4% | 50.0% | +6.5 | 0.0060 | +0.126 | yes | FAIL |
| F1 | 3.0σ / 3.0σ | 559 / 536 (4.1%) | 55.6% | 50.0% | 50.0% | +5.6 | 0.0095 | +0.107 | 435 / 411 (5.5%) | 57.2% | 50.0% | +7.2 | 0.0030 | +0.134 | yes | FAIL |
| F2 | 1.0σ / 1.0σ | 127 / 126 (0.8%) | 67.5% | 50.0% | 50.0% | +17.5 | 0.0005 | +0.347 | 75 / 75 (0.0%) | 58.7% | 50.0% | +8.7 | 0.1219 | +0.173 | yes | FAIL |
| F2 | 1.0σ / 3.0σ | 127 / 124 (2.4%) | 38.7% | 27.5% | 25.0% | +11.2 | 0.0070 | +0.544 | 75 / 72 (4.0%) | 34.7% | 27.5% | +7.3 | 0.1479 | +0.374 | yes | FAIL |
| F2 | 2.0σ / 2.0σ | 127 / 124 (2.4%) | 71.0% | 49.9% | 50.0% | +21.0 | 0.0005 | +0.403 | 75 / 74 (1.3%) | 58.1% | 50.0% | +8.1 | 0.1559 | +0.159 | yes | FAIL |
| F2 | 3.0σ / 3.0σ | 127 / 123 (3.1%) | 58.5% | 50.0% | 50.0% | +8.6 | 0.0635 | +0.165 | 75 / 69 (8.0%) | 62.3% | 49.9% | +12.5 | 0.0340 | +0.221 | yes | FAIL |
### Frozen: [['F1', 1.0, 1.0]]
### Confirmation (read once)
| cell | inst | discovery lift (p) | confirmation n / resolved (censored) | win | matched base | lift pp | p | E[R] | verdict |
|---|---|---|---|---|---|---|---|---|---|
| F1 1.0σ/1.0σ | NIFTY_FUT | +14.8 (p 0.0005) | 209 / 209 (0.0%) | 56.0% | 49.9% | +6.1 | 0.0845 | +0.120 | FAIL confirmation (magnitude < 50% of discovery) |
| F1 1.0σ/1.0σ | BANKNIFTY_FUT | +9.5 (p 0.0005) | 161 / 161 (0.0%) | 56.5% | 50.0% | +6.5 | 0.1009 | +0.130 | CONFIRMED (PRE-COST / PENDING) |
### Cost in R (references only; PRE-COST / PENDING)
| inst | cell | reference | cost / stop | discovery | confirmation |
|---|---|---|---|---|---|
| NIFTY_FUT | F1 1.0σ/1.0σ | option_path_fut_pts = 2.62 pts | 0.54 R | disc E[R] +0.294 → net -0.246 R | conf E[R] +0.120 → net -0.420 R |
| NIFTY_FUT | F1 1.0σ/1.0σ | futures_before_spread_fut_pts = 7.24 pts | 1.50 R | disc E[R] +0.294 → net -1.206 R | conf E[R] +0.120 → net -1.380 R |
| BANKNIFTY_FUT | F1 1.0σ/1.0σ | option_path_fut_pts = 7.96 pts | 0.57 R | disc E[R] +0.188 → net -0.382 R | conf E[R] +0.130 → net -0.440 R |
| BANKNIFTY_FUT | F1 1.0σ/1.0σ | futures_before_spread_fut_pts = 17.2 pts | 1.22 R | disc E[R] +0.188 → net -1.032 R | conf E[R] +0.130 → net -1.090 R |
### Head-to-head vs run 1
| framing | cell | NIFTY effect | NIFTY p | BANKNIFTY effect | BANKNIFTY p | same sign | met its run's bar |
|---|---|---|---|---|---|---|---|
| run 1 mean return (L1–5) | ask_refills @30s | -0.525 bp | 0.0010 | -0.510 bp | 0.0010 | yes | yes |
| run 1 mean return (L1–5) | ask_refills @120s | -0.677 bp | 0.0010 | -0.838 bp | 0.0010 | yes | yes |
| run 1 mean return (L1–5) | bid_refills @30s | +0.381 bp | 0.0010 | +0.194 bp | 0.0220 | yes | no |
| run 3 hit-first (discovery) | F1 1.0σ/1.0σ | +14.8 pp (E[R] +0.29) | 0.0005 | +9.5 pp (E[R] +0.19) | 0.0005 | yes | yes |
| run 3 hit-first (discovery) | F1 1.0σ/3.0σ | +8.8 pp (E[R] +0.44) | 0.0010 | +8.5 pp (E[R] +0.43) | 0.0005 | yes | no |
| run 3 hit-first (discovery) | F1 2.0σ/2.0σ | +9.0 pp (E[R] +0.17) | 0.0005 | +6.5 pp (E[R] +0.13) | 0.0060 | yes | no |
| run 3 hit-first (discovery) | F1 3.0σ/3.0σ | +5.6 pp (E[R] +0.11) | 0.0095 | +7.2 pp (E[R] +0.13) | 0.0030 | yes | no |

## 7. Censoring
Share of usable discovery bars where neither +kσ nor −kσ is reached within H (the level-reach censoring that bounds every first-passage number):
| inst | H | k=0.25 | k=0.5 | k=0.75 | k=1.0 | k=1.5 | k=2.0 | k=3.0 |
|---|---|---|---|---|---|---|---|---|
| NIFTY_FUT | 1m | 4% | 19% | 40% | 59% | 83% | 93% | 98% |
| NIFTY_FUT | 5m | 0% | 0% | 2% | 7% | 26% | 46% | 74% |
| NIFTY_FUT | 15m | 0% | 0% | 0% | 1% | 4% | 11% | 33% |
| NIFTY_FUT | 30m | 0% | 0% | 0% | 0% | 1% | 4% | 13% |
| NIFTY_FUT | 60m | 0% | 0% | 0% | 0% | 1% | 2% | 5% |
| NIFTY_FUT | 120m | 0% | 0% | 0% | 0% | 1% | 2% | 4% |
| NIFTY_FUT | close | 0% | 0% | 0% | 0% | 0% | 0% | 0% |
| BANKNIFTY_FUT | 1m | 7% | 24% | 44% | 61% | 82% | 92% | 98% |
| BANKNIFTY_FUT | 5m | 0% | 1% | 4% | 9% | 27% | 46% | 73% |
| BANKNIFTY_FUT | 15m | 0% | 0% | 0% | 1% | 4% | 12% | 34% |
| BANKNIFTY_FUT | 30m | 0% | 0% | 0% | 1% | 2% | 4% | 16% |
| BANKNIFTY_FUT | 60m | 0% | 0% | 0% | 1% | 1% | 3% | 8% |
| BANKNIFTY_FUT | 120m | 0% | 0% | 0% | 1% | 1% | 3% | 6% |
| BANKNIFTY_FUT | close | 0% | 0% | 0% | 0% | 0% | 0% | 0% |
Per scored cell (events unresolved before the session's last snapshot):
| inst | cell | events | resolved | censored share |
|---|---|---|---|---|
| NIFTY_FUT | F1 1.0σ/1.0σ | 559 | 553 | 1.1% |
| BANKNIFTY_FUT | F1 1.0σ/1.0σ | 435 | 434 | 0.2% |
| NIFTY_FUT | F1 1.0σ/3.0σ | 559 | 546 | 2.3% |
| BANKNIFTY_FUT | F1 1.0σ/3.0σ | 435 | 428 | 1.6% |
| NIFTY_FUT | F1 2.0σ/2.0σ | 559 | 542 | 3.0% |
| BANKNIFTY_FUT | F1 2.0σ/2.0σ | 435 | 427 | 1.8% |
| NIFTY_FUT | F1 3.0σ/3.0σ | 559 | 536 | 4.1% |
| BANKNIFTY_FUT | F1 3.0σ/3.0σ | 435 | 411 | 5.5% |
| NIFTY_FUT | F2 1.0σ/1.0σ | 127 | 126 | 0.8% |
| BANKNIFTY_FUT | F2 1.0σ/1.0σ | 75 | 75 | 0.0% |
| NIFTY_FUT | F2 1.0σ/3.0σ | 127 | 124 | 2.4% |
| BANKNIFTY_FUT | F2 1.0σ/3.0σ | 75 | 72 | 4.0% |
| NIFTY_FUT | F2 2.0σ/2.0σ | 127 | 124 | 2.4% |
| BANKNIFTY_FUT | F2 2.0σ/2.0σ | 75 | 74 | 1.3% |
| NIFTY_FUT | F2 3.0σ/3.0σ | 127 | 123 | 3.1% |
| BANKNIFTY_FUT | F2 3.0σ/3.0σ | 75 | 69 | 8.0% |

## 8. 🔑 THE ANSWER
On the 26 discovery sessions, a path-dependent rule on shallow refill does show a hit-first edge above the volatility- and time-of-day-matched baseline: oriented by side, a bid-side refill burst reaches +1σ_1m before −1σ_1m 64.9% of the time on NIFTY_FUT and 59.4% on BANKNIFTY_FUT against a 50% baseline (p = 0.0005 on both, the smallest value the 2000-draw test can produce), and every one of the 8 pre-registered cells points the same way on both instruments; only that one cell clears the third-look bar, and the location-conditioned variant (F2) cannot be judged on BANKNIFTY's 75 events. On the quarantined 12-session confirmation set, read once, the frozen cell was NOT confirmed on both instruments (NIFTY: FAIL confirmation (magnitude < 50% of discovery); BANKNIFTY: CONFIRMED (PRE-COST / PENDING)) (NIFTY lift +6.1 pp vs +14.8 in discovery, p 0.0845; BANKNIFTY +6.5 pp vs +9.5, p 0.1009) — but the confirmation set is UNPOWERED for the pre-registered 5-pp question (actual MDE in the table above), so a confirmation there is a sign-and-magnitude agreement on a small sample, not a powered test. In R units the edge does not survive the repo's documented cost references at ANY stop in the grid: F1 1σ/1σ NIFTY +0.294 R pre-cost vs option-path 0.54 R (net -0.246) and futures 1.50 R (net -1.206); BANKNIFTY +0.188 R pre-cost vs option-path 0.57 R (net -0.382) and futures 1.22 R (net -1.032); F1 1σ/3σ NIFTY +0.438 R pre-cost vs option-path 0.54 R (net -0.102) and futures 1.50 R (net -1.062); BANKNIFTY +0.429 R pre-cost vs option-path 0.57 R (net -0.141) and futures 1.22 R (net -0.791); F1 2σ/2σ NIFTY +0.173 R pre-cost vs option-path 0.27 R (net -0.097) and futures 0.75 R (net -0.577); BANKNIFTY +0.126 R pre-cost vs option-path 0.28 R (net -0.154) and futures 0.61 R (net -0.484); F1 3σ/3σ NIFTY +0.107 R pre-cost vs option-path 0.18 R (net -0.073) and futures 0.50 R (net -0.393); BANKNIFTY +0.134 R pre-cost vs option-path 0.19 R (net -0.056) and futures 0.41 R (net -0.276) — the best reference-net expectancy anywhere in the grid is -0.056 R, i.e. negative on every cell and both instruments, so every result stays PRE-COST / PENDING and none is GREEN. Run 1's mean-return framing and this framing agree on the direction of shallow refill; the path framing shows the effect is real in hit-first terms and still too small to pay a documented round trip at any stop in the grid.

## 9. 🔴 Required statement
This is the third examination of the same tape and therefore not final proof. A forward-sealed confirmation window at the observed thinned event rate (21.5 NIFTY / 16.7 BANKNIFTY events per session) would need n ≈ 1570 events per instrument to detect a 5-pp lift at 80% power — about **94 future sessions** for the slower instrument (73 for NIFTY, 94 for BANKNIFTY); to detect a lift of the size seen in discovery on NIFTY (≈ 15 pp) would need ≈ 174 events ≈ 8 sessions, and for BANKNIFTY's ≈ 9.5 pp ≈ 435 events ≈ 26 sessions. The magnitude actually observed out of sample was ≈ 6 pp on both instruments; powering for THAT would need ≈ 1090 events per instrument = **51 sessions (NIFTY) / 65 sessions (BANKNIFTY)**, and none of these figures is a prediction that the lift would persist.

## 10. Still NOT MEASURED after this run
- Cost per event (ATM premium and recorded delta for the option path; a contract-note-verified futures round trip): the repo references are assumptions; nothing is cost-GREEN.
- Intra-snapshot path (the ~200 ms sampling bounds first-passage times from above; a level touched and left between snapshots is invisible).
- Any stop/target outside the 7 k-values, any horizon structure beyond session close, tolerance or window sensitivity for F2 (one value, never swept), and F2 on BANKNIFTY (75 events).
- Root cause of the two corrupt Mondays; whether the intermittent recorder defect recurs after 09-04.
- Regimes beyond this 8-week window; behaviour across the two contract rolls beyond the within-session guard; capturability of a 1σ move as a fill (mid-price only, no queue position, no execution modelled).
- Eaten-vs-pulled at any level (disqualified by construction).
