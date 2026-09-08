# HL-LEDGER TRAIN v2 — PARTIAL REPORT

**Run date:** 2026-09-08 (IST)
**Worktree:** `/Users/jayeshparekh/projects/trading-bridge-hl-ledger`, branch `research/hl-ledger`
**Outcome: CP1 RED at CP1.5.** CP0 passed. The study stopped at the leaderboard-source gate.

---

## 1. Checkpoint ledger

| CP | Status | One line |
|---|---|---|
| CP0 | **GREEN** | Worktree verified, concurrency counted (warning recorded), disk 28.98%, python3 3.14.3 + requests 2.31.0, `meta` returned 200 / 233 universe entries |
| CP1 | **RED** | CP1.5: no first-party leaderboard exists on `api.hyperliquid.xyz/info`; reaching one would require a host that HARD SAFETY RULE 1 forbids |
| CP2 | PENDING | No cohort assembled, no `COHORT.json`, no hash |
| CP3 | PENDING | No `PREREG.md` written or committed |
| CP4 | PENDING | No fills pulled |
| CP5 | PENDING | No synthetic validation run |
| CP6 | PENDING | No wallet classified |
| CP7 | PENDING | This partial report only |

---

## 2. Self-check log

- **CP0.1 — nothing found.** Re-ran `rev-parse`/`status` from a fresh process; toplevel, branch and clean status identical both times.
- **CP0.2 — found:** a naive `ps` count returns 4 claude pids and would read as 4 sessions. **Fixed by** resolving `ppid` and collapsing wrapper→worker pairs, giving **2 distinct session roots**. Both have the **primary checkout** as cwd; **0 sessions hold this worktree as cwd**, so CP0.2(a) is not RED. CP0.2(b) warning recorded: **pid 28860** (resumed session `8d181a7d`) alive, `ps` state `S`, elapsed 24:43 at time of check.
- **CP0.3 — nothing found.** Disk re-read within 0.1 pp between the two reads.
- **CP0.4 — nothing found.** No venv was created; system `python3` already had `requests`.
- **CP0.5 — nothing found.** `meta` returned 200 on both the gate call and the self-check re-call.
- **CP1 — found:** the request counter in `hl_client.py` is **per-process**, so each `python3` invocation restarted it at zero and the final probe printed `requests used: 1` when the true running total was **20**. **Fixed by** counting cumulatively by hand for this receipt (2 + 4 + 13 + 1 = 20) and recording that **any resumed run must persist the counter to disk before CP4's bulk pull**, otherwise the declared cap cannot be enforced across processes. This was caught before any bulk pull, so no number in this report is affected.

---

## 3. The numbers

Nothing about Hyperliquid wallets was measured. What *was* measured:

| Quantity | Value |
|---|---|
| Worktree toplevel | `/Users/jayeshparekh/projects/trading-bridge-hl-ledger` |
| Branch | `research/hl-ledger`, `git status --porcelain` = 0 lines |
| Sessions with this worktree as cwd | **0** (gate: RED only if >1) |
| Sessions on the primary checkout | **2** (warning; pid 28860 alive) |
| Free disk | 69,375,216 KiB = **66.16 GiB** of 228.27 GiB = **28.98%** |
| Python / HTTP lib | Python 3.14.3 / requests 2.31.0 |
| `{"type":"meta"}` | HTTP **200**, **17,560 bytes**, **233** universe entries |
| Leaderboard type names tried on `/info` | **14**, all HTTP **422** |
| API requests used | **20** of a declared cap of **2000** |
| Hosts called | `api.hyperliquid.xyz` only |
| Paths called | `/info` only |

---

## 4. The RED, stated precisely

`/info` exposes **no leaderboard method**. Fourteen candidate type names — `leaderboard`, `leaderBoard`, `userLeaderboard`, `spotLeaderboard`, `leaderboardV2`, `traderLeaderboard`, `perpLeaderboard`, `topTraders`, `rankings`, `userRanking`, `leaders`, `vaultLeaderboard`, `userRole`, `subAccounts` — all returned **HTTP 422, "Failed to deserialize the JSON body into the target type"**, meaning the value is not in the endpoint's type enum.

The endpoint itself is healthy: `meta` → 200 with 233 entries, `vaultSummaries` → 200 (empty list), `portfolio` → 200 (an all-zero empty portfolio containing **0** `0x…` addresses, so not a wallet source either).

### The instruction conflict I would not resolve on my own

- **HARD SAFETY RULE 1:** *"The only network host you may call is `https://api.hyperliquid.xyz`, only the `/info` path."*
- **CP1.5 step 2:** *"Any leaderboard path you can find by reading the official Hyperliquid documentation, and only on a `hyperliquid.xyz` domain."*

Hyperliquid's first-party leaderboard is **not** served from `api.hyperliquid.xyz/info`. Reaching it requires a *different* `hyperliquid.xyz` host — which CP1.5 step 2 contemplates but rule 1 forbids, under a heading that says violating it is an immediate STOP.

**I stopped rather than choosing.** I did not call any host other than `api.hyperliquid.xyz`, did not call any path other than `/info`, and did not substitute a third-party aggregator (which CP1.5 forbids outright, and which would silently change what the study measures).

**This is a one-line decision for you** — see §8.

---

## 5. NOT MEASURED

- **CP1.1 probe address — NOT SELECTED.** The honest first-party source for a real wallet address was the leaderboard. The task forbids inventing an address, and no reachable `/info` method returns one.
- **CP1.2 fills schema — NOT MEASURED.** Including, critically, whether **`crossed` is PRESENT** — the field the whole maker-vs-taker question depends on. That decisive gate was never reached.
- Also unmeasured from CP1.2: `dir` / `side` / `sz` / `px` / `time` / `closedPnl` / `fee` / `feeToken` / `coin` / `startPosition` / `oid` / `tid` / `hash`; whether numerics are returned as **strings or numbers**; whether `startPosition` is **signed**; the distinct values of `dir`.
- **CP1.3 funding schema — NOT MEASURED** (`userFunding` vs `nonUserFundingUpdates`, field names, sign convention).
- **CP1.4 position schema — NOT MEASURED** (`assetPositions`, `marginSummary.accountValue`).
- **CP2** — cohort, per-window ranks, `COHORT.json`, its sha256, 60-second churn.
- **CP4** — fills history depth, per-wallet fill counts, dedup counts, re-request determinism.
- **CP5** — all four synthetic recoveries.
- **CP6** — all eight metrics for every wallet; label counts; notional shares; persistence overlaps; metric distributions; never-closed-episode fractions.

No number in this report is estimated, and no API field is inferred from another.

---

## 6. THE DECISION

**Cannot tell.** This run cannot say whether Hyperliquid's top wallets are mostly directional, mostly neutral/carry, or mostly market-making, because it never obtained the list of top wallets. Twenty API calls were made, all to `api.hyperliquid.xyz/info`, and they establish only that the endpoint is healthy and that it does not serve a leaderboard.

**What would be needed to tell:** a first-party list of top wallets. Concretely, one of — (a) authorisation to call Hyperliquid's own stats host on the `hyperliquid.xyz` domain, which is what CP1.5 step 2 anticipated; or (b) a leaderboard `/info` type name I did not guess, if one exists; or (c) a wallet list you supply directly, in which case CP2's "top 30 per window" framing would change to "the wallets Jayesh named" and the study would answer a slightly different question, which must then be restated in the pre-registration. After that, the run still faces its real decisive gate at CP1.2: **if `crossed` is ABSENT from `userFillsByTime`, the maker-vs-taker question cannot be answered from fills at all** and the train stops there instead.

---

## 7. The forward test that is now free

**None.** No cohort was sealed, so there is no `COHORT.json` and no sha256. The free 30-day out-of-sample re-measurement is forfeited for this run and is recovered by re-running once the leaderboard source is resolved.

---

## 8. The one decision needed to resume

Pick one and say so; nothing here needs undoing first:

1. **Authorise the Hyperliquid stats host** (a read-only, unauthenticated GET on a `hyperliquid.xyz` domain) — this is what CP1.5 step 2 already contemplated, and it makes rule 1 and CP1.5 consistent; or
2. **Supply the wallet list yourself**, accepting that the question becomes "what are *these* wallets doing" rather than "what are the top-ranked wallets doing"; or
3. **Accept the RED** and close the study here.

---

## 9. Cost line

| Item | Value |
|---|---|
| API requests used | **20** of declared cap **2000** |
| Hosts / paths touched | `api.hyperliquid.xyz` only; `/info` only |
| `/exchange`, signing, credentials | **none — no such code path exists in `hl_client.py`** |
| Wall-clock | ~4 minutes |
| Bytes on disk (receipts + scripts) | ~30 KB; **raw fill cache not created** |
| Free disk at start | 66.16 GiB (28.98%) |
| Free disk at end | 66.16 GiB (28.98%) — unchanged, nothing bulk-pulled |
| Files deleted | **none** |
| Primary checkout modified | **no** — verified `git status --porcelain` = 0 and branch unchanged |
