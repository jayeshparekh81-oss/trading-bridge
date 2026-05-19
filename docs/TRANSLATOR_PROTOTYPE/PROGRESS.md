# Queue BB — Translator Prototype: PROGRESS

Per-template translation outcome on the **29 currently-active** seed templates,
using the parser built in `backend/app/strategy_engine/translator/`.

Synthetic backtest harness: 720 5-min bars (IST trading window, 10 days),
sine-wave NIFTY-like prices that produce 5-10 clean crossovers per indicator pair.

| # | Slug | Verdict | Trades | Return % | Detail / next step |
|---|------|---------|--------|----------|---------------------|
| 1 | `aroon-crossover` | **PASS** | 10 | 2.79 | engine ran cleanly |
| 2 | `cci-momentum` | **PASS** | 17 | 2.39 | engine ran cleanly |
| 3 | `cmf-confirmation` | **PASS** | 10 | -0.46 | engine ran cleanly |
| 4 | `ema-crossover-20-50` | **PASS** | 11 | -1.71 | engine ran cleanly |
| 5 | `ema-crossover-9-21` | **PASS** | 11 | 1.36 | engine ran cleanly |
| 6 | `mfi-overbought-oversold` | **PASS** | 108 | 3.24 | engine ran cleanly |
| 7 | `rsi-oversold-bounce` | **PASS** | 328 | 3.59 | engine ran cleanly |
| 8 | `williams-pct-r-reversal` | **PASS** | 83 | 2.94 | engine ran cleanly |
| 9 | `bb-rsi-oversold` | **FAIL_VALIDATION** | — | — | ValidationError: 1 validation error for StrategyJSON   Value error, Co |
| 10 | `macd-trend-signal` | **FAIL_VALIDATION** | — | — | ValidationError: 1 validation error for StrategyJSON   Value error, Co |
| 11 | `orb-15min` | **FAIL_VALIDATION** | — | — | ValidationError: 1 validation error for StrategyJSON   Value error, Co |
| 12 | `rsi-macd-confluence` | **FAIL_VALIDATION** | — | — | ValidationError: 1 validation error for StrategyJSON   Value error, Co |
| 13 | `adx-strong-trend-filter` | **FAIL_UNPARSEABLE** | — | — | entry_long: adx_14 > 25 AND ema_9 crosses above ema_21 AND ema_9 slopi |
| 14 | `bb-mean-reversion` | **FAIL_UNPARSEABLE** | — | — | entry_long: low <= bb_lower AND previous close > bb_lower |
| 15 | `bb-squeeze-breakout` | **FAIL_UNPARSEABLE** | — | — | entry_long: bb_width at 20-bar low AND close > bb_upper AND atr_14 inc |
| 16 | `camarilla-pivots-intraday` | **FAIL_UNPARSEABLE** | — | — | entry_long: price closes above H3 (Camarilla 3rd resistance) with volu |
| 17 | `doji-reversal` | **FAIL_UNPARSEABLE** | — | — | entry_long: previous bar doji (body < 10% of range) AND price was exte |
| 18 | `donchian-channel-breakout` | **FAIL_UNPARSEABLE** | — | — | entry_long: close > 20-bar donchian upper band (new 20-bar high) AND a |
| 19 | `engulfing-candle-reversal` | **FAIL_UNPARSEABLE** | — | — | entry_long: current bar bullish engulfing pattern (current close > pre |
| 20 | `hull-ma-trend` | **FAIL_UNPARSEABLE** | — | — | entry_long: hull_ma_21 colour flips from red (sloping down) to green ( |
| 21 | `ichimoku-cloud-crossover` | **FAIL_UNPARSEABLE** | — | — | entry_long: close crosses above kumo (cloud) AND tenkan > kijun AND ch |
| 22 | `inside-bar-breakout` | **FAIL_UNPARSEABLE** | — | — | entry_long: previous bar fully inside the bar before it (inside-bar pa |
| 23 | `macd-divergence` | **FAIL_UNPARSEABLE** | — | — | entry_long: price prints lower low in last 25 bars AND macd histogram  |
| 24 | `macd-histogram-momentum` | **FAIL_UNPARSEABLE** | — | — | entry_long: macd_histogram crosses above 0 AND macd_histogram[0] > mac |
| 25 | `obv-divergence` | **FAIL_UNPARSEABLE** | — | — | entry_long: price prints lower low in last 25 bars AND obv prints high |
| 26 | `rsi-divergence` | **FAIL_UNPARSEABLE** | — | — | entry_long: price prints lower low in last 20 bars AND rsi_14 prints h |
| 27 | `supertrend-rider` | **FAIL_UNPARSEABLE** | — | — | entry_long: supertrend flips to bullish (close > supertrend) |
| 28 | `triple-ema-crossover` | **FAIL_UNPARSEABLE** | — | — | entry_long: ema_8 > ema_21 > ema_55 AND ema_8 crosses above ema_21 in  |
| 29 | `vwap-bounce` | **FAIL_UNPARSEABLE** | — | — | entry_long: prior bars > vwap AND current low touches vwap AND close > |

## Counts
- **FAIL_UNPARSEABLE**: 17
- **PASS**: 8
- **FAIL_VALIDATION**: 4

## Translated outputs (engine-callable)

PASS templates have their canonical `StrategyJSON` dumped to
`docs/TRANSLATOR_PROTOTYPE/translated/<slug>.json` — these are ready
to drop into a `Strategy.strategy_json` row.

## Coverage on the 29-template active set

- Mechanically translated by the parser: **8 / 29** (27%).
- Need founder overrides: **21 / 29** — see FOUNDER_OVERRIDES_NEEDED.md.