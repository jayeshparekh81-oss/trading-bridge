# CP2 — POWER CHECK (event counts only; no event-conditional outcome computed)

Trigger (stated before counting): per instrument, per 15-minute time-of-day slot (25 slots from 09:15), pooled across the 25 usable sessions, T_slot = the 0.99 quantile of the feature's own values (ratio features: over bars where the ratio is defined); **event iff value > T_slot** (strict, so ties keep the rate ≤ 1%). Features: the six ELIGIBLE columns from CP0 on 5-second bars, rolling window 10 bars. Excluded session: ['2026-08-17'] (CP1).
Dependence: event bars cluster (episodes = runs of consecutive event bars); n_eff(h) thins events greedily so kept events are ≥ h apart within a session; for "close" every event in a session shares one closing mid, so n_eff(close) = sessions with ≥ 1 event.

MDE arithmetic (two-sided α = 0.05, power 0.80, difference of two means with equal group sizes n_eff, σ_h pooled = unconditional std of the h-second forward mid change over all bars):
MDE_h = (z_0.975 + z_0.80) · σ_h · √(2 / n_eff) = (2.80159) · σ_h · √(2 / n_eff). bps = MDE / mean mid × 10⁴.
Plausibility anchor (measured, not assumed): the unconditional **median |forward mid move|** at the same horizon. A mean effect larger than the typical absolute move is not a plausible mean effect, so MDE_h > median|move|_h ⇒ UNPOWERED for that (feature, horizon).
Unconditional quantities were computed over ALL bars with no feature joined; no event-conditional forward return was computed at this checkpoint.
Mid tick check: smallest positive |Δmid| between consecutive bars = NIFTY_FUT 0.049999999995634425 pts, BANKNIFTY_FUT 0.09999999999126885 pts (half of the 0.05 price tick, as expected for a mid). The 3.6e-12 printed by the script is float noise from averaging two prices; this recheck applies a 1e-6 floor.

### NIFTY_FUT: sessions=25, bars=112,500, mean mid=24,305.01
| horizon | unconditional σ (pts) | σ (bps) | median |move| (pts) | bars |
|---|---|---|---|---|
| 5s | 1.580 | 0.65 | 0.450 | 110,722 |
| 30s | 3.654 | 1.50 | 1.750 | 110,595 |
| 120s | 7.348 | 3.02 | 3.950 | 110,145 |
| close | 55.098 | 22.67 | 29.950 | 110,765 |

| feature | defined bars | events n_raw | recount | rate | episodes | per-session min/med/max | top-session share | sessions | h | n_eff | MDE pts | MDE bps | median|move| pts | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bid_refills | 112,500 | 820 | 820 | 0.73% | 708 | 1/20/136 | 0.17 | 24 | 5s | 820 | 0.219 | 0.09 | 0.450 | POWERED |
| bid_refills | 112,500 | 820 | 820 | 0.73% | 708 | 1/20/136 | 0.17 | 24 | 30s | 621 | 0.581 | 0.24 | 1.750 | POWERED |
| bid_refills | 112,500 | 820 | 820 | 0.73% | 708 | 1/20/136 | 0.17 | 24 | 120s | 445 | 1.380 | 0.57 | 3.950 | POWERED |
| bid_refills | 112,500 | 820 | 820 | 0.73% | 708 | 1/20/136 | 0.17 | 24 | close | 24 | 44.560 | 18.33 | 29.950 | UNPOWERED |
| ask_refills | 112,500 | 754 | 754 | 0.67% | 626 | 1/27/110 | 0.15 | 23 | 5s | 754 | 0.228 | 0.09 | 0.450 | POWERED |
| ask_refills | 112,500 | 754 | 754 | 0.67% | 626 | 1/27/110 | 0.15 | 23 | 30s | 539 | 0.624 | 0.26 | 1.750 | POWERED |
| ask_refills | 112,500 | 754 | 754 | 0.67% | 626 | 1/27/110 | 0.15 | 23 | 120s | 390 | 1.474 | 0.61 | 3.950 | POWERED |
| ask_refills | 112,500 | 754 | 754 | 0.67% | 626 | 1/27/110 | 0.15 | 23 | close | 23 | 45.519 | 18.73 | 29.950 | UNPOWERED |
| bid_refill_ratio | 28,332 | 264 | 264 | 0.93% | 261 | 2/11/31 | 0.12 | 25 | 5s | 264 | 0.385 | 0.16 | 0.450 | POWERED |
| bid_refill_ratio | 28,332 | 264 | 264 | 0.93% | 261 | 2/11/31 | 0.12 | 25 | 30s | 251 | 0.914 | 0.38 | 1.750 | POWERED |
| bid_refill_ratio | 28,332 | 264 | 264 | 0.93% | 261 | 2/11/31 | 0.12 | 25 | 120s | 229 | 1.924 | 0.79 | 3.950 | POWERED |
| bid_refill_ratio | 28,332 | 264 | 264 | 0.93% | 261 | 2/11/31 | 0.12 | 25 | close | 25 | 43.660 | 17.96 | 29.950 | UNPOWERED |
| ask_refill_ratio | 18,586 | 181 | 181 | 0.97% | 177 | 1/6/17 | 0.09 | 24 | 5s | 181 | 0.465 | 0.19 | 0.450 | UNPOWERED |
| ask_refill_ratio | 18,586 | 181 | 181 | 0.97% | 177 | 1/6/17 | 0.09 | 24 | 30s | 173 | 1.101 | 0.45 | 1.750 | POWERED |
| ask_refill_ratio | 18,586 | 181 | 181 | 0.97% | 177 | 1/6/17 | 0.09 | 24 | 120s | 157 | 2.323 | 0.96 | 3.950 | POWERED |
| ask_refill_ratio | 18,586 | 181 | 181 | 0.97% | 177 | 1/6/17 | 0.09 | 24 | close | 24 | 44.560 | 18.33 | 29.950 | UNPOWERED |
| bid_refills_w | 112,500 | 1017 | 1017 | 0.90% | 227 | 8/48/248 | 0.24 | 15 | 5s | 1017 | 0.196 | 0.08 | 0.450 | POWERED |
| bid_refills_w | 112,500 | 1017 | 1017 | 0.90% | 227 | 8/48/248 | 0.24 | 15 | 30s | 276 | 0.871 | 0.36 | 1.750 | POWERED |
| bid_refills_w | 112,500 | 1017 | 1017 | 0.90% | 227 | 8/48/248 | 0.24 | 15 | 120s | 171 | 2.226 | 0.92 | 3.950 | POWERED |
| bid_refills_w | 112,500 | 1017 | 1017 | 0.90% | 227 | 8/48/248 | 0.24 | 15 | close | 15 | 56.365 | 23.19 | 29.950 | UNPOWERED |
| ask_refills_w | 112,500 | 978 | 978 | 0.87% | 193 | 1/36/182 | 0.19 | 17 | 5s | 978 | 0.200 | 0.08 | 0.450 | POWERED |
| ask_refills_w | 112,500 | 978 | 978 | 0.87% | 193 | 1/36/182 | 0.19 | 17 | 30s | 256 | 0.905 | 0.37 | 1.750 | POWERED |
| ask_refills_w | 112,500 | 978 | 978 | 0.87% | 193 | 1/36/182 | 0.19 | 17 | 120s | 144 | 2.426 | 1.00 | 3.950 | POWERED |
| ask_refills_w | 112,500 | 978 | 978 | 0.87% | 193 | 1/36/182 | 0.19 | 17 | close | 17 | 52.946 | 21.78 | 29.950 | UNPOWERED |

### BANKNIFTY_FUT: sessions=25, bars=112,500, mean mid=57,616.27
| horizon | unconditional σ (pts) | σ (bps) | median |move| (pts) | bars |
|---|---|---|---|---|
| 5s | 4.507 | 0.78 | 1.000 | 110,748 |
| 30s | 10.812 | 1.88 | 4.700 | 110,621 |
| 120s | 22.528 | 3.91 | 10.800 | 110,171 |
| close | 180.380 | 31.31 | 76.200 | 110,778 |

| feature | defined bars | events n_raw | recount | rate | episodes | per-session min/med/max | top-session share | sessions | h | n_eff | MDE pts | MDE bps | median|move| pts | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bid_refills | 112,500 | 575 | 575 | 0.51% | 492 | 2/13/180 | 0.31 | 24 | 5s | 575 | 0.745 | 0.13 | 1.000 | POWERED |
| bid_refills | 112,500 | 575 | 575 | 0.51% | 492 | 2/13/180 | 0.31 | 24 | 30s | 418 | 2.095 | 0.36 | 4.700 | POWERED |
| bid_refills | 112,500 | 575 | 575 | 0.51% | 492 | 2/13/180 | 0.31 | 24 | 120s | 319 | 4.998 | 0.87 | 10.800 | POWERED |
| bid_refills | 112,500 | 575 | 575 | 0.51% | 492 | 2/13/180 | 0.31 | 24 | close | 24 | 145.882 | 25.32 | 76.200 | UNPOWERED |
| ask_refills | 112,500 | 363 | 363 | 0.32% | 351 | 4/12/60 | 0.17 | 25 | 5s | 363 | 0.937 | 0.16 | 1.000 | POWERED |
| ask_refills | 112,500 | 363 | 363 | 0.32% | 351 | 4/12/60 | 0.17 | 25 | 30s | 331 | 2.355 | 0.41 | 4.700 | POWERED |
| ask_refills | 112,500 | 363 | 363 | 0.32% | 351 | 4/12/60 | 0.17 | 25 | 120s | 261 | 5.525 | 0.96 | 10.800 | POWERED |
| ask_refills | 112,500 | 363 | 363 | 0.32% | 351 | 4/12/60 | 0.17 | 25 | close | 25 | 142.935 | 24.81 | 76.200 | UNPOWERED |
| bid_refill_ratio | 10,483 | 107 | 107 | 1.02% | 107 | 1/4/15 | 0.14 | 23 | 5s | 107 | 1.726 | 0.30 | 1.000 | UNPOWERED |
| bid_refill_ratio | 10,483 | 107 | 107 | 1.02% | 107 | 1/4/15 | 0.14 | 23 | 30s | 106 | 4.161 | 0.72 | 4.700 | POWERED |
| bid_refill_ratio | 10,483 | 107 | 107 | 1.02% | 107 | 1/4/15 | 0.14 | 23 | 120s | 100 | 8.926 | 1.55 | 10.800 | POWERED |
| bid_refill_ratio | 10,483 | 107 | 107 | 1.02% | 107 | 1/4/15 | 0.14 | 23 | close | 23 | 149.020 | 25.86 | 76.200 | UNPOWERED |
| ask_refill_ratio | 9,766 | 98 | 98 | 1.00% | 98 | 1/3/17 | 0.17 | 23 | 5s | 98 | 1.804 | 0.31 | 1.000 | UNPOWERED |
| ask_refill_ratio | 9,766 | 98 | 98 | 1.00% | 98 | 1/3/17 | 0.17 | 23 | 30s | 94 | 4.418 | 0.77 | 4.700 | POWERED |
| ask_refill_ratio | 9,766 | 98 | 98 | 1.00% | 98 | 1/3/17 | 0.17 | 23 | 120s | 85 | 9.681 | 1.68 | 10.800 | POWERED |
| ask_refill_ratio | 9,766 | 98 | 98 | 1.00% | 98 | 1/3/17 | 0.17 | 23 | close | 23 | 149.020 | 25.86 | 76.200 | UNPOWERED |
| bid_refills_w | 112,500 | 911 | 911 | 0.81% | 176 | 5/23/334 | 0.37 | 19 | 5s | 911 | 0.592 | 0.10 | 1.000 | POWERED |
| bid_refills_w | 112,500 | 911 | 911 | 0.81% | 176 | 5/23/334 | 0.37 | 19 | 30s | 224 | 2.862 | 0.50 | 4.700 | POWERED |
| bid_refills_w | 112,500 | 911 | 911 | 0.81% | 176 | 5/23/334 | 0.37 | 19 | 120s | 129 | 7.859 | 1.36 | 10.800 | POWERED |
| bid_refills_w | 112,500 | 911 | 911 | 0.81% | 176 | 5/23/334 | 0.37 | 19 | close | 19 | 163.957 | 28.46 | 76.200 | UNPOWERED |
| ask_refills_w | 112,500 | 866 | 866 | 0.77% | 208 | 1/19/214 | 0.25 | 24 | 5s | 866 | 0.607 | 0.11 | 1.000 | POWERED |
| ask_refills_w | 112,500 | 866 | 866 | 0.77% | 208 | 1/19/214 | 0.25 | 24 | 30s | 238 | 2.777 | 0.48 | 4.700 | POWERED |
| ask_refills_w | 112,500 | 866 | 866 | 0.77% | 208 | 1/19/214 | 0.25 | 24 | 120s | 145 | 7.412 | 1.29 | 10.800 | POWERED |
| ask_refills_w | 112,500 | 866 | 866 | 0.77% | 208 | 1/19/214 | 0.25 | 24 | close | 24 | 145.882 | 25.32 | 76.200 | UNPOWERED |

## Self-check
Independent recount (pandas groupby-quantile + map, vs the numpy per-slot loop): every feature's n_raw matches exactly (column "recount").

## Gate
Powered on BOTH instruments (the cross-instrument gate needs both): **5 s**: bid_refills, ask_refills, bid_refills_w, ask_refills_w (bid_refill_ratio powered on NIFTY only; ask_refill_ratio and both BANKNIFTY ratios UNPOWERED at 5 s); **30 s and 120 s**: all six; **session close**: NOTHING (n_eff = 15–25 sessions; MDE 44–56 pts NIFTY, 143–164 pts BANKNIFTY vs median |move| 29.95 / 76.2). 16 (feature, horizon) cells carried to scoring. **CP2 GREEN** with the powered subset; the close horizon is pre-registered but not scoreable on this sample.
