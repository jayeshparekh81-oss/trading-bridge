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

---

## Module R4 — Levels & Context Engine

The daily "map": reference levels R6 scores location against. Two paths — INTRADAY
(`levels.run`, replays recorded ticks → session VWAP + volume profile) and
DAILY/HISTORICAL (`levels.daily`, vendored Dhan v2 fetch → pivots / prior levels).
Output `analysis/{date}/levels_{symbol}_{sid}.parquet` + `vwap_{...}.parquet` +
`levels_summary.json` (gitignored, S3-excluded — same policy as R3). The
`LevelRegistry.distance_to_nearest()` is R6's entry point.

### Knob classes — an explicit doctrine distinction
Not every knob must ship inert. Two classes:
- **Descriptive-context knobs** MAY ship **functional-uncalibrated** — they only
  label/measure context and never fire a trade decision on their own. Examples:
  `gap_threshold_pct` (gap up/down/flat band), `volume_profile.bin_size`,
  `vwap.bands`. They ship with sensible working defaults, marked UNCALIBRATED.
- **Signal-firing knobs** ship **INERT (0/off)** — anything whose non-zero value
  would emit a discrete signal/flag a strategy could act on. Examples:
  `hvn_threshold` / `lvn_threshold` (HVN/LVN node flags), and R3's
  `bigprint.notional_threshold`, `depth.ofi_enabled`.
When adding a knob, classify it: does a wrong value merely mislabel context, or
does it fire a signal? The former may ship functional; the latter ships inert.

### Levels knob catalog (`tape_config.yaml` → `levels:`)

| Knob | Default | Class / status | Calibrate from |
|---|---|---|---|
| `vwap.bands` | [1.0, 2.0] | descriptive, functional | keep 1σ/2σ unless evidence says otherwise |
| `vwap.snapshot_every_trades` | 100 | structural, functional | output granularity vs file size |
| `volume_profile.bin_size.{class}` | 5.0 / 0.5 / 1.0 | descriptive, functional-UNCALIBRATED | tick size + price scale per instrument |
| `volume_profile.value_area_pct` | 0.70 | structural | standard 70%; rarely changed |
| `volume_profile.hvn_threshold` | 0 | **signal, INERT** | volume-per-bin distribution (e.g. bins > pXX of total) |
| `volume_profile.lvn_threshold` | 0 | **signal, INERT** | volume-per-bin distribution (low-node quantile) |
| `pivots.set` | classic | structural | only set implemented |
| `prior_levels.gap_threshold_pct.{class}` | 0.3 / 0.5 | descriptive, functional-UNCALIBRATED | distribution of open-vs-PDC gaps |
| `historical.cache_dir` / `daily_lookback_days` | cache/historical / 60 | structural | lookback covers prior-week + pivots |

### Calibration procedure (levels)
1. Replay N clean days → dump per-instrument volume-per-price-bin distributions.
2. Set `hvn_threshold` / `lvn_threshold` from that distribution (e.g. HVN at a high
   quantile of bin volume, LVN at a low quantile) so node flags are rare/meaningful.
3. Dump the open-vs-PDC gap distribution → confirm `gap_threshold_pct` splits
   gap/flat sensibly per class.
4. Confirm `bin_size` gives a readable profile (not 1 giant bin, not thousands).

### Historical fetcher — vendored, not imported
`levels/historical.py` is a **minimal vendored** Dhan v2 client (stdlib urllib,
sync, atomic parquet cache, ≤90-day/≤5-year pagination). The backend/pine_replica
client is **neither imported nor modified** — orderflow_engine stays self-contained
(it would otherwise drag in `app.core`/`app.schemas`/redis/per-user async). Token
via `recorder.creds`; security_id via `recorder.scrip_master`.

### `levels.run` daily merge + `--require-daily`
By default `levels.run` merges daily/pivot levels only when the historical cache
exists, degrading to **intraday-only** offline. Pass **`--require-daily`** on
Monday-evening runs to FAIL LOUDLY if the cache is missing rather than silently
produce a partial map.

### R3/R4 addendum (footprint + Initial Balance) — new knobs, UNCALIBRATED

**R3 footprint matrix** — each bar now carries a `footprint` (JSON: `price_bin →
[buy_vol, sell_vol]`) accumulated per price level × aggressor side, plus a
**stacked-imbalance detector** (diagonal bid×ask): `buy_vol[P] ≥ ratio ·
sell_vol[P−bin]` (and the sell mirror) across ≥ `stacked_min_levels` consecutive
bins → a `STACKED_IMBALANCE` tape event.

| Knob (`tape:` → `footprint:`) | Default | Class / status | Calibrate from |
|---|---|---|---|
| `bin_size.{class}` | 1.0 / 0.1 / 1.0 | descriptive, functional-UNCALIBRATED | tick size / price scale |
| `imbalance_ratio` | 0 | **signal, INERT** | diagonal-ratio distribution (e.g. 3:1) |
| `stacked_min_levels` | 3 | structural | run length that reads as a real stack |

**R4 Initial Balance** — `IB_HIGH` / `IB_LOW` = high/low over the first
`initial_balance.minutes` of the session, added to the LevelRegistry (queryable by
`distance_to_nearest_level`) and the levels summary. Founder-validated level type
(BANKNIFTY IB-breakout); the flow-confirmation logic lives in R6, not here.

| Knob (`levels:` → `initial_balance:`) | Default | Class | Calibrate from |
|---|---|---|---|
| `minutes` | 60 | descriptive, functional | standard 60-min IB; rarely changed |

---

## Module R5 — Option-Chain Analytics

Reconstructs each index's chain from replayed option ticks + `manifest.json`
(strikes/expiries) and derives OI/ΔOI, **offline IV+Greeks** (BSM from the
contemporaneous index spot), PCR, max-pain, ATM-IV, basis, a GEX proxy, and a
price×OI buildup matrix. `python -m chain.run --date … [--index NIFTY]` →
`analysis/{date}/chain_{index}.parquet` + `chain_summary.json`. R0 captures **no**
IV/Greeks (verified), so R5 computes them — no R0 change, no Monday risk.

### Knob catalog (`tape_config.yaml` → `chain:`)

| Knob | Default | Class / status | Calibrate from |
|---|---|---|---|
| `risk_free_rate` | 0.065 | functional-UNCALIBRATED | prevailing short rate; low IV-sensitivity |
| `day_count` | 365 | structural | convention (also the T year: day_count·86400 s) |
| `greeks_t_floor_s` | 300 | functional | 2026-07-15: floors intraday T at 5 min so √T never 0 in the closing-auction regime; below 5 min greeks are meaningless anyway |
| `iv_sanity_min` | 0.03 | functional | 2026-07-15: backed-out IV below this → `iv_suspect` flag (real NIFTY ATM IV floors ~8-10%; <3% = degenerate, exclude from greek calibration) |
| `spot_staleness_s` | 5 | descriptive, functional | spot tick cadence (Monday check #2) |
| `snapshot_interval_s` | 60 | structural, functional | grid granularity vs file size (0 = per-tick) |
| `delta_oi_windows_s` | [60,300,900] | structural | signal horizons |
| `contract_size.{index}` | 75/35/65/140/20 | functional | scrip-master lot size (WARN on mismatch) |
| `gex.regime_flag_threshold` | 0 | **signal, INERT** | net-GEX distribution vs observed pin/accel |
| `buildup.window_s` | 300 | structural | ΔOI horizon |
| `buildup.price_threshold_pct` / `oi_threshold_pct` | 0 | **signal, INERT** | move-size distribution per class |
| `iv_percentile.min_days` | 20 | structural | percentile stability vs recency |

### GEX convention (a calibration subject, not a constant)
Net GEX uses the standard **SqueezeMetrics-style** dealer convention — **call
gamma positive, put gamma negative** (net dealer gamma), flip = the zero-crossing
of cumulative signed GEX across strikes. This **sign and scale is itself
UNCALIBRATED**: validate it against observed **pin / acceleration** behaviour on
replay (does price actually pin near the flip in positive-gamma regimes and
accelerate away in negative-gamma?). The net GEX + flip are computed and logged,
but the **regime flag is INERT** (threshold 0) until that validation is done.

### IV/Greeks — offline, edge cases
BSM (stdlib `math.erf`, no scipy). Per snapshot, per strike: IV by bisection on σ
in the no-arb band, then Greeks. **Edge cases:** expired (`T≤0`) → IV/Greeks None;
price ≤ intrinsic or ≥ underlying → IV None (deep ITM/OTM / stale / arb); **spot
missing or stale → last-known spot used with `spot_stale=True`**, or None IV if no
spot ever seen. Coverage is reported honestly per index (`strikes_with_iv /
strikes`, `spot_missing`) — e.g. the salvaged 2026-07-09 day shows `0/22 [SPOT
MISSING]` yet still yields PCR / max-pain / buildup / ΔOI from OI+volume alone.
Snapshots fire on a 60s grid **and on-demand at R3 big-print / velocity-spike
timestamps** (loaded from `tape_events.parquet` when present) — the moments R6
will ask "what was IV doing?".

### Calibration procedure (chain)
1. Replay N clean days → dump distributions of net GEX, per-strike ΔOI, buildup
   move sizes, ATM-IV.
2. Set `gex.regime_flag_threshold` where the regime flag becomes meaningful, and
   validate the GEX sign/scale against observed pin/accel (above).
3. Set `buildup` thresholds so "significant" fires rarely/meaningfully.
4. IV-percentile is UNCALIBRATED until `min_days` sessions accrue (it builds day
   by day into `analysis/iv_history/{index}.parquet`).

### Spot-proxy interim mode (2026-07-13 finding)
The first full live day proved the IDX_I index spots delivered **zero packets**
(no NIFTY_SPOT/BANKNIFTY_SPOT/VIX files at all) — so offline IV had no spot.
Interim: `chain.spot_proxy: future_fallback` (default) uses the index FUTURE's
price as spot-proxy for IV/greeks/GEX when the real spot never ticked — WARNED in
the log and marked `spot_source: future_proxy` in chain_summary (Glass Box: never
a silent substitute); `strict` restores no-spot→no-IV. **Bias note:** the proxy
adds a basis offset to IV levels (future ≈ spot + basis) — acceptable for
percentile/relative use (the IV-history series), flagged for absolute use.
`basis` itself stays None under the proxy (it would be trivially ~0). The IDX_I
subscription ROOT FIX is a separate gated R0 task (investigate FULL-mode vs
TICKER-mode subscriptions for index instruments).

### ⚠️ Two Monday sanity-checks (the offline-IV dependency)
1. **Spot population** — offline IV needs the index spot ticking. On the salvaged
   2026-07-09 day `BANKNIFTY_SPOT` / `NIFTY_SPOT` are empty (disk-full, cut short),
   so IV is `0/N`. **Confirm spots populate normally on Monday's clean day** before
   trusting IV; `chain_summary.json` surfaces `spot_missing` per index.
2. **ts-cadence for IV alignment** — spot and option `ts_recv_ns` are receipt
   timestamps; IV at a strike tick uses the *last-known* spot (staleness-flagged
   beyond `spot_staleness_s`). Sanity-check on the first real day that the spot
   ticks frequently enough that `spot_stale` is rarely set during active trading.

> Intraday time-decay refinement: `T` is currently day-granular (with a half-day
> floor on expiry day). Intraday `T` decay is a post-calibration refinement.

---

## Module R6 — Confluence Signal Engine (the brain)

The scored/explained/gated layer. `python -m signals.run --date D [--index NIFTY]
[--long-only|--short-only]` replays a day through **R3+R4+R5+R6 in one pass**
(composite consumer) and writes `analysis/{date}/signals.parquet` (glass box — one
row per candidate) + `signals_summary.json`. Long and short are first-class
mirrors. `fire_threshold` ships at **999 (INERT)** — the engine evaluates and
explains but fires NOTHING until calibration lowers it.

> ⚠️ The package is `signals/` (plural) on purpose — `signal` is a Python stdlib
> module and would shadow it (breaking asyncio + `recorder`'s `import signal`).
> The yaml config key is still `signal:`.

### Knob registry (`signal:`)
| Group | Knob | Default | Status |
|---|---|---|---|
| fire | `fire_threshold`, `short.fire_threshold` | 999 / 999 | **INERT** — calibration lowers |
| components | `components.{name}.{enabled,weight}` (9 components) | book_ofi 25, big_print 20, queue_imbalance 15, vwap_value_location 15, cvd_confirm 10, level_zone 5, tape_velocity 5, regime 5, pain_map 0 | weights UNCALIBRATED; `book_ofi`/`queue_imbalance` STUB (0) until R1 depth; `pain_map` INERT (weight 0) |
| short | `short.weight_overrides.{name}` | {} (falls back to long) | UNCALIBRATED |
| params | `component_params.*` (windows/mins/ticks) | see file | UNCALIBRATED |
| ofi (graded) | `component_params.ofi_min` (per-instrument magnitude floor) | NIFTY_FUT 2000 / BANKNIFTY_FUT 1000 / _default 1500 | **HYPOTHESIS-FROM-1-DAY (2026-07-15)** — noise floor; refine via 15-day leak-proof test |
| ofi (graded) | `component_params.ofi_scale` (per-instrument typical STRONG per-bar \|OFI\|) | NIFTY_FUT 15000 / BANKNIFTY_FUT 7000 / _default 10000 | **HYPOTHESIS-FROM-1-DAY (2026-07-15)** — signed OFI of floor+scale → activation 1.0; refine via 15-day test |
| regime | `regime.vix_low/high`, `trend_ma_bars/slope_min`, `participant_oi_bias`, `use_gex`, `gex_flag` | 12 / 18 / 20 / 0 / neutral / true / false | vix + bias UNCALIBRATED; `gex_flag` INERT |
| asym gate | `asymmetric_gate.strong_*_penalty`, `disable_countertrend` | +10 / +10 / false | UNCALIBRATED |
| gates | `gates.*` (first_minutes, cutoff, max_trades, one_open, cooldown, liquidity, expiry_theta) | 5 / 14:45 / 3 / true / 300 / stub / 14:00 | liquidity STUB (0) until depth |
| exits | `exits.*` (partial_fraction, chandelier_k_long/short, thesis_stop_buffer, sleeper_minutes, momentum_death 2-of-2) | 0.5 / 3 / 3 / 2 / 60 / 2 | UNCALIBRATED; momentum_death live flags = cvd_flip(+ofi_flip when OFI on) |
| exits (R-stab) | `exits.stop_slippage_ticks` / `tick_size` / `min_stop_atr` / `min_stop_pct` / `atr_bars` | 2 / 0.05 / 0.3 / 0.03 / 14 | 2026-07-16; stop floor + slippage. min_stop_* HYPOTHESIS-FROM-2-DAYS |

### Calibration order-of-operations (which knobs first)
1. **Structure before thresholds.** First replay N clean days with `fire_threshold`
   still inert and read the glass box: distribution of long/short SCORES, component
   activations, gate-rejection reasons. Confirm components activate sensibly.
2. **Regime knobs** (`vix_low/high`, `trend_*`) — a wrong regime poisons the
   asymmetric gate + the regime component. Set these from the VIX + trend
   distributions before touching thresholds.
3. **`fire_threshold`** — set from the score distribution so fires are rare and
   high-confluence (start high, lower until the fire rate is sane). Long and short
   separately.
4. **Exit knobs** last — with fires happening, sweep `chandelier_k`, `partial_fraction`,
   `sleeper_minutes`, momentum-death `conditions_required` to maximise expectancy (R).
5. **Weights** only after 1–4 look right — and only via Sweep 2.0 (≤3 at a time).
6. `book_ofi`/`queue_imbalance`/liquidity come alive once R1 depth data exists.

### Plateau / perturbation doctrine (Sweep 2.0)
`python -m signals.sweep` sweeps **≤3 knobs** (a hard budget guard — more is an
overfitting risk) and reports a **plateau**: we want a broad, stable region where
the metric holds (`is_plateau` = ≥2 combos within tolerance of the best), NOT a
lone sharp peak that won't survive live. `signals.perturb` then nudges the chosen
knobs ±δ and asserts the metric doesn't collapse (`robust`). A setting that only
works at one exact value is rejected. Calibrate to plateaus, not peaks.

### Pain-map hypothesis (Rothschild lens, INERT weight 0)
Trapped traders fuel the move that forces their exit: trapped LONGS
(long_buildup gone offside + long_unwinding) must SELL → downside fuel; trapped
SHORTS (short_buildup + short_covering) must BUY → upside fuel; max-pain is a
magnet into expiry. Computed + logged now (weight 0), raised post-calibration once
the buildup-matrix + ΔOI signals are validated on replay.

### Monday-evening end-to-end sequence (first clean recorded day)
```
D=2026-07-13
# 1) tape (bars/CVD/big-prints/velocity/footprint)
python -m tape.run    --date $D
# 2) levels (VWAP/profile/IB + daily pivots — fetch daily OHLCV first if needed)
python -m levels.daily --symbol NIFTY --from 2026-05-01 --to $D
python -m levels.run  --date $D --require-daily
# 3) chain (IV/Greeks/PCR/max-pain/GEX) — confirm spots populate (spot_missing=false)
python -m chain.run   --date $D --index NIFTY
# 4) signal — evaluates + explains; fires NOTHING at inert 999 (expected)
python -m signals.run --date $D
# then read analysis/$D/signals.parquet (the glass box) and begin calibration
# order-of-operations above; sweep with signals.sweep (<=3 knobs, plateau-first).
```

---

### Gate anchoring note (`first_minutes_no_entry`)
This gate anchors to the **first observed tick of the dataset/replay**
(`SignalEngine._first_ts`), NOT to exchange open 09:15 IST. On a full clean session
the first tick ≈ 09:15 so they coincide; on a **partial/late-starting day** (e.g.
salvaged 2026-07-09, data begins ~10:02) "first 5 minutes" is measured from that
first tick, not 09:15. Revisit during calibration if a session-open anchor is
preferred (an R6 change; R6 frozen until Monday validation).

---

## Module R7 — Telegram Alerts (send-only skeleton)

Consumes R6's glass-box output (`analysis/{date}/signals.parquet` +
`signals_summary.json`) and formats/dedups/dispatches alerts. `python -m alerts.run
--date D [--dry-run|--send] [--min-score X] [--daily-summary] [--top N]`. Ships
INERT: `alerts.enabled=false`, so `--send` is a no-op until armed. Credentials come
ONLY from env (`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`, see `.env.example`); the
token is never printed or logged. A send failure logs WARN + returns False — alerts
are an OUTPUT, never a dependency.

> **R7 live wiring is DEFERRED until R6 is calibrated.** `alerts/hook.py`
> `on_signal_fired(payload)` is the documented seam the running engine will call in
> real time; nothing calls it today. The plan's p95<2s acceptance applies to that
> live wiring later, not to this skeleton. Chart-snapshot rendering is NOT built —
> `AlertPayload.image_path` is a reserved stub only.

### Knob registry (`tape_config.yaml` → `alerts:`)
| Knob | Default | Meaning |
|---|---|---|
| `enabled` | **false (INERT)** | master toggle — nothing is sent while false |
| `transport` | telegram | telegram (send-only) \| dryrun |
| `send_timeout_sec` | 5 | per-request timeout |
| `send_retries` | 2 | retries after the first attempt (+ exponential backoff) |
| `retry_backoff_sec` | 1.0 | base backoff; doubles each retry |
| `cooldown_sec` | 300 | suppress a repeat (instrument, side) within this window |
| `min_gap_sec` | 10 | minimum gap between ANY two sends |
| `max_alerts_per_day` | 20 | spam guard (hard cap) |
| `persist_state` | true | `alerts_state.json` → same-evening rerun won't re-send |
| `daily_summary_top_n` | 5 | top-N candidates in the daily-summary message |
| `truncate_max_chars` | 4096 | Telegram hard limit; drop lowest-weighted components first |

Env (never in yaml, never committed): `ORDERFLOW_TELEGRAM_BOT_TOKEN`,
`ORDERFLOW_TELEGRAM_CHAT_ID` — NAMESPACED, with **no fallback** to the live
system's bare `TELEGRAM_BOT_TOKEN` (asserted by
`test_no_fallback_to_live_bare_telegram_names`).

> **FOUNDER DECISION 12 Jul — R7 shares the live bot (single-inbox).** The live
> token also lives in `orderflow_engine/.env` under the `ORDERFLOW_*` names
> (placed by the founder — a deliberate feed, not an inherited env). **TRIPWIRE:**
> any rate-limit event or late/missed live alert → dedicated R7 bot same day.

### Gate representation (honest, not enriched)
The alert shows gates exactly as R6 records them: R6 logs only the FIRST failing
gate in `gate_reason` (or `""` when entry is allowed). R7 renders that as
`gates: ✅ passed` or `gates: ⛔ <reason>` — it does NOT fabricate a full
per-gate passed/failed list. A richer per-gate trace is a **calibration-season
candidate** (would require an R6 change; R6 is frozen until Monday validation).

### Evening ritual (after the Monday chain runs)
```
python -m signals.run --date $D                      # writes signals.parquet
python -m alerts.run  --date $D --dry-run --daily-summary   # one summary message
python -m alerts.run  --date $D --dry-run --min-score <X>   # inspect real candidates' formatting
# once R6 is calibrated + armed: set alerts.enabled=true, export TELEGRAM_*, use --send
```

### Monday-evening check (R7 exit block)
On the 2026-07-13 replay, the R7 alert **exit block must show a real `thesis_stop`
and `1R`** (not `—`). The `—` seen on the salvaged 2026-07-09 dry-run was because
that day was **levels-degraded** (no daily cache → the exit planner had a thin
registry, and non-fired candidates carry no exit plan). If the exit block is still
`—` on the clean Monday day, **investigate the levels → R6 exit-planner wiring
before calibrating** (the thesis-stop is sourced from the R4 LevelRegistry).


---

## Calibration-season notes (parked observations)

### Gap-threshold recalibration (2026-07-15) — verify was mis-measuring, not the data
`gap_threshold_s=3.0` + verify's flat "any gap → PARTIAL" (aggregate over all 10
watched instruments) guaranteed EVERY clean day reported PARTIAL, so G0 never
started. Diagnostic on the 2026-07-15 clean full-day (1,739 raw gaps):
- **(a) 96% is index CADENCE noise.** Gap count collapses **1,734 → 78 at 5s →
  23 at 10s**; watched-instrument median quiet 3.3-4.3s, p95 ≤5.1s. Index spots
  have ZERO gaps >10s. A sub-10s quiet on an index is normal cadence, not a fault.
- **(b) ~~The ONE real gap: a ~445s simultaneous lull~~ → CORRECTED 2026-07-16, see
  below.** The ~445s "gap" across ALL index futures (NIFTY 445.2 / BANKNIFTY 445.8 /
  FINNIFTY 447.2 / MIDCPNIFTY 446.0 / SENSEX 361) **ends at 09:15:00 = MARKET OPEN.**
  It is the **pre-open no-trade window** (connect ~09:07 → first tick at the 09:15
  opening auction), NOT a feed pause. The tell was in plain sight — all futures
  resolve at the *same* instant *and that instant is market open*; a real feed pause
  wouldn't align to 09:15:00. Originally mislabeled here as "the one real hole"; it
  was never a hole. See the 2026-07-16 pre-open fix below.
- **(c) options/equities/VIX are already exempt** — `gap_check=false`, so the
  watchdog never watches them; only 5 index futures + 5 index spots are watched
  (VIX `gap_check=false` too). The old premise "illiquid option strikes" was wrong.

Fix: `gap_threshold_s` 3→10 (config.yaml watchdog — effective next restart; +
verify_session GAP_THRESHOLD_S for reclassifying existing days). Verdict is now
SCOPED to liquid tradeables (NIFTY_FUT/BANKNIFTY_FUT) and OUTAGE-based: PARTIAL
only on a single liquid gap >60s (LIQUID_GAP_OUTAGE_S), reconnect/disconnect, or
coverage <95% — thin futures + spots keep logging gaps but don't drive the verdict;
session-end open-ended gaps are excluded. ~~**Standard preserved: the 445s lull still
→ PARTIAL.**~~ (CORRECTED 2026-07-16: the 445s was pre-open, not a lull — see below.)
FOLLOW-UP CANDIDATE: non-monotonic futures volume is a SEPARATE chronic
PARTIAL driver (Dhan feed volume quirk, flags every day incl. 07-15) — likely needs
the same "is-this-real?" recalibration before clean days truly PASS.

### Non-monotonic futures-volume recalibration (2026-07-15) — feed jitter, not corruption
The verify "future volume decreased N times" flag was the last chronic false PARTIAL
(every day: 07-13/14/15). Diagnostic:
- **Quantify:** 8 decreases across ~167K future rows on 07-15 (**0.005%**), magnitudes
  30-520 contracts. Liquid futures single ≤0.018% / summed ≤0.022% of max daily
  volume (NIFTY 2.9M). FINNIFTY reads **0.667%** for a trivial 60-contract dip ONLY
  because its daily volume is tiny (9,000) — the reason the verdict must be liquid-scoped.
- **Root cause (evidence, not guess):** (1) OUT-OF-ORDER/STALE feed packets — the drop
  packet's **`ltt` steps BACKWARD** (BANKNIFTY 13:31 ltt 1784122273→**268**; 13:34
  449→**448**; MIDCPNIFTY 728→**705**), a `V→V+δ→V→V+δ` transient at 3-15ms spacing; the
  ltt-sorted count resolves most of these (BANKNIFTY 3→1, MIDCPNIFTY 1→0). (2) PRE-OPEN
  corrections — NIFTY 09:05 `910→845` and it STAYS (same ltt), the exchange adjusting
  indicative auction volume before open. NOT our consolidation (files ts_sorted=True,
  drops present in ts order), NOT a roll (same contract, drops 30-520 not a reset),
  NOT a post-lull reset (445s lull was 09:15, volume never collapsed).
- **Downstream: harmless.** `tape/trades.py:55` `if dvol <= 0: return None` — a decrease
  emits NO trade (skipped as "repeat/correction"), so CVD/bars aren't fed negative
  deltas. Only residual: `_last_volume` absorbs the dip into the next trade's size,
  bounded by summed decreases (≤650 NIFTY contracts vs 2.9M daily = <0.02%). Cosmetic.

Fix (measurement, NOT the standard): verify keeps the raw decrease COUNT + magnitudes +
an ltt-sorted observability line, but the VERDICT fires only on a REAL reset, LIQUID-
scoped (NIFTY_FUT/BANKNIFTY_FUT): a single decrease > VOLUME_RESET_PCT (1%) of max vol
(a genuine reset collapses to ~0 = ~100%), OR summed > VOLUME_BUDGET_PCT (0.5%). Today's
liquid jitter (≤0.018%/≤0.022%) sits ~55x/~23x under the bars. A genuine reset (collapse
+ stays low) still PARTIALs — proven by test. After this + the gap fix, 07-15's ONLY
remaining verdict driver was the ~445s "feed hole" — ~~real~~ which the 2026-07-16
pre-open fix (below) showed to be the pre-open no-trade window, so 07-15 now correctly
PASSES (verified: first genuinely clean day).

### Pre-open gap exclusion — market-open clock (2026-07-16) — THIRD verdict correction
The ~445s (07-15) / ~433s (07-16) "liquid feed hole" was the **pre-open no-trade
window**: index FUTURES don't trade 09:07–09:15, so the watchdog logs a connect→
09:15:00-opening-tick gap on NIFTY_FUT/BANKNIFTY_FUT **every single day**. It was
masked on 07-13 (disk crash) and 07-14 (43% coverage) by bigger real PARTIAL drivers,
so it never surfaced alone until 07-16 — the first otherwise-clean day — where it would
have false-PARTIALed. Fix: liquid-future gaps are **clocked from MARKET OPEN (09:15:00
IST)** — a gap is credited only its POST-open portion (`_market_open_ns`; pre-open-only
→ 0, straddling → minutes after open, mid-session → full duration), symmetric to the
existing session-end open-ended exclusion. `liquid_max_gap_raw_s` keeps the pre-clip
value for observability. Tests: pre-open 433s → 0 (PASS); mid-session 120s → 120
(PARTIAL); straddle 09:10→09:20 → 300s (only post-open). **4-day re-audit with all
three fixes: 07-13 PARTIAL (disk+84.6% cov, real), 07-14 PARTIAL (43.4% cov, real),
07-15 PASS (clean), 07-16 clean gap-driver so far (pre-open clips 433.4→5.8s).** The
two genuinely-bad days still PARTIAL for their real reasons — verifier not broken the
other way.

> ⚠️ **GOVERNANCE — verdict logic has now been corrected THREE times** (gap threshold
> 3→10, volume magnitude verdict, pre-open market-open clock) — all three were
> pre-first-clean-day blind guesses that only surfaced against real recorded days.
> **NO further verify verdict changes without a full re-audit of ALL recorded days
> (07-13 onward), showing each day's status + driver, and confirming the known-bad
> days still PARTIAL for real reasons.** If a clean day still fails AFTER this, the
> finding is REAL — do not tune the verifier to make it green. The verifier has spent
> its benefit of the doubt.

**G0 — Day-1 = 2026-07-15 (PASS).** With the pre-open fix, 07-15 verifies PASS: the
first clean recorded session. **This is NOT goalpost-shifting.** 07-15's *data* was
always clean — 100.5% coverage, single uninterrupted session, spot/VIX live, no
reconnect/disk/real-gap; the only thing that changed is the *verifier* stopped
counting the pre-open no-trade window as an outage. The data didn't move; the blind
ruler did. **G0 counter starts 15 Jul 2026** (Day-1). Track consecutive clean-day
PASSes from here — this is the "≥N clean days" denominator every calibration/predictive
test (OFI, levels, regime, max-pain) draws from. NOTE the deployed container still runs
the OLD verifier until a post-15:40 rebuild, so same-day auto-`report.json` may read
PARTIAL until then — re-run verify manually on finalized data for the true verdict.

### ⛔ realized_r has NEVER existed — there is no outcome baseline (2026-07-16)
**`realized_r` has never existed. Every expectancy / outcome claim to date was null.
The scoring baseline is real; there is NO outcome baseline.** Why, in code: `fire_threshold`
ships at 999 (INERT); max observed score is 46.4; `engine.py` `fired = adj_thr<999_999
and score>=adj_thr` is therefore always False → `_fire` never runs → a `SimPosition` is
never created (`_fire` is its only constructor) → `_on_new_bar`'s `pos.step()` never runs →
every row keeps its initial `realized_r = None`. Confirmed by our own summary line
`fired: 0  net R: 0`. What exists and is real: the SCORE distribution (candidates,
component activations, firing rates, gate rejects, ceiling). What does NOT exist: any
simulated trade, R-multiple, expectancy, win-rate, or PF. The exit simulator was fully
written and fully un-executed. **The first honest net number will be IN-SAMPLE on 2 clean
days (07-15, 07-16) — a pipeline SMOKE TEST proving we can compute an after-cost PF at all,
NOT a G2 result** (G2 needs walk-forward + permutation over ≥15 clean days, none built).
Build order agreed: (b) exit engine → (a) threshold → (c) cost model.

### Exit-engine MVP (2026-07-16, item (b)) — four corrections before any trade fires
Done ahead of lowering the threshold, so the FIRST `realized_r` we ever produce isn't
garbage. `signals/exits.py` + `signals/engine.py` (`momentum_flow_flags`, a pure testable
fn) + config:
1. **Side-aware momentum-death.** `_flow_flags` now takes `side`; a flag is True only when
   flow turned AGAINST the OPEN position — `cvd_flip = cvd_slope*sign < 0` (long: slope<0,
   short: slope>0), `ofi_flip` mirrors it. Was side-BLIND (`cvd_slope<0` for everyone) → a
   winning short was killed exactly when its thesis worked. Locked by test.
2. **velocity_die DROPPED.** It was `not velocity_spike` — true ~94% of bars because the
   spike threshold is UNCALIBRATED (an always-on constant, not a death signal). Removed
   from the count until velocity has a real spike threshold; re-add then.
3. **Honest denominator.** `big_print_opposite` (INERT: notional_threshold=0) and
   `level_reject` (unbuilt) were hardcoded False — DROPPED, not counted. `ofi_flip` is
   emitted only when `depth.ofi_enabled`. Live flags = `cvd_flip` (+`ofi_flip` when OFI on)
   and `conditions_required = 2` = the real count (no more "2-of-5" lie). Consequence:
   **with OFI off only 1 flag is live < 2 → momentum-death is DORMANT**; stop / 1R-partial→BE
   / chandelier trail / sleeper carry all exits until OFI (or another calibrated signal)
   brings a 2nd flag online.
4. **Stop slippage.** Stops no longer fill at the exact stop price: `stop_slip =
   stop_slippage_ticks × tick_size` (config, default 2 × 0.05 = 0.10 for index futures),
   applied ADVERSE (long fills below stop, short above). Knobs in `signal.exits`.
Tests (`tests/signals/test_exit_engine.py`, both directions): winning short survives the
flow bar; dead flags not emitted; conditions_required == live-flag count; dormant at 1 live
flag, fires at 2; stop fills strictly worse than the stop level. Suite 426 passed, 1 skipped.
KNOWN-DEFERRED (not this MVP): `thesis_stop_buffer_ticks` is applied as a raw PRICE offset
(`stop = base − 2.0`) — its "ticks" name is a misnomer (2.0 price = 40 ticks at 0.05),
pre-existing, flagged not fixed. Momentum/sleeper/session exits fill at bar close without
slippage (only STOP fills slip) — next-step if it matters.

### R-stability: stop-distance floor + buffer-in-ticks (2026-07-16) — make R a real unit
The thesis stop is the nearest STRUCTURAL level (registry: VWAP bands / POC/VAH/VAL /
IB / pivots / PDH-PDL-PDC / PWH-PWL / daily), fallback 0.5%. With a dense ladder (NIFTY_FUT
07-15: 22 levels over 476pt, min inter-level gap 0) and entries that fire NEAR levels by
design (vwap_value_location, level_zone), the nearest level is often ~0 pts from entry →
**near-zero R → exploding R-multiples.** MEASURED before-floor long-stop distances:
NIFTY_FUT 07-15 min 0.73pt (0.003%) / med 12.5pt / max 49.6pt; **07-16 min 0.02pt (0.000%)**;
BANKNIFTY_FUT 07-15 min 1.0pt / med 40.4pt. A 0.02-pt stop makes any move an infinite R.
FIX: `stop = structural, but never CLOSER than max(min_stop_atr*ATR, min_stop_pct%*entry)`;
the structural stop is kept whenever it is WIDER (`stop_source="floor"` marks a bind). ATR =
rolling per-bar True Range over `atr_bars` (14), plumbed via `ctx.atr` (engine `_update_atr`).
Also FIXED the buffer misnomer: `thesis_stop_buffer_ticks` now means TICKS (×`tick_size`) →
buffer 2.0pt → **0.10pt** (2 ticks), as intended.
DEFAULTS min_stop_atr=0.3, min_stop_pct=0.03% — **HYPOTHESIS-FROM-2-DAYS** (measured ATR14:
NIFTY_FUT ~20pt/07-15 ~15pt/07-16; BANKNIFTY_FUT ~64pt/~57pt). Chosen 0.3 over 0.5 because
**0.3 kills the pathological tail yet leaves the MEDIAN structural stop intact** (NIFTY
12.5→12.9pt) whereas 0.5 over-floors (BANKNIFTY median 40→57pt) — the floor is a MINIMUM,
not a median-rewriter. BEFORE→AFTER long-stop (0.3): NIFTY_FUT 07-15 min 0.73→7.2pt (med
12.5→12.9); 07-16 min 0.02→7.2pt (med 10.1→10.5); BANKNIFTY_FUT 07-15 min 1.0→19.4pt (med
40.4→42.6); 07-16 min 1.1→17.4pt (med 19.9→25.8). ~25-45% of bars floored (the tight tail).
Tests: `tests/signals/test_stop_floor.py` — floor binds when structural too tight (both
sides), structural used when wider (both sides), stop never inside the floor across a ladder,
buffer is ticks not raw price, pct backstop when ATR absent. Suite 433 passed, 1 skipped.
REFINE via the 15-day set. NOTE: threshold stays 999 until this lands and R is stable.

> **DESIGN PRINCIPLE — for ALL future floors/caps/guards: a floor kills the pathological
> TAIL, it does not rewrite the MEDIAN.** If a proposed floor moves the median materially
> (as 0.5×ATR did: BANKNIFTY median 40→57pt), it is too aggressive — it's overriding
> legitimate structure, not just clipping noise. Pick the level that removes the degenerate
> tail while leaving the bulk of the distribution untouched. Same logic as `ofi_min`
> (noise floor, not a re-scaler) and the verify verdicts (fire on real outages, not cadence).

TWO CAVEATS ON THESE DEFAULTS (both must stay attached to the numbers):
1. **HYPOTHESIS-FROM-2-DAYS.** min_stop_atr=0.3 / min_stop_pct=0.03% are set from 07-15 +
   07-16 ATR only. Two days is not a distribution — refine on the 15-day leak-proof set
   before treating them as more than a starting hypothesis.
2. **EOD-ladder proxy.** The before/after distribution used the END-OF-DAY level ladder as
   the structural set; the real per-bar registry (VWAP bands / developing POC/VA / IB) MOVES
   intraday — early-session ladders are sparser than EOD. So the measured stop-distance
   distribution is a fair proxy for SHAPE (the tail exists, the floor removes it), NOT the
   exact per-bar stop each fire would have used. The floor CODE uses the live registry; only
   the measurement used the proxy.

### Risk-management research findings (2026-07-16) — calibration/R8 candidates, NOT built
Source: institutional risk-management practice (verified via search 2026-07-16 + known
market-maker / prop-desk practice). Three things our system currently violates or lacks.
All are CANDIDATES — the signal menu stays CLOSED; nothing here is tonight's work, and no
number below is to be guessed into config without the 15-day set + a sweep.

**1. STOP PLACEMENT — "beyond the level, not ON it" (calibration candidate).** Documented:
*"The mistake most traders make is placing the stop ON the level instead of BEYOND it, where
normal liquidity probes occur."* Our code: `stop = structural_level − thesis_stop_buffer_ticks
× tick_size = level − 0.10pt` (2 ticks) — effectively **ON the level**, inside the stop-hunt
zone the founder flags from 15y of tape. NB this is the *thesis-stop buffer*, a separate knob
from the R-stability `min_stop_*` FLOOR (the floor sets the MINIMUM distance; the buffer sets
how far PAST the level the stop sits). CANDIDATE: make the buffer **volatility-scaled** (a
fraction of ATR) instead of a fixed tick count, so the stop clears the liquidity probe.
Decide the fraction from the 15-day set + a Sweep-2.0 plateau — do NOT guess it now.

**2. POSITION SIZING — the missing layer (HARD R8 REQUIREMENT).** Documented: *"Loss size is
determined by POSITION SIZE, not stop distance. A wide stop with small size can risk less than
a tight stop with oversized exposure,"* and *"if volatility expands your stop widens — but
position size must SHRINK to keep risk constant."* Our exit sim models **no quantity**
(`SimPosition.remaining = 1.0` fraction, no lots, no ₹) — see the realized_r note above — so we
**cannot express the core institutional mechanism: hold RISK constant by varying SIZE against
stop distance.** Flag as a hard R8 requirement: **R8 must size = risk_budget / stop_distance,
NOT fixed lots** (fractional-Kelly, the I4 item). Also the **2-lot-minimum reality**: the 1R
partial (`partial_fraction=0.5`) is impossible with 1 lot — the fractional sim assumes it away;
R8 must model integer lots and either require ≥2 lots for the partial or skip the partial at 1.

**3. DAILY LOSS LIMIT / DRAWDOWN BRAKE — absent (R8 candidate).** Documented institutional rule
set: cut risk after drawdown, halt after N consecutive losses, rebuild smaller; plus an
ATR-regime rule — *when 14-day ATR rises above its 6-month median, drop risk per idea 25–50%.*
We have `gates.max_trades_per_day=3` but **NO daily loss limit, NO consecutive-loss halt, NO
vol-regime risk scaling.** D1 (post-win size-down) is in the plan but unbuilt. CANDIDATE for R8
(these are RISK gates, not signal components — they don't touch the closed menu).

**Myth-correction (for the record).** *"Professionals don't use stop losses"* is **FALSE** —
they use predefined risk relentlessly; some via hard stops, some manual/mental, but the risk is
**always predefined**. Market makers delta-hedge instead of stopping; large directional funds
use mental stops + scaled exits because their SIZE would be seen on the tape. **Neither is our
situation — we are small enough to use real hard stops**, which is what the exit engine models.

### Stop-probe-depth MEASURED on our data (2026-07-16) — empirically confirms "we sit in the sweep zone"
Tool `research/stop_probe_depth.py` (read-only). For each registry level, per fresh touch,
classify PROBE (wicks past L then closes back on the origin side — level held) vs BREAK
(continues), forward window K=5 bars; report the probe-depth distribution. Result on 07-15+
07-16, NIFTY_FUT + BANKNIFTY_FUT: **73–93% of level touches are PROBES**; probe depth median
**0.17–0.37 ATR**, p75 **0.46–0.67 ATR**, **p90 ~0.76–1.17 ATR**. Our 0.10pt buffer sits far
INSIDE even the median probe (4.7–25.5pt) → **empirical proof our stop is ON the level and gets
swept**, confirming 15y of the founder's tape reading. Buffer to clear p75 ≈ 0.5 ATR; to clear
p90 ≈ 1 ATR — both far above 0.10pt. **COST: a 0.5-ATR buffer ~DOUBLES median R (NIFTY 12.6→24.7pt,
BANKNIFTY 40.5→83pt); a p90 (~1-ATR) buffer ~TRIPLES it.** Not a free fix — a trade-off.
**N=2 IS UNSTABLE — the two days disagree materially** (NIFTY p90 28.6 vs 14.8pt; BANKNIFTY
break rate 0.26 vs 0.065). **NO number goes near config** — the 15-day set decides. Caveat:
EOD-ladder proxy (intraday registry moves), so shape not exact per-bar.

**THREE competing answers to the sweep problem — the 15-day set must quantify all three (menu
CLOSED, do NOT build):**
1. **Buffer approach** (calibration candidate, §"beyond the level" above): wider stop, SAME entry,
   buffer ~0.5–1 ATR to clear p75/p90 → **2–3× the R denominator**. You keep being the liquidity,
   just further out.
2. **Sweep-entry approach** (I1, "trade the machine's shadow" — ENTRY-TIMING candidate, AFTER
   G2 / v3). Enter AFTER the sweep, not before: level swept → RECLAIMED → entry, stop below the
   sweep low (TIGHT, not wide). Inverts the trade-off — you stop BEING the liquidity and start
   FOLLOWING it. Same/tighter stop, LATER entry, but **misses the probes that never reclaim**
   (and the 7–27% that break). This is a SIGNAL change (entry logic), not a buffer change — it
   does NOT touch the closed component menu; it's a v3 entry-timing item.
3. Status quo (0.10pt buffer) — demonstrably swept; the null to beat.
Buffer vs sweep-entry are **competing**, not additive: buffer = wider stop / same entry / 2–3×R;
sweep-entry = tighter stop / later entry / fewer fills. The 15-day set should measure BOTH
against the status quo before either earns a config number or a menu slot.

### GEX predictive-vs-descriptive — measurement tool built, verdict PENDING 15+ days
QUESTION (founder, 2026-07-15): chain.run's net_GEX is a DAY-AGGREGATE (hindsight). GEX
is built from OI (largely prior-day frozen), so an EARLY read might be PREDICTIVE of the
day's realized behaviour — or only descriptive after the fact. **GEX stays weight-0 until
answered.** TOOL: `research/gex_predictive.py` — per day: EARLY net_GEX + gamma-flip from
ONLY the first-N-min chain snapshots (strict no-look-ahead, default N=15 → 09:15-09:30);
REALIZED NIFTY_FUT outcomes (range, range%, realized-vol std, pin proxy |close-max_pain|
+ time-within-Xpts, trend proxy |close-open|/(H-L)); EOD net_GEX + early-vs-EOD SIGN
agreement. FIRST LOOK (3 usable days — NOT a conclusion):
| date | early_GEX | EOD_GEX | sign | range% | trend | pin_t% | note |
|---|---|---|---|---|---|---|---|
| 07-13 | +1.10M | -0.18M | FLIP | 1.08 | 0.01 | 15.6 | future_proxy spot (unreliable) |
| 07-14 | 0 | -88.1M | FLIP | 0.30 | 0.60 | 83.6 | early window had NO chain (broken AM) → early=0 artifact |
| 07-15 | +1.54M | +2.10M | SAME | 0.98 | 0.21 | 12.7 | clean (real spot, full chain) |
Sign agreement 1/3 — BUT the 2 "FLIP"s are CONFOUNDED (07-13 proxy spot, 07-14 no early
chain), not proven intraday instability. The one clean day (07-15) agrees in sign. 07-09
skipped (no spot, net_gex=0), 07-10 skipped (no chain). VERDICT NEEDS 15+ CLEAN days
(real spot, chain from open); do not weight GEX until then. Tests: no-look-ahead
(post-window snapshot ignored) + outcome metrics on a synthetic fixture.

**`research/gex_predictive.py` IS THE TEMPLATE for every component's predictive test.**
The pattern, mandatory for any feature before it earns weight:
(1) extract the EARLY read with a STRICT no-look-ahead window + a test that PROVES
    post-window data cannot leak in (see test_early_gex_ignores_post_window_snapshots);
(2) compute realized outcomes INDEPENDENTLY of the read;
(3) state N, state the confounds, and REFUSE to conclude below the sample bar (15+ clean
    days). Anecdote is not signal; discipline over result.
**CANONICAL LEAK EXAMPLE (why (1) is non-negotiable — proven on our own data, 2026-07-15):**
in the BANKNIFTY constituent lead-lag, a CENTERED velocity window (which peeks forward)
manufactured a STRONG fake signal — "cash leads future +10s, corr **+0.41**" on 07-13.
Switching the SAME analysis to a CAUSAL/trailing window DESTROYED it: corr **−0.06**. A
look-ahead of a few seconds fabricated a 0.41 correlation out of nothing. Every predictive
read MUST be leak-proof AND have a test that proves post-window/future data cannot leak in;
a strong result from a non-causal window is worthless. This is the single most valuable
finding of the 07-15 session.
The SAME test must eventually run for each still-unproven component — each stays weight-0
or unchanged until ITS OWN test passes on 15+ clean days:
- **book_ofi** (already wired, weight-0 pending flip + this test) — see the OFI note above.
- **VWAP / levels** — does the MORNING level (VWAP / prior-day / ONH-ONL) predict the
  day's reaction (bounce/reject), or only describe it? [[orderflow_r0_recorder]]
- **regime / VIX bands** — is the early VIX-band regime read predictive of realized vol?
- **max_pain** — does the early max_pain predict the close's pin, or drift with OI intraday?

### queue_imbalance weight 15 → 0 (2026-07-15) — burden-of-proof inversion, code kept
Config change (`signals/config.py`): queue_imbalance weight **15 → 0**. Changes NOTHING
functionally — it's an unbuilt `None` stub already contributing 0; this makes the config
HONEST about the real score ceiling instead of reserving 15 phantom points on faith. The
pure function (`tape/depth_imbalance.py::queue_imbalance`) + its tests are KEPT (cheap,
and needed for the revival test).
- **Evidence (N=1, 07-15, NIFTY_FUT / BANKNIFTY_FUT):** QI predictive corr(QI[t],ΔMid[t+1])
  = **+0.030 / +0.009** vs OFI +0.070 / +0.133; incremental R² over OFI = **+0.0007 /
  +0.0001** (negligible); orthogonal to OFI (corr +0.015 / +0.045) but non-predictive.
  L1-only QI same (+0.019 / +0.012).
- **Mechanism:** QI's documented edge is a sub-100ms EVENT-level effect (queue race / fill
  probability) in tight-spread EQUITIES; our feed is **~200ms SNAPSHOTS of index FUTURES**
  — the effect is washed out by sampling + different microstructure.
- **STANDING RULE:** queue_imbalance stays at **weight 0** until a formal **15-clean-day
  predictive test** (`research/gex_predictive.py` template, strict no-look-ahead) earns it
  back. N=1 is a first look, not a verdict — the CODE stays, the PHANTOM WEIGHT goes. This
  is the template's discipline applied to a weight, not just a flag.

### OPEN CALIBRATION QUESTION (founder, 2026-07-15) — assumed weights vs measured weights
The v2 component WEIGHTS (book_ofi 25, big_print 20, vwap_value_location 15,
queue_imbalance 15, cvd_confirm 10, level_zone 5, regime 5, tape_velocity 5; pain_map 0)
are LITERATURE-INFORMED HYPOTHESES, not fitted to our data. The current calibration plan
tunes component THRESHOLDS but ASSUMES these weights. **Open question: should each
component's weight be DERIVED from its own measured predictive power (via the same
no-look-ahead template as `research/gex_predictive.py`) rather than assumed?** Early
evidence already contradicts the assumed numbers: queue_imbalance (assumed 15) shows
~zero predictive corr + negligible incremental R² over OFI on 07-15 (recommend re-weight
to 0 pending a 15-day test); book_ofi (assumed 25) shows a real but modest edge (73-77%
sign agreement). DECIDE THIS BEFORE CALIBRATION CONCLUDES — tuning thresholds on top of
wrong weights bakes the hypotheses in. Proposed approach when ≥15 clean days exist: run
the predictive template per component, rank by measured edge (corr / incremental R² /
sign-agreement), and set weights proportional to measured predictive power — with the
same discipline (refuse to weight a component that fails its own test). Related: the
score ceiling is already only 40 with 3 components dead (below), so weights matter less
than getting the dead components live/dropped first.

### Intraday time-to-expiry — greeks fixed for 0-DTE (2026-07-15, urgent for R8 18-19 Jul)
**(a) ROOT CAUSE = integer-day T.** `_time_to_expiry_years` used `(expiry−session_date).days`
(a FLAT half-day floor on expiry day), so within a day T never changed → 0-DTE greeks were
degenerate and intraday theta never decayed. We trade WEEKLIES (0-DTE every Tuesday), and
R8 needs greeks precisely on expiry day (expiry-guard/time-stop/strike-selection). FIX:
T now measures to the expiry-day **15:30 IST close** per snapshot, in years
(`day_count·86400 s`); `greeks_t_floor_s`=300 floors the final minutes; `days<0 → None`
kept (past expiry). PROOF (07-14 0-DTE ATM CE 24100, OLD vs NEW): **IV recovered ~7% → ~17%**
(plausible NIFTY territory) and **theta now grows/decays through the session** (−45k→−65k/yr,
then collapses as the option dies) vs OLD flat-T. 07-15 (6-DTE) unchanged — ATM delta
0.515→0.516, gamma/vega still peak at ATM (no regression). HONEST CORRECTION to the Q3 audit:
the near-close ATM delta ~0.008 was NOT the bug — near-binary delta at 0-DTE close is CORRECT;
delta is robust to the T/σ tradeoff (same option price). The real degeneracy was the **IV**
(and thus theta); delta didn't need "recovering."
**0-DTE IV-sanity flag:** new `iv_suspect` column (schema) = `iv < iv_sanity_min` (0.03) so R8
+ calibration EXCLUDE degenerate near-intrinsic reads instead of learning from them — flag,
not drop (observability).
**(b) PROXY-SPOT BASIS ERROR (not retroactively fixable):** days where spots were dead and the
chain used `spot_source=future_proxy` (07-13, and any pre-IDX-fix day) computed delta/gamma
against the FUTURE price, off by basis (fut ≈ spot + basis) — DEGRADED, exclude from
greek-based calibration. Real spot since 07-15 fixes it going forward, not the past.
**(c) PRE-FIX RECORDED DAYS have degenerate expiry-day greeks** (flat-T): any day recorded
before this fix has unreliable 0-DTE greeks + no intraday theta decay. Re-running chain on
those days with the new engine re-derives correct greeks from the stored ltp/spot (as the
07-14 proof did); the raw ticks are fine, only the derived greeks were wrong. Files: chain
engine/config/schema + 2 test-fixture timestamp fixes (07-13 base) + intraday-greeks tests.
**PENDING GATED ITEM (do NOT do tonight):** Re-run chain on ALL recorded days after the
intraday-T fix to re-derive correct greeks (raw ticks unaffected). Priority before R8
calibration — every pre-fix day carries degenerate expiry-day IV/theta, so calibrating on
them poisons exactly the expiry-day regime R8 depends on.

### BANKNIFTY constituent lead-lag — footprint detection, NOT participation (I1)
**FRAMING (mandatory, incl. any customer-facing text):** we are NOT replicating the Jane
Street pattern — that is manipulation and ILLEGAL. We DETECT its footprint: observation,
not participation. This is **I1 "trade the machine's shadow."** Hypothesis: to move
BankNifty you must move its cash constituents, so causality may FLIP from future-leads
(arbitrage, no edge) to cash-leads when the index is being driven.
Tool: `research/constituent_leadlag.py` (weighted 5-bank basket vs BANKNIFTY_FUT cross-
correlation both directions + regime split + big-print event study; leak-proof tests).
**FIRST LOOK (3 days — NOT a conclusion):**
- **The headline is METHODOLOGICAL:** a CENTERED velocity window (look-ahead) manufactured
  a spurious "cash leads future +10s, corr 0.41" on 07-13; switching the regime classifier
  to a CAUSAL/trailing window collapsed it to **−0.06**. The signal was a leak artifact.
  This is why every predictive test must be leak-proof — vindicated in the data.
- Leak-proof result: **no robust cash-leads-future signal** across 3 days. 07-15 (clean)
  shows the EXPECTED arbitrage shape (future-leads in normal windows −5s corr 0.12,
  co-movement in high-velocity). 07-14 (0-DTE, thin) shows a weak cash-lead (+0.12) but is
  noisy. Big-print event study: future forward returns after a bank cash print are ~0–1 bps,
  no consistent per-bank driver (HDFC/ICICI/etc.).
- **UNIVERSE GAP:** we record 5 of ~12 BANKNIFTY constituents = **78.5%**; MISSING **21.5%**
  (IndusInd, BoB, PNB, Federal, IDFCFirst, AU, Canara…). And **CASH ONLY — no constituent
  futures**; Jane St's documented pattern used constituents AND their futures, so a
  futures-led push is INVISIBLE to us. The missing 21.5% + no-constituent-futures could
  each invalidate a negative result — absence of footprint here is NOT absence of footprint.
- **STANDING RULE:** stays weight-0 / non-component (menu is CLOSED). Needs a 15-clean-day
  leak-proof test before any claim; N=3 with confounds (leak, thin 0-DTE, universe gap) is a
  first look only.
- **OPEN ITEM — universe expansion (do NOT act; post-G2 scope decision):** a NEGATIVE result
  here is NOT a disproof — with 21.5% of the index unrecorded AND no constituent futures, we
  may simply be looking in the wrong place. Recording the 7 missing banks + constituent
  FUTURES is a config/scope decision for AFTER G2, not now.

### OPEN ITEM — FII/DII participant-OI as a data asset (do NOT act until the legal gate clears)
NSE publishes participant-wise OI (FII/DII/Pro/Client, futures+options) daily post-close;
archive is file-per-day back years. Founder hypothesis ("DNA crack"): EOD FII bias + our
intraday orderflow trigger = highest-conviction trade. Decision: middle path — ingest as a
PASSIVE data asset (it only accrues forward, so start the clock) but do NOT wire/calibrate.
**HARD GATE: verify the archive-file download is ToU-clean for internal use BEFORE writing
any ingester** — NSE ToU restricts automated site scraping; don't build on grey. Honest test
(when data exists): **H0 = delta-adjusted, momentum-controlled day-over-day change in FII
positioning has NO predictive relationship with next-session returns** (metric: IC / decile
forward-return spread). Known flaws to respect: FII futures shorts are often cash-hedges not
bear bets; "FII" is a blend of hundreds of funds incl. MMs/arb; options OI is contracts not
delta; the futures-hedge component can't be separated from the aggregate. The FII-standalone
claim is backtestable on the multi-year archive; the COMBINED claim needs **6-12 months
forward** (our orderflow only starts Jul 2026). Menu stays CLOSED — data-asset + test only.

### Score-distribution baseline (2026-07-15, pre-OFI) — the REAL ceiling is 40, not 60
`research/score_distribution.py` (read-only on signals.parquet). 280 candidates: median
10.0, p90 19.6, **max 27.9**; nothing near fire_threshold (999, inert). **THREE**
weight-bearing components are always-zero, each a DIFFERENT root cause (parquet flags,
code diagnoses):
- **book_ofi (25)** — wired 2026-07-15, GATED off (`depth.ofi_enabled=false`) → activates on the flip.
- **queue_imbalance (15)** — STILL an unbuilt `None` stub (`signals/context.py:59`, never
  assigned in engine) → a genuine no-op, the SAME bug OFI was. Only book_ofi got wired.
- **big_print (20)** — BUILT (`recent_big_print_side`) but detector `notional_threshold=0`
  (INERT/uncalibrated) → activates when the threshold is calibrated, not dead code.
So the **CURRENT max achievable score = 100 − 25 − 15 − 20 = 40** (pain_map is weight-0
inert-by-design). Observed max 27.9 = **70% of the 40 ceiling** — candidates reach what's
currently reachable; the ceiling is the problem. After the OFI flip the ceiling rises to
**65 (not 100)** — queue_imbalance (unbuilt) + big_print (uncalibrated) still zero 35 pts.
LIVE components: cvd_confirm(10)/vwap(15)/level_zone(5)/regime(5)/tape_velocity(5). No
redundant live pair (max co-fire Jaccard cvd&regime 0.48). Only gate that rejected:
`after_session_cutoff_14:45` (36). NIFTY 160 / BANKNIFTY 120.

**Short-side penalty clarification (confirmed in code):** `apply_asymmetric`
(`signals/regime.py:69`) escalates the counter-trend side's THRESHOLD (base 999 → 1009 in
a STRONG bull/bear regime), stored as `threshold` vs `base_threshold` in engine.py:132 — it
NEVER lowers the score, and only fires in a strong regime (07-15 was `neutral` → no
escalation, threshold==base==999). So shorts scoring HIGHER on 07-15 (median 13.0 vs long
9.6) is a DAY characteristic (gap-up / resistance rejection), NOT a missing penalty.

### Book OFI wired end-to-end (2026-07-15) — data limitation + validation + candidate
R1 depth OFI is now computed in the tape engine (`tape/engine.py.on_depth` →
`book_ofi`, per-bar `ofi` column, gated on `depth.ofi_enabled`, still OFF) and
plumbed to signals (`ctx.book_ofi`, `ofi_flip`). Three parked facts:

**(a) Dhan 20-depth is a ~200ms THROTTLED SNAPSHOT feed, NOT event-level.** Median
inter-snapshot 201ms, p95 402ms, p99 ~480-510ms (~5 Hz), measured on the
2026-07-15 clean full-day (NIFTY_FUT + BANKNIFTY_FUT). So the OFI here is
**bar-aggregated over ~200ms snapshots**, not the tick-by-tick book-event OFI the
Cont/Kukanov/Stoikov paper assumes. Known, permanent data limitation — use OFI
aggregated over a bar window, never react per-snapshot. There are also occasional
large gaps (the ~445s gap on 2026-07-15 is the pre-open window, connect→09:15 open —
see the pre-open correction above; genuine intraday lulls also occur) — the
`depth.ofi_gap_guard_s` knob (default 5s) skips any increment across such a gap so it
can't emit a spike (correct behavior for the pre-open window too).

**(b) Validation numbers (2026-07-15, offline `book_ofi` on the two futures):** OFI
is non-degenerate (std 92 BANKNIFTY / 395 NIFTY, ~33% nonzero, symmetric
percentiles) and MEANINGFUL — positive vs mid-price change with **directional
sign-agreement 73.4% (NIFTY) / 76.7% (BANKNIFTY)** on nonzero OFI (corr +0.070 /
+0.133; low raw corr is expected at 200ms/L1, which is why OFI is used
bar-aggregated). Book integrity: 20 levels 0 nulls, 100% bid/ask ts-paired,
crossed/locked ~0.005% (guarded by `book_ok`).

**(c) Multi-level OFI — calibration candidate.** `book_ofi` is L1-only (best
level) though we capture all 20 levels. A depth-weighted multi-level OFI (sum L1..LN
contributions) would likely lift the correlation; separate calibration-season item,
not built. The flip + live validation is a gated pre-market item (config value
`depth.ofi_enabled` stays false until then).

**(d) GRADED ACTIVATION FIX (2026-07-15) — the binary-gate catch.** The first
`ofi_enabled=true` re-run exposed that `book_ofi` was a **binary 0/25 gate**:
`_clamp01(signed - ofi_min)` at `ofi_min=0` saturates to 1.0 on OFI *sign* alone, so
on a directional day every long earned the full 25 and every short 0 — a coin-flip
dressed as a signal, re-expressing the day's drift (activation was literally
`{1.0: 140, 0.0: 140}`; top-of-book scores inflated into the low 50s; long/short
skew 61/39). Fix: a per-instrument magnitude **floor** (`ofi_min`, noise below it
earns nothing) plus a per-instrument **scale** (`ofi_scale`, the typical STRONG
per-bar |OFI| that maps to activation 1.0), so `(signed − floor)/scale` clamped to
[0,1] gives a real gradient. NB the seed values come from the **per-BAR** |OFI|
distribution (NIFTY med ~8.8k, BANKNIFTY med ~4.1k), NOT the per-increment std
(395/92 in note (b)) — seeding from the per-increment std would re-saturate. Graded
re-run result: activation now `min 0.010 / med 0.571 / max 1.0` with only 24/116
firing candidates saturated at 1.0 (79% partial); OFI fire-rate 41.4% (the floor
drops the weak-magnitude bars that used to earn 25 on sign); nothing crosses 50;
long/short top-56 skew softened 61/39 → 59/41 but did **not** vanish (2026-07-15 was
an up-drift day and OFI stays net-positive). **One day cannot separate "OFI leads
price" from "OFI re-expresses drift"** — grading made the *mechanism* honest (graded
magnitude + noise floor, no sign-saturation), but the residual lean's predictive
value is exactly what the 15-day leak-proof test must decide. Wiring real, edge
unproven — `ofi_min`/`ofi_scale` are `HYPOTHESIS-FROM-1-DAY` (registered above).

**PRE-REGISTERED OFI TEST (falsifiable, write it down before the data arrives).**
The FIRST question the 15-day leak-proof test must answer, ahead of any P&L/edge
metric: **does `book_ofi`'s side-skew flip with the drift, or persist regardless?**
On 2026-07-15 (an up-drift day) OFI leaned LONG (top-56 skew 59/41; fires 53% of
longs vs 30% of shorts). The clean test: **on down-drift days, does the skew flip
SHORT?**
  - If OFI leans SHORT on down days and LONG on up days → it tracks the day's
    direction, i.e. **drift-following, REJECT as signal** (it's just re-expressing
    the trend, the exact failure the binary gate hid).
  - If the side-skew is decorrelated from the day's net drift — OFI sometimes leans
    *against* the day and that lean *precedes* price — → candidate signal, proceed to
    the predictive/edge test.
Metric: regress per-day OFI side-skew (long-share of top-N) on the day's net return;
a near-1 slope = drift-following = fail. Requires ≥15 clean days spanning both up and
down drift. Standard leak-proof discipline: trailing-only windows, no look-ahead,
refuse to conclude below 15 clean days. Until this passes, `depth.ofi_enabled` stays
false and `book_ofi` weight is inert-by-gate.

### Bogus-epoch `ltt` on quiet strikes (BENIGN)
Some non-trading option strikes carry a placeholder `ltt = 315532800`
(= 1980-01-01 UTC) — seen on `FINNIFTY_CE_26150`, 2026-07-09 replay. Benign for
ordering: the replay total-order key is `(ts_recv_ns, ltt, class, sid, i)` with
`ts_recv_ns` PRIMARY (`replayer/engine.py:116`), so a bogus `ltt` only affects
tie-ordering at an identical receive-instant (still deterministic), never a row's
position in time. R3 classification (prev-price tick rule) and R5 IV (uses ts) are
unaffected. Any future `ltt`-based analysis must treat `ltt <= ~3.16e8` as "no real
last trade", not a 1980 date.

### Regime asymmetric gate: any-bull vs STRONG-bull (calibration candidate)
`apply_asymmetric` escalates the counter-trend threshold on ANY
`direction=='bull'/'bear'` (`signals/regime.py:73-78`) — the docstring says
"strong" but `direction` has no strength gradation, so a mild bull triggers the
full `strong_bull_short_penalty`. Calibration: define "strong" (trend slope beyond
a threshold, vol band, or a regime-confidence score) and gate the penalty on it.
R6 change — apply during calibration season, not before.

### 13 Jul disk incident (first live day)
Root disk hit the 2GB disk-guard floor at 14:33 IST (build-cache ~3.5GB from the
12 Jul hotfix + first full-day volume ~7.6GB). Writes paused/dropped 14:33-15:30 —
tail lost; EOD consolidation did not run in-session (salvage flow used instead).
Fix applied: docker builder prune + old rollback tags removed + root EBS 29G->96G
(74G free). **G0 clock restarts 14 Jul.** Ops-runbook candidate: a post-build
`docker builder prune` step after every backend image build.

Post-incident audit findings (13 Jul evening):
- **R1's disk guard DID trip** — 14:33:04, 46s before R0's (independent 60s poll
  phases) — but it logs under the SHARED `recorder.diskguard` logger name
  (`recorder/diskguard.py:74`), so a quick tail of the depth container reads as if
  no pause happened. **Observability candidate: per-daemon log tags** (e.g. pass a
  logger prefix into DiskGuard) so R0/R1 guard events are distinguishable at a glance.
- **Teardown hang (both daemons):** `run_session`'s `await asyncio.gather(*tasks)`
  never returns after record_end because the feed task's `async for message in ws:`
  blocks on an idle-but-open websocket (ping/pong keeps it alive past close); stop
  is only checked between connections. First production record_end (today) exposed
  it; consolidation/verify/backup never ran in-session. Fixed-by-restart tonight +
  code fix gated separately.
- **Depth parts explosion:** flush_interval_s=2 -> ~8,795 parts/instrument/day
  (158k files); naive per-part consolidation writes ~10-row row-groups (metadata
  dominates: 127MB half-file) and can OOM the 1G container. EOD consolidation must
  ACCUMULATE rows to ~64k per row-group (done in tonight's salvage); code fix +
  a larger depth flush_interval are calibration-season candidates.

### PENDING GATED ITEM — WIND_DOWN empty-session re-entry (source fix, future pre-market)
14 Jul: the recorder main loop runs a session for phase in {CONNECT, RECORD,
WIND_DOWN} (`main.py:712`), but `_session_clock` ends any session the instant
`_now() >= record_end` (`main.py:574`). WIND_DOWN is 15:35-15:40
(`scheduler.py:31,77-78`), so after the real session consolidates (~15:37 for
435 instruments) the loop RE-ENTERS run_session for empty core-only sessions
until 15:40. Each empty session used to (A) overwrite manifest.json core-only and
(B) zero the core finals via `_finalize_primary`. **This recurs EVERY day** (not
just restart days); masked before the 07-13 teardown fix because sessions hung at
record_end instead of cleanly closing/re-entering. Tonight's fixes (manifest
MERGE + no-clobber-nonempty-final, committed on feat/orderflow-r7-alerts) make
the empty sessions HARMLESS (defense-in-depth), but the trigger still fires.
SOURCE FIX (gated, future pre-market — NOT tonight): stop re-entering run_session
after the day's session has ended — treat WIND_DOWN as non-recording in the loop
(`main.py:712` -> `{CONNECT, RECORD}`) or add a per-day "session already ran"
guard. Blast radius = recorder main loop only; live-recorder-runtime change, so
deploy-gated. Until then, harmless but noisy (2-3 empty "25 instruments, 0 rows"
closes at ~15:37-15:39 daily).
