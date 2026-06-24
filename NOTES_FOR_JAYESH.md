# NOTES FOR JAYESH

> **Integration branch `integration/marketplace-billing`** — deploy bundle: showcase + Phase 1 fan-out (incl. leak bugfix) + Phase 2 Razorpay. Each track's notes are preserved verbatim below; the integration-prep summary is at the very end.

# ============================================================
# TRACK S — showcase / Track Record (feat/showcase-angelone-prep)
# ============================================================

# NOTES FOR JAYESH — overnight showcase-prep run

**Session:** night of 2026-06-21 → morning 2026-06-22 (you asleep, review on wake).
**Branch:** `feat/showcase-angelone-prep` (off `main` @ 730ce91). **Pushed to origin. NOT merged to main.**
**Commits (this branch, in order):**
- `7f656e0` — Task 1: ANGELONE ingested into isolated store (append-only)
- `463930e` — Task 2: consolidated honest summary + generator
- `7b5782d` — Task 3: showcase backend design proposal (review only)
- (this NOTES file)

---

## What I built

### Task 1 — ANGELONE ingested ✅
- File used: `~/Downloads/MA_+_..._NSE_ANGELONE_2026-06-22.csv` (see decision #1 — the path you gave didn't exist on this host).
- New script `backend/scripts/ingest_angelone_trade_list.py` — **append-only**, reuses the exact parse + NFO-cost logic of `ingest_backtest_trade_list.py` (imported, not copied).
- **942 ANGELONE trades** (620 long / 322 short, **0 open**, all cleanly paired), 2020-10 → 2026-06, into `backtest_trades` in the isolated SQLite store.
- Tags applied: `source=tv_trade_list`, `strategy_version=v4.8.1`, `broker=ANGELONE`, `is_backtest=1`, `is_live=0`, `is_paper=1`.
- Added `broker` + `is_paper` columns to the **isolated SQLite** table (not the app DB).
- **BSE (1149) and CDSL (1032) rows untouched** — verified before/after. Signal-history table (731) untouched. Compounded cumulative + qty/value/INR artifacts **excluded** (not stored).

### Task 2 — Consolidated honest metrics ✅
- `backend/scripts/build_showcase_summary.py` (reads the store read-only) → `backend/scripts/SHOWCASE_BACKTEST_SUMMARY.md`.

| | BSE | CDSL | ANGELONE |
|---|---|---|---|
| Closed trades | 1,149 | 1,031 (+1 open excl.) | 942 |
| Win rate | 77.46% | 70.81% | 73.14% |
| Avg gross/trade | +1.622% | +1.133% | +1.415% |
| Avg NET/trade (est.) | +1.592% | +1.103% | +1.386% |
| Profit factor | 5.80 | 3.91 | 3.82 |
| Longest losing streak | 6 | 13 | 7 |
| **Max drawdown (non-comp.)** | 5.24% | 5.21% | **9.89%** |

- **Honest flag:** ANGELONE's max drawdown (~9.9%) is ~2× BSE/CDSL — it's the more volatile of the three. Surfaced, not buried.
- Caveats in the MD: in-sample, charges-only-not-slippage, no walk-forward, curve-fit risk, ANGELONE=PAPER, no compounded totals.

### Task 3 — Backend design PROPOSAL (no code) ✅
- `backend/scripts/SHOWCASE_BACKEND_DESIGN.md` — read-only `/api/showcase` endpoints, JSON data-contract (no compounded/INR fields by construction), 4-state labelling spec (backtest-in-sample / live-real / paper / forward-test), + **10 open questions**. Nothing implemented.

---

## Decisions I made (and why)

1. **ANGELONE file path.** The path in the task (`/mnt/user-data/uploads/...`) does **not exist** on this Mac. An **identically-named** file (`...NSE_ANGELONE_2026-06-22.csv`, v4.8.1) exists in `~/Downloads` — same naming convention as the BSE/CDSL files you uploaded earlier today, which were also in `~/Downloads`. I used that copy. File identity is unambiguous by name. **→ Confirm this is the right file.**
2. **Append-only, new script** (not re-running the base script, which DROP+recreates and would re-ingest BSE/CDSL). Idempotent: re-running refreshes ANGELONE only.
3. **Added `broker`/`is_paper` columns to the isolated SQLite** (allowed — not the app DB). For ANGELONE: `broker=ANGELONE`, `is_paper=1`.
4. **Left BSE/CDSL `broker`/`is_paper` = NULL** — I did **not** guess their values (see open Q below).
5. **Excluded ANGELONE's compounded cumulative** (16,242%) and all qty/value/INR — per the honesty doctrine.
6. **Committed the reused base ingester** (`ingest_backtest_trade_list.py`, previously untracked) as the dependency so the branch is reproducible.

---

## Open questions (need your call — I did NOT guess)

1. **BSE/CDSL store tags.** Their `broker`/`is_paper` are NULL. Backfill to `broker='BSE'/'CDSL'`, `is_paper=0` (they're live-real)? Or leave NULL? (I left them, per "don't guess.")
2. **"broker" terminology.** Your tag `broker='ANGELONE'` denotes the **NSE:ANGELONE instrument** (Angel One Ltd stock futures), NOT the Angel One brokerage. I stored it literally as `broker=ANGELONE` but suggest renaming the field to `instrument`/`symbol` to avoid confusion with Dhan/Fyers. Confirm.
3. **Live-tracking data source** (design Q2): live per-trade NET needs realized P&L, but the reconciler is log-only (`final_pnl` mostly NULL). I did **not** flip `PNL_RECONCILER_WRITE`. How should live metrics be sourced — or shown as "insufficient data"?
4. **Show ANGELONE (paper) publicly?** It has no live track record. Surface clearly-labelled, or hold until forward-tested?
5. **BSE/CDSL thin live record** (~0 confirmed live fills per the M1 audit): show "Live — 0 confirmed fills", or hold live until N fills?
6. Remaining design open Q's (public-vs-authed, static-prebake-vs-live-read, slug-vs-UUID, forward-test track, "verified" gate) are enumerated in `SHOWCASE_BACKEND_DESIGN.md` §5.

---

## What I deliberately did NOT do (and why)

- **No prod / EC2 / app-Postgres touch.** All live/trading data left untouched (didn't even read it tonight — only the isolated SQLite).
- **No sacred/live-trading files touched** (strategy_executor / direct_exit / strategy_webhook / kill_switch / dhan.py / fyers.py / strategy.py model / strategies migrations). Not opened.
- **No flag flips.** `PNL_RECONCILER_WRITE` still False, `PAYWALL_ENFORCED` still OFF.
- **No new Postgres migration, no app-DB schema change.** New columns went only to the isolated SQLite.
- **No merge to main, no prod deploy.** Branch pushed to origin only.
- **No showcase UI / no API implementation** — Task 3 is a written proposal only, as instructed.
- **No compounded totals** computed, stored, or written anywhere.
- **Did not guess** the BSE/CDSL `broker`/`is_paper` values or the live-data-source question — flagged above instead.

---

## How to verify (morning)
- `git log --oneline main..feat/showcase-angelone-prep`
- Read `backend/scripts/SHOWCASE_BACKTEST_SUMMARY.md` and `SHOWCASE_BACKEND_DESIGN.md`.
- Store check: `sqlite3 backend/backtest_signal_history.sqlite3 "SELECT strategy_label,count(*),sum(is_open) FROM backtest_trades GROUP BY strategy_label;"` → BSE 1149, CDSL 1032 (1 open), ANGELONE 942 (0 open).
- The SQLite store is git-ignored (data stays local/isolated); the scripts + docs are on the branch.

---

# BATCH 2 — overnight continuation (same branch, morning review)

**Branch:** `feat/showcase-angelone-prep` (pushed). **Commits added this batch:**
- `443e341` — Task 1: store fixes (broker→instrument, is_paper NULL)
- `638d2c3` — Task 2: static `showcase_backtest.json` + generator
- `0bba08b` — Task 3: DRAFT read-only `/api/showcase` router + tests (NOT wired)
- `403fcbc` — Task 4: resolved the 10 design open-questions
- (this notes update)

## What I built (Batch 2)

**Task 1 — store fixes** (`backend/scripts/fix_backtest_trades_schema.py`): renamed `broker`→`instrument` (now holds BSE/CDSL/ANGELONE) and set **`is_paper` = NULL on all backtest rows** (a backtest is neither paper nor real). Isolated SQLite only; counts intact (BSE 1149 / CDSL 1032 / ANGELONE 942).

**Task 2 — static artifact** (`backend/scripts/showcase_backtest.json`, 132 KB, committable): per-strategy size-independent metrics + **non-compounded cumulative series** (I exposed **both** gross and net so the gross/net choice stays yours). 4-state labels baked: backtest=in-sample for all; live-status **BSE=LIVE_REAL, CDSL=FORWARD_TEST, ANGELONE=PAPER**. **No INR, no qty/value, no compounded totals** (audited).

**Task 3 — DRAFT API** (`backend/app/api/showcase_draft.py` + `backend/tests/test_showcase_draft.py`): inert router (deliberately omitted from `main.py` — verified not referenced). `/backtest/{key}` serves the static JSON; `/live/{key}` builds an HONEST record from **read-only raw SELECTs** (no sacred-model import). Because the reconciler is log-only, `final_pnl` is mostly NULL → the record reports "N recorded, 0 reconciled" and **withholds metrics, never fabricates**. **10/10 tests pass** (`.venv/bin/python -m pytest tests/test_showcase_draft.py`).

**Task 4 — resolved 10 Qs** (appended as §7 to `SHOWCASE_BACKEND_DESIGN.md`): technical ones decided; honesty/framing ones flagged with **draft public-facing copy** for your approval.

## Decisions I made (and why)
1. **`instrument` backfilled = strategy_label** (BSE/CDSL/ANGELONE) — factual mapping, not a guess (the instrument for a 'BSE' row is 'BSE').
2. **Cumulative series exposed as both gross AND net** — to avoid making a framing choice; frontend/you decide which (or whether) to chart.
3. **Removed the literal ₹ notional from the JSON** (kept the size-independent cost % instead) so the public artifact carries **zero INR**.
4. **Live metrics always `null` tonight** — even when position count is "sufficient", per-trade NET needs reconciled `final_pnl`, which doesn't exist (reconciler log-only). I refuse to fabricate.

## Open framing questions — YOUR call (I did NOT decide)
- **F1. Show the thin/zero live record publicly?** (BSE/CDSL have ~0 reconciled fills.) Show honestly vs hold behind login. (Design §7 Q1/Q4.)
- **F2. CDSL labelled FORWARD_TEST** as you instructed — but CDSL is a *live-real-money* strategy (live ~2026-05-25). Confirm "forward test" is the framing you want for a real-money strategy (it under-claims, which is safe, but is it intended?).
- **F3. The cumulative series endpoint is a large non-compounded sum** (BSE net ≈ +1,829%). If charted, it must NOT be presented as a % return. Recommend normalised-shape-only or no curve. (Design §7 copy block.)
- **F4. Enable reconciler write-path?** Needed before any live per-trade metric can ever be shown. **I did NOT flip `PNL_RECONCILER_WRITE`** — your decision.
- **F5. "Verified" gate** (N reconciled trips before a LIVE_REAL record is shown) — I proposed N≈30; you set it.
- Draft label/caption copy for all of the above is in `SHOWCASE_BACKEND_DESIGN.md` §7 — approve/replace before any UI.

## What I deliberately did NOT do (and why)
- **No `main.py` wiring** of the draft router (would "enable" it) — left inert.
- **No flag flips** (`PNL_RECONCILER_WRITE` False, `PAYWALL_ENFORCED` OFF).
- **No app-DB migration / no Postgres schema change** — only the isolated SQLite was altered; live tables are read-only SELECT only (and not even queried tonight — the live endpoint is untested against prod by design).
- **No sacred/live/prod/EC2 touch, no deploy, no merge to main.**
- **No compounded totals** anywhere. **No fabricated live metrics.**
- **Did not decide any honesty/framing call** — flagged F1–F5 instead.

## How to verify (Batch 2)
- `git log --oneline main..feat/showcase-angelone-prep` (9 commits total).
- `cd backend && .venv/bin/python -m pytest tests/test_showcase_draft.py -q` → 10 passed.
- `python3 -c "import json;d=json.load(open('backend/scripts/showcase_backtest.json'));print([(s['key'],s['live_status']['track_type']) for s in d['strategies']])"`
- Confirm inert: `grep -c showcase backend/app/main.py` → 0.

---

# SHOWCASE BUILD — Module 1 of 4: honest metrics engine + regenerate data

**Branch:** `feat/showcase-angelone-prep`. Frontend NOT touched this module. No sacred/DB/flag/prod changes.

## Why: the previous `showcase_backtest.json` had WRONG max-drawdown
The old DD was computed as `(peak − equity)/peak` on a `1+Σr` curve — a peak-NORMALISED (compounded-flavoured) basis → ~2× too low (e.g. BSE showed **5.24%**). Corrected basis: **peak-to-trough of the running SUM of per-trade Net PnL %, in percentage points, NOT normalised**.

## ✅ Verification — engine vs independent reference (ALL PASS)
| | trades | win % | avg/tr | PF | **max-DD (was → now)** |
|---|---|---|---|---|---|
| BSE | 1149 ✓ | 77.5 ✓ | +1.62 ✓ | 5.80 ✓ | **5.24 → −10.30 ✓** |
| CDSL | 1032 ✓ | 70.8 ✓ | +1.13 ✓ | 3.91 ✓ | **5.21 → −11.89 ✓** |
| ANGELONE | 942 ✓ | 73.1 ✓ | +1.42 ✓ | 3.82 ✓ | **9.89 → −17.86 ✓** |

ANGELONE per-year max-DD all PASS: 2020 −17.86 · 2021 −15.45 · 2022 −13.91 · 2023 −16.31 · 2024 −15.95 · 2025 −14.14 · 2026 −14.61. **Zero mismatches** — no silent adjustment was needed.

Basis confirmed by matching the references: order by **EXIT date**; **all** trades counted (CDSL 1032 includes the 1 open MTM row); raw **Net PnL %** (no cost model). CSV spot-check (3/strategy, incl. trade #1/mid/last) all MATCH the source files.

## What changed (this module)
- **NEW** `backend/scripts/showcase_metrics.py` — the single honest engine: `metrics`, `max_drawdown` (corrected), `aggregate_metrics`, `per_period` (year/month, DD resets per period), `build_doc`, and a `verify()` that checks the reference values + a `regen` CLI that **refuses to regenerate if verification fails**.
- **REGENERATED** `backend/scripts/showcase_backtest.json` — replaces the old wrong-DD file. New shape: per strategy `backtest.aggregate` + `backtest.by_year` + `backtest.by_month`; 4-state labels (BSE=`LIVE_REAL`, **CDSL=`LIVE_NO_TRADES`** "newly live — no live trades yet", ANGELONE=`PAPER`); in-sample caveats. **Removed** `cumulative_series` (F3) and all compounded/INR.
- **NEW** `backend/tests/test_showcase_metrics.py` — 9 tests (DD known-sequences incl. "not normalised by peak", win/avg/PF, per-period reset, + integration test reproducing the references). `9 passed`.

## ⚠️ Cost-model question — FLAGGED, not decided (Task 5)
The reference values + this JSON are on the **raw Net PnL %** basis. `meta.cost_model.applied=false`. **Your call:** apply the Indian F&O cost model (`costs.py`) as a **uniform** haircut across ALL metrics + every period — or keep raw. If applied it must be uniform everywhere (and the reference numbers would shift down). NOTE on naming: the JSON field `avg_net_pct_per_trade` = TradingView's *raw* "Net PnL %" (net of TV's ~0 commission), **not** after the Indian cost model — I can rename to avoid confusion once you decide.

## What was NOT done (and why)
- **Did NOT apply the cost model** — flagged above for your decision.
- **Did NOT touch the frontend.** ⚠️ The frontend draft copy `frontend/src/lib/showcase/showcase-backtest.json` + `page.tsx` still hold the **OLD wrong-DD** data and the **old shape** (`backtest.metrics.closed_trades`, `cumulative_series`). The UI module must re-sync from the new backend JSON and re-key: `backtest.metrics`→`backtest.aggregate`, `closed_trades`→`trades`, and render `max_drawdown_pct` as the new **negative** value.
- **Did NOT delete the superseded batch-2 artifacts.** ⚠️ `backend/scripts/build_showcase_json.py` and `build_showcase_summary.py` + `SHOWCASE_BACKTEST_SUMMARY.md` still compute/contain the OLD normalised DD — do NOT use them; `showcase_metrics.py` is now the single source. Recommend deleting/replacing them in a later module.
- No sacred/live/prod/config/migration/flag changes; no merge to main.

## How to verify (Module 1)
- `python3 backend/scripts/showcase_metrics.py` → "OVERALL: ALL PASS".
- `cd backend && .venv/bin/python -m pytest tests/test_showcase_metrics.py -q` → 11 passed.
- `python3 -c "import json;d=json.load(open('backend/scripts/showcase_backtest.json'));print([(s['instrument'], s['backtest']['aggregate']['all']['max_drawdown_pct']) for s in d['strategies']])"` → BSE −10.3 / CDSL −11.89 / ANGELONE −17.86.

## Module 1 ADDENDUM — per-direction metrics (all / long / short)
Added per-DIRECTION breakdown (direction = entry-row Type: Entry long / Entry short). Every level — **aggregate, by_year, by_month** — is now split `{all, long, short}`.

✅ **All 24 per-direction reference values reproduced exactly (zero mismatches):**
| | long | short |
|---|---|---|
| BSE | 805 tr · 82.4% · PF 6.50 · DD −10.00 | 344 tr · 66.0% · PF 4.55 · DD −9.14 |
| CDSL | 742 tr · 75.2% · PF 3.95 · DD −10.92 | 290 tr · 59.7% · PF 3.82 · DD −17.01 |
| ANGELONE | 620 tr · 77.4% · PF 3.69 · DD −20.49 | 322 tr · 64.9% · PF 4.07 · DD −12.87 |

- Each long/short slice carries **`slice_of_full_system: true`** (at every level) + a `caveat` on the aggregate slices; `meta.slice_caveat` holds the canonical text for the UI to render: *"Long-only / short-only is a SLICE of the full long+short system … NOT an independently-validated standalone strategy."* The `all` slice carries no flag (it IS the full system).
- ⚠️ **DISPLAY data only** — no per-direction signal-routing / execution logic was added (that touches the sacred executor and is explicitly a separate future module, out of scope here).
- Tests now 11 (added per-direction split + slice-flag + side-isolation); `regen` still refuses if any reference (now incl. per-direction) mismatches.
- Same cost-model FLAG applies to the per-direction figures (raw Net PnL % basis).

---

# Module 1.5 — cost model as a transparent layer + cleanup

**Decision implemented:** display **NET-of-charges**, keep **RAW** as verified ground truth. Both are in the JSON (nested `backtest.raw` / `backtest.net` + `backtest.cost_delta`), so the haircut is fully auditable. RAW `verify()` (all + per-direction + per-year refs) is **UNCHANGED and still ALL PASS** — integrity baseline intact.

## Raw → Net deltas (aggregate, all) — for your review
| | avg/tr raw → net | charge/tr | PF raw → net | maxDD raw → net |
|---|---|---|---|---|
| **BSE** | +1.622% → **+1.487%** | 0.135% | 5.80 → 5.01 | −10.30 → −11.13 |
| **CDSL** | +1.132% → **+1.053%** | 0.079% | 3.91 → 3.56 | −11.89 → −12.83 |
| **ANGELONE** | +1.415% → **+1.342%** | 0.073% | 3.82 → 3.57 | −17.86 → −18.50 |

(BSE's charge is higher because it has many early low-price trades → higher brokerage % on small 1-lot notionals. Net win-rate also dips slightly as marginal raw-wins flip to net-losses after charges.)

## Charge rates used (web-verified 2026-06-22) + source
Added a **separate, dated** `SHOWCASE_NFO_RATES` constant in `costs.py` (used by the showcase via the `rates=` override) — NSE equity FUTURES:
- **STT 0.05% on SELL** (hiked from 0.02% → 0.05%, eff. 2026-04-01) · NSE txn **0.00183%** · SEBI **₹10/cr** · stamp **0.002% buy** · GST **18%** on (brokerage+txn+SEBI) · brokerage **Dhan ₹20/order**.
- Source: **Zerodha charges** (https://zerodha.com/charges/), cross-checked vs NSE/web. All flagged `estimated=true` in meta.
- Position value = **1 lot at current contract lot size** (BSE 375 / CDSL 475 / ANGELONE 2500, web-verified); brokerage is the only size-dependent charge. Historical lot revisions are NOT modelled (documented in meta).

## ⚠️ Two flags for you
1. **Reconciler rates are now stale:** I did **NOT** touch `SEGMENT_RATES["NFO"]` (still 0.02% STT) — changing it would break the deployed reconciler's ~10 pinned cost-test assertions and alter its (log-only) cost model. The reconciler's NFO STT should be refreshed to 0.05% in its **own** task (with its test updates). Kept separate to preserve the reconciler integrity baseline.
2. **SLIPPAGE is excluded** — not estimated, not applied. It is expected to be the **LARGER** real-world drag and will be measured later from real live fills vs backtest signal price. NET is therefore **best-case**; caveated in `meta` + `cost_model.slippage_excluded=true`. No execution-path changes were made.

## Renames / structure
- Renamed the ambiguous `avg_net_pct_per_trade` → **`avg_pct_per_trade`** (and `median_*` likewise); raw-vs-net is now explicit via the `backtest.raw` / `backtest.net` nesting. `backtest.display_basis="net"`.

## Cleanup (single source of truth = showcase_metrics.py)
Deleted the superseded batch-2 artifacts that still carried the OLD wrong/normalised DD: `backend/scripts/build_showcase_json.py`, `build_showcase_summary.py`, `SHOWCASE_BACKTEST_SUMMARY.md`. (No code referenced them.)

## What was NOT done
- Did not touch the **frontend** (re-syncs in the UI module — it must now read `backtest.net.*`, the `{all,long,short}` split, and render the slice + slippage caveats).
- No sacred/prod/flag/migration changes; reconciler `SEGMENT_RATES` + tests untouched (13 pass); no merge to main.

## Verify (Module 1.5)
- `python3 backend/scripts/showcase_metrics.py` → RAW "OVERALL: ALL PASS".
- `cd backend && .venv/bin/python -m pytest tests/test_showcase_metrics.py tests/test_pnl_reconciler.py -q` → **29 passed**.
- `python3 -c "import json;d=json.load(open('backend/scripts/showcase_backtest.json'));b=d['strategies'][0]['backtest'];print('display',b['display_basis'],'| BSE net avg',b['net']['aggregate']['all']['avg_pct_per_trade'],'| charge',b['cost_delta']['all']['avg_charge_pct_per_trade'])"`

---

# Module 2 — read-only /api/showcase API

**New router:** `backend/app/api/showcase_api.py` — serves the `showcase_backtest.json` **NET** figures only (no recompute; `showcase_metrics.py` stays the single source of truth). All GET, all read-only.

## Endpoints
- **`GET /api/showcase`** — lists all 3 strategies: key, instrument, name, 4-state `live_status` (BSE=LIVE_REAL, CDSL=LIVE_NO_TRADES, ANGELONE=PAPER), and NET headline metrics (win_rate_pct, avg_pct_per_trade, profit_factor, max_drawdown_pct, trades) + global meta.
- **`GET /api/showcase/{key}`** — full NET detail: `aggregate + by_year + by_month`, each split `{all, long, short}`; long/short slices carry `slice_of_full_system` + `caveat`; includes `meta` (in-sample/hypothetical caveats, `slippage_excluded=true`, `cost_model` rates+asof+estimated) and the per-strategy `cost_delta`. 404 on unknown key.
- **`GET /api/showcase/{key}/live`** — honest reconciled-real-trade count via a **read-only `SELECT count(*)`** (raw `text()`, joins `strategy_positions`+`strategies` on `is_paper=false AND final_pnl IS NOT NULL`). Currently 0 everywhere (reconciler log-only) → returns `{"status":"tracking_active","reconciled_trades":0,"note":"Live tracking active — no trades reconciled/published yet"}`. ANGELONE (no live deployment) → `{"status":"paper_no_live",...}`. **NEVER fabricates P&L.**

## What was mounted (exactly)
In `backend/app/main.py` `create_app()`, two lines added:
- import: `from app.api.showcase_api import router as showcase_router`
- include: `app.include_router(showcase_router)  # Showcase M2 — read-only public GET /api/showcase (no writes)`

Verified: `create_app()` mounts `/api/showcase`, `/api/showcase/{key}`, `/api/showcase/{key}/live` — all **GET-only**.

## Read-only verification (result)
- Router imports only: `json`, `os`, `typing`, `fastapi`, and (lazily, for /live) `app.db.session.get_session` + `sqlalchemy.text`. **No** executor / direct_exit / strategy_webhook / kill_switch / broker / order_router import.
- Static scan (and a unit test) confirm **zero** write/mutation tokens (`INSERT`/`UPDATE`/`DELETE`/`.commit(`/`session.add`/`.flush(`) and no trading-module tokens. The only DB op is `SELECT count(*)`.
- Tests: `tests/test_showcase_api.py` — list/detail shapes, **NET-not-RAW** assertion, slice caveats present, honest empty live state, "never fabricates P&L", and the no-write/no-trading-path assertion. **39 passed** (showcase_api + showcase_metrics + reconciler together).

## Cleanup
Removed the superseded inert `app/api/showcase_draft.py` + `tests/test_showcase_draft.py` (read the OLD JSON shape — its test was already failing against the regenerated NET JSON). `showcase_api.py` replaces it.

## What was NOT done
- No recompute in the API (serves the artifact). No write path anywhere. No new endpoint beyond the 3.
- No sacred/config/migration/flag changes; no deploy; no merge to main. (Edited `main.py` only — not a sacred file — to mount the router, as Task 4 requires.)
- Frontend still not touched (UI module). The reconciler-rate staleness flag from Module 1.5 still stands.

## Verify (Module 2)
- `cd backend && .venv/bin/python -m pytest tests/test_showcase_api.py -q` → passes.
- `cd backend && .venv/bin/python -c "from app.main import create_app; a=create_app(); print(sorted(r.path for r in a.routes if 'showcase' in getattr(r,'path','')))"` → the 3 routes.

---

# Module 3 — frontend showcase page (Next.js draft)

**Built:** `frontend/src/app/(public)/showcase/page.tsx` — a proper Next.js page on existing brand tokens + `GlassmorphismCard` (dark theme; demo hexes map 1:1 to tokens: `--background #0A0E1A`, `--profit/neon-green #00FF88`, `--accent-blue/purple/gold`, `--loss`). Consumes the Module 2 API at runtime via `useApi` — `/api/showcase`, `/api/showcase/{key}`, `/api/showcase/{key}/live` — **NET basis**.

## Replaced / re-keyed
- Rewrote the stale Module-0 page (old static-JSON shape) → now API-driven, re-keyed to the new shape (`backtest.net.aggregate / by_year / by_month`, each `{all,long,short}`).
- `frontend/src/lib/showcase/data.ts` → **types only** (API response shapes + badge map); no static data.
- **Deleted** the stale `frontend/src/lib/showcase/showcase-backtest.json` (old-shape copy) — the API is the source.
- Drawdown rendered as the **negative** value the API returns (e.g. BSE net **−11.13%**), not the demo's stale −5.24%.

## Matches the approved demo — with the honesty fixes the task requires
- Hero thesis "**Backtest nahi. Proof.**", "Verified record first, backtest as context", How-it-works, disclaimer band, per-strategy cards, All/Long/Short + Yearly/Monthly toggles (matches `_2` demo UX).
- **Transparency Ledger = mechanism/concept, NOT a fake feed.** No fabricated trade rows, no fake `0x…` hashes (the chain isn't built). Shows the 3-step mechanism + honest state: *"Live tracking active — 0 trades reconciled & published yet."* (from `/live`).
- Per card: 4-state badge (LIVE_REAL green / LIVE_NO_TRADES blue / PAPER muted) — factual, not a screaming hero; honest live panel from `/live` (thin/empty, no fabricated numbers); **max drawdown as prominent as returns** (big `--loss` figure); backtest section dashed + "In-sample backtest — hypothetical, not a guarantee", visually subordinate.
- **Direction toggle** swaps win/avg/PF/DD/trades to `aggregate[all|long|short]`; long/short render the API's `slice_of_full_system` caveat. **Period toggle** renders `by_year`/`by_month` table for the selected direction (API nests `{all,long,short}` per period — used directly).
- Disclaimer band: high-risk, hypothetical/hindsight, **slippage-excluded (best-case)**, no guaranteed returns, white-box, fixed-size basis differs from TradingView's compounded figures.
- Accessibility: toggles are real `<button>`s (keyboard-focusable, `aria-pressed`, focus-visible ring); no essential motion (CSS hover only) so `prefers-reduced-motion` is respected; responsive (stacks on mobile). A "◆ DRAFT — for review · not the live site" ribbon is shown.

## Verification
- **Typecheck clean** on my files (`tsc --noEmit` → 0 showcase errors; the only 10 errors are the pre-existing `tests/*` baseline). **Lint clean** (`eslint` → no output) on `page.tsx` + `data.ts`.
- Not visually rendered here (needs the backend running) — see local-run below.

## How to run it locally (for review)
1. Backend (serves the API): `cd backend && .venv/bin/python -m uvicorn app.main:app --reload` (needs the local Postgres for `/live`; list+detail read the static JSON artifact so they work even if the DB is down — `/live` will just error and the card shows its honest fallback).
2. Frontend: `cd frontend && npm run dev` → open `http://localhost:3000/showcase`.
3. If `/showcase` shows "Couldn't load — is the backend running?", the API base isn't reachable; confirm the backend is up and the frontend's API base points at it (`.env.local`).

## What was NOT done
- Frontend only — no backend/API/sacred/config/migration/flag change.
- No fabricated live data, no fake hashes/ledger rows, no compounded totals, no cumulative-return curve, no rupee P&L.
- **No merge to main, no deploy** (Vercel auto-deploys main). Branch only.

---

# Module 3.5 — honest chart series (data only, no UI)

Added 3 series in `showcase_metrics.py` (single source of truth), computed on the **NET (post-cost)** per-trade series, per strategy AND per direction `{all,long,short}`. **HARD RULE held: NON-compounded, fixed-size.** No `1+r` compounded curve, no INR, no compounded totals.

- **`equity_curve_noncompounded`** — running **SUM** of per-trade % (start 0), one `{d, v}` point per trade in exit-date order. (BSE all ends at **+1708.58%** — the honest fixed-size sum, NOT the +16,242% TradingView compounded fantasy.)
- **`drawdown_curve`** — `running_sum − running_peak` at each point (≤0 throughout, underwater plot), `{d, v}`.
- **`monthly_returns_grid`** — `year → month → {ret (SUM of per-trade %, non-compounded), n (trade count)}` for a heatmap.

Placed under `backtest.net.series.{all,long,short}`; the M2 detail endpoint **passes them through** in the existing `/api/showcase/{key}` payload (`backtest.series`) — **no new endpoints**.

## ✅ VERIFY (gates regen; STOP on mismatch) — ALL PASS
| | last equity (all) == Σ NET % | min(drawdown) (all) == net max-DD (ref) |
|---|---|---|
| BSE | +1708.58 == +1708.58 ✓ | −11.13 == −11.13 (−11.13) ✓ |
| CDSL | +1086.76 == +1086.76 ✓ | −12.83 == −12.83 (−12.83) ✓ |
| ANGELONE | +1264.28 == +1264.28 ✓ | −18.50 == −18.50 (−18.50) ✓ |

`regen` now runs BOTH `verify()` (RAW refs — kept intact, still ALL PASS) AND the new `verify_series()`, and refuses to write if either fails.

## Notes
- `showcase_backtest.json` grew to ~**658 KB** (the per-trade curves). The detail endpoint serves one strategy's slice (~200 KB); gzip shrinks it heavily. If size matters later we can down-sample the curves — flag for the UI module.
- Tests: **45 pass** (added equity=cumulative-sum-not-compounded, drawdown-underwater-min=max-DD, monthly grid sum+count, series basis label, `verify_series` integration, and the API passthrough test).

## Scope
`showcase_metrics.py` + `showcase_api.py` only. No sacred/trading/migration/config/flag change. **No frontend**, no deploy, no merge to main.

## Verify (Module 3.5)
- `python3 backend/scripts/showcase_metrics.py regen backend/scripts/showcase_backtest.json` → "SERIES OVERALL: ALL PASS".
- `cd backend && .venv/bin/python -m pytest tests/test_showcase_metrics.py tests/test_showcase_api.py -q` → pass.

---

# Module 4 — Showcase FINISH (frontend only) · 2026-06-23

**Branch:** `feat/showcase-angelone-prep`. **Frontend only** — no backend/API/sacred/migration/config/flag change. **No new chart component** (reused the existing one). No deploy, no merge to main.

## What changed (4 files)
1. **`frontend/src/app/(public)/showcase/page.tsx`** — each strategy card now renders the **existing** `EquityCurve` component (reused, not rebuilt), fed `detail.backtest.series[dir].equity_curve_noncompounded` mapped `{d,v} → {time,value}`. It **follows the active All/Long/Short toggle** (same `dir` state the stats use). Captioned exactly as requested: *"Cumulative edge — fixed-size, non-compounded (NOT a compounded return)."* Loading state while `detail` is null; empty-slice state (*"No {dir} trades to chart."*) for a direction with zero trades. The chart sits **inside** the existing dashed "In-sample backtest · Hypothetical — not a guarantee" box, so it inherits that framing. **No compounded / +16,242%-style curve is rendered** — only the non-compounded cumulative-sum series the API already serves (BSE "all" ends at +1708.58%, the honest fixed-size sum).
2. **`frontend/src/components/charts/equity-curve.tsx`** — added two **backward-compatible optional props**: `unit?: "inr" | "pct"` (default `"inr"`) and `valueLabel?`. The default path is byte-identical to before, so the only other runtime caller (`dashboard/hero-pnl.tsx`, passes `data` only) is unaffected. The showcase passes `unit="pct"`, so the axis/tooltip read **`%`, not `₹`** — the series values are cumulative NET percentage-points and rendering rupees on them would be misleading. **Did NOT create a new chart component.**
3. **`frontend/src/lib/showcase/data.ts`** — added frontend types `SeriesPoint` + `SeriesBlock` and an **optional/nullable** `series` field on `ShowcaseDetail.backtest` to type the M3.5 passthrough the API already serves. **Type-only; no API change.**
4. **`frontend/src/app/(public)/layout.tsx`** — added **"Track Record" → `/showcase`** to `navLinks` (between Features and Pricing). One array drives both the desktop nav and the mobile menu, so `/showcase` is now reachable from both, matching existing nav-link styling.

Also **fixed the garbled hero caption** under "Live Strategies": the truncated *"…Risk utna hi prominent jitna return."* is now clean — *"…risk ko return jitni hi prominence di jaati hai, koi cherry-picking nahi."*

## Decisions / honesty notes
- **Drawdown curve NOT rendered** (task allowed equity-only). Risk is already prominent on each card (a 3xl Max-DD figure + a per-period Max-DD column), so a second chart would add clutter without new info. `drawdown_curve` is typed (`SeriesBlock`) and available if you want it later — same component, `unit="pct"`.
- The `/showcase` page still carries its "◆ DRAFT — for review · not the live site" ribbon. It's now linked in the public nav; remove the ribbon when you're ready to call it live.

## Verify (Module 4)
- `cd frontend && npx tsc --noEmit` → **zero errors in any changed file**. (Pre-existing failures are all in `tests/chart/*` + `tests/strategies/*` test files — unrelated test-type-debt, not introduced here.)
- `cd frontend && npx eslint "src/app/(public)/showcase/page.tsx" "src/components/charts/equity-curve.tsx" "src/lib/showcase/data.ts" "src/app/(public)/layout.tsx"` → **exit 0, clean**.
- Visual: `cd frontend && npm run dev` → open `http://localhost:3000/showcase` (needs the backend up for the API). "Track Record" appears in the top nav; each card shows the cumulative-edge chart and follows the direction toggle.
- **Not deployed, not merged to main.**

# ============================================================
# TRACK A — marketplace fan-out + leak bugfix (feat/marketplace-fanout)
# ============================================================

# NOTES FOR JAYESH — marketplace fan-out build

**Branch:** `feat/marketplace-fanout` (off `main` @ 730ce91). Pushed to origin. **NOT merged to main, NOT deployed.**
(Note: this file did not exist on `main`; the showcase NOTES live on the `feat/showcase-angelone-prep` branch. This is a fresh NOTES for the marketplace track.)

---

# Marketplace Module 0 — safety scaffold (ZERO live touch)

**Goal:** lay the foundation for subscriber fan-out WITHOUT touching the live path. After M0 **nothing executes differently** — it is purely a dormant flag + an empty, uncalled module. The owner 1→1 execution path is byte-identical.

## What was added (additive only — 3 files)
1. **Dormant feature flag** — `backend/app/core/config.py`
   - Added `marketplace_fanout_enabled: bool = Field(default=False)` (env `MARKETPLACE_FANOUT_ENABLED`), placed right after `paywall_enforced` and mirroring its style. **No existing config value was changed.**
   - Default **False** ⇒ platform stays owner-only 1→1. When later modules flip it True, the subscriber path runs **additively, alongside** the owner execution (never instead of it).
2. **Dormant stub module** — `backend/app/services/marketplace_fanout.py` (NEW)
   - `fanout_enabled() -> bool` — pure read of the flag.
   - `resolve_active_subscriptions(strategy_id) -> []` — STUB, always returns empty list. Docstring describes the future read-only query (active, non-expired `MarketplaceSubscription` rows for a strategy's listing).
   - `dispatch_subscriber_executions(signal, strategy) -> None` — STUB, no-op. Docstring describes the future additive per-subscriber dispatch (each subscriber's own `broker_credential_id` + per-subscriber qty, subscriber-scoped idempotency, per-subscriber partial-failure isolation).
   - Implements **nothing live**: zero DB access, zero broker calls, zero Celery dispatch, zero mutation. ORM types are imported **only under `TYPE_CHECKING`**, so the module is fully decoupled from the live path and importing it has no side effects.
3. **Tests** — `backend/tests/services/test_marketplace_fanout.py` (NEW), 6 tests, all green:
   - (a) flag field exists + `default is False`; runtime value False; `fanout_enabled()` False.
   - (b) **zero call sites**: each of `strategy_webhook.py`, `strategy_executor.py`, `signal_execution.py`, `direct_exit.py` is asserted to contain NO reference to `marketplace_fanout`; and a repo-wide scan asserts nothing under `app/` imports the module.
   - (c) stubs import cleanly + are no-ops (`resolve_… == []`, `dispatch_… is None`).

## Owner path untouched — confirmation
- **Tracked diff on this branch = `backend/app/core/config.py` ONLY** (one additive field). The two new files are net-new untracked additions.
- **No sacred file modified**: `strategy_webhook.py`, `strategy_executor.py`, `signal_execution.py`, `direct_exit.py`, kill_switch, broker adapters, `db/models/strategy.py`, and all migrations are byte-identical to `main`.
- **Zero call sites** in the live path — enforced by code AND by test (b), so a future accidental wiring would fail CI.
- **No DB migration** in this module. **No deploy, no EC2/prod touch, no merge to main.**

## Verify (Module 0)
- `cd backend && .venv/bin/python -m pytest tests/services/test_marketplace_fanout.py -q` → **6 passed**.
- `cd backend && .venv/bin/python -m pytest tests/test_config.py -q` → **9 passed** (additive flag broke nothing).
- `git diff --name-only main..feat/marketplace-fanout` → `backend/app/core/config.py` + the 2 new files only; no sacred files.

## What was deliberately NOT done
- Did NOT wire the module into the webhook/executor (that is a later module, behind the flag).
- Did NOT add a migration, change any model, or touch the live 1→1 path.
- No deploy, no merge to main.

---

# Marketplace Module 1 — subscriber lookup in webhook (flag-gated, LOG-ONLY)

**Goal:** when a signal arrives, resolve the strategy's ACTIVE subscribers and ONLY log them — no execution, no dispatch, no orders. Proves the lookup works while the owner 1→1 path stays byte-identical.

## What changed (2 live files + tests)
1. **`backend/app/services/marketplace_fanout.py`** — implemented `resolve_active_subscriptions(strategy_id, db)` as a real **READ-ONLY** query:
   - `SELECT` joining `marketplace_subscriptions` → `marketplace_listings` on `listing_id`, filtered by `listing.strategy_id == strategy_id` AND `subscription.status == 'active'`.
   - Returns a list of frozen `SubscriberRef` dataclasses carrying **only fields that exist today** (`subscription_id`, `subscriber_id`, `listing_id`, `status`, `subscribed_at`, `access_until`) — deliberately NOT broker_credential_id / qty (those columns don't exist yet).
   - Pure SELECT: no INSERT/UPDATE/DELETE, no flush, no commit, no session mutation.
   - `dispatch_subscriber_executions(...)` **stays a no-op stub** — no dispatch is implemented in this module.
2. **`backend/app/api/strategy_webhook.py`** — added ONE import and the additive hook **after** the owner dispatch + the owner `signal_received` log, **before** the existing success return (see the additive block below). The owner dispatch (ENTRY/PARTIAL/EXIT/SL_HIT) and the returned response are **untouched**.

### The additive block (verbatim)
```python
    # 15. Marketplace fan-out — ADDITIVE, flag-gated, LOG-ONLY (Module 1).
    if get_settings().marketplace_fanout_enabled:
        try:
            subscribers = await resolve_active_subscriptions(strategy_id, session)
            logger.info("fanout.dry_run.resolved", signal_id=..., strategy_id=...,
                        action=..., subscriber_count=len(subscribers))
            for sub in subscribers:
                logger.info("fanout.dry_run.subscriber", signal_id=..., strategy_id=...,
                            subscription_id=str(sub.subscription_id),
                            subscriber_id=str(sub.subscriber_id),
                            note="would route signal to subscriber (LOG-ONLY — no dispatch)")
        except Exception as exc:  # noqa: BLE001
            logger.warning("fanout.dry_run.failed", ..., error=str(exc))
    return { "status": "accepted", ... }   # unchanged owner response
```

## Owner path byte-identical when flag OFF — confirmation
- The whole block lives behind `if get_settings().marketplace_fanout_enabled:`. With the flag **False** (prod default), the block is skipped entirely; the **only** added cost is one short-circuiting bool read. The owner dispatch and the returned dict are byte-identical.
- The block is also wrapped in try/except so that, even with the flag ON, a subscriber-lookup failure can never affect the owner response (which has already dispatched above).
- **LOG-ONLY:** the block calls `resolve_active_subscriptions` (read-only SELECT) and `logger.info` per subscriber. **No** `dispatch_signal`, **no** broker calls, **no** order placement, **no** position writes, **no** mutation.
- **No sacred file touched:** `strategy_executor.py`, `direct_exit.py`, `kill_switch`, broker adapters, `db/models/strategy.py`, and migrations are all byte-identical. Only `strategy_webhook.py` (the one sanctioned call site) + `marketplace_fanout.py` changed. No migration.

## Tests (all green)
- `backend/tests/services/test_marketplace_fanout.py` (updated for M1): flag exists+defaults False; **call-site discipline** — the sacred execution files (`strategy_executor`/`signal_execution`/`direct_exit`) never reference the module, and the webhook is asserted to be the **only** importer under `app/`; dispatch stub still a no-op. (The M0 "zero call sites" guard was intentionally narrowed: the webhook is now the single allowed call site; the executor/worker/exit path stays sacred — and a test enforces exactly that.)
- `backend/tests/integration/test_marketplace_fanout_webhook.py` (new, against real sqlite + live webhook):
  - **(a) flag OFF** → `resolve_active_subscriptions` never called, owner `dispatch_signal` fires exactly once.
  - **(b) flag ON + 2 active + 1 cancelled seeded** → resolve returns the 2 active, handler logs `fanout.dry_run.resolved` (count=2) + one `fanout.dry_run.subscriber` per active sub; owner dispatch still exactly once (fan-out adds none); **zero** positions written.
  - **(c) read-only** → resolve returns active-only (cancelled excluded), subscription row count unchanged, nothing pending on the session.

## Verify (Module 1)
- `cd backend && .venv/bin/python -m pytest tests/services/test_marketplace_fanout.py tests/integration/test_marketplace_fanout_webhook.py tests/integration/test_strategy_webhook_async.py -q` → **21 passed** (incl. the full owner-path webhook regression suite).
- `cd backend && .venv/bin/python -m pytest tests/test_direct_exit_webhook.py tests/test_webhook_paper_mode_gate.py tests/integration/test_strategy_webhook_kill_switch.py tests/integration/test_exit_skip_reresolve.py tests/test_config.py -q` → **44 passed**.

## Deliberately NOT done
- No dispatch / no execution / no broker / no position writes — log-only, as scoped.
- No change to the owner dispatch or response; no migration; no flag flip in prod (default stays False).
- No deploy, no merge to main.

---

# Marketplace Module 2 — per-subscriber PAPER dispatch (flag-gated)

**Goal:** turn M1's log-only fan-out into actual per-subscriber dispatch — **PAPER ONLY**. Each active subscriber gets a *simulated* execution of the signal. No real broker order for any subscriber, under any config.

## What changed (2 live files + tests)
1. **`backend/app/services/marketplace_fanout.py`** — implemented `dispatch_subscriber_executions(signal, strategy, subscribers, db)` (was an M0 no-op stub):
   - For each active subscriber it runs **one simulated fill** by calling the OWNER's exact paper primitive — `app.services.strategy_executor._simulate_fill` (the same code the owner paper path runs at executor line ~193), reused via a lazy import. Returns one `PaperExecutionResult` per subscriber (new frozen dataclass), tagged `paper=True` + `subscription_id` + `subscriber_id`; logs `fanout.paper.executed` per subscriber + a `fanout.paper.summary`.
   - Default qty = `strategy.entry_lots or 1` (paper lot_size 1) — a sensible default; **per-subscriber qty is M4**.
   - Switched the module logger from stdlib to the codebase's structlog `get_logger` so per-subscriber structured logs work.
2. **`backend/app/api/strategy_webhook.py`** — the flag-gated block (after the untouched owner dispatch) now resolves subscribers (M1) → `await dispatch_subscriber_executions(...)`, replacing the M1 log loop. Still wrapped in try/except (a fan-out failure can't touch the owner response). Import + that block are the only changes; the owner dispatch and the returned response are byte-identical.

## PAPER-ONLY — how it's guaranteed
- The subscriber path's ONLY execution primitive is `_simulate_fill`, which is **pure** (builds a `PAPER-{uuid}` fill dict; no broker SDK, no network). It does **not** read or honour `strategy.is_paper` / `settings.strategy_paper_mode` for subscribers — subscribers are forced to paper regardless. A test sets BOTH flags live and asserts the result is still paper and `place_strategy_orders` (the live entry) is never called.

## Owner byte-identical — and WHY no subscriber positions are written
- When the flag is **False** (prod default) the whole block is skipped (one bool read). When True, the owner still dispatches first and unchanged.
- ⚠️ **Important design call:** M2 deliberately writes **NO** `StrategyPosition` / `StrategyExecution` rows for subscribers. Positions are keyed by `(strategy, symbol, side)` **ignoring `user_id`** (`_find_existing_open_position`), and `strategy_positions.broker_credential_id` is **NOT NULL**. So a subscriber paper position would *sum into the OWNER's live position* — inflating the owner's `remaining_quantity` and causing a real-money over-exit later. Correct per-subscriber positions need a per-subscriber scoping column (+ real creds + per-subscriber qty) — that's **Module 4** (which needs a migration, forbidden here). M2 therefore stays at the simulate-and-record layer: it proves the fan-out actually runs a paper execution per subscriber with **zero** risk to the owner. **No sacred file was modified** — `strategy_executor.py` (incl. `_simulate_fill`) is imported and reused, never edited; `direct_exit`/`kill_switch`/broker adapters/`strategy.py` model/migrations untouched.

## Per-subscriber isolation
- Each subscriber's simulation is wrapped in its own try/except: a failure is logged + recorded as `status="failed"` and the loop continues. One subscriber failing never stops the others or the owner (test (d) proves: `[filled, failed, filled]`, no exception escapes).

## Tests (all green)
- `tests/services/test_marketplace_fanout.py` (unit, no DB): N subscribers → N paper results each `paper=True` + `PAPER-` order id (b); paper even with live flags set + zero `place_strategy_orders` calls (c); one failing subscriber isolated, others proceed (d). Plus the M1 flag/call-site discipline tests.
- `tests/integration/test_marketplace_fanout_webhook.py` (real webhook): (a) flag OFF → `dispatch_subscriber_executions` never called, owner dispatches once; (b) flag ON + 2 active/1 cancelled → `_simulate_fill` called exactly 2× (cancelled excluded), owner dispatches once, **zero** live-entry calls, **zero** positions written; (c) resolve read-only/active-only.

## Verify (Module 2)
- `cd backend && .venv/bin/python -m pytest tests/services/test_marketplace_fanout.py tests/integration/test_marketplace_fanout_webhook.py tests/integration/test_strategy_webhook_async.py -q` → **23 passed**.
- Broad owner-path regression (executor paper-flag / qty / lifecycle / direct-exit / paper-gate / kill-switch / config + webhook suite): **89 passed**.
- `ruff check` clean on the new/changed module + test files. `strategy_webhook.py` has 6 **pre-existing** ruff findings (HEAD=6, after my change=6 — I introduced none and did not drive-by-fix them).

## Deliberately NOT done
- No real broker call / real order / live flag honoured for subscribers — paper only.
- No `StrategyPosition`/`StrategyExecution` writes for subscribers (see the design call above) — durable per-subscriber positions + real creds + per-subscriber qty are M4 (migration).
- No sacred file modified; no migration; no flag flip in prod (default stays False); no deploy, no merge to main.

---

# Marketplace Module 3 — subscription_id scoping (FIRST migration; additive/nullable)

**Goal:** add the scoping dimension that M2 was missing, so subscriber PAPER positions are ISOLATED from the owner's LIVE position, then persist them safely. **Migration created + validated locally only; NOT applied to prod.**

## 1. Migration (additive + nullable) — `migrations/versions/034_subscription_position_scoping.py`
Single new head off `033_strategy_state_audit`. Generated DDL (offline `alembic --sql`, both directions):
```sql
-- upgrade
ALTER TABLE strategy_positions  ADD COLUMN subscription_id UUID;          -- nullable
CREATE INDEX ix_strategy_positions_subscription_id  ON strategy_positions (subscription_id);
ALTER TABLE strategy_positions  ADD CONSTRAINT fk_strategy_positions_subscription_id  FOREIGN KEY(subscription_id) REFERENCES marketplace_subscriptions (id) ON DELETE CASCADE;
ALTER TABLE strategy_executions ADD COLUMN subscription_id UUID;          -- nullable
CREATE INDEX ix_strategy_executions_subscription_id ON strategy_executions (subscription_id);
ALTER TABLE strategy_executions ADD CONSTRAINT fk_strategy_executions_subscription_id FOREIGN KEY(subscription_id) REFERENCES marketplace_subscriptions (id) ON DELETE CASCADE;
-- downgrade drops both FKs, indexes, and columns.
```
- **Additive/nullable ONLY**: no existing column changed, no NOT-NULL, no data backfill. Every existing (owner) row keeps `subscription_id = NULL`. `ON DELETE CASCADE` so a subscriber row can never decay to NULL (which would bleed it into the owner's scope).
- ⚠️ **No local Postgres was running**, so per the repo's established pattern (its migration tests say "alembic upgrade runs against real Postgres in deployment, not the harness") I validated via: offline `--sql` (above), a structural migration test (`tests/db/test_subscription_scoping_migration.py` — nullable, chains off 033, additive+reversible source), and the integration tests which run against `create_all` with the new columns. **Migration NOT applied to prod.**

## 2. Owner-vs-subscriber position isolation (5 query files, each an additive `subscription_id IS NULL` filter)
The owner's open-position lookups key by `(strategy, symbol, side)` ignoring `user_id`, so each had to scope to NULL or a subscriber paper row would corrupt the owner:
| File | Lookup | Change |
|---|---|---|
| `strategy_executor.py` | `_find_existing_open_position` (owner entry-sum) | added optional `subscription_id` param (default None → `IS NULL`); owner caller unchanged → byte-identical. Subscriber path reuses it with its own id. |
| `direct_exit.py` | `get_open_position` (owner exit) | + `subscription_id IS NULL` |
| `position_lookup.py` | `find_open_position_by_strategy` (webhook exit-pin) | + `subscription_id IS NULL` |
| `position_manager.py` | loop poll | + `subscription_id IS NULL` — **so the loop NEVER manages a subscriber paper row** (which would otherwise fire a REAL exit on a LIVE strategy) |
| `reconciliation_loop.py` | drift poll | + `subscription_id IS NULL` — a subscriber paper row on a LIVE strategy would otherwise show as false `db_only` drift + CRITICAL alert |

Each is **behavior-preserving**: all existing owner rows are `subscription_id = NULL`, so every owner query matches *exactly* the rows it matched before the column existed. The 5 query diffs total **39 insertions / 2 deletions**. No live-order/broker code, no `kill_switch`, no `strategy.py` model touched.

## 3. Persist subscriber PAPER positions/executions — `dispatch_subscriber_executions`
For ENTRY signals, per subscriber (in its own **SAVEPOINT** for isolation) it now writes a `StrategyPosition` + `StrategyExecution` tagged with `subscription_id`, reusing the executor primitives (`_simulate_fill`, `_compute_levels`, `_resolve_side`, the now-scoped `_find_existing_open_position`). Subscriber re-entries sum **only within their own scope**. `broker_credential_id` reuses the owner strategy's as a paper placeholder (no broker is ever built/called). Non-entry (exit) actions are log-only — subscriber exit routing is M4.

## Proven (tests)
- **Owner byte-identical:** with an owner row AND a subscriber row on the same `(strategy, NIFTY, buy)`, `_find_existing_open_position` (owner) and `get_open_position` both return the OWNER row (NULL scope), never the subscriber; the scoped lookup returns the subscriber row.
- **3-way isolation, no bleed:** owner(10) + 2 subscribers, dispatched twice → 3 isolated rows; owner stays at 10; each subscriber sums to 2 within its own scope.
- **PAPER ONLY:** zero `place_strategy_orders`/broker calls even with the strategy flipped LIVE (`is_paper=False`); all subscriber fills are `PAPER-…`.
- **Persist + webhook:** flag on → one isolated paper position+execution per active subscriber (cancelled excluded), owner dispatches once, no live calls.

## Verify (Module 3)
- `cd backend && .venv/bin/python -m pytest tests/services/test_marketplace_fanout.py tests/db/test_subscription_scoping_migration.py tests/integration/test_marketplace_fanout_webhook.py tests/integration/test_strategy_webhook_async.py -q` → **27 passed**.
- **Owner regression across all 5 touched query files: 225 passed.** The 16 local failures (test_live_order_flow / reconciliation drift / product_type) are **PRE-EXISTING** — I ran the SAME suspect tests on the pre-M3 baseline (git stash) and got the identical 16 failures (they need Postgres locally). So M3 introduced **zero** new failures.
- `ruff` clean on new/changed files. The 5 sacred query files: HEAD vs now error counts are equal (14=14, 6=6, 0=0, 0=0, 2=2) — I introduced no new lint debt and did not drive-by-fix theirs.

## Deliberately NOT done
- Migration NOT applied to prod (validated locally/offline only); no flag flip (default stays False).
- Subscriber EXIT-signal routing + real per-subscriber creds/qty = Module 4. `kill_switch` left untouched (owner kill switch is naturally isolated by `user_id`; a subscriber's own kill switch never fires in M3 — noted for M4).
- No deploy, no merge to main.

---

# Marketplace Module 4 — subscription execution fields + per-subscriber qty (PAPER)

**Goal:** give each subscriber their OWN size, and build (but NOT use for real orders) per-subscriber broker-credential resolution. Still PAPER ONLY. **Migration validated locally only; NOT applied to prod.**

## 1. Migration `035` (additive, off 034) — `migrations/versions/035_subscription_execution_fields.py`
Single new head off `034`. Generated DDL (offline `alembic --sql`, both directions verified):
```sql
-- upgrade (marketplace_subscriptions ONLY)
ADD COLUMN lots_override        INTEGER;                         -- nullable
ADD COLUMN execution_mode       VARCHAR(16) DEFAULT 'auto' NOT NULL;
ADD COLUMN is_paper             BOOLEAN     DEFAULT true   NOT NULL;
ADD COLUMN direction_filter     VARCHAR(8)  DEFAULT 'all'  NOT NULL;
ADD COLUMN broker_credential_id UUID;                            -- nullable, FK -> broker_credentials (SET NULL)
+ index on broker_credential_id
+ CHECK ck_marketplace_subscriptions_execution_mode_valid   (execution_mode IN ('auto','one_click','offline'))
+ CHECK ck_marketplace_subscriptions_direction_filter_valid (direction_filter IN ('all','long','short'))
-- downgrade drops all of the above (create==drop constraint names verified).
```
- **Additive ONLY**, on `marketplace_subscriptions` ONLY. No existing column changed, no backfill, no NOT-NULL-without-default. The three NOT-NULL columns ship safe server-defaults so existing rows fill automatically. (Fixed a naming-convention gotcha: short logical CHECK names so create==drop match cleanly, mirroring migration 032.)
- ⚠️ No local Postgres available — validated via offline `--sql` (both directions), the structural migration test, and the `create_all`-backed integration tests, per the repo's established pattern. **NOT applied to prod.**

## 2. Per-subscriber size — `dispatch_subscriber_executions`
Each subscriber's paper position is now sized by **`subscription.lots_override` when set, else the strategy default** (paper `lot_size=1`). `SubscriberRef` was extended to carry the 5 new fields (`lots_override`, `execution_mode`, `is_paper`, `direction_filter`, `broker_credential_id`), populated by `resolve_active_subscriptions`.

## 3. Per-subscriber credential resolution (machinery only) — `resolve_subscriber_credential(subscriber, db)`
New pure-SELECT resolver + `SubscriberCredentialResolution` result. Order: **explicit** (the subscriber's chosen active cred) → **fallback** (their most-recent active cred) → **none** (`usable=False`, the missing-credential flag).
- ⚠️ **RESOLVED + validated but NEVER used.** It never builds a broker, calls a broker, decrypts a credential, or places an order. `dispatch_subscriber_executions` calls it per subscriber and **records** the result (`resolved_credential_id` + `credential_source`) in the execution's `broker_response`, the logs, and the `PaperExecutionResult` — but the position/execution FK stays the **owner's strategy credential (paper placeholder)**. Wiring the resolved cred to a real order is a later, separately-gated phase.

## 4. execution_mode / direction_filter / is_paper — carried, NOT branched on
All three are stored + carried on `SubscriberRef` but the fan-out does **not** branch on them: paper always simulates regardless of mode, and subscribers are forced to paper regardless of `subscription.is_paper`.

## Proven (tests)
- **Owner byte-identical:** owner qty logic untouched (the executor's qty resolver was not modified); the lots_override test seeds an owner position (qty 10) and confirms it stays 10 while subscribers get their own sizes. Owner regression: **68 passed**.
- **Per-subscriber size:** two subscribers with `lots_override=[2, 5]` → isolated paper positions of remaining_quantity 2 and 5; owner unchanged at 10; 3 distinct rows.
- **Credential resolution:** explicit → the chosen cred; no-explicit-but-has-cred → fallback; no cred → `usable=False, source='none'`; and the resolver places **zero** real orders (`place_strategy_orders` spy stays empty).
- **PAPER ONLY / zero broker:** the M3 "zero real-broker even when strategy is LIVE" test still passes.

## Verify (Module 4)
- `cd backend && .venv/bin/python -m pytest tests/services/test_marketplace_fanout.py tests/db/test_subscription_execution_fields_migration.py tests/db/test_subscription_scoping_migration.py tests/integration/test_marketplace_fanout_webhook.py tests/integration/test_strategy_webhook_async.py -q` → **32 passed**.
- Owner regression (direct-exit / position-loop / lifecycle / pine-qty / paper-flag / kill-switch / config): **68 passed**.
- `tests/strategy_engine/api/test_marketplace.py`: 2 passed / 24 errors — **PRE-EXISTING** (JSONB-on-SQLite harness issue in that file; identical on the pre-M4 baseline via git stash). M4 introduced zero new failures.
- `ruff` clean on all M4 changed/new files. M4 touched **no** owner-path file (only the subscription model + `marketplace_fanout` + migration).

## Deliberately NOT done
- Per-subscriber credential is resolved + recorded but NEVER used to build/call a broker or place a real order. No `execution_mode`/`direction_filter`/`is_paper` branching. PAPER ONLY.
- No live-order/`direct_exit`-live/`kill_switch`/broker-adapter code touched. Migration NOT applied to prod; no flag flip (default stays False); no deploy, no merge to main.

---

# Marketplace Module 5 — partial-failure hardening + subscriber-aware idempotency (Phase 1 complete, PAPER)

**Goal:** make the paper fan-out robust — duplicate signals don't double-execute per subscriber, and any single subscriber's failure is contained, logged, and alerted without touching the owner or other subscribers. **NO migration** (reused the existing Redis idempotency + existing fields).

## What changed (2 source files + tests — no migration, no sacred file)
1. **`backend/app/services/marketplace_fanout.py`**
   - **Subscriber-aware idempotency:** before persisting an ENTRY, each subscriber claims `{subscription_id}:{signal_hash}` via the EXISTING `redis_client.set_idempotency_key` (SET NX). Distinct from the owner key `{signal_hash}` (= `user_id:digest`, claimed unchanged by the webhook). A duplicate → `status="duplicate"`, no second paper position/execution. **Fail-open**: a Redis outage is treated as first-time so it never blocks dispatch. (`signal_token` falls back to `signal.id` when no hash is threaded.)
   - **Partial-failure hardening:** each subscriber already runs in its own SAVEPOINT (M3); a failure is caught, logged structured (`fanout.paper.subscriber_failed`), recorded as `status="failed"` with the reason, and the others + owner proceed. The returned `list[PaperExecutionResult]` IS the per-subscriber summary (`status` ∈ `{filled, duplicate, failed}`); the summary log now counts all three.
   - **Failure alerting:** on a subscriber failure, best-effort `_alert_subscriber_failure` emits a WARNING via the EXISTING `telegram_alerts.send_alert` (the operator channel signal_execution already uses). Wrapped so an alert failure can never break dispatch.
2. **`backend/app/api/strategy_webhook.py`** — one additive kwarg: `dispatch_subscriber_executions(..., signal_hash=signal_hash)` inside the already-flag-gated block. The owner idempotency claim (`set_idempotency_key(signal_hash)`) is **byte-identical** — unchanged.

## Owner byte-identical — confirmation
- The webhook diff is a single additive kwarg inside the `if marketplace_fanout_enabled:` block. The owner key/claim/behavior is unchanged. Flag OFF (default) → the block is skipped entirely.
- **No sacred/owner-exec file touched** (no `strategy_executor`/`direct_exit`/`kill_switch`/`position_manager`/`position_lookup`/`reconciliation_loop`/broker adapters). **No migration.**

## Proven (tests)
- **(a) idempotent:** same `signal_hash` dispatched twice for a subscriber → first `filled`, second `duplicate`; exactly ONE paper position + ONE execution (remaining_quantity stays 1, not doubled). (The M3 re-entry-summing test was updated to use DISTINCT signal hashes — two different signals correctly sum; identical ones correctly dedupe.)
- **(b) mixed `[ok, fail, ok]`:** 2 filled + 1 failed; the failed subscriber's row rolled back; owner UNCHANGED at 10; the 2 ok subscribers persisted; the failure was **alerted** via the existing service (WARNING); zero live-order calls.
- **(c) keys per-subscription + distinct:** each subscription's `{subscription_id}:{hash}` key is claimed; dispatch does NOT touch the owner key `{hash}`.
- **(d) zero real-broker:** the M3 "zero broker even when LIVE" test still passes; (b) also asserts `place_strategy_orders` is never called.
- **(e) owner byte-identical:** owner webhook regression suite + 85 owner-path tests pass.

## Verify (Module 5)
- `cd backend && .venv/bin/python -m pytest tests/services/test_marketplace_fanout.py tests/integration/test_marketplace_fanout_webhook.py tests/integration/test_strategy_webhook_async.py -q` → **28 passed**.
- Owner regression (kill-switch / exit-reresolve / direct-exit / paper-gate / lifecycle / pine-qty / paper-flag / both subscription migrations / config): **85 passed**.
- `ruff` clean on changed files; `strategy_webhook.py` HEAD vs now = 6 = 6 (no new lint; the 6 are pre-existing).

## Deliberately NOT done
- No migration (reused existing Redis idempotency + fields). PAPER ONLY — no real broker calls under any config; subscriber EXIT routing + real orders remain a later gated phase.
- No flag flip (default stays False); no deploy, no merge to main. **Phase 1 (PAPER fan-out: M0–M5) is complete on this branch.**

---

# Phase 1 CLOSEOUT — real-Postgres migrations + end-to-end paper validation (LOCAL ONLY)

Ran the migrations on a **real local Postgres 16** (throwaway `docker-compose-test.yml` stack: PG `:5433`, Redis `:6380`) and drove the **real webhook** end-to-end with the flag ON. **Local only — prod (alembic 033) was never touched, nothing deployed, nothing merged. The local DB + volumes were torn down afterward.**

## 🐞 Bug the closeout caught + fixed (offline `--sql` could NOT catch this)
- `alembic upgrade 033→034` **FAILED on real PG**: `asyncpg StringDataRightTruncationError: value too long for type character varying(32)`.
- Root cause: the revision IDs `034_subscription_position_scoping` and `035_subscription_execution_fields` are **33 chars**, but alembic's `alembic_version.version_num` is **VARCHAR(32)**. Offline `--sql` never stamps the version table, so it passed; the real DB stamp overflowed. (All IDs ≤033 are ≤32 chars.)
- **Fix (this commit):** shortened the revision IDs to `034_subscription_scoping` (24) and `035_subscription_exec_fields` (28). Filenames + test import paths unchanged; only the `revision`/`down_revision` strings + the test assertions changed. This is the kind of defect the closeout exists to find.

## 1. Migrations on real Postgres — ✅ clean apply / revert / re-apply
- Clean DB → `alembic upgrade 033` ran 001→033 with **no errors** (incl. migration 027, which an old note worried about — fine on PG 16).
- `033→034→035` applied cleanly; `035→034→033` **downgraded cleanly** (reversible); re-`upgrade head` returned to `035`. Single head `035_subscription_exec_fields`.
- Final schema verified on PG: `strategy_positions.subscription_id` + `strategy_executions.subscription_id` = `uuid NULLABLE`; `marketplace_subscriptions`: `lots_override int NULL`, `execution_mode varchar NOT NULL default 'auto'`, `is_paper bool NOT NULL default true`, `direction_filter varchar NOT NULL default 'all'`, `broker_credential_id uuid NULL`; + 2 CHECK + 3 FK constraints present.

## 2–4. End-to-end PAPER fan-out (real PG + real Redis, flag ON, paper) — ✅ everything proven
Driven via FastAPI TestClient (real ASGI POST) against the migrated PG + real Redis. Seed: 1 owner strategy (is_paper) + a published listing + a **pre-seeded owner NIFTY position (qty 10)** + 3 active subscriptions: subA `lots_override=2` (own cred), subB `=5` (own cred), subC `=3` (**no credential**).

| Step | Result |
|---|---|
| **ENTRY** (NIFTY) | HTTP 202; owner dispatched; 3 subscribers **filled** with their OWN sizes — subA=2, subB=5, subC=3. subC `credential_source="none"` (missing cred recorded, **still paper, no real order**). |
| **DUPLICATE** (same body) | HTTP `200 "duplicate signal suppressed"`; subscribers **not** re-dispatched (owner idempotency caught it) → **no double**. |
| **EXIT** (NIFTY) | HTTP 202; owner exit dispatched. (Subscriber EXIT routing is a later phase — non-entry actions are log-only.) |
| **FAILURE** (BANKNIFTY, subC sim injected to raise) | subC → **`failed`** (no position) + **`WARNING` operator alert sent** (existing `telegram_alerts`); subA=2, subB=5 **filled**; owner + the 2 ok subs unaffected. |
| **Owner isolation** | Final NIFTY: OWNER row `subscription_id NULL`, **still 10/10 (UNCHANGED — no bleed)** alongside 3 distinct subscriber rows. `owner_positions_NULL_scope=1`. |
| **Zero broker** | `_live_place_order=[]`, `broker_built=[]` — **zero real-broker calls** the whole run. |

Honest caveat: the owner **Celery worker** was NOT run in-process — running it eagerly inside TestClient offloads to `async_bridge`'s separate loop and would use the app's asyncpg engine across event loops (the integration suite sidesteps this with SQLite). So the owner *dispatch* + *idempotency* + *isolation* were validated on real PG, while the owner *execution* itself (place_strategy_orders) is unchanged and covered by the owner regression suite. The **subscriber fan-out — the new Phase-1 code — ran for real on asyncpg** throughout.

## Verify (post-fix, sqlite harness)
- `cd backend && .venv/bin/python -m pytest tests/db/test_subscription_scoping_migration.py tests/db/test_subscription_execution_fields_migration.py tests/services/test_marketplace_fanout.py tests/integration/test_marketplace_fanout_webhook.py -q` → **22 passed** (revision-id rename consistent).

## Teardown
- `docker compose -f docker-compose-test.yml down -v` — containers + volumes removed; `:5433` closed. Throwaway e2e script + env overrides deleted. Prod untouched; nothing deployed/merged.

---

# BUGFIX — owner view leaked subscriber (fan-out) rows (display-only, latent)

**What was wrong:** the two customer-facing READ endpoints did not filter
`subscription_id`, so once `MARKETPLACE_FANOUT_ENABLED` flips, subscriber paper
rows (non-NULL `subscription_id`) would surface in a user's OWN view:
- `GET /api/strategies/executions` (`strategy_signals.py`) joined `StrategySignal
  WHERE user_id == current_user` only. Subscriber executions link to the OWNER's
  signal → they'd appear in the OWNER's trades view (pollution).
- `GET /api/strategies/positions` (`strategy_positions.py`) filtered `user_id ==
  current_user` only, and `StrategyPositionRead` has no `subscription_id` field →
  a subscriber's own paper positions (user_id = subscriber) would show UNLABELED.

**Fix (additive, read-path only):** both endpoints now add `subscription_id IS
NULL`, scoping each to the user's OWN (owner) rows. This mirrors the internal
owner lookups (entry-sum / exit / position-loop / reconciliation), which ALREADY
filter `subscription_id IS NULL` — those were **not** touched.

## Endpoints fixed
| Endpoint | File | Change |
|---|---|---|
| `GET /api/strategies/executions` | `app/api/strategy_signals.py` (`list_executions`) | `+ StrategyExecution.subscription_id.is_(None)` in the WHERE |
| `GET /api/strategies/positions`  | `app/api/strategy_positions.py` (`list_positions`)  | `+ StrategyPosition.subscription_id.is_(None)` in the WHERE |

## Guarantees
- **Owner view = NULL-scoped, no leak.** With subscriber rows present, both
  endpoints return ONLY `subscription_id IS NULL` rows (proven).
- **Behaviour-preserving for the owner.** With NO subscriber rows (today, flag
  OFF), every owner row is still returned — the filter drops nothing (proven).
- **Internal lookups untouched.** `git diff` touches ONLY the two read endpoint
  files (+ the new test). No change to `strategy_executor` / `direct_exit` /
  `kill_switch` / `webhook` / brokers / `position_lookup` / `position_manager` /
  `reconciliation_loop` / migrations. Display-only; no execution / live-order
  logic changed. Per-subscription SUBSCRIBER views remain a separate, additive
  endpoint for later (out of scope here).

## Verify (local)
- `cd backend && .venv/bin/python -m pytest tests/test_owner_view_subscription_isolation.py -q`
  → **4 passed** — (a) positions + executions exclude subscriber rows; (b) both
  unchanged with no subscriber rows.
- Regression: `test_paywall_gated_endpoints` + the fan-out suite + isolation →
  **37 passed** together. `ruff` clean on the changed files; `mypy` adds no new
  error (the lone `rowcount` note in `strategy_positions.py` is **pre-existing**
  on HEAD, in the untouched kill-switch code).
- NOT deployed, NOT merged to main.

# ============================================================
# TRACK B — Razorpay billing (feat/razorpay-billing)
# ============================================================

# NOTES FOR JAYESH — Razorpay billing (Phase 2)

**Branch:** `feat/razorpay-billing` (off `main` @ 730ce91). Pushed. **NOT merged to main, NOT deployed.**
(This NOTES file did not exist on `main`; it's a fresh one for the Razorpay track. The marketplace-fanout NOTES live on that branch.)

---

# Phase 2 (Razorpay), Module 1 — recurring core + platform-plan flow

**Goal:** wire Razorpay recurring subscriptions to the EXISTING entitlement layer (B1–B3) — the verified, idempotent webhook drives `users.plan_status` / `active_plan_id` / `plan_expires_at`. Payment-only. **No trading code touched. `paywall_enforced` stays False (building billing ≠ enforcing).**

## Endpoints (all NEW, under `/api/billing`)
| Method + path | Auth | Purpose |
|---|---|---|
| `POST /api/billing/subscribe` | user | Create a Razorpay recurring Subscription for the caller + a plan; persist the row; returns `{razorpay_subscription_id, razorpay_key_id (PUBLIC), status, short_url, plan_tier, amount_inr}` for the frontend checkout. |
| `POST /api/billing/webhook/razorpay` | public (Razorpay) | **Verifies `X-Razorpay-Signature` HMAC FIRST**, then idempotently applies the event. Invalid signature → 400, grants nothing. |
| `POST /api/billing/admin/sync-plans` | admin | Map each active plan tier → a Razorpay Plan (create-if-absent, no duplicates). |

## Webhook events handled → entitlement transition (REUSES the B2 fields)
| Razorpay event | `users.plan_status` | also sets |
|---|---|---|
| `subscription.activated` / `subscription.charged` | `active` | `active_plan_id` = plan, `plan_expires_at` = `current_end` |
| `subscription.halted` | `expired` | — |
| `subscription.cancelled` | `cancelled` | — |
| `subscription.completed` | `expired` | — |
Every event is logged (`razorpay.webhook.*`) and writes an `audit_logs` row (ActorType.SYSTEM), mirroring `admin.set_user_plan`. `plan_is_active()` (the paywall predicate) is reused unchanged.

## Env vars needed (secrets via ENV only, default EMPTY — nothing hardcoded/committed)
- `RAZORPAY_KEY_ID` — API key id (also the PUBLIC id the frontend checkout uses).
- `RAZORPAY_KEY_SECRET` — API secret (server-only; never returned/logged).
- `RAZORPAY_WEBHOOK_SECRET` — webhook signing secret. **Empty → every webhook is rejected (fail-closed).**
Use Razorpay **TEST** keys in dev; never live keys in code/tests.

## Security + correctness guarantees
- **Signature-verified:** `razorpay_webhook` calls `verify_webhook_signature(raw_body, X-Razorpay-Signature, RAZORPAY_WEBHOOK_SECRET)` BEFORE touching the body. This reuses the platform's existing constant-time `app.core.security.verify_hmac_signature` (Razorpay signs the exact body with HMAC-SHA256 hex — same scheme). A spoofed/unverified webhook can NEVER grant a plan; an empty secret rejects everything.
- **Idempotent:** durable `razorpay_webhook_events` table with a UNIQUE `event_id` (the `X-Razorpay-Event-Id` header, else a derived `{event}:{entity}:{created_at}` hash). A duplicate delivery dedupes → the entitlement effect happens **exactly once** (proven: a duplicate `event_id` carrying a `cancelled` body does NOT override the prior `active`).
- **Entitlement-reused:** the webhook writes ONLY the B2 triple via `_apply_entitlement` — same fields `plan_is_active` reads. Plan/status logic is NOT rebuilt.
- **No trading code touched:** confirmed `strategy_webhook`/`executor`/`direct_exit`/`kill_switch`/`brokers`/`marketplace_fanout`/`position*`/`reconciliation` are absent from the diff.
- **`paywall_enforced` unchanged** (default False) — billing is built, not enforced.

## Data (migration 034_razorpay_billing — additive, off main's head 033)
- NEW `razorpay_payments` (user_id, plan_id, razorpay_order_id, razorpay_subscription_id, razorpay_payment_id, status, amount_inr, notes, created_at) — the durable `sub_… → user+plan` link.
- NEW `razorpay_webhook_events` (UNIQUE event_id) — idempotency ledger.
- ADD `users.razorpay_subscription_id` (nullable) + `subscription_plans.razorpay_plan_id` (nullable, create-if-absent map).
- Changes no existing column, no backfill. Reversible.
- ⚠️ **Revision-id note:** both this branch and `feat/marketplace-fanout` fork off 033, so each has a "034". This one is `034_razorpay_billing` (distinct id from the marketplace `034_subscription_scoping`); when both land on main, a single alembic **merge revision** will join the two heads. Kept ≤32 chars (alembic_version VARCHAR(32) — lesson from the marketplace closeout).

## Verify (done locally)
- **Migration on REAL local Postgres 16** (docker `:5433`): clean `033→034_razorpay_billing`, clean downgrade `034→033`, clean re-upgrade to head. Schema confirmed: both tables + the UNIQUE `event_id` + the two nullable handle columns. Local DB torn down. **NOT run on prod (prod stays at 033).**
- **Tests (MOCKED Razorpay, no live calls):** `cd backend && .venv/bin/python -m pytest tests/integration/test_razorpay_billing.py -q` → **5 passed** — subscription creation persists + returns the handle (plan create-if-absent); signature valid passes / invalid rejected; webhook endpoint bad-sig → 400 grants nothing, good-sig → 200 applies; duplicate event_id = single effect; `charged→active` / `cancelled→cancelled` reuse `plan_is_active`.
- `ruff` clean on all new files. (`main.py` carries a pre-existing I001 unchanged — HEAD=1, now=1.) Entitlement/config regression unaffected.

## Deliberately NOT done (follow-ups)
- **Sandbox end-to-end** (real Razorpay test-mode order → checkout → real webhook) — pending once `RAZORPAY_*` TEST keys are in the env. The SDK call layer is mocked in tests; the live path is wired but unexercised against Razorpay.
- The frontend checkout wiring (open Razorpay checkout.js with `razorpay_subscription_id` + `razorpay_key_id`) — a later module.
- `paywall_enforced` flip — separate, deliberate decision.
- No deploy, no merge to main.

---

# Phase 2 (Razorpay), Module 2 — marketplace per-strategy recurring subscription

**Goal:** replace the marketplace **stub** subscribe with a real Razorpay recurring subscription, REUSING M1's client + the ONE signature-verified idempotent webhook. The paid, **active** `marketplace_subscription` is the row the Phase-1 fan-out spine routes signals to — but **paying ≠ real trading yet**: fan-out stays disabled and execution stays PAPER (real-money subscriber execution is a later phase, post-empanelment).

## What changed
| Endpoint | Before (stub) | After (M2) |
|---|---|---|
| `POST /api/marketplace/listings/{id}/subscribe` | Always wrote an **active** sub with `amount_paid_inr = price`, as if paid. | **Paid listing + Razorpay configured** → creates a recurring Razorpay Subscription, persists a **`pending`** sub (+ a `razorpay_payments` row, `kind=marketplace`), returns the **checkout handle**. NOT active until the webhook confirms the charge. **Free listing OR gateway unconfigured** → unchanged stub path (immediate `active`, ₹0/price). |

The webhook is **the same** `POST /api/billing/webhook/razorpay` from M1 — NOT a second webhook. It now routes by `razorpay_payments.kind`:
| `kind` | Webhook effect |
|---|---|
| `platform_plan` (M1) | drives `users.plan_status` (entitlement) — unchanged |
| `marketplace` (M2) | flips the linked `marketplace_subscriptions` row: `charged`/`activated` → `active` (+ `access_until`, + `amount_paid_inr`, + `subscriber_count`++); `cancelled` → `cancelled`; `halted`/`completed` → `expired` |

A marketplace charge writes **only** the subscription's status/access fields + an `audit_logs` row (ActorType.SYSTEM, `resource_type=marketplace_subscription`). It does **not** touch `users.plan_status` — the two kinds are cleanly separated.

## Data (migration `035_razorpay_marketplace` — additive, off this branch's head `034_razorpay_billing`)
- ADD `razorpay_payments.kind` (NOT NULL, default `'platform_plan'`) — the webhook discriminator. Existing M1 rows correctly become `platform_plan`.
- ADD `razorpay_payments.marketplace_subscription_id` (nullable FK → SET NULL) — the durable `sub_… → marketplace_subscription` link.
- ADD `marketplace_subscriptions.razorpay_subscription_id` (nullable, indexed) — the recurring handle on the sub.
- ADD `marketplace_listings.razorpay_plan_id` (nullable) — create-if-absent Razorpay Plan per listing price (no duplicate plans).
- EXPAND the `marketplace_subscriptions` status CHECK to add `'pending'` (drop+recreate `ck_marketplace_subscriptions_status_valid`; purely additive to the allowed set — existing rows stay valid).
- Changes no existing column type, no backfill. Reversible (downgrade restores the original 3-value CHECK; it refuses if `'pending'` rows remain — clear them first).
- ⚠️ **Revision-id note:** like 034, this forks off 033 in parallel with `feat/marketplace-fanout`; a single alembic **merge revision** joins the heads when both land on main. Kept ≤32 chars (`035_razorpay_marketplace` = 24).

## Security + correctness guarantees
- **ONE signature-verified webhook:** marketplace events flow through the SAME `razorpay_webhook` endpoint, which verifies `X-Razorpay-Signature` BEFORE anything (bad sig → 400, grants nothing) and dedupes on the durable `event_id` ledger. No second webhook, no duplicated signature logic. Proven: a bad-sig delivery leaves the sub `pending`; a good-sig one activates it.
- **Idempotent:** a duplicate `event_id` has a SINGLE effect — `subscriber_count` is incremented exactly once across two `charged` deliveries.
- **Paying ≠ real trading (asserted):** a paid, **active** marketplace subscription triggers **zero broker calls** — a test installs recorders on `DhanBroker.place_order` + `FyersBroker.place_order` and asserts they never fire across subscribe + activate; `paywall_enforced` stays **False** and there is no `marketplace_fanout_enabled` on this branch. The fan-out execution spine lives on `feat/marketplace-fanout`, not here.
- **No trading code touched:** diff is the marketplace router + the Razorpay service/models/migration + tests only. `strategy_webhook`/`executor`/`direct_exit`/`kill_switch`/`brokers`/`positions` are NOT in the diff.
- **Secrets via ENV only** (`RAZORPAY_*`, default empty); mocked tests, no live calls; the PUBLIC key id only is returned for checkout.

## Verify (done locally)
- **Migration on REAL local Postgres 16** (docker `:5433`): clean `034→035`, clean downgrade `035→034` (CHECK reverts to the 3-value set), clean re-upgrade to head. Confirmed: `kind` default `platform_plan`, the two FK/handle columns, the listing plan column, and the widened `pending` CHECK. Single alembic head. Local DB torn down.
- **Tests (MOCKED Razorpay, no live calls):** `cd backend && .venv/bin/python -m pytest tests/integration/test_razorpay_marketplace.py -q` → **6 passed** — pending-not-active + Razorpay sub; charged→active (platform entitlement untouched); cancelled→cancelled; idempotent single-count; shared-webhook signature gate; zero-broker-calls.
- **No regression:** the existing marketplace suite (`test_marketplace.py`, 26 tests — they fall to the stub path since Razorpay is unconfigured) + M1 billing (5) all still pass: **37 passed** together.
- `ruff check` clean on all changed files. `mypy` clean on the new code (one **pre-existing** `no-any-return` in M1's `sync_plan_to_razorpay` remains — verified present at HEAD, untouched). The 19 failing local integration tests (`live_order_flow`, `reconciliation_loop`, webhook-HMAC, telegram) are **pre-existing** — verified identical at HEAD with my changes stashed (local-harness gaps: HMAC defaults off, Postgres-needed paths).

## Deliberately NOT done (follow-ups)
- **Sandbox end-to-end** against real Razorpay test-mode — same as M1, pending `RAZORPAY_*` TEST keys in env.
- **Frontend checkout** for the marketplace handle (`requires_payment=true` → open checkout.js). → done in M3.
- **Fan-out activation / real subscriber execution** — deliberately OUT (Phase 3, post-empanelment). A paid sub is access-only today.
- No `paywall_enforced` flip, no deploy, no merge to main.

---

# Phase 2 (Razorpay), Module 3 — checkout UI + per-subscriber sizing/execution-mode UI

**Goal:** wire the real Razorpay checkout into the frontend (marketplace subscribe + pricing upgrade) and let a subscriber set their per-subscription size + execution mode. FRONTEND-focused (+ two tiny non-sacred read/write endpoints). No trading/executor/broker/fan-out code touched.

## What changed (frontend)
| Area | Before | After (M3) |
|---|---|---|
| Marketplace **subscribe** (`subscribe-button.tsx`) | Paid → "Payment integration coming soon / Phase 4 stub" modal that recorded a fake `amount_paid_inr`. | Paid → calls the backend subscribe endpoint → opens **Razorpay Checkout** (checkout.js from Razorpay's CDN) with the PUBLIC `razorpay_key_id` + `subscription_id`. Shows **"payment processing"** and **polls** `GET /marketplace/subscriptions/me` until the (webhook-driven) status flips `active`. Free → direct subscribe (unchanged). The stub modal is deleted. |
| **Pricing** page CTA (`plan-checkout-button.tsx`) | "Start Free Trial" → `/register` for everyone. | Guests still get the register link; **logged-in** users get "Upgrade to {plan}" → `POST /api/billing/subscribe` → Razorpay Checkout → poll `GET /api/billing/me` until `is_active`. |
| **My subscriptions** (`/marketplace/me`) | Active/Past only; "(stub)" amount copy. | Adds a **Processing payment** group for `pending` subs + a per-subscription **Settings** panel (sizing + execution mode) on active/pending rows; removed the "(stub)" copy. |
| Honest copy | "Real Razorpay … Phase 4 mein lagega", "stub mode", "actual payment Phase 4 mein launch hoga" (subscribe modal + FAQ). | Removed. New copy: checkout is live; **execution stays paper (simulated) until live trading is enabled (Phase 3 / empanelment)**; "past performance does not guarantee future results"; no guaranteed returns. (The remaining "Phase 4" string is the on-chain ledger roadmap, not payments.) |

New shared libs: `src/lib/billing/razorpay.ts` (lazy checkout.js loader + `openSubscriptionCheckout`) and `src/lib/billing/subscription-settings.ts` (`validateLotsOverride`, `EXECUTION_MODES`, types). New components: `marketplace/subscription-settings.tsx`, `billing/plan-checkout-button.tsx`.

## Backend (two tiny, non-sacred endpoints — no trading code)
- `GET /api/billing/me` — read-only `{plan_status, is_active, plan_tier, plan_expires_at}` for post-checkout **polling** of the platform plan. Reuses the existing entitlement fields + `plan_is_active`.
- `GET` + `PATCH /api/marketplace/subscriptions/{id}/settings` — per-subscriber `{lots_override, execution_mode, is_paper}`. Owner-scoped (404 otherwise). Validates the **even / 2-20** sizing rule and the `auto|one_click|offline|paper` enum server-side. **Persists only when the fan-out columns exist** (see flag below) — otherwise validated-but-not-persisted with `applied=false`.

## Confirmations (the guardrails)
- **PUBLIC key only on the frontend.** Checkout uses `razorpay_key_id` (the public id the backend returns). The key SECRET and webhook secret never leave the server / never appear in frontend code. checkout.js is loaded from `https://checkout.razorpay.com/v1/checkout.js`.
- **Webhook-driven activation.** The frontend NEVER marks anything active. After checkout it shows "processing" and polls the backend; it reflects `active` only when the backend (driven by the M1/M2 signature-verified webhook) says so. On dismiss/failure it surfaces a graceful message + a Resume path.
- **Sizing validation = even, minimum 2 (4/6/8…), max 20.** Enforced in the UI (`validateLotsOverride`, live error + disabled Save) AND server-side (Pydantic `ge=2/le=20` + an even-number field validator → 422). Unit-tested.
- **Paper is the default + the only live mode.** `execution_mode` defaults to `paper`, `is_paper` defaults true; auto/one-click/offline render as labelled previews with a "activates when live trading is enabled (Phase 3)" note. No real-execution path is reachable from this UI.
- **No trading code touched.** Diff is the marketplace router (settings endpoints) + billing router (`/me`) + frontend components/pages + tests. No executor/broker/direct_exit/kill_switch/fan-out/positions.

## ⚠️ DEPENDENCY ON `feat/marketplace-fanout` (must merge for settings to persist)
The per-subscriber execution-settings COLUMNS — `marketplace_subscriptions.lots_override` / `execution_mode` / `is_paper` — are added by the fan-out track (M4) on `feat/marketplace-fanout`, **not on this branch**. So on `feat/razorpay-billing` the settings PATCH **validates but does NOT persist**: it returns `applied=false`, `pending_fanout_merge=true`, and the UI shows a paper-only **preview**. The endpoint is column-guarded (`hasattr`) so the moment the two branches converge on main (with the fan-out columns present), the same endpoint **persists automatically** — no further code change. This is the forward contract; flag it at merge time.

## Verify (done locally)
- **Frontend tests (vitest, mocked api + razorpay):** `cd frontend && npx vitest run tests/marketplace/subscribe-button.test.tsx tests/billing/subscription-settings.test.tsx` → **15 passed** — free vs paid subscribe, checkout opened with the PUBLIC key + sub id, gateway-unconfigured fallback, pending/active resting states; `validateLotsOverride` even/min-2/max-20; settings PATCH validation + preview toast.
- **Backend tests:** `tests/integration/test_billing_me_and_settings.py` → **8 passed** — billing/me reflects entitlement; settings PATCH rejects odd/below-min/bad-mode (422), accepts even (200, `applied=false`/`pending_fanout_merge=true`), GET defaults to paper, non-owned 404. M2 marketplace + razorpay regression: **45 passed** together.
- **Lint/types:** `npx tsc --noEmit` clean on all changed files (pre-existing errors remain only in `tests/chart`, `tests/strategies`, and a generated `.next` validator — unrelated). `eslint` clean on changed files. Backend `ruff` + `mypy` clean on `billing.py` + `marketplace.py`.

## Deliberately NOT done (M3 follow-ups)
- **Sandbox end-to-end** (real Razorpay test-mode checkout → real webhook) — pending `RAZORPAY_*` TEST keys in the env (the SDK + checkout.js are mocked in tests).
- **Persisting per-subscriber settings** — blocked on the fan-out-branch columns (see flag above); the UI + endpoint are ready.
- No deploy, no merge to main, no `paywall_enforced` flip.

---

# Phase 2 (Razorpay), Module 4 — payment lifecycle robustness (completes Phase 2)

**Goal:** harden the money lifecycle so billing state and access never silently diverge — cancellation, payment failure/dunning, plan change, and gateway↔DB reconciliation. Payment + entitlement/subscription-status only; **no trading code touched**.

## Events + endpoints added
| Razorpay event | effect (platform `plan_status` / marketplace `status`) |
|---|---|
| `subscription.pending` (renewal charge failed, retrying) | **`past_due`** (NEW) — access denied (`plan_is_active` is false for any non-`active`); a recovered `charged` re-activates |
| `subscription.charged` | `active` — also the dunning **recovery** path |
| `subscription.halted` (retries exhausted) | `expired` |
| `subscription.cancelled` | `cancelled` |
| `subscription.completed` | `expired` |

| Method + path | Auth | Purpose |
|---|---|---|
| `POST /api/billing/cancel` | user | Cancel platform plan. Default **at period end**; `at_cycle_end=false` cancels immediately. |
| `POST /api/billing/change-plan` | user | Upgrade/downgrade — next-cycle (no proration, no double charge). |
| `DELETE /api/marketplace/listings/{id}/subscribe` | user | Now gateway-aware: **free** → immediate cancel + 204 (unchanged); **paid** → Razorpay cancel-at-period-end → 200 `{scheduled_cancel:true, access_until}` (access retained until period end). |
| `GET /api/billing/admin/reconcile?subscription_id=…\|user_id=…` | admin | **READ-ONLY** drift report: live Razorpay status vs our stored status; mutates nothing. |
| `POST /api/billing/admin/reconcile/{sub_id}/apply` | admin | **EXPLICIT** admin fix: apply the gateway's truth onto our DB (attributed to `ActorType.ADMIN`). |
| `GET /api/billing/me` | user | now also returns `cancel_at_period_end`. |

## Rules chosen (explicit + tested)
- **Access-end on cancel = cancel-at-period-end (the standard).** Razorpay keeps the sub live until the cycle ends, then fires `subscription.cancelled` → the verified webhook flips status. Access naturally lapses at `plan_expires_at` (the `plan_is_active` expiry check already enforces this — proven: a past-dated expiry returns `is_active=false`). Immediate cancel is opt-in (`at_cycle_end=false`) and, as an explicit authenticated user action, revokes now.
- **Dunning.** `subscription.pending` → `past_due` (access denied during the failed-renewal window); a recovered `subscription.charged` → `active`. Strict (under-grant, never over-grant). New `past_due` value added to both `users.plan_status` and `marketplace_subscriptions.status` CHECKs (migration 036).
- **Plan change = next-cycle, no proration, no double charge.** A NEW subscription is created to **`start_at` the current period's end** (so the new plan's first charge never overlaps the old paid period), and the OLD sub is cancelled at cycle-end (its paid period is honoured). The user's active handle flips to the new sub immediately, so the **OLD sub's lifecycle events are treated as SUPERSEDED** (a webhook guard: only the user's current handle mutates entitlement) and can't clobber the new plan. The new plan's entitlement lands when its first charge webhook arrives. With no current sub, this is just a fresh subscribe.
- **Reconciliation = log-only first.** The admin GET reports drift between gateway truth and our DB and **mutates nothing**; a separate, explicit admin `/apply` (never automatic) applies the gateway status via the same appliers the webhook uses.

## Confirmations (guardrails)
- **Webhook-driven revocation.** Every status change that revokes access is driven by the M1 **single, signature-verified, idempotent** webhook (cycle-end) OR an explicit authenticated user/admin call — never client-side. The new events flow through the SAME `POST /api/billing/webhook/razorpay` (bad signature → 400 grants nothing; good → applies — tested for `subscription.pending`). No second webhook, no duplicated signature logic.
- **Idempotent throughout** — duplicate `event_id` (durable ledger) = single effect; proven for the dunning path.
- **No trading code touched** — diff is the billing/marketplace routers + the Razorpay service/schemas/migration + a `past_due` CHECK widening + tests. A test patches `DhanBroker`/`FyersBroker.place_order` and asserts **zero broker calls** across cancel + dunning + plan-change + reconcile.
- **`paywall_enforced` NOT flipped** (default False).

## Data (migration 036_billing_past_due — additive, off 035, ≤32 chars)
- Widen `users.plan_status` CHECK + `marketplace_subscriptions.status` CHECK to add `past_due`. No new columns, no backfill (cancellation intent + plan-change links live in the existing `razorpay_payments.notes` JSON). Reversible (downgrade restores the prior sets; refuses if `past_due` rows remain).

## Verify (done locally)
- **Migration on REAL Postgres 16** (`:5433`): clean `035→036`, downgrade `036→035`, re-upgrade; both CHECKs confirmed to include `past_due`; single head `036`. Torn down.
- **Backend tests (mocked Razorpay):** `tests/integration/test_razorpay_lifecycle.py` → **8 passed** — cancel-at-period-end keeps access then webhook expires; period-end lapse; immediate cancel revokes; dunning `pending→past_due` + recovery `charged→active` + idempotent; plan-change `start_at`/no-double-charge + superseded guard + entitlement moves on new charge; reconcile flags injected drift + admin apply fixes; shared-webhook signature gate for `subscription.pending`; zero broker calls. Plus **4** endpoint tests (cancel 200/404, marketplace paid-cancel 200-scheduled, admin reconcile drift report). **Full M1–M4 + entitlements + admin regression: 84 passed.**
- `ruff` + `mypy` clean on all changed backend files (the M1 `sync_plan_to_razorpay` `no-any-return` is now fixed too). Frontend `tsc`/`eslint` clean on the `past_due` type additions; M3 vitest still **15 passed**.

## Deliberately NOT done (M4 follow-ups)
- **Sandbox end-to-end** against real Razorpay test-mode (cancel/recovery/plan-change/reconcile) — pending `RAZORPAY_*` TEST keys; SDK is mocked here (and not installed in the local venv, so the live `subscription.cancel/fetch/create(start_at)` calls are wired but unexercised against Razorpay).
- **Dunning UI surface** — `past_due` is exposed in `/me` + typed on the frontend with an amber badge, but a dedicated "update your payment method" banner is a later polish.
- No deploy, no merge to main, no `paywall_enforced` flip.

# ============================================================
# DEPLOY-PREP REBUILD (integration/marketplace-billing) — step 1 of 2, DRY RUN
# ============================================================

**What this is:** a FRESH integration branch off `main` (730ce91) bundling everything to
deploy together — **showcase + Phase 1 fan-out (incl. leak bugfix 03e1706) + Phase 2
Razorpay** — single alembic head, all suites green, flags OFF. The prior integration
branch was rebuilt from scratch so the bugfix is included. **NOT pushed to main, NOT
deployed** (deploy is the separate market-close step 2).

## 1. Merge order + conflicts
Branch off main; merged **showcase → fanout(03e1706) → razorpay**. Conflicts + resolutions:

| Merge | Conflicts | Resolution |
|---|---|---|
| showcase | none (linear off main) | clean |
| fanout | `NOTES_FOR_JAYESH.md` | union (showcase + fanout notes) |
| razorpay | `NOTES`, `main.py`, `config.py`, `marketplace_subscription.py` | **NOTES** union; **main.py** keep BOTH `app.include_router(showcase_router)` + `billing_router` (imports auto-merged); **config.py** keep BOTH `marketplace_fanout_enabled` + `razorpay_*` settings; **marketplace_subscription.py** git **auto-merged** (all 6 cols coexist). |

Verified: full app builds (`create_app()`), both `/api/showcase` and `/api/billing/subscribe`
routes registered; the seam columns all present on `MarketplaceSubscription`.

## 2. Leak bugfix present
`GET /api/strategies/positions` and `GET /api/strategies/executions` both scope
`subscription_id IS NULL` (owner view never leaks subscriber fan-out rows). The two
endpoint files + `tests/test_owner_view_subscription_isolation.py` are **byte-identical to
feat/marketplace-fanout @ 03e1706**; the isolation test passes here.

## 3. Alembic — single head
Re-created `037_merge_fanout_billing` (joins the two heads → single) + `038_exec_mode_paper`
(additive `execution_mode` CHECK widen for billing's `'paper'`). Final single head
**`038_exec_mode_paper`**; the diamond:
```
033 ┬─ 034_razorpay_billing → 035_razorpay_marketplace → 036_billing_past_due ┐
    └─ 034_subscription_scoping → 035_subscription_exec_fields ───────────────┤
                       (035_subscription_exec_fields, 036_billing_past_due) → 037_merge (mergepoint) → 038 (head)
```
On **local Postgres 16**: `upgrade head` applies the full diamond cleanly; `downgrade
033_strategy_state_audit` (7) + re-`upgrade head` (7) clean; `alembic heads` = exactly one.
`execution_mode` CHECK confirmed `IN ('auto','one_click','offline','paper')`. **Showcase
adds NO migration.**

## 4. Verified together
- **ALL suites green: 134 passed** — showcase (`test_showcase_api`, `test_showcase_metrics`)
  + fan-out paper (services + webhook + 2 migration tests, incl.
  `test_flag_off_skips_fanout_and_owner_dispatches_once`) + razorpay billing (M1–M4) +
  the **bugfix isolation test** + shared marketplace CRUD + paywall-gate.
- **Flags default OFF:** `marketplace_fanout_enabled=False`, `paywall_enforced=False`;
  razorpay keys empty (asserted via `get_settings()`).
- **Owner 1→1 byte-identical:** all owner-execution + fan-out + read-endpoint files
  (`strategy_executor` / `direct_exit` / `strategy_webhook` / `position_lookup` /
  `position_manager` / `reconciliation_loop` / `marketplace_fanout` / the two strategy-row
  models / the two read endpoints) are **byte-identical to feat/marketplace-fanout** (which
  Phase 1 proved identical to main's owner path with the flag off). Zero real-broker calls
  (fan-out paper + flag-off; billing never calls a broker).
- **Showcase present:** `frontend/src/app/(public)/showcase/page.tsx` + the **Track Record**
  nav link (`{ label: "Track Record", href: "/showcase" }`) in `(public)/layout.tsx`; the
  `GET /api/showcase` route is registered.
- **Lint:** `ruff` clean on the resolved files; the lone `main.py` I001 is **pre-existing**
  on `main` (count unchanged 1→1 — the billing/showcase imports are correctly sorted).

## 5. Cross-track seam re-applied
The fan-out `execution_mode` columns now exist, so the M3 settings PATCH persists
(`applied=True`) and a fresh sub defaults to `execution_mode='auto'` + `is_paper=True`;
billing's `'paper'` mode coexists (CHECK widened). Seam tests updated accordingly. (Same
clean follow-up before any main merge: collapse the redundant `'paper'` mode into
`is_paper`.)

## 6. Local DB torn down. NOT pushed to main, NOT deployed. Deploy = separate step 2 (merge + migrate + push at market close).

# ============================================================
# DEPLOY LOG — integration → main → prod (2026-06-24, market closed)
# ============================================================

**Deploy:** merged `integration/marketplace-billing` → `main` and migrated/recreated prod.
Window: ~23:08–23:30 IST Wed 2026-06-24 (market CLOSED, both live strategies FLAT).
Bundle: showcase (Track Record) + Phase 1 fan-out (incl. leak bugfix 03e1706) + Phase 2 Razorpay.

## Revisions
| | before | after |
|---|---|---|
| git main | `730ce91` | `b7721d3` (merge of integration `946fa13`) |
| prod alembic | `033_strategy_state_audit` | **`038_exec_mode_paper`** (single head) |
| backend image | (3-day-old) | rebuilt `trading_bridge_backend:latest` (manifest `7aa34fc…`) |

Migration applied the full diamond cleanly: `034_razorpay_billing → 035_razorpay_marketplace →
036_billing_past_due` + `034_subscription_scoping → 035_subscription_exec_fields` → `037_merge
_fanout_billing` (join) → `038_exec_mode_paper` (exec_mode CHECK +`'paper'`). Exit 0, no errors.

## Live strategy state — UNCHANGED (owner path intact)
| Strategy | before | after |
|---|---|---|
| BSE LTD Futures `89423ecc` | is_paper=f, is_active=t, 0 open | **is_paper=f, is_active=t, 0 open** |
| CDSL `0252e82c` | is_paper=f, is_active=t, 0 open | **is_paper=f, is_active=t, 0 open** |

Platform-wide open positions: 0 before, 0 after. Migrations are additive/nullable — `strategies`
untouched; `strategy_positions.subscription_id` added nullable=YES; existing data intact
(strategies=4, users=6). Live owner webhook `/api/webhook/strategy/{webhook_token}` mounted +
healthy; celery worker connected to redis + `ready`.

## Flags — OFF in the RUNNING prod app (fan-out + billing dormant)
`marketplace_fanout_enabled=False`, `paywall_enforced=False`, `razorpay_key_id` empty,
`razorpay_webhook_secret` empty. Nothing customer-facing is active; the new subscriber/billing
paths are present but inert until keys + flags are deliberately set.

## Showcase / customer surface — LIVE
- `https://tradetri.com` → 200, `https://tradetri.com/showcase` → 200 (Track Record live, Vercel
  auto-deployed from the main push), `https://api.tradetri.com/api/showcase` → 200,
  `https://api.tradetri.com/health` → 200.
- Existing surface intact: `/api/pricing/plans` → 200, `/api/auth/login` → 405 (POST-only route mounted).

## Verify summary (steps 8–12)
8. alembic current = **038**; new tables/columns present; existing data intact. ✅
9. BSE + CDSL is_paper/is_active/positions **unchanged** vs pre-deploy record. ✅
10. Flags confirmed **OFF** in the running prod app (razorpay unconfigured). ✅
11. `tradetri.com/showcase` loads; `/api/showcase` responds; dashboard/login routes serve. ✅
12. **No errors** in backend logs (clean `Application startup complete`); live owner webhook
    healthy; worker `ready`. ✅

## Issues / notes
- `celery_worker` / `celery_beat` show docker "unhealthy" — **known cosmetic** misconfigured
  healthcheck (curl :8000 on a non-web container); present before this deploy too. Worker is
  application-healthy (connected to redis, `ready`, no errors). Not a fault.

## Rollback (if ever needed)
- Prod DB backup: `/home/ubuntu/backups/prod_pre_cutover_038_20260624_173857.dump` (custom-format,
  316 TOC entries) — restore: `docker exec -i trading_bridge_postgres pg_restore -U $POSTGRES_USER
  -d $POSTGRES_DB --clean --if-exists < <dump>`; then `alembic downgrade 033_strategy_state_audit`
  (or restore img + `git reset` main). NOT needed — deploy clean.

**Deploy successful. Owner trading path live + unchanged; fan-out + billing dormant; showcase live.**

# ============================================================
# BUGFIX — public showcase counted a PAPER trade as "live reconciled"
# ============================================================

**Credibility bug (confirmed on prod):** `GET /api/showcase/{key}/live` counted a
`strategy_positions` row when the strategy's CURRENT `is_paper=false` AND `final_pnl
IS NOT NULL` — it never checked whether the POSITION itself was a real or paper fill.
Result for BSE: one STALE PAPER position (`bf70e28c`, `broker_order_id 'PAPER-…'`,
`broker_response "paper-mode simulated fill"`, P&L 0, opened 2026-05-24, manually
closed) was reported as **"1 live trade reconciled"**, while the 5 genuinely-real Dhan
trades (real `broker_order_id`s, `final_pnl` NULL — not yet reconciled) were NOT
counted. The public Track Record page showed a paper trade as a verified live trade —
directly contradicting "Proof, not promises."

## Fix (read-path / display only — `app/api/showcase_api.py::_count_reconciled_real_trades`)
The count now requires a REAL broker fill, not just the strategy's flag:
```sql
SELECT count(*) FROM strategy_positions p
JOIN strategies s ON p.strategy_id = s.id
WHERE CAST(s.id AS TEXT) LIKE :p          -- portable; == ::text on Postgres
  AND s.is_paper = false
  AND p.final_pnl IS NOT NULL             -- reconciled P&L
  AND EXISTS (                            -- ...AND a REAL broker fill
    SELECT 1 FROM strategy_executions e
    WHERE e.signal_id = p.signal_id
      AND e.broker_order_id IS NOT NULL
      AND e.broker_order_id NOT LIKE 'PAPER-%'   -- paper sims tagged 'PAPER-…'
  );
```
Real-vs-paper marker = `broker_order_id`: paper (simulated) fills are tagged
`'PAPER-…'` (and carry `broker_response.raw.paper_mode = true`); real fills carry the
broker's own id. The `EXISTS` requires positive proof of a real fill, so it
under-counts ambiguous rows rather than over-counting (honest by construction).

## BSE `/live` — before vs after (validated against REAL prod data, read-only)
| | count |
|---|---|
| OLD (buggy) query on prod | **1** (the stale PAPER row miscounted) |
| NEW (fixed) query on prod | **0** (paper excluded; the 5 real trades aren't reconciled yet → `final_pnl` NULL) |
| CDSL (fixed) | 0 |

So BSE now renders the HONEST 0-state: `status="tracking_active"`, `reconciled_trades=0`,
note *"Live tracking active — no trades reconciled/published yet."* No P&L is shown
(never was). When the reconciler genuinely populates `final_pnl` for the real trades,
they'll start counting; the paper row never will.

## Guarantees
- **No data mutated.** The stale paper position `bf70e28c` is left exactly as-is — the
  fix only stops *counting* it. Read-only `SELECT`; the router still imports no
  executor/broker/webhook/kill-switch module (the `test_router_has_no_write_or_trading_path`
  guard still passes).
- **No trading/executor/migration/flag/strategies change.** Diff is `showcase_api.py`
  (the one count query + docstring) + a new test. `CAST(…AS TEXT)` is identical to
  `::text` on Postgres (also lets the test run on sqlite).
- **Honest framing preserved** — 0 genuinely-reconciled → the page says exactly that;
  no invented or padded P&L.

## Verify
- `cd backend && .venv/bin/python -m pytest tests/integration/test_showcase_live_real_only.py -q`
  → **5 passed**: paper position never counted; real-but-unreconciled not counted; real+
  reconciled counted; paper strategy excluded; the BSE scenario renders the honest 0-state
  end-to-end (no P&L). Existing showcase suite: **32 passed** (no regression). `ruff`/`mypy`
  add no new errors (the pre-existing B904/typing on main are unchanged 3→3, 6→6).
- Frontend/Vercel auto-deploys on merge; display-correctness only.

## DEPLOYED to prod (2026-06-25 ~00:30 IST, market closed)
Backend rebuilt + recreated (backend + celery_worker + celery_beat) from main `fa3e06c`;
**no migration** (alembic stays 038). Verified live:
- `https://api.tradetri.com/api/showcase/bse/live` → **`reconciled_trades:0`** (was `1`) —
  honest *"Live tracking active — no trades reconciled/published yet."* CDSL = 0 too.
- BSE `89423ecc` + CDSL `0252e82c`: `is_paper=f, is_active=t` **unchanged**; 0 open positions.
- Backend healthy, clean startup, no errors; worker connected+`ready`; live owner webhook
  `/api/webhook/strategy/{token}` mounted (405 on GET = healthy). Owner trading path untouched.
The public Track Record page no longer reports the paper trade as a live reconciled trade.

# ============================================================
# Showcase follow-up — Part A (already shipped) + Part B (equity range selector)
# ============================================================

## Part A — credibility fix (ALREADY DONE + LIVE on prod)
The `/api/showcase/{key}/live` real-vs-paper miscount was fixed + deployed earlier
this session (commit `fa3e06c`, backend redeployed): the count now requires a REAL
fill (`broker_order_id NOT LIKE 'PAPER-%'` on the position's signal) + a reconciled
`final_pnl`. **BSE before → after: 1 (stale PAPER row miscounted) → 0** (honest
"live tracking active — no trades reconciled/published yet"); CDSL 0. The stale
paper position `bf70e28c` was NOT mutated. (Full writeup is the "BUGFIX — public
showcase…" section above.) No further code change needed for Part A.

## Part B — re-based time-range selector on the equity curves (this branch)
Frontend-only. The "Cumulative edge" non-compounded equity curve on each strategy
card now has a range selector and re-bases each window to start at 0%.
- **Ranges:** 1M / 3M / 6M / 1Y / 2Y / 3Y / 4Y / 5Y / All — **default 3M** — rendered
  with the existing brand `Seg` toggle (same control as All/Long/Short), in a row
  below the chart (horizontally scrollable on narrow screens).
- **Re-base:** new pure helper `src/lib/showcase/range.ts::rebaseToWindow(points,
  months)` — filters `equity_curve_noncompounded` to the window, subtracts the
  pre-window cumulative baseline, and prepends a 0% anchor. So a window reads
  "+X% over the last N months" **from 0** — the LAST point = the SUM of that
  window's per-trade %s (e.g. +35%), NOT the full-series figure (+1700%). "All"
  shows the full series as-is (from the first trade). Each range reads correctly
  on its own.
- **Window is from the SERIES' OWN latest date** (the backtest ends ~2026-06-18/19),
  not today — so 3M/6M always show data. Stated in a caption under the chart.
- **Direction-consistent:** the range applies to the active All/Long/Short series.
  The per-period Yearly/Monthly table is unchanged — this is the CHART only.
- **Data is already present** (`backtest.series.{dir}.equity_curve_noncompounded`
  with dates); pure frontend filtering + re-basing, **no new backend/endpoint**.

## Guardrails
- **Frontend + the one `/live` query only.** Part B touches `showcase/page.tsx` +
  the new `range.ts` (+ test). NO trading/executor/webhook/reconciler/migration/flag/
  strategies change; no data mutated.
- **Verify:** `cd frontend && npx vitest run tests/showcase/range.test.ts` → **9
  passed** (default 3M; 3M starts at 0% & ends at the window's per-trade sum, not
  +full; 6M/1M re-base; All = full series; whole-series window has no negative
  baseline; empty → empty; never invents points). `tsc` + `eslint` clean on changed
  files. Vercel auto-deploys on merge.
