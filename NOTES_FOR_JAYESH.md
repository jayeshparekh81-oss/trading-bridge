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
