# Phase 1 Original-15 Validation — `macd-histogram-momentum`

**Template name:** MACD Histogram Momentum
**Category:** Momentum
**Verdict:** **BLOCKED_TRANSLATOR_GAP**
**Reason:** Pydantic StrategyJSON validation failed with 16 errors.

## Template `config_json` (relevant fields)
- `indicators`: ['macd_12_26_9']
- `entry_long.condition`: `"macd_histogram crosses above 0 AND macd_histogram[0] > macd_histogram[1] > macd_histogram[2]"`
- `exit_long.condition`: `"macd_histogram > 0 AND macd_histogram[0] < macd_histogram[1]"`

## Why BLOCKED
The template's `config_json` is documentation-shape — list-of-strings for `indicators`
and prose strings for `entry_long.condition` / `exit_long.condition`. The
backtest engine's `StrategyJSON` requires structured `IndicatorConfig` dicts
(`{id, type, params}`) and discriminated-union conditions (`IndicatorCondition`,
`CandleCondition`, etc.). All 15 original Phase 1 templates share this shape
and fail identically; see `SUMMARY.md` for the full table.

## What's needed
A `template_config_json → StrategyJSON` translator. Proposal in
[`docs/TRANSLATOR_ARCHITECTURE_PROPOSAL.md`](../TRANSLATOR_ARCHITECTURE_PROPOSAL.md).

## Backtest result
- trades: N/A (engine never reached)
- win_rate / total_return / max_dd / sharpe: N/A
