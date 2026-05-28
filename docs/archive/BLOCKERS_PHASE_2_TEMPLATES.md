# BLOCKERS — Phase 2 Template Configs

**Date:** 2026-05-17 (overnight queue Task 2 of 5)
**Branch:** `feat/phase-2-template-configs`

---

## Open questions for founder review

### 1. Indicator naming convention drift (cross-system)

The Phase 1 active templates (`backend/data/strategy_templates_seed.json`) use informal indicator names in their `indicators_used` field:

```
psar           bb_20_2          stochastic_14_3_3        rsi_14
ema_9          orb_15           williams_pct_r           macd_12_26_9
```

The Phase 2 proposals on this branch use the **strategy_engine canonical names** (verified via `ls backend/app/strategy_engine/indicators/calculations/`):

```
parabolic_sar  bollinger_bands  stochastic               williams_r
ema            (no orb)         (no _suffix variants)    cci
```

Recommendation: **unified naming sprint** — pick one convention (probably the strategy_engine canonical names, since those map to actual calculation file names) and rewrite Phase 1 active configs to match. The Phase 2 proposal on this branch is **already in the canonical style**, so merging it as-is creates a mixed namespace until Phase 1 is also normalised.

**Decision needed**: rename Phase 1 configs now (pre-Phase-2-merge) or post-merge?

### 2. Heikin-Ashi templates skipped — confirm

Two Heikin-Ashi templates in the inactive pool (`heikin-ashi-trend`, `heikin-ashi-smooth-trend`) were skipped because the strategy_engine catalog has NO `heikin_ashi.py` (verified via `ls` — top candidates are `hammer.py`, `harami_bearish.py`, `harami_bullish.py`, but no Heikin-Ashi candle transform). 

Heikin-Ashi requires a candle-input transform, not a per-bar indicator. **Question**: defer until Heikin-Ashi support lands in strategy_engine (Phase 3+), or commission its addition first?

### 3. Other "needs new indicator" candidates

These inactive equity templates couldn't be Phase 2-promoted because their indicators aren't shipped:

| Slug | Missing indicator |
|---|---|
| `fibonacci-retracement-entry` | Swing-point detection (no `swing.py` in calculations/) |
| `range-trading-sr` | Support/resistance detection (no `support_resistance.py`) |
| `renko-trend` | Renko bar transform (no `renko.py`) |
| `inside-bar-breakout` | Inside-bar pattern detection (no `inside_bar.py`) |
| `obv-divergence`, `rsi-divergence`, `macd-divergence` | Divergence-detection logic — non-trivial; multiple peaks/troughs |
| `squeeze-momentum` | LazyBear squeeze (compound indicator; no `squeeze_momentum.py`) |
| `pivot-reversal-strategy` | Swing pivot detection (no `pivot_swing.py`) |

These represent "indicator gaps" — separate Phase 3 work item to commission the missing calculations.

### 4. Stop-loss / take-profit defaults are conservative

All 15 proposals use SL between 0.8% and 2.0% and TP between 1.6% and 6%. These are **retail-friendly conservative defaults**, NOT optimised values. The actual right values per strategy come out of backtest engine validation (Phase F C4 work, see `BLOCKERS_BACKTEST_ENGINE.md`).

**Recommendation:** do NOT promote any of these 15 to `is_active=true` until the backtest engine validates each on at least 6 months of historical data and surfaces the actual best SL/TP envelope.

### 5. Conditional expression vocabulary drift

The Phase 2 proposals use expression strings like:
- `parabolic_sar flips below close (bullish flip)`
- `volume > avg_volume_20 * 2`
- `stochastic_k crosses above stochastic_d AND stochastic_k < 20`
- `bullish_engulfing == 1`
- `bars_in_trade >= 10`

The Phase 1 active templates use the same general shape but with informal indicator names. The condition_evaluator (Phase F C4 skeleton) will need to parse this vocabulary. **Question**: is there a written spec for the boolean-expression grammar, or does each engine implementation invent its own parser? If the latter, this is a Phase F C4 spec ambiguity that propagates here.

### 6. `trend == down` and `trend == up` shorthand

Two pattern templates (`hammer-hanging-man-pattern`, `doji-reversal`) reference `trend == down` / `trend == up` as condition prerequisites. This is shorthand for "we're in a downtrend at the moment of pattern formation" — but there's no `trend` field on a bar.

**Resolution:** the condition_evaluator should expose a derived `trend` variable from a short-period EMA slope (e.g., EMA20 slope sign over last 10 bars). Either:
(a) ship a `trend` derived indicator in strategy_engine.indicators
(b) inline the condition as `ema_20 slope < 0 for last 5 bars`
(c) the condition_evaluator implicitly resolves `trend` via convention

Recommendation: (a) — adds a `trend.py` indicator that returns "up" / "down" / "sideways" categorically. Phase 3 indicator commission.

### 7. `bars_in_trade` and `previous_close` / `previous_high` references

Several conditions reference per-position state (`bars_in_trade`, `entry_price`) or per-bar lookback (`previous_close`, `previous_high`, `next_close`). These aren't indicators — they're **runtime context the condition_evaluator must expose** to the parsed boolean expressions.

**Spec ask**: the condition_evaluator's setup() method should pre-bind a context object including:
- `bars_in_trade` (int, since-entry bar count, 0 outside trade)
- `entry_price` (float, current position entry price, None outside trade)
- `previous_close`, `previous_high`, `previous_low` (1-bar lookback)
- `next_close` (one bar ahead — only valid when the evaluator is processing a confirmation-bar logic)

This belongs in Phase F C4's `condition_evaluator.py` Protocol. The skeleton on `feat/backtest-engine-spec` doesn't enumerate these — surfaced for that team to fold in.

---

## What this branch ships

```
docs/PHASE_2_TEMPLATE_CONFIGS.md                       ~250 lines
backend/data/phase_2_template_configs.json             15 proposals
BLOCKERS_PHASE_2_TEMPLATES.md                          this file
```

NOT touched: `backend/data/strategy_templates_seed.json` (live seed). NOT modified: any existing source file. NO migration. NO indicator implementations added.

## What needs to happen post-review

1. **Founder reviews each of the 15 configs** — math + SL/TP + condition vocabulary
2. **Indicator-naming-unification decision** (Q1 above) — rename Phase 1 or Phase 2?
3. **Heikin-Ashi decision** (Q2) — defer or commission?
4. **Trend-shorthand decision** (Q6) — pick (a)/(b)/(c) for the `trend == X` syntax
5. **Backtest engine spec finalisation** — Q5 + Q7 belong in `BLOCKERS_BACKTEST_ENGINE.md`'s open-questions list
6. **Merge approved configs into `strategy_templates_seed.json`** + re-run seed loader on EC2
