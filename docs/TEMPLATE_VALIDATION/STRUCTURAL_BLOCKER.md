# Queue Y — Structural Blocker: Templates Are Not Engine-Callable

**Discovered:** 2026-05-19, Phase 2 of `chore/template-validation-sprint`
**Impact:** Validation sprint cannot proceed for any template (Phase 1 OR batch-activated).
**Root cause:** Templates store documentation-shape `config_json` (prose conditions); the backtest engine requires structured Pydantic `StrategyJSON`. No translator exists.

---

## What the templates store

`backend/data/strategy_templates_seed.json` `config_json` example (batch-activated `donchian-channel-breakout`):

```json
{
  "indicators": ["donchian_channel_20", "donchian_channel_10", "adx_14"],
  "entry_long": {
    "condition": "close > 20-bar donchian upper band (new 20-bar high) AND adx_14 > 20"
  },
  "exit_long": {
    "condition": "close < 10-bar donchian lower band (Turtle 20/10 asymmetric trail)"
  },
  "stop_loss_pct": 2.0,
  "take_profit_pct": 6.0,
  "position_sizing": {"method": "fixed_amount", "amount_inr": 75000},
  "max_open_positions": 1,
  "trading_hours": {"start": "09:30", "end": "15:00"}
}
```

The "Phase 1 original" templates use the **same** shape:

```json
{
  "indicators": ["ema_9", "ema_21"],
  "entry_long": {"condition": "ema_9 crosses above ema_21"},
  "exit_long":  {"condition": "ema_9 crosses below ema_21"},
  ...
}
```

Key properties:
- `indicators` is `list[str]` (registry id references as strings).
- `entry_long.condition`, `exit_long.condition` are **prose strings** describing the rule.
- No `id`, `name`, `mode`, `execution`, structured `entry/exit/risk` blocks.

The shape is validated by `app/templates/validator.py::validate_config_json`, which only checks structural keys/types — it does NOT parse the condition strings.

## What the backtest engine requires

`backend/app/strategy_engine/schema/strategy.py::StrategyJSON` is a strict, frozen Pydantic model:

```python
class StrategyJSON(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)
    id: str
    name: str
    mode: StrategyMode
    version: int = 1
    indicators: list[IndicatorConfig]            # list of dicts {id, type, params}, NOT strings
    entry: EntryRules                            # structured conditions: IndicatorCondition / CandleCondition / TimeCondition / PriceCondition
    exit: ExitRules
    risk: RiskRules
    execution: ExecutionConfig
```

`IndicatorConfig`:
```python
class IndicatorConfig(BaseModel):
    id: str        # e.g. "ema_20"
    type: str      # e.g. "ema"
    params: dict[str, Any]
```

`IndicatorCondition` (one of the structured condition variants):
```python
class IndicatorCondition(BaseModel):
    type: Literal["indicator_compare"]
    left: str                # indicator instance id
    op: IndicatorConditionOp # e.g. CROSSES_ABOVE, GT, LT, ...
    right: str | None        # peer indicator id OR None when compared to scalar
    value: float | None
```

## Concrete failure (reproducible)

```python
from app.strategy_engine.schema.strategy import StrategyJSON
import json

template_cfg = {
  "indicators": ["donchian_channel_20", "donchian_channel_10", "adx_14"],
  "entry_long": {"condition": "close > 20-bar donchian upper band ... AND adx_14 > 20"},
  ...
}
StrategyJSON(**template_cfg)
```
Produces:
```
ValidationError: 16 validation errors for StrategyJSON
  id            Field required
  name          Field required
  mode          Field required
  execution     Field required
  entry         Field required
  exit          Field required
  indicators.0  Input should be a valid dictionary or instance of IndicatorConfig
                [input was 'donchian_channel_20' (str)]
  ...
```

Every one of the 113 catalog templates — Phase 1 and batch alike — fails identically because the *shape* is wrong, not the *content*.

## Translator: planned but not built

`backend/app/templates/clone_service.py` (lines 28–31) explicitly says:

> Phase 1 deliberately doesn't try to auto-populate the strategy's execution-engine fields from `config_json`; that's a Phase 7-8 backtest-engine concern.

So when a user clicks "use this template" on the UI, `clone_service` creates a `Strategy` row with **name + user_id only** — it does NOT translate the template into engine-callable form. The user is expected to manually re-author the strategy in the builder UI before backtesting or live-trading it.

That means **no template — Phase 1 or batch — is currently runnable in the backtest engine without manual rebuilding by a user.**

## What this means for the seed loader / router mount

1. **No template loaded via the seed loader is engine-callable.**
   - Cloning a template produces a manually-completable shell, not a working strategy.
   - Backtesting a template would require the user to first rebuild it in the canonical shape.

2. **The 17 batch-activated templates are no more (and no less) "validated" than the 12 Phase 1 templates.**
   - All 29 active rows in `origin/main` are documentation; none have ever passed a backtest.
   - The "validate the 14" framing of Queue Y presumes a runnable engine path that does not yet exist.

3. **Router mount can still proceed safely** for the backtest extension `/api/backtest` endpoint, because:
   - The endpoint receives a fully-formed `BacktestEnqueueRequest` (which already carries a canonical `strategy_json` or strategy_id pointing to a real Strategy row built via the builder UI).
   - It does NOT auto-pull from `strategy_templates_seed.json`.
   - Templates only become input to the engine after a user clones one and manually builds it out.

The seed loader's `is_active` flag is therefore a **catalog-visibility** flag, not an "engine-ready" flag. Risk to live users: a customer clicks "use template" → clone_service creates a half-empty Strategy → the customer must manually complete it → no auto-run path. Risk is bounded by the manual-completion gate.

## Recommended actions (founder's call)

### Path A — Build the translator (~3–5 days)
- Author a `template_to_strategy_json()` function in `app/templates/translator.py`.
- Maintain a condition-string DSL parser (or a lookup table from the 113-template prose to canonical IndicatorCondition tuples) — this is the heavier lift.
- Re-run Queue Y harness on all 29 active templates (12 + 17). Resulting PASS/WARN/FAIL drives the seed `is_active` patch.
- THEN router mount with confidence.

### Path B — Deactivate the 17 in seed, ship anyway
- Cosmetically, the customer-facing "explore templates" page lists only the 12 Phase 1 templates until the translator ships.
- Risk: customers who saw the 17 in the UI today may be confused tomorrow when they vanish.
- Mitigation: leave the 17 in catalog with a "coming soon" copy + `is_active=false`.

### Path C — Accept current state, document the gap
- Keep all 29 active in catalog. Document on each template page "live trading + auto-backtest not yet available — copy the rules into the builder manually."
- Router mount goes ahead. Customers expecting one-click validation will hit a UX gap.

### Recommendation: **Path B for ship safety + Path A in parallel**
- Today (no engineering): patch the seed to deactivate the 17 batch-activated, keep the 12 Phase 1 (which were similarly unvalidated but at least UI-tested through prior days). Bias toward fewer untested customer surfaces.
- This week: spec the translator. The condition strings are stylistically consistent (`"X crosses above Y"`, `"X > N"`, etc.) — a small grammar would cover the bulk. Treat this as a Phase 7 unblocker.

A proposed seed-deactivation patch is in
[`proposed_deactivation_patch.json`](proposed_deactivation_patch.json).

## What was NOT done in this Queue Y session

- Phase 2 (build `scripts/validate_template.py`) — would have failed identically on every template.
- Phase 3 (loop over 17) — would have produced 17 identical Pydantic ValidationError reports.
- Phase 4 (`SUMMARY.md` table) — no meaningful PASS/WARN/FAIL rows to populate.

The 2-hour budget was preserved by stopping at Phase 1 once the structural gap was concretely reproduced.
