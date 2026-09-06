# CP1 — DEEP-BOOK FEATURE BUILD (levels 6–20; new module `deep_book.py`; `research/depth_proxies.py` untouched and not imported)

Inputs only: `price_N`, `qty_N`, `orders_N` (N = 1..20), `side`, `ts_recv_ns`. Sides aligned at each 5-second bar end (last snapshot per side with age ≤ 2 s; side 0 = bid, 1 = ask per `recorder/depth_schema.py`, verified on the data in CP0 by the ladder-direction check). Consecutive-snapshot diffs are BY PRICE (never by level index), gap guard 5 s.

| # | feature | definition | trade tape / aggressor needed? |
|---|---|---|---|
| 1 | `deep_imb_qty` (signed state) | (Σqty L6–20 bid − Σqty L6–20 ask) / (Σ bid + Σ ask), sampled at bar end | no |
| 2 | `deep_imb_orders` (signed state) | same with `orders_N` | no |
| 3 | `slope_diff` (signed state) | slope_bid − slope_ask; slope = OLS slope of log(qty_N) on N over levels with price>0 and qty>0 (≥ 3 levels) — a FIT, stated | no |
| 4 | `conc_diff` (signed state) | conc_bid − conc_ask; conc = Σqty L6–20 / Σqty L1–20 per side | no |
| 5 | `wall_appear_{bid,ask}` (+ `_w` trailing 10-bar sum) | a price present now and absent in the previous snapshot of the same side, at level index ≥ 6 now, qty ≥ rolling P90 of deep level sizes (last 500 per side, refreshed every 25 snapshots), lying strictly inside the previous snapshot's price span | no |
| 5 | `wall_disappear_{bid,ask}` (+ `_w`) | a price present before at level ≥ 6 with qty ≥ P90, absent now, strictly inside the current span — APPEAR/DISAPPEAR only, never "eaten" | no |
| 6 | `deep_refill_{bid,ask}` (+ `_w`) | run-1 refill construction at deep levels: price present in both snapshots at level ≥ 6 in both, qty drops (pending k = 5 snapshots), then rises at the same price → refill | no |

Gate check: no implemented feature consumes the trade tape or an aggressor tag; nothing removed; 10 tested features (4 signed states + 6 count `_w` features) ≥ 2.

**REASONING, not measurement:** at levels 1–5 a level-size decrease is ambiguous between "eaten" and "pulled" because trades print at the touch and the tape shows almost none of them; at levels 6–20 the mid would have to travel 6+ levels for resting size there to be eaten, so within a 200 ms snapshot interval a deep decrease is more likely a cancel than a fill. This argument is stated only to explain why deep wall features are less contaminated in principle. It is NOT used: nothing is labelled eaten or pulled; the module counts appear/disappear and refill only.

## Self-check (one full session, 2026-07-14 NIFTY_FUT, independent code path: pandas masks + per-row `np.polyfit` for the state; array/`np.isin` event loop)
State features: `deep_imb_qty`, `deep_imb_orders`, `conc_diff` match with max |diff| 0; `slope_diff` max |diff| 3.4e-16. Events: module 158,070 vs independent 158,070 — **IDENTICAL** per kind and side (deep_refill bid 33,747 / ask 113,384; wall_appear 2,922 / 2,750; wall_disappear 2,789 / 2,478).
Implementation note recorded: the pending-refill bookkeeping was changed from a list scan to a per-price FIFO dict before any run (same definition; the independent path uses the same FIFO semantics and matches).

## Gate
**CP1 GREEN** — 10 aggressor-free deep-book features.
