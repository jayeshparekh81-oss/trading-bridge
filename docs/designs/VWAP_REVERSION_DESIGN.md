# D6 — VWAP REVERSION DESIGN
## MOTIVATED BY MARKET-DNA M4 (in-sample, N=6 days, ba7b0e0) — hypothesis generated on
## burned data; the EXAM runs on fresh blind data; this design is sealed before ITS OWN
## exam data exists.
DESIGN-ONLY DRAFT. Zero outcome numbers. Nothing enabled anywhere.

## Observation (citations only, no new numbers)
- MARKET-DNA M4: VWAP-distance vs forward-30-min return Spearman NEGATIVE on 12/12
  instrument-days, pooled CIs exclude 0 on both instruments (docs/market_dna, ba7b0e0).
- MARKET-DNA M3: midday is the most mean-reverting bucket; the open bucket is distinct
  (least mean-reverting, owns the range).
- FEED_PHYSICS §6: the price/VWAP family is PHYSICS-CLEAN (LTP path exact at packet
  cadence; session VWAP/SD causal) — no mis-sign floor applies to this family.

## Mechanical rule (PROPOSALS; final freeze at Round-2 pre-registration)
- Universe: NIFTY_FUT + BANKNIFTY_FUT, per-instrument (separate walk-forward runs).
- Time filter: buckets 2+3 ONLY (10:30-15:30). Bucket-1 EXCLUDED for two independent
  reasons, both cited: M3 (open bucket least mean-reverting, VR5 ~1.0) and
  FEED_PHYSICS open-window noise (collapse peaks 64-86%, w most unstable at the open).
- Setup: at each 5-min close, stretch d = close - developing session VWAP; TRIGGER when
  |d| > P-th percentile of same-bucket |d| drawn from a TRAILING reference window
  recomputed per P2 boundaries (the median-anchor pattern — train-window-only, never
  the test day; NO absolute point thresholds anywhere). Proposal P = 80th.
- Direction: TOWARD VWAP — short if d > 0, long if d < 0. Entry at the NEXT 5-min open.
- Exits (frozen shape):
  * target = touch of CURRENT developing VWAP (moving target);
  * stop = FIXED at entry price +/- S x entry-stretch (proposal S = 1.0, symmetric);
  * max-hold = 30 min wall-clock (M4's measured horizon);
  * session-end flatten.
- RE-ENTRY RESET — after a stop-out, no re-entry in that instrument until |d| falls
  back below the P-th percentile and a FRESH stretch episode begins (prevents
  averaging into a trending move).
- One position per instrument — the SEQUENTIAL DE-DUP view is the ONLY judged view;
  candidate-level totals reported for honesty only (bar-size-sweep lesson: overlapping
  candidate sums are not tradeable numbers).

## Parameters-to-freeze (at Round-2 pre-registration, before blind data)
P (trigger percentile), S (stop factor), max-hold minutes, bucket set, trailing
reference-window length (proposal: trailing 5 sessions, recomputed per P2
boundaries), the RE-ENTRY RESET rule, and the 5-min bar spec (time bars from
volume-advancing trades, 09:15 anchor — the Market-DNA construction).

## Physics note
Uses ONLY price + session VWAP (PHYSICS-CLEAN family). No delta, no OFI, no qi, no
pain_map anywhere in the rule — the design is untouched by the Lee-Ready mis-sign
floor and by every probe-flagged component.

## Relation note
SEPARATE family from the frozen delta+vwap evaluator (continuation-flavored, sealed,
untouched, mid-exam on the frozen window); both stand until their own exams speak.
D6 does not read, modify, or depend on that evaluator or its window.

## Cost honesty
Mean-reversion = more trades than continuation families; the exam must clear the
~0.29R/trade net-cost hurdle; gross AND net are reported side by side, and the
sequential de-dup view is the decision basis.
HONESTY LINE: at 1:1 shape with ~0.29R/trade cost, breakeven WR ~= 65% — the
exam's bar, stated upfront (arithmetic, not data).

## Exam design (Round-2, fresh blind data ONLY)
Per-instrument, full harness: OOS walk-forward + permutation + DSR + plateau + costs;
PLUS a shuffled-entry-time null (random entries at matched same-bucket |d|-percentile
times — does the SPECIFIC trigger timing beat random timing at the same stretch
class?); PLUS the NEG-01 random-removal null on any subsetting step.

## What-would-kill-it
- Net edge ~= cost-mechanics under the NEG-01 random-removal null.
- Target-touch rate ~= the shuffled-entry-time null (timing adds nothing over the
  stretch class itself).
- Effect present ONLY in bucket-1 (contradiction of the design's own exclusion —
  would mean the M3/M4 reading was wrong).
- Effect vanishes at sequential de-dup (candidate-level mirage, the sweep lesson).

## Ledger binding-format entry
- id: R2-19 (new)
- observation: M4 VWAP-distance vs fwd-30-min negative 12/12 instrument-days with
  CIs excluding 0 (both instruments); M3 midday most mean-reverting, open bucket
  distinct; price/VWAP family PHYSICS-CLEAN (FEED_PHYSICS §6). Hypothesis generated
  on burned data (ba7b0e0); design sealed before its own exam data exists.
- mechanical rule: bucket-2/3-only VWAP-stretch reversion — trigger |d| > P-th
  same-bucket trailing percentile (P2 boundaries), enter next 5-min open toward
  VWAP, target VWAP touch, stop S x entry-stretch, 30-min max-hold, session flatten,
  one position per instrument (sequential de-dup judged).
- parameters-to-freeze: P, S, max-hold, bucket set, reference-window length, 5-min
  bar spec.
- exam design: Round-2 fresh blind data, per-instrument, full harness + shuffled-
  entry-time null + NEG-01 random-removal null; gross AND net; de-dup view decides.
- what-would-kill-it: cost-mechanics equivalence (NEG-01); timing ~= shuffled-entry
  null; bucket-1-only effect (self-contradiction); de-dup evaporation.
