# Translator Architecture Proposal — Template `config_json` → `StrategyJSON`

**Owner:** Queue AA, Phase 3 (design only — no code in this branch)
**Status:** Recommendation pending Jayesh's go/no-go

---

## 1. Current state (concrete field map)

### Template `config_json` schema (the doc-shape input)
Validated by `backend/app/templates/validator.py::validate_config_json`. Active templates require:

```python
{
  "indicators":        list[str],          # registry IDs as strings: ["ema_9", "ema_21"]
  "entry_long":        {"condition": str}, # prose: "ema_9 crosses above ema_21"
  "exit_long":         {"condition": str},
  "entry_short":       {"condition": str}, # optional (both shorts present or both absent)
  "exit_short":        {"condition": str},
  "stop_loss_pct":     float,              # 0.1 - 10.0
  "take_profit_pct":   float,              # 0.1 - 20.0
  "position_sizing":   {"method": str, "amount_inr": int>0},
  "max_open_positions": int,               # must be exactly 1 in Phase 1
  "trading_hours":     {"start": "HH:MM", "end": "HH:MM"}
}
```

Key property: **`condition` is a free-form prose string.** The validator only ensures it's non-empty; semantic interpretation is the consumer's responsibility (today, the consumer is "a human reading the template card in the UI").

### `StrategyJSON` schema (the engine-callable target)
Defined in `backend/app/strategy_engine/schema/strategy.py`. Frozen Pydantic model with extra fields rejected:

```python
{
  "id":         str,
  "name":       str,
  "mode":       StrategyMode,             # beginner | intermediate | expert
  "version":    int >= 1,
  "indicators": list[IndicatorConfig],    # NOT strings — dicts:
                                          #   {id: "ema_9", type: "ema", params: {period: 9, source: "close"}}
  "entry":      EntryRules,               # structured: side + list[Condition]
  "exit":       ExitRules,
  "risk":       RiskRules,                # stop_loss, take_profit, position_size, max_concurrent
  "execution":  ExecutionConfig,          # mode (backtest/paper/live), order_type, product_type
}
```

`Condition` is a discriminated union (via `type` discriminator):
- `IndicatorCondition` — `{type: "indicator", left: <ind_id>, op: > | < | >= | <= | == | != | crossover | crossunder, right: <ind_id> | None, value: float | None}` (exactly one of right/value; crossover/crossunder require `right`)
- `CandleCondition` — `{type: "candle", pattern: bullish|bearish|engulfing|doji|hammer|shooting_star}`
- `TimeCondition` — `{type: "time", op: after|before|between|exact, value: "HH:MM", end: "HH:MM" (only for between)}`
- `PriceCondition` — `{type: "price", op: > | < | >= | <= | previous_high_breakout | previous_low_breakdown, value: float | None}`

### The gap, named
1. **Indicators:** strings → must become `IndicatorConfig` dicts with `(id, type, params)`. The `id_to_type` heuristic (`ema_9 → type="ema", params={period: 9}`) covers ~80% of cases; multi-output indicators (`bb_20_2 → bollinger_bands with {period: 20, std: 2}`) and named-period ones (`ichimoku_9_26_52`) need a lookup table.
2. **Conditions:** prose → must become `Condition[]`. Requires a prose grammar/parser.
3. **Missing top-level fields:** `id`, `name`, `mode`, `execution`, structured `entry/exit/risk` — must be generated/defaulted by the translator from template metadata.

---

## 2. Three translation paths

### Option X — Founder hand-rewrites every template's `config_json`
- Replace every prose `condition` with a JSON `Condition` block, by hand, across 113 templates (29 active + 84 catalogued).
- Pros: zero new code; full founder control over each translation.
- Cons: 113 templates × ~5 min/each careful work = ~10 hours. Tedious. New templates added later would need the same treatment. Doc-shape is lost as a docs surface (or has to be maintained separately).

### Option Y — Build a prose → `StrategyJSON` translator (Python module)
- Module under `backend/app/templates/translator.py` that parses the prose grammar and emits canonical `StrategyJSON`.
- Per-condition prose grammar covers: `"<ind> crosses above|below <ind>"`, `"<ind> > <num>"`, `"<ind> crosses above|below <num>"`, `"close > <ind>"`, `"timestamp >= HH:MM"`, single `AND`/`OR` conjunctions, candle patterns by name.
- Pros: works for all 113 templates AND future templates with no per-template work. UI keeps the prose copy for human readability. Translator is testable in isolation.
- Cons: parser must cover the variants the templates actually use. Edge cases (`"previous close > bb_lower"`, `"close > 20-bar donchian upper band (new 20-bar high)"`) push complexity up.

### Option Z — Hybrid (translator handles 80%, founder reviews 20%)
- Translator handles the mechanical 80% (single conditions, common compositions).
- Templates with conditions the translator can't parse are flagged + emit a `BLOCKED_TRANSLATION` reason; founder writes them in canonical JSON directly in a side file (`backend/data/strategy_templates_overrides.json`).
- Translator merges its output with overrides at load time (`overrides win when present`).
- Pros: gets to ~100% coverage faster than Option Y alone. Founder only edits the gnarly few. Adds a defensive layer where unparseable templates are explicitly flagged, not silently broken.
- Cons: two source files for one truth (the doc-shape `config_json` + the override JSON).

---

## 3. End-to-end worked example — `ema-crossover-9-21`

### Input (current state, in `backend/data/strategy_templates_seed.json`)
```json
{
  "slug": "ema-crossover-9-21",
  "name": "EMA Crossover (9, 21)",
  "category": "Trend Following",
  "complexity": "beginner",
  "config_json": {
    "indicators": ["ema_9", "ema_21"],
    "entry_long":  {"condition": "ema_9 crosses above ema_21"},
    "entry_short": {"condition": "ema_9 crosses below ema_21"},
    "exit_long":   {"condition": "ema_9 crosses below ema_21"},
    "exit_short":  {"condition": "ema_9 crosses above ema_21"},
    "stop_loss_pct": 1.5,
    "take_profit_pct": 3.0,
    "position_sizing": {"method": "fixed_amount", "amount_inr": 50000},
    "max_open_positions": 1,
    "trading_hours": {"start": "09:15", "end": "15:15"}
  }
}
```

### Output (target `StrategyJSON` after translation)
```json
{
  "id": "template:ema-crossover-9-21",
  "name": "EMA Crossover (9, 21)",
  "mode": "beginner",
  "version": 1,
  "indicators": [
    {"id": "ema_9",  "type": "ema", "params": {"period": 9,  "source": "close"}},
    {"id": "ema_21", "type": "ema", "params": {"period": 21, "source": "close"}}
  ],
  "entry": {
    "side": "BUY",
    "conditions": [
      {"type": "indicator", "left": "ema_9", "op": "crossover",  "right": "ema_21"},
      {"type": "time",      "op": "between", "value": "09:15", "end": "15:15"}
    ]
  },
  "exit": {
    "indicator_exits": [
      {"type": "indicator", "left": "ema_9", "op": "crossunder", "right": "ema_21"}
    ],
    "partial_exits": []
  },
  "risk": {
    "stop_loss_percent": 1.5,
    "take_profit_percent": 3.0,
    "position_size": {"method": "fixed_amount", "amount_inr": 50000},
    "max_concurrent_positions": 1
  },
  "execution": {
    "mode": "backtest",
    "order_type": "MARKET",
    "product_type": "INTRADAY"
  }
}
```

### Translation rules applied
| Source | Target | Rule |
|--------|--------|------|
| `slug` | `id` (prefixed with `template:`) | Synthetic id, namespaces template-derived strategies |
| `name` | `name` | Verbatim |
| `complexity` | `mode` | direct enum mapping (beginner/intermediate/expert) |
| `indicators[i]` (string) | `IndicatorConfig` (dict) | parse `<type>_<param1>_<param2>` → `{id, type, params}` via per-type lookup |
| `entry_long.condition: "ema_9 crosses above ema_21"` | `IndicatorCondition(left, op=CROSSOVER, right)` | regex: `^(\w+) crosses above (\w+)$` → CROSSOVER |
| `exit_long.condition: "ema_9 crosses below ema_21"` | `IndicatorCondition(left, op=CROSSUNDER, right)` | regex: `^(\w+) crosses below (\w+)$` → CROSSUNDER |
| `trading_hours` | TimeCondition appended to entry/exit conditions | mechanical |
| `stop_loss_pct`, `take_profit_pct`, `position_sizing`, `max_open_positions` | `RiskRules` | mechanical rename |
| (none) | `ExecutionConfig` | defaults: `mode=backtest, order_type=MARKET, product_type=INTRADAY` |

### What this template needs from the translator
- An indicator-id grammar (`<type>_<n>` → `{type, params: {period: n}}`).
- Two regex patterns: `^X crosses above Y$` and `^X crosses below Y$`.
- A defaults layer for `execution`, `id`, `version`.

Estimated implementation effort for THIS template alone: ~2 hours including tests. Estimated for ALL 113 templates: see Section 5.

---

## 4. Recommended option

**Option Z — Hybrid.**
- Option Y alone is right philosophically but the prose has enough variety (`"new 20-bar high"`, `"previous close > bb_lower"`, `"timestamp >= 09:30 IST"`, multi-condition `OR`s) that hitting 100% with the parser alone risks weeks of grammar-tweaking. Z lets the parser handle the high-volume mechanical work while Jayesh writes 5-10 hand-translated overrides for the gnarly templates — bounded, time-boxed.
- Templates also gain a sanity gate: any prose the translator can't parse becomes an explicit failure, not a silent miss. This is the engineering equivalent of "fail loud, fail early."

Pure Option X is rejected because the doc-shape is genuinely valuable (UI gallery copy + customer marketing reads from these strings), and Pure Option Y is rejected because the long tail of prose variants is high-effort with low marginal payoff.

---

## 5. Effort estimate per option

Assumptions: working with a single dev (not paired), with code review at the end. Effort includes calc + tests + reviewing the produced `StrategyJSON` for all 113 templates.

| Option | Day 1 | Day 2 | Day 3 | Day 4 | Day 5 | Total |
|--------|-------|-------|-------|-------|-------|-------|
| **X — Hand-rewrite all 113** | 30 templates | 30 | 30 | 23 + QA | — | **~4 founder-days** |
| **Y — Pure parser** | Grammar + regex + IndicatorConfig lookup table | Conditions: indicator/candle/time/price coverage | Multi-condition AND/OR + integration tests | Edge-case sweep on all 113 + bug-fix loop | Final review + golden-output snapshots | **~5 dev-days** |
| **Z — Hybrid** | Grammar + 80% of 113 templates handled | Coverage sweep + flag failures | Founder writes ~10-15 overrides | Integration tests + override merge layer | Final review | **~3-4 dev-days + 0.5 founder-day** |

Cost crossover: Z and Y are similar effort, but Z reaches usable state ~1 day sooner because partial coverage is acceptable from day 2 onward. X looks cheaper but burns founder time, which is the scarcest resource.

---

## 6. Implementation sketch (Option Z) — for the supervised session

### Module structure
```
backend/app/templates/translator.py             # main translator
  - translate(config_json, slug, name, complexity) -> StrategyJSON | None
  - parse_condition(prose: str) -> list[Condition] | UNPARSEABLE
  - parse_indicator_id(s: str) -> IndicatorConfig

backend/app/templates/overrides.py              # override loader
  - load_overrides() -> dict[slug, StrategyJSON]

backend/data/strategy_templates_overrides.json  # hand-written, slug-keyed

backend/tests/templates/test_translator.py      # per-pattern tests
backend/tests/templates/test_translate_all_113.py  # smoke run all 113
```

### Coverage targets
- 100% of the 113 templates either translate via parser OR have an override.
- Parser coverage target: ~70% (~80 of 113) on day 2; ~85% by day 3 as edge-case rules added.
- Overrides for the remaining ~17-20 by day 3.
- All 113 must produce a valid `StrategyJSON` by end of day 4.

### Acceptance criteria for the supervised session
1. `translate(config_json, ...)` round-trip test for every template — output must `StrategyJSON.model_validate(...)` clean.
2. `run_backtest(BacktestInput(strategy=translate(...), candles=synthetic))` runs to completion for every template without raising.
3. Trade-count > 0 on synthetic candles for at least 60% of translated templates (smoke check that conditions can actually fire; threshold reflects that synthetic candles may not stimulate every strategy's logic).
4. No translator code touches live-trading paths.

### Out of scope for this session
- Actually clicking "use template" from the UI gallery and getting a working backtest end-to-end. That requires `clone_service.py` to call `translate(...)` and populate `strategy_json` — a small integration to be done in a follow-up.
- Translator versioning. The translator is deterministic and pinned via tests; bumps are reviewable as code changes.
- Round-tripping (StrategyJSON → prose). Out of scope; UI keeps the original prose for human readability.

---

## 7. What this proposal does NOT do
- Build the translator (this branch is design-only).
- Touch `backend/data/strategy_templates_seed.json` (Queue AA guardrail).
- Wire `clone_service.py` to use it.
- Mount the `/api/backtest` router (Day 7 work, founder's manual step).

All of those are downstream of the go/no-go decision on Option X/Y/Z, captured in `QUEUE_AA_FINAL_REPORT.md`.
