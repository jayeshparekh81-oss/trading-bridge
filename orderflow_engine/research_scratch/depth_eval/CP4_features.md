# CP4 — FEATURE COMPUTATION (still no outcomes)

Computed with `scripts/features.py` (sha256 frozen in PREREG) calling the UNMODIFIED `research/depth_proxies.py` engine (defaults; levels=5; trade tape never fed; the cancel/wall events it still emits are DISQUALIFIED — counted in `features/_summary.json`, never stored as features). Per-session parquet: `features/{date}_{inst}.parquet` (52 files incl. the excluded 08-17, 4.4 MB total); columns: bar_end_ns, slot, bid/ask_refills, bid/ask_refill_ratio, bid/ask_refills_w, bid1, ask1, mid.
Bug report at the gate: none — no logic in `depth_proxies.py` needed patching. One data-handling note, not a patch: `snapshot_to_book` treats NaN as truthy; the usable sessions have 0–924 NaN/zero cells among the ten top-5 columns per session (out of ~1.9M cells), left exactly as the file handles them.

## Recompute-from-scratch self-check (stronger than the one-session minimum)
All 50 usable sessions were recomputed from S3 into `features_recheck/` and compared with the stored files: **byte-identical 50/50, row-identical 50/50**, differing: [].

## Rows in, events out, per-session spread (triggers = the thresholds frozen in cp2_power.json)

### NIFTY_FUT: 25 sessions, 4,763,428 depth rows in, 112,500 bars
| feature | events out | sessions with events | events/session min/median/max | top session (share) | verdict |
|---|---|---|---|---|---|
| bid_refills | 820 | 24 | 0/19/136 | 2026-07-28 (17%) | spread OK |
| ask_refills | 754 | 23 | 0/25/110 | 2026-07-16 (15%) | spread OK |
| bid_refill_ratio | 264 | 25 | 2/11/31 | 2026-08-04 (12%) | spread OK |
| ask_refill_ratio | 181 | 24 | 0/5/17 | 2026-08-12 (9%) | spread OK |
| bid_refills_w | 1017 | 15 | 0/20/248 | 2026-07-28 (24%) | spread OK |
| ask_refills_w | 978 | 17 | 0/16/182 | 2026-08-14 (19%) | spread OK |

Per-session table (rows in | engine refill events bid/ask | triggered events per feature): see `cp4_events_by_session.json`.

### BANKNIFTY_FUT: 25 sessions, 4,759,828 depth rows in, 112,500 bars
| feature | events out | sessions with events | events/session min/median/max | top session (share) | verdict |
|---|---|---|---|---|---|
| bid_refills | 575 | 24 | 0/11/180 | 2026-07-20 (31%) | spread OK; CONCENTRATION FLAG: 2026-07-20 = 31% |
| ask_refills | 363 | 25 | 4/12/60 | 2026-07-17 (17%) | spread OK |
| bid_refill_ratio | 107 | 23 | 0/4/15 | 2026-07-16 (14%) | spread OK |
| ask_refill_ratio | 98 | 23 | 0/3/17 | 2026-08-04 (17%) | spread OK |
| bid_refills_w | 911 | 19 | 0/18/334 | 2026-07-20 (37%) | spread OK; CONCENTRATION FLAG: 2026-07-20 = 37% |
| ask_refills_w | 866 | 24 | 0/18/214 | 2026-07-17 (25%) | spread OK |

Per-session table (rows in | engine refill events bid/ask | triggered events per feature): see `cp4_events_by_session.json`.

## Gate
No feature has its events in fewer than 3 distinct sessions (minimum 15 sessions) → no SINGLE-EPISODE exclusion. Two features carry a concentration flag (one session ≥ 30% of events): BANKNIFTY_FUT bid_refills (2026-07-20, 31%) and bid_refills_w (2026-07-20, 37%); NIFTY_FUT bid_refills_w is 24% on 2026-07-28. They stay in scoring per the pre-registered rule, flagged. **CP4 GREEN.**
