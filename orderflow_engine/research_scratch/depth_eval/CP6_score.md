# CP6 — SCORE (one run, exactly as pre-registered; second run byte-identical)

`scripts/cp6_score.py` on the stored features, PREREG §2–§7, seed 20260905, B=1000. Run twice: `cp6_result_run1.json` and `cp6_result_run2.json` sha256 both `4649f422421b85d389a1c0fabe8614a5942f0fdacd9be961d425915e31b7d895` → deterministic, no non-determinism to report.
Cost: the repo's cost model (PREREG §8) needs an ATM premium and a recorded delta per event, which this run does not measure → nothing is cost-adjusted; every cell is **PRE-COST / PENDING**. No cell is GREEN.

## Result table (16 scored cells + the pre-registered but UNPOWERED close horizon)
| horizon | feature | inst | n_raw | n_eff | mean fwd (event) pts | baseline mean pts | diff pts | diff bps | sd event | sd non-event | p | sign | same sign both | verdict | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5s | bid_refills | NIFTY_FUT | 820 | 820 | +0.229 | +0.008 | +0.222 | +0.091 | 1.341 | 1.582 | 0.001 | + | yes | FAIL | PRE-COST / PENDING |
| 5s | bid_refills | BANKNIFTY_FUT | 575 | 575 | +0.429 | +0.028 | +0.401 | +0.070 | 4.317 | 4.508 | 0.024 | + | yes | FAIL | PRE-COST / PENDING |
| 5s | ask_refills | NIFTY_FUT | 754 | 754 | -0.284 | +0.011 | -0.296 | -0.122 | 1.309 | 1.582 | 0.001 | − | yes | FAIL | PRE-COST / PENDING |
| 5s | ask_refills | BANKNIFTY_FUT | 363 | 363 | -0.679 | +0.014 | -0.693 | -0.120 | 5.363 | 4.503 | 0.005 | − | yes | FAIL | PRE-COST / PENDING |
| 5s | bid_refills_w | NIFTY_FUT | 1017 | 1017 | +0.140 | +0.010 | +0.130 | +0.054 | 1.338 | 1.582 | 0.009 | + | yes | FAIL | PRE-COST / PENDING |
| 5s | bid_refills_w | BANKNIFTY_FUT | 911 | 911 | +0.456 | +0.012 | +0.444 | +0.077 | 4.551 | 4.506 | 0.003 | + | yes | FAIL | PRE-COST / PENDING |
| 5s | ask_refills_w | NIFTY_FUT | 978 | 978 | -0.171 | +0.006 | -0.176 | -0.073 | 1.300 | 1.582 | 0.002 | − | yes | FAIL | PRE-COST / PENDING |
| 5s | ask_refills_w | BANKNIFTY_FUT | 866 | 866 | -0.369 | +0.010 | -0.379 | -0.066 | 5.491 | 4.498 | 0.007 | − | yes | FAIL | PRE-COST / PENDING |
| 30s | bid_refills | NIFTY_FUT | 818 | 619 | +0.966 | +0.040 | +0.925 | +0.381 | 3.098 | 3.657 | 0.001 | + | yes | FAIL | PRE-COST / PENDING |
| 30s | bid_refills | BANKNIFTY_FUT | 574 | 417 | +1.212 | +0.091 | +1.120 | +0.194 | 9.299 | 10.816 | 0.022 | + | yes | FAIL | PRE-COST / PENDING |
| 30s | ask_refills | NIFTY_FUT | 753 | 538 | -1.228 | +0.047 | -1.275 | -0.525 | 3.319 | 3.656 | 0.001 | − | yes | PRE-COST PASS / PENDING | PRE-COST / PENDING |
| 30s | ask_refills | BANKNIFTY_FUT | 363 | 331 | -2.839 | +0.100 | -2.939 | -0.510 | 11.902 | 10.807 | 0.001 | − | yes | PRE-COST PASS / PENDING | PRE-COST / PENDING |
| 30s | bid_refill_ratio | NIFTY_FUT | 263 | 250 | +0.216 | +0.026 | +0.190 | +0.078 | 3.892 | 3.652 | 0.425 | + | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | bid_refill_ratio | BANKNIFTY_FUT | 107 | 106 | -0.547 | +0.126 | -0.673 | -0.117 | 11.848 | 10.811 | 0.519 | − | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | ask_refill_ratio | NIFTY_FUT | 179 | 171 | -0.094 | +0.039 | -0.132 | -0.054 | 3.869 | 3.653 | 0.629 | − | yes | FAIL | PRE-COST / PENDING |
| 30s | ask_refill_ratio | BANKNIFTY_FUT | 98 | 94 | -1.278 | +0.152 | -1.429 | -0.248 | 11.562 | 10.812 | 0.221 | − | yes | FAIL | PRE-COST / PENDING |
| 30s | bid_refills_w | NIFTY_FUT | 1014 | 275 | +0.665 | +0.018 | +0.646 | +0.266 | 3.287 | 3.658 | 0.005 | + | yes | FAIL | PRE-COST / PENDING |
| 30s | bid_refills_w | BANKNIFTY_FUT | 911 | 224 | +1.797 | +0.043 | +1.755 | +0.305 | 9.518 | 10.822 | 0.014 | + | yes | FAIL | PRE-COST / PENDING |
| 30s | ask_refills_w | NIFTY_FUT | 978 | 256 | -0.897 | +0.045 | -0.942 | -0.388 | 3.050 | 3.658 | 0.001 | − | yes | PRE-COST PASS / PENDING | PRE-COST / PENDING |
| 30s | ask_refills_w | BANKNIFTY_FUT | 866 | 238 | -2.247 | +0.047 | -2.293 | -0.398 | 12.672 | 10.800 | 0.003 | − | yes | PRE-COST PASS / PENDING | PRE-COST / PENDING |
| 120s | bid_refills | NIFTY_FUT | 811 | 438 | +1.066 | +0.134 | +0.932 | +0.384 | 6.743 | 7.355 | 0.004 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | bid_refills | BANKNIFTY_FUT | 572 | 317 | +2.406 | +0.343 | +2.064 | +0.358 | 22.066 | 22.530 | 0.075 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | ask_refills | NIFTY_FUT | 749 | 385 | -1.559 | +0.087 | -1.646 | -0.677 | 6.716 | 7.351 | 0.001 | − | yes | PRE-COST PASS / PENDING | PRE-COST / PENDING |
| 120s | ask_refills | BANKNIFTY_FUT | 362 | 261 | -4.681 | +0.150 | -4.831 | -0.838 | 22.744 | 22.531 | 0.001 | − | yes | PRE-COST PASS / PENDING | PRE-COST / PENDING |
| 120s | bid_refill_ratio | NIFTY_FUT | 263 | 228 | -0.143 | +0.094 | -0.237 | -0.097 | 7.676 | 7.347 | 0.609 | − | yes | FAIL | PRE-COST / PENDING |
| 120s | bid_refill_ratio | BANKNIFTY_FUT | 107 | 100 | -1.437 | +0.398 | -1.835 | -0.318 | 21.659 | 22.529 | 0.423 | − | yes | FAIL | PRE-COST / PENDING |
| 120s | ask_refill_ratio | NIFTY_FUT | 179 | 155 | +0.373 | +0.086 | +0.287 | +0.118 | 7.371 | 7.347 | 0.632 | + | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 120s | ask_refill_ratio | BANKNIFTY_FUT | 98 | 85 | -0.456 | +0.404 | -0.860 | -0.149 | 22.085 | 22.530 | 0.720 | − | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 120s | bid_refills_w | NIFTY_FUT | 993 | 169 | +1.368 | +0.054 | +1.314 | +0.541 | 5.965 | 7.359 | 0.024 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | bid_refills_w | BANKNIFTY_FUT | 911 | 129 | +2.748 | +0.177 | +2.571 | +0.446 | 23.805 | 22.525 | 0.201 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | ask_refills_w | NIFTY_FUT | 978 | 144 | -1.903 | +0.078 | -1.981 | -0.815 | 6.387 | 7.353 | 0.003 | − | yes | FAIL | PRE-COST / PENDING |
| 120s | ask_refills_w | BANKNIFTY_FUT | 866 | 145 | -3.530 | +0.323 | -3.853 | -0.669 | 22.953 | 22.533 | 0.042 | − | yes | FAIL | PRE-COST / PENDING |
| close | bid_refills | NIFTY_FUT | 820 | 820 | +1.546 | +13.905 | -12.359 | -5.085 | 39.262 | 55.189 | 0.001 | − | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | bid_refills | BANKNIFTY_FUT | 575 | 575 | +78.320 | +43.510 | +34.811 | +6.042 | 178.061 | 180.377 | 0.001 | + | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | ask_refills | NIFTY_FUT | 754 | 754 | +13.858 | +13.899 | -0.041 | -0.017 | 47.234 | 55.148 | 0.983 | − | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | ask_refills | BANKNIFTY_FUT | 363 | 363 | +72.189 | +38.227 | +33.962 | +5.895 | 204.170 | 180.291 | 0.001 | + | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | bid_refill_ratio | NIFTY_FUT | 264 | 264 | +10.953 | +13.001 | -2.047 | -0.842 | 56.248 | 55.096 | 0.544 | − | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | bid_refill_ratio | BANKNIFTY_FUT | 107 | 107 | +38.652 | +40.979 | -2.326 | -0.404 | 160.128 | 180.400 | 0.904 | − | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | ask_refill_ratio | NIFTY_FUT | 181 | 181 | +20.016 | +13.171 | +6.845 | +2.816 | 51.970 | 55.103 | 0.095 | + | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | ask_refill_ratio | BANKNIFTY_FUT | 98 | 98 | +80.443 | +43.767 | +36.676 | +6.366 | 238.805 | 180.319 | 0.060 | + | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | bid_refills_w | NIFTY_FUT | 1017 | 1017 | -2.793 | +13.706 | -16.499 | -6.788 | 34.478 | 55.231 | 0.001 | − | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | bid_refills_w | BANKNIFTY_FUT | 911 | 911 | +69.423 | +43.477 | +25.946 | +4.503 | 201.886 | 180.178 | 0.001 | + | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | ask_refills_w | NIFTY_FUT | 978 | 978 | +15.754 | +13.466 | +2.288 | +0.941 | 48.901 | 55.150 | 0.200 | + | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | ask_refills_w | BANKNIFTY_FUT | 866 | 866 | +98.095 | +44.496 | +53.599 | +9.303 | 229.911 | 179.873 | 0.001 | + | yes | UNPOWERED — not scored | PRE-COST / PENDING |

## Reading the table
- **3 of 16 scored cells meet the pre-registered pass bar (PRE-COST PASS / PENDING):** ask_refills @30s (NIFTY -1.27 pts p=0.001; BANKNIFTY -2.94 pts p=0.001); ask_refills_w @30s (NIFTY -0.94 pts p=0.001; BANKNIFTY -2.29 pts p=0.003); ask_refills @120s (NIFTY -1.65 pts p=0.001; BANKNIFTY -4.83 pts p=0.001). They are one underlying feature — ask-side refill bursts — at adjacent horizons (ask_refills_w is the 10-bar rolling sum of ask_refills), so this is one finding, not three independent ones.
- Sign structure: every count feature (bid/ask refills and their rolling sums) has the SAME sign on both instruments at 5 s, 30 s and 120 s (12/12 cells): ask-side refill bursts precede a lower mid, bid-side bursts a higher mid. The bid-side cells fail only because BANKNIFTY's p is above 0.003125 (0.003–0.201), not by sign.
- **2 sign flips**, both on the ratio features (bid_refill_ratio @30 s, ask_refill_ratio @120 s); the ratio features show nothing on either instrument (p 0.22–0.72).
- Session close: sign flips and ±12–54 pt differences on n_eff = 15–25 sessions; UNPOWERED per CP2, reported, not scored.
- Magnitude for readability only (not a pass/fail input): the passing cells are 0.4–0.8 bps of mid over 30–120 s, i.e. NIFTY −1.28 / −0.94 / −1.65 pts and BANKNIFTY −2.94 / −2.29 / −4.83 pts, against the repo's own documented reference lines of 2.62 (NIFTY) / 7.96 (BANKNIFTY) future-points for an option round trip and 7.24 / 17.2 future-points for a futures round trip before spread (TAPE_NOTES.md 710–713, verbatim in PREREG §8). Those references are ASSUMPTIONS flagged as such in the repo and were not applied.
- Concentration flags from CP4 (BANKNIFTY bid-side features on 2026-07-20) touch bid-side cells, none of which pass; the passing ask-side cells have top-session shares of 15–17%.

## Self-check
End-to-end re-run on the stored features: byte-identical output (hashes above).

## Gate
None at this checkpoint — reported as found.
