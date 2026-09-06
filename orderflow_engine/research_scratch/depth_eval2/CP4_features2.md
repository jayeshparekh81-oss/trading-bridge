# CP4 (run 2) — FEATURE COMPUTATION (still no outcomes)

`scripts/features2.py` → `deep_book.compute_session` (hash frozen in PREREG2) for the 38 usable dates × 2 instruments = 76 sessions, streamed from S3 (486 s), per-session parquet in `features/` (76 files, 29 MB). Columns: bar_end_ns, slot, bid1, ask1, mid, per-side deep_q/deep_o/conc/slope, the four signed diffs, per-side per-bar counts and `_w` sums for wall_appear / wall_disappear / deep_refill.

## Recompute-from-scratch self-check
Four sessions recomputed from S3 into `features_recheck/` and compared with the stored files — 2026-07-14 NIFTY_FUT, 2026-07-29 BANKNIFTY_FUT (first roll day), 2026-08-26 BANKNIFTY_FUT (second roll day), 2026-09-04 NIFTY_FUT (newest): **byte-identical 4/4, row-identical 4/4** (2026-07-14_NIFTY_FUT.parquet, 2026-07-29_BANKNIFTY_FUT.parquet, 2026-08-26_BANKNIFTY_FUT.parquet, 2026-09-04_NIFTY_FUT.parquet).

## Rows in, events out, per-session spread (triggers frozen in cp2_power2.json)

### NIFTY_FUT: 38 sessions, 7,264,084 depth rows in, 171,000 bars
| feature | events out | sessions with events | events/session min/median/max | top session (share) | verdict |
|---|---|---|---|---|---|
| deep_imb_qty | 1706 | 37 | 0/20/276 | 2026-07-16 (16%) | spread OK |
| deep_imb_orders | 1703 | 38 | 3/24/246 | 2026-07-29 (14%) | spread OK |
| slope_diff | 1707 | 38 | 7/27/298 | 2026-07-27 (17%) | spread OK |
| conc_diff | 1707 | 38 | 4/35/164 | 2026-07-27 (10%) | spread OK |
| wall_appear_bid_w | 1689 | 27 | 0/17/247 | 2026-09-02 (15%) | spread OK |
| wall_appear_ask_w | 1701 | 25 | 0/7/859 | 2026-07-23 (50%) | spread OK; CONCENTRATION FLAG 2026-07-23 = 50% |
| wall_disappear_bid_w | 1669 | 26 | 0/18/243 | 2026-09-02 (15%) | spread OK |
| wall_disappear_ask_w | 1702 | 26 | 0/5/878 | 2026-07-23 (52%) | spread OK; CONCENTRATION FLAG 2026-07-23 = 52% |
| deep_refill_bid_w | 1699 | 10 | 0/0/845 | 2026-08-25 (50%) | spread OK; CONCENTRATION FLAG 2026-08-25 = 50% |
| deep_refill_ask_w | 1714 | 13 | 0/0/345 | 2026-08-19 (20%) | spread OK |

### BANKNIFTY_FUT: 38 sessions, 7,256,702 depth rows in, 171,000 bars
| feature | events out | sessions with events | events/session min/median/max | top session (share) | verdict |
|---|---|---|---|---|---|
| deep_imb_qty | 1703 | 37 | 0/36/291 | 2026-08-06 (17%) | spread OK |
| deep_imb_orders | 1692 | 36 | 0/12/435 | 2026-08-06 (26%) | spread OK |
| slope_diff | 1707 | 38 | 10/36/198 | 2026-08-06 (12%) | spread OK |
| conc_diff | 1707 | 38 | 2/35/189 | 2026-08-03 (11%) | spread OK |
| wall_appear_bid_w | 1687 | 25 | 0/7/613 | 2026-09-02 (36%) | spread OK; CONCENTRATION FLAG 2026-09-02 = 36% |
| wall_appear_ask_w | 1679 | 27 | 0/10/495 | 2026-09-02 (29%) | spread OK |
| wall_disappear_bid_w | 1688 | 25 | 0/7/574 | 2026-09-02 (34%) | spread OK; CONCENTRATION FLAG 2026-09-02 = 34% |
| wall_disappear_ask_w | 1684 | 27 | 0/9/504 | 2026-09-02 (30%) | spread OK |
| deep_refill_bid_w | 1691 | 8 | 0/0/453 | 2026-08-25 (27%) | spread OK |
| deep_refill_ask_w | 1698 | 14 | 0/0/614 | 2026-08-06 (36%) | spread OK; CONCENTRATION FLAG 2026-08-06 = 36% |

Per-session table: `cp4_events_by_session2.json`.

## Gate
No feature has its events in fewer than 3 sessions (minimum: BANKNIFTY deep_refill_bid_w, 8 sessions; NIFTY deep_refill_bid_w, 10). → no SINGLE-EPISODE exclusion. Concentration flags (one session ≥ 30% of events): NIFTY wall_appear_ask_w and wall_disappear_ask_w (2026-07-23, 50% / 52%), NIFTY deep_refill_bid_w (2026-08-25, 50%), BANKNIFTY wall_appear_bid_w / wall_disappear_bid_w (2026-09-02, 36% / 34%), BANKNIFTY deep_refill_ask_w (2026-08-06, 36%). Deep-refill events cluster in a few very active sessions because the trigger is a pooled 99th percentile and deep refill activity varies by an order of magnitude across days. All stay in scoring per PREREG2, flagged. **CP4 GREEN.**
