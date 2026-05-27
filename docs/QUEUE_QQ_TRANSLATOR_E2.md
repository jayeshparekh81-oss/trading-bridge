# Queue QQ — Translator Extension E2: Candle-Pattern Template Overrides

Branch: `feat/translator-e2-candle-overrides` (stacked on `feat/translator-d2-trend-overrides` @ `b2c89ba`, NOT merged to main).
Goal: unlock the active candle-pattern templates via the override-registry pattern (same as C2/D2).
Approach: hand-crafted `StrategyJSON` per slug, using the schema's `CandleCondition` primitive.

---

## Phase 1 — Discovery findings

### Candle-pattern template inventory

| slug | is_active | indicators_used | translatable? |
|---|---|---|---|
| `doji-reversal` | **True** | `doji_pattern` | ✅ FAIL_UNPARSEABLE today → target |
| `engulfing-candle-reversal` | **True** | `engulfing_pattern` | ✅ FAIL_UNPARSEABLE today → target |
| `hammer-hanging-man-pattern` | **False** | `hammer_pattern` | ❌ **out of scope** (see below) |

**`hammer-hanging-man-pattern` is excluded:**
- It is `is_active=False` — not in the active-coverage set, and the clone path returns 409
  (not-cloneable) for inactive templates *before* translation, so an override would never fire.
- Its entry references `auto_support_resistance_20` — **not a registered indicator** (no
  `support`/`resist` id in the registry). "within 0.5% of strong support" has no schema primitive;
  dropping it would gut the strategy's core idea.
- Activating it + inventing an S/R indicator is a separate, larger piece of work — not this queue.

So this queue targets **2 active templates → coverage 18 → 20.**

### Targets (verbatim seed `config_json`) — both currently FAIL_UNPARSEABLE_CONDITION

**`doji-reversal`** (beginner; indicators `["ema_50","rsi_14"]`)
- entry_long: `"previous bar doji (body < 10% of range) AND price was extended below ema_50 in last 5 bars (downtrend) AND rsi_14 < 35 AND current bar closes above doji's high"`
- exit_long: `"close < doji's low OR rsi_14 > 60 (mean-reversion complete)"`
- SL 1.0% / TP 2.5% / trading_hours 09:30-15:00

**`engulfing-candle-reversal`** (beginner; indicators `["ema_50","rsi_14"]`)
- entry_long: `"current bar bullish engulfing pattern (current close > previous open AND current open < previous close AND previous bar bearish) AND rsi_14 < 40 AND close > ema_50 OR close within 2% of ema_50"`
- exit_long: `"current bar bearish engulfing OR close < entry_low (engulfing bar's low)"`
- SL 1.5% / TP 4.0% / trading_hours 09:30-15:00

### Engine support (`engines/candle_pattern.py`, `engines/entry.py`)

`CandlePattern` enum: `bullish, bearish, engulfing, doji, hammer, shooting_star`. `detect_candle_pattern`:
- **DOJI** — single-bar: body ≤ 10% of range.
- **HAMMER / SHOOTING_STAR** — single-bar shape tests.
- **ENGULFING** — two-bar, **direction-agnostic** (bullish OR bearish; current body covers prior
  body, opposite directions). Returns `False` when no prior bar.
- `entry.py:116` passes `prior_candle` to detection → ENGULFING works in entry.

**Key constraint (from C2 discovery):** `CandleCondition` is evaluated **only in ENTRY**. The exit
engine ignores non-`IndicatorCondition` entries in `indicator_exits` (Phase 2). So candle-pattern
*exits* (e.g. "bearish engulfing") cannot drive exits — those templates exit on SL/TP/square-off
(+ any expressible `IndicatorCondition`, e.g. `rsi > 60`).

### Mapping (prose → primitives)

| Prose | Primitive |
|---|---|
| doji "previous bar doji (body<10%)" | `CandleCondition(DOJI)` (current bar; 2-bar confirm not modelled) |
| doji "extended below ema_50 in last 5 bars" | `close < ema_50` |
| doji "rsi_14 < 35" | `rsi_14 < 35` |
| doji "current bar closes above doji's high" | dropped (prior-bar-relative, no primitive) |
| doji exit "close < doji's low OR rsi_14 > 60" | `rsi_14 > 60` (+ SL/TP/square-off); doji-low ref dropped |
| engulfing "bullish engulfing pattern" | `CandleCondition(ENGULFING)` ∧ `CandleCondition(BULLISH)` (engine ENGULFING is direction-agnostic; ∧ BULLISH = current-bar-bullish-engulfs-prior-bearish = bullish engulfing) |
| engulfing "rsi_14 < 40" | `rsi_14 < 40` |
| engulfing "close > ema_50 OR within 2%" | `close > ema_50` (relaxable — reversal lows may sit below ema_50, like C2's obv) |
| engulfing exit "bearish engulfing OR close < entry_low" | not expressible as IndicatorCondition → SL/TP/square-off only |

`close` declared as `ema(period=2)` ≈ raw price (parser convention, reused C2/D2). `CandleCondition`
references no indicator id (it reads the raw OHLC), so it needs no indicator declaration.

### Simplifications (founder sign-off — decision below)

- doji: current-bar DOJI (2-bar confirm + "closes above doji's high" dropped); "5-bar extended" → `close < ema_50`.
- engulfing: bullish engulfing = `ENGULFING ∧ BULLISH`; trend filter `close > ema_50` (relaxable); exit = SL/TP/square-off only (candle-pattern exit not engine-supported).
- hammer-hanging-man-pattern excluded (inactive + unregistered S/R indicator).

### Regression safety (pre-checked)

The slugs appear in tests only in `test_seed_shape.py`'s active-slug-SET assertion (seed untouched →
unaffected; that test already fails pre-existing on active-count drift). No translator/clone test
asserts these slugs are untranslatable.

---

## Phase 2 — Design decisions (founder signed off 2026-05-27)

| # | Decision | Choice (approved) |
|---|---|---|
| 1 | **Approach** | Override registry — hand-crafted `StrategyJSON` per slug (C2/D2 pattern). |
| 2 | **Registration** | New `translator/candle_overrides.py` (`CANDLE_OVERRIDES` + `register_candle_overrides()`); `override_registry` seeds `{**DIVERGENCE_OVERRIDES, **TREND_OVERRIDES, **CANDLE_OVERRIDES}`. |
| 3 | **Scope** | **2 active targets** (`doji-reversal`, `engulfing-candle-reversal`) → 18 → 20. **`hammer-hanging-man-pattern` excluded** (inactive + references unregistered `auto_support_resistance_20`). |
| 4 | **Simplifications** | doji = current-bar `DOJI` ∧ `close < ema_50` ∧ `rsi_14 < 35` (2-bar confirm + "closes above doji high" dropped); doji exit `rsi_14 > 60` + SL/TP. engulfing = `ENGULFING` ∧ `BULLISH` ∧ `rsi_14 < 40` (trend filter `close > ema_50` **dropped** — verified ZERO trades with it, since a bullish-engulfing reversal sits at an oversold low below the 50-EMA, same as C2's obv); engulfing exit = SL/TP/square-off only (candle-pattern exits not engine-supported). |

## Phase 3 — Implementation (additive only)

| File | Δ | What |
|---|---|---|
| `translator/candle_overrides.py` | **new, 154** | 2 hand-written `StrategyJSON` dicts + `CANDLE_OVERRIDES` + `register_candle_overrides()` (lazy import, cycle-free). |
| `translator/override_registry.py` | +10/-3 | Seed `_OVERRIDES = {**DIVERGENCE_OVERRIDES, **TREND_OVERRIDES, **CANDLE_OVERRIDES}`. |

Override condition shapes:

- **doji-reversal** (mode beginner) — `ema_50`, `rsi_14`, `close`(ema-2).
  Entry (AND): `CandleCondition(DOJI)` ∧ `close < ema_50` ∧ `rsi_14 < 35` ∧ time 09:30-15:00.
  Exit (OR): `rsi_14 > 60`; + SL 1.0% / TP 2.5% / square-off 15:00.
- **engulfing-candle-reversal** (mode beginner) — `rsi_14` only (trend filter dropped).
  Entry (AND): `CandleCondition(ENGULFING)` ∧ `CandleCondition(BULLISH)` ∧ `rsi_14 < 40` ∧ time.
  Exit: SL 1.5% / TP 4.0% / square-off 15:00 (no `indicator_exits` — the seed's candle/price
  exits aren't evaluated by the Phase-2 exit engine).

## Phases 4-5 — Test + regression results

### Phase 4 — new tests (`tests/strategy_engine/translator/test_candle_overrides.py`, 185 lines) → **6 passed**

- `test_candle_patterns_supported_by_engine` — doji/engulfing/bullish are real CandlePattern members.
- `test_doji_override_uses_doji_candle_condition` — entry carries `CandleCondition(DOJI)`.
- `test_engulfing_override_is_bullish_specific` — entry carries `ENGULFING` ∧ `BULLISH`.
- `test_2_targets_pass_validation` (×2) — translate → `model_validate` round-trip → synthetic backtest **trades ≥ 1**.
- `test_overrides_cover_exactly_the_two_slugs` — scope guard (hammer excluded).

Synthetic trade counts: **doji-reversal=23** (oversold decline + zero-body doji bars),
**engulfing-candle-reversal=11** (decline → pause → bullish engulf of the prior small bar, rsi<40).

### Phase 5 — regression

- **20/20 templates PASS** (12 baseline + 3 C2 + 3 D2 + 2 E2) → **coverage 18 → 20.**
- `tests/strategy_engine/translator/` + A2 `test_indicator_runner_sub_outputs.py` + `test_pack11_indicators.py` + `tests/services/test_pine_mapper_options.py` → **161 passed** (options 48 green).
- **`tests/strategy_engine/` — 25 failed, byte-identical to D2 base `b2c89ba`** (revert-and-diff → empty → **ZERO new failures**). All pre-existing pollution (api-auth/401, compliance, indicator_admin, registry).

## Live-trading risk: ZERO

- **Sacred files untouched**: `strategy_executor.py`, `direct_exit.py`, `api/webhook/*`, `kill_switch.py`, `brokers/*`, `alembic/versions/*`. LIVE BSE LTD `89423ecc-c76e-432c-b107-0791508542f0` path unaffected.
- **A2 / C2 / D2 source untouched**: only `override_registry.py` is edited (merges in candle overrides). `divergence_overrides.py` and `trend_overrides.py` not modified.
- **No live path imports the new code** — only the offline `clone_service.py` imports the translator (best-effort, non-fatal).

## Files changed (diff vs D2 base `b2c89ba`)

| File | Δ |
|---|---|
| `backend/app/strategy_engine/translator/candle_overrides.py` | +154 (new) |
| `backend/app/strategy_engine/translator/override_registry.py` | +10 / -3 |
| `backend/tests/strategy_engine/translator/test_candle_overrides.py` | +185 (new) |
| `docs/QUEUE_QQ_TRANSLATOR_E2.md` | this doc |

## Stack & next step

Stack: A2 `84ef9f9` → C2 `e8a589c` → D2 `b2c89ba` → E2 (this) — all unpushed, to merge to main together.
Coverage progression: `8 → 12 (A2) → 15 (C2) → 18 (D2) → 20 (E2)`.

Remaining FAIL_UNPARSEABLE actives for future queues: `bb-mean-reversion`, `bb-squeeze-breakout`,
`vwap-bounce`, `macd-histogram-momentum`, `donchian-channel-breakout`, `ichimoku-cloud-crossover`,
`adx-strong-trend-filter`, `camarilla-pivots-intraday`, `inside-bar-breakout`. To raise *active*
coverage further also consider whether `hammer-hanging-man-pattern` should be activated + given an
auto-support/resistance indicator.
