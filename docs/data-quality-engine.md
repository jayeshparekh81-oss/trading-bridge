# Data Quality Engine

> Status: Production-ready
> Introduced: Commit `a505ffb` (18 tests)
> Backtest integration: Commit `4cd340f`
> Real Dhan candle gating: Commit `4476387`
> Last updated: 2026-05-09

## Overview

The Data Quality Engine inspects an OHLCV candle stream for
common defects — missing bars, out-of-order timestamps, zero
volume runs, anomalous price spikes, duplicates — and returns a
quality score (0-100) plus a `can_backtest` decision flag and a
list of typed `DataQualityIssue` records. The Phase 1 backtest
endpoint runs the engine over its candle window and either
gates a run with a 422 (`can_backtest is False`) or attaches the
score + warnings to the response so the frontend renders an
inline data-health badge.

## Why It Exists

Garbage candles produce garbage backtests. A historical data
fetch that silently drops bars during a market-hours blackout
will let a strategy "succeed" on the gappy slice in ways it
never could on a complete stream. The engine:

- **Catches the silent failure mode** of bad data feeds before
  the user trusts the resulting backtest.
- **Surfaces the warning at the right altitude.** Quality
  warnings ride alongside the backtest result so the UI can
  render them inline instead of relegating them to a log.
- **Gates the worst-quality runs.** Below the configured floor
  the engine refuses to backtest, with an explanatory message.

## Quality Scoring Algorithm

```python
score = 100
for issue in issues:
    score -= penalty_for_severity(issue.severity)
score = max(0, score)
```

Source: `backend/app/strategy_engine/data_quality/scorer.py`.

| Severity | Penalty per issue |
|---|---|
| `INFO` | small (a heads-up; doesn't accumulate quickly) |
| `WARNING` | medium |
| `CRITICAL` | large (a few of these floor the score) |

The penalty constants live in
`data_quality/constants.py::INFO_PENALTY`,
`WARNING_PENALTY`, `CRITICAL_PENALTY`. The
`QUALITY_FLOOR_FOR_BACKTEST` constant in the same file controls
the gate — score below the floor → `can_backtest is False`.

The scorer is **pure** — no I/O, no clock, no state. The
companion validator (`data_quality/validator.py`) is similarly
pure. Both are easy to unit-test and trivially deterministic.

## Issue Catalogue

The validator emits these issue types:

| Type | Severity | Cause |
|---|---|---|
| `MISSING_BARS` | warning / critical | Trading-day candles missing beyond `MAX_MISSING_PERCENT`. |
| `OUT_OF_ORDER_TIMESTAMPS` | critical | Candles arrive non-monotonically. |
| `DUPLICATE_BARS` | warning | Same timestamp appears twice. |
| `ZERO_VOLUME` | info | Bars with zero volume — flagged but tolerated. |
| `ANOMALOUS_PRICE_SPIKE` | warning | Single-bar move > configured % multiple. |
| `SHORT_HISTORY` | info | Fewer than the recommended candle count. |
| `WEEKEND_BAR` | info | Candle timestamped on Sat/Sun (data-feed glitch). |

Source: `backend/app/strategy_engine/data_quality/validator.py`.

## Public API

```python
from app.strategy_engine.data_quality import (
    validate_candles,
    compute_quality_score,
    can_backtest_with_quality,
)

issues = validate_candles(candles)
score = compute_quality_score(issues)
can_run = can_backtest_with_quality(score)

# OR — one-shot:
report = run_quality_check(candles)
# report.score          → 0-100
# report.can_backtest   → bool
# report.issues         → tuple[DataQualityIssue]
# report.summary_hi     → Hinglish status string
```

The Hinglish summary the frontend renders verbatim:

| Score band | Summary |
|---|---|
| 90-100 | "Data quality acchi hai — backtest reliable hoga." |
| 70-89 | "Data thodi sketchy hai — backtest results ko cautiously dekho." |
| 50-69 | "Data quality kam hai — koi major issue ho sakti hai." |
| < 50 | "Data quality bohot kharab — backtest run nahi hoga, source check karo." |

## Backtest Integration

The Phase 1 backtest endpoint
(`/api/strategies/{id}/backtest`, commit `4cd340f`) runs the
quality check before invoking the engine:

1. Fetch candles (default Dhan path or test fixture).
2. `report = run_quality_check(candles)`.
3. If `report.can_backtest is False` → 422 with the issue list.
4. Otherwise → run backtest + attach `report` to the response
   under `data_quality`.

The frontend Backtest Results page reads `data_quality` and
shows a badge (green `Acchi quality` / yellow `Sketchy` /
red `Kharab`).

## Real Dhan Candle Gating

Commit `4476387` integrated the real Dhan historical-data
fetcher into the backtest endpoint. The integration:

1. Pulls the candle window from Dhan via the data-provider
   builders (see
   [`backend/app/strategy_engine/data_provider/DHAN_API_NOTES.md`](../backend/app/strategy_engine/data_provider/DHAN_API_NOTES.md)).
2. Runs `run_quality_check` over the fetched candles.
3. Refuses the backtest if quality drops below floor — Dhan's
   API has known weekend / market-holiday gaps that the
   validator catches deterministically.

This is the load-bearing reason real Dhan integration didn't
have to wait on a "perfect data feed". The quality engine
catches Dhan's documented failure modes; the backtest engine
trusts post-quality candles unconditionally.

## Configuration

Constants in `data_quality/constants.py`:

- `INFO_PENALTY`, `WARNING_PENALTY`, `CRITICAL_PENALTY` — the
  per-severity score deduction.
- `QUALITY_FLOOR_FOR_BACKTEST = 50` (default) — score below
  this gates the backtest.
- `MAX_MISSING_PERCENT = 5` — proportion of expected bars
  allowed missing before the issue's severity escalates from
  warning to critical.
- `ANOMALOUS_PRICE_MULTIPLE = 5` — single-bar % move
  classification threshold.

These are constants, not env vars, for the same load-bearing
reason as the rest of the safety surfaces — silently lowering
the quality floor in production weakens the gate.

## Edge Cases & Limitations

- **Single-asset focus.** The validator inspects one stream at
  a time. Multi-asset strategies that need correlated quality
  checks across symbols are out of scope today.
- **No cross-source comparison.** The validator can't say "this
  bar from Dhan disagrees with this bar from BSE Bhavcopy". It
  only checks self-consistency within the stream you give it.
- **Weekend bars are info-level.** Holiday calendars vary by
  exchange + segment + year. We log + flag rather than reject,
  so a real holiday doesn't black out a backtest mid-stream.
- **No quality-aware backtest splicing.** A 365-day window with
  10 bad days could ideally backtest the 355 good days. Today
  the engine refuses the whole window if the score floor is
  breached. A future enhancement would splice around bad
  segments.

## Testing

- `tests/strategy_engine/data_quality/test_validator_*.py` —
  per-issue-type fixture matrix.
- `tests/strategy_engine/data_quality/test_scorer.py` — penalty
  schedule + floor gating.
- `tests/strategy_engine/data_quality/test_run_quality_check.py`
  — end-to-end on representative candle streams.
- `tests/strategy_engine/api/test_backtest_quality_gating.py` —
  endpoint integration: 422 on poor quality, attached score on
  good quality.

## Future Work

- **Splicing-aware backtests.** Backtest only the high-quality
  contiguous segments + report the gaps. Would unlock more
  research-mode backtests on patchy historical data.
- **Cross-source consistency.** Compare Dhan candles against a
  second source (Bhavcopy, NSE official). Useful for the
  marketplace's transparency-ledger guarantees.
- **Per-instrument quality calibration.** ATR-percentile-based
  anomaly thresholds today are global; tuning per instrument
  would shrink false positives on naturally-volatile symbols.
- **Quality history tracking.** A timeseries of per-symbol
  quality scores would surface when a data feed is degrading
  *over time*, not just on a single fetch.

## References

- Module source: `backend/app/strategy_engine/data_quality/`
- Backtest integration: `backend/app/strategy_engine/api/backtest.py`
- Dhan integration notes: [`../backend/app/strategy_engine/data_provider/DHAN_API_NOTES.md`](../backend/app/strategy_engine/data_provider/DHAN_API_NOTES.md)
- Tests: `backend/tests/strategy_engine/data_quality/`
- Sister doc: [`/docs/strategy-truth-engine.md`](./strategy-truth-engine.md)
- Sister doc: [`/docs/indicator-registry.md`](./indicator-registry.md)
