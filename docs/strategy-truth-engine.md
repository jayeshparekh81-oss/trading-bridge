# Strategy Truth Engine

Phase 6 of the AI trading system (commit `4647810`). Internal developer
reference — not user-facing copy.

## Purpose

Detect misleading or fake-looking backtests. The engine consumes a
pre-computed reliability report and answers a single question:

> "Is this backtest actually reliable, or is it giving false confidence?"

The output is a frozen `TruthReport` partitioned into four warning
buckets — fake-backtest, overfitting, execution, cost — plus
strengths, weaknesses, and a recommended-next-action list. The engine
is **pure, deterministic, AI-free**: no LLM calls, no network, no
clock reads. Same inputs always produce the same `TruthReport`.

## When to use

- After backtest + reliability report are computed (the engine
  consumes the reliability output, so it cannot run without it).
- Before recommending paper trading or live deployment.
- As a blocking input to the Broker Execution Guard. The check
  `check_truth_score` (in `app/strategy_engine/broker_guard/checks.py`)
  rejects live deployment when `truth_score < MIN_TRUTH_SCORE_FOR_LIVE`
  (currently `55`, defined in `broker_guard/constants.py`).

## Module location

`backend/app/strategy_engine/truth/`

| File | Purpose |
|------|---------|
| `__init__.py` | Public surface: `TruthReport`, `RiskLevel`, `evaluate_strategy_truth`. |
| `truth_score.py` | The evaluator — `evaluate_strategy_truth()`, `TruthReport` model, the twelve inspection rules, helpers. |
| `constants.py` | All numeric thresholds and per-rule deductions. Re-exports the relevant Phase 4 reliability constants so a future tightening propagates automatically. |

## Public API

Real signature from `app/strategy_engine/truth/truth_score.py`:

```python
def evaluate_strategy_truth(
    *,
    strategy: StrategyJSON,
    reliability: ReliabilityReport,
    cost_settings: CostSettings,
    ambiguity_mode: AmbiguityMode = AmbiguityMode.CONSERVATIVE,
    pre_cost_pnl: float | None = None,
) -> TruthReport: ...
```

All keyword-only. No positional invocation is supported.

### Inputs

| Parameter | Type | Source module |
|-----------|------|----------------|
| `strategy` | `StrategyJSON` | `app.strategy_engine.schema.strategy` |
| `reliability` | `ReliabilityReport` | `app.strategy_engine.reliability.reliability_report` |
| `cost_settings` | `CostSettings` | `app.strategy_engine.backtest.costs` |
| `ambiguity_mode` | `AmbiguityMode` | `app.strategy_engine.backtest.runner` |
| `pre_cost_pnl` | `float \| None` | Caller-supplied. When non-`None` and positive, enables the explicit cost-impact comparison. |

`strategy` is currently consumed only for completeness of the public
contract; the running heuristics derive from `reliability.backtest`
plus reliability sub-results. The argument is reserved so future rules
can consult `strategy.execution` or indicator count without changing
the signature.

### Output

`TruthReport` — frozen Pydantic model, JSON-serialised with master-prompt
camelCase aliases (`truthScore`, `fakeBacktestWarnings`, ...).

### Example

```python
from app.strategy_engine.backtest.runner import AmbiguityMode
from app.strategy_engine.reliability import build_reliability_report
from app.strategy_engine.truth import evaluate_strategy_truth

reliability = build_reliability_report(
    strategy=strategy_json,
    candles=candles,
    initial_capital=100_000.0,
    quantity=1.0,
    cost_settings=cost_settings,
)

truth = evaluate_strategy_truth(
    strategy=strategy_json,
    reliability=reliability,
    cost_settings=cost_settings,
    ambiguity_mode=AmbiguityMode.CONSERVATIVE,
)

if truth.truth_score >= 55 and truth.risk_level in {"low", "medium"}:
    proceed_to_paper_trading()
```

The actual orchestration in production lives in
`app/strategy_engine/api/backtest.py` (the
`POST /api/strategies/{id}/backtest` endpoint), which runs backtest →
reliability → truth in that order and returns all three in one
response.

## Output schema

Field shapes from `TruthReport` in `truth_score.py`:

| Field | Type | Notes |
|-------|------|-------|
| `truth_score` | `int` (0-100) | Wire alias `truthScore`. |
| `grade` | `Literal["A","B","C","D","F"]` | The `Grade` literal lives in `reliability/constants.py` and is re-exported by `truth/constants.py`. |
| `verdict` | `str` (1-128 chars) | One of three locked phrases — see [Verdict mapping](#verdict-mapping). |
| `risk_level` | `Literal["low","medium","high","extreme"]` | Wire alias `riskLevel`. Counts triggered warnings, not score. |
| `fake_backtest_warnings` | `tuple[str, ...]` | Wire alias `fakeBacktestWarnings`. Rules 1-6. |
| `overfitting_warnings` | `tuple[str, ...]` | Wire alias `overfittingWarnings`. Rules 7, 8, 11. |
| `execution_warnings` | `tuple[str, ...]` | Wire alias `executionWarnings`. Rules 10, 12. |
| `cost_warnings` | `tuple[str, ...]` | Wire alias `costWarnings`. Rule 9. |
| `strengths` | `tuple[str, ...]` | Positive observations, no alias rename. |
| `weaknesses` | `tuple[str, ...]` | Short labels (e.g. `"High win-rate trap"`), no alias rename. |
| `recommended_next_actions` | `tuple[str, ...]` | Wire alias `recommendedNextActions`. Ordered by triggering rule. |

`model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)`
— attribute access stays snake_case in Python; serialisation by alias
emits camelCase.

## Truth Score calculation

Computed in `evaluate_strategy_truth`:

1. Start `score = 100`.
2. For each rule that fires, subtract its `DEDUCT_*` constant from
   `constants.py`.
3. Final `score = max(0, min(100, score))` — clamped at the boundary.

### Per-rule deductions (from `truth/constants.py`)

| Rule | Bucket | Deduction |
|------|--------|-----------|
| 1. High win-rate risk | fake-backtest | `DEDUCT_HIGH_WIN_RATE_RISK = 20` |
| 2. Low trade count | fake-backtest | `DEDUCT_LOW_TRADE_COUNT = 15` |
| 3. Poor risk-reward | fake-backtest | `DEDUCT_POOR_RISK_REWARD = 10` |
| 4. Avg-loss dominates win | fake-backtest | `DEDUCT_AVG_LOSS_DOMINATES = 12` |
| 5. High max drawdown | fake-backtest | `DEDUCT_HIGH_DRAWDOWN = 15` |
| 6. Weak profit factor | fake-backtest | `DEDUCT_WEAK_PROFIT_FACTOR = 12` |
| 7. OOS degradation | overfitting | `DEDUCT_OOS_DEGRADATION = 20` |
| 8. Fragile parameters | overfitting | `DEDUCT_FRAGILE_PARAMETERS = 15` |
| 9. Cost impact | cost | `DEDUCT_COST_IMPACT = 12` |
| 10. Optimistic same-bar | execution | `DEDUCT_AMBIGUITY_OPTIMISTIC = 6` |
| 11. Overfitting stack (7 + 8) | overfitting | `DEDUCT_OVERFITTING_STACK = 8` |
| 12. Frictionless execution | execution | `DEDUCT_UNREALISTIC_FRICTIONLESS = 8` |

Bucket-level weighting is implicit in the per-rule values: fake-backtest
deductions sum to a maximum of 84, overfitting to 43 (with the stack
penalty), execution to 14, cost to 12. A single severe red flag in
the fake-backtest bucket can drop a clean 100 to a C; stacking
multiple flags reaches F (< 40) without any single deduction being
unrealistically large.

### Score-to-grade mapping

From `TRUST_SCORE_GRADES` in `app/strategy_engine/reliability/constants.py`
(re-exported through `truth/constants.py`):

| Grade | Score range |
|-------|-------------|
| A | 85-100 |
| B | 70-84 |
| C | 55-69 |
| D | 40-54 |
| F | 0-39 |

Implemented by the private `_grade_for(score: int) -> Grade` helper.

### Risk-level mapping

Risk level is **orthogonal to grade** — it counts how many warnings
fired across all four buckets. From `RISK_LEVEL_THRESHOLDS = (1, 3, 5)`
in `truth/constants.py`:

| Total warnings | Risk level |
|----------------|------------|
| 0-1 | `low` |
| 2-3 | `medium` |
| 4-5 | `high` |
| 6+ | `extreme` |

Implemented by `_risk_level(*, warning_count: int)`.

### Verdict mapping

From `TRUTH_VERDICTS` in `truth/constants.py`:

| Grade | Verdict |
|-------|---------|
| A, B | `"Ready for paper trading"` |
| C, D | `"Needs improvement"` |
| F | `"Not ready"` |

Three bands so the UI can show a single primary call-to-action without
parsing every warning.

## Detection rules

Twelve inspections, with the constants they consult. All thresholds
are imported from `truth/constants.py` (some re-exported from the
Phase 4 reliability constants for cohesion).

### Bucket: fake-backtest

1. **High win-rate risk** — fires when
   `win_rate > HIGH_WIN_RATE_WARNING_THRESHOLD` (`0.85`) AND
   (profit factor below `SUSPICIOUS_WIN_RATE_PROFIT_FACTOR` (`1.5`)
   OR average loss dominates average win). Catches the "looks great
   on paper, fails badly live" pattern.
2. **Low trade count** — `total_trades < LOW_TRADE_COUNT_THRESHOLD`
   (`30`). Statistics below this threshold are too noisy to trust.
3. **Poor risk-reward** — `avg_win / avg_loss < BAD_RISK_REWARD_RATIO`
   (`1.0`). The strategy needs an unrealistically high win rate just
   to break even.
4. **Avg-loss dominates win (asymmetry trap)** —
   `avg_loss > AVG_LOSS_RATIO_THRESHOLD * avg_win` (`1.5x`). Rare
   large losers can wipe out many small winners.
5. **High max drawdown** — `max_drawdown > HIGH_DRAWDOWN_THRESHOLD`
   (`0.30`, i.e. 30 %). Few traders can sit through a peak-to-trough
   decline this large.
6. **Weak profit factor** — profit factor below
   `MARGINAL_PROFIT_FACTOR` (`1.3`). Small slippage or cost changes
   can flip the strategy negative.

### Bucket: overfitting

7. **Out-of-sample degradation** —
   `reliability.out_of_sample.degradation_percent >
   OOS_DEGRADATION_WARNING_THRESHOLD` (`0.25`, i.e. 25 %). Skipped
   entirely when `reliability.out_of_sample is None`.
8. **Fragile parameters** —
   `reliability.sensitivity.fragile is True`. Skipped entirely when
   `reliability.sensitivity is None`.
11. **Overfitting stack** — fires only when 7 AND 8 both fired in
    the same evaluation. The combined evidence is stronger than
    either signal alone, so it costs an extra
    `DEDUCT_OVERFITTING_STACK` (`8`) on top of the individual
    deductions.

### Bucket: execution

10. **Optimistic same-bar resolution** —
    `ambiguity_mode is AmbiguityMode.OPTIMISTIC`. Best-case fill
    ordering rarely matches live execution.
12. **Unrealistic frictionless execution** — all three of
    `cost_settings.fixed_cost`, `cost_settings.percent_cost`, and
    `cost_settings.slippage_percent` are zero. The backtest assumes
    free trading.

### Bucket: cost

9. **Cost impact** — fires under either of two paths:
   * **Explicit:** `pre_cost_pnl is not None` AND `pre_cost_pnl > 0`
     AND `(pre_cost_pnl - backtest.total_pnl) / pre_cost_pnl >
     COST_IMPACT_FRACTION_THRESHOLD` (`0.20`).
   * **Heuristic:** costs configured (not frictionless) AND profit
     factor `>= 1.0` AND `< MARGINAL_PROFIT_FACTOR` (`1.3`). Below
     1.0 the unprofitability check fires instead — costs are not the
     headline issue.

> Numbering note: the source code groups rules by bucket rather than
> by index, so rule 11 (overfitting stack) is implemented just after
> rule 8, and rule 9 (cost impact) is implemented after rules 10 and
> 12. The numbering above matches the bucket-aligned comment headers
> in `truth_score.py`.

### Strengths

`evaluate_strategy_truth` also emits positive observations:

- Sufficient trade count for statistical confidence (≥ 30).
- Strong profit factor (`>= SUSPICIOUS_WIN_RATE_PROFIT_FACTOR`).
- Drawdown is contained (`<= HIGH_DRAWDOWN_THRESHOLD / 2`).
- Out-of-sample performance held up (OOS sub-result present and
  rule 7 did not fire).
- Robust to ±20 % parameter perturbations (sensitivity sub-result
  present and rule 8 did not fire).
- Realistic costs + conservative same-bar resolution.

## Integration points

### Reads from

- `BacktestResult` — Phase 3, `app/strategy_engine/backtest/runner.py`.
  Consumed via `reliability.backtest`.
- `ReliabilityReport` — Phase 4,
  `app/strategy_engine/reliability/reliability_report.py`.
  Optional sub-results `out_of_sample` and `sensitivity` gate rules
  7 and 8 respectively.
- `CostSettings` — `app/strategy_engine/backtest/costs.py`.
- `AmbiguityMode` — `app/strategy_engine/backtest/runner.py`.

### Used by

- **Backtest API endpoint** —
  `app/strategy_engine/api/backtest.py` orchestrates the
  backtest → reliability → truth pipeline and returns all three in
  the `BacktestRunResponse` (`truth: TruthReport | None`).
- **Broker Execution Guard** —
  `app/strategy_engine/broker_guard/checks.py::check_truth_score`
  blocks live deployment when `truth.truth_score <
  MIN_TRUTH_SCORE_FOR_LIVE` (`55`). A separate `check_truth_risk_level`
  surfaces non-blocking signals for high/extreme risk.
- **Advisor + Doctor** —
  `app/strategy_engine/advisor/advisor.py` and `doctor.py` both
  accept `truth: TruthReport | None` and translate the score and
  warnings into actionable advice / problems. The
  `LLMProvider.explain_truth_score` method
  (`advisor/llm_provider.py`) feeds the truth report into the LLM
  explainer.

> Note: the Strategy Coach (`app/strategy_engine/coach/generator.py`,
> `generate_health_card`) does **not** consume `TruthReport` directly.
> Coach and Truth are sibling layers in the API response — the API
> orchestrator runs both against the same backtest+reliability inputs.

### Frontend

- `frontend/src/components/strategies/strategy-truth-panel.tsx`
  exports `StrategyTruthPanel` and the `TruthReportPayload` /
  `TruthGrade` / `TruthRiskLevel` types. The wire shape uses the
  camelCase aliases from `TruthReport` (e.g. `truthScore`,
  `fakeBacktestWarnings`).
- Mounted on the backtest result page at
  `frontend/src/app/(dashboard)/strategies/[id]/backtest/page.tsx`
  alongside the trust panel and market-regime panel.

## Hinglish UI examples

Sample message strings produced by the engine (English, but routed
through the Truth Panel which renders them in user-facing copy):

- _High win-rate trap (rule 1):_
  > "Win rate is high (88.0 %), but average loss is much larger than
  > average win or profit factor is weak. This strategy may look good
  > but can fail badly in live conditions."

- _OOS degradation (rule 7):_
  > "Training result is strong, but out-of-sample result dropped
  > 32.5 %. Overfitting risk is high."

- _Cost impact, explicit path (rule 9):_
  > "Cost-adjusted performance is weak: charges and slippage took
  > 27.4 % of gross profit (1500.00 → 1089.00)."

- _Frictionless execution (rule 12):_
  > "Cost settings are zero — the backtest assumes free trading.
  > Real fills include broker fees and slippage."

> Hinglish phrasing is generated by the consuming layer (Strategy
> Truth Panel / Coach copy / Hinglish summary on regime), not by the
> Truth Engine itself. The engine's strings are English-only.

## Test coverage

`backend/tests/strategy_engine/truth/` — directory of focused test
modules. **16 tests collected** at the time of writing.

| Test file | What it pins |
|-----------|--------------|
| `test_good_strategy_high_score.py` | Clean strategy lands in grade A with no warnings; clean strategy outscores a strategy with a single red flag. |
| `test_high_win_rate_poor_rr_warning.py` | Rule 1 fires for the high-win-rate trap with dominant avg-loss. |
| `test_low_trade_count_reduces_score.py` | Rule 2 deducts and emits a warning. |
| `test_oos_degradation_overfitting.py` | Rule 7 fires above threshold; below threshold does not fire; rule 11 stack penalty applies when 7 + 8 both fire. |
| `test_cost_impact_warning.py` | Rule 9 explicit path with `pre_cost_pnl`; heuristic path with marginal profit factor; no warning when above marginal threshold. |
| `test_grade_verdict_risk_mapping.py` | Grade ranges cover 0-100 contiguously; every grade has a verdict; risk thresholds monotonic and non-overlapping; risk `low` when no warnings; risk `extreme` when many buckets fire. |
| `test_evaluate_does_not_mutate_inputs.py` | Round-trip equality on backtest + reliability inputs after the engine runs (frozen-Pydantic enforcement check). |

Critical invariants pinned by the suite:

- Determinism (frozen models + no clock/network ⇒ identical inputs
  produce identical reports).
- Immutability of inputs (round-trip equality).
- Grade and verdict tables cover the full score domain.
- Risk-level bands are monotonic and don't overlap.
- Each rule's individual deduction and warning attribution.

## Limitations

- The Truth Engine **does not run a backtest**. It consumes a
  pre-computed `ReliabilityReport`. Calling code is responsible for
  the backtest + reliability pipeline.
- The engine **cannot guarantee** a strategy will be profitable in
  live trading — it can only flag patterns historically associated
  with fake-looking results.
- A high truth score is **necessary but not sufficient** for live
  deployment. The Broker Execution Guard combines truth with a trust
  score, kill-switch state, and other gates before allowing real
  orders.
- The cost-impact rule's heuristic path (no `pre_cost_pnl`) is a
  proxy, not a measurement. Pass `pre_cost_pnl` for the explicit
  comparison whenever the gross figure is available.
- `strategy: StrategyJSON` is currently a reserved input — no rule
  consults it yet. Treat it as part of the contract for forward
  compatibility, not as a behaviour-driving parameter today.

## Future enhancements

- TODO: walk-forward truth validation. The reliability report
  already exposes `walk_forward`; no current rule consults it.
- TODO: regime-conditional truth scoring. Phase 8 produces a
  `RegimeReport`; pairing regime context with the existing rules
  could refine the verdict (e.g. demote a strategy whose backtest
  ran exclusively in a trending regime).
- TODO: live deviation feedback loop — feed live vs backtest
  deviation back into the truth score so a strategy that is drifting
  in production is reflected in subsequent evaluations.
- TODO: rule consumption of `strategy.execution` and indicator
  count, leveraging the already-reserved `strategy` parameter.
