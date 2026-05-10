# AI Advisor

> Status: Production-ready
> Introduced: Commit `f8afaf9`
> Last updated: 2026-05-09

## Overview

The AI Advisor walks a strategy's backtest + reliability + truth +
optional regime / deviation artefacts through 11 deterministic rules
and emits a typed checklist of advice the UI renders next to the
backtest result. Two derived booleans —
`paper_trading_recommended` and `live_trading_recommended` — gate
the "go live" buttons so a strategy missing a stop-loss, scoring
poorly on the Truth Engine, or showing live deviation never gets
promoted by accident.

The advisor is **not an LLM**. Every recommendation is a pure
function of the strategy spec + numeric reports, which means:

- Identical inputs always produce identical advice (testable).
- No outbound network call, no API key required.
- Zero token cost — runs inline on every backtest.

## Why It Exists

The master prompt's "AI Doctor" persona promises grounded advice,
not generated text. Building a deterministic rules engine first
gives us:

- A trustworthy baseline that survives audits + regulatory review.
- A test surface we can pin behaviour on (`tests/strategy_engine/advisor/`).
- A natural extension point: the LLM Doctor (separate module) layers
  natural-language summaries on top of these rules without
  replacing them.

## Public API

The advisor lives in `app.strategy_engine.advisor.advisor`. The two
entry points:

```python
from app.strategy_engine.advisor import generate_advice, summarise_advice

# After running the backtest + truth + (optional) regime / deviation
# pipelines, hand everything to the advisor:
advice_list = generate_advice(
    strategy=strategy_json,
    backtest=backtest_result,
    reliability=reliability_report,
    truth=truth_report,
    regime=regime_report,        # optional
    deviation=deviation_report,  # optional
)

# advice_list is a tuple of Advice records:
#   Advice(rule_id=..., severity=..., title=..., body=..., action=...)

summary = summarise_advice(advice_list)
# Has paper_trading_recommended + live_trading_recommended booleans.
```

The 11 rules walked in order:

| # | Rule | Severity |
|---|---|---|
| 1 | Indicator suggestions (only-trend → add momentum, etc.) | info |
| 2 | Missing stop loss | critical |
| 3 | Missing exit primitive | critical (defensive) |
| 4 | Indicator overload (> N indicators) | warning |
| 5 | High win-rate caution (suspicious overfitting) | warning |
| 6 | Low trust score → paper-trade extensively | warning |
| 7 | Poor truth score → kill any live recommendation | critical |
| 8 | Overfitting (OOS degradation from TruthReport) | warning |
| 9 | High drawdown → reduce position size | warning |
| 10 | Market regime mismatch (when caller supplies a regime hint) | warning |
| 11 | Live deviation warning (when caller supplies a deviation report) | warning |

Source: `app/strategy_engine/advisor/advisor.py`.

## Integration Points

**Consumes:**
- `BacktestResult` (Phase 1 backtest engine).
- `ReliabilityReport` (Phase 4 walk-forward + sensitivity).
- `TruthReport` (Phase 5 truth-engine).
- `RegimeReport` (Phase 8, optional).
- `DeviationReport` (Phase 9, optional).

**Consumed by:**
- The `/api/strategies/{id}/backtest` endpoint, which packs the
  advice into the same response the frontend backtest panel
  renders.
- The Strategy Doctor (`advisor/doctor.py`) — Doctor consumes
  Advisor output as one of several diagnostic inputs.
- The frontend `<AdviceListPanel />` component on the backtest
  results page.

## Configuration

No runtime configuration. Thresholds are constants in
`advisor/constants.py` (e.g. `MIN_TRUST_SCORE_FOR_LIVE`,
`HIGH_DRAWDOWN_THRESHOLD_PCT`). Changing them requires a code
change + test update — deliberate; an env-var-driven threshold
would let an operator silently weaken safety.

## Edge Cases & Limitations

- **`live_trading_recommended` is conservatively false.** It
  requires every gate (stop loss + trust score + truth score + no
  overfitting + no critical advice) to pass simultaneously. A
  strategy with one warning still gets `live_trading_recommended =
  False`. This is intentional — false negatives are cheaper than
  false positives in trading.
- **Regime + deviation rules are conditional on caller-supplied
  reports.** If the caller doesn't pass a `RegimeReport`, rule 10
  isn't checked at all (not "passed" — skipped). Same for rule 11.
- **No personalisation.** The advisor doesn't know the user's
  capital, risk tolerance, or trading history. Every recommendation
  is strategy-shape-driven.
- **No ranking.** Returns rules in their declared order, not
  severity-sorted. Consumers that want severity sort do it client-side.

## When NOT to Use the Advisor

- **As the only safety check before live trading.** Advice is
  advisory; the SafetyChain in `live_orders/safety_chain.py` is the
  load-bearing gate that actually blocks order placement.
- **For natural-language explanations.** That's the LLM Doctor's
  job (`advisor/doctor.py` + the `apply-fix` workflow).
- **For real-time alerting.** Advice is computed once per
  backtest, not on a live tick. The Deviation Monitor is the
  live-monitoring counterpart.

## Testing

- `tests/strategy_engine/advisor/test_advisor_indicator_rules.py`
  — every rule has positive + negative cases pinned.
- `tests/strategy_engine/advisor/test_advisor_smoke.py` — end-to-end
  paper / live recommendation gate matrix.

Determinism is the contract. Any change to advisor logic must
update the tests with new fixture data; the failure surface is the
test asserting equality with the expected `Advice` record.

## Future Work

- **LLM-augmented summaries.** The Doctor module already drafts
  improved strategy variants; a planned extension surfaces a
  one-paragraph natural-language summary built from the
  deterministic rules' output. Strict guardrail: the LLM never
  invents new findings, only translates the rule output into
  Hinglish prose.
- **Per-user personalisation.** Risk tolerance + capital + recent
  trade history would let the advisor tighten / loosen thresholds.
  Out of scope for v1.0.
- **Streamed advice.** Currently runs in one synchronous pass.
  For very long backtests a streamed yield would let the UI
  progressively render advice as each rule completes.

## References

- Module source: `backend/app/strategy_engine/advisor/`
- Frontend integration: `frontend/src/components/strategies/advice-list-panel.tsx`
- Tests: `backend/tests/strategy_engine/advisor/`
- Sister doc: [`/docs/ai-strategy-doctor.md`](./ai-strategy-doctor.md)
- Sister doc: [`/docs/strategy-truth-engine.md`](./strategy-truth-engine.md)
- Sister doc: [`/docs/strategy-coach.md`](./strategy-coach.md)
