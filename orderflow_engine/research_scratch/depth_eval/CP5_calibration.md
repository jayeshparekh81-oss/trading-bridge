# CP5 — INSTRUMENT CALIBRATION (the dummy exam)

Scorer: `scripts/scorer.py`, exactly PREREG §5–§7 (thinned events, B=1000 slot-matched non-event samples, two-sided empirical p, pass bar p ≤ 0.003125 on both instruments + same sign + n_eff ≥ 100). Each exam run with seeds 1 and 2.

## RANDX — pure random events at each feature's own per-slot event rate
32 cells (16 × 2 seeds), 64 instrument-tests: **cells passing the pass bar: 0**; p < 0.05 on 1/64 (expected ≈ 3.2 under a uniform null); min p 0.050; median p 0.536. → the null is read as null.

## INJ+ / INJ− as sealed in PREREG §9 (δ = ±3·MDE added to the REAL events' forward return)
INJ+: within 2 SE 36/64, correct sign 64/64, cells passing the pass bar 28/32. INJ−: within 2 SE 36/64, correct sign 64/64, cells passing the pass bar 28/32.
Reading: recovered = δ + (the real event effect). The residual (recovered − injected) is **identical between INJ+ and INJ− on 64/64** instrument-tests, i.e. it is the real event-vs-baseline difference that CP6 measures, not instrument error; the 36/64 "within 2 SE" count simply marks the cells whose real effect is below 2 SE. The sealed criterion cannot separate instrument error from a real effect, which is why the next exam was added.

## INJ+R / INJ−R — clean recovery (added in this checkpoint's self-check): δ injected onto RANDOM events, so the truth is exactly δ
INJ+R: within 2 SE 64/64, correct sign 64/64, cells passing the pass bar 28/32. INJ−R: within 2 SE 64/64, correct sign 64/64, cells passing the pass bar 28/32. → **the instrument recovers a known truth within 2 SE with the correct sign on every one of the 128 instrument-tests.**

## Self-check
- `self-check found`: seeds 1 and 2 produced identical numbers — per-draw streams were seeded `seed + b`, so the two seeds shared 999 of 1000 streams; `fixed by` seeding each draw with the seed sequence `[seed, b]`. Also found: the RANDX event picker used Python's per-process `hash()` (not reproducible across runs); `fixed by` a CRC32 of the feature/horizon string. Both exams re-run after the fix; seeds now differ in the third decimal as expected.
- `self-check found`: the sealed INJ design confounds recovery with the real effect (above); `fixed by` adding INJ±R on random events (PREREG §5–§7 unchanged; the scoring rule was not touched).

## Gate
RANDX does not pass; injected effects are recovered close to their injected values with the correct sign (INJ±R 64/64 within 2 SE; INJ± sign 64/64 with the residual proven to be the real effect). **CP5 GREEN.**

## Full tables
### INJ+R
| seed | horizon | feature | inst | n_eff | injected (pts) | recovered (pts) | SE (pts) | recovered − injected | within 2 SE | sign ok | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 5s | bid_refills | NIFTY_FUT | 809 | +0.656 | +0.574 | 0.079 | -0.082 | yes | yes | 0.001 |
| 1 | 5s | bid_refills | BANKNIFTY_FUT | 563 | +2.234 | +2.348 | 0.269 | +0.114 | yes | yes | 0.001 |
| 1 | 5s | ask_refills | NIFTY_FUT | 734 | +0.684 | +0.711 | 0.082 | +0.027 | yes | yes | 0.001 |
| 1 | 5s | ask_refills | BANKNIFTY_FUT | 354 | +2.812 | +2.599 | 0.339 | -0.212 | yes | yes | 0.001 |
| 1 | 5s | bid_refills_w | NIFTY_FUT | 1010 | +0.589 | +0.580 | 0.070 | -0.009 | yes | yes | 0.001 |
| 1 | 5s | bid_refills_w | BANKNIFTY_FUT | 899 | +1.775 | +1.883 | 0.213 | +0.108 | yes | yes | 0.001 |
| 1 | 5s | ask_refills_w | NIFTY_FUT | 963 | +0.601 | +0.566 | 0.072 | -0.035 | yes | yes | 0.001 |
| 1 | 5s | ask_refills_w | BANKNIFTY_FUT | 853 | +1.820 | +1.964 | 0.218 | +0.144 | yes | yes | 0.001 |
| 1 | 30s | bid_refills | NIFTY_FUT | 773 | +1.743 | +1.555 | 0.186 | -0.187 | yes | yes | 0.001 |
| 1 | 30s | bid_refills | BANKNIFTY_FUT | 546 | +6.286 | +6.119 | 0.654 | -0.166 | yes | yes | 0.001 |
| 1 | 30s | ask_refills | NIFTY_FUT | 701 | +1.871 | +1.614 | 0.195 | -0.257 | yes | yes | 0.001 |
| 1 | 30s | ask_refills | BANKNIFTY_FUT | 350 | +7.064 | +6.854 | 0.817 | -0.209 | yes | yes | 0.001 |
| 1 | 30s | bid_refill_ratio | NIFTY_FUT | 258 | +2.741 | +2.816 | 0.322 | +0.075 | yes | yes | 0.001 |
| 1 | 30s | bid_refill_ratio | BANKNIFTY_FUT | 102 | +12.483 | +11.790 | 1.514 | -0.693 | yes | yes | 0.001 |
| 1 | 30s | ask_refill_ratio | NIFTY_FUT | 174 | +3.302 | +3.202 | 0.392 | -0.100 | yes | yes | 0.001 |
| 1 | 30s | ask_refill_ratio | BANKNIFTY_FUT | 96 | +13.255 | +13.553 | 1.561 | +0.298 | yes | yes | 0.001 |
| 1 | 30s | bid_refills_w | NIFTY_FUT | 947 | +2.614 | +2.618 | 0.168 | +0.004 | yes | yes | 0.001 |
| 1 | 30s | bid_refills_w | BANKNIFTY_FUT | 867 | +8.587 | +8.247 | 0.519 | -0.340 | yes | yes | 0.001 |
| 1 | 30s | ask_refills_w | NIFTY_FUT | 925 | +2.714 | +2.641 | 0.170 | -0.073 | yes | yes | 0.001 |
| 1 | 30s | ask_refills_w | BANKNIFTY_FUT | 815 | +8.330 | +8.574 | 0.536 | +0.243 | yes | yes | 0.001 |
| 1 | 120s | bid_refills | NIFTY_FUT | 691 | +4.140 | +4.082 | 0.395 | -0.058 | yes | yes | 0.001 |
| 1 | 120s | bid_refills | BANKNIFTY_FUT | 488 | +14.993 | +14.880 | 1.442 | -0.112 | yes | yes | 0.001 |
| 1 | 120s | ask_refills | NIFTY_FUT | 635 | +4.423 | +4.382 | 0.412 | -0.041 | yes | yes | 0.001 |
| 1 | 120s | ask_refills | BANKNIFTY_FUT | 329 | +16.575 | +15.315 | 1.756 | -1.260 | yes | yes | 0.001 |
| 1 | 120s | bid_refill_ratio | NIFTY_FUT | 247 | +5.771 | +5.396 | 0.661 | -0.375 | yes | yes | 0.001 |
| 1 | 120s | bid_refill_ratio | BANKNIFTY_FUT | 103 | +26.777 | +25.930 | 3.139 | -0.848 | yes | yes | 0.001 |
| 1 | 120s | ask_refill_ratio | NIFTY_FUT | 171 | +6.970 | +7.437 | 0.795 | +0.466 | yes | yes | 0.001 |
| 1 | 120s | ask_refill_ratio | BANKNIFTY_FUT | 96 | +29.044 | +28.699 | 3.252 | -0.345 | yes | yes | 0.001 |
| 1 | 120s | bid_refills_w | NIFTY_FUT | 815 | +6.679 | +6.251 | 0.364 | -0.428 | yes | yes | 0.001 |
| 1 | 120s | bid_refills_w | BANKNIFTY_FUT | 757 | +23.576 | +22.714 | 1.158 | -0.863 | yes | yes | 0.001 |
| 1 | 120s | ask_refills_w | NIFTY_FUT | 793 | +7.278 | +7.169 | 0.369 | -0.109 | yes | yes | 0.001 |
| 1 | 120s | ask_refills_w | BANKNIFTY_FUT | 703 | +22.237 | +22.580 | 1.202 | +0.342 | yes | yes | 0.001 |
| 2 | 5s | bid_refills | NIFTY_FUT | 809 | +0.656 | +0.671 | 0.079 | +0.015 | yes | yes | 0.001 |
| 2 | 5s | bid_refills | BANKNIFTY_FUT | 572 | +2.234 | +2.038 | 0.266 | -0.195 | yes | yes | 0.001 |
| 2 | 5s | ask_refills | NIFTY_FUT | 733 | +0.684 | +0.682 | 0.083 | -0.002 | yes | yes | 0.001 |
| 2 | 5s | ask_refills | BANKNIFTY_FUT | 351 | +2.812 | +2.743 | 0.340 | -0.068 | yes | yes | 0.001 |
| 2 | 5s | bid_refills_w | NIFTY_FUT | 1000 | +0.589 | +0.634 | 0.071 | +0.045 | yes | yes | 0.001 |
| 2 | 5s | bid_refills_w | BANKNIFTY_FUT | 900 | +1.775 | +1.730 | 0.212 | -0.045 | yes | yes | 0.001 |
| 2 | 5s | ask_refills_w | NIFTY_FUT | 961 | +0.601 | +0.651 | 0.072 | +0.050 | yes | yes | 0.001 |
| 2 | 5s | ask_refills_w | BANKNIFTY_FUT | 850 | +1.820 | +1.866 | 0.219 | +0.046 | yes | yes | 0.001 |
| 2 | 30s | bid_refills | NIFTY_FUT | 760 | +1.743 | +1.625 | 0.187 | -0.118 | yes | yes | 0.001 |
| 2 | 30s | bid_refills | BANKNIFTY_FUT | 541 | +6.286 | +6.359 | 0.657 | +0.073 | yes | yes | 0.001 |
| 2 | 30s | ask_refills | NIFTY_FUT | 724 | +1.871 | +1.720 | 0.192 | -0.151 | yes | yes | 0.001 |
| 2 | 30s | ask_refills | BANKNIFTY_FUT | 349 | +7.064 | +7.886 | 0.819 | +0.823 | yes | yes | 0.001 |
| 2 | 30s | bid_refill_ratio | NIFTY_FUT | 254 | +2.741 | +2.652 | 0.324 | -0.089 | yes | yes | 0.001 |
| 2 | 30s | bid_refill_ratio | BANKNIFTY_FUT | 104 | +12.483 | +13.542 | 1.499 | +1.059 | yes | yes | 0.001 |
| 2 | 30s | ask_refill_ratio | NIFTY_FUT | 178 | +3.302 | +3.079 | 0.387 | -0.223 | yes | yes | 0.001 |
| 2 | 30s | ask_refill_ratio | BANKNIFTY_FUT | 97 | +13.255 | +14.628 | 1.553 | +1.372 | yes | yes | 0.001 |
| 2 | 30s | bid_refills_w | NIFTY_FUT | 961 | +2.614 | +2.404 | 0.167 | -0.210 | yes | yes | 0.001 |
| 2 | 30s | bid_refills_w | BANKNIFTY_FUT | 865 | +8.587 | +8.656 | 0.520 | +0.069 | yes | yes | 0.001 |
| 2 | 30s | ask_refills_w | NIFTY_FUT | 912 | +2.714 | +2.605 | 0.171 | -0.110 | yes | yes | 0.001 |
| 2 | 30s | ask_refills_w | BANKNIFTY_FUT | 807 | +8.330 | +8.797 | 0.538 | +0.467 | yes | yes | 0.001 |
| 2 | 120s | bid_refills | NIFTY_FUT | 681 | +4.140 | +4.295 | 0.398 | +0.155 | yes | yes | 0.001 |
| 2 | 120s | bid_refills | BANKNIFTY_FUT | 480 | +14.993 | +13.560 | 1.454 | -1.432 | yes | yes | 0.001 |
| 2 | 120s | ask_refills | NIFTY_FUT | 628 | +4.423 | +4.575 | 0.415 | +0.152 | yes | yes | 0.001 |
| 2 | 120s | ask_refills | BANKNIFTY_FUT | 315 | +16.575 | +16.331 | 1.795 | -0.244 | yes | yes | 0.001 |
| 2 | 120s | bid_refill_ratio | NIFTY_FUT | 244 | +5.771 | +5.702 | 0.665 | -0.070 | yes | yes | 0.001 |
| 2 | 120s | bid_refill_ratio | BANKNIFTY_FUT | 103 | +26.777 | +22.865 | 3.139 | -3.913 | yes | yes | 0.001 |
| 2 | 120s | ask_refill_ratio | NIFTY_FUT | 171 | +6.970 | +7.082 | 0.795 | +0.112 | yes | yes | 0.001 |
| 2 | 120s | ask_refill_ratio | BANKNIFTY_FUT | 91 | +29.044 | +26.474 | 3.340 | -2.570 | yes | yes | 0.001 |
| 2 | 120s | bid_refills_w | NIFTY_FUT | 814 | +6.679 | +7.004 | 0.364 | +0.325 | yes | yes | 0.001 |
| 2 | 120s | bid_refills_w | BANKNIFTY_FUT | 750 | +23.576 | +23.538 | 1.163 | -0.039 | yes | yes | 0.001 |
| 2 | 120s | ask_refills_w | NIFTY_FUT | 803 | +7.278 | +7.341 | 0.367 | +0.063 | yes | yes | 0.001 |
| 2 | 120s | ask_refills_w | BANKNIFTY_FUT | 714 | +22.237 | +21.407 | 1.192 | -0.830 | yes | yes | 0.001 |
### INJ−R
| seed | horizon | feature | inst | n_eff | injected (pts) | recovered (pts) | SE (pts) | recovered − injected | within 2 SE | sign ok | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 5s | bid_refills | NIFTY_FUT | 809 | -0.656 | -0.737 | 0.079 | -0.082 | yes | yes | 0.001 |
| 1 | 5s | bid_refills | BANKNIFTY_FUT | 563 | -2.234 | -2.120 | 0.269 | +0.114 | yes | yes | 0.001 |
| 1 | 5s | ask_refills | NIFTY_FUT | 734 | -0.684 | -0.657 | 0.082 | +0.027 | yes | yes | 0.001 |
| 1 | 5s | ask_refills | BANKNIFTY_FUT | 354 | -2.812 | -3.024 | 0.339 | -0.212 | yes | yes | 0.001 |
| 1 | 5s | bid_refills_w | NIFTY_FUT | 1010 | -0.589 | -0.598 | 0.070 | -0.009 | yes | yes | 0.001 |
| 1 | 5s | bid_refills_w | BANKNIFTY_FUT | 899 | -1.775 | -1.666 | 0.213 | +0.108 | yes | yes | 0.001 |
| 1 | 5s | ask_refills_w | NIFTY_FUT | 963 | -0.601 | -0.635 | 0.072 | -0.035 | yes | yes | 0.001 |
| 1 | 5s | ask_refills_w | BANKNIFTY_FUT | 853 | -1.820 | -1.677 | 0.218 | +0.144 | yes | yes | 0.001 |
| 1 | 30s | bid_refills | NIFTY_FUT | 773 | -1.743 | -1.930 | 0.186 | -0.187 | yes | yes | 0.001 |
| 1 | 30s | bid_refills | BANKNIFTY_FUT | 546 | -6.286 | -6.452 | 0.654 | -0.166 | yes | yes | 0.001 |
| 1 | 30s | ask_refills | NIFTY_FUT | 701 | -1.871 | -2.127 | 0.195 | -0.257 | yes | yes | 0.001 |
| 1 | 30s | ask_refills | BANKNIFTY_FUT | 350 | -7.064 | -7.273 | 0.817 | -0.209 | yes | yes | 0.001 |
| 1 | 30s | bid_refill_ratio | NIFTY_FUT | 258 | -2.741 | -2.666 | 0.322 | +0.075 | yes | yes | 0.001 |
| 1 | 30s | bid_refill_ratio | BANKNIFTY_FUT | 102 | -12.483 | -13.175 | 1.514 | -0.693 | yes | yes | 0.001 |
| 1 | 30s | ask_refill_ratio | NIFTY_FUT | 174 | -3.302 | -3.402 | 0.392 | -0.100 | yes | yes | 0.001 |
| 1 | 30s | ask_refill_ratio | BANKNIFTY_FUT | 96 | -13.255 | -12.958 | 1.561 | +0.298 | yes | yes | 0.001 |
| 1 | 30s | bid_refills_w | NIFTY_FUT | 947 | -2.614 | -2.610 | 0.168 | +0.004 | yes | yes | 0.001 |
| 1 | 30s | bid_refills_w | BANKNIFTY_FUT | 867 | -8.587 | -8.927 | 0.519 | -0.340 | yes | yes | 0.001 |
| 1 | 30s | ask_refills_w | NIFTY_FUT | 925 | -2.714 | -2.788 | 0.170 | -0.073 | yes | yes | 0.001 |
| 1 | 30s | ask_refills_w | BANKNIFTY_FUT | 815 | -8.330 | -8.087 | 0.536 | +0.243 | yes | yes | 0.001 |
| 1 | 120s | bid_refills | NIFTY_FUT | 691 | -4.140 | -4.198 | 0.395 | -0.058 | yes | yes | 0.001 |
| 1 | 120s | bid_refills | BANKNIFTY_FUT | 488 | -14.993 | -15.105 | 1.442 | -0.112 | yes | yes | 0.001 |
| 1 | 120s | ask_refills | NIFTY_FUT | 635 | -4.423 | -4.463 | 0.412 | -0.041 | yes | yes | 0.001 |
| 1 | 120s | ask_refills | BANKNIFTY_FUT | 329 | -16.575 | -17.835 | 1.756 | -1.260 | yes | yes | 0.001 |
| 1 | 120s | bid_refill_ratio | NIFTY_FUT | 247 | -5.771 | -6.146 | 0.661 | -0.375 | yes | yes | 0.001 |
| 1 | 120s | bid_refill_ratio | BANKNIFTY_FUT | 103 | -26.777 | -27.625 | 3.139 | -0.848 | yes | yes | 0.001 |
| 1 | 120s | ask_refill_ratio | NIFTY_FUT | 171 | -6.970 | -6.504 | 0.795 | +0.466 | yes | yes | 0.001 |
| 1 | 120s | ask_refill_ratio | BANKNIFTY_FUT | 96 | -29.044 | -29.389 | 3.252 | -0.345 | yes | yes | 0.001 |
| 1 | 120s | bid_refills_w | NIFTY_FUT | 815 | -6.679 | -7.107 | 0.364 | -0.428 | yes | yes | 0.001 |
| 1 | 120s | bid_refills_w | BANKNIFTY_FUT | 757 | -23.576 | -24.439 | 1.158 | -0.863 | yes | yes | 0.001 |
| 1 | 120s | ask_refills_w | NIFTY_FUT | 793 | -7.278 | -7.387 | 0.369 | -0.109 | yes | yes | 0.001 |
| 1 | 120s | ask_refills_w | BANKNIFTY_FUT | 703 | -22.237 | -21.895 | 1.202 | +0.342 | yes | yes | 0.001 |
| 2 | 5s | bid_refills | NIFTY_FUT | 809 | -0.656 | -0.641 | 0.079 | +0.015 | yes | yes | 0.001 |
| 2 | 5s | bid_refills | BANKNIFTY_FUT | 572 | -2.234 | -2.429 | 0.266 | -0.195 | yes | yes | 0.001 |
| 2 | 5s | ask_refills | NIFTY_FUT | 733 | -0.684 | -0.686 | 0.083 | -0.002 | yes | yes | 0.001 |
| 2 | 5s | ask_refills | BANKNIFTY_FUT | 351 | -2.812 | -2.880 | 0.340 | -0.068 | yes | yes | 0.001 |
| 2 | 5s | bid_refills_w | NIFTY_FUT | 1000 | -0.589 | -0.544 | 0.071 | +0.045 | yes | yes | 0.001 |
| 2 | 5s | bid_refills_w | BANKNIFTY_FUT | 900 | -1.775 | -1.820 | 0.212 | -0.045 | yes | yes | 0.001 |
| 2 | 5s | ask_refills_w | NIFTY_FUT | 961 | -0.601 | -0.551 | 0.072 | +0.050 | yes | yes | 0.001 |
| 2 | 5s | ask_refills_w | BANKNIFTY_FUT | 850 | -1.820 | -1.774 | 0.219 | +0.046 | yes | yes | 0.001 |
| 2 | 30s | bid_refills | NIFTY_FUT | 760 | -1.743 | -1.861 | 0.187 | -0.118 | yes | yes | 0.001 |
| 2 | 30s | bid_refills | BANKNIFTY_FUT | 541 | -6.286 | -6.213 | 0.657 | +0.073 | yes | yes | 0.001 |
| 2 | 30s | ask_refills | NIFTY_FUT | 724 | -1.871 | -2.021 | 0.192 | -0.151 | yes | yes | 0.001 |
| 2 | 30s | ask_refills | BANKNIFTY_FUT | 349 | -7.064 | -6.241 | 0.819 | +0.823 | yes | yes | 0.001 |
| 2 | 30s | bid_refill_ratio | NIFTY_FUT | 254 | -2.741 | -2.831 | 0.324 | -0.089 | yes | yes | 0.001 |
| 2 | 30s | bid_refill_ratio | BANKNIFTY_FUT | 104 | -12.483 | -11.423 | 1.499 | +1.059 | yes | yes | 0.001 |
| 2 | 30s | ask_refill_ratio | NIFTY_FUT | 178 | -3.302 | -3.525 | 0.387 | -0.223 | yes | yes | 0.001 |
| 2 | 30s | ask_refill_ratio | BANKNIFTY_FUT | 97 | -13.255 | -11.883 | 1.553 | +1.372 | yes | yes | 0.001 |
| 2 | 30s | bid_refills_w | NIFTY_FUT | 961 | -2.614 | -2.824 | 0.167 | -0.210 | yes | yes | 0.001 |
| 2 | 30s | bid_refills_w | BANKNIFTY_FUT | 865 | -8.587 | -8.518 | 0.520 | +0.069 | yes | yes | 0.001 |
| 2 | 30s | ask_refills_w | NIFTY_FUT | 912 | -2.714 | -2.824 | 0.171 | -0.110 | yes | yes | 0.001 |
| 2 | 30s | ask_refills_w | BANKNIFTY_FUT | 807 | -8.330 | -7.864 | 0.538 | +0.467 | yes | yes | 0.001 |
| 2 | 120s | bid_refills | NIFTY_FUT | 681 | -4.140 | -3.985 | 0.398 | +0.155 | yes | yes | 0.001 |
| 2 | 120s | bid_refills | BANKNIFTY_FUT | 480 | -14.993 | -16.425 | 1.454 | -1.432 | yes | yes | 0.001 |
| 2 | 120s | ask_refills | NIFTY_FUT | 628 | -4.423 | -4.270 | 0.415 | +0.152 | yes | yes | 0.001 |
| 2 | 120s | ask_refills | BANKNIFTY_FUT | 315 | -16.575 | -16.819 | 1.795 | -0.244 | yes | yes | 0.001 |
| 2 | 120s | bid_refill_ratio | NIFTY_FUT | 244 | -5.771 | -5.841 | 0.665 | -0.070 | yes | yes | 0.001 |
| 2 | 120s | bid_refill_ratio | BANKNIFTY_FUT | 103 | -26.777 | -30.690 | 3.139 | -3.913 | yes | yes | 0.001 |
| 2 | 120s | ask_refill_ratio | NIFTY_FUT | 171 | -6.970 | -6.858 | 0.795 | +0.112 | yes | yes | 0.001 |
| 2 | 120s | ask_refill_ratio | BANKNIFTY_FUT | 91 | -29.044 | -31.614 | 3.340 | -2.570 | yes | yes | 0.001 |
| 2 | 120s | bid_refills_w | NIFTY_FUT | 814 | -6.679 | -6.354 | 0.364 | +0.325 | yes | yes | 0.001 |
| 2 | 120s | bid_refills_w | BANKNIFTY_FUT | 750 | -23.576 | -23.615 | 1.163 | -0.039 | yes | yes | 0.001 |
| 2 | 120s | ask_refills_w | NIFTY_FUT | 803 | -7.278 | -7.215 | 0.367 | +0.063 | yes | yes | 0.001 |
| 2 | 120s | ask_refills_w | BANKNIFTY_FUT | 714 | -22.237 | -23.068 | 1.192 | -0.830 | yes | yes | 0.001 |
### INJ+ (sealed design)
| seed | horizon | feature | inst | n_eff | injected (pts) | recovered (pts) | SE (pts) | recovered − injected | within 2 SE | sign ok | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 5s | bid_refills | NIFTY_FUT | 820 | +0.656 | +0.878 | 0.078 | +0.222 | no | yes | 0.001 |
| 1 | 5s | bid_refills | BANKNIFTY_FUT | 575 | +2.234 | +2.644 | 0.266 | +0.411 | yes | yes | 0.001 |
| 1 | 5s | ask_refills | NIFTY_FUT | 754 | +0.684 | +0.392 | 0.081 | -0.292 | no | yes | 0.001 |
| 1 | 5s | ask_refills | BANKNIFTY_FUT | 363 | +2.812 | +2.120 | 0.335 | -0.691 | no | yes | 0.001 |
| 1 | 5s | bid_refills_w | NIFTY_FUT | 1017 | +0.589 | +0.726 | 0.070 | +0.137 | yes | yes | 0.001 |
| 1 | 5s | bid_refills_w | BANKNIFTY_FUT | 911 | +1.775 | +2.220 | 0.211 | +0.445 | no | yes | 0.001 |
| 1 | 5s | ask_refills_w | NIFTY_FUT | 978 | +0.601 | +0.423 | 0.071 | -0.177 | no | yes | 0.001 |
| 1 | 5s | ask_refills_w | BANKNIFTY_FUT | 866 | +1.820 | +1.442 | 0.217 | -0.378 | yes | yes | 0.001 |
| 1 | 30s | bid_refills | NIFTY_FUT | 619 | +1.743 | +2.665 | 0.208 | +0.922 | no | yes | 0.001 |
| 1 | 30s | bid_refills | BANKNIFTY_FUT | 417 | +6.286 | +7.429 | 0.749 | +1.143 | yes | yes | 0.001 |
| 1 | 30s | ask_refills | NIFTY_FUT | 538 | +1.871 | +0.606 | 0.223 | -1.264 | no | yes | 0.001 |
| 1 | 30s | ask_refills | BANKNIFTY_FUT | 331 | +7.064 | +4.121 | 0.840 | -2.943 | no | yes | 0.001 |
| 1 | 30s | bid_refill_ratio | NIFTY_FUT | 250 | +2.741 | +2.933 | 0.327 | +0.192 | yes | yes | 0.001 |
| 1 | 30s | bid_refill_ratio | BANKNIFTY_FUT | 106 | +12.483 | +11.826 | 1.485 | -0.657 | yes | yes | 0.001 |
| 1 | 30s | ask_refill_ratio | NIFTY_FUT | 171 | +3.302 | +3.169 | 0.395 | -0.133 | yes | yes | 0.001 |
| 1 | 30s | ask_refill_ratio | BANKNIFTY_FUT | 94 | +13.255 | +11.879 | 1.577 | -1.376 | yes | yes | 0.001 |
| 1 | 30s | bid_refills_w | NIFTY_FUT | 275 | +2.614 | +3.254 | 0.312 | +0.640 | no | yes | 0.001 |
| 1 | 30s | bid_refills_w | BANKNIFTY_FUT | 224 | +8.587 | +10.336 | 1.022 | +1.749 | yes | yes | 0.001 |
| 1 | 30s | ask_refills_w | NIFTY_FUT | 256 | +2.714 | +1.778 | 0.323 | -0.936 | no | yes | 0.001 |
| 1 | 30s | ask_refills_w | BANKNIFTY_FUT | 238 | +8.330 | +6.039 | 0.991 | -2.292 | no | yes | 0.001 |
| 1 | 120s | bid_refills | NIFTY_FUT | 438 | +4.140 | +5.073 | 0.497 | +0.933 | yes | yes | 0.001 |
| 1 | 120s | bid_refills | BANKNIFTY_FUT | 317 | +14.993 | +17.097 | 1.789 | +2.104 | yes | yes | 0.001 |
| 1 | 120s | ask_refills | NIFTY_FUT | 385 | +4.423 | +2.737 | 0.530 | -1.685 | no | yes | 0.001 |
| 1 | 120s | ask_refills | BANKNIFTY_FUT | 261 | +16.575 | +11.739 | 1.972 | -4.835 | no | yes | 0.001 |
| 1 | 120s | bid_refill_ratio | NIFTY_FUT | 228 | +5.771 | +5.573 | 0.688 | -0.198 | yes | yes | 0.001 |
| 1 | 120s | bid_refill_ratio | BANKNIFTY_FUT | 100 | +26.777 | +24.903 | 3.186 | -1.875 | yes | yes | 0.001 |
| 1 | 120s | ask_refill_ratio | NIFTY_FUT | 155 | +6.970 | +7.240 | 0.835 | +0.270 | yes | yes | 0.001 |
| 1 | 120s | ask_refill_ratio | BANKNIFTY_FUT | 85 | +29.044 | +28.174 | 3.456 | -0.870 | yes | yes | 0.001 |
| 1 | 120s | bid_refills_w | NIFTY_FUT | 169 | +6.679 | +8.001 | 0.799 | +1.322 | yes | yes | 0.001 |
| 1 | 120s | bid_refills_w | BANKNIFTY_FUT | 129 | +23.576 | +26.042 | 2.805 | +2.466 | yes | yes | 0.001 |
| 1 | 120s | ask_refills_w | NIFTY_FUT | 144 | +7.278 | +5.324 | 0.866 | -1.954 | no | yes | 0.001 |
| 1 | 120s | ask_refills_w | BANKNIFTY_FUT | 145 | +22.237 | +18.532 | 2.646 | -3.706 | yes | yes | 0.001 |
| 2 | 5s | bid_refills | NIFTY_FUT | 820 | +0.656 | +0.880 | 0.078 | +0.224 | no | yes | 0.001 |
| 2 | 5s | bid_refills | BANKNIFTY_FUT | 575 | +2.234 | +2.640 | 0.266 | +0.407 | yes | yes | 0.001 |
| 2 | 5s | ask_refills | NIFTY_FUT | 754 | +0.684 | +0.391 | 0.081 | -0.293 | no | yes | 0.001 |
| 2 | 5s | ask_refills | BANKNIFTY_FUT | 363 | +2.812 | +2.103 | 0.335 | -0.708 | no | yes | 0.001 |
| 2 | 5s | bid_refills_w | NIFTY_FUT | 1017 | +0.589 | +0.724 | 0.070 | +0.135 | yes | yes | 0.001 |
| 2 | 5s | bid_refills_w | BANKNIFTY_FUT | 911 | +1.775 | +2.220 | 0.211 | +0.446 | no | yes | 0.001 |
| 2 | 5s | ask_refills_w | NIFTY_FUT | 978 | +0.601 | +0.423 | 0.071 | -0.177 | no | yes | 0.001 |
| 2 | 5s | ask_refills_w | BANKNIFTY_FUT | 866 | +1.820 | +1.437 | 0.217 | -0.383 | yes | yes | 0.001 |
| 2 | 30s | bid_refills | NIFTY_FUT | 619 | +1.743 | +2.673 | 0.208 | +0.930 | no | yes | 0.001 |
| 2 | 30s | bid_refills | BANKNIFTY_FUT | 417 | +6.286 | +7.400 | 0.749 | +1.114 | yes | yes | 0.001 |
| 2 | 30s | ask_refills | NIFTY_FUT | 538 | +1.871 | +0.601 | 0.223 | -1.269 | no | yes | 0.001 |
| 2 | 30s | ask_refills | BANKNIFTY_FUT | 331 | +7.064 | +4.114 | 0.840 | -2.950 | no | yes | 0.001 |
| 2 | 30s | bid_refill_ratio | NIFTY_FUT | 250 | +2.741 | +2.926 | 0.327 | +0.185 | yes | yes | 0.001 |
| 2 | 30s | bid_refill_ratio | BANKNIFTY_FUT | 106 | +12.483 | +11.821 | 1.485 | -0.662 | yes | yes | 0.001 |
| 2 | 30s | ask_refill_ratio | NIFTY_FUT | 171 | +3.302 | +3.149 | 0.395 | -0.153 | yes | yes | 0.001 |
| 2 | 30s | ask_refill_ratio | BANKNIFTY_FUT | 94 | +13.255 | +11.891 | 1.577 | -1.365 | yes | yes | 0.001 |
| 2 | 30s | bid_refills_w | NIFTY_FUT | 275 | +2.614 | +3.259 | 0.312 | +0.645 | no | yes | 0.001 |
| 2 | 30s | bid_refills_w | BANKNIFTY_FUT | 224 | +8.587 | +10.349 | 1.022 | +1.762 | yes | yes | 0.001 |
| 2 | 30s | ask_refills_w | NIFTY_FUT | 256 | +2.714 | +1.787 | 0.323 | -0.928 | no | yes | 0.001 |
| 2 | 30s | ask_refills_w | BANKNIFTY_FUT | 238 | +8.330 | +5.976 | 0.991 | -2.354 | no | yes | 0.001 |
| 2 | 120s | bid_refills | NIFTY_FUT | 438 | +4.140 | +5.068 | 0.497 | +0.928 | yes | yes | 0.001 |
| 2 | 120s | bid_refills | BANKNIFTY_FUT | 317 | +14.993 | +17.022 | 1.789 | +2.030 | yes | yes | 0.001 |
| 2 | 120s | ask_refills | NIFTY_FUT | 385 | +4.423 | +2.746 | 0.530 | -1.676 | no | yes | 0.001 |
| 2 | 120s | ask_refills | BANKNIFTY_FUT | 261 | +16.575 | +11.745 | 1.972 | -4.830 | no | yes | 0.001 |
| 2 | 120s | bid_refill_ratio | NIFTY_FUT | 228 | +5.771 | +5.528 | 0.688 | -0.243 | yes | yes | 0.001 |
| 2 | 120s | bid_refill_ratio | BANKNIFTY_FUT | 100 | +26.777 | +24.945 | 3.186 | -1.832 | yes | yes | 0.001 |
| 2 | 120s | ask_refill_ratio | NIFTY_FUT | 155 | +6.970 | +7.223 | 0.835 | +0.253 | yes | yes | 0.001 |
| 2 | 120s | ask_refill_ratio | BANKNIFTY_FUT | 85 | +29.044 | +28.177 | 3.456 | -0.867 | yes | yes | 0.001 |
| 2 | 120s | bid_refills_w | NIFTY_FUT | 169 | +6.679 | +7.938 | 0.799 | +1.259 | yes | yes | 0.001 |
| 2 | 120s | bid_refills_w | BANKNIFTY_FUT | 129 | +23.576 | +26.171 | 2.805 | +2.595 | yes | yes | 0.001 |
| 2 | 120s | ask_refills_w | NIFTY_FUT | 144 | +7.278 | +5.280 | 0.866 | -1.998 | no | yes | 0.001 |
| 2 | 120s | ask_refills_w | BANKNIFTY_FUT | 145 | +22.237 | +18.485 | 2.646 | -3.752 | yes | yes | 0.001 |
### INJ− (sealed design)
| seed | horizon | feature | inst | n_eff | injected (pts) | recovered (pts) | SE (pts) | recovered − injected | within 2 SE | sign ok | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 5s | bid_refills | NIFTY_FUT | 820 | -0.656 | -0.434 | 0.078 | +0.222 | no | yes | 0.001 |
| 1 | 5s | bid_refills | BANKNIFTY_FUT | 575 | -2.234 | -1.823 | 0.266 | +0.411 | yes | yes | 0.001 |
| 1 | 5s | ask_refills | NIFTY_FUT | 754 | -0.684 | -0.976 | 0.081 | -0.292 | no | yes | 0.001 |
| 1 | 5s | ask_refills | BANKNIFTY_FUT | 363 | -2.812 | -3.503 | 0.335 | -0.691 | no | yes | 0.001 |
| 1 | 5s | bid_refills_w | NIFTY_FUT | 1017 | -0.589 | -0.452 | 0.070 | +0.137 | yes | yes | 0.001 |
| 1 | 5s | bid_refills_w | BANKNIFTY_FUT | 911 | -1.775 | -1.329 | 0.211 | +0.445 | no | yes | 0.001 |
| 1 | 5s | ask_refills_w | NIFTY_FUT | 978 | -0.601 | -0.778 | 0.071 | -0.177 | no | yes | 0.001 |
| 1 | 5s | ask_refills_w | BANKNIFTY_FUT | 866 | -1.820 | -2.198 | 0.217 | -0.378 | yes | yes | 0.001 |
| 1 | 30s | bid_refills | NIFTY_FUT | 619 | -1.743 | -0.820 | 0.208 | +0.922 | no | yes | 0.001 |
| 1 | 30s | bid_refills | BANKNIFTY_FUT | 417 | -6.286 | -5.143 | 0.749 | +1.143 | yes | yes | 0.001 |
| 1 | 30s | ask_refills | NIFTY_FUT | 538 | -1.871 | -3.135 | 0.223 | -1.264 | no | yes | 0.001 |
| 1 | 30s | ask_refills | BANKNIFTY_FUT | 331 | -7.064 | -10.007 | 0.840 | -2.943 | no | yes | 0.001 |
| 1 | 30s | bid_refill_ratio | NIFTY_FUT | 250 | -2.741 | -2.549 | 0.327 | +0.192 | yes | yes | 0.001 |
| 1 | 30s | bid_refill_ratio | BANKNIFTY_FUT | 106 | -12.483 | -13.140 | 1.485 | -0.657 | yes | yes | 0.001 |
| 1 | 30s | ask_refill_ratio | NIFTY_FUT | 171 | -3.302 | -3.435 | 0.395 | -0.133 | yes | yes | 0.001 |
| 1 | 30s | ask_refill_ratio | BANKNIFTY_FUT | 94 | -13.255 | -14.632 | 1.577 | -1.376 | yes | yes | 0.001 |
| 1 | 30s | bid_refills_w | NIFTY_FUT | 275 | -2.614 | -1.974 | 0.312 | +0.640 | no | yes | 0.001 |
| 1 | 30s | bid_refills_w | BANKNIFTY_FUT | 224 | -8.587 | -6.838 | 1.022 | +1.749 | yes | yes | 0.001 |
| 1 | 30s | ask_refills_w | NIFTY_FUT | 256 | -2.714 | -3.651 | 0.323 | -0.936 | no | yes | 0.001 |
| 1 | 30s | ask_refills_w | BANKNIFTY_FUT | 238 | -8.330 | -10.622 | 0.991 | -2.292 | no | yes | 0.001 |
| 1 | 120s | bid_refills | NIFTY_FUT | 438 | -4.140 | -3.208 | 0.497 | +0.933 | yes | yes | 0.001 |
| 1 | 120s | bid_refills | BANKNIFTY_FUT | 317 | -14.993 | -12.888 | 1.789 | +2.104 | yes | yes | 0.001 |
| 1 | 120s | ask_refills | NIFTY_FUT | 385 | -4.423 | -6.108 | 0.530 | -1.685 | no | yes | 0.001 |
| 1 | 120s | ask_refills | BANKNIFTY_FUT | 261 | -16.575 | -21.410 | 1.972 | -4.835 | no | yes | 0.001 |
| 1 | 120s | bid_refill_ratio | NIFTY_FUT | 228 | -5.771 | -5.970 | 0.688 | -0.198 | yes | yes | 0.001 |
| 1 | 120s | bid_refill_ratio | BANKNIFTY_FUT | 100 | -26.777 | -28.652 | 3.186 | -1.875 | yes | yes | 0.001 |
| 1 | 120s | ask_refill_ratio | NIFTY_FUT | 155 | -6.970 | -6.700 | 0.835 | +0.270 | yes | yes | 0.001 |
| 1 | 120s | ask_refill_ratio | BANKNIFTY_FUT | 85 | -29.044 | -29.914 | 3.456 | -0.870 | yes | yes | 0.001 |
| 1 | 120s | bid_refills_w | NIFTY_FUT | 169 | -6.679 | -5.357 | 0.799 | +1.322 | yes | yes | 0.001 |
| 1 | 120s | bid_refills_w | BANKNIFTY_FUT | 129 | -23.576 | -21.110 | 2.805 | +2.466 | yes | yes | 0.001 |
| 1 | 120s | ask_refills_w | NIFTY_FUT | 144 | -7.278 | -9.232 | 0.866 | -1.954 | no | yes | 0.001 |
| 1 | 120s | ask_refills_w | BANKNIFTY_FUT | 145 | -22.237 | -25.943 | 2.646 | -3.706 | yes | yes | 0.001 |
| 2 | 5s | bid_refills | NIFTY_FUT | 820 | -0.656 | -0.432 | 0.078 | +0.224 | no | yes | 0.001 |
| 2 | 5s | bid_refills | BANKNIFTY_FUT | 575 | -2.234 | -1.827 | 0.266 | +0.407 | yes | yes | 0.001 |
| 2 | 5s | ask_refills | NIFTY_FUT | 754 | -0.684 | -0.977 | 0.081 | -0.293 | no | yes | 0.001 |
| 2 | 5s | ask_refills | BANKNIFTY_FUT | 363 | -2.812 | -3.520 | 0.335 | -0.708 | no | yes | 0.001 |
| 2 | 5s | bid_refills_w | NIFTY_FUT | 1017 | -0.589 | -0.454 | 0.070 | +0.135 | yes | yes | 0.001 |
| 2 | 5s | bid_refills_w | BANKNIFTY_FUT | 911 | -1.775 | -1.329 | 0.211 | +0.446 | no | yes | 0.001 |
| 2 | 5s | ask_refills_w | NIFTY_FUT | 978 | -0.601 | -0.778 | 0.071 | -0.177 | no | yes | 0.001 |
| 2 | 5s | ask_refills_w | BANKNIFTY_FUT | 866 | -1.820 | -2.203 | 0.217 | -0.383 | yes | yes | 0.001 |
| 2 | 30s | bid_refills | NIFTY_FUT | 619 | -1.743 | -0.812 | 0.208 | +0.930 | no | yes | 0.001 |
| 2 | 30s | bid_refills | BANKNIFTY_FUT | 417 | -6.286 | -5.172 | 0.749 | +1.114 | yes | yes | 0.001 |
| 2 | 30s | ask_refills | NIFTY_FUT | 538 | -1.871 | -3.140 | 0.223 | -1.269 | no | yes | 0.001 |
| 2 | 30s | ask_refills | BANKNIFTY_FUT | 331 | -7.064 | -10.014 | 0.840 | -2.950 | no | yes | 0.001 |
| 2 | 30s | bid_refill_ratio | NIFTY_FUT | 250 | -2.741 | -2.556 | 0.327 | +0.185 | yes | yes | 0.001 |
| 2 | 30s | bid_refill_ratio | BANKNIFTY_FUT | 106 | -12.483 | -13.144 | 1.485 | -0.662 | yes | yes | 0.001 |
| 2 | 30s | ask_refill_ratio | NIFTY_FUT | 171 | -3.302 | -3.455 | 0.395 | -0.153 | yes | yes | 0.001 |
| 2 | 30s | ask_refill_ratio | BANKNIFTY_FUT | 94 | -13.255 | -14.620 | 1.577 | -1.365 | yes | yes | 0.001 |
| 2 | 30s | bid_refills_w | NIFTY_FUT | 275 | -2.614 | -1.969 | 0.312 | +0.645 | no | yes | 0.001 |
| 2 | 30s | bid_refills_w | BANKNIFTY_FUT | 224 | -8.587 | -6.825 | 1.022 | +1.762 | yes | yes | 0.001 |
| 2 | 30s | ask_refills_w | NIFTY_FUT | 256 | -2.714 | -3.642 | 0.323 | -0.928 | no | yes | 0.001 |
| 2 | 30s | ask_refills_w | BANKNIFTY_FUT | 238 | -8.330 | -10.685 | 0.991 | -2.354 | no | yes | 0.001 |
| 2 | 120s | bid_refills | NIFTY_FUT | 438 | -4.140 | -3.213 | 0.497 | +0.928 | yes | yes | 0.001 |
| 2 | 120s | bid_refills | BANKNIFTY_FUT | 317 | -14.993 | -12.963 | 1.789 | +2.030 | yes | yes | 0.001 |
| 2 | 120s | ask_refills | NIFTY_FUT | 385 | -4.423 | -6.099 | 0.530 | -1.676 | no | yes | 0.001 |
| 2 | 120s | ask_refills | BANKNIFTY_FUT | 261 | -16.575 | -21.405 | 1.972 | -4.830 | no | yes | 0.001 |
| 2 | 120s | bid_refill_ratio | NIFTY_FUT | 228 | -5.771 | -6.015 | 0.688 | -0.243 | yes | yes | 0.001 |
| 2 | 120s | bid_refill_ratio | BANKNIFTY_FUT | 100 | -26.777 | -28.610 | 3.186 | -1.832 | yes | yes | 0.001 |
| 2 | 120s | ask_refill_ratio | NIFTY_FUT | 155 | -6.970 | -6.717 | 0.835 | +0.253 | yes | yes | 0.001 |
| 2 | 120s | ask_refill_ratio | BANKNIFTY_FUT | 85 | -29.044 | -29.911 | 3.456 | -0.867 | yes | yes | 0.001 |
| 2 | 120s | bid_refills_w | NIFTY_FUT | 169 | -6.679 | -5.420 | 0.799 | +1.259 | yes | yes | 0.001 |
| 2 | 120s | bid_refills_w | BANKNIFTY_FUT | 129 | -23.576 | -20.982 | 2.805 | +2.595 | yes | yes | 0.001 |
| 2 | 120s | ask_refills_w | NIFTY_FUT | 144 | -7.278 | -9.276 | 0.866 | -1.998 | no | yes | 0.001 |
| 2 | 120s | ask_refills_w | BANKNIFTY_FUT | 145 | -22.237 | -25.990 | 2.646 | -3.752 | yes | yes | 0.001 |
