# Queue RR — Zero-Trades Root-Cause Diagnosis (DISCOVERY ONLY)

**Status:** Investigation complete. **No code changed.** This document is the
only artifact produced.

**Scope:** Why did the translator-stack templates (A2 `84ef9f9` → C2 `e8a589c`
→ D2 `b2c89ba` → E2 `04a0ddd`, merged `99c5473`) show **0 trades / ₹0** in the
production browser backtest, while CC's unit tests showed trades?

**Method:** static code-path tracing + empirical reproduction against the *real*
engine (current `main` `4da606a`, which contains the full stack) and an isolated
`6bf7f26` worktree (the code production is currently rolled back to). Production
DB inspected read-only.

---

## TL;DR — there are TWO independent causes, not one

1. **Divergence family (`rsi-divergence`, `macd-divergence`, `obv-divergence`):
   0 trades is EXPECTED on the production synthetic data — NOT a bug.** The
   production backtest's placeholder series is a *pure periodic sine*, which by
   construction contains **no divergence**, so `*_divergence > 0` fires on **0 of
   700** bars. Reproduced (0 locally too); engineered data → 10 trades.
   → Hypotheses **H1 + H2 + H5** (data shape / length / "needs real structure").

2. **All other newly-unlocked templates (trend, candle, sub-output): they DO
   trade on the stack — production's 0 is a ROLLBACK/SCHEMA incompatibility.**
   The A2 layer added an `output` field to `IndicatorConfig`. Strategies created
   under the stack store `"output": null`. Production is currently rolled back to
   `6bf7f26`, whose `IndicatorConfig` has **no `output` field and
   `extra="forbid"`**, so `StrategyJSON.model_validate(stored_json)` **raises
   `extra_forbidden`** → the backtest cannot run → surfaces as 0/₹0.
   → **NEW hypothesis H6 (schema forward-incompatibility across the rollback).**

Neither cause is a defect in the translator stack's engine logic. On the full
stack, every template that *can* express its setup on the synthetic data trades.

---

## Production backtest path (Phase 1, with citations)

- Endpoint: **`POST /api/strategies/{strategy_id}/backtest`** →
  `run_strategy_backtest` at
  `backend/app/strategy_engine/api/backtest.py:230`. (The async
  `backtest_extension` router is **not** mounted in `app/main.py`.)
- Flow: load `Strategy.strategy_json` → `StrategyJSON.model_validate(...)`
  (`backtest.py:254`) → `_resolve_candles()` → `run_backtest(BacktestInput(...))`
  (`backtest.py:264`).
- **Synthetic fallback:** `_synthetic_candles(n=120)` at `backtest.py:628-651`.
  Pure sine: `mid = 100 + 5·sin(i/8)`, `close = mid + 0.2·sin(i/4)`, 1-min bars,
  start `2026-01-01 09:30 UTC`. Bar count **hardcoded 120**, not request-driven.
  **Identical** between deployed `99c5473` and current `main` (git-verified).
- **Override registry is consumed only at TRANSLATE/CLONE time**
  (`translator/parser.py:100` via `clone_service.py:185`), **not** at backtest
  time. Backtest uses the **stored** `strategy_json`. Overrides are populated at
  import (`translator/override_registry.py:33`) and confirmed present at runtime.

---

## Hypothesis matrix (evidence per H1–H6)

| # | Hypothesis | Verdict | Evidence |
|---|-----------|---------|----------|
| **H1** | Synthetic data too short (120 vs 720) | **Partial — not the lever** | rsi-divergence = 0 trades at 120 **and** 360 **and** 720 bars. Length alone does not fix it. |
| **H2** | Synthetic data shape mismatch | **CONFIRMED (divergence subset)** | `_synthetic_candles` is a pure sine. `rsi_divergence` series = `0.0` on **0/700** bars → `rsi_div>0` never true → AND-entry never fires. Engineered candles → **10 trades** (engine fine). |
| **H3** | Engine evaluation regression (A2 `output`) | **Rejected (on the stack)** | On current `main`, stored Supertrend JSON trades 2/6/6; sub-output template `macd-trend-signal` trades 2/6. Engine reads `output` correctly (`indicator_runner.py:93-102`). |
| **H4** | DSL pipeline / "Legacy / not set" | **Rejected** | "DSL configured (legacy row)" is just a null-`strategy_json` guard (`backtest.py:248`). User saw an equity curve ⇒ backtest ran ⇒ JSON present. Not a separate pipeline. |
| **H5** | Expected (designed for real data) | **CONFIRMED (divergence subset)** | Divergence is a multi-bar swing relationship; a periodic sine has none. These templates need real (or structured) data to fire. |
| **H6** | **Schema forward-incompat across rollback** | **CONFIRMED (all non-divergence)** | `6bf7f26` `IndicatorConfig` has no `output` + `extra="forbid"`; `model_validate(stored_json)` → `extra_forbidden` on `indicators.*.output`. Production is rolled back to `6bf7f26` → stack-created strategies cannot be parsed → backtest errors → 0/₹0. |

---

## Empirical reproduction (Phases 2–4)

Engine: real `run_backtest`. Data: production `_synthetic_candles`.

```
rsi-divergence (current main / full stack):
  prod-sine n=120 → 0 ;  n=360 → 0 ;  n=720 → 0
  shifted into 09:30–15:00 IST, n=120 → 0 ; n=720 → 0   (time gate is NOT the blocker)
  rsi_div>0 fires on 0/700 bars; all non-null divergence values = 0.0
  ENGINEERED unit-test candles → 10 trades            (engine path proven good)

macd-trend-signal (A2) prod-sine → n=120: 2 , n=720: 6
supertrend-rider   (D2) prod-sine → n=120: 2 , n=720: 6
doji-reversal      (E2) prod-sine → n=120: 3 , n=720: 17

Stored prod strategy "Supertrend Rider (from template)" (id 1b56365b):
  current main (stack) → n=120: 2 , n=360: 6 , n=720: 6      ✅ trades
  6bf7f26 (rolled-back prod) → ValidationError: indicators.0.output
                               "Extra inputs are not permitted [extra_forbidden]"  ❌ cannot run
```

Production DB (read-only): only **one** stack-derived saved strategy exists —
`Supertrend Rider (from template)` (`1b56365b`, created 2026-05-30), with a valid
override-shaped `strategy_json` (carries `"output": null`). No divergence/doji
strategies are persisted (those backtests were ad-hoc template runs).

### Hard-stops encountered
- **Hard-stop #1 (local > production)** TRIGGERED for trend/candle/sub-output
  templates: they trade locally on the stack but showed 0 in production → this is
  an **environment/version difference**, traced to the rollback (**H6**), not an
  engine bug. Reported here rather than "fixed."

---

## Confirmed root causes

**RC-1 (divergence subset): degenerate synthetic data.** The production
placeholder series cannot express divergence; `*_divergence` is flat-zero on a
sine. This is correct behaviour given the input — the templates are sound.

**RC-2 (everything else): schema forward-incompatibility surfaced by the
rollback.** A2's `IndicatorConfig.output` is written into stored `strategy_json`,
but the rolled-back `6bf7f26` schema forbids unknown fields, so every
stack-created strategy fails validation on the live (rolled-back) code. On the
stack itself these templates trade.

---

## Recommended fix scope (read-only recommendation — founder decides)

1. **RC-1 — synthetic data (the real product gap).** Replace/augment
   `_synthetic_candles` with a **structurally rich** generator: trend legs +
   pullbacks + a few engineered divergence/reversal segments + an in-session IST
   timestamp window — OR (preferred) wire the backtest to **real Dhan historical
   data** (the generator's own docstring defers this to "Phase 8B/9"). Until
   then, divergence/swing templates will always read 0 on the placeholder, which
   is misleading in the UI. *Effort: ~3–5 h for a richer generator; ~1–2 d for
   real-data wiring.*

2. **RC-2 — make the schema rollback-safe.** The `output` field + `extra=forbid`
   combination is a migration landmine: once strategies are saved under the
   stack, the app can never be rolled back below the field without bricking those
   strategies' backtests. Options: (a) re-deploy the stack (forward, not back) so
   `output` is understood — the templates then work; (b) if a rollback below the
   field is ever needed, relax `extra` to `ignore` on the read path, or
   data-migrate `output` out of stored JSON. *Effort: deploy = minutes;
   `extra=ignore` shim = ~1 h + tests.*

3. **UI honesty:** confirm whether a failed `model_validate` renders as "0 trades
   / ₹0" rather than an error — if so, that masking is itself worth a fix so a
   validation failure is never mistaken for a flat strategy.

---

## Confidence & remaining unknowns

- **RC-1: HIGH.** Directly reproduced; the divergence series is provably flat on
  the sine, and engineered data trades.
- **RC-2: HIGH** for the mechanism (the `extra_forbidden` error is reproduced on
  `6bf7f26` against the actual stored JSON). **MEDIUM** on whether the user's
  *original* 0-trades observation (pre-rollback, on the stack) was RC-1-only
  (divergence) vs already mixing RC-2 — the timeline of which code was live at
  each backtest is not fully pinned. The user reported "ALL 12 = 0"; on the stack
  only the 3 divergence templates are structurally 0, the other 9 trade — so the
  uniform "all 0" is best explained by RC-2 (rolled-back code rejecting every
  stack-shaped strategy).
- Unknown: exact UI rendering of a validation error (assumed → "0/₹0").
- Unknown: whether ad-hoc (unsaved) template backtests use a different
  strategy_json source than saved strategies.

## Estimated total fix effort
- Quick unblock (re-deploy stack forward): **minutes** (RC-2 disappears; RC-1
  remains a data-quality caveat).
- Proper fix (richer/real backtest data + `extra=ignore` read shim + UI error
  surfacing): **~1–2 days**.

---

*Investigation time: ~70 min. Files created: this document only. No source,
branch, or production change.*
