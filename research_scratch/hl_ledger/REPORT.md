# HL-LEDGER TRAIN v2 — REPORT

**Run date:** 2026-09-08 (IST). **Worktree:** `trading-bridge-hl-ledger`, branch `research/hl-ledger`.
**Amendment 1 applied** — permitted surface widened to any host under the `hyperliquid.xyz` domain suffix, read-only, unauthenticated. `/exchange` remained forbidden on every host and is refused in code.

---

## 1. Checkpoint ledger

| CP | Status | One line |
|---|---|---|
| CP0 | **GREEN** | Worktree verified, 0 sessions on it (2 on primary — the documented warning), disk 28.98%, python3 3.14.3 + requests 2.31.0, `meta` 200 / 233 universe entries |
| CP1 | **GREEN** | `crossed` **PRESENT** (decisive gate passes); all 14 required fill keys present; funding retrievable; leaderboard resolved at 45,086 rows |
| CP2 | **GREEN** | 94-wallet union of top-30-by-pnl across 4 windows; sha256 sealed; 60-second churn measured |
| CP3 | **GREEN** | `PREREG.md` committed **before** any fill was pulled — commit `d62a46cc` |
| CP4 | **GREEN** | 94/94 wallets pulled; re-request byte-identical; **re-run once after the self-check found inverted pagination** |
| CP5 | **GREEN** | Classifier recovered **4/4** synthetics, twice (before and after a performance rewrite) |
| CP6 | **GREEN** | 94 wallets classified under the sealed rules; **re-run once** after a false zero-fill was corrected |
| CP7 | **GREEN** | This report |

---

## 2. Self-check log

- **CP0 — found:** naive `ps` counting reads 4 claude pids as 4 sessions. **Fixed by** collapsing wrapper→worker via `ppid`, giving 2 roots; 0 hold this worktree as cwd. Warning recorded: pid 28860 alive throughout.
- **CP1 — found:** the request counter was **per-process** and under-reported (a probe printed "1" when the true total was 20). **Fixed by** persisting it to `receipts/request_counter.json`, loading at client startup, backfilling 20, and proving cross-process visibility with four separate interpreters (A write → B read → C increment → D read). Also found the **#1 wallet by day pnl has `vlm = 0.0` and zero fills** — recorded as a finding, probe address moved to the top wallet with non-zero volume.
- **CP2 — nothing found.** Cohort re-derived from the cached pull and matched.
- **CP3 — nothing found.** `PREREG.md` verified to contain the question verbatim, all 8 metrics, the 4 sealed rules in order with all 7 threshold numbers, all 6 mandated limitations plus 3 discovered in CP1, and 3e.
- **CP4 — found, and this one mattered.** 39 of 50 active wallets sat at exactly 2000 fills with `truncated=False`; one had 2000 fills spanning 0.44 h while its earliest fill was 16.5 days before the window end. **Diagnosed empirically** (not assumed): `userFillsByTime` returns fills **ascending from `startTime`**, oldest-first — my paginator walked backwards. A forward probe returned 2000 *more* fills. **Fixed by** inverting the walk to `startTime = newest_seen + 1`, raising the page budget 12 → 20, and **re-running CP4 in full**. The superseded receipt is kept at `receipts/cp4_SUPERSEDED_backward_pagination.json`. After the fix the same wallets returned 9k–28k fills and exhausted naturally.
- **CP4 — found (second):** 57 HTTP 429s occurred and **one request exhausted its retries**, recording wallet `0xb37f083b…` as `fills = 0`. That zero was an artefact, not a fact. **Fixed by** re-pulling that wallet: it actually has **9,851 fills**. CP6 was then re-run. Without this check it would have been counted among the zero-fill wallets and mislabelled UNCLASSIFIED.
- **CP4 determinism — nothing found.** A random wallet (`0x7e4e766d…`, 27,704 cached fills) was re-requested on an identical slice: **2000 records compared, byte-identical**.
- **CP5 — nothing found.** 4/4 both before and after the `net_exposure` bisect rewrite (the rewrite was for speed; the regression re-run proves it did not move a label).
- **CP6 — found:** the first pass ran on the pre-correction data. **Fixed by** re-running after the `0xb37f083b…` re-pull. Net effect: DIRECTIONAL 4 → 5, NEUTRAL/CARRY 29 → 28, zero-fill 45 → 44.

---

## 3. The numbers

**Cohort:** 94 wallets = union of top 30 by pnl in each of day / week / month / allTime. Total gross notional observed: **$4,417,657,263**.

### Labels — count and notional share

| Label | Count | % of cohort | Gross notional | % of notional |
|---|---|---|---|---|
| MARKET-MAKER | 1 | 1.1% | $59,859,264 | 1.4% |
| NEUTRAL/CARRY | 28 | 29.8% | $666,463,788 | 15.1% |
| DIRECTIONAL | 5 | 5.3% | $868,829,128 | 19.7% |
| **UNCLASSIFIED** | **60** | **63.8%** | **$2,822,505,082** | **63.9%** |

**44 of 94 wallets (46.8%) returned zero perp fills in 30 days** and are UNCLASSIFIED by construction.

Among only the **34 wallets that could be classified**: NEUTRAL/CARRY 28 (82.4% by count, 41.8% of classified notional), DIRECTIONAL 5 (14.7% by count, **54.5%** of classified notional), MARKET-MAKER 1 (2.9%, 3.8%).

### Persistence (raw overlap counts, each out of 30)

| | overlap |
|---|---|
| day ∩ week | 5 |
| day ∩ month | 2 |
| day ∩ allTime | 5 |
| month ∩ allTime | 11 |

**60-second churn re-check:** 0 of 30 changed, in every one of the four windows.

### Metric distributions across the cohort

| metric | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| `maker_share_ntl` | 50 | 0.0000 | 0.0680 | 0.3773 | 0.8339 | 1.0000 |
| `fills_per_active_day` | 50 | 4.00 | 508.45 | 1367.44 | 3225.25 | 9809.50 |
| `median_flat_to_flat_holding_seconds` | 28 | 0.00 | 74.05 | 5311.06 | 60106.28 | 857875.43 |
| `mean_abs_net_exposure_over_gross` | 49 | 0.2656 | 0.6911 | 0.9617 | 1.0000 | 1.0000 |
| `funding_share_of_pnl` | 55 | 0.0000 | 0.0067 | 0.5240 | 0.9546 | 1.0000 |
| `n_distinct_coins` | 94 | 0 | 0 | 1 | 10 | 116 |
| `fee_paid_over_gross_notional` | 50 | −0.0000 | 0.0001 | 0.0002 | 0.0003 | 0.0325 |
| `best_episode_share_of_profit` | 47 | 0.0007 | 0.0097 | 0.0219 | 0.0818 | 1.0000 |
| `never_closed_fraction` | 50 | 0.0000 | 0.5000 | 0.8485 | 1.0000 | 1.0000 |

**Never-closed episodes: cohort mean 0.7377** — on average roughly three-quarters of a wallet's position episodes never returned to flat inside the 30-day window. Only 28 of 94 wallets produced a median holding time at all. **1 wallet** hit the page budget and is truncated; its fill-derived metrics are lower bounds.

---

## 4. NOT MEASURED

- **`funding_share_of_pnl` for 39 of 94 wallets** — no funding rows and/or no positive `closedPnl` in the window.
- **`median_flat_to_flat_holding_seconds` for 66 of 94 wallets** — 44 have no fills, and 22 more never returned to flat, so no episode closed.
- **`mean_abs_net_exposure_over_gross` for 45 wallets**; **`maker_share_ntl` / `fills_per_active_day` / `fee_paid_over_gross_notional` for 44**; **`best_episode_share_of_profit` for 47** — all for want of fills.
- **Why the 44 zero-fill wallets have leaderboard PnL** — not measured. They may be vaults, spot-only, or HLP-style; this run did not probe that.
- **The complete `dir` vocabulary** — CP1 observed only `Open Short`; the bulk pull was not re-scanned to enumerate the full set.
- **Cross-venue positions** — structurally invisible (PREREG limitation 1).
- **Whether the leaderboard's own ranking matches pnl-descending** — `leaderboardRows` is *not* pre-sorted; I imposed pnl-descending as the stated ranking criterion.
- **Anything beyond 30 days**, and anything past the 20-page budget for the 1 truncated wallet.
- **Sharpe / PF / expectancy / win rate** — deliberately out of scope, not computed.

---

## 5. THE DECISION

**Cannot tell.** Nearly two-thirds of these top-ranked wallets — 60 of 94, and 63.9% of all the notional we observed — do not fit any of the four sealed definitions, so the honest answer is that this data does not settle what the top of the Hyperliquid leaderboard is doing. Two things drive that. First, **47% of the cohort placed no perpetual-futures fills at all in 30 days**, so for nearly half these wallets there is simply no trading behaviour in this dataset to classify. Second, among the wallets that do trade, **about three-quarters of their position episodes never closed inside the window**, so the holding-time test that separates fast market-making from slow directional betting could not be evaluated for most of them. Of the 34 wallets that could be classified, carry-like books dominate by headcount (28 of 34) while a handful of directional wallets carry the most volume (54.5% of classified notional) — but that is a minority of a minority and should not be read as the answer. **To actually tell**, you would need three things: a longer window so slow books close at least one episode (90 days would cover most of the observed holding times), a way to see what the zero-fill wallets are actually doing (spot, vaults, or HLP — a different endpoint, not `userFillsByTime`), and cross-venue visibility, without which any hedged book looks directional to us.

---

## 6. The forward test that is now free

`COHORT.json` sha256 **`6d24d6a20357c39dc621c00062ca6b1ca09048db9f69267ff6100dd48ff401c9`**

These wallets are sealed as of **2026-09-08**; re-running CP4 through CP6 on this same cohort after 30 days is an out-of-sample test requiring no new design.

The persistence numbers already hint at what that will show: only **2 of the top-30 daily** wallets are also top-30 monthly, and only **5** are top-30 all-time.

---

## 7. Cost line

| Item | Value |
|---|---|
| API requests used | **1,052** of the declared cap **2,000** |
| Non-200 responses | 59 — 1 × HTTP 422 (a probe), 57 × HTTP 429, 1 × 429-exhausted (re-pulled and corrected) |
| Hosts called | `api.hyperliquid.xyz`, `stats-data.hyperliquid.xyz` — both under the permitted suffix |
| `/exchange`, signing, credentials | **none** — refused in code (`ForbiddenPath`), and the host guard also refuses suffix-spoofing such as `evil-hyperliquid.xyz.attacker.com` |
| Wall-clock | ~35 minutes |
| Raw cache on disk | **246.3 MiB** (not committed; `raw/` is gitignored) |
| Receipts + scripts | ~225 KiB (committed) |
| Free disk at start | 66.16 GiB (28.98%) |
| Free disk at end | 65.88 GiB (28.86%) |
| Files deleted | **none** |
| Primary checkout | **unmodified** — verified `git status --porcelain` = 0, branch unchanged |

---

## 8. Honest caveats on the headline number

1. **The UNCLASSIFIED bucket is doing the work here**, and it is mostly an artefact of data availability rather than of wallet behaviour: 44 zero-fill wallets plus 22 whose positions never closed.
2. **The 30-day window is shorter than these books trade.** Median holding time among wallets that *did* close an episode is 5,311 s, but p75 is 60,106 s and the max is 857,875 s (≈10 days) — PREREG limitation 6 anticipated exactly this, and the 0.74 never-closed fraction is the measurement of it.
3. **Thresholds were not moved.** The classifier ran once, at the values sealed in commit `d62a46cc`. The full distributions in §3 are published precisely so a future run can recalibrate honestly against real data instead of guesses.
4. **Survivorship stands** (PREREG limitation 2): this says what today's winners are doing, never that any of it makes money.
