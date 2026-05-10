# Deviation Monitor

> Status: Production-ready (advisory only — wiring to actions is deferred)
> Introduced: Commits `21ed6c0`, `58ba119`
> Last updated: 2026-05-09

## Overview

The Deviation Monitor compares a strategy's **live or paper-trading
performance** against its **backtest baseline** and flags drift. It
emits an advisory `DeviationReport` with per-metric comparisons,
aggregate severity, and a read-only `auto_kill_switch_signal`
boolean — but it never triggers the actual kill switch, never
talks to a broker, never writes to the strategy's execution path.

The isolation is load-bearing. An AST-inspection test pins that
the deviation module imports nothing from the live-execution
modules — by design, so a misconfigured deviation calc can't
take a user offline.

## Why It Exists

Backtests lie politely. A strategy can pass every Trust Engine +
Truth Engine check on historical candles and then drift in
production because:

- Real fills include slippage the backtest didn't model.
- Live regime is different from the backtest window's regime.
- Index composition changed since the backtest period.
- The user's risk caps are tighter than the backtest assumed.

The Deviation Monitor watches for these gaps on every
post-trade reconciliation pass. When the gap exceeds the
configured threshold, the monitor surfaces the warning to the
frontend Deviation Panel and the AI Advisor's rule 11.

## Public API

```python
from app.strategy_engine.deviation import detect_deviation

report = detect_deviation(
    backtest=backtest_result,
    actual_stats=actual_performance_stats,
)
# report.status                     → "ok" | "warning" | "critical" | "insufficient_data"
# report.metric_comparisons         → tuple[MetricComparison]
# report.aggregate_severity         → 0.0-1.0
# report.auto_kill_switch_signal    → bool (advisory only)
# report.summary                    → Hinglish status sentence
# report.recommended_actions        → tuple[str]
```

Source: `app/strategy_engine/deviation/`.

## How Detection Works

Pure decision pipeline:

```
backtest + actual stats ─► per-metric comparisons ─► aggregate ─►
decision flags ─► report
```

1. **Per-metric comparison** — each tracked metric (win rate,
   average PnL, max drawdown, total trades, etc.) gets a
   side-by-side comparison: backtest value, actual value,
   delta %, severity bucket.
2. **Aggregate severity** — weighted average across metrics.
3. **Decision flags** — given the aggregate severity, the
   monitor picks a status (`ok` / `warning` / `critical`) and
   sets the advisory `auto_kill_switch_signal` boolean.

The signal stays advisory until a future phase explicitly wires
it. The reasoning lives in the module docstring:

> The module emits an *advisory* `DeviationReport` — including a
> read-only `auto_kill_switch_signal` — but never invokes the
> actual kill switch, broker, or any execution path. Wiring the
> boolean into the safety system is a separate future phase by
> design; the AST inspection test pins that isolation.

## Integration Points

**Consumes:**
- `BacktestResult` from the Phase 1 backtest engine.
- An `ActualStats` dict computed from completed `PaperSession` /
  `Trade` rows (caller's responsibility — there's no built-in
  collector to keep the module stateless).

**Consumed by:**
- AI Advisor rule 11 (live deviation warning).
- Frontend `<DeviationPanel />` on the backtest / strategy detail page.
- Marketplace listing detail (the cached
  `performance_snapshot.deviation_status` field).

**Deliberately NOT consumed by:**
- The actual `KillSwitchService`. The
  `auto_kill_switch_signal` is read-only — wiring it requires a
  follow-up phase + a separate audit-log decision trail.

## Configuration

Thresholds in `deviation/constants.py`:

- `MIN_TRADES_FOR_EVAL` — below this trade count the report
  status is `insufficient_data` (no false alarms on day 1).
- `WARNING_SEVERITY_THRESHOLD` — aggregate severity above this
  flips status to `warning`.
- `CRITICAL_SEVERITY_THRESHOLD` — above this flips to
  `critical` and sets the kill-switch signal to `True`.

Per-metric thresholds (`MAX_WIN_RATE_DELTA_PCT`,
`MAX_AVG_PNL_DELTA_PCT`, etc.) live alongside.

## Hinglish Summaries

The `summary` and `recommended_actions` fields ship Hinglish
strings the UI renders verbatim. Examples:

| Status | Summary |
|---|---|
| `ok` | "Live performance backtest se match kar raha hai — sab theek hai." |
| `warning` | "Live performance backtest se thoda alag hai — review karo." |
| `critical` | "Live performance bohot alag hai — strategy pause karne pe sochna chahiye." |
| `insufficient_data` | "Abhi pakka kuch nahi keh sakte — aur trades chahiye verdict ke liye." |

Source: `deviation/messages.py`.

## Edge Cases & Limitations

- **Backtest baseline is fixed.** Once the strategy is created,
  the deviation monitor compares every actual run against the
  *original* backtest. Re-running the backtest with new candles
  and updating the baseline is the user's explicit choice (via
  the strategy detail page).
- **Insufficient data is a status, not an error.** Strategies
  with fewer than `MIN_TRADES_FOR_EVAL` actual trades return
  `insufficient_data`. The frontend renders this as a neutral
  "wait for more trades" hint.
- **No regime adjustment.** A strategy that backtested in a
  trending market and is now running in choppy conditions will
  show deviation. This is correct — the deviation is real — but
  the AI Advisor pairs the deviation warning with a regime hint
  so the user understands *why* the deviation appeared.
- **No multi-strategy correlation.** Each strategy's deviation
  is computed independently. A portfolio-level deviation summary
  is a v1.1 follow-up.

## Alert Thresholds

The default thresholds are tuned for daily-bar strategies. A
high-frequency strategy (5-minute bars, 100+ trades/day) saturates
the per-metric deltas faster, so the constants will need
per-strategy override hooks before HFT support lands.

## Testing

- `tests/strategy_engine/deviation/test_metric_comparisons.py` —
  per-metric delta calculation pinned.
- `tests/strategy_engine/deviation/test_isolation.py` — AST
  inspection test that the deviation package imports nothing
  from live-order / kill-switch / broker modules. **Don't break
  this test.** Loosening it would make the module a vector for
  unintended trading actions.
- `tests/strategy_engine/deviation/test_decision_flags.py` —
  status / severity / signal matrix.

## Future Work

- **Wire `auto_kill_switch_signal` into a dedicated trip type.**
  Currently the kill-switch trips on realized + unrealized PnL
  thresholds; deviation-driven trips would be a separate trip
  reason with its own audit trail and reset workflow.
- **Streaming evaluation.** Today the monitor evaluates on
  request. A scheduled job that runs the evaluation per-strategy
  every N minutes (and emits an event when status changes) is
  an obvious follow-up.
- **Per-strategy threshold overrides.** Move the
  `deviation/constants.py` thresholds behind a per-strategy
  override the user can tune via the strategy detail page.

## References

- Module source: `backend/app/strategy_engine/deviation/`
- Frontend integration: `frontend/src/components/strategies/deviation-panel.tsx`
- Tests: `backend/tests/strategy_engine/deviation/`
- AST isolation test: `backend/tests/strategy_engine/deviation/test_isolation.py`
- Sister doc: [`/docs/ai-advisor.md`](./ai-advisor.md)
- Sister doc: [`/docs/auto-kill-switch-integration.md`](./auto-kill-switch-integration.md)
