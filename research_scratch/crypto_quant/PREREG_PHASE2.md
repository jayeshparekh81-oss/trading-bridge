# PREREG — PHASE 2 GATING STUDY (BLUEPRINT v3, head 1e7ac830, sha256 7a67d68f…)

**Written and committed BEFORE any outcome was computed (A1).** The CP0 aggressor-flag and arrival-rate measurements that precede this file are data-quality checks, not outcome tests, and observe no forward return.

## The question

Was the delta / CVD / absorption family dead **everywhere**, or only dead on the NSE feed which could not tag aggressors at all (94.2% of depth intervals with no trade print, volume advancing in 20.3% of tick intervals, delta sign carrying 8–20% irreducible noise)?

## Data

- **Instrument:** BTCUSDT USDⓈ-M perpetual, Binance. One instrument only (Phase 1).
- **Source:** `data.binance.vision` daily `aggTrades`, public, unauthenticated, read-only.
- **Window:** 183 days ending 2026-09-06.
- **Aggressor convention, fixed here:** `is_buyer_maker = false` → the taker was the **buyer** (signed volume `+qty`); `true` → the taker was the **seller** (`−qty`). Verified populated at CP0.
- **Bars:** 1-minute, built from trades. `delta` = Σ signed qty in the bar. `CVD` = cumulative Σ delta.
- **σ:** trailing standard deviation of 1-minute log returns over the previous 60 bars, converted to price units at the event bar. Causal — no bar at or after the event contributes.

## Sealed split (A3)

Chronological. **Discovery = the first 70% of days; confirmation = the final 30%.** The confirmation half is quarantined by `cq_guards.SealedSplit`, which raises `SealedDataAccess` for any discovery-stage request; the guard is demonstrated firing in calibration C2. It is unlocked **once**, for the batch pre-registered in this file, and is then spent (v3-3).

## The three hypotheses — the complete list, fixed now

Each fires at the close of a 1-minute bar; entry is at the next bar's open.

- **H1 — CVD divergence.** Price makes a new 60-bar low while CVD does **not** make a new 60-bar low → **long**. Mirror (new 60-bar high, CVD does not confirm) → **short**.
- **H2 — Absorption.** `|delta|` in the top decile of its trailing 1440-bar distribution **and** `|bar return|` in the bottom tercile of its trailing 1440-bar distribution → take the side **opposite** the aggressor (aggressive flow absorbed by passive).
- **H3 — Aggressive-flow imbalance.** `delta / total_volume` in the top decile (or bottom decile) of its trailing 1440-bar distribution → take the side **with** the aggressor.

All deciles/terciles are computed on trailing windows only, strictly causal.

## Outcome measurement (A6)

One first-passage object per event: `t_up[k]` and `t_dn[k]` for `k ∈ {1.0, 1.5, 2.0, 3.0}` in σ units, plus MFE and MAE in σ. **Horizon 240 minutes.** Events resolving neither way inside the horizon are **censored and counted**, never dropped.

- **Primary cell per hypothesis:** target 1.0σ, stop 1.0σ.
- **Secondary cell per hypothesis:** target 2.0σ, stop 1.0σ.

## Hypothesis ledger (A2)

This study contributes **6 cells** (3 hypotheses × 2 (target, stop) pairs). Cumulative ledger count entering this study: **0** — this is the first entry against this dataset. Cumulative after: **6**.

**Adjustment: Bonferroni at 6.** α_adjusted = 0.05 / 6 = **0.008333**, two-sided. This α is used for every significance statement and for the MDE calculation.

## Independence and effective N (A10)

Default spacing rule: an event opening inside a prior surviving event's unresolved window is **suppressed**. Raw N, effective N and the variance ratio `effective_N / raw_N` are reported for every cell. Significance uses a **block bootstrap** with block length ≥ the median first-passage time, not an i.i.d. formula.

## Nulls (A4)

1. **Random-walk theoretical:** P(target first) = stop/(stop+target). 0.5000 at 1:1, 0.3333 at 2:1. Printed beside every result.
2. **Volatility-matched control:** non-event bars matched on hour-of-day **and** trailing-volatility quintile, drawn without replacement, under the same spacing rule. Unmatched events are reported, not dropped.

## Cost model (A8, v3-5)

`cost_R = (2 · f · p0 + spread + slippage) / (stop_k · σ)`, computed **per event** from the measured `p0` and `σ`.

- **`f` (fee rate) is a pre-registered parameter, not a measurement.** Grid: **{0.0002, 0.0005, 0.0010}** per side. The Binance published USDⓈ-M VIP0 schedule is the stated source; it is **NOT verified from a first-party endpoint in this run** and is recorded as such.
- **`spread` and `slippage` are NOT MEASURABLE from aggTrades** (no order book in this product) and are set to 0 in the primary computation. This makes every cost figure here a **lower bound**, and the verdict is stated accordingly.
- **Funding** is charged per A8/v3-5 as the actual 8-hourly stamps each holding path crosses, sign-aware, paid and received reported separately. Sub-stamp holds pay exactly zero. Funding rates for the window are NOT pulled in this study; funding is therefore reported as **stamps crossed per event** with the charge left as `NOT MEASURED` unless the rate series is obtained.
- **Every result states crossing vs posting.** These three rules all cross the spread on entry by construction, so the taker leg of the grid is the honest primary.

## The power gate (A5, v3-2) — binding

For each cell, at **effective N**:

- `p0` = the random-walk rate for that (target, stop).
- `worth_having` = `cost_R / (1 + target/stop)` — the smallest edge over the random walk that survives cost.
- `MDE` = smallest detectable |p − p0| at effective N, α = 0.008333 (ledger-adjusted), power = 0.80.

**If `MDE > worth_having`, the cell DOES NOT RUN.** It is recorded as `NOT RUN — UNDERPOWERED` with both numbers, and **consumes no hypothesis count**. A null from such a cell is `NOT MEASURED — POWER UNKNOWN` and is never written up as "no edge".

## Pass bar

A cell passes only if **all** hold:

1. Discovery hit-first rate exceeds the random-walk rate by more than `worth_having`, significant at α = 0.008333 under the block bootstrap;
2. It also exceeds the volatility-matched control by the same margin;
3. On the sealed confirmation set it holds the **same sign** with **comparable magnitude**;
4. Expectancy in R is **positive net of cost** at `f = 0.0005`;
5. Effective N is sufficient that the MDE gate passed.

## What would make this run wrong (3e)

If A5 calibration had failed, every number here would be void. It ran on synthetic data before any download and returned **8/8 GREEN** (C1 host guard, C2 sealed guard + single use, C3 disk/request limits, C4 random walk to theory at z = −0.09/+0.69/−0.04, C5 an effect injected **at** the MDE recovered at +0.02567 against 0.02556, C6 structureless events indistinguishable from null at z = +1.22, C7 per-stamp funding with sub-stamp zero, C8 2974 raw → 170 effective, variance ratio 0.0572).

## Gate semantics (v3-4)

- **Negative:** the family is dead with a clean aggressor tag too. Phases 3–5 order-flow infrastructure is not built.
- **Positive:** a discovery-stage positive does **not** authorise Stage 2 spend by itself; it must first survive confirmation on the sealed set at the ledger-adjusted bar.
- **Underpowered:** gates **nothing in either direction**, and is reported as such rather than as a negative.
