# MARKET DNA — DRAFT (market character ONLY; zero strategy-outcome/PnL/R numbers)
Study run 2026-07-25 per the pre-declared M1-M5 spec (frozen before results; STEP-1
declaration commit 6630508 sealed the portfolio framing BEFORE this ran).
Data: NIFTY_FUT + BANKNIFTY_FUT raw tick parquets; days 2026-07-13 (LOCAL — included),
07-15, 16, 17, 20, 21; 07-14 EXCLUDED (degraded). 1-min/5-min OHLCV from
volume-advancing trades, 09:15-15:30 IST (saturating-packet-clock finding => no tick
bars). Day-block bootstrap 1000 draws, seed 20260725. Peak RSS 94MB.
N = 6 days — UNDECIDABLE-AT-N is an expected verdict class.

## M1 — Variance ratios + autocorrelation
| inst | VR5 [95% CI] | VR15 | VR30 | ac1(1m) [CI] | ac1(5m) |
|---|---|---|---|---|---|
| NIFTY | 0.765 [0.700, 0.845] | 0.818 | 0.795 | -0.112 [-0.173, -0.063] | -0.079 |
| BANKNIFTY | 0.869 [0.733, 1.071] | 0.897 | 0.887 | -0.036 [-0.127, +0.057] | -0.073 |
NIFTY: VR<1 with CI EXCLUDING 1 and ac1<0 with CI excluding 0 => sub-random-walk,
negatively autocorrelated (mean-reverting character) at the 1-5min scale.
BANKNIFTY: same direction but both CIs straddle the null => UNDECIDABLE-AT-N.
Per-day VR5 spread: NIFTY 0.649-0.931; BANKNIFTY 0.659-1.283 (07-15 the outlier >1).
M1 CAVEAT: 1-min negative ac1 partly reflects bid-ask bounce (Roll effect) in
trade prices — magnitude not readable as tradeable alpha; the character claim
rests on VR15/VR30 < 1 and M4's 30-min horizon.

## M2 — ORB (OR 09:15-09:30; break = first 1-min close beyond; follow = +0.5xOR-width
before mid-retouch; fade = mid-retouch first)
| inst | n breaks | follow | fade | unresolved | follow rate [95% CI] | ttr min (list) |
|---|---|---|---|---|---|---|
| NIFTY | 6 | 3 | 3 | 0 | 0.50 [0.167, 1.000] | 3,142,68,45,60,17 (median ~52) |
| BANKNIFTY | 6 | 2 | 3 | 1 | 0.33 [0.000, 0.667] | 9,205,6,46,222 (median 46) |
Per-day: NIFTY up/F, up/fade, up/fade, up/F, dn/fade, dn/F; BANKNIFTY up/F, up/fade,
dn/fade, up/F, dn/fade, dn/unresolved. Directions mixed; CIs span the coin =>
UNDECIDABLE-AT-N on follow-vs-fade.

## M3 — Time-of-day buckets (mean across days)
| inst | bucket | range share | rv(1m) bp | VR5 | ac1(1m) |
|---|---|---|---|---|---|
| NIFTY | 09:15-10:30 | 0.63 | 3.3 | 0.98 | -0.13 |
| NIFTY | 10:30-13:00 | 0.57 | 2.8 | 0.55 | -0.12 |
| NIFTY | 13:00-15:30 | 0.50 | 3.0 | 0.81 | -0.17 |
| BANKNIFTY | 09:15-10:30 | 0.71 | 4.2 | 1.09 | -0.02 |
| BANKNIFTY | 10:30-13:00 | 0.54 | 3.6 | 0.71 | -0.12 |
| BANKNIFTY | 13:00-15:30 | 0.55 | 3.6 | 0.82 | -0.06 |
Open bucket owns the range (0.63/0.71 share) and is the LEAST mean-reverting
(VR5 ~1.0); midday is the most mean-reverting (VR5 0.55/0.71). Character varies by
bucket — any Round-2 family should expect bucket-dependence.

## M4 — VWAP-distance vs forward 30-min return (Spearman on 5-min closes)
| inst | per-day rho | pooled mean [95% CI] |
|---|---|---|
| NIFTY | -0.582, -0.184, -0.277, -0.316, -0.247, -0.745 | -0.392 [-0.563, -0.242] |
| BANKNIFTY | -0.620, -0.240, -0.453, -0.288, -0.214, -0.672 | -0.414 [-0.563, -0.279] |
NEGATIVE on all 12 instrument-days; pooled CIs exclude 0 on BOTH instruments =>
price stretched from VWAP tends to revert over the next 30 min. The single most
consistent character statistic in the study.

## M5 — Gaps (ANECDOTE-N: 5 observations per instrument; day-by-day list, NO inference)
NIFTY: 07-15 -174.0 (-0.718%), 07-16 +45.0 (+0.187%), 07-17 -7.6 (-0.032%),
07-20 -99.0 (-0.407%), 07-21 -57.1 (-0.235%).
BANKNIFTY: 07-15 -530.4 (-0.911%), 07-16 +76.0 (+0.131%), 07-17 -26.0 (-0.045%),
07-20 -629.6 (-1.074%), 07-21 -105.0 (-0.181%).

## FAMILY FIT TABLE (prioritization input ONLY; nothing adopted)
| family | evidence line | verdict |
|---|---|---|
| bias/trend (intraday) | VR<1 + ac1<0 (NIFTY CI-backed) + M4 reversion both insts — intraday drift-following is fighting the measured character | ANTI-FIT (NIFTY) / UNDECIDABLE-AT-N (BANKNIFTY) |
| breakout-FOLLOW | follow rate 0.50 / 0.33 with CIs [0.17,1.00] / [0.00,0.67] spanning the coin | UNDECIDABLE-AT-N |
| breakout-FADE | fade rate 0.50 / 0.60-of-resolved, same spanning CIs; midday VR5 lowest (fade-friendly bucket hint only) | UNDECIDABLE-AT-N |
| mean-revert | the ONLY CI-backed positive: M4 rho -0.39/-0.41 (CIs exclude 0, 12/12 days negative) + NIFTY VR5/ac1 CI-backed | FIT (strongest measured character) |
| option-vehicle | no M1-M5 metric addresses vehicle economics; decided by the D3/R2-17 execution exam, not by market character | UNDECIDABLE (out of this study's scope) |

FAMILY FIT FOOTER: FIT = measured character, in-sample N=6 days — NOT an edge
claim. Any mean-revert candidate must clear the ~0.29R/trade cost hurdle + full
harness on fresh blind data (Round-2). Next-design note: VWAP-reversion family
draft (D6) motivated by M4; to be drafted design-only and sealed before ITS OWN
exam data.

## D5 SEAT LINE
ORB base-rate verdict for the ASLI-BREAK METER seat (FOLLOW vs FADE):
**UNDECIDABLE-AT-N** — 6 breaks/instrument, follow-rate CIs [0.167, 1.000] and
[0.000, 0.667] both span 0.5. The seat decision defers to more sessions; the D5
design remains direction-agnostic as built.
