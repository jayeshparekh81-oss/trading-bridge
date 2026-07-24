# D4 — IV-RANK DEFINITION (mechanical, feeds D3 variant (b))
DESIGN-ONLY DRAFT — pre-Market-DNA. Zero outcome numbers.

## Definition (mechanical)
IV_rank(strike, t) = percentile rank of R5-computed IV(strike, t) within a frozen
REFERENCE SET. Two candidate reference sets — ONE must be frozen before any use:
  REF-A (cross-sectional): today's ATM±20 same-side IVs at the same grid time t —
    ranks a strike against its neighbors NOW.
  REF-B (temporal): this strike's own IV over the trailing H sessions' grid points
    (iv_history.py store) — ranks now vs its own history.
FOUNDER FREEZE (recorded): REFERENCE = REF-B — own-strike trailing H=5 sessions via
iv_history. REF-A rejected — cross-sectional rank collapses toward ATM via the
smile. Wing-reorder kill tolerance frozen = 10% of adjacent-strike pairs
reordering under +/-150bp.

## Calibration honesty (mandatory statements)
- R5 IV is Black-Scholes-on-SPOT with risk_free_rate = 6.5% — FUNCTIONAL,
  UNCALIBRATED (chain/config.py:12; FEED_PHYSICS §3 context). Absolute IV LEVELS
  therefore carry rate-model error.
- IS percentile-rank calibration-invariant? PARTIALLY: a rate error shifts all IVs
  of similar moneyness/tenor in the same direction, so WITHIN-day cross-sectional
  rank (REF-A) is largely invariant to the rate constant; but the mapping is not
  perfectly monotone across moneyness (rate enters d1/d2 asymmetrically), so
  deep-wing ranks can reorder under a different rate. Temporal rank (REF-B) is
  invariant only if the rate constant is CONSTANT across the window (it is, 6.5%
  hardcoded) — so REF-B is internally consistent but absolute levels remain
  uncalibrated. State both in any exam.
- Ledger dependency flagged: R2-12 (risk-free-rate calibration) — a rate calibration
  would change wing ranks; any D3(b) result must state whether it survives a ±150bp
  rate perturbation re-rank (cheap invariance check, no new data).

## Parameters-to-freeze
Reference set (REF-A/REF-B/combined + H if temporal), grid time convention, moneyness
window (ATM±20), side handling (CE/PE ranked separately), tie behavior, the
±150bp perturbation check as a mandatory robustness line.

## Ledger binding-format entry
- id: R2-10 (EXPANDED — this draft IS the mechanical definition R2-10 required;
  dependency on R2-12 recorded)
- observation: R5 computes per-strike IV offline; no rank definition exists, and the
  6.5% rate is uncalibrated — raw IV levels are not trustworthy as absolutes.
- mechanical rule: percentile-rank per the frozen reference set above.
- parameters-to-freeze: as listed.
- exam design: none standalone — D4 is a DEFINITION feeding D3(b)/R2-17; its
  robustness line (rate-perturbation re-rank stability) rides inside that exam.
- what-would-kill-it: rank instability under the ±150bp perturbation (wing reorder
  rate above a pre-frozen tolerance) => IV-rank unusable until R2-12 lands.
