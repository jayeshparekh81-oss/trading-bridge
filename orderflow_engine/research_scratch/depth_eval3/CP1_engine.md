# CP1 (run 3) — FIRST-PASSAGE ENGINE (`first_passage.py`; `research/depth_proxies.py` imported unmodified for the L1–5 refill events only)

- Anchor: mid at the event bar end, mid = (bid1 + ask1)/2 from the depth rows (each side ≤ 2 s old). No trade tape.
- Path: the snapshot-level mid series (every depth timestamp, ~200 ms) after the anchor, within the session.
- σ (stated, never peeks forward): σ_1m = std of the 5-second mid changes over the trailing 360 bars whose window ENDS AT THE PREVIOUS BAR (changes with index ≤ i−1), × √12 → a 1-minute-equivalent realised volatility; undefined with fewer than 120 changes (so nothing is scored in the first ~10 minutes and events before 09:25 have no σ).
- Joint object, computed ONCE for EVERY bar with orientation +1 (a −1 orientation swaps up/down): first-passage times to ±k·σ for k ∈ {0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0} (NaN = never reached before the session's last snapshot; `censor_s` = time to that last snapshot, so right-censoring is explicit), MFE / MAE / time-to-MFE / time-to-MAE / mid at horizon for {1m, 5m, 15m, 30m, 60m, 120m, close}, in points (bp and σ units derived at scoring from `mid` and `sigma_1m`). Any (stop = a·σ, target = b·σ) hit-first outcome is read off `t_up`/`t_dn` without recomputation.
- Events: F1 = per-bar shallow refill count per side (unmodified engine) above the per-slot 99th percentile (discovery-only thresholds), oriented +1 for a bid-side burst, −1 for an ask-side burst; both sides in one bar → dropped. F2 = F1 within TOL = 1.0·σ_1m of previous-clean-session high/low/close (bar-mid series) or the 09:15–09:30 opening-range high/low; eligible after 09:30; undefined on a session with no previous clean session (07-13) — those bars carry `prev_levels_defined = False`.

## Self-check (2026-07-14 NIFTY_FUT, discovery; independent paths)
mid series (92,773 snapshots) via pandas `merge_asof`: MATCHES; bar mid: MATCHES; σ_1m via pandas rolling std: 4,379 defined on both paths, max |diff| 1.2e-14; first-passage times and MFE/MAE by a naive forward scan on 300 random bars: 8,400 values, 0 mismatches; refill counts vs run 1's independently produced parquet: IDENTICAL (bid 671 / ask 1,237).

## Gate
Censoring at 30 m is reported in CP2 from the discovery sample. **CP1 GREEN** (engine reproduces every independent path).
