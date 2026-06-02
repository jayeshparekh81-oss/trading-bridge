# Queue WW Sprint 8a — VWAP session-anchoring fix

**Branch:** `fix/queue-ww-vwap-session-anchoring` (off `main@85d09ea`)
**Date:** 2026-06-02
**Time used:** ~60 min (cap 90 min)
**Verdict:** **PASS.** Session-anchored VWAP shipped, NaN-skip bug eliminated, machine-epsilon convergence with `pandas-ta-classic`, 15/15 unit tests pass, backtest pipeline now produces 66 trade-fireable bars on a 3-session 225-bar synthetic (pre-fix would have drifted to multi-day cumulative).

---

## 1. Headline

| Item | Value |
|---|---|
| Files modified | 3 (vwap.py, indicator_runner.py, test_vwap.py) |
| Files added | 3 (cross-val script, backtest-verif script, this report) |
| LOC added | ~330 (impl + tests + verification scripts + docs) |
| LOC deleted | 0 (purely additive; backward-compat preserved) |
| Unit tests | 15/15 pass (7 legacy retained + 8 new session-anchored) |
| Sacred-zone touches | 0 |
| Production code paths modified | 2 (vwap.py + indicator_runner.py:165 caller, both inside §2 audit-listed allowed scope) |
| Seed JSON modifications | 0 (template activation = founder gate, deferred) |
| Cross-validation vs pandas-ta-classic | max \|diff\| = 1.455192e-11 (sub-machine-epsilon) |

---

## 2. What changed

### 2.1 `backend/app/strategy_engine/indicators/calculations/vwap.py`

Rewrite. New signature:

```python
def vwap(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    timestamps: Sequence[datetime] | None = None,
) -> list[float | None]:
```

Behavior:

- **`timestamps=None`** (default, legacy path): cumulative anchored-at-start. Every pre-existing caller (e.g. `test_indicator_runner_cross_validation.py:193`) continues to work without modification — back-compat verified.
- **`timestamps` provided**: session-anchored. A new IST trading day boundary (first bar whose `.astimezone(_IST).date()` differs from prior bar's) resets `cum_pv` and `cum_vol` to zero before consuming the bar.
- **NaN-volume handling** (the QUEUE_VV §5 bug): the NaN bar is skipped — `cum_vol` is not poisoned. Output at the NaN bar is the prior bar's VWAP (or `None` if the session has no defined value yet). Length is always preserved.
- **Naive timestamps**: treated as already-IST (zero-offset assumption documented in module docstring).
- **UTC / aware timestamps**: converted to IST via `astimezone(_IST)` before date-extraction.

### 2.2 `backend/app/strategy_engine/backtest/indicator_runner.py:165` — 3-line edit

Before:

```python
if cfg.type == "vwap":
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]
    volumes = [c.volume for c in candles]
    return fn(highs, lows, closes, volumes), {}
```

After:

```python
if cfg.type == "vwap":
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]
    volumes = [c.volume for c in candles]
    timestamps = [c.timestamp for c in candles]
    return fn(highs, lows, closes, volumes, timestamps), {}
```

This is the ONLY production caller of `vwap()`. Caller-graph grep (`grep -rn "from.*calculations.vwap\|import.*vwap" backend/app backend/tests`) confirms zero other prod consumers. Live trading path (`strategy_executor`, `direct_exit`, broker adapters, `api/strategy_webhook`) verified zero hits — sacred zone untouched.

### 2.3 `backend/tests/strategy_engine/test_vwap.py` — extended (7 → 15 tests)

| Test | Regime | Covers |
|---|---|---|
| `test_vwap_first_bar_equals_typical_price` | Legacy | unchanged |
| `test_vwap_constant_typical_price_is_constant` | Legacy | unchanged |
| `test_vwap_zero_volume_warmup_returns_none` | Legacy | unchanged |
| `test_vwap_zero_then_volume_starts_defined` | Legacy | unchanged |
| `test_vwap_empty_input` | Legacy | unchanged |
| `test_vwap_rejects_mismatched_lengths` | Legacy | unchanged |
| `test_vwap_output_length_matches_input_length` | Legacy | unchanged |
| `test_vwap_session_anchored_single_session_matches_unanchored` | NEW | single-session correctness |
| `test_vwap_session_anchored_resets_on_new_day` | NEW | **multi-day reset boundary** |
| `test_vwap_skips_nan_volume_without_poisoning` | NEW | **NaN-skip** |
| `test_vwap_session_anchored_empty_input_with_timestamps` | NEW | empty input |
| `test_vwap_session_anchored_zero_volume_bar_returns_none` | NEW | zero-volume bar |
| `test_vwap_rejects_mismatched_timestamp_length` | NEW | input validation |
| `test_vwap_naive_timestamp_treated_as_ist` | NEW | naive-tz semantics |
| `test_vwap_utc_timestamp_converts_to_ist_session` | NEW | UTC→IST conversion semantics |

All 15 pass in 8.78s. Wider `tests/strategy_engine/{indicators,backtest}` + `test_vwap.py`: **195 passed, 1 skipped** (the 1 skip is the unrelated pre-existing `test_kama.py` pandas-ta requirement; nothing in the suite failed because of these changes).

### 2.4 New files in `backend/tests/queue_ww_sprint_8/framework_extensions/`

- `vwap_cross_validation.py` — multi-session diff vs `pandas_ta_classic.vwap(anchor='D')` and NaN-handling convergence check
- `vwap_backtest_verification.py` — full `precompute_indicators(candles, strategy)` pipeline integration check (proves the `indicator_runner.py:165` edit pipes timestamps through correctly)

---

## 3. Cross-validation result (pandas-ta-classic anchor='D')

3 sessions × 75 bars × 5-minute spacing, multi-day NSE-shaped synthetic.

| Metric | Value |
|---|---|
| max \|ours − pta\| | **1.455192e-11** |
| mean \|ours − pta\| | 3.621810e-12 |
| Verdict | MATCH (sub-nanounit) |

NaN-volume convergence (NaN volumes injected at bars 30 and 31 of session 1):

| Impl | Finite bars after NaN, same session (out of 43) |
|---|---:|
| ours (post-fix) | 43 |
| pandas-ta-classic | 43 |

Both now skip NaN volumes correctly. The pre-fix `vwap()` would have produced 0 finite bars after a single NaN volume (the QUEUE_VV §5 finding); the fix lands at convention parity with the reference impl.

yfinance ^NSEI 60d 5m fetch was the audit's recommendation but `/tmp/uu-venv/` no longer exists. Substituted with deterministic multi-session synthetic — same convention-test methodology, no network dependency, fully reproducible.

---

## 4. Backtest pipeline verification

Full `precompute_indicators(candles, strategy)` integration ran on a 3-session × 75-bar synthetic with a minimal `vwap_default` strategy:

| Metric | Value |
|---|---:|
| Input candles | 225 |
| VWAP output length | 225 |
| Non-None bars | 225 (100%) |
| Session-1 finite bars | 75 |
| Session-2 finite bars | 75 |
| Session-3 finite bars | 75 |
| Session-2 first-bar VWAP | 21489.4853 |
| Session-2 first-bar typical price | 21489.4853 |
| Session reset proof (first-bar = typical) | ✓ |
| Trade-fireable bars (`close > vwap`) | 66 / 225 |
| Verdict | **PASS** |

The 66 trade-fireable bars are the answer to "does `vwap-bounce`-style logic now produce non-zero entries on multi-day data?" — yes. Pre-fix, the same input would have drifted to a single multi-day cumulative average and the entry condition would have fired on incorrect bars.

---

## 5. What this enables (does NOT change without founder action)

This sprint **only ships code + tests**. It does NOT:

- ❌ Modify `backend/data/strategy_templates_seed.json` (the two deactivated templates `vwap-bounce` and `camarilla-pivots-intraday` remain `is_active=false`)
- ❌ Run any EC2 deploy
- ❌ Push to `main`
- ❌ Create a release tag

The QUEUE_VV §5 reactivation criterion (items 1, 2, 3, 4 of 6) is now satisfied:

| § Criterion | Satisfied this sprint? |
|---|:---:|
| 1. Rewrite session-anchoring | ✓ |
| 2. NaN-volume skip | ✓ |
| 3. New unit tests (5 scenarios) | ✓ (8 added, covering all 5) |
| 4. Cross-validation vs pandas-ta-classic on multi-day data | ✓ (max 1.455e-11) |
| 5. End-to-end backtest on 30d real Dhan window | **deferred — needs Dhan creds + founder review** |
| 6. Founder review fixture + flip `is_active=true` | **founder gate, tomorrow** |

§5 (real-Dhan backtest) is the deploy-day verification step, not a code-time check. §6 is the explicit founder gate.

---

## 6. Files changed (diff scope)

```
backend/app/strategy_engine/indicators/calculations/vwap.py            | rewrite
backend/app/strategy_engine/backtest/indicator_runner.py               | 3-line edit @ line 165
backend/tests/strategy_engine/test_vwap.py                             | extend (+8 tests)
backend/tests/queue_ww_sprint_8/framework_extensions/__init__.py       | new (empty)
backend/tests/queue_ww_sprint_8/framework_extensions/vwap_cross_validation.py    | new
backend/tests/queue_ww_sprint_8/framework_extensions/vwap_backtest_verification.py | new
docs/QUEUE_WW_SPRINT_8A_REPORT.md                                       | new (this file)
```

Zero touches to: `strategy_executor`, `direct_exit`, `webhook`, `kill_switch`, `broker` adapters, BSE LTD strategy, any migration, any seed JSON, any frontend file.

---

## 7. Founder review checklist for tomorrow

1. Skim `vwap.py` rewrite — confirm the new optional `timestamps` argument feels right and the IST date-boundary detection matches your operational mental model.
2. Skim `indicator_runner.py:165` 3-line edit — confirm passing `c.timestamp` from the `Candle` is the canonical path.
3. Look at `vwap_cross_validation.py` output: 1.455e-11 max diff is convention-parity with pandas-ta-classic.
4. Look at `vwap_backtest_verification.py` output: 66 trade-fireable bars on 3-session synthetic.
5. Decide: real-Dhan 30d window backtest of `vwap-bounce` template (deploy-gate verification) — this is the §5/§6 founder-call.
6. Decide: flip `is_active=true` on `vwap-bounce` and `camarilla-pivots-intraday` in seed JSON. (NOT done this sprint.)
