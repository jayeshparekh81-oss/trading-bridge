# D5 — BREAKOUT FAMILY: ASLI-BREAK METER v0
## DESIGN FROZEN PRE-MARKET-DNA — no thresholds fitted to any data
DESIGN-ONLY DRAFT. Zero outcome numbers. Nothing enabled.

## Frame
ORH/ORL (opening-range high/low) continuation-vs-failure fork — the mirror of the LAR
state machine (R4/P7): where LAR watches approach→touch→resolution at reference
levels, the ASLI-BREAK METER scores whether a BREAK of ORH/ORL is real (continuation)
or fake (failure/sweep) — using PHYSICS-CLEAN inputs only.

## Four MANDATORY gates (all must pass; each PHYSICS-CLEAN by FEED_PHYSICS class)
- G1 UNSIGNED RESPONSE EFFICIENCY (P5 variant): |dPrice| per unit TOTAL volume over
  the break bar(s) — UNSIGNED, so it does NOT inherit the Lee-Ready mis-sign floor
  (per the approved §6 caveat line). Gate: efficiency HIGH vs the SAME TIME-BUCKET's
  percentile (frozen bucket grid), AND closes must HOLD beyond the level (close
  beyond ORH/ORL for the required bars, not just wick beyond).
- G2 P6 DEPTH CONFIRM: on the break side, opposite-side WALLS VANISH (P6 wall
  detector) AND NO replenishment INTO the break (P6 refill detector on the broken
  side) within the confirm window. Book-only → PHYSICS-CLEAN.
- G3 P7 LAR-VETO (the fake-break trap): if the level was SWEPT and then shows
  absorption / reclaim-AGAINST the break within K bars (LAR's TOUCHED→
  absorption/reclaim transitions), classify FAKE => block entry / exit if in.
- G4 HYGIENE GATES: spread gate (book spread <= frozen ticks), data-quality gate
  (no watchdog RED / coverage floor per HEALTH_CARD), OR-width gate (opening range
  width within a frozen band — degenerate-narrow and blown-out ranges both
  excluded), time-bucket gate (breaks scored only in frozen buckets).

## EXCLUDED inputs (with citations — these do NOT get seats)
- qi (queue_imbalance): R2-02 probe — inside the null on BOTH instruments.
- pain_map: R2-03 probe — sign-flip across instruments = noise; fuel term never
  populated (EMPTY-GRID gap) — nothing to admit.
- delta / book_ofi as VETO: PHYSICS-BOUNDED (FEED_PHYSICS §3 mis-sign floor; probe
  inverse-only tails). Permitted ONLY as a >=10:00 tie-breaker via its own future
  pre-registration — never in v0.

## Exits (selection phase, frozen)
-1R / +1.5R bracket, futures-priced first (options only via D3 after it passes).
No trailing/partial in v0 — selection-phase simplicity is the point.

## Parameters-to-freeze (list — values at pre-registration, NOT here, NOT from data)
OR window minutes; hold-bars count; G1 percentile threshold (proposal: 80th,
same-time-bucket) + bucket grid; G2 confirm window + wall/refill definitions (P6's
existing frozen ones); G3 K = P7's EXISTING constant sweep_to_absorption_bars = 10
(lar_study.py STUDY_CONFIG, tick-100 bars — no new number invented); G4 spread
ticks, OR-width band, time buckets; K-bar entry timeout. Final values re-frozen at
Round-2 pre-registration before blind data, per this design's own rule.

## SEQUENCING NOTE (the point of writing this now)
Market-DNA's ORB follow-through/fade base-rate — when it is measured later — decides
whether this family's seat is FOLLOW (continuation) or FADE (failure); the METER's
gates are direction-agnostic by construction, so the design is frozen BEFORE that
number exists and cannot have been shaped by it. Round-2 pre-registration on fresh
blind data only.

## Ledger binding-format entry
- id: R2-18 (new)
- observation: ORH/ORL breaks are the highest-visibility intraday events; the stack
  has PHYSICS-CLEAN sensors (unsigned P5 variant, P6 walls/refill, P7 LAR states)
  that have never been composed into a break-quality score; signed-flow components
  are excluded by probe results and physics.
- mechanical rule: 4-gate ASLI-BREAK METER above, direction seat decided by
  Market-DNA base-rate, exits -1R/+1.5R futures-priced.
- parameters-to-freeze: the list above, frozen at pre-registration before any
  fresh-data contact.
- exam design: Round-2 fresh blind data; per-instrument; gates-on vs gates-off
  candidate sets through the full harness (permutation, DSR, costs, random-removal
  null per NEG-01 precedent); one frozen parameter set (no sweeps in v0).
- what-would-kill-it: gate-passing breaks' continuation rate indistinguishable from
  all-breaks base rate (gates add nothing); or the whole edge explained by the
  time-bucket gate alone (then it's a time-of-day effect, not break quality); or
  Market-DNA base-rate so one-sided that the fork itself is degenerate.
