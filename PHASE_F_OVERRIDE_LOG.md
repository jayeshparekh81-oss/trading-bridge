# PHASE F — Override Log

Audit trail for one-time existing-file edits authorized under the
Phase F Component 1 sprint. Each entry documents scope, justification,
files touched, root cause analysis, and approver. New entries
require explicit founder authorization; precedent does not carry
forward to future sprints.

---

## 2026-05-17 — BB stddev math fix (APPLIED)

### Files (all authorized)

- `backend/app/services/indicators/bb.py` — lines 67-72 (Bessel correction removed) + docstring rewrite (lines 1-26)
- `backend/tests/services/indicators/fixtures/bb_expected.csv` — regenerated against Pine reference via post-fix `BollingerBandsIndicator` on existing `shared_input.csv`
- `backend/tests/services/indicators/test_bb.py` — lines 82-101 deleted (`test_pine_compat_correction_applied` — test asserted presence of the now-fixed bug; coverage preserved + improved by new `test_bollinger_matches_pine_reference` against independent pandas-ta-classic fixture)

### Scope

One-time. The test deletion is a direct consequence of the math fix, not new precedent for general test-file edits. Future sprints touching `app/services/indicators/*` or `tests/services/indicators/*` require their own founder authorization.

### Root cause (discovered during sprint)

May 9-10 weekend Day-6 build encoded a factual error: developer/CC believed Pine `ta.stdev` uses sample stddev (divisor `N-1`). Actually Pine `ta.stdev` defaults to `biased=true` (divisor `N`), same as TA-Lib's BBANDS internal. The applied "correction" therefore inflated bands by `sqrt(N/(N-1)) ≈ +2.60%` at length=20 (and equivalent scaling at other lengths). 100% deterministic, every post-warmup bar.

### Detection-mechanism failure

The bug went undetected for 8 days because of a closed loop with no independent ground truth:

1. The `bb_expected.csv` fixture was generated from TRADETRI's own (buggy) output, then committed.
2. The shape-correctness tests (`test_warmup_then_valid`, `test_band_ordering_*`, etc.) only verify structural properties that survive the inflation.
3. The `test_tradingview_result_match` test compared TRADETRI against the fixture — both reflected the same buggy output, so it passed.
4. The `test_pine_compat_correction_applied` test *explicitly asserted the buggy correction was applied* — directly defending the bug from being noticed.

Result: full self-confirmation. The Phase F sub-audit broke this loop by introducing an *independent* ground truth (pandas-ta-classic) and cross-verifying.

### Justification for fix

- `PHASE_F_DEVIATION_ANALYSIS.md` (Part 1) — empirical confirmation:
  - +2.60% band-width inflation (= `sqrt(20/19) - 1` exactly)
  - 3 signal-level disagreements on a 100-bar synthetic series (1 lower-band + 2 upper-band touches; 0 middle-crossover disagreements — sanity check passes)
  - ~10% estimated signal disagreement rate on a 5K-bar real backtest
- Independent verification via `pandas-ta-classic 0.5.44` confirmed Pine convention.
- Universal industry consensus: Pine `ta.bb`, TA-Lib `BBANDS`, and `pandas-ta-classic ta.bbands` all use biased (population) stddev. No defensible interpretation of the wrong-direction correction.

### Commits

```
63932b0 fix(indicators): BB stddev — remove erroneous Bessel correction at bb.py:67-72 (authorized override)
333b675 test(indicators): regenerate bb_expected.csv against Pine reference (authorized override)
a0bced4 test(indicators): delete obsolete test_pine_compat_correction_applied (authorized BB-fix consequence)
```

### Approver

Jayesh — explicit authorization on 2026-05-17 for `bb.py:67-72`, `bb_expected.csv` regen, and Option α₁ extension to delete the obsolete `test_pine_compat_correction_applied` test.

### Verification

- `pytest backend/tests/services/indicators/ -v` → 51 passed, 1 xfailed, 0 failed
- `pytest backend/tests/api/test_indicator.py -v` → 13 passed, 0 failed
- Phase F reference test `test_bollinger_matches_pine_reference` → PASS post-fix
- Cross-check: TRADETRI BB band-width now within 1e-8 absolute of pandas-ta-classic Pine reference (machine epsilon).

---

## 2026-05-17 — MACD seeding convention (DEFERRED — empirical verification pending)

### Status

Not applied. TRADETRI's `macd.py` preserves TA-Lib's aligned-seeding convention.

### Finding

`PHASE_F_COMPONENT_1_BLOCKERS.md` Finding #2 — `talib.MACD` does **not** equal `talib.EMA(close, fast) - talib.EMA(close, slow)`. Standalone TA-Lib EMA matches Pine docs' independent SMA-seeded convention to machine epsilon. But the internal `talib.MACD` uses ALIGNED EMA seeding: fast EMA seeded at index `slow-1` with `SMA(close[slow-fast..slow-1])` (the last `fast` closes immediately before the slow EMA's seed point), NOT at index `fast-1` with `SMA(close[0..fast-1])` as standalone `talib.EMA` does.

Both implementations exist in the wild:

- **Pine docs**: independent SMA seeding (matches my hand-roll, ~18.267 at bar 33)
- **TA-Lib + pandas-ta-classic `ta.macd()` default**: aligned seeding (~18.902 at bar 33)
- **pandas-ta-classic compositional via `ta.ema(presma=True)`**: independent seeding (matches Pine docs)

Empirical magnitude: ~0.6 absolute difference on `macd_line` at NIFTY price levels (~0.003% relative). Signal-relevant for crossover timing on tight strategies.

### Why not auto-fixed in this sprint

1. Pine docs and TradingView's actual implementation MAY disagree — without an empirical TradingView UI check we don't know which convention TV's `ta.macd` actually emits.
2. Re-implementing MACD to match the Pine docs (independent seeding) would diverge from TA-Lib + pandas-ta-classic + most charting libs — creating its own credibility risk if TV actually uses aligned seeding.
3. Customer-docs footnote about MACD convention is premature without that empirical evidence.

### Test status

`backend/tests/services/indicators/test_indicators_phase_f_reference.py::test_macd_matches_pine_reference` marked `@pytest.mark.xfail(strict=False)` with full Finding #2 reason. Test runs in CI but doesn't fail the suite. Becomes a watch-this-space marker until the TV check resolves it.

Commit: `daad5e7`.

### Post-launch action item (target: 2026-05-25)

1. Manually generate MACD(12,26,9) values in TradingView UI for the synthetic 100-bar NIFTY dataset (regenerate via `_generate_phase_f_fixtures.py` and load the close column into a Pine indicator script).
2. Compare TV's output to:
   - TRADETRI's output (aligned seeding) — call this match `A`
   - Hand-rolled independent-seeded reference — call this match `B`
3. Whichever convention matches TV empirically becomes canonical.
4. **If TRADETRI matches TV** (`A`): un-xfail the test by regenerating `macd_12_26_9_pine_expected.csv` against the aligned-seeding output, remove the xfail decorator, close this open item.
5. **If TRADETRI does NOT match TV** (`B`): separate authorized sprint to fix `macd.py` (rewrite to use independent EMAs) + regen `macd_expected.csv` + customer disclosure.

### Approver

Jayesh — explicit decision on 2026-05-17 to defer MACD code change pending empirical TV check. No customer-facing docs footnote about MACD until the check completes.
