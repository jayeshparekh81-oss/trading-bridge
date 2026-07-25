# HYPOTHESIS LEDGER — orderflow_engine (Round-2 / Round-3 exam roster)

The queue of ideas to test AFTER the frozen Round-1 OOS window (07-23..08-12, see
[TAPE_NOTES.md](TAPE_NOTES.md) "OOS EVALUATION WINDOW — FROZEN 2026-07-22"). This is a
roster, not a result: it records what to examine and under what preconditions.

**Header rule (binding):** every entry requires **fresh pre-registration on blind data**
before any live change. In-sample exploration NEVER earns a seat by itself — a hypothesis
generated or tuned on already-seen days must still be frozen and re-tested on days it has
not touched. Status `shadow-recording` means the value is being captured live (weight 0,
inert) for LATER analysis; it does not imply the feature is live or endorsed.

| id | hypothesis | origin | status | prerequisites | notes |
|----|-----------|--------|--------|---------------|-------|
| R2-01 | big_print revival (percentile mode + pre-registered threshold) | O-audit: fixed-mode threshold 0 → INERT | queued-R2 | tape-events path built; a frozen percentile + notional threshold | physically post-window (changes the tape-events firing path) |
| R2-02 | queue_imbalance ON (weight > 0) | O1 audit + qi-shadow wiring | shadow-recording since 24-Jul pipeline | pre-registered weight + a blind ranking test | value recorded inert (weight 0) since the qi-shadow merge; 24-Jul probe: inside null both instruments |
| R2-03 | pain_map revival (weight > 0) | O1 audit + painmap-shadow wiring | shadow-recording since 24-Jul pipeline | pre-registered weight + blind test | buildup_matrix now wired to ctx, recorded inert (weight 0); qi/pain_map shadow store recording began post-rebuild (07-24 backfilled offline; 24-Jul pipeline ran pre-rebuild image 40584); 24-Jul probe: NIFTY -0.212 @0.1st INVERSE, BANKNIFTY sign-flip — contra-use would be a new pre-reg; fuel term never populated (first-grid ltp=None gap, engine.py:209) — probe finding = max-pain-side only; fuel fix is a prerequisite for any real pain_map exam |
| R2-04 | regime OI-bias wiring (live OI → participant bias) | O1 audit: participant_oi_bias is a static config string | queued-R2 | pre-registration; note it changes regime_direction + the ±10 penalty | STRATEGY change — out of bounds during the window |
| R2-05 | ATR-adaptive threshold | tuning idea | queued-R2 | pre-registered adaptation rule | tuning knob |
| R2-06 | book-toxicity veto (spread-variance) | microstructure idea | queued-R2 | NEW capture plumbing (per-bar spread series) | depth days only |
| R2-07 | absorption veto @ 2× | veto exploration | queued-R2 | pre-registered 2× rule | 3× variant near-inert in-sample (2/367 fires) |
| R2-08 | structure-based regime (mechanical BOS/CHoCH swing tracker) | discretionary-structure idea | queued-R2 | MUST be frozen mechanically BEFORE any data | no discretionary swing labels — a deterministic tracker or it is untestable |
| R2-09 | FVG bar feature | price-action idea | queued-R2 | frozen FVG definition | minor |
| R2-10 | IV-rank filter — DEFINITION SEALED in D4 (docs/designs/D4): REF-B own-strike trailing H=5 sessions; wing-reorder kill tolerance 10% of adjacent pairs under +/-150bp | chain analytics + D4 design | queued-R2 (definition frozen) | iv_history store; rate-perturbation robustness line rides in R2-17; depends R2-12 | REF-A rejected (smile collapse toward ATM); 6.5% rate uncalibrated — ranks partially invariant, stated in D4 |
| R2-11 | IV-aware strike selection | execution idea | SUPERSEDED by R2-17 (D3) | — | folded into the option execution exam's value-cheap variant |
| R2-12 | risk-free-rate calibration (6.5% uncalibrated) | O-audit: chain.risk_free_rate functional/uncalibrated | queued-R2 | a calibration source | quality — affects IV/greeks accuracy, not a strategy edge by itself |
| R2-13 | volume / tick-bar sweep 100/200/300/500/1000 | pre-registered (TAPE_NOTES ~1099/1105) | pre-registered | walk-forward harness + plateau/DSR (multiple-comparison burden) | already pre-registered; runs post-window with the paid N-trials discount |
| R2-14 | dynamic-sleeper + momentum-death variants | exit-lifecycle idea | queued-R2 | frozen variant set | minor |
| R2-15 | bar-scaled sleeper / exit-granularity variant (sleeper in bars, not wall-clock minutes) | s1000 degeneracy finding (2026-07-24 sweep: median bar 39-52min vs 60-min sleeper) | queued-R2 | mechanical definition frozen BEFORE any test | |
| R2-16 | cross-asset flow confirm (futures<->options M-of-4 agreement CONFIRM/VETO overlay) | D2 design (docs/designs/D2, sealed pre-Market-DNA) | queued-R2 | freeze M/W/K + vote defs + tie rule; R2-03 fuel fix for the buildup vote; host = ALL fired candidates of frozen baseline | max-pain vote retained despite R2-03 prior-against — bundle exam adjudicates; NEG-01 cost-mechanics null mandatory |
| R2-17 | option execution exam — frozen signals re-priced on recorded ATM+/-20 premiums, buy-only CE/PE, variants ATM vs frozen value-cheap selector (supersedes R2-11) | D3 design (docs/designs/D3, sealed) | queued-R2 | D4 IV-rank frozen; OPTION-specific frozen cost schedule (STT 0.15% sell-side premium, Budget 2026; statutory rates re-pinned at pre-reg date); pre-registered signal set | lottery-premium trap named: Rs-cheap != value-cheap; decides options-viable vs theta/spread-eaten |
| R2-18 | ASLI-BREAK METER v0 — ORH/ORL continuation-vs-failure fork, 4 PHYSICS-CLEAN gates (unsigned P5 efficiency+hold, P6 walls/refill, P7 LAR-veto K=sweep_to_absorption_bars=10, hygiene) | D5 design (docs/designs/D5, DESIGN FROZEN PRE-MARKET-DNA) | queued-R2 | final values re-frozen at Round-2 pre-reg; Market-DNA base-rate decides FOLLOW vs FADE seat | qi/pain_map/delta-veto EXCLUDED with citations; exits frozen -1R/+1.5R futures-priced; NEG-01 null mandatory; 25-Jul exploration (feat/orderflow-d5-explore @ 088165f): 88 episodes / 4 trades — gates showed no selection vs base rate at N=4 — no conclusion; base rate ~73% stop-first at -1R/+1.5R (mean-revert corroboration #3); BINDING for any Round-2 exam using level-anchored R-units: the R-unit must be sealed WITH a stability floor (C-note-4 pattern, min_stop_atr analogue; exact floor value sealed at pre-registration, not now) |
| R2-19 | VWAP-stretch reversion (bucket-2/3 only; trigger |d|>P-th same-bucket trailing pctile per P2 boundaries; toward-VWAP; VWAP-touch target / S x stretch fixed stop / 30-min max-hold; re-entry reset; sequential de-dup judged) | Market-DNA M4 12/12-day negative rho, CIs exclude 0 (ba7b0e0); design sealed pre-exam (docs/designs/VWAP_REVERSION_DESIGN.md) | queued-R2 | freeze P/S/max-hold/bucket set/5-session reference window/re-entry rule/5-min bar spec | PHYSICS-CLEAN family only; breakeven WR ~65% at 1:1 with ~0.29R cost (arithmetic bar); exam adds shuffled-entry-time null + NEG-01 null |
| NEG-01 | band veto K=1 SD | veto exploration | **NEGATIVE (in-sample)** | — | 23-Jul null check, 1000 draws seed 20260723 — net at 9.6th pctile of the random-removal null on NIFTY (anti-selective), 59.5th on BANKNIFTY (inside body); pure cost mechanics; DROPPED as a Round-2 selection candidate, retained as a documented negative |
| R3-01 | de Prado-style ML on recorded features via the existing harness | research-lane | queued-R3 | 60+ sessions (~Oct) + purge/embargo/DSR discipline | |
| R3-02 | Nightly Analyst ritual — DESIGN SEALED in D1 (docs/designs/D1): 3-section observations-only diary, <=3 proposals/night in binding format, founder-gated | process idea + D1 design | queued-post-window (ACTIVATION: first run AFTER the 12-Aug window eval) | run-time/inputs/diary-format/quota frozen per D1 | binding exam metric = SURVIVAL rate vs random-proposal null (admission rate descriptive only — founder-gated => circular); live-LLM stays excluded |
| R3-03 | LAR full-resolution ranking | LAR study | queued-R3 | 60+ sessions | |

## AUDIT NOTES — Phase 1(C) (Machine Health Card, 2026-07-25; descriptive, burned days)
- C-note-1 (R2-15/R2-14 context): sleeper leg unused at size-100 (0/14 cached exits;
  median hold 3-9 min vs 60-min sleeper) — bar-scaled sleeper is a large-size concern
  only; exit-variant exams should treat sleeper as inert at baseline size.
- C-note-2 (R2-14 input): trail giveback structure — winners book +0.5..+1.0R against
  bar-path MFE median ~2.5R (burned days, bar-approx, descriptive). Path-MFE is not
  capturable by construction (clairvoyance); informs R2-14 exit variants only — no
  promise of capture.
- C-note-3 (standing-reframe corroboration): ~50% of fires end at the hard stop in
  BOTH families; positive mass sits in the top-2 fires per set.
- C-note-4 (BINDING REQUIREMENT): stop fills are modeled at stop+2 ticks, but size-100
  stops resolve inside one ~4.7-min tick-bar whose 1-min path shows -1.2..-4R
  excursion — flat-slip is optimistic on sweep bars. Round-2 EXIT-FAMILY EXAMS MUST
  CARRY A STOP-SLIP STRESS VARIANT (existing slippage_multiplier knob covers the
  mechanics). Path excursion = UPPER BOUND on fill damage, not expected fill; the
  stress variant spans flat-slip -> excursion-scaled slip.
