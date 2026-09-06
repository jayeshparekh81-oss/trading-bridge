# CP6 (run 2) — SCORE (one run, exactly as PREREG2; second run byte-identical)

`scripts/cp6_score2.py` on the stored features; `cp6_result2_run1.json` and `cp6_result2_run2.json` sha256 both `bc04783d20edfd95ad9519048105d2c03dd4d996cbcb3a1b54558cfb17f97180` → deterministic. Second-look bar: α = 0.05/46 = 0.001087 on both instruments, same sign, n_eff ≥ 100. Cost: model found, not applicable (PREREG2 §8) → every cell PRE-COST / PENDING; no cell GREEN.

## Result table (30 scored cells + the pre-registered but UNPOWERED close horizon)
| h | feature | inst | n_raw | n_eff | mean Y (event) pts | baseline pts | diff pts | diff bps | ±2 SE bps | sd event | sd non-event | p | sign | same sign | verdict | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5s | deep_imb_qty | NIFTY_FUT | 1706 | 1706 | +0.135 | +0.075 | +0.061 | +0.025 | 0.043 | 1.427 | 1.512 | 0.0950 | + | yes | FAIL | PRE-COST / PENDING |
| 5s | deep_imb_qty | BANKNIFTY_FUT | 1703 | 1703 | +0.393 | +0.228 | +0.164 | +0.029 | 0.052 | 4.305 | 4.332 | 0.1109 | + | yes | FAIL | PRE-COST / PENDING |
| 5s | deep_imb_orders | NIFTY_FUT | 1703 | 1703 | +0.082 | +0.065 | +0.017 | +0.007 | 0.043 | 1.479 | 1.511 | 0.6242 | + | yes | FAIL | PRE-COST / PENDING |
| 5s | deep_imb_orders | BANKNIFTY_FUT | 1692 | 1692 | +0.432 | +0.223 | +0.209 | +0.036 | 0.052 | 3.861 | 4.328 | 0.0455 | + | yes | FAIL | PRE-COST / PENDING |
| 5s | slope_diff | NIFTY_FUT | 1707 | 1707 | -0.125 | -0.011 | -0.114 | -0.047 | 0.043 | 1.303 | 1.515 | 0.0030 | − | yes | FAIL | PRE-COST / PENDING |
| 5s | slope_diff | BANKNIFTY_FUT | 1707 | 1707 | -0.203 | -0.061 | -0.141 | -0.024 | 0.052 | 3.829 | 4.354 | 0.1829 | − | yes | FAIL | PRE-COST / PENDING |
| 5s | conc_diff | NIFTY_FUT | 1705 | 1705 | -0.004 | -0.016 | +0.012 | +0.005 | 0.043 | 1.493 | 1.513 | 0.7551 | + | yes | FAIL | PRE-COST / PENDING |
| 5s | conc_diff | BANKNIFTY_FUT | 1707 | 1707 | +0.243 | -0.013 | +0.255 | +0.044 | 0.052 | 4.450 | 4.348 | 0.0180 | + | yes | FAIL | PRE-COST / PENDING |
| 5s | wall_appear_bid_w | NIFTY_FUT | 1684 | 1684 | -0.026 | +0.002 | -0.028 | -0.012 | 0.043 | 1.923 | 1.508 | 0.4533 | − | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 5s | wall_appear_bid_w | BANKNIFTY_FUT | 1687 | 1687 | +0.361 | +0.008 | +0.354 | +0.061 | 0.052 | 5.516 | 4.336 | 0.0005 | + | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 5s | wall_appear_ask_w | NIFTY_FUT | 1700 | 1700 | +0.034 | +0.002 | +0.032 | +0.013 | 0.043 | 2.049 | 1.507 | 0.3643 | + | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 5s | wall_appear_ask_w | BANKNIFTY_FUT | 1678 | 1678 | -0.070 | +0.006 | -0.076 | -0.013 | 0.052 | 5.696 | 4.334 | 0.4753 | − | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 5s | wall_disappear_bid_w | NIFTY_FUT | 1664 | 1664 | -0.081 | +0.003 | -0.084 | -0.035 | 0.043 | 1.829 | 1.510 | 0.0250 | − | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 5s | wall_disappear_bid_w | BANKNIFTY_FUT | 1688 | 1688 | +0.287 | +0.004 | +0.283 | +0.049 | 0.052 | 5.543 | 4.336 | 0.0110 | + | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 5s | wall_disappear_ask_w | NIFTY_FUT | 1701 | 1701 | +0.023 | +0.002 | +0.021 | +0.009 | 0.043 | 1.854 | 1.509 | 0.5747 | + | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 5s | wall_disappear_ask_w | BANKNIFTY_FUT | 1683 | 1683 | +0.001 | +0.008 | -0.007 | -0.001 | 0.052 | 5.837 | 4.332 | 0.9480 | − | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 5s | deep_refill_bid_w | NIFTY_FUT | 1699 | 1699 | +0.119 | +0.001 | +0.118 | +0.048 | 0.043 | 1.346 | 1.515 | 0.0015 | + | yes | FAIL | PRE-COST / PENDING |
| 5s | deep_refill_bid_w | BANKNIFTY_FUT | 1691 | 1691 | +0.290 | +0.003 | +0.287 | +0.050 | 0.052 | 3.578 | 4.357 | 0.0070 | + | yes | FAIL | PRE-COST / PENDING |
| 5s | deep_refill_ask_w | NIFTY_FUT | 1714 | 1714 | -0.107 | +0.003 | -0.110 | -0.045 | 0.043 | 1.552 | 1.513 | 0.0025 | − | yes | FAIL | PRE-COST / PENDING |
| 5s | deep_refill_ask_w | BANKNIFTY_FUT | 1697 | 1697 | -0.163 | +0.011 | -0.174 | -0.030 | 0.052 | 7.498 | 4.306 | 0.0970 | − | yes | FAIL | PRE-COST / PENDING |
| 30s | deep_imb_qty | NIFTY_FUT | 1704 | 745 | +0.435 | +0.246 | +0.189 | +0.078 | 0.149 | 3.749 | 3.478 | 0.1399 | + | yes | FAIL | PRE-COST / PENDING |
| 30s | deep_imb_qty | BANKNIFTY_FUT | 1701 | 862 | +2.412 | +0.754 | +1.658 | +0.287 | 0.171 | 10.559 | 10.177 | 0.0005 | + | yes | FAIL | PRE-COST / PENDING |
| 30s | deep_imb_orders | NIFTY_FUT | 1698 | 751 | +0.383 | +0.234 | +0.149 | +0.062 | 0.148 | 4.208 | 3.473 | 0.2324 | + | yes | FAIL | PRE-COST / PENDING |
| 30s | deep_imb_orders | BANKNIFTY_FUT | 1690 | 972 | +2.137 | +0.697 | +1.440 | +0.250 | 0.161 | 9.882 | 10.148 | 0.0005 | + | yes | FAIL | PRE-COST / PENDING |
| 30s | slope_diff | NIFTY_FUT | 1707 | 973 | +0.030 | +0.108 | -0.078 | -0.032 | 0.130 | 3.383 | 3.487 | 0.5097 | − | yes | FAIL | PRE-COST / PENDING |
| 30s | slope_diff | BANKNIFTY_FUT | 1707 | 1026 | -0.156 | -0.012 | -0.144 | -0.025 | 0.157 | 9.956 | 10.235 | 0.6487 | − | yes | FAIL | PRE-COST / PENDING |
| 30s | conc_diff | NIFTY_FUT | 1706 | 669 | +0.238 | +0.073 | +0.165 | +0.068 | 0.157 | 3.699 | 3.487 | 0.2169 | + | yes | FAIL | PRE-COST / PENDING |
| 30s | conc_diff | BANKNIFTY_FUT | 1702 | 775 | +0.600 | +0.177 | +0.423 | +0.073 | 0.180 | 11.597 | 10.228 | 0.2534 | + | yes | FAIL | PRE-COST / PENDING |
| 30s | wall_appear_bid_w | NIFTY_FUT | 1679 | 382 | -0.089 | +0.015 | -0.104 | -0.043 | 0.208 | 4.747 | 3.473 | 0.5707 | − | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | wall_appear_bid_w | BANKNIFTY_FUT | 1687 | 424 | +1.509 | +0.042 | +1.467 | +0.254 | 0.244 | 13.642 | 10.189 | 0.0015 | + | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | wall_appear_ask_w | NIFTY_FUT | 1695 | 375 | +0.053 | +0.007 | +0.046 | +0.019 | 0.210 | 5.418 | 3.466 | 0.8016 | + | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | wall_appear_ask_w | BANKNIFTY_FUT | 1678 | 403 | -0.402 | +0.055 | -0.457 | -0.079 | 0.250 | 13.867 | 10.188 | 0.3683 | − | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | wall_disappear_bid_w | NIFTY_FUT | 1659 | 376 | -0.361 | +0.011 | -0.372 | -0.153 | 0.210 | 4.358 | 3.476 | 0.0455 | − | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | wall_disappear_bid_w | BANKNIFTY_FUT | 1688 | 421 | +1.098 | +0.027 | +1.071 | +0.186 | 0.245 | 14.585 | 10.192 | 0.0305 | + | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | wall_disappear_ask_w | NIFTY_FUT | 1696 | 373 | -0.011 | +0.016 | -0.026 | -0.011 | 0.210 | 4.954 | 3.473 | 0.8816 | − | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | wall_disappear_ask_w | BANKNIFTY_FUT | 1684 | 402 | +0.065 | +0.047 | +0.018 | +0.003 | 0.250 | 14.515 | 10.191 | 0.9750 | + | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 30s | deep_refill_bid_w | NIFTY_FUT | 1697 | 412 | +0.350 | +0.003 | +0.347 | +0.143 | 0.200 | 3.541 | 3.488 | 0.0410 | + | yes | FAIL | PRE-COST / PENDING |
| 30s | deep_refill_bid_w | BANKNIFTY_FUT | 1691 | 395 | +1.020 | +0.033 | +0.987 | +0.171 | 0.253 | 7.850 | 10.247 | 0.0480 | + | yes | FAIL | PRE-COST / PENDING |
| 30s | deep_refill_ask_w | NIFTY_FUT | 1714 | 399 | -0.455 | +0.012 | -0.467 | -0.192 | 0.203 | 3.285 | 3.487 | 0.0070 | − | yes | FAIL | PRE-COST / PENDING |
| 30s | deep_refill_ask_w | BANKNIFTY_FUT | 1693 | 392 | -1.019 | +0.041 | -1.059 | -0.184 | 0.254 | 16.637 | 10.224 | 0.0405 | − | yes | FAIL | PRE-COST / PENDING |
| 120s | deep_imb_qty | NIFTY_FUT | 1689 | 417 | +0.578 | +0.470 | +0.108 | +0.045 | 0.401 | 7.586 | 7.010 | 0.7666 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | deep_imb_qty | BANKNIFTY_FUT | 1694 | 515 | +4.013 | +1.323 | +2.690 | +0.467 | 0.459 | 20.326 | 21.121 | 0.0045 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | deep_imb_orders | NIFTY_FUT | 1688 | 417 | +0.676 | +0.440 | +0.235 | +0.097 | 0.401 | 8.297 | 7.005 | 0.4738 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | deep_imb_orders | BANKNIFTY_FUT | 1686 | 601 | +3.619 | +1.123 | +2.496 | +0.433 | 0.425 | 20.388 | 21.084 | 0.0045 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | slope_diff | NIFTY_FUT | 1702 | 634 | +0.541 | +0.381 | +0.160 | +0.066 | 0.325 | 6.981 | 7.015 | 0.5802 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | slope_diff | BANKNIFTY_FUT | 1703 | 691 | +0.638 | +0.288 | +0.350 | +0.061 | 0.396 | 21.114 | 21.229 | 0.6687 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | conc_diff | NIFTY_FUT | 1703 | 421 | +0.484 | +0.295 | +0.189 | +0.078 | 0.399 | 6.582 | 7.025 | 0.6137 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | conc_diff | BANKNIFTY_FUT | 1698 | 466 | +1.681 | +0.585 | +1.096 | +0.190 | 0.483 | 24.607 | 21.197 | 0.2629 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | wall_appear_bid_w | NIFTY_FUT | 1673 | 184 | -0.181 | +0.029 | -0.210 | -0.086 | 0.603 | 7.730 | 7.013 | 0.6827 | − | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 120s | wall_appear_bid_w | BANKNIFTY_FUT | 1687 | 228 | +1.473 | +0.043 | +1.430 | +0.248 | 0.690 | 28.533 | 21.178 | 0.3128 | + | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 120s | wall_appear_ask_w | NIFTY_FUT | 1678 | 169 | +0.149 | +0.049 | +0.100 | +0.041 | 0.629 | 9.428 | 7.001 | 0.8676 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | wall_appear_ask_w | BANKNIFTY_FUT | 1677 | 205 | +1.877 | +0.280 | +1.597 | +0.277 | 0.727 | 30.377 | 21.134 | 0.2884 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | wall_disappear_bid_w | NIFTY_FUT | 1657 | 185 | -0.246 | +0.010 | -0.255 | -0.105 | 0.602 | 7.224 | 7.014 | 0.5942 | − | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 120s | wall_disappear_bid_w | BANKNIFTY_FUT | 1688 | 230 | +0.922 | +0.166 | +0.756 | +0.131 | 0.687 | 26.633 | 21.197 | 0.5802 | + | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 120s | wall_disappear_ask_w | NIFTY_FUT | 1679 | 172 | -0.098 | +0.024 | -0.122 | -0.050 | 0.624 | 9.485 | 7.002 | 0.8286 | − | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 120s | wall_disappear_ask_w | BANKNIFTY_FUT | 1684 | 211 | +3.304 | +0.171 | +3.133 | +0.543 | 0.717 | 27.523 | 21.165 | 0.0410 | + | NO | FAIL (sign flip) | PRE-COST / PENDING |
| 120s | deep_refill_bid_w | NIFTY_FUT | 1691 | 192 | +0.024 | -0.018 | +0.042 | +0.017 | 0.590 | 7.639 | 7.016 | 0.9360 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | deep_refill_bid_w | BANKNIFTY_FUT | 1690 | 181 | +1.460 | +0.088 | +1.372 | +0.238 | 0.774 | 18.051 | 21.257 | 0.3978 | + | yes | FAIL | PRE-COST / PENDING |
| 120s | deep_refill_ask_w | NIFTY_FUT | 1714 | 190 | -0.314 | +0.014 | -0.328 | -0.135 | 0.594 | 7.219 | 7.020 | 0.5472 | − | yes | FAIL | PRE-COST / PENDING |
| 120s | deep_refill_ask_w | BANKNIFTY_FUT | 1693 | 184 | -3.783 | -0.001 | -3.782 | -0.656 | 0.768 | 18.976 | 21.261 | 0.0155 | − | yes | FAIL | PRE-COST / PENDING |
| close | deep_imb_qty | NIFTY_FUT | 1706 | 1706 | +26.256 | +5.812 | +20.443 | +8.422 | 1.682 | 61.037 | 59.741 | 0.0005 | + | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | deep_imb_qty | BANKNIFTY_FUT | 1703 | 1703 | -50.660 | -2.002 | -48.658 | -8.439 | 1.988 | 128.099 | 167.700 | 0.0005 | − | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | deep_imb_orders | NIFTY_FUT | 1703 | 1703 | +15.981 | +6.628 | +9.353 | +3.853 | 1.684 | 57.113 | 59.676 | 0.0005 | + | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | deep_imb_orders | BANKNIFTY_FUT | 1692 | 1692 | -19.433 | -1.999 | -17.434 | -3.024 | 1.994 | 123.673 | 167.591 | 0.0005 | − | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | slope_diff | NIFTY_FUT | 1707 | 1707 | +28.130 | +4.409 | +23.722 | +9.773 | 1.682 | 67.752 | 59.785 | 0.0005 | + | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | slope_diff | BANKNIFTY_FUT | 1707 | 1707 | +10.926 | +2.606 | +8.321 | +1.443 | 1.985 | 143.309 | 168.093 | 0.0395 | + | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | conc_diff | NIFTY_FUT | 1707 | 1707 | +15.250 | +4.331 | +10.919 | +4.498 | 1.682 | 66.637 | 59.846 | 0.0005 | + | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | conc_diff | BANKNIFTY_FUT | 1707 | 1707 | -2.018 | +2.004 | -4.022 | -0.698 | 1.985 | 151.284 | 168.026 | 0.3178 | − | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | wall_appear_bid_w | NIFTY_FUT | 1685 | 1685 | -1.760 | +7.561 | -9.321 | -3.840 | 1.693 | 64.863 | 59.567 | 0.0005 | − | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | wall_appear_bid_w | BANKNIFTY_FUT | 1687 | 1687 | +13.718 | +15.029 | -1.311 | -0.227 | 1.997 | 139.826 | 167.456 | 0.7341 | − | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | wall_appear_ask_w | NIFTY_FUT | 1701 | 1701 | -5.397 | +7.630 | -13.027 | -5.367 | 1.685 | 56.016 | 59.651 | 0.0005 | − | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | wall_appear_ask_w | BANKNIFTY_FUT | 1679 | 1679 | +44.553 | +14.839 | +29.715 | +5.154 | 2.002 | 118.013 | 167.597 | 0.0005 | + | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | wall_disappear_bid_w | NIFTY_FUT | 1665 | 1665 | -1.546 | +7.499 | -9.044 | -3.726 | 1.703 | 64.978 | 59.567 | 0.0005 | − | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | wall_disappear_bid_w | BANKNIFTY_FUT | 1688 | 1688 | +16.630 | +14.964 | +1.667 | +0.289 | 1.996 | 144.763 | 167.414 | 0.6807 | + | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | wall_disappear_ask_w | NIFTY_FUT | 1702 | 1702 | -4.689 | +7.607 | -12.296 | -5.066 | 1.684 | 55.429 | 59.658 | 0.0005 | − | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | wall_disappear_ask_w | BANKNIFTY_FUT | 1684 | 1684 | +45.524 | +14.871 | +30.653 | +5.316 | 1.999 | 124.763 | 167.547 | 0.0005 | + | NO | UNPOWERED — not scored | PRE-COST / PENDING |
| close | deep_refill_bid_w | NIFTY_FUT | 1699 | 1699 | +96.688 | +6.555 | +90.134 | +37.132 | 1.686 | 80.003 | 58.696 | 0.0005 | + | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | deep_refill_bid_w | BANKNIFTY_FUT | 1691 | 1691 | +25.552 | +15.089 | +10.463 | +1.815 | 1.995 | 130.217 | 167.532 | 0.0120 | + | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | deep_refill_ask_w | NIFTY_FUT | 1714 | 1714 | +35.571 | +7.145 | +28.426 | +11.710 | 1.678 | 66.399 | 59.488 | 0.0005 | + | yes | UNPOWERED — not scored | PRE-COST / PENDING |
| close | deep_refill_ask_w | BANKNIFTY_FUT | 1698 | 1698 | +27.016 | +14.957 | +12.060 | +2.092 | 1.990 | 115.536 | 167.641 | 0.0035 | + | yes | UNPOWERED — not scored | PRE-COST / PENDING |

## Reading
- **0 of 30 scored cells pass the pre-registered second-look bar.** 11 cells are sign flips (every wall appear/disappear feature at 5 s and 30 s, three at 120 s): the noise signature.
- BANKNIFTY-only signal: deep_imb_qty / deep_imb_orders at 30 s (+0.29 / +0.25 bp, p = 0.0005) and 120 s (+0.47 / +0.43 bp, p = 0.0045) are not confirmed on NIFTY (+0.08 / +0.06 bp, p 0.14–0.77) → FAIL by the cross-instrument gate as pre-registered; reported, not promoted.
- Deep refill carries the SAME sign as run 1's shallow refill on both instruments at 5 s and 30 s (bid +, ask −) but is **weaker**: deep_refill_ask_w at 30 s −0.19 / −0.18 bp (p 0.007 / 0.041) vs run 1's ask_refills −0.53 / −0.51 bp (p 0.001 / 0.001); at 120 s the deep cells are not distinguishable from zero on NIFTY.
- Session close: sign flips on 6 of 10 features and ±3–37 bp differences on n_eff = 8–38 sessions; UNPOWERED, not scored.
- The concentration-flagged features (CP4) are the wall features and deep refill; the flips sit on the wall features.

## Head-to-head vs run 1 (PREREG2 §10; run-1 numbers read from ../depth_eval/cp6_result_run1.json, sha256 4649f422421b85d389a1c0fabe8614a5942f0fdacd9be961d425915e31b7d895)
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
No run-2 cell meets its bar, so no deep-book feature "beats run 1". Deep refill vs shallow refill: 30s ask: weaker, 30s bid: weaker, 120s ask: weaker, 120s bid: weaker.

## Self-check
End-to-end re-run byte-identical (hashes above). Gate: none — reported as found.
