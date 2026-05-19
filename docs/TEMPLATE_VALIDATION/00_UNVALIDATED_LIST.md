# Queue Y — Phase 1: Unvalidated Templates List

**Generated:** 2026-05-19, on branch `chore/template-validation-sprint`
**Working tree base:** `feat/backtest-engine-day-7` (= Day 6 + engine version module)

## How the unvalidated set was derived

Active-template sets across the relevant refs (all data from `backend/data/strategy_templates_seed.json`):

| Ref | Total templates | Active |
|-----|-----------------|--------|
| `ef53486` (May 17 18:18 IST — original Phase 1 foundation) | 113 | 15 |
| `2b32e8e` (May 18 21:31 IST — post-batch-activate + 16 deactivations) | 113 | 29 |
| `origin/main` (current) | 113 | 29 |
| `origin/feat/backtest-engine-day-6` (this branch's base) | 113 | 15 |

The May-17-night batch added ~30 activation commits between `ef53486` and `2b32e8e`. The follow-up `2b32e8e` deactivated 16 templates flagged unsafe.

## Mission arithmetic vs actual count

The mission predicted **14 unvalidated** from `29 - 15 = 14`. Actual count is **17** — three of the 16 deactivations were Phase 1 templates (not batch-activated), so subtracting the full 16 over-counts:

- **Phase 1 templates removed by deactivation** (3): `banknifty-weekly-equity`, `pdh-pdl-breakout`, `premarket-gap`
- Net Phase 1 still active in `origin/main`: 15 − 3 = **12**
- Net batch-activated still active: 30 − 13 (the batch portion of the 16 deactivations) = **17**
- Sanity check: 12 + 17 = 29 ✅

## The 17 unvalidated, still-active, batch-added templates

| # | Slug | Category | Indicators (per seed) |
|---|------|----------|----------------------|
| 1 | `adx-strong-trend-filter` | Trend Following | adx_14 |
| 2 | `aroon-crossover` | Trend Following | aroon_14 |
| 3 | `camarilla-pivots-intraday` | Intraday | (pivot calc) |
| 4 | `cci-momentum` | Momentum | cci_20 |
| 5 | `cmf-confirmation` | Volume Profile | cmf_20 |
| 6 | `doji-reversal` | Pattern Recognition | (candle pattern) |
| 7 | `donchian-channel-breakout` | Breakout | donchian_channel_20, donchian_channel_10, adx_14 |
| 8 | `engulfing-candle-reversal` | Pattern Recognition | (candle pattern) |
| 9 | `hull-ma-trend` | Trend Following | hull_ma_20 |
| 10 | `ichimoku-cloud-crossover` | Trend Following | ichimoku |
| 11 | `inside-bar-breakout` | Pattern Recognition | (candle pattern) |
| 12 | `macd-divergence` | Momentum | macd |
| 13 | `mfi-overbought-oversold` | Mean Reversion | mfi_14 |
| 14 | `obv-divergence` | Volume Profile | obv |
| 15 | `rsi-divergence` | Mean Reversion | rsi_14 |
| 16 | `triple-ema-crossover` | Trend Following | ema_5, ema_13, ema_34 |
| 17 | `williams-pct-r-reversal` | Mean Reversion | williams_r_14 |

## What stopped the validation sprint

**STRUCTURAL BLOCKER discovered during Phase 2 setup** — see
[`STRUCTURAL_BLOCKER.md`](STRUCTURAL_BLOCKER.md). The templates'
`config_json` is documentation-shape (string-condition prose like
`"close > 20-bar donchian upper band (new 20-bar high) AND adx_14 > 20"`),
NOT engine-callable `StrategyJSON`. The backtest engine cannot consume
templates as-is — a translator layer (slated for Phase 7/8 per
`clone_service.py`'s own docstring) does not yet exist.

This affects ALL 113 templates, not just the 17 unvalidated. Even the 12
"original Phase 1 active" templates share the same shape and were not
validated by backtest — they're docs/UI placeholders.

Phases 2–4 of Queue Y are STOPPED until the translator ships.
