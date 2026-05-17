# Phase 2 Template Configs — design rationale

**Status:** Proposal. Pending founder review before merging into the live seed.
**Branch:** `feat/phase-2-template-configs`
**Date:** 2026-05-17

## What this delivers

Proposes `config_json` for **15 of the 35 cataloged-but-inactive equity templates** from `backend/data/strategy_templates_seed.json`. Each picked entry was selected per the Task 2 priority order:

1. Strategy popularity in Indian retail
2. Beginner/intermediate complexity (skipped expert)
3. Coverage diversity across categories
4. Existing indicator support (verified against `backend/app/strategy_engine/indicators/calculations/`)

Selected 15:

| # | Slug | Category | Complexity | Why picked |
|---:|---|---|---|---|
| 1 | `parabolic-sar-reversal` | Trend Following | beginner | PSAR is a top-5 indicator on TradingView India dashboards; simple flip-driven entries |
| 2 | `stochastic-oscillator` | Mean Reversion | beginner | Classic %K/%D crossover — taught in every Indian options-trading course |
| 3 | `engulfing-candle-reversal` | Pattern Recognition | beginner | Bullish/bearish engulfing is the #1 price-action pattern in Indian retail education |
| 4 | `hammer-hanging-man-pattern` | Pattern Recognition | beginner | Hammer at support / hanging man at resistance — visual + simple |
| 5 | `doji-reversal` | Pattern Recognition | beginner | Doji indecision + confirmation bar — common entry pattern |
| 6 | `donchian-channel-breakout` | Breakout | intermediate | Turtle-trader style 20-period high/low; diversifies away from BB-only breakouts |
| 7 | `triple-ema-crossover` | Trend Following | intermediate | EMA ribbon (5/20/50) — popular variant with stronger filtering than 9/21 |
| 8 | `adx-strong-trend-filter` | Trend Following | intermediate | ADX > 25 filter is the canonical trend-strength gate; pairs with EMA20 direction |
| 9 | `williams-pct-r-reversal` | Mean Reversion | intermediate | Williams %R extremes at -80/-20 — RSI cousin, popular for intraday |
| 10 | `cci-momentum` | Momentum | intermediate | CCI ±100 momentum entries — diversifies away from RSI/MACD-only momentum |
| 11 | `pivot-point-bounce` | Mean Reversion | intermediate | Standard pivot R1/R2/S1/S2 bounce — the bread-and-butter of Indian intraday traders |
| 12 | `bollinger-pct-b-extreme` | Mean Reversion | intermediate | %B < 0 or > 1 extremes — narrower than band-touch mean reversion |
| 13 | `chandelier-exit-trail` | Trend Following | intermediate | ATR-based trailing stop wrapped around an EMA20 entry; teaches dynamic exits |
| 14 | `volume-spike-price-confirm` | Volume Profile | intermediate | Above-2x-avg volume bar + directional close — diversifies into volume signals |
| 15 | `mfi-overbought-oversold` | Mean Reversion | intermediate | Money Flow Index 80/20 — volume-weighted RSI, complements the plain-RSI active template |

Category coverage across Phase 1 active + Phase 2 proposed:

| Category | Phase 1 active | Phase 2 proposed | Combined |
|---|---:|---:|---:|
| Trend Following | 2 | 4 | 6 |
| Mean Reversion | 4 | 5 | 9 |
| Breakout | 3 | 1 | 4 |
| Momentum | 3 | 1 | 4 |
| Event-Driven | 2 | 0 | 2 |
| Pattern Recognition | 0 | 3 | 3 |
| Volume Profile | 0 | 1 | 1 |

Phase 2 specifically backfills Pattern Recognition + Volume Profile (zero coverage in Phase 1) and broadens Trend Following + Mean Reversion. Event-Driven stays Phase 1-only because the inactive set has no Event-Driven candidates worth surfacing yet.

## NOT picked (and why)

| Slug | Reason skipped |
|---|---|
| heikin-ashi-trend, heikin-ashi-smooth-trend | Both depend on a Heikin-Ashi candle transform indicator that may not exist as a first-class indicator in `strategy_engine.indicators.calculations/` (no obvious matching .py file). Flagged in BLOCKERS for Lokesh/Jayesh confirmation before adding. |
| keltner-channel-bounce | Keltner less popular than BB in Indian retail; lower priority |
| ichimoku-cloud-crossover | Advanced — skipped per complexity rule |
| aroon-crossover | Aroon is niche in India; defer to Phase 3 |
| psar-ema-combo | Redundant with the simpler `parabolic-sar-reversal` |
| camarilla-pivots-intraday | Advanced + Camarilla is a specialised pivot variant; defer |
| fibonacci-retracement-entry | Requires swing-high/low detection which needs a separate "swing point" calculation that may not exist yet — non-trivial |
| renko-trend | Advanced + Renko requires non-time-bar transform |
| range-trading-sr | Requires Support/Resistance detection logic, also non-trivial |
| inside-bar-breakout | Minor variant of price action; lower retail-popularity than engulfing/hammer |
| obv-divergence, rsi-divergence, macd-divergence | All advanced + divergence-detection logic is non-trivial |
| cmf-confirmation | CMF less popular than MFI; mfi-overbought-oversold covers the volume-weighted oscillator slot |
| squeeze-momentum | Advanced |
| hull-ma-trend, alma-slope | Less popular than EMA in India |
| kama-adaptive-trend | Advanced |
| pivot-reversal-strategy | Redundant with `pivot-point-bounce` |

20 remaining inactive equity slugs go in a Phase 3 batch.

## Config shape

Every config matches the Phase 1 validator schema (`backend/app/templates/validator.py`):

```jsonc
{
  "indicators": ["..."],
  "entry_long":  { "condition": "..." },
  "entry_short": { "condition": "..." },    // optional, paired with exit_short
  "exit_long":   { "condition": "..." },
  "exit_short":  { "condition": "..." },
  "stop_loss_pct": 1.5,
  "take_profit_pct": 3.0,
  "position_sizing": { "method": "fixed_amount", "amount_inr": 50000 },
  "max_open_positions": 1,
  "trading_hours": { "start": "09:15", "end": "15:15" }
}
```

Each proposed config sits in `backend/data/phase_2_template_configs.json` as
`{slug: <slug>, config_json: {…}}` entries. The file is purely a proposal —
the actual seed loader runs against `strategy_templates_seed.json`, which is
unchanged on this branch. Jayesh reviews + decides which proposals to merge.

## Indicator naming convention drift (flagged in BLOCKERS)

Phase 1 seed used informal names like `psar`, `stochastic_14_3_3`, `williams_pct_r` while the strategy_engine catalog uses `parabolic_sar`, `stochastic`, `williams_r`. The Phase 2 configs in this proposal use the **strategy_engine canonical names** (verified via `ls calculations/`). This will become a mismatch with the Phase 1 active templates' `indicators_used` field — surfaced in BLOCKERS for a unified-naming sprint.

## What needs to happen post-review

1. Founder reviews each of the 15 configs (math + tuning parameters)
2. Picks N (≤15) to promote to active
3. Re-runs seed loader: `python -m app.templates.scripts.seed_strategy_templates` with the updated `strategy_templates_seed.json` (after merging the chosen configs in)
4. Optionally: backtest engine validates each before activation (Phase F C4 work — see `BLOCKERS_BACKTEST_ENGINE.md`)

## Risk envelope

These configs are **starting points, not optimised parameters**. Stop-loss and take-profit values are conservative defaults (mostly 1.5% SL / 3% TP) chosen for retail-friendly risk envelopes, not back-tested. Backtest engine work (Phase F C4) will surface which configs need parameter tuning.

NO config will go to active without backtest validation in the final flow. The seed `is_active=true` switch should be a deliberate per-config decision after backtest review, not a batch flip.
