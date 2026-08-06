# NIFTY Option Data Inventory

**Type:** read-only data inventory. No strategy code written, no strategy module
created, no option prices generated or simulated. No EC2, prod, live config or
credentials touched. Nothing modified except this file.

**Date of scan:** 2026-08-06
**Repo:** `/home/user/trading-bridge` @ branch `claude/new-session-iii669`

---

## 0. SCOPE OF THE SEARCH — read this before trusting any "NOT PRESENT" below

The task said "search the Mac". **This session is not running on the Mac.** It is
a Claude Code remote cloud session in an ephemeral Linux container
(`Linux vm 6.18.5 x86_64`) that was created by cloning
`jayeshparekh81-oss/trading-bridge` fresh. What was actually searched:

| Searched | Result |
|---|---|
| Entire writable filesystem (`find / -xdev`) for `*.parquet`, `*.csv`, `*.feather`, `*.h5/.hdf5`, `*.db`, `*.sqlite*`, `*.jsonl`, `*.pkl`, `*.duckdb` | Only repo test-result CSVs, OS files, and Claude CLI logs |
| `/home/user` | Contains **only** `trading-bridge`. No other directory. |
| Mounted filesystems | Root ext4 + read-only system images (`/opt/claude-code`, `/opt/rclone`, `/opt/env-runner`, `/mnt/skills`). **No Mac volume, no external mount, no network share.** |
| The `trading-bridge` repo, full tree | Inventoried below |

**Therefore:** every "NOT PRESENT" in this document means *not present in the
trading-bridge repo and not present on this container's disk*. It is **not**
evidence about what exists on your Mac's local disks, on EC2, or in S3. Those
were not reachable and were not probed. If a dataset exists on the Mac, this
report cannot see it and does not contradict it.

The Postgres database is likewise **not reachable from here** — no DB server is
running in this container. Anything stored only as table rows (see §5) could not
be row-counted or date-ranged; only the schema definition in the repo was read.

---

## 1. Historical NIFTY option contract prices

**NOT PRESENT** — zero option price files on disk.

`find / -xdev -type f -name '*.parquet'` returns **zero results**. There is no
`data/` directory in the repo, no `data/habitat/`, no option chain dump, no CSV
of option prices, no database file.

What *does* exist is a **reader for a data layout that has no data behind it in
this environment**:

**Source: `backend/app/services/options_premium_lookup.py`** — reader only, no data

- **Path (code):** `backend/app/services/options_premium_lookup.py`
- **Path (data it expects):** caller-supplied `day_dir`; layout is
  `{day_dir}/manifest.json` + `{day_dir}/{SYMBOL}_{security_id}.parquet`
  (e.g. `NIFTY_CE_24800_49081.parquet`). **No default path, no configured root,
  no env var** — the directory is a function argument. Nothing in the repo calls
  it with a real path.
- **Format:** Parquet, one file per instrument per day, indexed by a per-day
  `manifest.json` (`{"date":…, "instruments":[{"symbol":…, "security_id":…, "kind":"option", "expiry":…}]}`)
- **Row count:** **NOT PRESENT** (no files exist to count)
- **First/last date:** **NOT PRESENT**
- **Distinct expiries:** **NOT PRESENT.** Note the reader's documented constraint
  (line 31-34): the upstream recorder arms **ONE chain expiry per underlying per
  day**, so even when populated this source is single-expiry-per-day, not a full
  expiry surface.
- **Distinct strikes:** **NOT PRESENT.** Reader docstring references a "±20-no-recenter"
  strike window in the recorder (line 43), implying ~41 strikes/day when populated —
  but that is a comment about the upstream writer, not data present here.
- **Frequency:** **TICK** (`ts_recv_ns` = epoch-nanoseconds UTC at receipt; LTP
  semantics, last row at-or-before the query timestamp)

Provenance of the layout, quoted from the module docstring (lines 7-8): the
schema was *audited from* branch `feat/orderflow-r0-recorder` @ commit `00fc4fe`
(`writer.py` / `schema.py` / `main.py` / `scrip_master.py`). **That recorder
branch is not present in this checkout** — only the reader written against it.
The docstring states plainly (lines 3-5): *"STANDALONE + FIXTURE-TESTED — nothing
imports this yet; wiring into entry/exit P&L, the real EC2/S3 data, and the
`expiry_date + entry_premium` migration are slice ③-b (separately gated)."*

The phrase **"the real EC2/S3 data"** is the repo's own statement that the actual
recorded option data — if it exists — lives on EC2/S3, which this task forbids
touching and which was not accessed.

**Test fixtures are synthetic, not historical data.**
`backend/tests/services/test_options_premium_lookup.py` builds throwaway parquet
files under pytest `tmp_path` (line 79-86, `pa.Table.from_pylist(rows, …)` then
`pq.write_table`). These are hand-written tick rows for assertions. They are not
market data and carry no dates, no real prices.

**Other candidate locations — all empty:**

| Path | Contents |
|---|---|
| `backend/app/services/options/` | `README.md` + `.gitkeep` only — **no data, no code** |
| `backend/data/` | `phase_2_template_configs.json`, `strategy_templates_seed.json` — strategy templates, **no market data** |
| `frontend/src/data/` | `indicator_library_badges.json`, `glossary.json`, `convention_tooltips.json` — UI copy, **no market data** |

---

## 2. bid / ask / bid_qty / ask_qty vs LTP-only — verbatim column names

### 2a. Recorded option tick layout (`options_premium_lookup.py`)

Columns **verbatim as read** at line 132-133:

```
"ts_recv_ns", "ltp", "bid_price_1", "ask_price_1"
```

- **Separate bid and ask: YES** — `bid_price_1`, `ask_price_1` (the `_1` suffix
  is top-of-book level 1).
- **bid_qty / ask_qty: NOT PRESENT in any code path.** The docstring at line 15
  describes the writer's schema as *"5-level depth `bid_price_1`/`ask_price_1`…"*
  — the ellipsis implies further depth columns exist in the file, but **the
  reader requests only these four columns and no quantity column is named
  anywhere in this repo.** Whether `bid_qty_1`/`ask_qty_1` exist in the actual
  recorder schema cannot be determined from here — `schema.py` lives on the
  absent `feat/orderflow-r0-recorder` branch.
- **LTP:** `ltp` — documented as *"THE premium"* (line 15).
- Usage: fresh `ltp` preferred (≤120 s stale, `LTP_MAX_STALENESS_S`); past that,
  `(bid_price_1 + ask_price_1) / 2` (≤600 s, `MID_MAX_STALENESS_S`); past 600 s →
  typed no-data.

### 2b. Historical candles table (`historical_candles`)

Columns verbatim, from `backend/app/db/models/historical_candle.py:72-110`:

```
symbol, exchange, timeframe, timestamp, open, high, low, close,
volume, dhan_security_id, source, fetched_at, fetched_by_user_id, quality_score
```

- **bid / ask / bid_qty / ask_qty: NOT PRESENT.** OHLCV only.

### 2c. Live broker quote schema (not historical)

`backend/app/schemas/broker.py:298-299` — `bid: Decimal`, `ask: Decimal`.
Populated live by `backend/app/brokers/fyers.py:496-497` (`bid=_money(data.get("bid"))`,
`ask=_money(data.get("ask"))`). **Live quote object, never persisted to history.**
No qty fields.

---

## 3. Per-contract open interest and volume

- **Open interest: NOT PRESENT as stored history.**
  - `backend/app/strategy_engine/data_provider/dhan_client.py:169-170` — Dhan's
    response carries `open_interest`, and the normaliser **explicitly drops it**:
    *"normalises them into the Phase 1 `Candle` shape, **dropping `open_interest`**"*.
  - `backend/app/brokers/dhan_websocket.py:91` — response code 5 (OI Data) is
    *"skipped in v1"*. Line 92 / 210 — code 6 (prev close + prev-day OI) also
    *"skipped in v1"*.
  - The `historical_candles` table has no OI column.
  - Every "OI" reference in the indicator packs is descriptive prose about market
    behaviour, not a data field (e.g. `_pack16_active.py:43`, `:238`).
- **Volume:**
  - **Underlying/equity candles: PRESENT** — `volume` column in `historical_candles`
    (`historical_candle.py:84`).
  - **Per option contract: NOT PRESENT.** No volume column is read by
    `options_premium_lookup.py`, and there is no per-contract store.
  - `backend/app/strategy_engine/indicators/calculations/cumulative_volume_delta.py:3`
    states the limitation directly: *"Real CVD requires bid/ask trade tape — a
    microstructure feed"* the bar-data layer doesn't carry
    (also `_pack10_active.py:19`, `:349`).

---

## 4. India VIX history

**NOT PRESENT.** No India VIX time series exists in any form — no file, no table,
no column, no fetcher.

VIX is consumed **only as a live scalar passed in on the signal payload**:

- `backend/app/services/ai_validator.py:224` — `vix = float(indicators.get("IndiaVIX", 0) or 0)`
  — read from the inbound signal's indicator dict.
- `ai_validator.py:163-164` — a **hardcoded default** is substituted when the
  payload omits one: *"Default IndiaVIX used when the signal payload omits one.
  Mid-band value → VIX rule passes through full qty."*
- `ai_validator.py:73` — VIX modulation band; `:175` — `REGIME_VIX_HIGH`;
  `:314` — `vix_adjust_qty(qty, vix)`; `:20` — rule is *"VIX < 11.5 OR > 20.0 →
  halve qty; else full."*

- **Path:** NOT PRESENT
- **Range:** NOT PRESENT

Everything else matching `vix` is unrelated: `frontend/src/lib/indicators/content/williams-vix-fix.ts`
is the **Williams VIX Fix** indicator — a price-derived synthetic computed from
OHLC of any instrument, explicitly *not* India VIX (it exists precisely because
non-index symbols have no vol index).

---

## 5. NIFTY futures history

**NOT PRESENT as a distinct futures dataset.** No futures-specific file, table or
column exists.

The only historical price store in the repo is the generic `historical_candles`
Postgres table, which is symbol-agnostic:

- **Path (schema):** `backend/app/db/models/historical_candle.py` (table
  `historical_candles`, line 70); migration `backend/migrations/versions/029_historical_candles.py`;
  backfill jobs `030_historical_backfill_jobs.py`
- **Key:** composite PK `(symbol, exchange, timeframe, timestamp)`
  (`backend/app/services/historical_candles/repository.py`, docstring)
- **Frequency:** whatever `timeframe` values were fetched — the column is free-form
  `Text`, **not** an enum, so the set of stored frequencies is a data question, not
  a schema question
- **Row count:** **NOT PRESENT / UNKNOWN.** No database is running in this
  container and prod DB access is out of scope. The table may hold NIFTY futures
  bars on EC2; that cannot be confirmed or denied from here.
- **Range:** **NOT PRESENT / UNKNOWN**, same reason. `repository.py` exposes a
  `coverage()` method returning `bar_count` + first/last timestamp — that is the
  query to run **on the real DB** to answer this properly.

Futures **contract resolution** logic exists (no price history):
`backend/app/services/futures_resolver.py` — resolves the active monthly futures
trading symbol from the Dhan scrip master (line 10). `indicator_candles.py:70-71`
maps `NSE_FNO`/`BSE_FNO` → `FUTIDX`.

---

## 6. NSE trading-holiday calendar / expiry calendar

**NOT PRESENT.** No holiday list, no expiry-date table, no calendar file of any
kind (no JSON, no CSV, no DB table, no constant).

What exists is a **weekend-only** calendar util with the holiday set left as an
unpopulated optional parameter:

- `backend/app/strategy_engine/trading_calendar.py`
  - Line 21: `_WEEKEND: frozenset[int] = frozenset({5, 6})` — Sat/Sun only
  - Line 24: `is_trading_day(day, holidays: set[date] | None = None)` — the
    `holidays` set is an **argument the caller must supply; nothing in the repo
    supplies one**
  - Lines 11-13 state the deliberate choice: *"`holidays` is a refinement, not a
    requirement for v1: real exchange expiries (`SEM_EXPIRY_DATE`) already encode
    holiday shifts, so weekend-only skipping is a safe default."*
- `backend/app/services/historical_candles/rate_limit_guard.py:96-98` —
  `if ist_now.weekday() >= 5:` weekend check, with the comment *"Phase 3+ holiday
  calendar handles weekday market holidays"* — i.e. **not built yet**
- `frontend/src/lib/market-hours.ts:21-29` — explicit TODO: *"This helper does NOT
  know about NSE holidays (Republic Day, Independence Day, Diwali Muhurat, etc.)…
  TODO: integrate NSE holiday calendar (post-launch)"*

### Does anything record the actual expiry WEEKDAY per date (Thu before Sep-2025, Tue after)?

**NO. NOT PRESENT.** There is no per-date expiry-weekday record anywhere. The
Thursday→Tuesday transition is **not stored as data** and cannot be reconstructed
from this repo.

The architecture deliberately **avoids** storing it, delegating to the broker's
scrip master at runtime:

- `backend/app/services/futures_resolver.py:24` — real expiry comes from the
  master, *"a computed last-Thursday only if the master omits it"*
- `futures_resolver.py:39-40` — *"last Tuesday) and holiday-induced shifts are
  tracked automatically — **no hardcoded calendar**. The last-Thursday computation
  survives only as a [fallback]"*
- `futures_resolver.py:136-137` — *"auto-tracks SEBI's last-Tuesday shift AND
  holiday-induced moves"*
- `backend/app/services/pine_mapper.py:587-588` — scrip master *"is already
  Tuesday-correct and holiday-shifted by the exchange — so **no weekday assumption
  survives**"*
- `backend/app/services/options_expiry_sweep.py:10` — `scrip_master.expiry_for(symbol, 'NSE_FNO')`
  is *"the REAL"* authority

**Consequence for backtesting:** the scrip master is a *live* lookup describing
*currently listed* contracts. It cannot tell you what the expiry weekday was on an
arbitrary past date. For historical work the Thu/Tue rule and its holiday shifts
would have to be sourced fresh — **nothing in this repo has it.**

---

## 7. Historical lot-size or strike-interval table for NIFTY

**NOT PRESENT — neither a lot-size table nor a strike-interval table, historical
or current.**

- **Lot size:** resolved at runtime from the Dhan scrip master, never stored.
  `backend/app/services/marketplace_fanout.py:398-410` — `_real_lot_size()` does a
  *"REAL lot_size via a read-only scrip-master lookup"* via `master.lot_size(sid)`.
  `backend/app/brokers/dhan.py:431` notes the master *"CSV stores lot units as float
  string (e.g. '375.0')"*. The scrip master is **fetched over the network at startup**
  (`backend/app/main.py:107-126`, `_scrip_master_warm_loop` → `settings.dhan_scrip_master_url`)
  and held in memory — **no local copy, no historical snapshots, no versioning.**
  A NIFTY lot size for any past date is therefore unavailable.
- **Strike interval:** no table. A single hardcoded default constant exists — see
  §8 below.

---

## 8. Hardcoded NIFTY expiry weekday and lot size — file + line

### 8a. Expiry weekday hardcodes

| File | Line | What is hardcoded |
|---|---|---|
| `backend/app/services/futures_resolver.py` | 110 | `def _last_thursday_of_month(yyyymm: str) -> date:` — Thursday baked into the name/contract |
| `backend/app/services/futures_resolver.py` | 121-122 | `# weekday(): Mon=0 ... Thu=3` / `offset = (last_day.weekday() - 3) % 7` — **literal `3` = Thursday** |
| `backend/app/services/futures_resolver.py` | 143 | `expiry = _last_thursday_of_month(middle)` — the fallback call site |
| `backend/app/strategy_engine/indicators/calculations/is_expiry_week.py` | 59 | `def _last_thursday_of_month(year: int, month: int) -> date:` |
| `backend/app/strategy_engine/indicators/calculations/is_expiry_week.py` | 63-64 | `# weekday(): Monday = 0, Thursday = 3.` / `while last.weekday() != 3:` — **literal `3`** |
| `backend/app/strategy_engine/indicators/calculations/is_expiry_week.py` | 43, 46-48 | `last_thursday_cache` — Thursday assumption in the cache key/flow |
| `backend/app/strategy_engine/indicators/calculations/is_expiry_week.py` | 21 | comment: *"Bar in a month where the last Thursday is a holiday: still …"* |
| `backend/app/strategy_engine/indicators/calculations/expiry_day_volatility.py` | 45 | `weekday_target: int = 3` — **default Thursday** (configurable, but 3 is the default) |
| `backend/app/strategy_engine/indicators/calculations/expiry_day_volatility.py` | 13 | docstring: *"Default `weekday_target = 3` (Thursday: Mon=0..Sun=6)"* |
| `backend/app/strategy_engine/indicators/_pack16_active.py` | 276-277 | `InputSpec(name="weekday_target", … default=3, min=0, max=6)` — **default 3 in the registry** |
| `backend/app/strategy_engine/indicators/_pack16_active.py` | 271 | description text: *"configured expiry weekday (default Thursday)"* |
| `backend/app/strategy_engine/indicators/_pack16_active.py` | 290 | Hindi description: *"typical Thursday"* |
| `backend/app/strategy_engine/indicators/_pack15_active.py` | 38 | *"*last Thursday of the month* (Indian F&O monthly expiry)"* |
| `backend/app/strategy_engine/indicators/_pack15_active.py` | 155 | *"the last Thursday of the month (Indian F&O monthly …)"* |

**Stale user-facing content asserting the wrong weekday** (not executable, but it
is a hardcoded claim about expiry weekday and it is out of date):

| File | Line | Claim |
|---|---|---|
| `frontend/src/lib/help/faq-content.ts` | 646 | *"NIFTY weekly options expire **Thursday**"* + *"BANKNIFTY … last Thursday of the month"* |
| `frontend/src/lib/help/faq-content.ts` | 648 | same claim, Hindi |
| `frontend/src/lib/algomitra-faqs.ts` | 507 | *"Weekly: NIFTY/BANKNIFTY/FINNIFTY/MIDCPNIFTY har Tuesday-Friday alag (rotating expiry). Monthly: … last Thursday."* — contradicts the file above |
| `backend/app/services/algomitra_ai.py` | 172 | *"expiries (rotating Tue-Fri). Stocks monthly (last Thursday)."* |
| `frontend/src/lib/indicators/content/macd.ts` | 85 | *"On NIFTY weekly expiries … reliable into Tuesday-Wednesday but noisy on Thursday morning"* |
| `frontend/src/lib/indicators/content/vwap.ts` | 67 | *"less reliable on Wednesday-Thursday of expiry week"* |

Reported as found; **no expectation enforced, nothing changed.**

### 8b. Lot size hardcodes

| File | Line | What is hardcoded |
|---|---|---|
| `backend/app/strategy_engine/indicators/calculations/fno_lot_size_atr.py` | 31 | `assumed_lot_size: int = 50` — **literal default 50** |
| `backend/app/strategy_engine/indicators/calculations/fno_lot_size_atr.py` | 8-10 | docstring: *"Default `assumed_lot_size = 50` (e.g. NIFTY index futures lot was 50 **prior to the November 2024 SEBI lot-size revision**). Operators should override per symbol from the latest exchange circular."* — **self-declared stale default** |
| `backend/app/services/strategy_executor.py` | 583 | `return 1` — paper mode / no broker falls back to **lot size 1** |
| `backend/app/services/strategy_executor.py` | 569-572 | docstring for that fallback: *"Paper mode: read `signal.raw_payload["lot_size_hint"]` if present, else **default to 1**"* |
| `backend/app/services/strategy_executor.py` | 130 | comment: `750` = `2 lots × 375 lot_size for BSE Ltd.` — **375 in prose** |
| `backend/app/services/strategy_executor.py` | 247-248, 457 | further `750`/`375` references in comments |
| `backend/app/api/strategy_webhook.py` | 88 | comment: *"750 (2 lots × 375)"* |

`375` appears only in **comments/examples**, never as an executable constant —
the live path resolves it from the scrip master. `50` and `1` **are** executable
defaults.

### 8c. Strike interval hardcode (adjacent, reporting for completeness)

| File | Line | What is hardcoded |
|---|---|---|
| `backend/app/services/pine_mapper.py` | 333 | `_DEFAULT_STRIKE_STEP: Final = Decimal("100")` |
| `backend/app/services/pine_mapper.py` | 330-332 | *"Default strike step for BSE LTD weekly options. **⚠️ ASSUMPTION — verify against the live contract spec before Phase 3.** Overridable per-strategy via `OptionsConfig.strike_step`."* |
| `backend/app/strategy_engine/indicators/_pack16_active.py` | 213, 243 | `default=100.0` for `strike_step` inputs (`atm_strike_distance`, `round_number_attraction`) |
| `backend/app/strategy_engine/indicators/_pack16_active.py` | 40 | *"configurable `strike_step` (default 100 = NIFTY-style)"* |

---

## 9. Places that GENERATE option premiums from a model instead of reading recorded prices

**NONE. NOT PRESENT.**

**There is no Black-Scholes implementation, and no option-pricing model of any
kind, anywhere in this repo.** Greps for `norm.cdf`, `scipy.stats`, `math.erf`,
`d1`/`d2`, `time_to_expiry`, `implied_vol`, `black_scholes` return **no pricing
implementation** — every hit is either an unrelated statistics indicator (Sharpe/
Sortino `risk_free_rate`, `annualization`) or a comment stating a model is *absent*.

The only path that produces an option premium is
`options_premium_lookup.premium_at()` (§1), which **reads recorded parquet ticks**
and returns a typed `no_data` result rather than inventing a number — this is the
opposite of model generation. Its docstring, line 38-39: *"Missing data is a
NORMAL, TYPED outcome — never an exception, **never a silently-wrong number**."*

### What exists instead: Pack 16 "Greeks" — price-derived proxies, NOT priced options

These compute an indicator from the **underlying's own OHLC**. They never produce
a premium, never take a strike or expiry, and never use a sigma in a pricing
formula. The repo labels them loudly and repeatedly:

| File | Line | Sigma / input used | Note |
|---|---|---|---|
| `backend/app/strategy_engine/indicators/_pack16_active.py` | 3-7 | — | *"⚠️ CRITICAL: All Pack 16 'Greeks' are PRICE-DERIVED PROXIES, NOT actual Black-Scholes Greeks. Real Greeks need: options [chain]…"* |
| `_pack16_active.py` | 45-47 | — | *"Real Greeks come from Black-Scholes inversion on actual option [data]"* |
| `.../calculations/iv_proxy_atr.py` | 1-27 | **ATR-percent × √252** (`atr_period = 20`, `bars_per_year = 252`) — **no implied vol, no option data** | *"This is a PROXY, not actual implied volatility. Real IV needs an options chain + Black-Scholes inversion + risk-free rate."* |
| `.../calculations/delta_proxy_directional.py` | 3-4 | price momentum, clamped −1..+1 | *"PRICE-DERIVED PROXY, NOT an actual Black-Scholes delta. Real delta needs an options chain + strike + expiry"* |
| `.../calculations/theta_proxy_decay.py` | 1-3 | realised range decay (avg range 1st half vs 2nd) | *"PROXY, not Black-Scholes theta"* |
| `.../calculations/vega_proxy_iv_sensitivity.py` | 1 | price change % per vol-regime shift | proxy |
| `.../calculations/gamma_proxy_acceleration.py` | 3 | smoothed 2nd derivative of price | *"PROXY, not Black-Scholes gamma"* |
| `backend/app/strategy_engine/indicators/registry.py` | 516-517 | — | *"ALL Greeks are PRICE-DERIVED PROXIES, not Black-Scholes; documented loudly."* |

Sigma used by the closest thing to a vol input (`iv_proxy_atr`) is **realised ATR
volatility of the underlying**, annualised by `√bars_per_year` (default 252). It
is never fed into a pricing formula.

### One adjacent price simulator — underlying only, not options, no model

`backend/app/services/strategy_executor.py:1049-1068` — `_simulate_fill()`. Paper
mode fill price. It **echoes the price from the inbound TradingView payload**
(`payload.get("price")`), or `Decimal("0")` if absent. **No model, no sigma, no
option pricing** — it copies a number or returns zero. Recorded here only so the
"generates prices" question has a complete answer.

---

## SUMMARY

| # | Question | Answer |
|---|---|---|
| 1 | Historical NIFTY option prices | **NOT PRESENT** on disk. A tick-parquet *reader* exists (`options_premium_lookup.py`, unwired); repo says the real data is on **EC2/S3** — not accessed |
| 2 | bid/ask/qty vs LTP | Reader takes `ts_recv_ns`, `ltp`, `bid_price_1`, `ask_price_1`. **bid_qty/ask_qty NOT PRESENT** anywhere. Candles table is OHLCV-only |
| 3 | Per-contract OI / volume | **OI NOT PRESENT** — explicitly dropped (`dhan_client.py:169-170`) and skipped (`dhan_websocket.py:91`). Per-contract volume **NOT PRESENT**; underlying volume present |
| 4 | India VIX history | **NOT PRESENT** — live scalar off the signal payload only, with a hardcoded default |
| 5 | NIFTY futures history | **NOT PRESENT** as a dataset. Generic `historical_candles` table exists; **row count and range UNKNOWN** (no DB reachable) |
| 6 | Holiday / expiry calendar | **NOT PRESENT.** Weekend-only util; `holidays` param never populated. **Per-date expiry weekday NOT recorded** — Thu→Tue transition is not reconstructible here |
| 7 | Lot-size / strike-interval table | **NOT PRESENT.** Lot size = runtime scrip-master lookup, network-fetched, not stored, no history |
| 8 | Hardcoded expiry weekday / lot size | Weekday `3` (Thu) hardcoded in **4 files**; lot size `50` and `1` executable defaults; strike step `100`. Full table in §8 |
| 9 | Model-generated premiums | **NONE.** No Black-Scholes anywhere. Pack 16 "Greeks" are underlying-price proxies, loudly labelled as such |

**Bottom line:** in the material reachable from this session there is **no
historical NIFTY option data of any kind** — no prices, no OI, no VIX, no futures
series, no expiry calendar, no lot-size history. There is a well-documented reader
waiting for data that lives elsewhere (EC2/S3, per the repo's own docstring) and a
consistent architectural choice to resolve contract facts live from the broker's
scrip master rather than store them. That choice is sound for live trading and is
exactly what blocks historical work: the scrip master cannot answer questions
about the past.

**What this report cannot tell you:** whether the Mac's local disks, the EC2 host,
or S3 hold any of the above. None were reachable; none were probed. To close those
gaps, this inventory needs to be re-run on the Mac, and `coverage()` needs to be
queried against the real database.
