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
