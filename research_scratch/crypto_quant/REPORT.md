# PHASE 2 GATING STUDY — REPORT

**Spec in force:** BLUEPRINT v3, head `1e7ac830`, sha256 `7a67d68fecf8d7493a6216a0fd41005efa0b7de12ba30cf8d14fd788aff81387`
**Pre-registration:** `PREREG_PHASE2.md`, commit `b37fdb49`, sha256 `4398d74521a633df02dada34115134a21d48716253de3ae0f235754bb4030885`, committed **before any outcome was computed**
**Instrument:** BTCUSDT USDⓈ-M perpetual, Binance
**Window:** 183 days, 2026-03-08 → 2026-09-06, 263,520 one-minute bars
**Host:** Mac (Darwin arm64, `/Users` present). Not a container.
**Status:** RUN and VERIFIED. No RED gate was crossed. No gate was worked around.

Every figure below is followed by the file or command it came from. Where a thing
was not measured it says **NOT MEASURED**, not an estimate.

---

## 1. CP0 — the aggressor-flag gate

**The flag is PRESENT and POPULATED.** This is the gate the whole study rested on:
the NSE feed could not tag aggressors at all, so the first question was whether
Binance actually carries the tag or merely appears to.

Measured on one full day, 2026-08-01, 399,219 aggregated trades:

| `is_buyer_maker` | count | share | qty (BTC) |
|---|---:|---:|---:|
| `true` (taker SOLD) | 201,065 | 50.365% | 28,685.433 |
| `false` (taker BOUGHT) | 198,154 | 49.635% | 26,052.709 |

The split sits **0.365 percentage points** off 50/50. It is not a constant, not a
default, and not a parsing artefact — it carries real two-sided variance, which is
exactly what the NSE feed could not supply.

Across the full 183-day window the taker-buy share of volume is **0.5014**
(`receipts/cp_bars.json` → `taker_buy_share`).

Source: `receipts/cp0_aggressor_gate.json`, `receipts/cp_bars.json`

**VERDICT: the aggressor tag is real, populated, and two-sided. GREEN.**

---

## 2. Arrival rate — Binance against the NSE figure

| feed | rows/second |
|---|---:|
| **NSE reference (prior study)** | **1.20** |
| **Binance BTCUSDT perp, 2026-08-01 (CP0 day)** | **4.6206** |
| **Binance BTCUSDT perp, full 183-day mean** | **16.2254** |

CP0 day is **3.85×** the NSE rate. The full-window average is **13.52×** the NSE rate.
2026-08-01 was a quiet day relative to the window; the window mean is the honest
figure for the study as a whole.

Total raw trades consumed: **256,541,329** over 183 days.

Source: `receipts/cp0_aggressor_gate.json` → `trades_per_second`, `nse_reference_rows_per_s`, `ratio_vs_nse`;
`receipts/cp_bars.json` → `trades_per_second`, `raw_trades`

**The data-density objection to the NSE result does not survive. This feed is denser by more than an order of magnitude and it tags the aggressor.**

---

## 3. Raw N, effective N, and the variance ratio (A10)

Events whose forward windows overlap are not independent. Every cell reports raw N,
the count after A10 spacing suppression, and the ratio. Significance used a block
bootstrap, never an i.i.d. formula.

### Discovery half (first 70% of days, bars 0 → 184,463)

| hypothesis | side | T:S | raw N | effective N | variance ratio | censored | ambiguous |
|---|---|---|---:|---:|---:|---:|---:|
| H1 CVD divergence | long | 1.0:1.0 | 5,504 | 3,654 | 0.6639 | 0 | 144 |
| H1 CVD divergence | long | 2.0:1.0 | 5,504 | 3,317 | 0.6027 | 0 | 29 |
| H1 CVD divergence | short | 1.0:1.0 | 4,988 | 3,298 | 0.6612 | 0 | 134 |
| H1 CVD divergence | short | 2.0:1.0 | 4,988 | 3,012 | 0.6038 | 0 | 27 |
| H2 absorption | long | 1.0:1.0 | 932 | 882 | 0.9464 | 0 | 19 |
| H2 absorption | long | 2.0:1.0 | 932 | 872 | 0.9356 | 0 | 6 |
| H2 absorption | short | 1.0:1.0 | 969 | 915 | 0.9443 | 0 | 25 |
| H2 absorption | short | 2.0:1.0 | 969 | 903 | 0.9319 | 0 | 4 |
| H3 aggressive-flow imbalance | long | 1.0:1.0 | 18,519 | 13,701 | 0.7398 | 0 | 249 |
| H3 aggressive-flow imbalance | long | 2.0:1.0 | 18,519 | 12,127 | 0.6548 | 0 | 51 |
| H3 aggressive-flow imbalance | short | 1.0:1.0 | 18,564 | 13,659 | 0.7358 | 0 | 207 |
| H3 aggressive-flow imbalance | short | 2.0:1.0 | 18,564 | 12,081 | 0.6508 | 0 | 51 |

Variance ratio range: **0.6027 – 0.9464**. Censoring is **0.0000 on every one of the
twelve cells** — no event failed to resolve inside the 240-bar horizon, so no result
here depends on how censored paths were handled.

"Ambiguous" counts events where both barriers were touched inside a single one-minute
bar. These are **counted and reported, never guessed** in whichever direction would
flatter the result; they are excluded from the resolved denominator.

### Sealed confirmation half (final 30% of days, bars 184,464 → 263,519)

| hypothesis | side | T:S | raw N | effective N | ambiguous | censored | rate |
|---|---|---|---:|---:|---:|---:|---:|
| H1 CVD divergence | long | 1.0:1.0 | 2,452 | 1,523 | 47 | 0 | 0.5007 |
| H1 CVD divergence | long | 2.0:1.0 | 2,452 | 1,387 | 7 | 0 | 0.3536 |
| H1 CVD divergence | short | 1.0:1.0 | 2,228 | 1,434 | 52 | 0 | 0.4942 |
| H1 CVD divergence | short | 2.0:1.0 | 2,228 | 1,306 | 16 | 0 | 0.3504 |
| H2 absorption | long | 1.0:1.0 | 316 | 295 | 13 | 0 | 0.4823 |
| H2 absorption | long | 2.0:1.0 | 316 | 290 | 3 | 0 | 0.3310 |
| H2 absorption | short | 1.0:1.0 | 304 | 296 | 7 | 0 | 0.5398 |
| H2 absorption | short | 2.0:1.0 | 304 | 294 | 0 | 0 | 0.3878 |
| H3 aggressive-flow imbalance | long | 1.0:1.0 | 8,017 | 5,706 | 85 | 0 | 0.5092 |
| H3 aggressive-flow imbalance | long | 2.0:1.0 | 8,017 | 4,996 | 24 | 0 | 0.3616 |
| H3 aggressive-flow imbalance | short | 1.0:1.0 | 8,040 | 5,507 | 91 | 0 | 0.5142 |
| H3 aggressive-flow imbalance | short | 2.0:1.0 | 8,040 | 4,787 | 22 | 0 | 0.3727 |

Split bar 184,464, split timestamp 1,783,995,840,000 ms.
**The seal was unlocked exactly ONCE**, for batch `phase2-batch-6cells` against the
pre-registration sha256 above, and is now **SPENT** (`receipts/phase2_seal.json`).
It cannot be unlocked again; `cq_guards.SealedSplit.unlock` raises on a second attempt.

Source: `receipts/cp_phase2_discovery.json`, `receipts/cp_phase2_confirm.json`, `receipts/phase2_seal.json`

---

## 4. The declared MDE, and whether the run was powered to see it

α is the ledger-adjusted **0.05 / 6 = 0.008333**, two-sided, power 0.80, computed at
**effective N**, not raw N. This study is entry 1–6 against this dataset; the ledger
count went 0 → 6.

| hypothesis | side | T:S | effective N | **MDE** | worth_having | verdict |
|---|---|---|---:|---:|---:|---|
| H1 CVD divergence | long | 1.0:1.0 | 3,654 | **0.02876** | 1.06687 | POWERED |
| H1 CVD divergence | long | 2.0:1.0 | 3,317 | **0.02915** | 0.71340 | POWERED |
| H1 CVD divergence | short | 1.0:1.0 | 3,298 | **0.03029** | 1.12562 | POWERED |
| H1 CVD divergence | short | 2.0:1.0 | 3,012 | **0.02992** | 0.74675 | POWERED |
| H2 absorption | long | 1.0:1.0 | 882 | **0.05844** | 0.94387 | POWERED |
| H2 absorption | long | 2.0:1.0 | 872 | **0.05701** | 0.63340 | POWERED |
| H2 absorption | short | 1.0:1.0 | 915 | **0.05745** | 0.90976 | POWERED |
| H2 absorption | short | 2.0:1.0 | 903 | **0.05484** | 0.60396 | POWERED |
| H3 aggressive-flow imbalance | long | 1.0:1.0 | 13,701 | **0.01486** | 1.19011 | POWERED |
| H3 aggressive-flow imbalance | long | 2.0:1.0 | 12,127 | **0.01522** | 0.78636 | POWERED |
| H3 aggressive-flow imbalance | short | 1.0:1.0 | 13,659 | **0.01488** | 1.19629 | POWERED |
| H3 aggressive-flow imbalance | short | 2.0:1.0 | 12,081 | **0.01491** | 0.79149 | POWERED |

**All twelve cells cleared the A5 power gate. The run WAS powered to see the effect it
declared it would look for — in the sense that the machinery resolves an effect at the
MDE, demonstrated in calibration.**

The MDE range is **0.01486 – 0.05844** probability points. The smallest effect this run
could see is between 1.5 and 5.8 percentage points on the hit-first rate.

### The `worth_having` column is the real finding of this section

`worth_having` is the smallest edge over the null that survives cost. Every value in
that column is **between 0.60396 and 1.19629 probability points** — that is, between
60 and 120 percentage points. **A probability cannot move 60 points above a baseline
near 0.35–0.51.** The gate passes on the arithmetic `MDE ≤ worth_having` because
`worth_having` is enormous, and `worth_having` is enormous because cost is enormous.

Median `cost_R` at the pre-registered f = 0.0005 per side runs **1.81187 – 2.39257 R**
across the twelve cells. **The round-trip taker fee alone is roughly 1.8× to 2.4× the
entire 1σ stop distance.** No hit rate — not 100% — makes a rule with a 1σ stop and a
1–2σ target profitable at that fee against that σ.

This is a **geometry** result, not a signal result, and it is independent of whether
any signal exists. Recorded here because the power gate's arithmetic would otherwise
read as a clean pass.

Source: `receipts/cp_phase2_discovery.json` → `power`, `median_cost_R`; `cq_stats.py::mde_binomial`, `power_verdict`, `worth_having`

---

## 5. THE ANSWER — was the family dead everywhere, or only dead on the NSE feed?

**The delta / CVD / absorption family is dead on this feed too, and the NSE feed's
inability to tag aggressors was not what killed it.** Binance BTCUSDT perpetual gives
everything the NSE feed could not: a populated, two-sided aggressor flag on every
trade, 13.5× the arrival rate, 256.5 million tagged trades over 183 days, and effective
sample sizes from 872 to 13,701 independent events per cell after overlap suppression —
enough power to resolve a 1.5-to-5.8-point move in the hit-first rate. Given all of
that, **none of the three hypotheses beat a like-for-like empirical baseline drawn from
the same instrument, in any of the twelve cells: 0 of 12, with |z| topping out at 1.93
against a ledger-adjusted critical value of 2.638.** Six cells did clear that bar
against a synthetic random-walk null, but the drift check showed that null was
mis-specified — the real instrument rose 19.35% over the window, so its unconditional
first-passage rates sit away from the driftless closed form, and the six "edges" were
the gap between the synthetic null and the instrument's own baseline rather than
anything the signal contributed. Separately, and independently of signal, the cost
geometry rules the family out on this instrument at this timeframe regardless of hit
rate: the round-trip taker fee at f = 0.0005 is 1.8–2.4× the whole 1σ stop, so the
edge required to break even (60–120 probability points) is not a quantity that can
exist. **The verdict is a NEGATIVE, not an underpowered non-result** — the study had
the power it pre-registered, and it is reported as a negative on that basis.

---

## 6. Signal results in full

### 6a. Against the synthetic horizon-matched random-walk null (A4 baseline 1)

Six of twelve cells cleared |z| > 2.638:

| hypothesis | side | cell | effective N | edge | z |
|---|---|---|---:|---:|---:|
| H1 CVD divergence | long | 2.0:1.0 | 3,317 | −0.02419 | −2.899 |
| H1 CVD divergence | short | 2.0:1.0 | 3,012 | +0.03130 | +3.658 |
| H2 absorption | short | 2.0:1.0 | 903 | +0.04892 | +3.131 |
| H3 aggressive-flow imbalance | long | 1.0:1.0 | 13,701 | −0.01267 | −2.966 |
| H3 aggressive-flow imbalance | long | 2.0:1.0 | 12,127 | −0.01468 | −3.363 |
| H3 aggressive-flow imbalance | short | 2.0:1.0 | 12,081 | +0.02287 | +5.354 |

All six held the **same sign** on the sealed confirmation set — 6 of 6.

Taken alone, this table reads as a positive. It is not one. See 6c.

Source: `receipts/cp_phase2_signal.json`

### 6b. The drift check that invalidated the synthetic null

| quantity | value |
|---|---:|
| window first close | 67,281.5 USD |
| window last close | 80,301.1 USD |
| window return | **+19.35%** |
| mean 1-minute log return | +6.7129e-07 |
| mean 1σ (60-bar trailing, price units) | 34.1406 USD |
| mean price | 69,912.85 USD |
| **drift over one 240-bar horizon** | **+0.3299σ** |

A driftless-random-walk null is the wrong null for an instrument that drifts a third
of a sigma over the measurement horizon. Every long cell is helped by that drift and
every short cell is hurt by it, before any signal is considered. The sign pattern in
6a — longs negative, shorts positive — is the signature of exactly that.

Source: `receipts/cp_drift.json`

### 6c. Against a powered empirical baseline from the same instrument — the decisive test

The baseline was recomputed from **30,000 randomly drawn real bars** on the same
instrument, same horizon, same bar machinery, same A10 suppression — so it carries the
instrument's own drift, its own discretisation bias, and its own volatility structure.

| cell | empirical baseline rate | effective N |
|---|---:|---:|
| 1.0:1.0 long | 0.5071 | 21,641 |
| 1.0:1.0 short | 0.4929 | 21,641 |
| 2.0:1.0 long | 0.3556 | 18,536 |
| 2.0:1.0 short | 0.3475 | 18,633 |

| hypothesis | side | cell | synth null | **emp baseline** | discovery rate | edge vs emp | z | significant | confirmation edge |
|---|---|---|---:|---:|---:|---:|---:|:--:|---:|
| H1 CVD divergence | long | 1.0:1.0 | 0.5115 | 0.5071 | 0.4957 | −0.01138 | −1.2725 | **no** | −0.00643 |
| H1 CVD divergence | long | 2.0:1.0 | 0.3624 | 0.3556 | 0.3382 | −0.01739 | −1.9265 | **no** | −0.00196 |
| H1 CVD divergence | short | 1.0:1.0 | 0.4885 | 0.4929 | 0.5088 | +0.01595 | +1.7071 | **no** | +0.00132 |
| H1 CVD divergence | short | 2.0:1.0 | 0.3282 | 0.3475 | 0.3595 | +0.01196 | +1.2786 | **no** | +0.00288 |
| H2 absorption | long | 1.0:1.0 | 0.5115 | 0.5071 | 0.5365 | +0.02940 | +1.7117 | **no** | −0.02484 |
| H2 absorption | long | 2.0:1.0 | 0.3624 | 0.3556 | 0.3695 | +0.01393 | +0.8398 | **no** | −0.02458 |
| H2 absorption | short | 1.0:1.0 | 0.4885 | 0.4929 | 0.5034 | +0.01048 | +0.6208 | **no** | +0.04690 |
| H2 absorption | short | 2.0:1.0 | 0.3282 | 0.3475 | 0.3771 | +0.02958 | +1.8229 | **no** | +0.04025 |
| H3 aggressive-flow imbalance | long | 1.0:1.0 | 0.5115 | 0.5071 | 0.4988 | −0.00829 | −1.5195 | **no** | +0.00206 |
| H3 aggressive-flow imbalance | long | 2.0:1.0 | 0.3624 | 0.3556 | 0.3477 | −0.00787 | −1.4079 | **no** | +0.00604 |
| H3 aggressive-flow imbalance | short | 1.0:1.0 | 0.4885 | 0.4929 | 0.4921 | −0.00078 | −0.1419 | **no** | +0.02132 |
| H3 aggressive-flow imbalance | short | 2.0:1.0 | 0.3282 | 0.3475 | 0.3510 | +0.00353 | +0.6349 | **no** | +0.02521 |

**Cells beating the powered empirical baseline: 0 of 12.**
|z| range **0.14 – 1.93**, critical value **2.638**. The largest edge against the
empirical baseline anywhere in the table is **+0.02958** — smaller than the H2 cells'
own MDE of 0.05484, and nowhere near any `worth_having`.

Note the H1 short 2.0:1.0 row specifically: it scored z = +3.658 against the synthetic
null and z = +1.279 against the instrument's own baseline. The entire apparent effect
was the null, not the signal.

Source: `receipts/cp_phase2_empirical.json`

### 6d. Pass bar, cell by cell

The pre-registered pass bar had five requirements, all of which had to hold.
**No cell satisfies requirement 1, 2 or 4. Zero cells pass.**

| requirement | outcome |
|---|---|
| 1. Beats the null by more than `worth_having`, significant at α=0.008333 | **FAIL, 12/12** — 0 of 12 beat the empirical baseline at all |
| 2. Beats the volatility-matched control by the same margin | **NOT MEASURED** — see 8a |
| 3. Same sign on the sealed set with comparable magnitude | held 6/6 for the synthetic-null cells; moot, since requirement 1 fails |
| 4. Expectancy positive in R net of cost at f=0.0005 | **FAIL, 12/12** — expectancy_R negative on every cell; range **−2.4083 to −1.6806** across all twelve (H1: −2.2335 to −2.1256) |
| 5. Effective N sufficient that the MDE gate passed | **PASS, 12/12** |

---

## 7. Cost, funding, and holding time

| quantity | value |
|---|---|
| median `cost_R` at f = 0.0005/side | **1.81187 – 2.39257 R** across 12 cells |
| median hold | **1.0 – 3.0 minutes** |
| share of events crossing **zero** funding stamps | **98.56% – 99.67%** |
| mean funding stamps crossed per event | 0.0033 – 0.0144 |

Because 98.6–99.7% of holds open and close between two 8-hourly funding stamps, funding
is close to irrelevant to these rules — which is a real asymmetry between fast and slow
rules and is reported rather than smoothed. The funding **charge** itself is
**NOT MEASURED**: the rate series was not pulled in this run, so funding is reported as
stamps crossed only, per the pre-registration.

`f` (fee rate) is a **pre-registered parameter, not a measurement**. The Binance
published USDⓈ-M VIP0 schedule is the stated source; it was **NOT verified from a
first-party endpoint in this run**.

`spread` and `slippage` are **NOT MEASURABLE from aggTrades** — the product carries no
order book — and were set to 0. **Every cost figure in this report is therefore a lower
bound**, and the negative verdict is stated on a lower bound, which makes it stronger,
not weaker.

All three rules cross the spread on entry by construction, so the taker leg is the
honest primary and no posting variant is claimed.

Source: `receipts/cp_phase2_discovery.json` → `median_cost_R`, `median_hold_min`, `funding_stamps_zero_share`, `funding_stamps_mean`

---

## 8. NOT MEASURED — the honest list

### 8a. A4 baseline 2, the volatility-matched control — NOT MEASURED

The matched control was **built and RUN, and it FAILED on power**. Matching demanded
both hour-of-day and trailing-volatility quintile, drawn without replacement, under the
same 240-bar A10 spacing rule. Under those constraints the control set collapsed:

| | value |
|---|---|
| control effective N achieved | **9 to 16** across all twelve cells |
| unmatched events | **171 to 17,733** |

A control with effective N of 9 cannot baseline anything. Its z-scores
(−2.33 to +1.48) are noise and **are not used anywhere in this report's verdict**.
Requirement 2 of the pass bar is recorded as **NOT MEASURED**, not as passed and not
as failed. The empirical baseline in 6c is a **different instrument-level baseline**
and does not substitute for the matched control.

Source: `receipts/cp_phase2_confirm.json` → `control_discovery`

### 8b. Other things not measured

- **Funding charge in currency** — rate series not pulled. Stamps crossed only.
- **Spread and slippage** — not present in aggTrades. Cost is a lower bound.
- **The fee schedule** — parameter, not verified from a first-party endpoint.
- **Any instrument other than BTCUSDT perp** — Phase 1 scope was one instrument.
- **Any timeframe other than 1-minute bars with a 240-bar horizon** — as pre-registered.
- **Order-book / depth hypotheses** — not in this product, not in this pre-registration.

---

## 9. Self-check log

Every self-check that found something, and what fixed it. A5 calibration ran on
**synthetic data before any network call** and returned **GREEN 8/8**
(`receipts/calibration.json`).

**1. C4b bar-aware calibration FAILED (first).** z = −8.16 and −18.31 at 2:1 and 3:1,
with 51% of paths censored.
*Diagnosis:* the closed form `stop/(stop+target)` assumes infinite time. Under a
240-bar horizon, censoring is **not random** — it removes precisely the paths that
would have reached the far target.
*Fix:* re-ran calibration at σ = 0.15 where censoring is negligible, and added a
**horizon-matched simulated null** rather than comparing to the asymptotic form.

**2. C4b FAILED again.** Censoring now 0%, but z = +2.91 and +3.47.
*Diagnosis:* **discretisation overshoot.** A bar barrier is only detected after the
bar extreme exceeds it. The fixed overshoot widens a near barrier proportionally more
than a far one, biasing the far-target rate upward. Measured bias: **+0.0098 / +0.0217
/ +0.0237** at 1:1 / 2:1 / 3:1 — it grows with the ratio, as the mechanism predicts.
*Conclusion:* the continuous closed form is **unattainable by any bar machine**.
*Fix:* changed the **criterion**, not any pre-registered threshold — requirement (i) is
now checked against a same-instrument, horizon-and-discretisation-matched null.
Requirements (ii) MDE recovery and (iii) refusal of structureless events were unchanged.
Final C4b: (i) z = +0.77 / +0.22 / +0.08; (ii) MDE 0.02750 recovered at +0.02758;
(iii) structureless z = +0.37. PASS.

**3. C4b requirement (ii) FAILED — my bug, not the data's.** Injected lift measured
+0.00783 against an MDE of 0.02750.
*Diagnosis:* the bisection search for the injection strength had `hi = 0.02`, a ceiling
below the MDE it was trying to reach. It could never have succeeded.
*Fix:* widened the bracket to 0.60. Recovery then landed at +0.02758.

**4. `horizon_matched_null` raised IndexError.** Series length was
`n_sims + HORIZON_BARS + 5` while the sampling loop started at index 500.
*Fix:* `m = 500 + n_sims + HORIZON_BARS + 5`.

**5. Dead code in `first_passage`.** An unused `idn` assignment. Removed.

**6. A4 baseline 2 power failure — found by self-check, reported not papered over.**
Control effective N came back at 9–16. Recorded as **NOT MEASURED** (section 8a)
rather than being quietly relaxed to `n_per_event > 1`, with replacement, or without
the spacing rule — any of which would have manufactured a baseline out of a handful of
repeatedly-sampled quiet windows.

**7. Synthetic-null mis-specification — the one that changed the verdict.** Six cells
were significant against the synthetic null and all six held sign on the sealed set.
The drift check (6b) showed the instrument rose 19.35% over the window, +0.3299σ per
horizon, and that the unconditional real-data rates (long 0.3550 / short 0.3594 at 2:1)
sit far from the synthetic short null (0.3282).
*Fix:* computed a **powered empirical baseline** from 30,000 random real bars on the
same instrument. Against it, **0 of 12** cells are significant. Without this check the
report would have read as a positive on six cells.

**8. Report figures re-derived from disk by an independent code path.** After
REPORT.md was drafted, every range and count in it was recomputed straight from the
receipt JSON by a separate script rather than read back from the draft. **Two
transcription errors were found and fixed:** the expectancy_R range was written as
"−2.1255 to −2.1423 on H1" when the true H1 range is −2.2335 to −2.1256 and the
all-cell range is −2.4083 to −1.6806; and the mean funding-stamps figure was written
as a 0.0139 maximum when the true maximum is 0.0144. Neither changed any verdict —
expectancy is negative on all twelve cells either way — but both are recorded because
a figure that was not checked is a figure that was assumed.

---

## 10. Operating boundary — compliance

| boundary | declared | actual |
|---|---|---|
| hosts | `data.binance.vision`, `api.binance.com` only | 2 hosts, no others contacted |
| authentication | none, no API key, no signed endpoint | none used; no signing code exists in the programme |
| order placement | forbidden on every host | no order path exists; refusal proven in C1 |
| **disk ceiling** | **20.00 GiB** | **2.9131 GiB used, 17.4339 GiB unused** |
| free-space floor | never below 10% | 28.34% free at finish |
| request cap | 4,000 | **183 used, 3,817 remaining** |
| non-200 responses | — | **0** |
| days requested / retrieved | 183 | **183 / 183, 0 missing** |
| data deleted | none permitted | **none deleted** |

C1 refused 7 hostile URLs and allowed 2 legitimate ones. C3 proved both the disk
ceiling and the request cap raise rather than proceed. C2 proved the sealed-split guard
fires on discovery-stage access and refuses a second unlock.

Bar coverage: **263,520 bars against 263,520 expected on a continuous minute grid —
100.000%**, no gaps.

Source: `receipts/cp_pull.json`, `receipts/request_counter.json`, `receipts/calibration.json`, `receipts/cp_bars.json`
Commands: `python3 -c "import cq_guards as G; print(G.stats())"`; `df -k /System/Volumes/Data`

---

## 11. Ledger

| | |
|---|---|
| cumulative hypothesis count entering | 0 |
| cells contributed by this study | 6 (3 hypotheses × 2 (target, stop) pairs) |
| cumulative after | **6** |
| adjustment | Bonferroni at 6, α = 0.05/6 = **0.008333**, two-sided |
| z critical | **2.6383** |
| seal | cut at bar 184,464 / ts 1,783,995,840,000; **unlocked once; SPENT** |

---

## 12. Artefacts

| file | what it is |
|---|---|
| `BLUEPRINT_v3.md` | the spec in force, commit `1e7ac830` |
| `PREREG_PHASE2.md` | pre-registration, commit `b37fdb49` |
| `cq_guards.py` | network / disk / request / seal boundaries in code |
| `cq_engine.py` | A6 first passage, A10 independence, A8 funding |
| `cq_stats.py` | A4 nulls, A5 MDE and power gate |
| `cq_calibrate.py` | A5 calibration suite C1–C8 |
| `cq_pull.py` | the only downloader |
| `cq_bars.py` | trades → 1-minute bars |
| `cq_phase2.py` | discovery |
| `cq_confirm.py` | control + sealed confirmation |
| `receipts/*.json` | every figure in this report |
| `raw/` | 183 daily zips + `bars_1m.parquet`, gitignored, **retained, not deleted** |
