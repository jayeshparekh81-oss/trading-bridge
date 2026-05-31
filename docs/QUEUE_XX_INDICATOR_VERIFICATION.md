# Queue XX — Indicator Verification Sweep

**Mission:** Tier-classify all 234 indicators in
`backend/app/strategy_engine/indicators/calculations/` so every customer
backtest / live signal runs on a confidence-tier-known foundation.

**Multi-sprint plan:**
- Sprint 1 (this doc) — top 7 priority indicators + reusable framework
- Sprint 2 — next 30 (deep verify, founder-curated)
- Sprint 3 — autonomous overnight CC pass on remaining ~184 (shallow)
- Sprint 4 — deep audit of Sprint 3 flagged items only

End state target: 234 indicators with `(name, tier, reason)` triple.

---

## 1. Confidence tier system (locked Sprint 1)

| Tier | Criteria | Action |
|---|---|---|
| **A — Production confident** | max abs Δ < 1e-6 against canonical reference AND 0 sign-flips AND 0 threshold-flips on real data | Ship as-is, no docs note |
| **B — Production OK** | 0 sign-flips AND 0 threshold-flips at canonical signal levels (signal-equivalent, small numerical accumulation noise) | Ship with one-line docstring noting the convention choice |
| **C — Needs decision** | 0.1%–5% divergence AND ≥1 threshold-flip OR convention mismatch (multiple wild conventions) | Founder decision — like Queue UU MACD seeding |
| **D — Needs fix** | Sign-flips OR > 5% divergence with threshold-flips OR NaN-poisoning OR all-NaN-on-real-data | Queue-WW-style sprint + deactivate consuming templates if customer-facing |

**Signal-equivalence dominates numerical divergence.** An indicator with 0.85%
drift but 0 threshold-flips at canonical trigger levels (e.g., ADX > 25) is
*signal-equivalent* — every trade decision is identical. That's Tier B, not C.
This rule was locked after ADX(14) showed 0.85% drift vs talib but 0 threshold-
flips at [20, 25] — the divergence sits where it can't change a decision.

---

## 2. Reference cascade (revised after Sprint 1 dogfood)

1. **TA-Lib direct** — primary where TA-Lib has the indicator. Industry default,
   matches Pine docs for canonical implementations.
2. **Hand-rolled Pine reference** — fallback for TA-Lib-missing indicators
   (Donchian, Ichimoku, and most of the Pack-2-16 custom indicators). Each
   indicator's verification block contains an inline reference function
   ~10-15 lines, auditable by reading.
3. **pandas-ta-classic** — SECONDARY cross-check ONLY. Sprint 1 discovered
   `pta.stoch` returns values that don't column-map cleanly (different output
   semantics than the column names suggest). Use only with per-indicator
   column verification.

**Why this changed mid-Sprint-1:** the initial framework defaulted to pandas-ta-
classic as primary. Stochastic dogfood showed pta.stoch's `STOCHk` column
diverging by ~85 absolute on a 0-100 scale vs both TRADETRI and TA-Lib (which
matched at sub-epsilon). pta-classic isn't a reliable plug-and-play reference
for every indicator.

---

## 3. Test data sources (locked Sprint 1)

### `/tmp/uu-venv/nifty_real_5m.csv` (yfinance ^NSEI 5m, 4280 bars, 60 days)
- Use for: non-volume indicators (SMA, EMA, RSI, MACD, BB, Stochastic, ADX,
  Donchian, Ichimoku, ROC, CCI, ATR, William %R, Aroon, parabolic SAR, etc.)
- **DO NOT use for volume-dependent indicators** — ^NSEI is an index, not a
  tradable instrument, so volume is zero on every bar. Sprint 1's MFI Tier-D
  false alarm came from this.

### `/tmp/uu-venv/reliance_real_5m.csv` (yfinance RELIANCE.NS 5m, 4291 bars, 60 days)
- Use for: MFI, OBV, VWAP (when fixed), CMF, Volume SMA, A/D Line, OBV
  divergence, money-flow indicators in general.
- Volume range `[0, 9.8M]` with ~99% of bars having non-zero volume.

### Synthetic 720-bar RC1 series (for session-boundary edge cases)
- Already used by Queue UU/VV. Single intraday session, 6 regimes packed in
  the structural portion. Useful for VWAP session-anchoring tests when that
  fix lands.

---

## 4. Sprint 1 results — 7 priority indicators

All verifications on real NIFTY (or RELIANCE for volume-aware) 4280-bar 5m
data. Pairwise max abs Δ shown vs primary reference.

| # | Indicator | Reference | max abs Δ | mean abs Δ | Threshold-flips | Sign-flips | NaN | **Tier** | One-line reason |
|---|---|---|---:|---:|---:|---:|---|:---:|---|
| 1 | **Stochastic(14, 3)** %K + %D | TA-Lib STOCH (slow, k=1) | 1.42e-14 | 2.02e-15 | 0 @ [20, 80] | 0 | finite=4267/4280 | **A** | ≡ TA-Lib at sub-epsilon; Lane canonical formula, Pine docs aligned |
| 2 | **ADX(14)** ADX + ±DI | TA-Lib ADX / PLUS_DI / MINUS_DI | 0.324 (ADX), 0.31 (-DI) | 2.7e-3 | 0 @ [20, 25] | 0 | finite=4253/4280 | **B** | 0.85% max rel drift from Wilder smoothing accumulation; zero threshold-flips = signal-equivalent |
| 3 | **Donchian Channel(20)** | hand-rolled max/min | 0.0 (exact) | 0.0 | 0 | 0 | finite=4261/4280 | **A** | Bit-identical to canonical max(high[-n:]) / min(low[-n:]) |
| 4 | **Ichimoku(9, 26)** Tenkan + Kijun | hand-rolled (h+l)/2 midline | 0.0 (exact) | 0.0 | 0 | 0 | finite=4272/4280 | **A** | Bit-identical to TV-Pine `ta.donchian` style midline |
| 5 | **MFI(14)** | TA-Lib MFI (on RELIANCE.NS — ^NSEI volume is zero) | 6.54e-13 | 8.96e-14 | 0 @ [20, 80] | 0 | finite=4277/4291 | **A** | ≡ TA-Lib at sub-epsilon; first run on ^NSEI flagged Tier-D from volume=0 data — methodology, not bug |
| 6 | **ROC(10)** | TA-Lib ROC | 1.11e-14 | 4.04e-15 | 0 @ [0] | 0 | finite=4270/4280 | **A** | ≡ TA-Lib at sub-epsilon; trivial close[i]/close[i-n] − 1 formula |
| 7 | **CCI(14)** | TA-Lib CCI | 1.87e-10 | 8.50e-12 | 0 @ [−100, +100] | 0 | finite=4267/4280 | **A** | ≡ TA-Lib at sub-epsilon; mean-deviation normalization matches Pine docs |

**Tier distribution Sprint 1:** 6 × A, 1 × B, 0 × C, 0 × D.

---

## 5. Cumulative scoreboard (Queue UU + Queue VV + Sprint 1)

| Indicator | Tier | Source |
|---|:---:|---|
| MACD(12,26,9) | A | Queue UU — ≡ FE TS, ≡ strategy_engine (both Pine-correct); services-aligned chain deleted |
| SMA(20) | A | Queue VV — ≡ all 3 impls at 5.82e-11 (machine ε) |
| EMA(20) | A | Queue VV — ≡ FE TS at 0.000e+00 (bit-identical); ≡ services at 1.46e-11 |
| RSI(14) | A | Queue VV — ≡ all impls at 2.13e-14 |
| BB(20, 2.0) | A | Queue VV — ≡ services at 1.30e-07 (post-Phase-F-fix) |
| ATR(14) | A | Queue VV — single impl, output sanity verified (range 12.82–88.26 NIFTY 5m) |
| VWAP | **D** | Queue VV — anchored-at-start cumulative, no session reset; consuming templates deactivated (release-cutover-4) pending Queue-WW fix |
| Stochastic(14, 3) | A | Sprint 1 |
| ADX(14) | B | Sprint 1 — 0.85% Wilder noise, signal-equivalent |
| Donchian(20) | A | Sprint 1 |
| Ichimoku(9, 26) | A | Sprint 1 |
| MFI(14) | A | Sprint 1 (RELIANCE.NS) |
| ROC(10) | A | Sprint 1 |
| CCI(14) | A | Sprint 1 |

**14 verified total. 12 × A, 1 × B, 1 × D.** D = VWAP, already de-risked via
template deactivation.

---

## 6. Sprint 2 candidate list (next 30, founder-curated priority)

### Priority tier 1 — indicators in **active** templates (post-VWAP-deactivation)

Frequency = how many active templates reference the indicator:

| Freq | Indicator | Notes |
|---:|---|---|
| 4× | `macd_12_26_9` | ✓ already Tier A (Queue UU) |
| 4× | `rsi_14` | ✓ already Tier A (Queue VV) |
| 3× | `ema_20` | ✓ already Tier A (Queue VV) |
| 3× | `bb_20_2` | ✓ already Tier A (Queue VV) |
| 2× | `ema_50` | inherits Tier A via param robustness |
| 1× each | `supertrend_10_3`, `atr_14`, `orb_15`, `donchian_20`, `ichimoku`, `adx_14`, `williams_pct_r`, `cci_20`, `aroon_14`, `obv`, `cmf_20`, `mfi_14`, `hull_ma_20`, `inside_bar`, `engulfing_pattern`, `doji_pattern` | Sprint 1 covered 6 of these; remaining 10 are Sprint 2 deep targets |

**Sprint 2 deep verify candidates (~12):**
- `supertrend_10_3` (ATR-based trend follower)
- `williams_pct_r` (oscillator)
- `aroon_14` (trend detector)
- `obv` (volume — needs RELIANCE.NS)
- `cmf_20` (Chaikin Money Flow — volume)
- `hull_ma_20` (custom MA)
- `inside_bar`, `engulfing_pattern`, `doji_pattern` (candlestick pattern detectors)
- `orb_15` (Opening Range Breakout — session-aware, may have VWAP-style issues)
- `parabolic_sar` (referenced by 1 template via mapping)
- `keltner_channel` (referenced by 1 template)

### Priority tier 2 — indicators in **inactive** templates (might activate)

About 22 unique indicators. Treat as Sprint 3 candidates unless a future
template re-activation needs them.

### Priority tier 3 — indicators NOT referenced by any template

About ~190 indicators. Sprint 3 autonomous shallow audit.

---

## 7. Sprint 3 readiness — autonomous overnight CC

For Sprint 3 (8–12 hr autonomous CC run on ~184 remaining indicators), the
framework needs:

1. **Auto-discovery** — `glob` the `calculations/` directory, parse each
   `def <name>(` signature, infer needed inputs (highs/lows/closes/volumes/periods).
   Skip private (`_*`) modules.
2. **Reference auto-resolver** — try TA-Lib `talib.<NAME.upper()>` first; if
   not present, try `pandas_ta_classic.<name>`; if neither, mark as
   `NEEDS_HANDROLL` and put in Sprint 4 queue.
3. **Skip list** — Sprint 1's 7 + Queue UU/VV's 7 = 14 already done.
   Sprint 2's ~12 (when complete) added to skip list before Sprint 3.
4. **Output schema** — single CSV: `name, tier, max_abs, mean_abs, sign_flips, threshold_flips, finite_count, reason`.
5. **Auto-flag rules** — any of: `tier=D`, `tier=C`, NaN finite_count < 0.5 ×
   total, sign_flips > 0 → flagged for Sprint 4 deep audit.
6. **Volume-data routing** — module-name pattern match: if name contains
   `mfi|obv|vwap|volume|cmf|ad_line|money_flow|chaikin` → use RELIANCE.NS;
   otherwise ^NSEI.

These six rules can be coded as ~150 LOC of extension to
`_xx_verification_framework.py`. To be written at the start of Sprint 3.

---

## 8. Lessons learned this sprint (worth capturing for the next agent)

1. **pandas-ta-classic column semantics are quirky.** Don't trust column-0-is-K
   assumptions. Per-indicator verification of pta's output meaning is needed
   before treating it as a reference. TA-Lib is the safer primary.
2. **Volume-data routing matters.** yfinance index symbols (`^NSEI`,
   `^NSEBANK`) have zero volume — MFI/OBV/VWAP comparisons fail meaninglessly.
   Always route volume-aware indicators to a tradable ticker (RELIANCE.NS,
   INFY.NS, etc.).
3. **Signal-equivalence dominates numerical drift in tier classification.**
   ADX's 0.85% drift looks like Tier C on raw numbers but is signal-equivalent
   (0 threshold-flips at [20, 25]). The framework's `classify_tier` was
   updated mid-sprint to put threshold-flip count ahead of pure relative-
   percent.
4. **Function signatures vary across the calculations directory.** Ichimoku's
   `(highs, lows, tenkan, kijun)` vs my assumption of `(highs, lows, closes)`
   crashed the batch run. Sprint 3 autonomous needs robust signature
   introspection (parse `inspect.signature`, route inputs by name).
5. **Hand-rolled references are surprisingly cheap.** Donchian and Ichimoku
   midlines are ~5 lines each. For the ~30 Pack-2-16 indicators in
   `calculations/`, hand-rolled references will likely outperform pandas-ta-
   classic on reliability per minute of investment.

---

## 9. Artifacts (Sprint 1 deliverables)

- `backend/tests/indicators_audit/_xx_verification_framework.py` (~250 LOC)
  — reusable framework: `diff_series`, `threshold_flips`, `nan_sanity`,
  `classify_tier`, `load_real_nifty`, `IndicatorVerdict`, `DiffStats`.
- `docs/QUEUE_XX_INDICATOR_VERIFICATION.md` — this document.
- Test data caches (regenerable):
  `/tmp/uu-venv/nifty_real_5m.csv`,
  `/tmp/uu-venv/reliance_real_5m.csv`.

---

## 10. Status summary

- **Sprint 1 budget used:** ~2 hours of the 4-hour allotment.
- **Verified count:** 14 cumulative (target was 14–20 per spec; landed at lower bound but with high confidence).
- **Tier distribution:** 12 A, 1 B, 1 D (the D is VWAP, already de-risked).
- **Branch:** `verify/queue-xx-sprint-1` — 1 commit pending.
- **Next:** Founder approval to merge Sprint 1; Sprint 2 starts next session
  with the ~12 candidates listed in §6.
