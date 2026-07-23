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
| R2-02 | queue_imbalance ON (weight > 0) | O1 audit + qi-shadow wiring | shadow-recording since 24-Jul pipeline | pre-registered weight + a blind ranking test | value recorded inert (weight 0) since the qi-shadow merge |
| R2-03 | pain_map revival (weight > 0) | O1 audit + painmap-shadow wiring | shadow-recording since 24-Jul pipeline | pre-registered weight + blind test | buildup_matrix now wired to ctx, recorded inert (weight 0) |
| R2-04 | regime OI-bias wiring (live OI → participant bias) | O1 audit: participant_oi_bias is a static config string | queued-R2 | pre-registration; note it changes regime_direction + the ±10 penalty | STRATEGY change — out of bounds during the window |
| R2-05 | ATR-adaptive threshold | tuning idea | queued-R2 | pre-registered adaptation rule | tuning knob |
| R2-06 | book-toxicity veto (spread-variance) | microstructure idea | queued-R2 | NEW capture plumbing (per-bar spread series) | depth days only |
| R2-07 | absorption veto @ 2× | veto exploration | queued-R2 | pre-registered 2× rule | 3× variant near-inert in-sample (2/367 fires) |
| R2-08 | structure-based regime (mechanical BOS/CHoCH swing tracker) | discretionary-structure idea | queued-R2 | MUST be frozen mechanically BEFORE any data | no discretionary swing labels — a deterministic tracker or it is untestable |
| R2-09 | FVG bar feature | price-action idea | queued-R2 | frozen FVG definition | minor |
| R2-10 | IV-rank filter | chain analytics | queued-R2 | IV history (iv_history.py) + a frozen rank rule | |
| R2-11 | IV-aware strike selection | execution idea | queued-R2 | frozen selection rule | execution layer |
| R2-12 | risk-free-rate calibration (6.5% uncalibrated) | O-audit: chain.risk_free_rate functional/uncalibrated | queued-R2 | a calibration source | quality — affects IV/greeks accuracy, not a strategy edge by itself |
| R2-13 | volume / tick-bar sweep 100/200/300/500/1000 | pre-registered (TAPE_NOTES ~1099/1105) | pre-registered | walk-forward harness + plateau/DSR (multiple-comparison burden) | already pre-registered; runs post-window with the paid N-trials discount |
| R2-14 | dynamic-sleeper + momentum-death variants | exit-lifecycle idea | queued-R2 | frozen variant set | minor |
| NEG-01 | band veto K=1 SD | veto exploration | **NEGATIVE (in-sample)** | — | 23-Jul null check, 1000 draws seed 20260723 — net at 9.6th pctile of the random-removal null on NIFTY (anti-selective), 59.5th on BANKNIFTY (inside body); pure cost mechanics; DROPPED as a Round-2 selection candidate, retained as a documented negative |
| R3-01 | de Prado-style ML on recorded features via the existing harness | research-lane | queued-R3 | 60+ sessions (~Oct) + purge/embargo/DSR discipline | |
| R3-02 | Nightly Analyst ritual (post-close feature journal → ledger) | process idea | queued-post-window | a repeatable post-close routine | feeds this ledger |
| R3-03 | LAR full-resolution ranking | LAR study | queued-R3 | 60+ sessions | |
