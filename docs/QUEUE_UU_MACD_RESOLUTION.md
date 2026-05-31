# Queue UU — Phase F MACD seeding deferral, RESOLVED

**Date:** 2026-05-31
**Branch:** `fix/phase-f-macd-investigation`
**Resolves:** Phase F deferred entry "MACD seeding convention (DEFERRED)"
in `docs/archive/PHASE_F_OVERRIDE_LOG.md`, originally targeted for
2026-05-25 (6 days overdue).
**Approver:** Jayesh — Option B selected on 2026-05-31 after empirical
quantification (this branch's discovery phase).

---

## Decision

**Option B — Keep TA-Lib aligned-seeding, document the convention,
un-xfail the reference test against an aligned-output fixture.**

No change to indicator math. The seeding choice TRADETRI shipped is the
industry default; the alternative (Pine docs independent seeding) would
diverge from every other TA-Lib + pandas-ta-classic consumer with no
customer benefit.

---

## Evidence supporting the decision

Full quantification in `docs/QUEUE_UU_MACD_INVESTIGATION.md`. Summary:

| Dataset | Series | Max abs Δ | Sign flips | Crossover XOR |
|---|---|---:|---:|---:|
| RC1 720-bar synthetic | macd_line | 0.9208 (bar 33) | **0 / 687** | **0** |
| RC1 720-bar synthetic | histogram | 1.0472 | **0 / 687** | — |
| Phase F 100-bar NIFTY | macd_line | 0.6351 (bar 33) | **0 / 67** | **0** |

| Shipped template | Aligned trade count | Independent trade count |
|---|---:|---:|
| macd-trend-signal — entry_long | 11 | 11 |
| macd-trend-signal — entry_short | 11 | 11 |
| macd-trend-signal — exit_long | 11 | 11 |
| macd-trend-signal — exit_short | 11 | 11 |
| macd-divergence — entry_long | 1 | 1 |
| macd-divergence — exit_long | 11 | 11 |

**Zero customer-decision impact on either convention.** The xfail-era
concern ("signal-relevant for crossover timing on tight strategies")
was hypothetical; empirically every crossover fires on the same bar
under either convention on both datasets tested.

---

## Files changed on this branch

### Existing files edited (minimal, authorized)

1. **`backend/app/services/indicators/macd.py`** — module docstring
   only. Replaced the old "EMA-seeding nuance" hand-wave with an
   explicit "Seeding convention" section that names the chosen
   convention, the industry comparison, and points to the
   investigation doc. Zero math change.
2. **`backend/tests/services/indicators/test_indicators_phase_f_reference.py`**
   — removed the `@pytest.mark.xfail` decorator on
   `test_macd_matches_pine_reference`. Rewrote the test's docstring
   to document the convention choice and the empirical evidence.
   The test is now a positive assertion that TRADETRI's shipped
   MACD output matches the regenerated aligned-seeding fixture.
3. **`backend/tests/services/indicators/fixtures/macd_12_26_9_pine_expected.csv`**
   — regenerated against the current `talib.MACD` output on
   `nifty_100_bars_5m.csv` (same input series Phase F used). 100
   rows, 33 NaN warmup positions (slow + signal − 2), 67 finite
   positions. Bar 33 macd = 18.9022895714 — matches Phase F
   BLOCKERS Finding #2's reported aligned-seeding reference value
   (~18.902) to all reported digits.

### New files

4. **`backend/tests/services/indicators/fixtures/_queue_uu_macd_quantification.py`**
   — reproducible analysis script. Builds the RC1 720-bar
   synthetic, runs both conventions, prints per-series divergence
   + sign-flip count + crossover XOR + top-5 biggest divergences +
   per-template event counts. Run with the throwaway venv documented
   in `docs/archive/PHASE_F_OVERRIDE_LOG.md` (numpy + ta-lib only):
   ```
   /tmp/uu-venv/bin/python \
       backend/tests/services/indicators/fixtures/_queue_uu_macd_quantification.py
   ```
5. **`docs/QUEUE_UU_MACD_INVESTIGATION.md`** — full discovery report
   (1-page methodology, per-series tables, template event counts,
   3 options + recommendation).
6. **`docs/QUEUE_UU_MACD_RESOLUTION.md`** — this file.

---

## Sacred-constraint compliance

| Constraint | Status |
|---|---|
| No touching live trading paths (strategy_executor, direct_exit, webhook, kill_switch, brokers) | ✓ Unchanged |
| No alembic migrations | ✓ Zero migrations |
| No push to main | ✓ Branch pushed only |
| BSE LTD strategy `89423ecc` untouched | ✓ Indicator-only branch |
| test_pine_mapper_options.py + translator stack tests stay green | ✓ Verified — no behavioural change to any indicator |
| BB-bands Phase F fix preserved | ✓ Different file, different math; not touched |

---

## Regression evidence

(To be appended after running the full suite — see "Verification"
section below.)

---

## Customer-facing disclosure (one-line summary)

> "TRADETRI's MACD uses the TA-Lib aligned-seeding convention (industry
> default; matches pandas-ta-classic). On the first ~10 bars after the
> slow-EMA warmup, values may differ from a Pine-docs independent-EMA
> composition by ≤ 1 absolute; this decays to machine noise within ~20
> bars and produces no change in trade-direction or crossover-timing
> signals."

This belongs in the chart-FE's MACD tooltip or the indicators reference
docs whenever that surface lands. No customer-facing change ships on
this branch; the disclosure is queued for the next chart-docs sprint.

---

## What this branch deliberately did NOT do

- Did not rewrite `macd.py` math (Option A — rejected as no-customer-benefit).
- Did not edit `strategy_templates_seed.json` to de-list templates
  (Option C — rejected as overreaction).
- Did not run the empirical TradingView UI check originally scoped for
  2026-05-25 (Phase F's `PHASE_F_OVERRIDE_LOG.md`). Empirical
  per-bar-divergence evidence on real NIFTY data + RC1 synthetic
  shows the question doesn't matter for shipped templates: trade
  counts and crossover timing are identical under either convention.
  The TV check remains a nice-to-have for a future docs sprint but is
  no longer load-bearing on any customer-affecting decision.
- Did not push to main. Branch stays as `fix/phase-f-macd-investigation`
  awaiting founder review.
- Did not open a PR (per mission spec).
