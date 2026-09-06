# CP6 (run 3) — SCORE: DISCOVERY, THEN ONE LOOK AT CONFIRMATION

Scorer `scripts/scorer3.py` per PREREG3 (thinned events ≥ 300 s; B = 2000 slot × σ-quintile matched draws with random orientation; third-look α = 0.000926 on both instruments; same sign; n_resolved ≥ 100). Discovery scored twice (`cp6_result_run1.json` = `cp6_result_run2.json`: identical) and again inside the final pass. Unresolved trades are counted (censored share shown) and marked at the session-close mid for the expectancy.

## Discovery (26 sessions)
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

## Frozen after discovery
[['F1', 1.0, 1.0]]

## Confirmation (12 sessions; read ONCE, stage CP6; access-logged) — scored only for the frozen cells
Events on confirmation: NIFTY F1 thinned 209 (F2 38); BANKNIFTY F1 161 (F2 25).
| cell | inst | discovery lift (p) | confirmation n / resolved (censored) | win | matched base | lift pp | p | E[R] | verdict |
|---|---|---|---|---|---|---|---|---|---|
| F1 1.0σ/1.0σ | NIFTY_FUT | +14.8 (p 0.0005) | 209 / 209 (0.0%) | 56.0% | 49.9% | +6.1 | 0.0845 | +0.120 | FAIL confirmation (magnitude < 50% of discovery) |
| F1 1.0σ/1.0σ | BANKNIFTY_FUT | +9.5 (p 0.0005) | 161 / 161 (0.0%) | 56.5% | 50.0% | +6.5 | 0.1009 | +0.130 | CONFIRMED (PRE-COST / PENDING) |

### Actual confirmation power (PREREG3 §8 re-stated on the actual count)
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

## Cost in R (PREREG3 §7 references; PRE-COST / PENDING, never GREEN)
| inst | cell | reference | cost / stop | discovery | confirmation |
|---|---|---|---|---|---|
| NIFTY_FUT | F1 1.0σ/1.0σ | option_path_fut_pts = 2.62 pts | 0.54 R | disc E[R] +0.294 → net -0.246 R | conf E[R] +0.120 → net -0.420 R |
| NIFTY_FUT | F1 1.0σ/1.0σ | futures_before_spread_fut_pts = 7.24 pts | 1.50 R | disc E[R] +0.294 → net -1.206 R | conf E[R] +0.120 → net -1.380 R |
| BANKNIFTY_FUT | F1 1.0σ/1.0σ | option_path_fut_pts = 7.96 pts | 0.57 R | disc E[R] +0.188 → net -0.382 R | conf E[R] +0.130 → net -0.440 R |
| BANKNIFTY_FUT | F1 1.0σ/1.0σ | futures_before_spread_fut_pts = 17.2 pts | 1.22 R | disc E[R] +0.188 → net -1.032 R | conf E[R] +0.130 → net -1.090 R |

## Head-to-head vs run 1
| framing | cell | NIFTY effect | NIFTY p | BANKNIFTY effect | BANKNIFTY p | same sign | met its run's bar |
|---|---|---|---|---|---|---|---|
| run 1 mean return (L1–5) | ask_refills @30s | -0.525 bp | 0.0010 | -0.510 bp | 0.0010 | yes | yes |
| run 1 mean return (L1–5) | ask_refills @120s | -0.677 bp | 0.0010 | -0.838 bp | 0.0010 | yes | yes |
| run 1 mean return (L1–5) | bid_refills @30s | +0.381 bp | 0.0010 | +0.194 bp | 0.0220 | yes | no |
| run 3 hit-first (discovery) | F1 1.0σ/1.0σ | +14.8 pp (E[R] +0.29) | 0.0005 | +9.5 pp (E[R] +0.19) | 0.0005 | yes | yes |
| run 3 hit-first (discovery) | F1 1.0σ/3.0σ | +8.8 pp (E[R] +0.44) | 0.0010 | +8.5 pp (E[R] +0.43) | 0.0005 | yes | no |
| run 3 hit-first (discovery) | F1 2.0σ/2.0σ | +9.0 pp (E[R] +0.17) | 0.0005 | +6.5 pp (E[R] +0.13) | 0.0060 | yes | no |
| run 3 hit-first (discovery) | F1 3.0σ/3.0σ | +5.6 pp (E[R] +0.11) | 0.0095 | +7.2 pp (E[R] +0.13) | 0.0030 | yes | no |

## Self-check
Discovery scoring deterministic across two runs; the final pass reproduced the same discovery cells (frozen list identical). Access log after CP6: confirmation reads happened only at stage CP6.
