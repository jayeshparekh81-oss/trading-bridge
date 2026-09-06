# CP0 — FEATURE AUDIT of research/depth_proxies.py (no data, no scoring)

File: `research/depth_proxies.py` — 13421 bytes, sha256 `638dc38cb821c50780b1018bc4b9827c6f70d96b1db80b69220c5a0a5e16d88b`; byte-identical to the shared checkout copy: True.
Engine defaults (constructor): levels=5, k_refill=5, near_ticks=2.0, tick=0.05 (near = 0.10), gap_guard_ns=5 s, wall_frac=0.2, wall_lookback=500.
The file reads ONLY the top **5** levels (`snapshot_to_book(parsed, levels=5)`); its own docstring lists "5 levels only" as a known limit. It never touches levels 6..20.

## Every feature / metric the file computes

| # | name (as the file computes it) | formula in plain terms | exact input columns touched | bucket |
|---|---|---|---|---|
| 1 | refill event (`ProxyEvent.kind='refill'`, fields removed/restored/ratio) | per side, for a price p present in BOTH consecutive snapshots: qty drops (d>0) → a pending record for up to k_refill=5 later snapshots; if qty later rises at the same p while the side's best price is within 0.10 of p → refill; ratio = restored/removed | `price_1..5`, `qty_1..5`, `side`, `ts_recv_ns` (gap guard: a >5 s gap discards the diff and pending state) | **ELIGIBLE** |
| 2 | `{side}_refills` (per bar, `aggregate`) | count of refill events with bar_start < ts ≤ bar_end | refill events (row 1) + bar bounds | **ELIGIBLE** |
| 3 | `{side}_refill_ratio` (per bar) | Σ restored ÷ Σ removed over the bar's refill events (None when no refills) | as row 1 | **ELIGIBLE** |
| 4 | `{side}_refills_w` (trailing rolling sum, window=10 bars) | Σ of row 2 over the last 10 bars incl. current | as row 1 | **ELIGIBLE** |
| 5 | cancel event (`kind='cancel'`), `cancel_qty = max(removed − traded_at(p), 0)` | qty decrease at a persisting price minus the TRADE-TAPE volume printed at exactly p in the interval; only emitted if that difference > 0 | `price_1..5`, `qty_1..5`, `side`, `ts_recv_ns` **plus the trade tape** via `on_trade` (ts, price, size from `TradeExtractor`, i.e. `ltp`/`ltq`/`volume`) | **DISQUALIFIED** — eaten-vs-pulled attribution |
| 6 | `{side}_cancel_qty` (per bar) and `{side}_cancel_qty_w` (rolling) | Σ cancel_qty | as row 5 | **DISQUALIFIED** — sums of row 5 |
| 7 | wall event (`kind='wall'`, "vanishing wall") | a previously quoted level with qty ≥ rolling P90 of the last 500 level sizes, absent now, strictly inside the side's current span, AND traded_at(p) < 0.2 × qty; cancel_qty = qty − traded | `price_1..5`, `qty_1..5`, `side`, `ts_recv_ns` **plus the trade tape** (the traded-fraction test) | **DISQUALIFIED** — requires the traded-fraction attribution |
| 8 | `{side}_walls` (per bar) and `{side}_walls_w` (rolling) | counts of row 7 | as row 7 | **DISQUALIFIED** — counts of row 7 |

Helpers / plumbing (not features, listed so nothing is unclassified): `ProxyEvent` (event record), `_Pending` (pending-refill record), `DepthProxyEngine.__init__` (parameters), `on_trade` (ingests the trade tape — DISQUALIFIED input), `_traded_at` (trade-tape volume at a price — DISQUALIFIED input), `_p90` (rolling P90 of level sizes — depth-only intermediate, used only by the wall rule), `on_snapshot` (the diff-by-price engine that emits rows 1, 5, 7), `aggregate` (bar binning + rolling sums for rows 2-4, 6, 8), `snapshot_to_book` (parses `price_i`/`qty_i`, i=1..5, into a price→qty dict; zero/absent levels excluded), `main` (CLI replay: feeds `TradeExtractor` trades into `on_trade`, so the CLI output as shipped is trade-tape-dependent).

Intermediates NOT promoted: `removed` (raw qty decrease at a persisting price) and the P90-level in-range disappearance are aggressor-free observables inside the same code path, but the file does not emit them as features — only the attributed `cancel_qty`/wall calls — so they are NOT added to the ELIGIBLE list here (adding them would be a new feature, not an evaluation of the existing code).

## Classification summary
- **ELIGIBLE (depth-only, no trade tape):** refill events → `bid_refills`, `ask_refills`, `bid_refill_ratio`, `ask_refill_ratio`, `bid_refills_w`, `ask_refills_w`. Computable by feeding `on_snapshot` only (never calling `on_trade`); the refill rule does not consult `_traded_at`.
- **DISQUALIFIED (need eaten-vs-pulled / trade-tape attribution):** cancel events + `{side}_cancel_qty`, `{side}_cancel_qty_w`; wall events + `{side}_walls`, `{side}_walls_w`. Reason: their definitions subtract or test trade-tape volume at a price; on this feed 94.2% of depth intervals carry no trade print, so the subtraction is forced to zero and the label is a tape artefact (background fact).

## Existing JSON outputs (CP0 step 4)
`analysis/2026-07-14/`, `analysis/2026-07-20/depth_proxies_NIFTY_FUT.json`, `analysis/2026-07-20/depth_proxies_BANKNIFTY_FUT.json`, `research_scratch/joinroot/2026-07-20/`:
**NOT FOUND on this machine** (Spotlight + `find` over the home directory: no `depth_proxies_*.json`, no `joinroot`, no `orderflow_engine/analysis/`), and **0 keys** matching `depth_proxies` in the S3 archive. They were produced by the CLI, which replays a local `data/<date>/` tree that exists only on the recorder host; that host's paths are off-limits under hard rule 1. Their key structure and value ranges are therefore **NOT MEASURED** in this run. What the CLI would have written, from the code: `{day, symbol, approximation_notes[4], event_counts{refill,cancel,wall}, rows[per tick-bar: start_ts_ns, end_ts_ns, bid/ask_refills, _refill_ratio, _cancel_qty, _walls, and rolling _w variants]}`.

## Self-check
AST definitions in the file (15): DepthProxyEngine, ProxyEvent, _C, _Pending, __init__, _p90, _traded_at, aggregate, main, on_depth, on_event, on_packet, on_snapshot, on_trade, snapshot_to_book.
Each name appears in this document: ALL PRESENT

## Gate
ELIGIBLE features exist (the refill family) → **CP0 GREEN**. Carried forward: bid_refills, ask_refills, bid_refill_ratio, ask_refill_ratio, bid_refills_w, ask_refills_w (levels=5, the file's own window).
