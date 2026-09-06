# CP5 (run 3) — CALIBRATION of the first-passage engine

Harness: run-1/2 fixes kept (seed sequences [seed, ·] → non-overlapping seeds 101 / 202; deterministic pickers; recovery tested on random events, never on the real signal). Synthetic driftless Gaussian walk at 5 Hz (σ_step = 0.3 pts, 6.25-h sessions) pushed through the REAL engine (trailing σ_1m + joint object); random events with random orientation; recovered hit-first win rate vs a/(a+b) on the full 7×7 grid; tolerance ±3.0 pp (PREREG3 §9).

## Self-check (why there are two passes)
- `self-check found`: the first pass (30 sessions × 60 events, ~1,790 resolved per cell) had a binomial SE ≈ 1.2 pp per cell, so the worst of 49 correlated cells breached the 3-pp tolerance on seed 202 (3.76 pp) while seed 101's worst was 2.08 pp with no directional pattern; `fixed by` quadrupling the events (60 × 120, SE ≈ 0.55 pp) with the tolerance and seeds unchanged. The first pass is kept in `cp5_calibration_firstpass.json`.
- `self-check found`: the injected-drift comparison used a closed form that assumes no right-censoring; under drift, trades left unresolved at session end are not random with respect to the outcome, so the resolved-only rate exceeded the closed form by 2–5 pp on both seeds, growing with barrier size — the censoring effect itself; `fixed by` comparing on events with ≥ 2 h to session end (unresolved share ≈ 0), closed form unchanged.

### Seed 101
**Driftless walk, second pass (60 sessions × 120 random events):** worst |recovered − a/(a+b)| = **2.23 pp** (tolerance 3.0 pp) → PASS; first pass (30 × 60) was 2.08 pp. Median σ_1m/σ_step = 17.3.
Recovered / theory (%, n resolved):
| stop \ target | 0.25σ | 0.5σ | 0.75σ | 1.0σ | 1.5σ | 2.0σ | 3.0σ |
|---|---|---|---|---|---|---|---|
| 0.25σ | 49.6 / 50.0 (n=7198) | 34.7 / 33.3 (n=7198) | 26.3 / 25.0 (n=7196) | 21.8 / 20.0 (n=7194) | 15.8 / 14.3 (n=7190) | 12.6 / 11.1 (n=7187) | 8.9 / 7.7 (n=7179) |
| 0.5σ | 64.9 / 66.7 (n=7195) | 49.9 / 50.0 (n=7194) | 40.8 / 40.0 (n=7191) | 34.7 / 33.3 (n=7188) | 26.5 / 25.0 (n=7182) | 21.6 / 20.0 (n=7178) | 15.6 / 14.3 (n=7163) |
| 0.75σ | 72.8 / 75.0 (n=7195) | 59.1 / 60.0 (n=7194) | 49.9 / 50.0 (n=7190) | 43.3 / 42.9 (n=7185) | 33.9 / 33.3 (n=7175) | 28.4 / 27.3 (n=7169) | 21.0 / 20.0 (n=7147) |
| 1.0σ | 77.9 / 80.0 (n=7192) | 65.3 / 66.7 (n=7190) | 56.6 / 57.1 (n=7185) | 49.9 / 50.0 (n=7179) | 40.3 / 40.0 (n=7167) | 34.2 / 33.3 (n=7159) | 25.9 / 25.0 (n=7130) |
| 1.5σ | 84.1 / 85.7 (n=7187) | 73.7 / 75.0 (n=7181) | 65.8 / 66.7 (n=7176) | 59.6 / 60.0 (n=7166) | 50.0 / 50.0 (n=7153) | 43.5 / 42.9 (n=7143) | 34.4 / 33.3 (n=7104) |
| 2.0σ | 87.5 / 88.9 (n=7184) | 78.8 / 80.0 (n=7177) | 71.8 / 72.7 (n=7167) | 66.1 / 66.7 (n=7157) | 57.3 / 57.1 (n=7140) | 50.7 / 50.0 (n=7129) | 41.2 / 40.0 (n=7072) |
| 3.0σ | 91.2 / 92.3 (n=7179) | 84.5 / 85.7 (n=7167) | 79.0 / 80.0 (n=7152) | 74.1 / 75.0 (n=7135) | 66.6 / 66.7 (n=7112) | 60.7 / 60.0 (n=7088) | 50.9 / 50.0 (n=7022) |
**Injected drift (+0.01·σ_step per 200 ms step; events with ≥ 2 h to session end; unresolved share on scored pairs [0.0, 0.0, 0.0, 0.0] %):** worst |recovered − closed form| = **1.98 pp** → PASS; first pass (all events, censoring included) was 4.94 pp.
| pair | no-drift theory | closed form with drift | recovered (2nd pass) | n resolved | recovered (1st pass, censoring not excluded) |
|---|---|---|---|---|---|
| 1.0:1.0 | 50.0% | 58.6% | 59.5% | 7200 | 61.6% |
| 1.0:3.0 | 25.0% | 39.1% | 40.4% | 7200 | 44.0% |
| 2.0:2.0 | 50.0% | 66.7% | 68.5% | 7200 | 70.5% |
| 3.0:3.0 | 50.0% | 73.9% | 75.9% | 7200 | 77.8% |
| 1.0:2.0 | 33.3% | 45.3% | 46.4% | 7200 | 49.7% |
| 0.5:0.5 | 50.0% | 54.3% | 55.7% | 7200 | 57.8% |
**RANDX on real discovery tape:** cells passing the pass bar 0/4; p < 0.05 on 1/8 instrument-tests; min p 0.0240; lifts (pp): NIFTY 1.0:1.0 -2.2, NIFTY 1.0:3.0 -1.5, NIFTY 2.0:2.0 +1.9, NIFTY 3.0:3.0 -1.1, BANKN 1.0:1.0 +0.0, BANKN 1.0:3.0 +1.5, BANKN 2.0:2.0 +4.2, BANKN 3.0:3.0 +5.6

### Seed 202
**Driftless walk, second pass (60 sessions × 120 random events):** worst |recovered − a/(a+b)| = **2.35 pp** (tolerance 3.0 pp) → PASS; first pass (30 × 60) was 3.76 pp. Median σ_1m/σ_step = 17.3.
Recovered / theory (%, n resolved):
| stop \ target | 0.25σ | 0.5σ | 0.75σ | 1.0σ | 1.5σ | 2.0σ | 3.0σ |
|---|---|---|---|---|---|---|---|
| 0.25σ | 50.0 / 50.0 (n=7195) | 34.6 / 33.3 (n=7191) | 26.1 / 25.0 (n=7190) | 21.2 / 20.0 (n=7189) | 15.5 / 14.3 (n=7187) | 11.7 / 11.1 (n=7183) | 8.3 / 7.7 (n=7179) |
| 0.5σ | 65.0 / 66.7 (n=7194) | 49.8 / 50.0 (n=7188) | 40.1 / 40.0 (n=7187) | 33.9 / 33.3 (n=7186) | 26.0 / 25.0 (n=7182) | 20.7 / 20.0 (n=7176) | 14.7 / 14.3 (n=7160) |
| 0.75σ | 72.8 / 75.0 (n=7193) | 58.8 / 60.0 (n=7186) | 49.4 / 50.0 (n=7184) | 42.8 / 42.9 (n=7181) | 33.7 / 33.3 (n=7175) | 27.5 / 27.3 (n=7163) | 20.1 / 20.0 (n=7141) |
| 1.0σ | 77.6 / 80.0 (n=7190) | 65.3 / 66.7 (n=7180) | 56.3 / 57.1 (n=7177) | 49.6 / 50.0 (n=7174) | 40.1 / 40.0 (n=7166) | 33.3 / 33.3 (n=7152) | 24.7 / 25.0 (n=7120) |
| 1.5σ | 83.7 / 85.7 (n=7188) | 73.6 / 75.0 (n=7176) | 65.7 / 66.7 (n=7173) | 59.5 / 60.0 (n=7167) | 50.2 / 50.0 (n=7152) | 43.1 / 42.9 (n=7131) | 33.5 / 33.3 (n=7084) |
| 2.0σ | 87.0 / 88.9 (n=7187) | 78.6 / 80.0 (n=7173) | 71.6 / 72.7 (n=7168) | 65.7 / 66.7 (n=7160) | 56.7 / 57.1 (n=7141) | 49.8 / 50.0 (n=7119) | 39.7 / 40.0 (n=7063) |
| 3.0σ | 90.9 / 92.3 (n=7182) | 84.7 / 85.7 (n=7163) | 79.1 / 80.0 (n=7156) | 74.2 / 75.0 (n=7144) | 66.4 / 66.7 (n=7114) | 59.6 / 60.0 (n=7084) | 49.7 / 50.0 (n=7011) |
**Injected drift (+0.01·σ_step per 200 ms step; events with ≥ 2 h to session end; unresolved share on scored pairs [0.0, 0.0, 0.0, 0.0] %):** worst |recovered − closed form| = **1.22 pp** → PASS; first pass (all events, censoring included) was 3.43 pp.
| pair | no-drift theory | closed form with drift | recovered (2nd pass) | n resolved | recovered (1st pass, censoring not excluded) |
|---|---|---|---|---|---|
| 1.0:1.0 | 50.0% | 58.6% | 58.9% | 7200 | 59.5% |
| 1.0:3.0 | 25.0% | 39.0% | 40.2% | 7200 | 40.9% |
| 2.0:2.0 | 50.0% | 66.6% | 66.9% | 7200 | 68.9% |
| 3.0:3.0 | 50.0% | 73.8% | 73.9% | 7200 | 77.3% |
| 1.0:2.0 | 33.3% | 45.3% | 46.4% | 7200 | 47.1% |
| 0.5:0.5 | 50.0% | 54.3% | 53.9% | 7200 | 55.6% |
**RANDX on real discovery tape:** cells passing the pass bar 0/4; p < 0.05 on 0/8 instrument-tests; min p 0.1577; lifts (pp): NIFTY 1.0:1.0 +1.3, NIFTY 1.0:3.0 +2.1, NIFTY 2.0:2.0 +1.5, NIFTY 3.0:3.0 +3.1, BANKN 1.0:1.0 -2.8, BANKN 1.0:3.0 +0.4, BANKN 2.0:2.0 -0.1, BANKN 3.0:3.0 -0.0

## Gate
Driftless grid within tolerance on both seeds: YES; injected drift recovered within tolerance with the correct direction on both seeds: YES; RANDX passes nothing: YES. **CP5 GREEN.**
