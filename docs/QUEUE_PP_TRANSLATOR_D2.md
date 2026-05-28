# Queue PP — Translator Extension D2: Trend Template Overrides

Branch: `feat/translator-d2-trend-overrides` (stacked on `feat/translator-c2-divergence` @ `e8a589c`, NOT merged to main).
Goal: unlock `supertrend-rider`, `hull-ma-trend`, `triple-ema-crossover` → coverage 15 → 18.
Approach: override-registry pattern (same as C2 — hand-crafted `StrategyJSON` per slug).

---

## Phase 1 — Discovery findings

### Targets (verbatim from seed `config_json`) — all currently FAIL_UNPARSEABLE_CONDITION

**`supertrend-rider`** (complexity=beginner; indicators `["supertrend_10_3"]`)
- entry_long: `"supertrend flips to bullish (close > supertrend)"`
- entry_short: `"supertrend flips to bearish (close < supertrend)"`  ← short side
- exit_long: `"supertrend flips to bearish"`  /  exit_short: `"supertrend flips to bullish"`
- SL 2.0% / TP 5.0% / trading_hours 09:15-15:15

**`hull-ma-trend`** (complexity=intermediate; indicators `["hull_ma_21"]`)
- entry_long: `"hull_ma_21 colour flips from red (sloping down) to green (sloping up) AND close > hull_ma_21"`
- exit_long: `"hull_ma_21 colour flips back to red"`
- SL 1.5% / TP 4.0% / trading_hours 09:30-15:00

**`triple-ema-crossover`** (complexity=intermediate; indicators `["ema_8","ema_21","ema_55"]`)
- entry_long: `"ema_8 > ema_21 > ema_55 AND ema_8 crosses above ema_21 in the last 2 bars"`
- exit_long: `"ema_8 crosses below ema_21 OR close < ema_55"`
- SL 1.5% / TP 4.5% / trading_hours 09:30-15:00

### Indicators (all ACTIVE + dispatched in `indicator_runner.py`)

| registry id | params | outputs | notes |
|---|---|---|---|
| `supertrend` | `period` (10), `multiplier` (3.0) | `line`, `direction` | `direction` = +1.0 bullish / -1.0 bearish / None warmup. Trend flips when close crosses the active band; `line` = active band level. |
| `hull_ma` | `period` (20), `source` | `line` | single line (Pack-2 single-source MA). |
| `ema` | `period`, `source` | `line` | known. |

Engine is fully wired for all three — **zero engine changes needed** (same situation as C2: the
work is purely translator overrides). These are simpler than divergence: every clause maps to a
crossover or a comparison the schema already supports — **no stateful primitive needed, hard-stop
#2 not in play.**

### Why FAIL_UNPARSEABLE today

The prose uses visual/UI semantics ("flips to bullish", "colour flips from red to green", "sloping
up") and a multi-bar window ("in the last 2 bars") that the prose grammar can't match. Queue BB's
founder doc (aggregate decision 4) already prescribed the fix: *"Hull-MA / Supertrend 'colour flip'
prose reference visual UI semantics — should rewrite to numeric primitives (e.g. `supertrend > close`
→ bullish)."* That is exactly what these overrides do.

### Mapping (prose → schema primitives)

| Prose | Primitive |
|---|---|
| supertrend "flips to bullish (close > supertrend)" | `close crossover supertrend_line` (the flip = close crossing above the band; prose's own parenthetical) |
| supertrend "flips to bearish" | `close crossunder supertrend_line` |
| hull "colour flips to green (sloping up) AND close > hull" | `close crossover hull_ma_21` |
| hull "colour flips back to red" | `close crossunder hull_ma_21` |
| "ema_8 > ema_21 > ema_55" | `ema_8 > ema_21` ∧ `ema_21 > ema_55` |
| "ema_8 crosses above ema_21 in the last 2 bars" | `ema_8 crossover ema_21` (single-bar; 2-bar window not expressible) |
| "ema_8 crosses below ema_21 OR close < ema_55" | `ema_8 crossunder ema_21` ∨ `close < ema_55` |

`close` is declared as `ema(period=2)` ≈ raw price (the parser's own pseudo-price convention, reused
in C2). `crossover`/`crossunder` operate between two indicator ids (schema-supported).

### Simplifications (need founder sign-off — decision 3)

- **supertrend long-only**: the seed has `entry_short`/`exit_short`, but the translator + StrategyJSON
  are single-side (BUY) in this prototype (parser ignores `entry_short`; C2 did the same). The short
  side is dropped; long captures "ride the supertrend up."
- **hull colour/slope → numeric**: "colour flips / sloping up/down" is UI semantics; mapped to
  `close` crossing the hull line (founder's prescribed rewrite). Slope nuance dropped.
- **triple-ema "in the last 2 bars"**: narrowed to a single-bar crossover (no N-bar-window primitive).

### Regression safety (pre-checked)

The 3 slugs appear in tests only in `test_seed_shape.py`'s active-slug-SET assertion (seed file
untouched → unaffected). No translator/clone test asserts these slugs are untranslatable. No test
references the supertrend/hull prose.

---

## Phase 2 — Design decisions (founder signed off 2026-05-27)

| # | Decision | Choice (approved) |
|---|---|---|
| 1 | **Approach** | Override registry — hand-crafted `StrategyJSON` per slug (pre-approved C2 pattern). |
| 2 | **Registration** | New module `translator/trend_overrides.py` (`TREND_OVERRIDES` + `register_trend_overrides()`); `override_registry` seeds `_OVERRIDES = {**DIVERGENCE_OVERRIDES, **TREND_OVERRIDES}`. |
| 3a | **supertrend signal** | `close crossover supertrend_line` (entry) / `close crossunder supertrend_line` (exit) — the flip moment, matches the prose parenthetical. |
| 3b | **Simplifications** | Accepted: supertrend **long-only** (drop seed's short side); hull colour/slope → `close` crossing the hull line; triple-ema "last 2 bars" → single-bar crossover. Core trend signals kept exact. |

## Phase 3 — Implementation (additive only)

| File | Δ | What |
|---|---|---|
| `translator/trend_overrides.py` | **new, 181** | 3 hand-written `StrategyJSON` dicts + `TREND_OVERRIDES` + `register_trend_overrides()` (lazy import, cycle-free). |
| `translator/override_registry.py` | +5/-2 | Seed `_OVERRIDES = {**DIVERGENCE_OVERRIDES, **TREND_OVERRIDES}` at module load. |

Override condition shapes:

- **supertrend-rider** (mode beginner) — `supertrend_10_3`(period 10, mult 3.0), `close`(ema-2).
  Entry (AND): `close crossover supertrend_10_3` ∧ time 09:15-15:15. Exit (OR): `close crossunder supertrend_10_3`; + SL 2.0% / TP 5.0% / square-off 15:15.
- **hull-ma-trend** (mode intermediate) — `hull_ma_21`(period 21), `close`(ema-2).
  Entry (AND): `close crossover hull_ma_21` ∧ time 09:30-15:00. Exit (OR): `close crossunder hull_ma_21`; + SL 1.5% / TP 4.0% / square-off.
- **triple-ema-crossover** (mode intermediate) — `ema_8`, `ema_21`, `ema_55`, `close`(ema-2).
  Entry (AND): `ema_8 > ema_21` ∧ `ema_21 > ema_55` ∧ `ema_8 crossover ema_21` ∧ time. Exit (OR): `ema_8 crossunder ema_21` ∨ `close < ema_55`; + SL 1.5% / TP 4.5% / square-off.

## Phases 4-5 — Test + regression results

### Phase 4 — new tests (`tests/strategy_engine/translator/test_trend_overrides.py`, 197 lines) → **11 passed**

- `test_trend_indicator_dispatch` (×3: supertrend/hull_ma/ema) — registry resolves each to a callable.
- `test_translator_handles_trend_conditions` (×3) — each seed template translates; declares the expected indicator; entry gated on the expected crossover.
- `test_supertrend_rider_is_long_only` — override is single-side BUY (short side dropped).
- `test_3_targets_pass_validation` (×3) — translate → `model_validate` round-trip → synthetic backtest **trades ≥ 1**.
- `test_overrides_cover_exactly_the_three_slugs` — scope guard.

Synthetic trade counts: **supertrend-rider=11, hull-ma-trend=10** (sine harness);
**triple-ema-crossover=6** (uptrend-with-pullbacks — the AND-entry needs the fast crossover
*and* the full stack bullish simultaneously, which a pure sine doesn't produce).

### Phase 5 — regression

- **18/18 templates PASS** (re-translated + backtested): the 12 baseline + 3 C2 divergence (rsi=10, macd=10, obv=63) + 3 D2 trend (11/10/6) → **coverage 15 → 18.**
- `tests/strategy_engine/translator/` + `backtest/test_indicator_runner_sub_outputs.py` (A2) + `test_pack11_indicators.py` + `test_pack8_indicators.py` + `tests/services/test_pine_mapper_options.py` → **196 passed.**
- **`tests/strategy_engine/` — 25 failed, byte-identical to C2 base `e8a589c`** (verified by revert-and-diff → empty → **ZERO new failures**). All pre-existing pollution (api-auth/401, compliance, indicator_admin, registry).

## Live-trading risk: ZERO

- **Sacred files untouched**: `strategy_executor.py`, `direct_exit.py`, `api/webhook/*`, `kill_switch.py`, `brokers/*`, `alembic/versions/*`. LIVE BSE LTD `89423ecc-c76e-432c-b107-0791508542f0` path unaffected.
- **A2 untouched**: `sub_outputs.py`, `parser.py`, `indicator_runner.py`, `field_mappers.py`, `schema/strategy.py`. **C2 untouched**: `divergence_overrides.py` not modified by D2.
- **No live path imports the new code** — only the offline `clone_service.py` imports the translator; translation is best-effort and non-fatal there.

## Files changed (diff vs C2 base `e8a589c`)

| File | Δ |
|---|---|
| `backend/app/strategy_engine/translator/trend_overrides.py` | +181 (new) |
| `backend/app/strategy_engine/translator/override_registry.py` | +5 / -2 |
| `backend/tests/strategy_engine/translator/test_trend_overrides.py` | +197 (new) |
| `docs/QUEUE_PP_TRANSLATOR_D2.md` | this doc |

## Next step

Remaining FAIL_UNPARSEABLE families for a future queue: candle-pattern templates
(`doji-reversal`, `engulfing-candle-reversal`, `hammer-hanging-man-pattern` — schema models
`CandleCondition`), and the remaining multi-bar / sub-output prose. Stack continues:
A2 → C2 → D2, all unpushed, to merge to main together.
