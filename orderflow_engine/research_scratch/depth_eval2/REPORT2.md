# REPORT2 — depth run 2: tape integrity + levels 6–20 (2026-09-06, research worktree, read-only on production, zero raw bytes stored)

**LIVE DEFECT FLAG: NOT RAISED under the gate's wording — the corruption is NOT in the most recent dates.** Last corrupt date observed: **2026-08-24** (a second occurrence, previously unknown, one week after 08-17; both Mondays with a late first snapshot; negative ask-side prices). Last clean date: **2026-09-04**, the newest in the bucket; the 8 sessions 08-25 … 09-04 have 0 non-positive prices on both instruments. The defect is intermittent, not fixed by evidence — only absent for 8 sessions.

Run location: worktree `.claude/worktrees/depth-eval`, branch `research/depth-eval`, `orderflow_engine/research_scratch/depth_eval2/`. Depth streamed from S3 and discarded; features 29 MB + a 4-session recheck; largest single local write ≈ 0.5 MB; Mac free disk 4.48% at the end (pre-existing 4.8% before run 1); nothing deleted.

## 2. Checkpoint table
| CP | status | one line |
|---|---|---|
| CP0 tape integrity | **GREEN** | 40 dates with objects (07-09/07-10 have none); 38 USABLE; 08-17 and 08-24 UNUSABLE (negative ask prices, both instruments); newest 8 clean; independent path 6/6 exact. |
| CP1 deep-book build | **GREEN** | 10 aggressor-free features on levels 6–20 in `deep_book.py`; one-session independent path identical (158,070 events). |
| CP2 power | **GREEN** | all 10 features powered at 5/30/120 s on both instruments; every 30 s cell detects run 1's 0.5 bp (MDE 0.18–0.36 bp); close unpowered everywhere. 30 cells. |
| CP3 pre-registration | **GREEN** | PREREG2.md sha256 `33d7be7dd143deee9b1709a92bba8a79001994df7196ceea47a2f48dc40db734` committed as 9404e257 before any outcome; second-look bar α = 0.05/46 on both instruments. |
| CP4 features | **GREEN** | 76 sessions; recheck 4/4 byte-identical; no SINGLE-EPISODE (min 8 sessions); 6 concentration flags. |
| CP5 calibration | **GREEN** | RANDX 0 passes (5/120 p<0.05, ≈6 expected); INJ±R recovered within 2 SE 240/240, sign 240/240; seeds 11/22 differ. |
| CP6 score | **RUN** | 0 of 30 cells pass; 11 sign flips; BANKNIFTY-only deep-imbalance signal fails the cross-instrument gate; deep refill weaker than shallow; run twice byte-identical. |
| CP7 report | **BUILT** | this file. |

## 3. Self-check log
- CP0: `self-check found` a second corrupt date, 2026-08-24, that the run-1 window never covered; `fixed by` excluding it with direct counts (NIFTY 5,098 / BANKNIFTY 2,053 rows with price ≤ 0). Independent pandas path on 07-14, 08-17, 09-04: all six counts match exactly on 6/6 objects.
- CP1: `self-check found` (before any run) the pending-refill bookkeeping scanned a list per rising price (quadratic at deep levels); `fixed by` a per-price FIFO dict with the same definition; the independent array/`np.isin` path then reproduced every event (158,070) and every state feature (max |diff| 3.4e-16).
- CP2: independent pandas recount matched all 20 feature counts exactly.
- CP3: hash identical on disk, in the commit and in PREREG2.sha256; printed back.
- CP4: 4 sessions recomputed from S3 byte-identical and row-identical.
- CP5: a numpy RuntimeWarning from `np.sign` on NaN feature values (orientation array) — harmless, NaN bars are never events or baseline draws; both seeds produce different numbers in every cell.
- CP6: end-to-end re-run byte-identical.
- Note: `cp0_sweep.log` is git-ignored by the repo (not committed); `cp0_integrity.json` carries the same numbers and is committed.

## 4. CP0 date table (per date per instrument)
| date | inst | sid | rows | price ≤ 0 rows | non-monotonic rows | zero qty/orders rows | crossed bars / defined | status |
|---|---|---|---|---|---|---|---|---|
| 2026-07-09 | NIFTY_FUT | — | ABSENT | | | | | ABSENT |
| 2026-07-09 | BANKNIFTY_FUT | — | ABSENT | | | | | ABSENT |
| 2026-07-10 | NIFTY_FUT | — | ABSENT | | | | | ABSENT |
| 2026-07-10 | BANKNIFTY_FUT | — | ABSENT | | | | | ABSENT |
| 2026-07-13 | NIFTY_FUT | 61093 | 163,246 | 0 (0.00%) | 0 (0.00%) | 5 (0.00%) | 0/3815 (0.00%) | **USABLE** |
| 2026-07-13 | BANKNIFTY_FUT | 61088 | 162,660 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1/3814 (0.03%) | **USABLE** |
| 2026-07-14 | NIFTY_FUT | 61093 | 185,696 | 92 (0.05%) | 0 (0.00%) | 6 (0.00%) | 0/4487 (0.00%) | **USABLE** |
| 2026-07-14 | BANKNIFTY_FUT | 61088 | 187,652 | 40 (0.02%) | 2 (0.00%) | 1 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-15 | NIFTY_FUT | 61093 | 187,856 | 7 (0.00%) | 0 (0.00%) | 7 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-15 | BANKNIFTY_FUT | 61088 | 187,220 | 8 (0.00%) | 0 (0.00%) | 1 (0.00%) | 1/4500 (0.02%) | **USABLE** |
| 2026-07-16 | NIFTY_FUT | 61093 | 187,616 | 10 (0.01%) | 1 (0.00%) | 4 (0.00%) | 1/4500 (0.02%) | **USABLE** |
| 2026-07-16 | BANKNIFTY_FUT | 61088 | 187,262 | 0 (0.00%) | 0 (0.00%) | 2 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-17 | NIFTY_FUT | 61093 | 187,496 | 2 (0.00%) | 1 (0.00%) | 3 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-17 | BANKNIFTY_FUT | 61088 | 187,024 | 14 (0.01%) | 0 (0.00%) | 0 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-20 | NIFTY_FUT | 61093 | 187,548 | 9 (0.00%) | 0 (0.00%) | 5 (0.00%) | 1/4500 (0.02%) | **USABLE** |
| 2026-07-20 | BANKNIFTY_FUT | 61088 | 187,164 | 0 (0.00%) | 0 (0.00%) | 1 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-21 | NIFTY_FUT | 61093 | 187,752 | 2 (0.00%) | 0 (0.00%) | 1 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-21 | BANKNIFTY_FUT | 61088 | 187,438 | 8 (0.00%) | 0 (0.00%) | 1 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-22 | NIFTY_FUT | 61093 | 182,346 | 0 (0.00%) | 1 (0.00%) | 4 (0.00%) | 0/4377 (0.00%) | **USABLE** |
| 2026-07-22 | BANKNIFTY_FUT | 61088 | 182,400 | 2 (0.00%) | 0 (0.00%) | 2 (0.00%) | 0/4377 (0.00%) | **USABLE** |
| 2026-07-23 | NIFTY_FUT | 61093 | 187,666 | 12 (0.01%) | 0 (0.00%) | 2 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-23 | BANKNIFTY_FUT | 61088 | 187,646 | 4 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-24 | NIFTY_FUT | 61093 | 187,210 | 6 (0.00%) | 0 (0.00%) | 3 (0.00%) | 0/4499 (0.00%) | **USABLE** |
| 2026-07-24 | BANKNIFTY_FUT | 61088 | 187,408 | 10 (0.01%) | 0 (0.00%) | 4 (0.00%) | 0/4499 (0.00%) | **USABLE** |
| 2026-07-27 | NIFTY_FUT | 61093 | 187,466 | 0 (0.00%) | 1 (0.00%) | 7 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-27 | BANKNIFTY_FUT | 61088 | 187,652 | 2 (0.00%) | 0 (0.00%) | 4 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-28 | NIFTY_FUT | 61093 | 186,912 | 6 (0.00%) | 0 (0.00%) | 1 (0.00%) | 0/4499 (0.00%) | **USABLE** |
| 2026-07-28 | BANKNIFTY_FUT | 61088 | 187,202 | 9 (0.00%) | 1 (0.00%) | 6 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-29 | NIFTY_FUT | 58072 | 149,838 | 0 (0.00%) | 0 (0.00%) | 3 (0.00%) | 0/3590 (0.00%) | **USABLE** |
| 2026-07-29 | BANKNIFTY_FUT | 58067 | 149,468 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1/3590 (0.03%) | **USABLE** |
| 2026-07-30 | NIFTY_FUT | 58072 | 188,334 | 2 (0.00%) | 0 (0.00%) | 3 (0.00%) | 1/4500 (0.02%) | **USABLE** |
| 2026-07-30 | BANKNIFTY_FUT | 58067 | 187,984 | 4 (0.00%) | 0 (0.00%) | 1 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-31 | NIFTY_FUT | 58072 | 199,406 | 2 (0.00%) | 1 (0.00%) | 4 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-07-31 | BANKNIFTY_FUT | 58067 | 198,966 | 2 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-03 | NIFTY_FUT | 58072 | 222,904 | 0 (0.00%) | 0 (0.00%) | 2 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-03 | BANKNIFTY_FUT | 58067 | 223,018 | 0 (0.00%) | 0 (0.00%) | 1 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-04 | NIFTY_FUT | 58072 | 189,824 | 0 (0.00%) | 0 (0.00%) | 4 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-04 | BANKNIFTY_FUT | 58067 | 189,754 | 0 (0.00%) | 0 (0.00%) | 2 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-05 | NIFTY_FUT | 58072 | 190,756 | 0 (0.00%) | 0 (0.00%) | 6 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-05 | BANKNIFTY_FUT | 58067 | 190,622 | 0 (0.00%) | 0 (0.00%) | 2 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-06 | NIFTY_FUT | 58072 | 190,402 | 0 (0.00%) | 1 (0.00%) | 4 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-06 | BANKNIFTY_FUT | 58067 | 190,078 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-07 | NIFTY_FUT | 58072 | 225,640 | 0 (0.00%) | 0 (0.00%) | 4 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-07 | BANKNIFTY_FUT | 58067 | 225,350 | 0 (0.00%) | 0 (0.00%) | 2 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-10 | NIFTY_FUT | 58072 | 219,428 | 0 (0.00%) | 0 (0.00%) | 5 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-10 | BANKNIFTY_FUT | 58067 | 218,914 | 0 (0.00%) | 0 (0.00%) | 2 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-11 | NIFTY_FUT | 58072 | 196,766 | 0 (0.00%) | 0 (0.00%) | 3 (0.00%) | 0/4498 (0.00%) | **USABLE** |
| 2026-08-11 | BANKNIFTY_FUT | 58067 | 196,454 | 0 (0.00%) | 0 (0.00%) | 2 (0.00%) | 0/4498 (0.00%) | **USABLE** |
| 2026-08-12 | NIFTY_FUT | 58072 | 190,682 | 0 (0.00%) | 0 (0.00%) | 5 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-12 | BANKNIFTY_FUT | 58067 | 190,252 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-13 | NIFTY_FUT | 58072 | 190,762 | 0 (0.00%) | 1 (0.00%) | 4 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-13 | BANKNIFTY_FUT | 58067 | 190,502 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-14 | NIFTY_FUT | 58072 | 189,876 | 0 (0.00%) | 0 (0.00%) | 1 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-14 | BANKNIFTY_FUT | 58067 | 189,738 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-17 | NIFTY_FUT | 58072 | 172,190 | 70193 (40.76%) | 1 (0.00%) | 2 (0.00%) | 0/703 (0.00%) | **UNUSABLE** |
| 2026-08-17 | BANKNIFTY_FUT | 58067 | 173,034 | 86517 (50.00%) | 0 (0.00%) | 0 (0.00%) | 0/0 (0.00%) | **UNUSABLE** |
| 2026-08-18 | NIFTY_FUT | 58072 | 189,508 | 0 (0.00%) | 0 (0.00%) | 5 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-18 | BANKNIFTY_FUT | 58067 | 189,154 | 0 (0.00%) | 0 (0.00%) | 3 (0.00%) | 1/4500 (0.02%) | **USABLE** |
| 2026-08-19 | NIFTY_FUT | 58072 | 192,660 | 0 (0.00%) | 0 (0.00%) | 3 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-19 | BANKNIFTY_FUT | 58067 | 192,642 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-20 | NIFTY_FUT | 58072 | 189,606 | 0 (0.00%) | 0 (0.00%) | 3 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-20 | BANKNIFTY_FUT | 58067 | 189,930 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-21 | NIFTY_FUT | 58072 | 190,174 | 0 (0.00%) | 0 (0.00%) | 1 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-21 | BANKNIFTY_FUT | 58067 | 190,160 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-24 | NIFTY_FUT | 58072 | 174,498 | 5098 (2.92%) | 0 (0.00%) | 0 (0.00%) | 0/3823 (0.00%) | **UNUSABLE** |
| 2026-08-24 | BANKNIFTY_FUT | 58067 | 188,784 | 2053 (1.09%) | 0 (0.00%) | 0 (0.00%) | 0/4314 (0.00%) | **UNUSABLE** |
| 2026-08-25 | NIFTY_FUT | 58072 | 192,392 | 0 (0.00%) | 0 (0.00%) | 2 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-25 | BANKNIFTY_FUT | 58067 | 191,782 | 0 (0.00%) | 0 (0.00%) | 1 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-26 | NIFTY_FUT | 68407 | 195,742 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4498 (0.00%) | **USABLE** |
| 2026-08-26 | BANKNIFTY_FUT | 68390 | 195,356 | 0 (0.00%) | 0 (0.00%) | 1 (0.00%) | 0/4498 (0.00%) | **USABLE** |
| 2026-08-27 | NIFTY_FUT | 68407 | 189,834 | 0 (0.00%) | 0 (0.00%) | 3 (0.00%) | 0/4498 (0.00%) | **USABLE** |
| 2026-08-27 | BANKNIFTY_FUT | 68390 | 189,496 | 0 (0.00%) | 1 (0.00%) | 0 (0.00%) | 0/4498 (0.00%) | **USABLE** |
| 2026-08-28 | NIFTY_FUT | 68407 | 192,536 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-28 | BANKNIFTY_FUT | 68390 | 192,294 | 4 (0.00%) | 0 (0.00%) | 2 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-31 | NIFTY_FUT | 68407 | 195,078 | 0 (0.00%) | 1 (0.00%) | 2 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-08-31 | BANKNIFTY_FUT | 68390 | 194,690 | 0 (0.00%) | 0 (0.00%) | 1 (0.00%) | 0/4500 (0.00%) | **USABLE** |
| 2026-09-01 | NIFTY_FUT | 68407 | 200,708 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4493 (0.00%) | **USABLE** |
| 2026-09-01 | BANKNIFTY_FUT | 68390 | 200,564 | 0 (0.00%) | 2 (0.00%) | 0 (0.00%) | 0/4493 (0.00%) | **USABLE** |
| 2026-09-02 | NIFTY_FUT | 68407 | 196,988 | 0 (0.00%) | 1 (0.00%) | 0 (0.00%) | 0/4499 (0.00%) | **USABLE** |
| 2026-09-02 | BANKNIFTY_FUT | 68390 | 196,364 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4499 (0.00%) | **USABLE** |
| 2026-09-03 | NIFTY_FUT | 68407 | 188,690 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4466 (0.00%) | **USABLE** |
| 2026-09-03 | BANKNIFTY_FUT | 68390 | 188,184 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0/4466 (0.00%) | **USABLE** |
| 2026-09-04 | NIFTY_FUT | 68407 | 186,740 | 0 (0.00%) | 1 (0.00%) | 0 (0.00%) | 2/4415 (0.05%) | **USABLE** |
| 2026-09-04 | BANKNIFTY_FUT | 68390 | 186,258 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1/4415 (0.02%) | **USABLE** |
Threshold: 1.0% per defect class (stated before classification); unusable share 2/40 = 5.0%. Contract rolls: 07-29 (61093/61088 → 58072/58067) and 08-26 (→ 68407/68390), handled within-session.

## 5. CP2 power (MDE = 2.80159·σ_h·√(2/n_eff); bps = /mean mid × 10⁴; UNPOWERED if MDE > median |move|_h)
Example: NIFTY deep_imb_qty @30 s: 2.80159 × 3.487 × √(2/746) = 0.506 pts = 0.208 bps ≤ 0.5 bp → can detect run 1's effect size.
| inst | feature | h | n_raw | n_eff | σ_h pts | MDE pts | MDE bps | median |move| pts | verdict | detects 0.5 bp @30 s |
|---|---|---|---|---|---|---|---|---|---|---|
| NIFTY_FUT | deep_imb_qty | 5s | 1706 | 1706 | 1.513 | 0.145 | 0.060 | 0.450 | POWERED |  |
| NIFTY_FUT | deep_imb_qty | 30s | 1706 | 746 | 3.487 | 0.506 | 0.208 | 1.650 | POWERED | YES |
| NIFTY_FUT | deep_imb_qty | 120s | 1706 | 419 | 7.022 | 1.359 | 0.560 | 3.750 | POWERED |  |
| NIFTY_FUT | deep_imb_qty | close | 1706 | 37 | 59.629 | 38.840 | 16.001 | 30.100 | UNPOWERED |  |
| NIFTY_FUT | deep_imb_orders | 5s | 1703 | 1703 | 1.513 | 0.145 | 0.060 | 0.450 | POWERED |  |
| NIFTY_FUT | deep_imb_orders | 30s | 1703 | 752 | 3.487 | 0.504 | 0.208 | 1.650 | POWERED | YES |
| NIFTY_FUT | deep_imb_orders | 120s | 1703 | 420 | 7.022 | 1.357 | 0.559 | 3.750 | POWERED |  |
| NIFTY_FUT | deep_imb_orders | close | 1703 | 38 | 59.629 | 38.325 | 15.789 | 30.100 | UNPOWERED |  |
| NIFTY_FUT | slope_diff | 5s | 1707 | 1707 | 1.513 | 0.145 | 0.060 | 0.450 | POWERED |  |
| NIFTY_FUT | slope_diff | 30s | 1707 | 973 | 3.487 | 0.443 | 0.182 | 1.650 | POWERED | YES |
| NIFTY_FUT | slope_diff | 120s | 1707 | 635 | 7.022 | 1.104 | 0.455 | 3.750 | POWERED |  |
| NIFTY_FUT | slope_diff | close | 1707 | 38 | 59.629 | 38.325 | 15.789 | 30.100 | UNPOWERED |  |
| NIFTY_FUT | conc_diff | 5s | 1707 | 1707 | 1.513 | 0.145 | 0.060 | 0.450 | POWERED |  |
| NIFTY_FUT | conc_diff | 30s | 1707 | 670 | 3.487 | 0.534 | 0.220 | 1.650 | POWERED | YES |
| NIFTY_FUT | conc_diff | 120s | 1707 | 422 | 7.022 | 1.354 | 0.558 | 3.750 | POWERED |  |
| NIFTY_FUT | conc_diff | close | 1707 | 38 | 59.629 | 38.325 | 15.789 | 30.100 | UNPOWERED |  |
| NIFTY_FUT | wall_appear_bid_w | 5s | 1689 | 1689 | 1.513 | 0.146 | 0.060 | 0.450 | POWERED |  |
| NIFTY_FUT | wall_appear_bid_w | 30s | 1689 | 383 | 3.487 | 0.706 | 0.291 | 1.650 | POWERED | YES |
| NIFTY_FUT | wall_appear_bid_w | 120s | 1689 | 186 | 7.022 | 2.040 | 0.840 | 3.750 | POWERED |  |
| NIFTY_FUT | wall_appear_bid_w | close | 1689 | 27 | 59.629 | 45.467 | 18.731 | 30.100 | UNPOWERED |  |
| NIFTY_FUT | wall_appear_ask_w | 5s | 1701 | 1701 | 1.513 | 0.145 | 0.060 | 0.450 | POWERED |  |
| NIFTY_FUT | wall_appear_ask_w | 30s | 1701 | 376 | 3.487 | 0.712 | 0.294 | 1.650 | POWERED | YES |
| NIFTY_FUT | wall_appear_ask_w | 120s | 1701 | 170 | 7.022 | 2.134 | 0.879 | 3.750 | POWERED |  |
| NIFTY_FUT | wall_appear_ask_w | close | 1701 | 25 | 59.629 | 47.251 | 19.466 | 30.100 | UNPOWERED |  |
| NIFTY_FUT | wall_disappear_bid_w | 5s | 1669 | 1669 | 1.513 | 0.147 | 0.060 | 0.450 | POWERED |  |
| NIFTY_FUT | wall_disappear_bid_w | 30s | 1669 | 377 | 3.487 | 0.712 | 0.293 | 1.650 | POWERED | YES |
| NIFTY_FUT | wall_disappear_bid_w | 120s | 1669 | 186 | 7.022 | 2.040 | 0.840 | 3.750 | POWERED |  |
| NIFTY_FUT | wall_disappear_bid_w | close | 1669 | 26 | 59.629 | 46.333 | 19.088 | 30.100 | UNPOWERED |  |
| NIFTY_FUT | wall_disappear_ask_w | 5s | 1702 | 1702 | 1.513 | 0.145 | 0.060 | 0.450 | POWERED |  |
| NIFTY_FUT | wall_disappear_ask_w | 30s | 1702 | 374 | 3.487 | 0.714 | 0.294 | 1.650 | POWERED | YES |
| NIFTY_FUT | wall_disappear_ask_w | 120s | 1702 | 173 | 7.022 | 2.115 | 0.871 | 3.750 | POWERED |  |
| NIFTY_FUT | wall_disappear_ask_w | close | 1702 | 26 | 59.629 | 46.333 | 19.088 | 30.100 | UNPOWERED |  |
| NIFTY_FUT | deep_refill_bid_w | 5s | 1699 | 1699 | 1.513 | 0.145 | 0.060 | 0.450 | POWERED |  |
| NIFTY_FUT | deep_refill_bid_w | 30s | 1699 | 413 | 3.487 | 0.680 | 0.280 | 1.650 | POWERED | YES |
| NIFTY_FUT | deep_refill_bid_w | 120s | 1699 | 193 | 7.022 | 2.003 | 0.825 | 3.750 | POWERED |  |
| NIFTY_FUT | deep_refill_bid_w | close | 1699 | 10 | 59.629 | 74.710 | 30.778 | 30.100 | UNPOWERED |  |
| NIFTY_FUT | deep_refill_ask_w | 5s | 1714 | 1714 | 1.513 | 0.145 | 0.060 | 0.450 | POWERED |  |
| NIFTY_FUT | deep_refill_ask_w | 30s | 1714 | 399 | 3.487 | 0.692 | 0.285 | 1.650 | POWERED | YES |
| NIFTY_FUT | deep_refill_ask_w | 120s | 1714 | 190 | 7.022 | 2.018 | 0.831 | 3.750 | POWERED |  |
| NIFTY_FUT | deep_refill_ask_w | close | 1714 | 13 | 59.629 | 65.525 | 26.994 | 30.100 | UNPOWERED |  |
| BANKNIFTY_FUT | deep_imb_qty | 5s | 1703 | 1703 | 4.350 | 0.418 | 0.072 | 0.900 | POWERED |  |
| BANKNIFTY_FUT | deep_imb_qty | 30s | 1703 | 864 | 10.232 | 1.379 | 0.239 | 4.400 | POWERED | YES |
| BANKNIFTY_FUT | deep_imb_qty | 120s | 1703 | 518 | 21.233 | 3.696 | 0.641 | 10.200 | POWERED |  |
| BANKNIFTY_FUT | deep_imb_qty | close | 1703 | 37 | 167.202 | 108.908 | 18.889 | 75.800 | UNPOWERED |  |
| BANKNIFTY_FUT | deep_imb_orders | 5s | 1692 | 1692 | 4.350 | 0.419 | 0.073 | 0.900 | POWERED |  |
| BANKNIFTY_FUT | deep_imb_orders | 30s | 1692 | 974 | 10.232 | 1.299 | 0.225 | 4.400 | POWERED | YES |
| BANKNIFTY_FUT | deep_imb_orders | 120s | 1692 | 604 | 21.233 | 3.423 | 0.594 | 10.200 | POWERED |  |
| BANKNIFTY_FUT | deep_imb_orders | close | 1692 | 36 | 167.202 | 110.410 | 19.149 | 75.800 | UNPOWERED |  |
| BANKNIFTY_FUT | slope_diff | 5s | 1707 | 1707 | 4.350 | 0.417 | 0.072 | 0.900 | POWERED |  |
| BANKNIFTY_FUT | slope_diff | 30s | 1707 | 1026 | 10.232 | 1.266 | 0.220 | 4.400 | POWERED | YES |
| BANKNIFTY_FUT | slope_diff | 120s | 1707 | 695 | 21.233 | 3.191 | 0.553 | 10.200 | POWERED |  |
| BANKNIFTY_FUT | slope_diff | close | 1707 | 38 | 167.202 | 107.465 | 18.638 | 75.800 | UNPOWERED |  |
| BANKNIFTY_FUT | conc_diff | 5s | 1707 | 1707 | 4.350 | 0.417 | 0.072 | 0.900 | POWERED |  |
| BANKNIFTY_FUT | conc_diff | 30s | 1707 | 777 | 10.232 | 1.454 | 0.252 | 4.400 | POWERED | YES |
| BANKNIFTY_FUT | conc_diff | 120s | 1707 | 470 | 21.233 | 3.880 | 0.673 | 10.200 | POWERED |  |
| BANKNIFTY_FUT | conc_diff | close | 1707 | 38 | 167.202 | 107.465 | 18.638 | 75.800 | UNPOWERED |  |
| BANKNIFTY_FUT | wall_appear_bid_w | 5s | 1687 | 1687 | 4.350 | 0.420 | 0.073 | 0.900 | POWERED |  |
| BANKNIFTY_FUT | wall_appear_bid_w | 30s | 1687 | 424 | 10.232 | 1.969 | 0.341 | 4.400 | POWERED | YES |
| BANKNIFTY_FUT | wall_appear_bid_w | 120s | 1687 | 228 | 21.233 | 5.571 | 0.966 | 10.200 | POWERED |  |
| BANKNIFTY_FUT | wall_appear_bid_w | close | 1687 | 25 | 167.202 | 132.492 | 22.979 | 75.800 | UNPOWERED |  |
| BANKNIFTY_FUT | wall_appear_ask_w | 5s | 1679 | 1679 | 4.350 | 0.421 | 0.073 | 0.900 | POWERED |  |
| BANKNIFTY_FUT | wall_appear_ask_w | 30s | 1679 | 403 | 10.232 | 2.019 | 0.350 | 4.400 | POWERED | YES |
| BANKNIFTY_FUT | wall_appear_ask_w | 120s | 1679 | 205 | 21.233 | 5.876 | 1.019 | 10.200 | POWERED |  |
| BANKNIFTY_FUT | wall_appear_ask_w | close | 1679 | 27 | 167.202 | 127.491 | 22.112 | 75.800 | UNPOWERED |  |
| BANKNIFTY_FUT | wall_disappear_bid_w | 5s | 1688 | 1688 | 4.350 | 0.419 | 0.073 | 0.900 | POWERED |  |
| BANKNIFTY_FUT | wall_disappear_bid_w | 30s | 1688 | 421 | 10.232 | 1.976 | 0.343 | 4.400 | POWERED | YES |
| BANKNIFTY_FUT | wall_disappear_bid_w | 120s | 1688 | 230 | 21.233 | 5.547 | 0.962 | 10.200 | POWERED |  |
| BANKNIFTY_FUT | wall_disappear_bid_w | close | 1688 | 25 | 167.202 | 132.492 | 22.979 | 75.800 | UNPOWERED |  |
| BANKNIFTY_FUT | wall_disappear_ask_w | 5s | 1684 | 1684 | 4.350 | 0.420 | 0.073 | 0.900 | POWERED |  |
| BANKNIFTY_FUT | wall_disappear_ask_w | 30s | 1684 | 402 | 10.232 | 2.022 | 0.351 | 4.400 | POWERED | YES |
| BANKNIFTY_FUT | wall_disappear_ask_w | 120s | 1684 | 211 | 21.233 | 5.791 | 1.004 | 10.200 | POWERED |  |
| BANKNIFTY_FUT | wall_disappear_ask_w | close | 1684 | 27 | 167.202 | 127.491 | 22.112 | 75.800 | UNPOWERED |  |
| BANKNIFTY_FUT | deep_refill_bid_w | 5s | 1691 | 1691 | 4.350 | 0.419 | 0.073 | 0.900 | POWERED |  |
| BANKNIFTY_FUT | deep_refill_bid_w | 30s | 1691 | 395 | 10.232 | 2.040 | 0.354 | 4.400 | POWERED | YES |
| BANKNIFTY_FUT | deep_refill_bid_w | 120s | 1691 | 182 | 21.233 | 6.236 | 1.082 | 10.200 | POWERED |  |
| BANKNIFTY_FUT | deep_refill_bid_w | close | 1691 | 8 | 167.202 | 234.216 | 40.622 | 75.800 | UNPOWERED |  |
| BANKNIFTY_FUT | deep_refill_ask_w | 5s | 1698 | 1698 | 4.350 | 0.418 | 0.073 | 0.900 | POWERED |  |
| BANKNIFTY_FUT | deep_refill_ask_w | 30s | 1698 | 393 | 10.232 | 2.045 | 0.355 | 4.400 | POWERED | YES |
| BANKNIFTY_FUT | deep_refill_ask_w | 120s | 1698 | 185 | 21.233 | 6.185 | 1.073 | 10.200 | POWERED |  |
| BANKNIFTY_FUT | deep_refill_ask_w | close | 1698 | 14 | 167.202 | 177.050 | 30.707 | 75.800 | UNPOWERED |  |

## 6. CP5 calibration
| exam | size | recovery | sign | note |
|---|---|---|---|---|
| RANDX | 30 cells × 2 seeds × 2 inst | passes 0 | p<0.05 on 5/120 (≈6 expected) | min p 0.0205, median 0.552 |
| INJ+R | 30 cells × 2 seeds × 2 inst | within 2 SE 120/120 | correct sign 120/120 | truth = δ exactly (random events) |
| INJ-R | 30 cells × 2 seeds × 2 inst | within 2 SE 120/120 | correct sign 120/120 | truth = δ exactly (random events) |

## 7. CP6 result table (second-look bar α = 0.001087 on both instruments; cross-instrument sign column)
| h | feature | NIFTY n_eff | NIFTY diff bps | NIFTY p | BANKNIFTY n_eff | BANKNIFTY diff bps | BANKNIFTY p | same sign | verdict | cost |
|---|---|---|---|---|---|---|---|---|---|---|
| 5s | deep_imb_qty | 1706 | +0.025 | 0.0950 | 1703 | +0.029 | 0.1109 | yes | FAIL | PRE-COST / PENDING |
| 5s | deep_imb_orders | 1703 | +0.007 | 0.6242 | 1692 | +0.036 | 0.0455 | yes | FAIL | PRE-COST / PENDING |
| 5s | slope_diff | 1707 | -0.047 | 0.0030 | 1707 | -0.024 | 0.1829 | yes | FAIL | PRE-COST / PENDING |
| 5s | conc_diff | 1705 | +0.005 | 0.7551 | 1707 | +0.044 | 0.0180 | yes | FAIL | PRE-COST / PENDING |
| 5s | wall_appear_bid_w | 1684 | -0.012 | 0.4533 | 1687 | +0.061 | 0.0005 | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 5s | wall_appear_ask_w | 1700 | +0.013 | 0.3643 | 1678 | -0.013 | 0.4753 | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 5s | wall_disappear_bid_w | 1664 | -0.035 | 0.0250 | 1688 | +0.049 | 0.0110 | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 5s | wall_disappear_ask_w | 1701 | +0.009 | 0.5747 | 1683 | -0.001 | 0.9480 | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 5s | deep_refill_bid_w | 1699 | +0.048 | 0.0015 | 1691 | +0.050 | 0.0070 | yes | FAIL | PRE-COST / PENDING |
| 5s | deep_refill_ask_w | 1714 | -0.045 | 0.0025 | 1697 | -0.030 | 0.0970 | yes | FAIL | PRE-COST / PENDING |
| 30s | deep_imb_qty | 745 | +0.078 | 0.1399 | 862 | +0.287 | 0.0005 | yes | FAIL | PRE-COST / PENDING |
| 30s | deep_imb_orders | 751 | +0.062 | 0.2324 | 972 | +0.250 | 0.0005 | yes | FAIL | PRE-COST / PENDING |
| 30s | slope_diff | 973 | -0.032 | 0.5097 | 1026 | -0.025 | 0.6487 | yes | FAIL | PRE-COST / PENDING |
| 30s | conc_diff | 669 | +0.068 | 0.2169 | 775 | +0.073 | 0.2534 | yes | FAIL | PRE-COST / PENDING |
| 30s | wall_appear_bid_w | 382 | -0.043 | 0.5707 | 424 | +0.254 | 0.0015 | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | wall_appear_ask_w | 375 | +0.019 | 0.8016 | 403 | -0.079 | 0.3683 | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | wall_disappear_bid_w | 376 | -0.153 | 0.0455 | 421 | +0.186 | 0.0305 | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | wall_disappear_ask_w | 373 | -0.011 | 0.8816 | 402 | +0.003 | 0.9750 | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | deep_refill_bid_w | 412 | +0.143 | 0.0410 | 395 | +0.171 | 0.0480 | yes | FAIL | PRE-COST / PENDING |
| 30s | deep_refill_ask_w | 399 | -0.192 | 0.0070 | 392 | -0.184 | 0.0405 | yes | FAIL | PRE-COST / PENDING |
| 120s | deep_imb_qty | 417 | +0.045 | 0.7666 | 515 | +0.467 | 0.0045 | yes | FAIL | PRE-COST / PENDING |
| 120s | deep_imb_orders | 417 | +0.097 | 0.4738 | 601 | +0.433 | 0.0045 | yes | FAIL | PRE-COST / PENDING |
| 120s | slope_diff | 634 | +0.066 | 0.5802 | 691 | +0.061 | 0.6687 | yes | FAIL | PRE-COST / PENDING |
| 120s | conc_diff | 421 | +0.078 | 0.6137 | 466 | +0.190 | 0.2629 | yes | FAIL | PRE-COST / PENDING |
| 120s | wall_appear_bid_w | 184 | -0.086 | 0.6827 | 228 | +0.248 | 0.3128 | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 120s | wall_appear_ask_w | 169 | +0.041 | 0.8676 | 205 | +0.277 | 0.2884 | yes | FAIL | PRE-COST / PENDING |
| 120s | wall_disappear_bid_w | 185 | -0.105 | 0.5942 | 230 | +0.131 | 0.5802 | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 120s | wall_disappear_ask_w | 172 | -0.050 | 0.8286 | 211 | +0.543 | 0.0410 | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 120s | deep_refill_bid_w | 192 | +0.017 | 0.9360 | 181 | +0.238 | 0.3978 | yes | FAIL | PRE-COST / PENDING |
| 120s | deep_refill_ask_w | 190 | -0.135 | 0.5472 | 184 | -0.656 | 0.0155 | yes | FAIL | PRE-COST / PENDING |
| close | deep_imb_qty | 1706 | +8.422 | 0.0005 | 1703 | -8.439 | 0.0005 | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | deep_imb_orders | 1703 | +3.853 | 0.0005 | 1692 | -3.024 | 0.0005 | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | slope_diff | 1707 | +9.773 | 0.0005 | 1707 | +1.443 | 0.0395 | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | conc_diff | 1707 | +4.498 | 0.0005 | 1707 | -0.698 | 0.3178 | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | wall_appear_bid_w | 1685 | -3.840 | 0.0005 | 1687 | -0.227 | 0.7341 | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | wall_appear_ask_w | 1701 | -5.367 | 0.0005 | 1679 | +5.154 | 0.0005 | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | wall_disappear_bid_w | 1665 | -3.726 | 0.0005 | 1688 | +0.289 | 0.6807 | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | wall_disappear_ask_w | 1702 | -5.066 | 0.0005 | 1684 | +5.316 | 0.0005 | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | deep_refill_bid_w | 1699 | +37.132 | 0.0005 | 1691 | +1.815 | 0.0120 | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | deep_refill_ask_w | 1714 | +11.710 | 0.0005 | 1698 | +2.092 | 0.0035 | yes | UNPOWERED — not scored | PRE-COST / PENDING |

### Run-1 comparison (shallow L1–5 refill from run 1 vs deep L6–20; run-1 numbers from its hashed result file)
| h | run | feature | NIFTY diff bps (±2 SE) | NIFTY p | BANKNIFTY diff bps (±2 SE) | BANKNIFTY p | same sign | meets its run's bar | beats run 1 (PREREG2 §10) |
|---|---|---|---|---|---|---|---|---|---|
| 30s | run 1 (L1–5) | ask_refills | -0.525 (±0.183) | 0.0010 | -0.510 (±0.292) | 0.0010 | yes | yes | — |
| 30s | run 2 (L6–20) | deep_refill_ask_w | -0.192 (±0.203) | 0.0070 | -0.184 (±0.254) | 0.0405 | yes | no | no (weaker than shallow) |
| 30s | run 1 (L1–5) | bid_refills | +0.381 (±0.171) | 0.0010 | +0.194 (±0.260) | 0.0220 | yes | no | — |
| 30s | run 2 (L6–20) | deep_refill_bid_w | +0.143 (±0.200) | 0.0410 | +0.171 (±0.253) | 0.0480 | yes | no | no (weaker than shallow) |
| 30s | run 2 best other (lowest max p, same sign) | deep_imb_qty | +0.078 (±0.149) | 0.1399 | +0.287 (±0.171) | 0.0005 | yes | no | no |
| 120s | run 1 (L1–5) | ask_refills | -0.677 (±0.436) | 0.0010 | -0.838 (±0.685) | 0.0010 | yes | yes | — |
| 120s | run 2 (L6–20) | deep_refill_ask_w | -0.135 (±0.594) | 0.5472 | -0.656 (±0.768) | 0.0155 | yes | no | no (weaker than shallow) |
| 120s | run 1 (L1–5) | bid_refills | +0.384 (±0.409) | 0.0040 | +0.358 (±0.621) | 0.0749 | yes | no | — |
| 120s | run 2 (L6–20) | deep_refill_bid_w | +0.017 (±0.590) | 0.9360 | +0.238 (±0.774) | 0.3978 | yes | no | no (weaker than shallow) |
| 120s | run 2 best other (lowest max p, same sign) | deep_imb_orders | +0.097 (±0.401) | 0.4738 | +0.433 (±0.425) | 0.0045 | yes | no | no |

## 8. 🔑 THE DECISION
On tape first proven clean (38 of 40 sessions; two corrupt Mondays excluded), levels 6–20 of the book carried no readable aggressor-free signal at 5, 30 or 120 seconds: none of the 30 pre-registered cells cleared the second-look bar, eleven were sign flips between the two instruments, the only sub-bar hint (deep qty/order imbalance on BANKNIFTY, +0.3 to +0.5 bp) is absent on NIFTY, and the deep refill — the direct descendant of run 1's one surviving effect — points the same way but at roughly a third of the shallow magnitude and does not reach significance. This is not a case of "the sample cannot tell": the sample was powered to detect effects a third the size of run 1's half-basis-point effect at 30 s (MDE 0.18–0.36 bp), so a deep-book effect of run 1's order would have been seen. What the measurements support for the purpose tested is therefore **STOP recording levels 6–20 for this purpose — the 5-level slice already contains the only effect found, and it is itself below the repo's documented cost references (PRE-COST / PENDING)**; the decision is the user's, and two limits bound it: (i) the session-close horizon cannot be answered by this or any practical sample — NIFTY_FUT: best close cell deep_imb_orders has n_eff = 38 sessions, MDE 38.3 pts vs median |move to close| 30.1 pts → sessions with events needed for MDE ≤ median move = 38 × (38.3/30.1)² = 62 (i.e. 24 more); for an effect of run 1's size (0.5 bp) at close: 38 × (15.8/0.5)² ≈ 37,892 sessions; BANKNIFTY_FUT: best close cell slope_diff has n_eff = 38 sessions, MDE 107.5 pts vs median |move to close| 75.8 pts → sessions with events needed for MDE ≤ median move = 38 × (107.5/75.8)² = 76 (i.e. 39 more); for an effect of run 1's size (0.5 bp) at close: 38 × (18.6/0.5)² ≈ 52,803 sessions — and (ii) only the ten pre-registered deep features at one configuration were tested. Separately from the study, the recorder has an intermittent defect that corrupted two Mondays; that is a fact about the recorder, not about the deep levels.

## 9. Still NOT MEASURED after this run
- Cost per event (ATM premium + recorded delta): the repo model was not applied; every result is PRE-COST / PENDING.
- Eaten-vs-pulled at any level (disqualified by construction); the REASONING that deep decreases are less contaminated was stated, not measured.
- The root cause of the 08-17 / 08-24 negative ask-side prices (both late-starting Mondays), and whether the defect recurs after 09-04.
- Session-close horizon (unpowered); regimes beyond this 8-week window; capturability as fills (mid-price only, no execution modelled).
- Deep features not pre-registered here (other windows, other percentiles, other definitions of imbalance or slope, cross-level queue dynamics); sensitivity to the 5-second bar, the 10-bar window, the P90 wall rule and k = 5.
- The P6 JSON outputs (not on this machine, not in S3).
- Whether the 5-level effect itself survives on the 13 new sessions (run 1 was not re-scored here; PREREG2 did not include it).
