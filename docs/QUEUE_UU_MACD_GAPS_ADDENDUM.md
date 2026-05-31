# Queue UU — Gaps 1 / 2 / 3 Addendum (Real NIFTY + Architecture)

**Date:** 2026-05-31 (~30 min after main investigation)
**Trigger:** Founder asked for three more gap checks before merge:
Gap 1 = real NIFTY quantification, Gap 2 = Pine-docs comparison on
real NIFTY, Gap 3 = MACD-magnitude downstream scan.
**Conclusion:** Gaps clear from a customer-impact perspective. New
architectural finding changes the recommendation on the proposed
Option B+ tooltip (recommend **SKIP** — would misinform customers).

---

## Real NIFTY data — 4280 bars 5m, 60 calendar days (yfinance ^NSEI)

Saved to `/tmp/uu-venv/nifty_real_5m.csv`. Range: 22186 → 24975 (~2788
point spread); real-noise + gap-between-sessions structure.

### Gap 1 — aligned-seeded vs independent-seeded talib on real NIFTY

| Series | n compared | max abs Δ | mean abs Δ | p99 abs Δ | max % Δ |
|---|---:|---:|---:|---:|---:|
| macd_line | 4247 | **1.4916** | 0.0023 | 0.0012 | 4.71% |
| signal_line | 4247 | 3.1880 | 0.0057 | 0.0044 | 10.33% |
| histogram | 4247 | 1.6964 | 0.0034 | 0.0031 | 280.10% |

Real-NIFTY divergence is **2.3× the synthetic max** (0.92 → 1.49). Real
volatility produces bigger seeding-boundary amplitudes than the RC1
synthetic; the original "~0.6 at bar 33" Phase F number was on the
quieter 100-bar fixture.

### Sign-flips on real NIFTY

| Series | Sign flips | Total bars |
|---|---:|---:|
| macd_line (A vs independent) | **0** | 4247 ✓ Hard-stop clear |
| **histogram (A vs independent)** | **3** | 4247 ← new on real data |

The 3 histogram sign-flips happen in the seeding-boundary warmup region
(< bar 60). The macd line itself never flips direction.

### Crossover-timing on real NIFTY

| Convention | Crossovers | Crossunders |
|---|---:|---:|
| A (aligned, talib.MACD) | 146 | 147 |
| B (independent talib EMAs) | 146 | 146 |
| C (strategy_engine hand-roll) | 146 | 146 |

| Comparison | Crossover XOR | Crossunder XOR |
|---|---:|---:|
| A vs B | **2** | **1** |
| A vs C | **2** | **1** |
| **B vs C** | **0** | **0** (bit-identical) ✓ |

So aligned vs independent disagrees on 3 specific bars across 60 days.

### Gap 2 — Pine-docs reference (TV-spec hand-roll) on real NIFTY

The TRADETRI **strategy_engine.indicators.calculations.macd** is a
hand-rolled independent-EMA implementation (`ema()` for fast +
`ema()` for slow + `ema()` on the line for signal — each seeded with
its own SMA of its first `length` values). This IS the Pine-docs
convention. Per-bar comparison against `talib.EMA`-composed
independent seeding shows **bit-identical output** (max |Δ| = 0.0000
across 4247 bars on all three series). So:

- `strategy_engine.indicators.calculations.macd` = Pine-docs reference
- Validated against `talib.EMA` independent composition to machine
  epsilon on real NIFTY data

This **substitutes for an empirical TradingView UI check** (which was
the original 2026-05-25 deferral). The Pine-docs spec is what TV's
own documentation says `ta.macd` computes; our strategy_engine path
matches it numerically. If TV's UI matches TV's docs, the customer
sees the strategy_engine output on the chart and gets matching values
in backtest. We don't need a manual TV screenshot to know this.

### Gap 3 — downstream MACD-magnitude consumers

Scanned `backend/app/strategy_engine/indicators/calculations/` for
modules that consume MACD line or histogram **magnitude** (not just
sign):

| Module | What it uses | Impact under aligned-vs-independent divergence |
|---|---|---|
| `trend_continuation_score.py:74` | `h >= 0` (SIGN ONLY) | 0 — sign-only |
| `momentum_quality_score.py:55-57` | `abs(h) / (close * 0.005)`, clipped to [0,1] | max Δ 0.34/100 on real NIFTY (invisible) |
| `macd_divergence.py:29` + `_divergence.py` | macd line magnitude (extrema in 20-bar window) | 3 bars on real NIFTY (0.07%) where divergence code flips |
| `divergence_strength_score.py` | sum of three divergence codes | inherits the 3-bar diff from macd_divergence |

Customer impact for shipped templates:
- `macd-trend-signal` uses macd line + signal line crossovers + hist
  sign. Engine path (independent) is what fires trades. **Zero impact
  on customer trades** (engine always uses Pine-correct path).
- `macd-divergence` uses macd line for divergence detection. Engine
  path (independent) is what fires trades. **3 bars in 60 days where
  the divergence detector would fire differently if it used the
  aligned impl** — but it doesn't.

---

## Architectural finding — three MACD impls, one customer-facing

Pre-existing in the codebase, surfaced by this investigation:

| Impl | Convention | Surface | Customer-facing? |
|---|---|---|---|
| `frontend/src/lib/chart/indicators.ts:138` `computeMACD` | INDEPENDENT (Pine docs) | Chart panel overlay (LWC) | **YES — what users see** |
| `backend/app/strategy_engine/indicators/calculations/macd.py` `macd()` | INDEPENDENT (Pine docs) | Backtest engine + score systems + trade firing | **YES — trade outcomes** |
| `backend/app/services/indicators/macd.py` `MacdIndicator` | ALIGNED (TA-Lib industry default) | `POST /api/chart/indicator` HTTP endpoint | **NO** — admin/internal only |

**Verified the chart UI doesn't call `/api/chart/indicator` for MACD:**

```
grep -rn "api/chart/indicator|api/indicator\b" frontend/src
→ ZERO hits
```

The chart panel computes MACD entirely client-side in TypeScript from
the candle array. The aligned-seeded backend `MacdIndicator` is an
HTTP endpoint that the chart UI does not consume. Numerical check
confirmed FE `computeMACD` ≡ strategy_engine `macd()` at machine
epsilon (max |Δ| = 2.55e-11 on 4247 bars).

### Consequence for the user-proposed Option B+ tooltip

The user's pre-stated trigger:

> "If TV comparison shows ~0.6 divergence on real NIFTY, add Option B+
> UI tooltip in chart panel ('MACD: TA-Lib aligned warmup, may differ
> from TV in first 50 bars by ~0.5')."

Pre-stated assumption: the chart shows TA-Lib aligned MACD. Reality:
the chart shows independent-seeded (Pine-correct) MACD already.
Adding the tooltip with the pre-stated text would **misinform** the
customer (telling them the chart uses aligned when it uses
independent, and that values may differ from TV when they actually
match TV docs to machine epsilon).

**Recommendation: SKIP the tooltip.** No customer-trust action is
needed for the chart. The aligned-seeded impl on
`/api/chart/indicator` is not customer-visible, and its convention
choice is already documented in `macd.py` + this branch's
`QUEUE_UU_MACD_RESOLUTION.md`.

If a separate tooltip is desired for the **admin indicator API**
(e.g. for admins comparing API output against TV), that's a tiny
additive task with no customer-trust component. Not on this branch's
scope.

---

## Updated merge recommendation

**Merge as-is.** The branch fixes the deferred xfail correctly for
`services.indicators.macd` (the admin-internal impl). All three
gaps clear from a customer-impact perspective:

| Gap | Result |
|---|---|
| Gap 1 (real NIFTY quantification) | Done. Aligned-vs-independent diverges by up to 1.5 abs on warmup, 3 sign-flip bars, 3 crossover-XOR bars. NOT customer-visible (lives in admin endpoint only). |
| Gap 2 (Pine-docs reference on real NIFTY) | Done. strategy_engine impl is bit-identical to Pine-docs hand-roll. Chart + engine + scores all already match TV docs. |
| Gap 3 (MACD-magnitude downstream) | Done. Trade firing uses Pine-correct path. momentum_quality_score impact < 0.34/100. macd_divergence code differs on 3 warmup bars but trade firing uses the independent (Pine) path so customer is unaffected. |

The "1 hr Option B+ tooltip" is **not built** because the architecture
finding shows it would misinform customers about a divergence the chart
doesn't have.

### Optional follow-up sprints (not on this branch)

1. **Architectural cleanup**: consolidate the three MACD impls into one
   shared source of truth. The duplication is a maintenance hazard
   (future divergence could go unnoticed). Out of scope here; flag for
   a future sprint.
2. **Empirical TV UI screenshot test**: still nice-to-have for the
   change-log but no longer load-bearing on any customer decision.

---

## Artifacts on this addendum

- This document (`docs/QUEUE_UU_MACD_GAPS_ADDENDUM.md`).
- Cached real NIFTY data: `/tmp/uu-venv/nifty_real_5m.csv` (4280 bars,
  ^NSEI 5m, 60 days). Discardable; reproducible via `yfinance.download
  ("^NSEI", period="60d", interval="5m")`.
- No backend code touched on this round. The only-edits-from-the-main-
  investigation (commits `be81d97` + `9efe9cc`) remain unchanged.
