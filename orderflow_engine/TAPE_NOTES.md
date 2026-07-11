# TAPE_NOTES — Module R3 (Tape Engine)

Analysis layer that turns a **replayed** recorded day into order-flow primitives.
It consumes the R2 replayer's consumer contract (`on_packet` / `on_depth` /
`on_event`) and never the live feed, so it carries **zero runtime risk** to the
R0/R1 recorders. Built 2026-07-11 on `feat/orderflow-r3-tape`.

Run it:
```
python -m tape.run --date 2026-07-13 [--instruments NIFTY_FUT,BANKNIFTY_FUT] [--no-write]
```
Writes `analysis/{date}/` (bars per instrument, `tape_events.parquet`,
`summary.json`) — **gitignored, and excluded from the S3 backup**: analysis is
DERIVED and reproducible from raw via replay. The raw data is the asset;
analysis is cattle.

---

## Calibration doctrine

Every threshold/weight is a config knob in `tape_config.yaml`, defaulted
**UNCALIBRATED**. Two postures:
- **Structural knobs** (bar size, velocity baseline/ratio, cvd window) ship
  *functional* so bars/CVD/velocity produce output immediately for exploration.
- **Threshold detectors** (big-print notional, volume-bar threshold, OFI) ship
  **INERT (0 / off)** so nothing fires on an uncalibrated value.

Real values come from replaying actual recorded days — **starting Monday
2026-07-13** (first clean R0 day + first R1 depth day).

## Knob catalog (`tape_config.yaml`)

| Knob | Default | Status | Calibrate from |
|---|---|---|---|
| `bars.tick_bar_size` | 100 | UNCALIBRATED (functional) | distribution of trades/session per instrument; pick so a bar ≈ a meaningful unit of flow |
| `bars.volume_bar_threshold.{index_fut,stock,option}` | 0 | **INERT** | per-class traded-volume distribution; set to a chosen quantile |
| `classify.method` | `lee_ready` | UNCALIBRATED | validate vs any available aggressor truth; else keep Lee-Ready |
| `classify.trade_size` | `volume_delta` | default | see "trade size" below |
| `cvd.slope_window_bars` | 20 | UNCALIBRATED (functional) | signal horizon you care about |
| `bigprint.notional_threshold.{class}` | 0 | **INERT** | per-class trade-notional distribution; set at a high quantile (e.g. p99) |
| `bigprint.cluster_k` / `cluster_window_s` | 3 / 10s | UNCALIBRATED | observed clustering of large prints |
| `velocity.baseline_bars` | 20 | UNCALIBRATED (functional) | bars/session so the median is stable but responsive |
| `velocity.spike_ratio` | 0.5 | UNCALIBRATED (functional) | velocity-ratio distribution; set below the body of the distribution |
| `depth.imbalance_levels` | 5 | UNCALIBRATED | how deep the book signal should read |
| `depth.ofi_enabled` | false | **off** | enable after R1 depth replay + OFI weight calibration |

## Calibration procedure (sketch)

1. Replay N clean recorded days (`--no-write` for exploration).
2. Dump the empirical distributions per instrument class: trades/session, bar
   durations, trade notionals, velocity ratios.
3. Set each threshold from a chosen quantile of its distribution (e.g. big-print
   notional at p99; velocity `spike_ratio` below the bulk of the ratio body).
4. Re-replay and sanity-check the rates: big prints and velocity spikes should be
   *rare and meaningful*, not firing every bar. Iterate.
5. Record the chosen values + the evidence date in this file when they graduate
   from UNCALIBRATED.

---

## Methodology notes (to VALIDATE against real data Monday)

### Trade size — `volume_delta` (default) vs `ltq`
Dhan FULL packets are **snapshots**, not trade prints (verified on 2026-07-09:
identical rows repeat until a new trade). A trade is counted only when cumulative
`volume` advances; the size is the volume delta.
- **They AGREE** when each snapshot captures exactly one trade and `volume`
  advances by exactly `ltq` (see `test_reconciliation_volume_delta_equals_ltq`).
- **They DIVERGE** when: (a) **multiple trades occur between two snapshots** —
  `volume` jumps by their sum while `ltq` shows only the *last* print's qty, so
  `ltq` undercounts; (b) volume carries adjustments (blocks/corrections) not tied
  to a single `ltq`; (c) a snapshot repeats without a trade (`ltq` is stale,
  `volume_delta` is 0 → correctly no trade). `volume_delta` is the robust default;
  `ltq` is available for A/B on real packets. **Monday: confirm how often Dhan
  emits >1 trade between snapshots** (the divergence driver).

### Aggressor classification — Lee-Ready
Quote rule vs the packet's own contemporaneous top-of-book, tick-rule fallback at
the mid / when the book is absent. Assumed **~80–90% accurate** vs true
order-level aggressor (Lee & Ready 1991); worse for illiquid names and at the mid.
Exact aggressor is unknowable without order-level data. Validate the buy/sell
split against total_buy/total_sell drift where sane.

### Big-print notional
`notional = price × size` (size = traded qty). The **futures lot-size multiplier
is folded into the per-class threshold** — it's a constant per class, so
calibrating the (uncalibrated) threshold absorbs it. If we later want true ₹
notional, multiply by lot size in the classer.

### Determinism
Given the replayer's deterministic total-order stream, the engine's emitted bars
+ events are **byte-identical every run** (`test_determinism_same_replay_same_hash`).
Analysis is therefore always reproducible from raw.

### Depth hooks (R1 data arrives Monday)
`queue_imbalance` and `book_ofi` are structurally correct pure functions but their
weights/thresholds are UNCALIBRATED; `depth.ofi_enabled` stays **off** until we
replay real 20-depth. The engine already wires `on_depth` through per instrument
(latest bid/ask row retained) so calibration is a config flip + weight-setting.
