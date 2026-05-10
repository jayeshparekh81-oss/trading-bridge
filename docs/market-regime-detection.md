# Market Regime Detection

> Status: Production-ready
> Introduced: Commit `0715750`
> Last updated: 2026-05-09

## Overview

The Regime module classifies a candle window into one of 8 named
market regimes — `sideways`, `trending`, `choppy`, `breakout`,
`gap_day`, `high_volatility`, `low_volatility`, `abnormal` —
plus a confidence score per match and a Hinglish summary the UI
surfaces. The classification is deterministic, runs in pure
Python with no LLM / network / clock reads, and mirrors the
Phase 8 spec's locked priority order.

## Why It Exists

A strategy that prints money in a trending market can bleed in
choppy conditions. The advisor's "regime mismatch" rule (rule 10)
needs an authoritative regime classification to compare the
strategy against; the marketplace's listing detail page surfaces
the regime so subscribers know what kind of tape the strategy was
designed for.

## Public API

```python
from app.strategy_engine.regime import (
    detect_regime,
    assess_suitability,
)

report = detect_regime(candles)
# report.regime       → RegimeName enum (one of 8 values)
# report.confidence   → 0.0-1.0
# report.metrics      → RegimeMetrics (ATR percentile, ADX, etc.)
# report.summary_hi   → Hinglish summary string
# report.summary_en   → English summary string

# Optional: how well a strategy fits the detected regime.
suitability = assess_suitability(
    strategy=strategy_json,
    report=report,
)
# suitability.score        → 0.0-1.0
# suitability.warnings     → tuple[str]
```

Source: `app/strategy_engine/regime/`.

## How Detection Works

Pure deterministic pipeline:

```
candles ─► metrics ─► classifier ─► (optional) suitability ─► report
```

1. **Metrics** (`regime/metrics.py`) — computes ATR, ATR percentile
   over the lookback window, ADX, direction-change count, gap
   sizes, and abnormal-move flags.
2. **Classifier** (`regime/classifier.py`) — walks predicate
   functions in the locked priority order and returns the first
   match. Each predicate is small + pure.

### Locked priority order

```
abnormal > breakout > gap_day > trending >
high_volatility > low_volatility > choppy > sideways
```

`abnormal` wins because abnormal moves often *invalidate* every
other regime classification — a strategy designed for `trending`
should still pause if abnormal moves are happening even though
the trend is intact. `sideways` is the catch-all when nothing
else matches.

3. **Suitability** (`regime/suitability.py`) — given a strategy
   and a regime report, scores how well the strategy fits and
   produces warnings. Trend-following strategies in `choppy` get
   a low score + a warning; mean-reversion strategies in `trending`
   get the same treatment.

## Hinglish Summaries

Each regime ships a `summary_hi` field that the AlgoMitra panel
and the marketplace listing detail page render verbatim. Examples:

| Regime | Hinglish summary |
|---|---|
| `trending` | "Strong trend chal raha hai — direction confirm ho gaya." |
| `choppy` | "Market choppy hai — bina clear direction ke whipsaw aata hai." |
| `breakout` | "Breakout signal — range tod ke price chal nikla." |
| `abnormal` | "Abnormal move detect hua — strategy pause karne ka time." |

Source: `regime/messages.py`.

## Integration Points

**Consumes:**
- `Sequence[Candle]` from any source — backtest data feed,
  paper-trading session, live ticks.

**Consumed by:**
- The AI Advisor's rule 10 (regime-mismatch warning).
- The frontend `<RegimePanel />` on the backtest results page.
- The marketplace listing detail (cached in
  `marketplace_listings.performance_snapshot`).

## Configuration

Thresholds live in `regime/constants.py`. Key values:

- `ATR_PERCENTILE_HIGH` — percentile above which a market is
  classified as high volatility.
- `ADX_TRENDING_MIN` — ADX floor for the `trending` predicate.
- `DIRECTION_CHANGES_CHOPPY_MIN` — direction flips in the
  window for the `choppy` predicate.
- `ABNORMAL_PRICE_MOVE` — single-bar % move that triggers the
  `abnormal` priority override.

These are constants (not env vars) — same reasoning as the
advisor: thresholds are a behaviour contract, not deploy-time
configuration.

## Edge Cases & Limitations

- **Single-window classification.** Each call classifies one
  contiguous candle window. There's no built-in transition
  detection ("was trending, now choppy") — callers that want
  that classify two adjacent windows and compare.
- **Lookback length matters.** Short windows produce noisy
  classifications. The advisor's regime rule uses the same
  lookback as the backtest's candle count, which is usually
  enough; live-tick callers should batch ticks into a min
  window before classifying.
- **No multi-timeframe view.** A strategy could be trending on
  the daily but choppy on the 5-minute. The module classifies
  whatever bars it's given; multi-timeframe analysis is the
  caller's job.

## How Strategies Should React to Regimes

This is policy, not enforcement — the regime module emits
information, not actions. Recommended pattern:

- **Trend-following strategies** check that the regime is
  `trending` or `breakout` before going live.
- **Mean-reversion strategies** prefer `choppy` or `sideways`.
- **Every strategy** should pause on `abnormal` (the regime
  module's confidence score helps decide how strongly to
  pause).

The frontend Regime Panel already surfaces these recommendations
in plain Hinglish.

## Testing

- `tests/strategy_engine/regime/test_classifier_*.py` — every
  predicate has fixture-driven positive + negative cases.
- `tests/strategy_engine/regime/test_priority_order.py` — pins
  the locked priority so a refactor that shuffles predicates
  trips a regression.
- `tests/strategy_engine/regime/test_suitability.py` — strategy
  type detection + scoring matrix.

## Future Work

- **Streaming regime detection.** Currently each call processes
  a full window. A streaming variant would recompute incrementally
  as new bars arrive, useful for live paper trading.
- **Regime transition detection.** First-class API for
  "regime just flipped from X to Y" — a richer signal than
  "current regime is Y".
- **Per-instrument calibration.** ATR / ADX thresholds today are
  global; some instruments (NIFTY vs BANKNIFTY) have different
  natural volatility envelopes. Per-instrument tuning is a v1.1
  enhancement.

## References

- Module source: `backend/app/strategy_engine/regime/`
- Frontend integration: `frontend/src/components/strategies/regime-panel.tsx`
- Tests: `backend/tests/strategy_engine/regime/`
- Sister doc: [`/docs/ai-advisor.md`](./ai-advisor.md)
- Sister doc: [`/docs/deviation-monitor.md`](./deviation-monitor.md)
