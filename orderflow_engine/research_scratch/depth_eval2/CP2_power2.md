# CP2 (run 2) — POWER CHECK (event counts only; no event-conditional outcome computed)

Triggers (stated before counting; per instrument, per 15-minute slot pooled over the 38 usable sessions): SIGNED state features — center = slot median, dev = f − center, event iff |dev| > 0.99-quantile of |dev| in the slot, orientation = sign(dev); COUNT features (trailing 10-bar sums) — event iff value > 0.99-quantile of the slot and > 0 (strict). Unconditional σ_h and median |move|_h over ALL bars are the only outcome-related quantities computed here (MDE arithmetic).
MDE_h = (z₀.₉₇₅ + z₀.₈₀)·σ_h·√(2/n_eff) = 2.80159·σ_h·√(2/n_eff); n_eff = events thinned to ≥ h apart within a session (close: sessions with ≥ 1 event); bps = MDE / mean mid × 10⁴; UNPOWERED if MDE > unconditional median |move|_h. Run-1 reference: 0.5 bp at 30 s → "detects" = MDE_bps(30 s) ≤ 0.5.

### NIFTY_FUT: sessions=38, bars=171,000, mean mid=24,273.71
| horizon | σ (pts) | σ (bps) | median |move| (pts) | bars |
|---|---|---|---|---|
| 5s | 1.513 | 0.62 | 0.450 | 169,065 |
| 30s | 3.487 | 1.44 | 1.650 | 168,840 |
| 120s | 7.022 | 2.89 | 3.750 | 168,104 |
| close | 59.629 | 24.57 | 30.100 | 169,134 |

| feature | kind | n_raw | recount | rate | episodes | per-session min/med/max | top share | sessions | h | n_eff | MDE pts | MDE bps | median|move| | verdict | detects 0.5 bp @30 s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| deep_imb_qty | signed | 1706 | 1706 | 1.01% | 948 | 1/20/276 | 0.16 | 37 | 5s | 1706 | 0.145 | 0.060 | 0.450 | POWERED |  |
| deep_imb_qty | signed | 1706 | 1706 | 1.01% | 948 | 1/20/276 | 0.16 | 37 | 30s | 746 | 0.506 | 0.208 | 1.650 | POWERED | YES |
| deep_imb_qty | signed | 1706 | 1706 | 1.01% | 948 | 1/20/276 | 0.16 | 37 | 120s | 419 | 1.359 | 0.560 | 3.750 | POWERED |  |
| deep_imb_qty | signed | 1706 | 1706 | 1.01% | 948 | 1/20/276 | 0.16 | 37 | close | 37 | 38.840 | 16.001 | 30.100 | UNPOWERED |  |
| deep_imb_orders | signed | 1703 | 1703 | 1.01% | 980 | 3/22/246 | 0.14 | 38 | 5s | 1703 | 0.145 | 0.060 | 0.450 | POWERED |  |
| deep_imb_orders | signed | 1703 | 1703 | 1.01% | 980 | 3/22/246 | 0.14 | 38 | 30s | 752 | 0.504 | 0.208 | 1.650 | POWERED | YES |
| deep_imb_orders | signed | 1703 | 1703 | 1.01% | 980 | 3/22/246 | 0.14 | 38 | 120s | 420 | 1.357 | 0.559 | 3.750 | POWERED |  |
| deep_imb_orders | signed | 1703 | 1703 | 1.01% | 980 | 3/22/246 | 0.14 | 38 | close | 38 | 38.325 | 15.789 | 30.100 | UNPOWERED |  |
| slope_diff | signed | 1707 | 1707 | 1.01% | 1228 | 7/27/298 | 0.17 | 38 | 5s | 1707 | 0.145 | 0.060 | 0.450 | POWERED |  |
| slope_diff | signed | 1707 | 1707 | 1.01% | 1228 | 7/27/298 | 0.17 | 38 | 30s | 973 | 0.443 | 0.182 | 1.650 | POWERED | YES |
| slope_diff | signed | 1707 | 1707 | 1.01% | 1228 | 7/27/298 | 0.17 | 38 | 120s | 635 | 1.104 | 0.455 | 3.750 | POWERED |  |
| slope_diff | signed | 1707 | 1707 | 1.01% | 1228 | 7/27/298 | 0.17 | 38 | close | 38 | 38.325 | 15.789 | 30.100 | UNPOWERED |  |
| conc_diff | signed | 1707 | 1707 | 1.01% | 806 | 4/34/164 | 0.10 | 38 | 5s | 1707 | 0.145 | 0.060 | 0.450 | POWERED |  |
| conc_diff | signed | 1707 | 1707 | 1.01% | 806 | 4/34/164 | 0.10 | 38 | 30s | 670 | 0.534 | 0.220 | 1.650 | POWERED | YES |
| conc_diff | signed | 1707 | 1707 | 1.01% | 806 | 4/34/164 | 0.10 | 38 | 120s | 422 | 1.354 | 0.558 | 3.750 | POWERED |  |
| conc_diff | signed | 1707 | 1707 | 1.01% | 806 | 4/34/164 | 0.10 | 38 | close | 38 | 38.325 | 15.789 | 30.100 | UNPOWERED |  |
| wall_appear_bid_w | count | 1689 | 1689 | 0.99% | 236 | 1/41/247 | 0.15 | 27 | 5s | 1689 | 0.146 | 0.060 | 0.450 | POWERED |  |
| wall_appear_bid_w | count | 1689 | 1689 | 0.99% | 236 | 1/41/247 | 0.15 | 27 | 30s | 383 | 0.706 | 0.291 | 1.650 | POWERED | YES |
| wall_appear_bid_w | count | 1689 | 1689 | 0.99% | 236 | 1/41/247 | 0.15 | 27 | 120s | 186 | 2.040 | 0.840 | 3.750 | POWERED |  |
| wall_appear_bid_w | count | 1689 | 1689 | 0.99% | 236 | 1/41/247 | 0.15 | 27 | close | 27 | 45.467 | 18.731 | 30.100 | UNPOWERED |  |
| wall_appear_ask_w | count | 1701 | 1701 | 0.99% | 211 | 1/16/859 | 0.50 | 25 | 5s | 1701 | 0.145 | 0.060 | 0.450 | POWERED |  |
| wall_appear_ask_w | count | 1701 | 1701 | 0.99% | 211 | 1/16/859 | 0.50 | 25 | 30s | 376 | 0.712 | 0.294 | 1.650 | POWERED | YES |
| wall_appear_ask_w | count | 1701 | 1701 | 0.99% | 211 | 1/16/859 | 0.50 | 25 | 120s | 170 | 2.134 | 0.879 | 3.750 | POWERED |  |
| wall_appear_ask_w | count | 1701 | 1701 | 0.99% | 211 | 1/16/859 | 0.50 | 25 | close | 25 | 47.251 | 19.466 | 30.100 | UNPOWERED |  |
| wall_disappear_bid_w | count | 1669 | 1669 | 0.98% | 240 | 5/40/243 | 0.15 | 26 | 5s | 1669 | 0.147 | 0.060 | 0.450 | POWERED |  |
| wall_disappear_bid_w | count | 1669 | 1669 | 0.98% | 240 | 5/40/243 | 0.15 | 26 | 30s | 377 | 0.712 | 0.293 | 1.650 | POWERED | YES |
| wall_disappear_bid_w | count | 1669 | 1669 | 0.98% | 240 | 5/40/243 | 0.15 | 26 | 120s | 186 | 2.040 | 0.840 | 3.750 | POWERED |  |
| wall_disappear_bid_w | count | 1669 | 1669 | 0.98% | 240 | 5/40/243 | 0.15 | 26 | close | 26 | 46.333 | 19.088 | 30.100 | UNPOWERED |  |
| wall_disappear_ask_w | count | 1702 | 1702 | 1.00% | 217 | 1/15/878 | 0.52 | 26 | 5s | 1702 | 0.145 | 0.060 | 0.450 | POWERED |  |
| wall_disappear_ask_w | count | 1702 | 1702 | 1.00% | 217 | 1/15/878 | 0.52 | 26 | 30s | 374 | 0.714 | 0.294 | 1.650 | POWERED | YES |
| wall_disappear_ask_w | count | 1702 | 1702 | 1.00% | 217 | 1/15/878 | 0.52 | 26 | 120s | 173 | 2.115 | 0.871 | 3.750 | POWERED |  |
| wall_disappear_ask_w | count | 1702 | 1702 | 1.00% | 217 | 1/15/878 | 0.52 | 26 | close | 26 | 46.333 | 19.088 | 30.100 | UNPOWERED |  |
| deep_refill_bid_w | count | 1699 | 1699 | 0.99% | 303 | 2/50/845 | 0.50 | 10 | 5s | 1699 | 0.145 | 0.060 | 0.450 | POWERED |  |
| deep_refill_bid_w | count | 1699 | 1699 | 0.99% | 303 | 2/50/845 | 0.50 | 10 | 30s | 413 | 0.680 | 0.280 | 1.650 | POWERED | YES |
| deep_refill_bid_w | count | 1699 | 1699 | 0.99% | 303 | 2/50/845 | 0.50 | 10 | 120s | 193 | 2.003 | 0.825 | 3.750 | POWERED |  |
| deep_refill_bid_w | count | 1699 | 1699 | 0.99% | 303 | 2/50/845 | 0.50 | 10 | close | 10 | 74.710 | 30.778 | 30.100 | UNPOWERED |  |
| deep_refill_ask_w | count | 1714 | 1714 | 1.00% | 268 | 3/70/345 | 0.20 | 13 | 5s | 1714 | 0.145 | 0.060 | 0.450 | POWERED |  |
| deep_refill_ask_w | count | 1714 | 1714 | 1.00% | 268 | 3/70/345 | 0.20 | 13 | 30s | 399 | 0.692 | 0.285 | 1.650 | POWERED | YES |
| deep_refill_ask_w | count | 1714 | 1714 | 1.00% | 268 | 3/70/345 | 0.20 | 13 | 120s | 190 | 2.018 | 0.831 | 3.750 | POWERED |  |
| deep_refill_ask_w | count | 1714 | 1714 | 1.00% | 268 | 3/70/345 | 0.20 | 13 | close | 13 | 65.525 | 26.994 | 30.100 | UNPOWERED |  |

### BANKNIFTY_FUT: sessions=38, bars=171,000, mean mid=57,657.98
| horizon | σ (pts) | σ (bps) | median |move| (pts) | bars |
|---|---|---|---|---|
| 5s | 4.350 | 0.75 | 0.900 | 169,091 |
| 30s | 10.232 | 1.77 | 4.400 | 168,866 |
| 120s | 21.233 | 3.68 | 10.200 | 168,130 |
| close | 167.202 | 29.00 | 75.800 | 169,147 |

| feature | kind | n_raw | recount | rate | episodes | per-session min/med/max | top share | sessions | h | n_eff | MDE pts | MDE bps | median|move| | verdict | detects 0.5 bp @30 s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| deep_imb_qty | signed | 1703 | 1703 | 1.01% | 1068 | 2/36/291 | 0.17 | 37 | 5s | 1703 | 0.418 | 0.072 | 0.900 | POWERED |  |
| deep_imb_qty | signed | 1703 | 1703 | 1.01% | 1068 | 2/36/291 | 0.17 | 37 | 30s | 864 | 1.379 | 0.239 | 4.400 | POWERED | YES |
| deep_imb_qty | signed | 1703 | 1703 | 1.01% | 1068 | 2/36/291 | 0.17 | 37 | 120s | 518 | 3.696 | 0.641 | 10.200 | POWERED |  |
| deep_imb_qty | signed | 1703 | 1703 | 1.01% | 1068 | 2/36/291 | 0.17 | 37 | close | 37 | 108.908 | 18.889 | 75.800 | UNPOWERED |  |
| deep_imb_orders | signed | 1692 | 1692 | 1.00% | 1281 | 1/13/435 | 0.26 | 36 | 5s | 1692 | 0.419 | 0.073 | 0.900 | POWERED |  |
| deep_imb_orders | signed | 1692 | 1692 | 1.00% | 1281 | 1/13/435 | 0.26 | 36 | 30s | 974 | 1.299 | 0.225 | 4.400 | POWERED | YES |
| deep_imb_orders | signed | 1692 | 1692 | 1.00% | 1281 | 1/13/435 | 0.26 | 36 | 120s | 604 | 3.423 | 0.594 | 10.200 | POWERED |  |
| deep_imb_orders | signed | 1692 | 1692 | 1.00% | 1281 | 1/13/435 | 0.26 | 36 | close | 36 | 110.410 | 19.149 | 75.800 | UNPOWERED |  |
| slope_diff | signed | 1707 | 1707 | 1.01% | 1294 | 10/33/198 | 0.12 | 38 | 5s | 1707 | 0.417 | 0.072 | 0.900 | POWERED |  |
| slope_diff | signed | 1707 | 1707 | 1.01% | 1294 | 10/33/198 | 0.12 | 38 | 30s | 1026 | 1.266 | 0.220 | 4.400 | POWERED | YES |
| slope_diff | signed | 1707 | 1707 | 1.01% | 1294 | 10/33/198 | 0.12 | 38 | 120s | 695 | 3.191 | 0.553 | 10.200 | POWERED |  |
| slope_diff | signed | 1707 | 1707 | 1.01% | 1294 | 10/33/198 | 0.12 | 38 | close | 38 | 107.465 | 18.638 | 75.800 | UNPOWERED |  |
| conc_diff | signed | 1707 | 1707 | 1.01% | 976 | 2/32/189 | 0.11 | 38 | 5s | 1707 | 0.417 | 0.072 | 0.900 | POWERED |  |
| conc_diff | signed | 1707 | 1707 | 1.01% | 976 | 2/32/189 | 0.11 | 38 | 30s | 777 | 1.454 | 0.252 | 4.400 | POWERED | YES |
| conc_diff | signed | 1707 | 1707 | 1.01% | 976 | 2/32/189 | 0.11 | 38 | 120s | 470 | 3.880 | 0.673 | 10.200 | POWERED |  |
| conc_diff | signed | 1707 | 1707 | 1.01% | 976 | 2/32/189 | 0.11 | 38 | close | 38 | 107.465 | 18.638 | 75.800 | UNPOWERED |  |
| wall_appear_bid_w | count | 1687 | 1687 | 0.99% | 308 | 1/47/613 | 0.36 | 25 | 5s | 1687 | 0.420 | 0.073 | 0.900 | POWERED |  |
| wall_appear_bid_w | count | 1687 | 1687 | 0.99% | 308 | 1/47/613 | 0.36 | 25 | 30s | 424 | 1.969 | 0.341 | 4.400 | POWERED | YES |
| wall_appear_bid_w | count | 1687 | 1687 | 0.99% | 308 | 1/47/613 | 0.36 | 25 | 120s | 228 | 5.571 | 0.966 | 10.200 | POWERED |  |
| wall_appear_bid_w | count | 1687 | 1687 | 0.99% | 308 | 1/47/613 | 0.36 | 25 | close | 25 | 132.492 | 22.979 | 75.800 | UNPOWERED |  |
| wall_appear_ask_w | count | 1679 | 1679 | 0.98% | 294 | 1/18/495 | 0.29 | 27 | 5s | 1679 | 0.421 | 0.073 | 0.900 | POWERED |  |
| wall_appear_ask_w | count | 1679 | 1679 | 0.98% | 294 | 1/18/495 | 0.29 | 27 | 30s | 403 | 2.019 | 0.350 | 4.400 | POWERED | YES |
| wall_appear_ask_w | count | 1679 | 1679 | 0.98% | 294 | 1/18/495 | 0.29 | 27 | 120s | 205 | 5.876 | 1.019 | 10.200 | POWERED |  |
| wall_appear_ask_w | count | 1679 | 1679 | 0.98% | 294 | 1/18/495 | 0.29 | 27 | close | 27 | 127.491 | 22.112 | 75.800 | UNPOWERED |  |
| wall_disappear_bid_w | count | 1688 | 1688 | 0.99% | 311 | 1/41/574 | 0.34 | 25 | 5s | 1688 | 0.419 | 0.073 | 0.900 | POWERED |  |
| wall_disappear_bid_w | count | 1688 | 1688 | 0.99% | 311 | 1/41/574 | 0.34 | 25 | 30s | 421 | 1.976 | 0.343 | 4.400 | POWERED | YES |
| wall_disappear_bid_w | count | 1688 | 1688 | 0.99% | 311 | 1/41/574 | 0.34 | 25 | 120s | 230 | 5.547 | 0.962 | 10.200 | POWERED |  |
| wall_disappear_bid_w | count | 1688 | 1688 | 0.99% | 311 | 1/41/574 | 0.34 | 25 | close | 25 | 132.492 | 22.979 | 75.800 | UNPOWERED |  |
| wall_disappear_ask_w | count | 1684 | 1684 | 0.98% | 288 | 2/23/504 | 0.30 | 27 | 5s | 1684 | 0.420 | 0.073 | 0.900 | POWERED |  |
| wall_disappear_ask_w | count | 1684 | 1684 | 0.98% | 288 | 2/23/504 | 0.30 | 27 | 30s | 402 | 2.022 | 0.351 | 4.400 | POWERED | YES |
| wall_disappear_ask_w | count | 1684 | 1684 | 0.98% | 288 | 2/23/504 | 0.30 | 27 | 120s | 211 | 5.791 | 1.004 | 10.200 | POWERED |  |
| wall_disappear_ask_w | count | 1684 | 1684 | 0.98% | 288 | 2/23/504 | 0.30 | 27 | close | 27 | 127.491 | 22.112 | 75.800 | UNPOWERED |  |
| deep_refill_bid_w | count | 1691 | 1691 | 0.99% | 285 | 1/238/453 | 0.27 | 8 | 5s | 1691 | 0.419 | 0.073 | 0.900 | POWERED |  |
| deep_refill_bid_w | count | 1691 | 1691 | 0.99% | 285 | 1/238/453 | 0.27 | 8 | 30s | 395 | 2.040 | 0.354 | 4.400 | POWERED | YES |
| deep_refill_bid_w | count | 1691 | 1691 | 0.99% | 285 | 1/238/453 | 0.27 | 8 | 120s | 182 | 6.236 | 1.082 | 10.200 | POWERED |  |
| deep_refill_bid_w | count | 1691 | 1691 | 0.99% | 285 | 1/238/453 | 0.27 | 8 | close | 8 | 234.216 | 40.622 | 75.800 | UNPOWERED |  |
| deep_refill_ask_w | count | 1698 | 1698 | 0.99% | 282 | 2/92/614 | 0.36 | 14 | 5s | 1698 | 0.418 | 0.073 | 0.900 | POWERED |  |
| deep_refill_ask_w | count | 1698 | 1698 | 0.99% | 282 | 2/92/614 | 0.36 | 14 | 30s | 393 | 2.045 | 0.355 | 4.400 | POWERED | YES |
| deep_refill_ask_w | count | 1698 | 1698 | 0.99% | 282 | 2/92/614 | 0.36 | 14 | 120s | 185 | 6.185 | 1.073 | 10.200 | POWERED |  |
| deep_refill_ask_w | count | 1698 | 1698 | 0.99% | 282 | 2/92/614 | 0.36 | 14 | close | 14 | 177.050 | 30.707 | 75.800 | UNPOWERED |  |

## Self-check
Independent recount (pandas groupby transform vs the numpy per-slot loop): every feature's n_raw matches exactly (column "recount"), 20/20.

## Gate
Powered on BOTH instruments: 5 s: 10/10, 30 s: 10/10, 120 s: 10/10, close: 0/10 (n_eff = 8–38 sessions; MDE 38–234 pts vs median |move| 30 / 76). Every powered cell at 30 s can detect an effect of run 1's order (MDE 0.18–0.36 bp < 0.5 bp). **30 cells carried to scoring; CP2 GREEN.** Concentration to be flagged in CP4: NIFTY wall_appear_ask_w / wall_disappear_ask_w (one session = 50–52% of events), NIFTY deep_refill_bid_w (50%, events in 10 sessions), BANKNIFTY deep_refill_bid_w (events in 8 sessions), BANKNIFTY wall_appear_bid_w (36%).
