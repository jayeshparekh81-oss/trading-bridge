# Queue NN — Translator B1 (Candle Pattern Conditions): DISCOVERY → HARD-STOP

**Verdict:** 🔴 **HARD-STOP #2 at Phase 1.** The 3 target templates cannot be
unlocked by "grammar-only" candle-pattern recognition: they require **bar-offset
lookback and prior-bar level references that the `CandleCondition` schema does not
support** (plus mixed AND/OR, proximity, inline pattern defs, and one missing
template). **No code changed.** Branch `feat/translator-b1-candle-patterns` created
off A2 (`feat/translator-a2-synonym-resolution`@84ef9f9) but contains no source edits.
Await founder decision before any implementation.

Hard-stop #1 (engine can't detect patterns) is **NOT** triggered — see §3.

## Pre-state
- Off A2 branch @84ef9f9 (12 PASS post-A2). main 6bf7f26.

## 1. The 3 targets — ACTUAL condition shapes (not May-21 assumptions)
- **`hammer-hanging-man`: DOES NOT EXIST in `strategy_templates_seed.json`.** (1 of 3 targets is phantom.)
- **`engulfing-candle-reversal`** (indicators ema_50, rsi_14):
  - entry: `current bar bullish engulfing pattern (current close > previous open AND current open < previous close AND previous bar bearish) AND rsi_14 < 40 AND close > ema_50 OR close within 2% of ema_50`
  - exit: `current bar bearish engulfing OR close < entry_low (engulfing bar's low)`
- **`doji-reversal`** (indicators ema_50, rsi_14):
  - entry: `previous bar doji (body < 10% of range) AND price was extended below ema_50 in last 5 bars (downtrend) AND rsi_14 < 35 AND current bar closes above doji's high`
  - exit: `close < doji's low OR rsi_14 > 60 (mean-reversion complete)`

## 2. Why "grammar only" is false — the blocking semantics
| Required by template | Supported today? |
|---|---|
| "current bar bullish engulfing" | ✅ `CandleCondition(pattern=engulfing)` + `detect_candle_pattern` |
| **"previous bar doji"** (bar offset −1) | ❌ no bar-offset on CandleCondition / detector |
| **"closes above doji's high"**, **"engulfing bar's low"** (prior pattern-bar level ref) | ❌ schema has no stateful level reference |
| **"extended below ema_50 in last 5 bars"** (N-bar window) | ❌ no lookback window |
| **mixed AND/OR** in one condition | ❌ `parse_conditions` raises (schema operator is flat) |
| **"within 2% of ema_50"** (proximity) | ❌ no proximity op |
| inline pattern definition `(body < 10% of range)` | n/a (decorative, but signals prose not tokens) |

## 3. What DOES exist (so the re-scope is sized correctly)
- `CandlePattern` enum has `bullish, bearish, engulfing, doji, hammer, shooting_star` ✓
- `engines/candle_pattern.py::detect_candle_pattern(pattern, current, prior)` is **real**
  (not stubbed) — single-bar doji/hammer/shooting_star + two-bar engulfing.
- `engines/entry.py::_evaluate_condition` dispatches `CandleCondition` →
  `detect_candle_pattern`, and the **backtest simulator imports `evaluate_entry`**
  (simulator.py:48). So a **current-bar** candle condition is fully translatable +
  backtestable today.
- **Implication:** a *simple* candle template (e.g. "current bar is hammer AND
  rsi_14 < 30 AND close > ema_50") would need only modest grammar work — no schema
  change. The 3 chosen templates are the hard ones (all need lookback/level refs).
- `CandleCondition` fields are exactly `{type, pattern}` — no offset/lookback/level.

## 4. What a real fix needs (C-tier, multi-hour — out of B1 scope)
1. **Schema:** extend `CandleCondition` with bar offset (e.g. `bars_ago: int = 0`)
   and a way to reference a prior pattern-bar's level (doji's high / engulfing low),
   plus a proximity comparator (or a new PriceCondition variant); decide how to
   express N-bar windows ("extended below in last 5 bars").
2. **Evaluator:** `detect_candle_pattern` + entry/exit evaluators need a candle
   *history* window (not just current+prior) and pattern-bar level capture.
3. **Grammar:** parse the verbose prose (mixed AND/OR precedence, parentheticals,
   proximity, stateful level references). Mixed AND/OR alone needs a real expression
   parser, not the current flat clause splitter.
4. Add `hammer-hanging-man` (or correct the target list).
   Faithful translation likely needs founder overrides per slug even after schema work.

## 5. SACRED / risk
**ZERO.** No files changed. Inspection only. LIVE BSE LTD path, brokers, webhook,
kill_switch, strategy_executor, migrations untouched. A2's tests + 12 PASS templates
unaffected.

## 6. Recommendation
Do not ship a lossy "grammar-only" approximation of these 3 (it would silently drop
the OR branches, proximity, lookback, and stateful exits — changing strategy
behavior). Options:
1. **Re-scope to C2** "candle pattern lookback + stateful level references" (schema +
   evaluator + grammar) — multi-hour, founder-prioritised.
2. **Pivot B1** to *simple* current-bar candle templates if/when added to the seed
   (cheap; engine already supports them).
3. **Founder overrides** for these 3 slugs — but they still need schema lookback to be
   faithful, so this only defers the schema work.
Coverage stays 12 until one of the above is chosen.
