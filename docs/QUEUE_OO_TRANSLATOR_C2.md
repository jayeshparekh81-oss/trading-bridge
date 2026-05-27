# Queue OO — Translator Extension C2: Divergence Indicator Templates

Branch: `feat/translator-c2-divergence` (stacked on `feat/translator-a2-synonym-resolution` @ `84ef9f9`, NOT merged to main).
Goal: unlock `rsi-divergence`, `macd-divergence`, `obv-divergence` → coverage 12 → 15.

---

## Phase 1 — Discovery findings

### 1. The divergence calc IS real (hard-stop #1 NOT triggered)

`backend/app/strategy_engine/indicators/calculations/_divergence.py` is a complete,
deterministic implementation — **not** a skeleton.

- `detect_divergence(prices, indicator, lookback) -> list[float | None]`
- Per-bar "regular" divergence code: `+1.0` bullish (price new low, indicator doesn't
  confirm), `-1.0` bearish (price new high, indicator doesn't confirm), `0.0` none,
  `None` during warmup / when the lookback window has unavailable indicator values.
- Three consumer calcs wrap it, all complete:
  - `rsi_divergence(closes, rsi_period=14, lookback=20)`
  - `macd_divergence(closes, fast=12, slow=26, signal=9, lookback=20)` — uses the MACD **line**
  - `obv_divergence(closes, volumes, lookback=20)`

### 2. The 3 indicators are registered AND dispatched (engine 100% done)

- **Registry**: `_pack11_active.py` declares `_RSI_DIVERGENCE`, `_MACD_DIVERGENCE`,
  `_OBV_DIVERGENCE` with full `IndicatorMetadata`. Each has `outputs=["line"]`,
  `category="Divergence"`, `status=ACTIVE`. Inputs:
  - `rsi_divergence`: `rsi_period` (14), `lookback` (20)
  - `macd_divergence`: `fast` (12), `slow` (26), `signal` (9), `lookback` (20)
  - `obv_divergence`: `lookback` (20)
- **Runner dispatch**: `backtest/indicator_runner.py:909-927` already has all three
  `if cfg.type == "<...>_divergence"` branches wired to the calc functions.

**Conclusion: zero engine changes are needed.** The divergence indicators are fully
backtest-callable today. The single +1/-1/0 `line` output encapsulates the multi-bar
swing detection internally.

### 3. The real gap: the 3 templates are FAIL_UNPARSEABLE prose (mission premise was off)

The mission assumed the templates "reference divergence as an indicator output."
They do **not**. The seed `config_json` for all three uses **free-text English prose**
referencing **base** indicators (not the divergence indicators), with stateful
multi-bar swing language. Verbatim from `backend/data/strategy_templates_seed.json`:

| slug | `indicators` | `entry_long.condition` |
|---|---|---|
| `rsi-divergence` | `["rsi_14"]` | `price prints lower low in last 20 bars AND rsi_14 prints higher low AND current candle bullish reversal pattern` |
| `macd-divergence` | `["macd_12_26_9"]` | `price prints lower low in last 25 bars AND macd histogram prints higher low (bullish divergence) AND macd line above its signal` |
| `obv-divergence` | `["obv","ema_50"]` | `price prints lower low in last 25 bars AND obv prints higher low (bullish divergence) AND close > ema_50 OR close within 1% of ema_50` |

Exit prose:
- `rsi-divergence`: `rsi_14 > 70 OR rsi_14 crosses below 50`
- `macd-divergence`: `macd line crosses below signal line OR macd histogram contracts for 3 consecutive bars`
- `obv-divergence`: `obv prints lower high while price prints higher high (bearish divergence emerging) OR close < ema_50 - 1%`

The Queue BB prototype (`docs/TRANSLATOR_PROTOTYPE/PROGRESS.md`) classifies all three as
**FAIL_UNPARSEABLE**. The Queue BB founder-overrides doc (line 361) said:

> Divergence templates: divergence is multi-bar pattern detection that the schema has
> NO primitive for. **Engine extension required — out of scope for Queue BB. Recommend
> deactivate in seed until divergence support ships.**

**That engine extension has since shipped** (finding #2). The divergence indicator IS
the missing primitive. The blocker is cleared.

### 4. Schema CAN express divergence without any grammar/schema stateful support

`schema/strategy.py::IndicatorCondition` accepts `left` (indicator id) + `op` +
`value` (constant). So:

```
IndicatorCondition(type="indicator", left="rsi_div", op=">", value=0.0)   # bullish divergence
```

collapses "price lower-low AND RSI higher-low" into ONE comparison, because the
`rsi_divergence` indicator already computed exactly that and emitted +1.0. **This is
why hard-stop #2 is AVOIDED** — we do NOT need the schema or the prose grammar to
support N-bar windows / stateful swing comparisons; the indicator owns the statefulness.

A prose-grammar approach, by contrast, WOULD require reimplementing swing-low/high
detection in the parser = B1-style scope blowup → would trigger hard-stop #2.

### 5. Translator architecture: override registry is the sanctioned path

`translate_template()` (`translator/parser.py`) consults `get_override(slug)` FIRST,
then falls back to the prose parser. The override registry
(`translator/override_registry.py`) is the "Option Z hybrid" mechanism explicitly
designed for "templates the parser cannot translate." It is currently **empty**
(`_OVERRIDES = {}`) and **nothing calls `register_override()`** at runtime, so a
registration hook is required (see Design decision 2).

The clone path (`templates/clone_service.py::_try_translate`) calls `translate_template`
defensively — translation failure is non-fatal (`strategy_json` stays NULL). So
populating overrides is purely additive and risk-free to the clone flow.

### 6. Engine combination semantics (verified)

- **Entry** (`engines/entry.py:86`): conditions combine via `EntryRules.operator`
  — `AND` = all pass, `OR` = at least one. Candle patterns ARE evaluated in entry
  (`engines/candle_pattern.py` supports `BULLISH`).
- **Exit** (`engines/exit.py:169`): `indicator_exits` are **OR'd** — each
  `IndicatorCondition` independently fires an exit event. **Non-`IndicatorCondition`
  entries in `indicator_exits` are IGNORED by the Phase-2 engine** (so exits must be
  `IndicatorCondition`s; dropping an inexpressible OR-clause is safe — SL/TP +
  remaining clauses still exit).
- `crossover`/`crossunder` require `right` (an indicator id); they are NOT defined
  against a constant `value`. So "rsi crosses below 50" cannot be a crossunder-vs-50.

### 7. Validation method (matches A2)

PASS = (a) translator produces a valid `StrategyJSON` (zero validation errors) AND
(b) synthetic backtest generates trades. The harness is the deterministic
720×5-min sine fixture (`trading_window_candles` in
`tests/strategy_engine/translator/test_parser.py`) + `run_backtest`.
Pre-existing `tests/strategy_engine/` failures on main: 11 (compliance/indicator_admin/registry).

### Gap summary (what the templates request vs what exists)

| Prose clause | Expressible today? | Mapping |
|---|---|---|
| "price lower low + X higher low (bullish divergence)" | ✅ | `<x>_divergence > 0` (indicator owns the statefulness) |
| "macd line above its signal" | ✅ | `macd_line > signal_line` (A2 sub-output path / direct override decl) |
| "current candle bullish reversal pattern" | ✅ | `CandleCondition(BULLISH)` in entry |
| "rsi_14 > 70" | ✅ | `rsi_14 > 70` |
| "close > ema_50" | ✅ | `close > ema_50` (close pseudo = ema(2)) |
| "macd line crosses below signal" | ✅ | `macd_line crossunder signal_line` (right=indicator) |
| "rsi crosses below 50" | ⚠️ | crossunder-vs-constant unsupported → `rsi_14 < 50` level, or drop |
| "macd histogram contracts for 3 consecutive bars" | ❌ | multi-bar; drop (OR-clause; SL/TP cover) |
| "close within 1% of ema_50" / "ema_50 - 1%" | ⚠️ | % band; simplify to plain `close >/< ema_50` |

---

## Phase 2 — Design decisions (founder signed off 2026-05-27)

| # | Decision | Choice (approved) |
|---|---|---|
| 1 | **Approach** | **Override registry** — hand-write 3 structured `StrategyJSON` overrides using the `rsi/macd/obv_divergence` indicators with `divergence > 0` conditions. Zero engine changes, zero grammar changes; avoids hard-stop #2 (the indicator owns the statefulness). |
| 2 | **Registration hook** | **New module `translator/divergence_overrides.py`** holds the 3 dicts + `register_divergence_overrides()`. `override_registry.py` seeds `_OVERRIDES` from it at module load (+2 lines, cycle-free — `divergence_overrides` does not import `override_registry` at module top). Works in both the clone path and tests. |
| 3 | **Prose fidelity** | **Accept faithful simplifications.** Kept exact: `<x>_divergence > 0`, `macd_line > signal_line`, `CandleCondition(BULLISH)`, `rsi_14 > 70`. Simplified: % bands → plain `close >/< ema_50`; "rsi crosses below 50" (crossunder-vs-constant unsupported) → dropped/level. Dropped: "macd histogram contracts 3 bars" (multi-bar, unsupported; OR-clause covered by SL/TP + crossunder). Trend filter may be relaxed so the no-trend synthetic harness generates trades. |

Regression safety verified before coding: `test_clone_fail…` keys on slug `rsi-divergence-test`
(≠ override key `rsi-divergence`); `test_seed_shape.py` asserts seed structure only (seed
untouched); `test_parser.py`'s autouse `clear_overrides()` isolates A2/BB parser tests from
the module-load seeding. A2's files (`sub_outputs.py`, `parser.py`, `indicator_runner.py`,
`field_mappers.py`, `schema/strategy.py`) are NOT in the C2 change set.

## Phase 3 — Implementation (additive only)

Two files (one new, one +8/-3), no engine changes.

| File | Δ | What |
|---|---|---|
| `translator/divergence_overrides.py` | **new, 210** | 3 hand-written `StrategyJSON` override dicts (`rsi-divergence`, `macd-divergence`, `obv-divergence`) + `DIVERGENCE_OVERRIDES` mapping + `register_divergence_overrides()` (lazy import to avoid cycle). |
| `translator/override_registry.py` | +8/-3 | Seed `_OVERRIDES = dict(DIVERGENCE_OVERRIDES)` at module load. Cycle-free: `override_registry` imports `divergence_overrides`, which does NOT import `override_registry` at module top. |

Override condition shapes (per template):

- **rsi-divergence** — indicators `rsi_div`(rsi_divergence, rsi_period=14, lookback=20), `rsi_14`.
  Entry (AND): `rsi_div > 0` ∧ `candle==BULLISH` ∧ time 09:30-15:00. Exit (OR): `rsi_14 > 70`; + SL 1.5% / TP 4.5% / square-off 15:00.
- **macd-divergence** — indicators `macd_div`(lookback=25), `macd_line`(macd output=macd), `signal_line`(macd output=signal).
  Entry (AND): `macd_div > 0` ∧ `macd_line > signal_line` ∧ time. Exit (OR): `macd_line crossunder signal_line`; + SL 1.5% / TP 4.5% / square-off.
- **obv-divergence** — indicators `obv_div`(lookback=25), `ema_50`, `close`(ema period=2).
  Entry (AND): `obv_div > 0` ∧ time. (Strict `close > ema_50` relaxed off entry — decision 3 — since a fresh price low cannot sit above the lagging 50-EMA; strict = 0 trades.)
  Exit (OR): `obv_div < 0` ∨ `close < ema_50`; + SL 1.8% / TP 5.0% / square-off.

## Phases 4-5 — Test + regression results

### Phase 4 — new tests (`tests/strategy_engine/translator/test_divergence_overrides.py`, 232 lines)

`python3 -m pytest tests/strategy_engine/translator/test_divergence_overrides.py` → **12 passed**.

- `test_divergence_calc_outputs` — calc shape: same length, values ∈ {+1,-1,0,None}; bullish code present.
- `test_divergence_indicator_dispatch` (×3) — registry knows each id, resolves to a callable calc.
- `test_runner_emits_divergence_series` — runner precomputes `rsi_div` and emits +1.
- `test_translator_handles_divergence_conditions` (×3) — each seed template translates; declares a divergence indicator; entry gated on `divergence > 0`.
- `test_3_targets_pass_validation` (×3) — translate → `model_validate` round-trip (zero errors) → synthetic backtest **trades ≥ 1**.
- `test_overrides_cover_exactly_the_three_slugs` — scope guard.

Synthetic-backtest trade counts (deterministic): **rsi-divergence=10, macd-divergence=10, obv-divergence=63.**
rsi/macd use a steep-then-flattening decline (new closing lows + recovering momentum = bullish divergence);
obv uses a down-drifting oscillation with up-weighted volume (OBV rises while price prints lower lows).

### Phase 5 — regression

- **12 currently-PASS templates still PASS** (re-translated + sine-harness backtested):
  aroon-crossover=10, cci-momentum=17, cmf-confirmation=10, ema-crossover-20-50=11, ema-crossover-9-21=11,
  mfi-overbought-oversold=108, rsi-oversold-bounce=328, williams-pct-r-reversal=83, macd-trend-signal=11,
  rsi-macd-confluence=19, bb-rsi-oversold=12, orb-15min=7 → **12/12, coverage 12 → 15.**
- **`tests/services/test_pine_mapper_options.py` — 48 passed** (parallel options work intact).
- **`tests/strategy_engine/` — 25 failed, 2000 passed, 1 skipped.** The 25 failures are **byte-identical to base @ `84ef9f9`** (verified by reverting C2 and diffing the failure sets — empty diff = **ZERO new failures**). All are pre-existing pollution (api-auth/401, compliance, indicator_admin, registry); none in translator/backtest/indicators.
- Translator suites (`tests/strategy_engine/translator/`, `backtest/test_indicator_runner_sub_outputs.py`, `test_pack11_indicators.py`, `test_pack8_indicators.py`) all green.
- Pre-existing-and-unrelated: 5 `tests/templates/` seed-shape/registry failures (seed-vs-spec active-count drift). Verified translator-independent (import no translator) and present at base. NOT a C2 regression.

## Live-trading risk: ZERO

- **Sacred files untouched** (verified via `git status`): `strategy_executor.py`, `direct_exit.py`,
  `api/webhook/*`, `kill_switch.py`, `brokers/*`, `alembic/versions/*`. LIVE BSE LTD
  `89423ecc-c76e-432c-b107-0791508542f0` path unaffected.
- **A2 files untouched** (additive-only honoured): `sub_outputs.py`, `translator/parser.py`,
  `backtest/indicator_runner.py`, `field_mappers.py`, `schema/strategy.py`.
- **No live path imports the new code.** The only importer of the translator package is
  `app/templates/clone_service.py` — the offline clone path, where translation is best-effort
  and non-fatal. No live executor / webhook / broker module imports `override_registry`,
  `divergence_overrides`, or the translator.

## Files changed (diff vs A2 base `84ef9f9`)

| File | Δ |
|---|---|
| `backend/app/strategy_engine/translator/divergence_overrides.py` | +210 (new) |
| `backend/app/strategy_engine/translator/override_registry.py` | +8 / -3 |
| `backend/tests/strategy_engine/translator/test_divergence_overrides.py` | +232 (new) |
| `docs/QUEUE_OO_TRANSLATOR_C2.md` | this doc |

## Next step

Founder D2 prose rewrite for the remaining unparseable templates (candle-pattern, MA colour-flip,
multi-bar lookback families) — the final coverage push beyond 15.
