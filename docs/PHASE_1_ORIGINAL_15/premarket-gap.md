# Phase 1 Original-15 Validation — `premarket-gap`

**Template name:** Pre-Market Gap Strategy
**Category:** Event-Driven
**Verdict:** **BLOCKED_TRANSLATOR_GAP**
**Reason:** Pydantic StrategyJSON validation failed with 16 errors.

## Template `config_json` (relevant fields)
- `indicators`: ['pre_market_gap_pct']
- `entry_long.condition`: `"pre_market_gap_pct between 0.5 and 1.5 AND first 2 bars close >= open"`
- `exit_long.condition`: `"close < open of bar 3 OR timestamp >= 14:30 IST"`

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
