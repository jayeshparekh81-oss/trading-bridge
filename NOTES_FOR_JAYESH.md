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
