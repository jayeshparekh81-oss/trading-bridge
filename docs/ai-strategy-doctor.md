# AI Strategy Doctor + Apply Fix

> Status: Production-ready
> Introduced: Commit `f8afaf9` (backend); Commit `984743f` (frontend)
> Last updated: 2026-05-09

## Overview

The Strategy Doctor is the deterministic counterpart to the
master-prompt "AI Doctor" persona. It inspects a strategy + its
backtest / reliability / truth artefacts and returns a
:class:`Diagnosis` partitioned into typed `problems`,
`recommendedFixes`, a `canAutoImprove` boolean, and (when
auto-improvement is possible) a concrete
`improvedStrategyDraft` — a brand-new strategy dict the user
can review and apply with one click.

The "Apply Fix & Compare" workflow on the frontend pairs the
doctor's draft with a fresh backtest run so the user sees the
old-vs-new equity curve side by side before committing.

## Why It Exists

A bare "your strategy has problems" message is unactionable. The
master prompt's voice — *"AI Doctor jaisi diagnosis"* — sets the
expectation that we give the user **a fix**, not just a finding.
The doctor:

1. Diagnoses 7 problem types deterministically.
2. Drafts a concrete improved strategy when the fix is mechanical
   (add stop loss, drop redundant indicator, tighten risk caps).
3. Hands the draft back without applying it. The compare-fix
   endpoint re-runs the backtest on the draft so the user
   compares before / after.

The original strategy is **never mutated**. Every draft is a
deep copy emitted as `model_dump(by_alias=True, mode="json")`
so the caller can write it back through the Phase 5 CRUD endpoint
without re-shaping.

## Public API

The doctor lives in `app.strategy_engine.advisor.doctor`. Entry
point:

```python
from app.strategy_engine.advisor.doctor import diagnose

diagnosis = diagnose(
    strategy=strategy_json,
    backtest=backtest_result,
    reliability=reliability_report,
    truth=truth_report,
    advice=advisor_advice,   # output of generate_advice()
)

# diagnosis.problems          → tuple[Problem]
# diagnosis.recommendedFixes  → tuple[str]
# diagnosis.canAutoImprove    → bool
# diagnosis.improvedStrategyDraft → dict | None
```

The 7 diagnosed problem types:

| Type | Detected when |
|---|---|
| `MISSING_STOP_LOSS` | `ExitRules` has no `stop_loss_percent`. |
| `LOW_TRUST_SCORE` | TrustReport grade is below the configured floor. |
| `LOW_TRUTH_SCORE` | TruthReport flags suspicious backtest patterns. |
| `OVERFITTING_DETECTED` | Walk-forward OOS degradation > threshold. |
| `INDICATOR_OVERLOAD` | More indicators than the per-mode cap. |
| `EXCESSIVE_DRAWDOWN` | Reported max drawdown > configured cap. |
| `INSUFFICIENT_TRADES` | Backtest produced fewer than the min-trade floor. |

Source: `advisor/doctor.py`.

### Apply Fix & Compare endpoint

```
POST /api/strategies/{id}/compare-fix
Body: { "improvedStrategyDraft": <doctor.improvedStrategyDraft> }
Response: {
  "before": <BacktestResult of original>,
  "after":  <BacktestResult of draft>,
  "diff":   <per-metric delta + sign-of-change>
}
```

The endpoint runs both backtests in parallel using the same
candle window so the comparison is fair.

## Integration Points

**Consumes:**
- The same artefacts as the AI Advisor (backtest, reliability,
  truth, regime, deviation).
- The Advisor's output as one input — many problem types reuse
  Advisor rules.

**Consumed by:**
- Frontend Doctor panel on the backtest results page (commit
  `984743f`).
- The compare-fix endpoint
  (`/api/strategies/{id}/compare-fix`) — runs both backtests
  and returns the diff.

## Configuration

No env vars. Thresholds are constants in `advisor/constants.py`
(shared with the Advisor — drift between the two is a known
hazard a future refactor should consolidate).

## Edge Cases & Limitations

- **`canAutoImprove` is conservative.** Returns `True` only when
  every problem the doctor found has a deterministic fix it knows
  how to draft. Mixed fixable + unfixable problems → `False` +
  no draft (caller still sees the problem list and recommended
  fixes as text).
- **Drafts never run.** The doctor produces the draft;
  re-running a backtest on it is the caller's responsibility. The
  compare-fix endpoint exists exactly to do this safely.
- **Drafts are not personalised.** "Add stop loss at 1 %" doesn't
  consider the user's volatility profile. The fix is a sane
  default, not an optimum.
- **Drafts can mask root causes.** A strategy with a poor truth
  score might get a "tighten the risk caps" draft that masks the
  real problem (the underlying signal is weak). The doctor flags
  the truth score in the problem list anyway, but a user who
  blindly accepts the draft can ship a band-aid.

## When NOT to Use the Doctor

- **As the only review of a strategy.** Doctor + Apply Fix is a
  feedback loop, not a verdict. The backtest + truth engine + live
  paper-trading + SafetyChain still gate live deployment.
- **On a strategy that has never been backtested.** Without a
  `BacktestResult` the doctor refuses to diagnose (insufficient
  data fixture).

## Testing

- `tests/strategy_engine/advisor/test_doctor_*.py` — fixture-driven
  positive + negative cases per problem type. Each `Problem` type
  has a "should detect" + "should not detect" pair.
- The compare-fix endpoint test
  (`tests/strategy_engine/api/test_compare_fix.py`) pins that the
  endpoint produces the expected diff shape end-to-end.

## Future Work

- **Multi-step drafts.** Currently each problem type drafts at
  most one fix. Some real-world strategies need a coordinated set
  of changes (e.g. add stop loss + reduce position size + drop
  one indicator). A planned extension lets the doctor return a
  ranked list of drafts.
- **LLM-translated explanations.** The deterministic problem list
  is the truth surface; a layered LLM call can translate it into
  Hinglish + offer per-problem rationale. Strict guardrail: the
  LLM never invents new problems.
- **Personalisation.** Use the user's capital + recent trade
  history to tune draft thresholds (e.g. a smaller account gets
  a tighter stop-loss draft).

## References

- Module source: `backend/app/strategy_engine/advisor/doctor.py`
- Compare-fix endpoint: `backend/app/strategy_engine/api/compare_fix.py`
- Frontend integration: `frontend/src/components/strategies/doctor-panel.tsx`
- Tests: `backend/tests/strategy_engine/advisor/`
- Sister doc: [`/docs/ai-advisor.md`](./ai-advisor.md)
- Sister doc: [`/docs/strategy-truth-engine.md`](./strategy-truth-engine.md)
