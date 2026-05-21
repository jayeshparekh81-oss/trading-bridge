# Phase 1 — Original 15 Templates: Validation Summary

## Headline answer

> **Translator gap is UNIVERSAL.** 15/15 original Phase 1 templates fail `StrategyJSON` validation with the same shape mismatch the 17 batch-activated templates exhibit (Queue Z `MISSING_INDICATORS.md`).

Combined evidence: **32/32 templates BLOCKED** (15 Phase 1 + 17 batch). The shape failure is structural, not per-template.

## Per-template results

| Slug | Verdict | Pydantic errors | Entry condition (truncated) |
|------|---------|-----------------|------------------------------|
| ema-crossover-9-21 | BLOCKED_TRANSLATOR_GAP | 17 | `"ema_9 crosses above ema_21"` |
| ema-crossover-20-50 | BLOCKED_TRANSLATOR_GAP | 17 | `"ema_20 crosses above ema_50"` |
| macd-trend-signal | BLOCKED_TRANSLATOR_GAP | 16 | `"macd line crosses above signal line"` |
| supertrend-rider | BLOCKED_TRANSLATOR_GAP | 16 | `"supertrend flips green ..."` |
| rsi-oversold-bounce | BLOCKED_TRANSLATOR_GAP | 14 | `"rsi_14 crosses above 30 from below"` |
| bb-mean-reversion | BLOCKED_TRANSLATOR_GAP | 14 | `"close < bollinger lower band"` |
| bb-squeeze-breakout | BLOCKED_TRANSLATOR_GAP | 17 | `"bollinger bandwidth < threshold ..."` |
| orb-15min | BLOCKED_TRANSLATOR_GAP | 16 | `"close > first 15-min high after 09:30"` |
| pdh-pdl-breakout | BLOCKED_TRANSLATOR_GAP | 17 | `"close > yesterday's high"` |
| vwap-bounce | BLOCKED_TRANSLATOR_GAP | 14 | `"close > vwap ..."` |
| macd-histogram-momentum | BLOCKED_TRANSLATOR_GAP | 16 | `"macd histogram > 0 and rising"` |
| banknifty-weekly-equity | BLOCKED_TRANSLATOR_GAP | 15 | (multi-condition) |
| premarket-gap | BLOCKED_TRANSLATOR_GAP | 16 | (multi-condition) |
| rsi-macd-confluence | BLOCKED_TRANSLATOR_GAP | 17 | (multi-condition) |
| bb-rsi-oversold | BLOCKED_TRANSLATOR_GAP | 15 | (multi-condition) |

## Counts
- PARSEABLE (engine-callable today): **0/15**
- BLOCKED_TRANSLATOR_GAP: **15/15**
- Variance in error count (14–17) reflects multi-condition templates needing additional `right`/`value` slots; not a per-template solvability difference.

## Implication for activation policy
The 12 Phase-1-still-active templates in `origin/main` are no more validated than the 17 batch-additions. The Queue Y framing — "12 are tested, 17 are untested" — was wrong. **All 29 currently-active templates are equally untested by the engine.**

Three implications:
1. **Path B (deactivate the 17 only) is half a solution.** Customers would still see 12 templates none of which has ever been backtest-validated.
2. **The seed's `is_active` flag is currently a UI-visibility flag, not an engine-readiness flag.** This should be acknowledged in the seed `_meta` block or in user-facing copy.
3. **Building the translator unlocks ALL 113 templates in one stroke**, not just the 17. Higher ROI than originally framed.

See [`../TRANSLATOR_ARCHITECTURE_PROPOSAL.md`](../TRANSLATOR_ARCHITECTURE_PROPOSAL.md) for the proposed translator design.

## Backtest results (for completeness)
None executed. Every template short-circuited at `StrategyJSON(**config_json)` before reaching `run_backtest`. trade_count / win_rate / total_return_pct / max_drawdown_pct / sharpe_ratio = N/A on all 15.
