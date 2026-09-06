# CP4 (run 3) — COMPUTE ON DISCOVERY ONLY

Events marked on the 52 discovery fp tables with the thresholds and σ-quintile edges frozen in `cp2_baseline.json` (PREREG3 hash); F1 = bid xor ask burst, oriented; F2 = F1 ∧ within 1.0·σ of a reference level ∧ previous-session levels defined; thinned ≥ 300 s within a session. Written to `features_discovery/` (per-session tables with `usable`, `sbucket`, `dir`, `F1`, `F2`, `F1_thin`, `F2_thin`, plus `events_<inst>.parquet`).

| inst | feature | raw | thinned | thinned / session | sessions with events | per-session min/med/max | top session (share) | orientation split | verdict |
|---|---|---|---|---|---|---|---|---|---|
| NIFTY_FUT | F1 | 1593 | 559 | 21.5 | 26 | 5/22/37 | 2026-07-28 (7%) | +1 291 / −1 268 | spread OK |
| NIFTY_FUT | F2 | 307 | 127 | 4.9 | 22 | 1/4/19 | 2026-08-10 (15%) | +1 78 / −1 49 | spread OK |
| BANKNIFTY_FUT | F1 | 930 | 435 | 16.7 | 26 | 6/16/34 | 2026-07-20 (8%) | +1 235 / −1 200 | spread OK |
| BANKNIFTY_FUT | F2 | 150 | 75 | 2.9 | 22 | 1/2/15 | 2026-07-20 (20%) | +1 43 / −1 32 | spread OK |

## Self-checks
- Recompute from scratch (stage CP4, guarded read) of 2026-07-16 BANKNIFTY_FUT vs the CP2-written table: **BYTE-IDENTICAL**.
- Access log (`access_log.jsonl`): allowed reads by stage {'CP2': 52, 'CP1': 2, 'CP4': 1}; **allowed reads of confirmation dates: 0**; denied attempts (guard test): 4.
- `self-check found`: CP2's count-only F2 figure for BANKNIFTY was 151 raw / 76 thinned; the sealed F2 definition additionally requires previous-session levels to exist (07-13 has none), giving 150 / 75 here; NIFTY 307 / 127 identical on both paths. Recorded; no change to the sealed definition.

## Gate
No feature concentrates in fewer than 3 sessions (F1 26/26, F2 22/26; top shares 7–20%). **CP4 GREEN.** Note for scoring: BANKNIFTY F2 has 75 thinned events < the pre-registered n_resolved ≥ 100, so no F2 cell can pass on BANKNIFTY by construction; it is scored and reported anyway.
