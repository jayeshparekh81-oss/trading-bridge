# Founder Overrides Needed — Queue BB Translator Prototype

21 of 29 currently-active templates need founder input or a per-template
hand-written `StrategyJSON` override. Grouped below by failure mode.

For each entry: the template's prose `entry_long.condition` is shown
alongside the parser's verdict and 2-3 candidate interpretations.

### Sub-output references (close/price vs an indicator's NAMED line)

Prose references a SUB-OUTPUT of a multi-line indicator (`macd_line`, `signal_line`, `macd_histogram`, `bb_lower`, `bb_middle`, `bb_upper`, `orb_15_high`, etc.). The current `StrategyJSON` schema requires every condition's `left`/`right` to be a registered indicator id, but sub-outputs aren't schema-modelled. **Decision needed:** either (a) extend schema with sub-output ids like `macd_12_26_9.line`, (b) ship multi-output indicators as multiple registry entries (`macd_line_12_26_9` + `macd_signal_12_26_9` + `macd_histogram_12_26_9`), or (c) hand-translate per-template into a normal IndicatorCondition.

#### `macd-trend-signal` — MACD Trend with Signal Cross

Prose (verbatim from seed):
- `entry_long`: `"macd_line crosses above signal_line AND macd_histogram > 0"`
- `exit_long`: `"macd_line crosses below signal_line"`

Parser verdict: **FAIL_VALIDATION** — `ValidationError: 1 validation error for StrategyJSON
  Value error, Conditions reference indicato`

  1. Declare each sub-output as its own registry entry (e.g. `macd_line_12_26_9` ACTIVE in the registry pointing at `compute_macd_line`).
  2. Add schema support for dotted-id references (`macd_12_26_9.line`).
  3. Hand-translate this template — write a 30-50 line StrategyJSON override that uses only top-level indicator ids the schema already accepts.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `orb-15min` — Opening Range Breakout (15-min)

Prose (verbatim from seed):
- `entry_long`: `"close > orb_15_high AND timestamp >= 09:30 IST"`
- `exit_long`: `"close < orb_15_high OR timestamp >= 14:45 IST"`

Parser verdict: **FAIL_VALIDATION** — `ValidationError: 1 validation error for StrategyJSON
  Value error, Conditions reference indicato`

  1. Declare each sub-output as its own registry entry (e.g. `macd_line_12_26_9` ACTIVE in the registry pointing at `compute_macd_line`).
  2. Add schema support for dotted-id references (`macd_12_26_9.line`).
  3. Hand-translate this template — write a 30-50 line StrategyJSON override that uses only top-level indicator ids the schema already accepts.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `rsi-macd-confluence` — RSI + MACD Confluence

Prose (verbatim from seed):
- `entry_long`: `"rsi_14 > 50 AND macd_line > signal_line"`
- `exit_long`: `"rsi_14 < 50 OR macd_line < signal_line"`

Parser verdict: **FAIL_VALIDATION** — `ValidationError: 1 validation error for StrategyJSON
  Value error, Conditions reference indicato`

  1. Declare each sub-output as its own registry entry (e.g. `macd_line_12_26_9` ACTIVE in the registry pointing at `compute_macd_line`).
  2. Add schema support for dotted-id references (`macd_12_26_9.line`).
  3. Hand-translate this template — write a 30-50 line StrategyJSON override that uses only top-level indicator ids the schema already accepts.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `bb-rsi-oversold` — BB + RSI Oversold

Prose (verbatim from seed):
- `entry_long`: `"low <= bb_lower AND rsi_14 < 30"`
- `exit_long`: `"close >= bb_middle OR rsi_14 > 50"`

Parser verdict: **FAIL_VALIDATION** — `ValidationError: 1 validation error for StrategyJSON
  Value error, Conditions reference indicato`

  1. Declare each sub-output as its own registry entry (e.g. `macd_line_12_26_9` ACTIVE in the registry pointing at `compute_macd_line`).
  2. Add schema support for dotted-id references (`macd_12_26_9.line`).
  3. Hand-translate this template — write a 30-50 line StrategyJSON override that uses only top-level indicator ids the schema already accepts.

**Question for Jayesh:** which option (1/2/3) for this template?

---

### Prose patterns the parser doesn't handle yet

Either the prose uses a grammar construct the parser doesn't implement (divergence detection, candle patterns, sloping/colour-flip filler, multi-bar lookbacks, sub-output references) or is genuinely too free-form to grammar-match cleanly. **Decision needed per template:** either (a) write a hand-translated `StrategyJSON` override, (b) extend the parser grammar if the pattern recurs, or (c) deactivate the template until the canonical builder ships.

#### `supertrend-rider` — Supertrend Rider

Prose (verbatim from seed):
- `entry_long`: `"supertrend flips to bullish (close > supertrend)"`
- `exit_long`: `"supertrend flips to bearish"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: supertrend flips to bullish (close > supertrend)`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `bb-mean-reversion` — Bollinger Band Mean Reversion

Prose (verbatim from seed):
- `entry_long`: `"low <= bb_lower AND previous close > bb_lower"`
- `exit_long`: `"close >= bb_middle"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: low <= bb_lower AND previous close > bb_lower`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `bb-squeeze-breakout` — BB Squeeze Breakout

Prose (verbatim from seed):
- `entry_long`: `"bb_width at 20-bar low AND close > bb_upper AND atr_14 increasing"`
- `exit_long`: `"close < bb_middle"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: bb_width at 20-bar low AND close > bb_upper AND atr_14 incre`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `vwap-bounce` — VWAP Bounce

Prose (verbatim from seed):
- `entry_long`: `"prior bars > vwap AND current low touches vwap AND close > vwap"`
- `exit_long`: `"close > vwap * 1.01 OR close < vwap"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: prior bars > vwap AND current low touches vwap AND close > v`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `macd-histogram-momentum` — MACD Histogram Momentum

Prose (verbatim from seed):
- `entry_long`: `"macd_histogram crosses above 0 AND macd_histogram[0] > macd_histogram[1] > macd_histogram[2]"`
- `exit_long`: `"macd_histogram > 0 AND macd_histogram[0] < macd_histogram[1]"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: macd_histogram crosses above 0 AND macd_histogram[0] > macd_`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `donchian-channel-breakout` — Donchian Channel Breakout

Prose (verbatim from seed):
- `entry_long`: `"close > 20-bar donchian upper band (new 20-bar high) AND adx_14 > 20"`
- `exit_long`: `"close < 10-bar donchian lower band (Turtle 20/10 asymmetric trail)"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: close > 20-bar donchian upper band (new 20-bar high) AND adx`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `ichimoku-cloud-crossover` — Ichimoku Cloud Crossover

Prose (verbatim from seed):
- `entry_long`: `"close crosses above kumo (cloud) AND tenkan > kijun AND chikou above price-26-bars-ago"`
- `exit_long`: `"tenkan crosses below kijun OR close drops back into kumo"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: close crosses above kumo (cloud) AND tenkan > kijun AND chik`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `adx-strong-trend-filter` — ADX Strong Trend Filter

Prose (verbatim from seed):
- `entry_long`: `"adx_14 > 25 AND ema_9 crosses above ema_21 AND ema_9 sloping up"`
- `exit_long`: `"ema_9 crosses below ema_21 OR adx_14 < 18"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: adx_14 > 25 AND ema_9 crosses above ema_21 AND ema_9 sloping`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `triple-ema-crossover` — Triple EMA Crossover

Prose (verbatim from seed):
- `entry_long`: `"ema_8 > ema_21 > ema_55 AND ema_8 crosses above ema_21 in the last 2 bars"`
- `exit_long`: `"ema_8 crosses below ema_21 OR close < ema_55"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: ema_8 > ema_21 > ema_55 AND ema_8 crosses above ema_21 in th`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `camarilla-pivots-intraday` — Camarilla Pivots Intraday

Prose (verbatim from seed):
- `entry_long`: `"price closes above H3 (Camarilla 3rd resistance) with volume > 1.5x recent average AND close > vwap"`
- `exit_long`: `"price reaches H4 OR price closes back below H3"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: price closes above H3 (Camarilla 3rd resistance) with volume`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `inside-bar-breakout` — Inside Bar Breakout

Prose (verbatim from seed):
- `entry_long`: `"previous bar fully inside the bar before it (inside-bar pattern) AND current close > previous bar's high AND close > ema_20"`
- `exit_long`: `"close < previous inside-bar's low OR close < ema_20"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: previous bar fully inside the bar before it (inside-bar patt`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `engulfing-candle-reversal` — Engulfing Candle Reversal

Prose (verbatim from seed):
- `entry_long`: `"current bar bullish engulfing pattern (current close > previous open AND current open < previous close AND previous bar bearish) AND rsi_14 < 40 AND close > ema_50 OR close within 2% of ema_50"`
- `exit_long`: `"current bar bearish engulfing OR close < entry_low (engulfing bar's low)"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: current bar bullish engulfing pattern (current close > previ`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `doji-reversal` — Doji Reversal

Prose (verbatim from seed):
- `entry_long`: `"previous bar doji (body < 10% of range) AND price was extended below ema_50 in last 5 bars (downtrend) AND rsi_14 < 35 AND current bar closes above doji's high"`
- `exit_long`: `"close < doji's low OR rsi_14 > 60 (mean-reversion complete)"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: previous bar doji (body < 10% of range) AND price was extend`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `obv-divergence` — OBV Divergence

Prose (verbatim from seed):
- `entry_long`: `"price prints lower low in last 25 bars AND obv prints higher low (bullish divergence) AND close > ema_50 OR close within 1% of ema_50"`
- `exit_long`: `"obv prints lower high while price prints higher high (bearish divergence emerging) OR close < ema_50 - 1%"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: price prints lower low in last 25 bars AND obv prints higher`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `rsi-divergence` — RSI Divergence

Prose (verbatim from seed):
- `entry_long`: `"price prints lower low in last 20 bars AND rsi_14 prints higher low AND current candle bullish reversal pattern"`
- `exit_long`: `"rsi_14 > 70 OR rsi_14 crosses below 50"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: price prints lower low in last 20 bars AND rsi_14 prints hig`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `macd-divergence` — MACD Divergence

Prose (verbatim from seed):
- `entry_long`: `"price prints lower low in last 25 bars AND macd histogram prints higher low (bullish divergence) AND macd line above its signal"`
- `exit_long`: `"macd line crosses below signal line OR macd histogram contracts for 3 consecutive bars"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: price prints lower low in last 25 bars AND macd histogram pr`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

#### `hull-ma-trend` — Hull MA Trend

Prose (verbatim from seed):
- `entry_long`: `"hull_ma_21 colour flips from red (sloping down) to green (sloping up) AND close > hull_ma_21"`
- `exit_long`: `"hull_ma_21 colour flips back to red"`

Parser verdict: **FAIL_UNPARSEABLE** — `entry_long: hull_ma_21 colour flips from red (sloping down) to green (sl`

  1. Hand-translate to StrategyJSON using IndicatorCondition / CandleCondition / TimeCondition primitives the schema supports today.
  2. Extend the parser grammar if this prose pattern recurs across multiple templates.
  3. Deactivate this template in the seed until the canonical builder ships and the user authors it directly.

**Question for Jayesh:** which option (1/2/3) for this template?

---

## Aggregate decisions worth making once

1. **Sub-output indicators (the largest single bucket — 4 templates):** decide between extending the schema OR shipping per-line registry entries. The schema extension touches `IndicatorCondition` which is engine-critical; per-line registry entries are additive and lower-risk but multiply the registry size for every multi-output indicator. Recommend the latter for speed.
2. **Candle-pattern templates (`doji-reversal`, `engulfing-candle-reversal`, `hammer-hanging-man-pattern`):** these reference patterns the schema *does* model (CandleCondition). The parser doesn't yet have grammar for them. Adding 3-5 patterns is a ~1-day grammar extension that unlocks all of these.
3. **Divergence templates (`rsi-divergence`, `macd-divergence`, `obv-divergence`):** divergence is multi-bar pattern detection that the schema has NO primitive for. Engine extension required — out of scope for Queue BB. Recommend deactivate in seed until divergence support ships.
4. **Hull-MA / Supertrend "colour flip" prose:** these reference visual UI semantics ("flips green", "colour flips from red"). Should rewrite to numeric primitives (e.g. `supertrend_10_3 > close` → bullish). 30-min fix per template once decided.