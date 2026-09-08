# PREREG — HL-LEDGER TRAIN v2

**Sealed before any fill data was downloaded.** Cohort file `COHORT.json`
sha256 `6d24d6a20357c39dc621c00062ca6b1ca09048db9f69267ff6100dd48ff401c9`,
pulled 2026-09-08T00:43:50.535597+00:00 UTC from
`https://stats-data.hyperliquid.xyz/Mainnet/leaderboard` (45,086 rows),
94 wallets = union of the top 30 by pnl in each of day / week / month / allTime.

---

## 3a. The question

*"Among Hyperliquid's currently top-ranked wallets, what fraction are DIRECTIONAL, NEUTRAL/CARRY, MARKET-MAKER, or UNCLASSIFIED, under the fixed rules below?"*

---

## 3b. The metrics — per wallet, from fills unless stated

1. `maker_share_ntl` = notional-weighted fraction of fills with `crossed == false`, where notional = `abs(sz) * px`.
2. `fills_per_active_day` = total fills / number of distinct UTC days on which at least one fill occurred.
3. `median_flat_to_flat_holding_seconds` — reconstruct signed position per coin from `startPosition` plus each fill. A **position episode** runs from a flat state to the next flat state. Report the **fraction of episodes that never closed** inside the window; **do not drop them silently**.
4. `mean_abs_net_exposure_over_gross` — at hourly sample points across the window: `abs(sum over coins of signed notional) / sum over coins of abs(notional)`. A book long one coin and short another scores low. Report the number of sample points used.
5. `funding_share_of_pnl` = funding received / (funding received + sum of positive `closedPnl`). CP1.3 **confirmed funding IS retrievable** via `userFunding`, and confirmed that **positive `delta.usdc` means funding RECEIVED** (verified against a wallet holding a short under a positive funding rate). So this metric **will be computed**, not `NOT MEASURED`.
6. `n_distinct_coins`.
7. `fee_paid_over_gross_notional`.
8. `closedPnl` distribution: count, median, mean, and **the share of total profit contributed by the single best episode**.

All of `sz`, `px`, `closedPnl`, `fee`, `startPosition` are returned as **STRINGS** (CP1.2) and are parsed explicitly with `float()` before any arithmetic.

---

## 3c. Classification rules — FIXED NOW, NEVER MOVED AFTER RESULTS

Evaluate in this order; **first match wins**:

- **MARKET-MAKER** if `maker_share_ntl >= 0.80` AND `fills_per_active_day >= 200` AND `median_flat_to_flat_holding_seconds <= 600`
- **NEUTRAL / CARRY** if not MM, AND (`funding_share_of_pnl >= 0.50` OR `mean_abs_net_exposure_over_gross <= 0.20`)
- **DIRECTIONAL** if not MM and not NEUTRAL, AND `maker_share_ntl <= 0.50` AND `median_flat_to_flat_holding_seconds >= 3600`
- **UNCLASSIFIED** otherwise

**Binding rule:** the numbers **0.80, 200, 600, 0.50, 0.20, 0.50, 3600** are sealed at this commit. If the results look ugly, **the results are the finding**. The full raw distribution of every metric will ALSO be reported so a future run can recalibrate honestly — but the classifier will **not** be re-run with different thresholds in this run, and **no new rule will be added**.

---

## 3d. The limitations

1. **Cross-venue neutrality is invisible here.** A wallet short perp on Hyperliquid as the hedge leg of a spot position held on another exchange will look DIRECTIONAL-SHORT to us. This is the largest known blind spot and it biases the count **toward DIRECTIONAL**.
2. **The leaderboard is survivors only.** Wallets that ran the same strategy and blew up are not in the cohort. This study therefore **cannot** say "this strategy makes money" — only "this is what today's top wallets are doing".
3. **One entity may run many wallets;** sub-accounts and vaults are separate addresses. We measure wallets, not people.
4. **Historical depth of the fills endpoint is unknown until CP4 measures it.** The observed span will be stated; nothing is assumed.
5. **Account value is a point-in-time snapshot,** so leaderboard ROI is not verified by us.
6. **A 30-day window may be shorter than a carry book's holding period,** which would push genuine carry wallets into UNCLASSIFIED via the never-closed-episode path. The never-closed fraction is reported so this is visible.

### Additional limitations discovered in CP1, recorded here before results

7. **`userFillsByTime` caps at 2000 rows per response** and `userFunding` at 500. CP4 must paginate backwards and dedup by `tid`. Any wallet whose 30-day activity exceeds what the pagination budget can retrieve will have a **truncated** history, and its `fills_per_active_day` and `n_distinct_coins` will be **lower bounds**. Truncation will be reported per wallet.
8. **The `dir` vocabulary is not fully known.** CP1 observed only `Open Short` in a single 0.4h page. The complete set will be recorded from the CP4 pull.
9. **A top-ranked wallet may have zero fills.** The #1 wallet by day pnl (`0xe6111266…`) reports `vlm = 0.0` and returned zero fills over 24h/7d/30d. Such wallets are kept in the cohort and reported, not dropped.

---

## 3e. What would make this run WRONG

**If CP5's synthetic recovery fails, every classification in CP6 is void.** The classifier must return MARKET-MAKER, NEUTRAL/CARRY, DIRECTIONAL and UNCLASSIFIED on the four labelled synthetics — 4/4. Anything less is RED and the run stops there. Thresholds will not be tuned to pass; only code defects will be fixed.
