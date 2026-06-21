# Showcase Backend — Design Proposal (REVIEW ONLY, do NOT ship)

> Status: **PROPOSAL for Jayesh to review.** No code written. Nothing here is
> implemented. This documents *what* the read-only showcase API could look like,
> the data contract, and the honest-labelling rules — and flags every open
> question. Implementation is a separate, explicitly-approved task.

## 0. Non-negotiable principles (carried from the honesty doctrine)

1. **Read-only.** The showcase API only ever READS. It never writes, never
   mutates a strategy, never flips a flag. No endpoint touches the live execution
   path (strategy_executor / direct_exit / webhook / kill_switch / brokers).
2. **No compounded/cumulative INR or % anywhere.** The data contract has **no
   field** that can carry a compounded total. Size-independent per-trade metrics
   only. This is enforced structurally (the field simply does not exist), not by
   convention.
3. **Backtest ≠ live ≠ paper.** Every number is stamped with an explicit
   `track_type` and provenance. A backtest is labelled in-sample and is never
   presented as a track record. Paper is never presented as real-money.
4. **No silent blending.** Backtest and live figures are NEVER summed, averaged,
   or merged into one headline. They are distinct objects with distinct labels.

## 1. The four states (honest-labelling spec)

`track_type` is a closed enum. Every metrics object carries exactly one, plus a
human-facing `label` and `disclaimer` the frontend must render verbatim.

| `track_type` | Meaning | Data source | Mandatory label | Mandatory disclaimer |
|---|---|---|---|---|
| `BACKTEST_IN_SAMPLE` | Historical signals replayed on the strategy's own history | isolated SQLite `backtest_trades` | "Backtest (in-sample)" | "In-sample backtest, not a guarantee of future results. Charges estimated, slippage excluded." |
| `LIVE_REAL` | Real-money executions, broker-confirmed fills | live app Postgres (read-only) | "Live (real money)" | "Live real-money results. Past performance ≠ future results." |
| `PAPER` | Simulated execution, no real money | live app Postgres paper rows / backtest store | "Paper (simulated)" | "Paper/simulated — no real money was traded." |
| `FORWARD_TEST` | Out-of-sample signals tracked live-forward, paper or tiny size | (future) dedicated forward-test store | "Forward test (out-of-sample)" | "Forward test — out-of-sample, limited sample, not a track record." |

Rules:
- A strategy MAY expose multiple states (e.g. BSE = `BACKTEST_IN_SAMPLE` **and**
  `LIVE_REAL`), returned as **separate objects** in a list — never merged.
- `LIVE_REAL` MUST carry `confirmed_fills_count`. **If it is 0 or thin, the state
  is still labelled honestly** ("Live — 0 broker-confirmed fills to date") rather
  than hidden or padded with backtest numbers. (Per the M1 audit, BSE had ~0
  confirmed-filled live Dhan executions — the contract must not let a thin live
  record borrow backtest credibility.)
- `PAPER` and `BACKTEST_IN_SAMPLE` may never set any field implying real money.
- ANGELONE today = `BACKTEST_IN_SAMPLE` + `PAPER` only. **No `LIVE_REAL`.**

## 2. Proposed read-only endpoints

All under `/api/showcase/*`, all `GET`, all read-only. (Auth: see open Q's.)

| Endpoint | Returns |
|---|---|
| `GET /api/showcase/strategies` | List of strategies with the track_types each exposes (no metrics) — a lightweight index. |
| `GET /api/showcase/strategies/{key}/backtest` | `BACKTEST_IN_SAMPLE` metrics object (from isolated SQLite). |
| `GET /api/showcase/strategies/{key}/live` | `LIVE_REAL` (or `PAPER`) tracking object (from live Postgres, read-only). Honest even when thin/empty. |

`{key}` = a stable showcase slug (`bse` / `cdsl` / `angelone`) — **not** the live
strategy UUID (decouples the public surface from internal ids; see open Q).

## 3. Response data-contract (proposed shape)

### 3a. Backtest metrics object (`BACKTEST_IN_SAMPLE`)
```jsonc
{
  "strategy_key": "angelone",
  "display_name": "NSE:ANGELONE Futures",
  "track_type": "BACKTEST_IN_SAMPLE",
  "label": "Backtest (in-sample)",
  "disclaimer": "In-sample backtest, not a guarantee ... slippage excluded.",
  "strategy_version": "v4.8.1",
  "source": "tv_trade_list",
  "in_sample_range": { "from": "2020-10", "to": "2026-06" },
  "metrics": {
    "closed_trades": 942,
    "open_excluded": 0,
    "win_rate_pct": 73.14,
    "avg_pct_per_trade_gross": 1.415,
    "avg_pct_per_trade_net": 1.386,   // after ESTIMATED NFO costs
    "median_pct_per_trade": 1.520,
    "best_trade_pct": 22.59,
    "worst_trade_pct": -10.91,
    "profit_factor": 3.82,            // Σwin% / |Σloss%|
    "longest_losing_streak": 7,
    "max_drawdown_pct": 9.89          // non-compounded, constant-notional
  },
  "cost_model": {
    "estimated": true,
    "segment": "NFO",
    "fixed_notional_inr": 1500000,
    "note": "Charges only — slippage/impact excluded. Published-rate model."
  },
  "drawdown_basis": "non_compounded_constant_notional",
  "excluded_artifacts": ["compounded_cumulative", "position_qty", "position_value", "inr_pnl"]
}
```
**Deliberately ABSENT:** any `cumulative_*`, any `total_return`, any INR P&L, any
position size. These fields do not exist in the contract.

### 3b. Live-tracking object (`LIVE_REAL` / `PAPER`)
```jsonc
{
  "strategy_key": "bse",
  "display_name": "NSE:BSE Futures",
  "track_type": "LIVE_REAL",
  "label": "Live (real money)",
  "disclaimer": "Live real-money results. Past performance ≠ future results.",
  "since": "2026-05-..",                 // first confirmed live action
  "confirmed_fills_count": 0,            // HONEST: shown even when 0/thin
  "closed_positions": 7,
  "open_positions": 0,
  "metrics": {                          // size-independent, per-trade ONLY
    "win_rate_pct": null,               // null until enough confirmed fills
    "avg_pct_per_trade_net": null,
    "max_drawdown_pct": null
  },
  "data_completeness": "thin",          // enum: empty | thin | sufficient
  "caveat": "0 broker-confirmed fills to date; metrics withheld until sufficient."
}
```
Open: live per-trade % needs a reliable realized-P&L source. The reconciler
computes NET per-trade from real fills but runs **log-only** (write flag OFF), so
`strategy_positions.final_pnl` is largely NULL. **Live metrics may be unavailable
by design today** — the contract must represent "not enough data" honestly rather
than fabricate. (See open Q on data source.)

## 4. Where the data comes from (proposed, read-only)

- **Backtest** → the isolated SQLite store (`backtest_trades`). Trivially
  read-only; no live coupling. Could be (a) read directly by a small read-only
  service, or (b) pre-baked into a static JSON at build time. **Recommendation:
  pre-bake to static JSON** — the showcase never needs live freshness for
  backtests, and a static artifact removes all coupling to the app DB.
- **Live** → the live Postgres, **read-only**, via a dedicated read-only query
  path. This is the sensitive one (it reads the live real-money strategy's
  records). Must be strictly SELECT-only and must honestly report thin/empty.

## 5. Open questions for Jayesh (every one — do not let me guess)

1. **Public or authed?** Is `/api/showcase/*` public (marketing site) or behind
   login? Public changes the threat model (rate-limiting, data minimization).
2. **Live data source.** Live per-trade NET needs realized P&L. The reconciler is
   log-only (write OFF) so `final_pnl` is mostly NULL. Options: (a) leave live
   metrics `null` + "insufficient data" until the reconciler write-path is
   approved; (b) a separate read-only live-metrics path. **Which?** I will NOT
   flip `PNL_RECONCILER_WRITE` — that is yours to decide.
3. **Show ANGELONE at all?** It's PAPER-only. Do we surface a paper strategy
   publicly, clearly labelled — or hold it back until forward-tested?
4. **BSE/CDSL thin live record.** With ~0 confirmed live fills, do we (a) show
   "Live — 0 confirmed fills, tracking", (b) show only the backtest with a "live
   tracking begins …" note, or (c) hold live until N confirmed fills? My default
   would be the most conservative (b/c), but this is a credibility call for you.
5. **Static pre-bake vs live read.** OK to pre-bake backtest metrics to a static
   JSON at build (recommended) — or do you want a live read-only endpoint?
6. **Strategy key vs UUID.** OK to expose stable slugs (`bse`/`cdsl`/`angelone`)
   and NOT the internal strategy UUIDs on the public surface?
7. **Backfill BSE/CDSL store tags.** The isolated `backtest_trades` now has
   `broker`/`is_paper` columns; ANGELONE rows are tagged, but **BSE/CDSL rows are
   left NULL** (I did not guess). Should BSE/CDSL be backfilled
   (`broker='BSE'/'CDSL'`, `is_paper=0` since they're live-real)? Your call.
8. **"broker" terminology.** The task tag `broker='ANGELONE'` actually denotes the
   **NSE:ANGELONE instrument** (Angel One Ltd stock futures), not the Angel One
   *brokerage*. Confirm the field name — `instrument`/`symbol` may be clearer than
   `broker`, to avoid confusion with Dhan/Fyers broker adapters.
9. **Forward-test track.** Do you want a `FORWARD_TEST` state wired now (out-of-
   sample, paper/tiny-size, tracked forward) as the honest bridge between backtest
   and live? If so it needs its own store (not the in-sample backtest table).
10. **Who signs off "verified".** What's the gate for a strategy to move from
    PAPER/backtest to a publicly-shown LIVE_REAL label? (e.g. N confirmed fills +
    reconciled NET P&L.)

## 6. Explicitly out of scope for this proposal
- No implementation. No routes, no models, no DB reads were coded.
- No new Postgres migration, no app-DB schema change.
- No change to the live execution path or any sacred file.
- No decision on the frontend — this is the backend contract only.

---

## 7. Resolutions (Batch 2) — proposed answers + flagged framing calls

Legend: **[RESOLVED]** = I took a technical decision (reversible). **[FLAG]** =
honesty/framing/business call — **I did NOT decide; Jayesh chooses.** Proposed
public-facing copy is a DRAFT for approval, never final.

1. **Public or authed?** — **[FLAG]** (business + risk). *Proposal:* launch
   **authed/internal preview first**; go public only after the live record is
   non-trivial. Rationale: a public page with a thin/zero live record invites
   "is this real?" — better to mature it behind login first. Your call.
2. **Live data source** (reconciler log-only → `final_pnl` mostly NULL). —
   **[RESOLVED + FLAG]**. *Resolved:* the live endpoint reads existing tables
   read-only and **withholds metrics**, reporting "N recorded, R reconciled"
   honestly (built + tested in `showcase_draft.py`). *Flag:* to ever show live
   per-trade NET, the reconciler write-path must be enabled — **I did NOT flip
   `PNL_RECONCILER_WRITE`; that is your decision.**
3. **Show ANGELONE (paper) publicly?** — **[FLAG]** (framing). *Proposal:* yes,
   but only behind an unmistakable **PAPER** badge, never adjacent to live numbers
   without the label. Copy below.
4. **BSE/CDSL thin live record — show or hold?** — **[FLAG]** (honesty/framing,
   the most important one). *Proposal:* **show it honestly** ("tracking has
   begun, 0 reconciled") rather than hide it OR pad it with backtest numbers.
   But whether to surface a near-empty live record publicly at all is your call.
   Copy below.
5. **Static pre-bake vs live read.** — **[RESOLVED]**. Backtest = **static
   pre-baked JSON** (`showcase_backtest.json`, committed) — no live coupling, no
   freshness need. Live record = read-only endpoint. (Done.)
6. **Strategy key vs UUID.** — **[RESOLVED]**. Public surface uses stable slugs
   (`bse`/`cdsl`/`angelone`); UUIDs stay internal. (Done in the draft router.)
7. **Backfill store tags.** — **[RESOLVED]** (Batch-2 Task 1). `broker`→
   `instrument` (= BSE/CDSL/ANGELONE); `is_paper` set NULL on ALL backtest rows
   (a backtest is neither paper nor real).
8. **"broker" terminology.** — **[RESOLVED]**. Renamed to `instrument`.
9. **Forward-test track.** — **[RESOLVED-as-instructed + FLAG].** You set
   **CDSL = FORWARD_TEST**; applied verbatim in the JSON + draft. **[FLAG]:** CDSL
   is a *live-real-money* strategy (went live ~2026-05-25). Labelling a real-money
   strategy "forward test" is *more* conservative (doesn't overclaim a record) —
   but confirm that's the framing you want vs "Live (early/thin)". A true
   forward-test track (out-of-sample, paper/tiny-size, tracked forward) would need
   its own store, separate from this in-sample backtest table.
10. **Who signs off "verified" (PAPER/backtest → publicly-shown LIVE_REAL)?** —
    **[FLAG]** (policy). *Proposal for a gate:* promote to a shown LIVE_REAL record
    only when **≥ N broker-confirmed, reconciled round-trips** exist (suggest
    N≈30) **and** their NET P&L is reconciler-confirmed. Until then the state stays
    "Live tracking (insufficient data)". You set N and own the sign-off.

### Proposed public-facing copy (DRAFT — approve/replace before any UI)
> These are *proposals*. The frontend/visualisation decision (incl. whether to
> chart the cumulative series) remains yours — I only expose the data.

- **Backtest badge:** `Backtest · in-sample` — tooltip: *"Historical signals
  replayed on the strategy's own history (v4.8.1). In-sample — not a guarantee of
  future results. Charges estimated; slippage excluded."*
- **Live (real) — thin record:** `Live tracking · {N} trades recorded · {R}
  reconciled` — caption: *"Live real-money tracking has begun. Verified per-trade
  results appear once enough trades are reconciled. Shown honestly — no backtest or
  estimated numbers are substituted here."*
- **Forward test (CDSL):** `Forward test · out-of-sample` — caption: *"Tracked
  live-forward on out-of-sample signals. Limited sample — not a track record."*
- **Paper (ANGELONE):** `Paper · simulated` — caption: *"Backtest-only candidate.
  No real money has been traded on this strategy."*
- **Cumulative series (IF charted):** caption: *"Illustrative cumulative edge — sum
  of per-trade % on a constant unit. NOT compounded and NOT a rupee return."*
  **[FLAG]:** the series endpoint is a large non-compounded sum (e.g. BSE ≈ +1,829%);
  showing it risks being misread as a return. Recommend **not** labelling it a
  percentage return, or charting normalised shape only. Your framing call.
