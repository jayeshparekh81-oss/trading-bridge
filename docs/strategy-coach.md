# Strategy Coach

Phase X of the AI trading system (commit `fa56af4`). Internal developer
reference — not user-facing copy.

## Purpose

Beginner-friendly explanation of every backtest metric in simple
Hinglish. The coach takes a Phase 3 `BacktestResult` (and optionally a
Phase 4 `ReliabilityReport`) and emits a frozen `StrategyHealthCard`
that answers, for each of seven metrics:

> "Yeh value kya hai, kahan chahiye, aur agar kharaab hai to kya karoon?"

The card pairs the user's value with a four-tier ideal range and a
template-driven Hinglish tip. The coach is **pure, deterministic,
AI-free**: no LLM calls, no network, no clock reads. Same inputs
always produce the same `StrategyHealthCard`.

> Sibling layer to the Strategy Truth Engine. The coach **does not
> consume** `TruthReport` — both layers run independently in the
> backtest API orchestrator and target different audiences (coach is
> education-first; truth is verification-first).

## Module location

`backend/app/strategy_engine/coach/`

| File | Purpose |
|------|---------|
| `__init__.py` | Public surface: `generate_health_card`, `StrategyHealthCard`, `MetricGrade`, `MetricGradeLevel`, `OverallGrade`. |
| `models.py` | Frozen Pydantic models — `MetricGrade`, `StrategyHealthCard` — plus the `MetricGradeLevel` and `OverallGrade` literals. |
| `generator.py` | `generate_health_card()` orchestrator. Per-metric builders, derived-metric helpers (`_risk_reward_value`, `_expectancy_percent`, `_recovery_factor_value`), overall-score → A-F mapping, learning-tips assembly, and the locked `_OVERALL_SUMMARY` / `_NEXT_STEPS` Hinglish tables. |
| `rubric.py` | Locked benchmark thresholds and `classify_*` pure functions for the seven metrics. Re-exports the eight `*_RUBRIC` records and `GRADE_WEIGHTS`. |
| `tips.py` | Hinglish tip templates — one generator per metric (`win_rate_tip`, `profit_factor_tip`, …). ASCII-safe text plus `%` and `₹` only. |

## Public API

Real signature from `app/strategy_engine/coach/generator.py`:

```python
def generate_health_card(
    backtest: BacktestResult,
    reliability: ReliabilityReport | None = None,
) -> StrategyHealthCard: ...
```

### Inputs

| Parameter | Type | Source module |
|-----------|------|----------------|
| `backtest` | `BacktestResult` | `app.strategy_engine.backtest.runner` |
| `reliability` | `ReliabilityReport \| None` | `app.strategy_engine.reliability.reliability_report` |

`reliability` is optional; when passed, its `trust_score.score` enters
the `learning_tips` list (see [Learning tips](#learning-tips)). Every
gate computation works without it — the seven metric grades come
purely from `backtest`.

### Output

`StrategyHealthCard` — frozen Pydantic model, snake_case fields, no
camelCase aliases (the wire shape is the attribute shape).

### Example

```python
from app.strategy_engine.coach import generate_health_card
from app.strategy_engine.reliability import build_reliability_report
from app.strategy_engine.backtest import run_backtest

backtest = run_backtest(backtest_input)
reliability = build_reliability_report(
    strategy=strategy_json,
    candles=candles,
    initial_capital=100_000.0,
    quantity=1.0,
    cost_settings=cost_settings,
)
card = generate_health_card(backtest, reliability=reliability)

if card.overall_grade in {"A", "B"}:
    proceed_to_paper_trading()
```

The actual orchestration in production lives in
`app/strategy_engine/api/backtest.py` (the
`POST /api/strategies/{id}/backtest` endpoint), which runs backtest →
reliability → coach in that order and returns the card alongside the
truth and regime reports.

## Output schema

Field shapes from `coach/models.py`:

### `StrategyHealthCard`

| Field | Type | Notes |
|-------|------|-------|
| `overall_grade` | `Literal["A","B","C","D","F"]` (`OverallGrade`) | Roll-up of the seven metric grades — see [Overall grade calculation](#overall-grade-calculation). |
| `overall_summary_hinglish` | `str` (1-512 chars) | One of five locked phrases keyed by `overall_grade` (see [`_OVERALL_SUMMARY`](#overall-summary-table)). |
| `metric_grades` | `tuple[MetricGrade, ...]` | Always seven entries in registration order: win-rate, profit-factor, max-drawdown, risk-reward, total-trades, expectancy, recovery-factor. |
| `learning_tips` | `tuple[str, ...]` | Coach-derived advisory lines — see [Learning tips](#learning-tips). |
| `next_steps_hinglish` | `tuple[str, ...]` | One of five locked tuples keyed by `overall_grade` (see [`_NEXT_STEPS`](#next-steps-mapping)). |

`model_config = ConfigDict(frozen=True, extra="forbid")` — the card is
immutable post-construction; serialisation matches attribute names.

### `MetricGrade`

| Field | Type | Notes |
|-------|------|-------|
| `metric_name` | `str` (1-64 chars) | Display name, e.g. `"Win Rate"`. |
| `your_value` | `float` | Numeric value the user achieved. Infinity is clamped to `1e9` for JSON-safe display when the underlying metric can be `inf`. |
| `unit` | `str` (≤ 16 chars) | Display suffix — `"%"`, `"x"`, `"trades"`, or `""`. The model doesn't render; the UI does. |
| `ideal_excellent` | `str` (1-64 chars) | Range string for the EXCELLENT band. |
| `ideal_good` | `str` (1-64 chars) | Range string for the GOOD band. |
| `ideal_acceptable` | `str` (1-64 chars) | Range string for the ACCEPTABLE band. |
| `ideal_concerning` | `str` (1-64 chars) | Range string for the CONCERNING band. |
| `your_grade` | `Literal["EXCELLENT","GOOD","ACCEPTABLE","CONCERNING"]` (`MetricGradeLevel`) | The user's grade for this metric. |
| `hinglish_tip` | `str` (1-512 chars) | Template-driven tip — see [Hinglish tip system](#hinglish-tip-system). |

## Seven metrics with locked benchmarks

Every classifier and rubric record below comes from
`coach/rubric.py`. Bands are inclusive on the lower bound where shown.

### 1. Win Rate (`classify_win_rate`)

| Range (%) | Grade |
|-----------|-------|
| 50-65 (inclusive) | EXCELLENT |
| 45-50 or 65-75 | GOOD |
| 40-45 or 75-85 | ACCEPTABLE |
| `<40` or `>85` | CONCERNING |

`WIN_RATE_RUBRIC.unit = "%"`. The ranges are deliberately bell-shaped:
extremes (very low or suspiciously high) are concerning. Above 85 % is
treated as an overfitting/curve-fitting tell — the CONCERNING tip
calls this out explicitly.

### 2. Profit Factor (`classify_profit_factor`)

| Value | Grade |
|-------|-------|
| `inf` (no losses) | EXCELLENT |
| `> 2.0` | EXCELLENT |
| `1.5 - 2.0` | GOOD |
| `1.2 - 1.5` | ACCEPTABLE |
| `< 1.2` | CONCERNING |

`PROFIT_FACTOR_RUBRIC.unit = "x"`. `inf` is recognised as EXCELLENT
but the EXCELLENT tip warns to verify trade count and sample period —
real strategies rarely have zero losses.

### 3. Max Drawdown (`classify_max_drawdown`)

| Range (%) | Grade |
|-----------|-------|
| `< 10` | EXCELLENT |
| `10 - 15` | GOOD |
| `15 - 25` | ACCEPTABLE |
| `> 25` | CONCERNING |

`MAX_DRAWDOWN_RUBRIC.unit = "%"`. The CONCERNING tip includes a
concrete `₹` example — `"har ₹100 par ~₹{value} loss"` — so the
operator feels the real-money impact.

### 4. Risk-Reward (`classify_risk_reward`)

`avg_win / avg_loss` (Phase 3 stores `average_loss` as a magnitude;
`generator._risk_reward_value` handles the zero-loss edge case by
returning `inf` if there's a positive average win, otherwise `0.0`).

| Value | Grade |
|-------|-------|
| `inf` or `> 2.0` | EXCELLENT |
| `1.5 - 2.0` | GOOD |
| `1.0 - 1.5` | ACCEPTABLE |
| `< 1.0` | CONCERNING |

`RISK_REWARD_RUBRIC.unit = "x"`.

### 5. Total Trades (`classify_total_trades`)

| Count | Grade |
|-------|-------|
| `> 100` | EXCELLENT |
| `50 - 100` | GOOD |
| `30 - 50` | ACCEPTABLE |
| `< 30` | CONCERNING |

`TOTAL_TRADES_RUBRIC.unit = "trades"`. Below 30 the sample is treated
as too small for any conclusion; the tip frames results as
"luck-based" until more data arrives.

### 6. Expectancy (`classify_expectancy`)

Computed via `_expectancy_percent`:
`backtest.total_return_percent / backtest.total_trades` (per-trade
percent return; `0.0` when `total_trades == 0`).

| Value (% per trade) | Grade |
|---------------------|-------|
| `> 0.5` | EXCELLENT |
| `0 - 0.5` (exclusive of 0) | GOOD |
| `-0.05 - 0` (inclusive on the lower side) | ACCEPTABLE |
| `< -0.05` | CONCERNING |

`EXPECTANCY_RUBRIC.unit = "%"`. The "near zero" ACCEPTABLE band
captures break-even strategies that costs would push negative.

### 7. Recovery Factor (`classify_recovery_factor`)

Computed via `_recovery_factor_value`:
`total_return_percent / max_drawdown_percent`. `inf` only when
drawdown is exactly zero AND the strategy is profitable; `0.0` when
both are zero (flat strategy).

| Value | Grade |
|-------|-------|
| `inf` or `> 5.0` | EXCELLENT |
| `3.0 - 5.0` | GOOD |
| `1.0 - 3.0` | ACCEPTABLE |
| `< 1.0` | CONCERNING |

`RECOVERY_FACTOR_RUBRIC.unit = "x"`.

## Overall grade calculation

`generator._overall_score` and `generator._grade_for`:

1. Map each metric grade to its weight from
   `rubric.GRADE_WEIGHTS`:

   | Grade | Weight |
   |-------|--------|
   | `EXCELLENT` | 4 |
   | `GOOD` | 3 |
   | `ACCEPTABLE` | 2 |
   | `CONCERNING` | 0 |

2. `average = sum(weights) / 7`.
3. `overall_score = average × 25` → produces a value in `[0, 100]`.
4. Map the score to a letter grade:

   | Score | Grade |
   |-------|-------|
   | `>= 85` | A |
   | `70 - 84` | B |
   | `55 - 69` | C |
   | `40 - 54` | D |
   | `< 40` | F |

> Note the multiplier — `EXCELLENT × 25 = 100` per metric, so a
> hypothetical all-EXCELLENT card scores 100. The CONCERNING weight is
> `0`, not `1`, so a single CONCERNING metric drops the average by
> `4/7 ≈ 14.3` points relative to a GOOD-everywhere card.

### Overall summary table

`generator._OVERALL_SUMMARY` (`dict[OverallGrade, str]`) — verbatim
strings:

| Grade | `overall_summary_hinglish` |
|-------|----------------------------|
| A | `"Strategy strong hai - paper trading shuru karo. Real money lagane se pehle 7 sessions complete karo."` |
| B | `"Strategy theek hai - 1-2 metrics mein improvements kar sakte ho. Doctor module check karo."` |
| C | `"Strategy workable but kuch weak metrics hain. Pehle inhe fix karo phir paper trading."` |
| D | `"Strategy mein significant issues hain. Risk parameters aur entry rules re-check karo."` |
| F | `"Strategy abhi reliable nahi hai. Risk parameters aur entry rules re-check karo - re-design ki zaroorat ho sakti hai."` |

### Next steps mapping

`generator._NEXT_STEPS` (`dict[OverallGrade, tuple[str, ...]]`).
Each tuple currently holds a single string:

| Grade | `next_steps_hinglish` |
|-------|------------------------|
| A | `("Strategy strong hai. Paper trading shuru karo - 7 sessions complete karo.",)` |
| B | `("Strategy theek hai. Doctor module se improvements dekho.",)` |
| C | `("Pehle weak metrics fix karo. Phir paper trading.",)` |
| D | `("Pehle weak metrics fix karo. Phir paper trading.",)` |
| F | `("Strategy abhi reliable nahi. Risk parameters re-check karo.",)` |

> The `tuple[str, ...]` shape leaves room for future multi-step
> guidance per grade without changing the public model.

## Hinglish tip system

`coach/tips.py` exports one generator per metric — no abstract
templating engine, just plain f-strings. Each generator takes
`(grade: MetricGradeLevel, value)` and returns one short tip
(typically 1-2 sentences). All output is ASCII-safe with `%` and `₹`
the only non-ASCII characters allowed; the
`test_all_card_strings_are_ascii_plus_rupee_and_percent` test pins
this guarantee.

Representative templates (verbatim from `tips.py`):

- **Win rate, EXCELLENT**:
  ```python
  return (
      f"Aapki strategy ne {value_pct:.1f}% baar profit kiya - sweet spot "
      "50-65% mein hai. Realistic aur sustainable."
  )
  ```

- **Profit factor, GOOD**:
  ```python
  return (
      f"Profit factor {value:.2f}x achha hai. Aap ₹1 risk leke "
      f"₹{value:.2f} kama rahe ho. >2.0 excellent hota hai."
  )
  ```

- **Max drawdown, CONCERNING** (with concrete `₹` example):
  ```python
  rs_per_100 = round(value_pct)
  return (
      f"Worst loss period mein {value_pct:.1f}% gawaaya - har ₹100 par "
      f"~₹{rs_per_100} loss. Zyada hai, <15% ideal."
  )
  ```

- **Risk-reward, CONCERNING**:
  ```python
  return (
      f"Average loss average win se bada hai (RR {value:.2f}x). Stop loss "
      "tighter ya target wider karo."
  )
  ```

- **Total trades, CONCERNING**:
  ```python
  return (
      f"Sirf {count} trades - sample chhota hai, results luck-based ho "
      "sakte hain. Longer period par test karo."
  )
  ```

Special cases handled by individual generators:

- `profit_factor_tip` and `risk_reward_tip` detect `value == float("inf")`
  in the EXCELLENT branch and switch to a "verify your data" message
  rather than printing infinity.
- `max_drawdown_tip` and `expectancy_tip` include a `₹`-denominated
  concrete example in the CONCERNING tier so the operator sees the
  real-money impact.

### Learning tips

`generator._learning_tips` produces the `learning_tips` tuple from
two signals:

1. **Concerning metrics call-out.** If any of the seven metric grades
   is `CONCERNING`, the coach prepends:
   `f"Focus areas: {names}. In metrics ko fix karne se overall grade improve hoga."`
2. **Reliability surfacing.** If `reliability is not None`, the coach
   adds either:
   - `f"Reliability trust score {trust}/100 hai - paper trading se pehle Strategy Doctor se diagnose karwao."` when `trust < 70`, or
   - `f"Reliability trust score {trust}/100 strong hai. Backtest ke result par bharosa kar sakte ho."` otherwise.
3. **Fallback.** If neither signal fires, the coach emits the generic
   maintenance tip:
   `"Strategy ke har metric ko time-time pe re-check karo. Markets change hote hain - rules update karte raho."`

The list is always non-empty — useful when the UI needs at least one
line of advisory copy.

## Integration points

### Reads from

- `BacktestResult` — Phase 3, `app/strategy_engine/backtest/runner.py`.
  Source of `win_rate`, `profit_factor`, `max_drawdown`,
  `average_win`, `average_loss`, `total_trades`,
  `total_return_percent`.
- `ReliabilityReport` (optional) — Phase 4,
  `app/strategy_engine/reliability/reliability_report.py`.
  Only `reliability.trust_score.score` is consumed, and only to
  enrich `learning_tips`. The seven metric grades never depend on it.

### Used by

- **Backtest API endpoint** —
  `app/strategy_engine/api/backtest.py` calls
  `generate_health_card(backtest_result, reliability=reliability_report)`
  and returns the result as `BacktestRunResponse.health_card`. The
  field is non-optional in the response (a card is always produced
  when a backtest succeeds).
- **Frontend `StrategyCoachCard`** —
  `frontend/src/components/strategies/strategy-coach-card.tsx`. The
  wire shape is snake_case (the model has no camelCase aliases),
  matching the response section's `health_card` key in the API
  payload.

> The coach does **not** read or write any other strategy-engine
> module's state; it is a leaf consumer of `BacktestResult` /
> `ReliabilityReport`.

## Hinglish UI examples

Sample tip strings produced by the coach (rendered verbatim by the
frontend `StrategyCoachCard`):

- _Profit factor, EXCELLENT (finite):_
  > "Profit factor 2.45x excellent hai. Aap ₹1 risk leke ₹2.45 kama
  > rahe ho on average."

- _Max drawdown, CONCERNING:_
  > "Worst loss period mein 30.0% gawaaya - har ₹100 par ~₹30 loss.
  > Zyada hai, <15% ideal."

- _Win rate, CONCERNING (above 85 %):_
  > "92.0% bahut zyada hai - real markets mein sustainable nahi,
  > overfitting ka sign."

- _Total trades, CONCERNING:_
  > "Sirf 15 trades - sample chhota hai, results luck-based ho sakte
  > hain. Longer period par test karo."

The overall summary and next-step strings are routed straight through
from `_OVERALL_SUMMARY` / `_NEXT_STEPS` (no value interpolation).

## Test coverage

`backend/tests/strategy_engine/coach/` — single test module
`test_strategy_coach.py`. **12 tests collected** at the time of
writing.

Test names (collected via `pytest --collect-only`):

| Test | What it pins |
|------|--------------|
| `test_excellent_strategy_lands_in_grade_a_with_all_metrics_excellent` | All-EXCELLENT input rolls up to overall grade A. |
| `test_high_win_rate_with_bad_risk_reward_concerns_win_rate_and_drops_grade` | 90 %+ win rate paired with sub-1 risk-reward yields a CONCERNING win-rate row and demotes the overall grade. |
| `test_fifteen_trades_marks_total_trades_concerning` | Below-threshold trade count classifies CONCERNING. |
| `test_thirty_percent_drawdown_concerning_with_rupee_example_in_tip` | The CONCERNING drawdown tip carries a `₹` example. |
| `test_negative_expectancy_marks_concerning_and_mentions_loss_in_tip` | Negative expectancy tip mentions the per-trade loss. |
| `test_card_produced_with_reliability_includes_trust_learning_tip` | Passing `reliability` adds a trust-score line to `learning_tips`. |
| `test_card_produced_without_reliability_still_has_learning_tips` | The fallback maintenance tip fires when neither concerning-metric nor reliability signals are present. |
| `test_profit_factor_and_drawdown_tips_use_rupee_for_monetary_examples` | `₹` appears in the relevant monetary-context tips. |
| `test_two_runs_produce_identical_cards` | Determinism — back-to-back calls produce equal `StrategyHealthCard` instances. |
| `test_health_card_round_trips_through_pydantic_validation` | `model_dump_json` → `model_validate_json` is a no-op on a real card. |
| `test_no_llm_or_network_imports_in_coach_package` | AST-walk of every coach `*.py` rejects forbidden imports (LLM SDKs, HTTP libs, `socket`/`websocket`). Pins the "pure deterministic" guarantee. |
| `test_all_card_strings_are_ascii_plus_rupee_and_percent` | Every string field on a generated card consists only of ASCII characters plus `%` and `₹`. |

Critical invariants pinned by the suite:

- **Determinism** — frozen models + no clock/network ⇒ identical
  inputs produce identical cards.
- **Encoding safety** — output strings are ASCII-safe save for `%`
  and `₹`, so logs / wire / UI never have to round-trip through
  exotic encodings.
- **Dependency hygiene** — AST inspection forbids LLM/network
  imports across the whole package.
- **JSON round-trip** — every `MetricGrade.your_value` stays a
  finite float (the `inf` clamp to `1e9` is the mechanism).

## Limitations

- The coach **does not run a backtest**. It consumes a pre-computed
  `BacktestResult`; calling code is responsible for the backtest
  pipeline.
- The coach **does not consume `TruthReport`**. Coach and Truth are
  sibling layers; the API orchestrator runs both against the same
  inputs and returns each in its own response section.
- Benchmarks are **hardcoded** in `rubric.py` and not user-
  configurable. A given account can't, e.g., shift the EXCELLENT win-
  rate band to 60-75 % without code changes.
- Hinglish tips are **templates with placeholders**, not generated
  text. The coach picks one of four template branches per metric and
  formats the user's value into it.
- A high overall grade is **necessary but not sufficient** for live
  deployment. The Broker Execution Guard combines other signals
  (truth, trust, kill-switch state) before allowing real orders.
- Infinity values on `your_value` are clamped to `1e9` for JSON-safe
  serialisation. Consumers that care about the genuine `inf` case
  must read `your_grade == "EXCELLENT"` plus the tip text rather than
  inspecting the numeric field.

## Future enhancements

- TODO: User-configurable benchmark profiles
  (aggressive / conservative / scalper). Today every user sees the
  same `*_RUBRIC` thresholds.
- TODO: Multi-language support (Gujarati, Tamil, Bengali). The
  Hinglish templates in `tips.py` would need parallel tables and a
  language-selector arg on `generate_health_card`.
- TODO: Personalisation based on user trading history (e.g., adjust
  `total_trades` thresholds for users who only trade weekly options).
- TODO: Coach feedback loop. The card today is a one-way artefact;
  the `learning_tips` could be informed by repeated CONCERNING grades
  across the user's recent strategies.
- TODO: Cross-engine consistency check. Coach and Truth share the
  `OverallGrade` literal vocabulary but compute it independently — a
  cross-validation rule could surface when the two disagree
  dramatically (coach A vs truth F or vice versa).
