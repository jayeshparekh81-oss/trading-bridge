# Phase 1 Original-15 Validation — `pdh-pdl-breakout`

**Template name:** Previous Day High/Low Breakout
**Category:** Breakout
**Verdict:** **BLOCKED_TRANSLATOR_GAP**
**Reason:** Pydantic StrategyJSON validation failed with 17 errors.

## Template `config_json` (relevant fields)
- `indicators`: ['pdh', 'pdl']
- `entry_long.condition`: `"close > pdh"`
- `exit_long.condition`: `"close < pdh"`

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
