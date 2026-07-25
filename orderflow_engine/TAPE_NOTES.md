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

### 🚨🚨 MOST IMPORTANT FINDING SO FAR — economic viability / the cost floor (2026-07-16)
Found by the founder looking at ONE fired trade and saying "that's too small." The lone
threshold-25 fire on 07-15 (NIFTY_FUT long) had **R-unit = 7.22 points** (stop source=FLOOR,
`min_stop_pct` 0.03% binding) and won **+0.849R ≈ 6 points**. 6 points is not a tradeable move
once you execute the OPTION. The R-stability floor we shipped kills the 0.02pt landmine but is
set ~3× TOO LOW to be economically viable.

**Round-trip cost ≈ 2 OPTION points** (NIFTY weekly ATM, per lot=75): **spread ~1.0 (dominant,
cross bid-ask entry+exit)** + brokerage ₹40/75 = **0.53** + STT/txn/GST **~0.33**. (Slippage on
stop-outs is extra.)

**A 7pt future R-unit → 3.5 option pts of 1R** (delta 0.5). Cost 2 / 3.5 = **~50-57% of 1R eaten
by costs.** Applied to the fired trade: gross **+0.849R → net ≈ +0.36R**; and its **-1R side would
be ≈ -1.5R net**. **Costs INVERT the payoff asymmetry** — wins shrink, losses amplify.

**MIN-VIABLE-R (derived from COST, not ATR):  min_viable_R (future pts) = C / (k × δ)**  where
C = round-trip cost in option pts (~2), k = target cost fraction of 1R, δ = ATM delta (~0.5):
  - k=20% → **~20pt** · k=15% → **~27pt** · k=10% → **~40pt**.  Sane minimum ≈ **20-27 NIFTY pts**.

**R-unit distribution, all candidates, 07-15+07-16 (EOD-ladder proxy):**
  - **NIFTY_FUT: ~55% of candidates under 15pt R-unit, ~80% under 25pt → only ~20% survive a 25pt
    viability bar.** (medians 11.8 / 14.3pt; many pinned at the 7.2pt floor.) Largely DEAD ON ARRIVAL.
  - **BANKNIFTY_FUT: median 25-42pt → 55-91% survive.** Its ~3× bigger point-moves clear the hurdle.

**THE CRITICAL DISTINCTION — min_viable_R must REJECT, not INFLATE.** Padding a 7pt structural
stop to 25pt does NOT create a 25pt move — it buys a **25pt LOSS on a 7pt move**. So min_viable_R
is a hard ENTRY GATE (don't take the trade), NOT a wider floor on the stop. A naive `max(...,
min_viable_R)` floor would do exactly the wrong thing.

**Proposed (NOT built): floor gains a third term for observability, but the ENTRY GATE is the real
fix** — `R_unit = max(atr_floor, pct_floor, min_viable_R)` only alongside a gate that REJECTS a
candidate whose *structural* stop is < min_viable_R. Config would carry `round_trip_cost_pts`
(~2, the cost model's single most important input) + `cost_fraction_target` (~0.15), per instrument.

**OPEN FOUNDER DECISIONS (do NOT act — needs the 15-day set + founder's call, not a config edit):**
  1. **Instrument primacy:** should BANKNIFTY be the PRIMARY instrument, with NIFTY conditional
     (only when its structural stop is naturally ≥ min_viable_R)?
  2. **Entry gate:** should min_viable_R be a hard ENTRY GATE that rejects sub-viable setups
     (vs the current floor that pads them into fake-size trades)?
  3. **Timeframe mismatch:** `tick_bar_size=100` ≈ 4.5-min bars on NIFTY — does that match a
     30-60min metaorder-ride design, or have we built a SCALPER by accident? The 7pt "trades"
     smell like scalps the cost structure can't support.

This is the cost-model question arriving early. It changes the SHAPE of the strategy (which
instrument, what timeframe, reject-vs-pad) — not a tonight edit. Menu stays closed.

### 🚨 HIGH — LOT-SIZE MISMATCH: data says NIFTY 65 / BANKNIFTY 30, chain config says 75 / 35 (2026-07-16)
Surfaced by accident while building the big-print tool: `derive_lot_size` = GCD of traded
qty on 07-15+07-16 gives **NIFTY 65, BANKNIFTY 30** (every NIFTY_FUT/NIFTY_CE ltq is a
multiple of 65; every BANKNIFTY a multiple of 30). But `chain/config.py:26` hardcodes
`contract_size = {NIFTY: 75, BANKNIFTY: 35, ...}`. If chain used the wrong multiplier,
**every GEX number is off by ~13% (NIFTY 75/65) to ~17% (BANKNIFTY 35/30)** — the +2.1M
(07-15), +1.38M (07-16), -88M (07-14) net-GEX, and the gamma-flip strike levels. Scaling
error, so SIGN and relative shape survive; magnitudes don't.

**INVESTIGATION COMPLETE (2026-07-17) — confirmed a real bug; root fix built on branch
`fix/orderflow-lotsize-scripmaster`, gated (no config value changed).**

**1. Authoritative source (scrip master `SEM_LOT_UNITS`) vs config — 4 of 5 WRONG, all high:**
| index | config | scrip master (truth) | error |
|---|---|---|---|
| NIFTY | 75 | **65** | +15.4% |
| BANKNIFTY | 35 | **30** | +16.7% |
| FINNIFTY | 65 | **60** | +8.3% |
| MIDCPNIFTY | 140 | **120** | +16.7% |
| SENSEX | 20 | **20** | ✅ correct |
Scrip master and the traded-qty GCD agree exactly where both exist. Only SENSEX was right.

**2. Wrong from DAY 1 — not a roll.** `SEM_LOT_UNITS` is CONSTANT across all 7 scrip masters
(07-09→07-17), same Jul-2026 contract (expiry 07-28), no roll in the window. A static hardcode
that never matched the contract.

**3. Only used by GEX — every other chain metric is IMMUNE.** `contract_size` call sites (fresh,
repo-wide): `chain/gex.py:21-45` (`strike_gex`/`net_gex`/`gamma_flip`), read at `chain/engine.py:217`
and live `signals/engine.py:297`, plus the `research/gex_predictive.py` copy. NOT used by greeks,
`max_pain`/PCR (`analytics.py:49-51` use raw OI), atm_iv, IV, or notional.

**4. Magnitude-only taint, with proof of immunity.** `contract_size` is a POSITIVE CONSTANT SCALE
on every strike's GEX, so:
  - TAINTED: `net_gex` MAGNITUDE only. Corrected (verified vs persisted): **07-15 NIFTY +2,101,296
    → +1,821,123 (×65/75); 07-16 NIFTY +1,376,758 → +1,193,190.** BANKNIFTY ×30/35, FINNIFTY ×60/65,
    MIDCPNIFTY ×120/140.
  - IMMUNE (proven in `tests/chain/test_gex.py`): `net_gex` **SIGN** (positive scale can't flip it),
    `gamma_flip` **LEVEL** (the zero-crossing interp has the constant in numerator AND denominator →
    exactly unchanged), plus `max_pain`/PCR/atm_iv/IV/greeks (lot-free).

**5. Nothing retroactively invalid.** GEX weight is **0** (regime flag INERT, direction ignores
gex_sign, gamma_flip scale-invariant) → NO score/gate/fire/exit ever consumed the tainted
magnitude. GEX calibration hasn't started. The only leak was the *logged* net_gex magnitude in
`chain_summary.json`, which nothing reads yet.

**THE ROOT FIX (built, gated):** chain now reads lot from the scrip master's `SEM_LOT_UNITS`
(`chain/lotsize.py` → `ChainEngine.contract_size`, wired in `chain/run.py` + `signals/pipeline.py`
+ `signals/engine.py`; `gex_predictive` uses the same source — no third hardcode). Kills the class
and survives rolls. The config dict stays ONLY as a **loud fallback** (WARNING + `lot_source=
config_fallback` in the summary; fail-LOUD-not-HARD, since GEX is inert and shares the pass with
lot-free metrics). Guard test asserts resolved lot == `SEM_LOT_UNITS` and ≠ config; invariant tests
pin sign + flip. **No config value changed** — the fix is correct without editing the dict, because
config is no longer the source of truth.

**RE-RUN: PARKED as the FIRST STEP of GEX calibration (post-15-day).** Not urgent — nothing consumes
the tainted magnitude today. When GEX calibration begins, re-run `chain` on 07-09→ with the wired
lot so persisted net_gex is correct; sign-based conclusions are already valid.

**GLASS BOX:** `chain_summary.json` per-index now carries `contract_size` + `lot_source`
(`scrip_master` | `config_fallback`). From now on every X-ray STATES where its lot came from — a
fallback is visible in the output, never silent.

**META-LESSON (the reason this survived ~2 months): a hardcoded constant with NO source of truth
behind it drifts silently.** The lot was mirrored into `chain/config.py` and never checked against
the exchange. **RULE: any constant that HAS an authoritative source (scrip master, exchange spec)
must READ that source, never mirror it into config.** Config is for knobs we choose; not for facts
the exchange already publishes.

**AUDIT FOLLOW-UP (filed as a task):** sweep for OTHER hardcoded constants that have an authoritative
source and should read it instead — candidates: `tick_size` (per instrument), `expiry` dates,
`strike_interval`, segment/exchange codes, and any lot/multiplier elsewhere. Each is a latent copy
of this same bug.

### Big-print threshold calibration — first measurement (2026-07-16), N=2 HYPOTHESIS ONLY
`bigprint.notional_threshold` is 0 (INERT) → big_print (weight 20 of 60) contributes ZERO on
every candidate. Measured trade-notional distribution + a LEAK-PROOF forward-outcome test
(`research/bigprint_calibration.py`, mirrors `gex_predictive`: `forward_point_move` /
`max_favorable_excursion` hard-bounded at t+horizon; unit-tested that a tick 1ns past the
horizon is invisible) on 07-15+07-16. Lot size DATA-DERIVED (see mismatch above).

- **Size DOES predict, monotonically — but it's a TILT, not a TRIGGER.** `P(favorable move ≥
  min_viable_R within 60s)` climbs with the notional threshold:
  - **NIFTY_FUT (R=20pt): 1.8% base → 5.7% (p90) → 9.2% (p99) — ~5× lift.**
  - **BANKNIFTY_FUT (R=50pt): 5.0% base → 13.5% (p99) → 15.4% (p99.5) — ~3× lift.**
  Directional hit-rate also lifts (NIFTY h60: 0.362 base → 0.448 at p99) but stays <0.5 at
  most horizons, and mean |move| rises (NIFTY h60 6.2→10.1pt; BANKNIFTY 20.2→36.5pt). So even
  a p99 print reaches viable-R only ~9% (NIFTY) of the time → **big_print is worth ~20/60
  confluence points, NEVER a standalone entry.** My honest read: a tilt, not a trigger.
- **Candidate thresholds — HYPOTHESIS-FROM-2-DAYS, NOT set:** NIFTY_FUT **~₹8.5Cr (p99,
  ≈54 lots)**; BANKNIFTY_FUT **~₹6.6Cr (p99, ≈38 lots)**. p99.5 didn't improve NIFTY's
  cost-link and halved the sample.
- **⚠️ BANKNIFTY high-threshold counts are UNSTABLE across the 2 days** (p99: 89 vs 15 prints;
  p99.5: 44 vs 8) — 07-16 had far fewer big BANKNIFTY prints. The 15-day set MUST resolve this
  before any threshold is trusted.
- **THIRD independent confirmation that BANKNIFTY clears the cost floor better than NIFTY**
  (after: the R-unit distribution above, and the min_viable_R survival rates). BANKNIFTY reaches
  its larger 50pt R more often than NIFTY reaches 20pt.

**N=2 is not a conclusion. Every number is IN-SAMPLE. Config stays INERT (0). The 15-day
out-of-sample sweep decides the threshold.**

### 🚨 MAJOR — the binary scorer + the cvd/regime redundancy REVERSES per instrument (2026-07-16)
Context: after the book_ofi binary-saturation fix, the score-distribution baseline showed
**7 of 8 components are binary** (activation ∈ {0, 0.5, 1.0} — a checklist, not a scorer):
`cvd_confirm`(w10), `regime`(w5), `tape_velocity`(w5), `vwap_value_location`(w15) = **35 live
points that are yes/no**, magnitude invisible. Binarisation sites: `components.py:88`
(cvd_slope>thr), `regime.py:40-44`+`components.py:113` (ma_slope>thr; direction is PURELY
sign(ma_slope) — participant_oi_bias=neutral, gex_flag INERT), `components.py:108`
(velocity_ratio spike-gate then delta-sign), `components.py:71-82` (two ±0.5 distance steps).
Measured raw magnitude thrown away: NIFTY cvd_slope spans **+133 … +128,050** (≈1000×) all →
one 10-pt bit; ma_slope **+0.01 … +26.2** (≈2000×) all → one 5-pt bit; velocity_ratio 0.07–6.6
collapsed to a 6.9% spike flag.

**THE REDUNDANCY QUESTION — and its reversal (the real finding):**
| | NIFTY_FUT | BANKNIFTY_FUT |
|---|---|---|
| Pearson r(cvd_slope, ma_slope) | **+0.827** | **−0.592** |
| Jaccard(cvd_fire, regime_fire) | 0.653 | 0.096 |
| both / cvd-only / regime-only (long) | 79 / 37 / 5 | 5 / 19 / 28 |
| one fires without the other | 24% | 46% |

- **NIFTY: CONFIRMED redundant.** r=+0.83, regime almost never fires without cvd (5 bars) →
  regime is a near-SUBSET of cvd. We pay **15 points (10+5) for ~1 directional signal.** Tonight's
  lone fired trade was NIFTY long with BOTH at 1.0 — exactly this collinearity.
- **BANKNIFTY: the reversal, and it's BIGGER.** r=**−0.59**, they disagree **46%** of bars. cvd
  slope UP while price-trend DOWN = **ABSORPTION** — the founder's own 15-year tape signal. Treating
  both as separate "yes" votes THROWS THAT INFORMATION AWAY. The pair is redundant *when they agree*
  (NIFTY) and *informative when they diverge* (BANKNIFTY).

**METHODOLOGICAL LESSON (binding going forward):** the AGGREGATE Jaccard 0.48 HID a 0.65 / 0.10
per-instrument split — it averaged a collinear instrument with an anti-correlated one into a
meaningless middle. **Aggregates lie. Every future redundancy / correlation / distribution check
MUST be per-instrument, never pooled across NIFTY+BANKNIFTY.**

**v3 CANDIDATE (menu stays CLOSED — test on the 15-day set, do NOT build):** a **CVD-vs-TREND
DIVERGENCE feature (absorption detector)** — when `cvd_slope` and `ma_slope` disagree (order flow
one way, price the other), score the DIVERGENCE as its own signal rather than counting two
half-redundant "yes" votes. This is the founder's documented tape signal; the BANKNIFTY r=−0.59
is the first data hint it's real here. Also parked: the graded floor+scale re-grade of all four
binary components (cvd/regime/velocity/vwap), per-instrument seeds measured but **NOT applied** —
N=2 and the redundancy reverses, so grading tonight would bake in a 2-day, instrument-flipping
relationship. The 15-day leak-proof test decides grading AND whether the cvd/regime pair is
reweighted, merged-on-NIFTY, or replaced by the divergence feature.

**FOURTH independent confirmation that NIFTY and BANKNIFTY are different animals:** (1) R-unit
distribution, (2) min_viable_R cost survival, (3) big_print predictive lift, and now (4) SIGNAL
STRUCTURE — cvd/trend are collinear on NIFTY but anti-correlated on BANKNIFTY. Four separate
lenses, same conclusion: they cannot share one calibration. Reinforces the open BANKNIFTY-primacy
decision.

*Nothing built or changed. Measurement was read-only (persisted bars + levels parquet). The
VWAP-band sub-check was NOT faithfully measured (persisted levels are EOD-static — needs a per-bar
levels replay, deferred).*

### 🚨🚨 Cost model — G2's actual gate, in code + the single most important number (2026-07-17)
`signals/costs.py` computes NET R. G2 = "PF ≥ 1.5 AFTER costs" — until this, nothing computed net,
so G2 couldn't be evaluated at all. Both gross AND net are reported (schema `realized_r`, `cost_r`,
`realized_r_net`); net never replaces gross.

**🎯 THE NUMBER — COST = 55% OF 1R on a 7.22pt R-unit.** This is the most important measurement in
the project so far. Everything downstream follows from it: `min_viable_R`, the BANKNIFTY-primary
lean, and the room-to-run entry gate are all consequences of this one figure. On the execution
option, a round trip costs ~2 option points; converted through delta onto a 7.22-pt future R-unit,
that is **cost_r = 0.543R ≈ 55% of 1R** (dead in the measured 50–57% band).

**⚖️ THE ASYMMETRY INVERSION — now PROVEN IN CODE, not just argued.** The cost is a FIXED per-round-
trip drag (`net_r = gross_r − cost_r`, same cost_r win or lose). So on the one real trade:
**+0.849R → +0.306R** (win shrinks) but **−1.000R → −1.543R** (loss inflates past −1R). Costs shrink
wins and inflate losses — **any strategy on small R is structurally dead.** This is why the whole
economic-viability finding exists.

**PROOF + RECONCILIATION (07-15 14:06 NIFTY_FUT long, gross +0.849R, R-unit 7.22pt):** itemised
brokerage ₹40 + STT ₹9.23 + txn ₹6.39 + SEBI ₹0.02 + stamp ₹0.27 + GST ₹8.35 = ₹64.26 = 0.989 opt-pts;
+ spread 1.0 + slippage 0 = **1.989 opt-pts** → /delta 0.5075 = 3.919 fut-pts → /7.22 = **cost_r
0.543R → NET +0.306R** (loss −1.543R). **Founder's hand-calc +0.36R vs itemised +0.31R — THE GAP WAS
GST.** Two independent routes, one answer; the −1.543R loss side matched the founder's −1.5R exactly.
**RULE: the model is AUTHORITATIVE; hand-arithmetic is a sanity check, not a source.**

**BOTH ANTI-PATTERNS AVOIDED BY CONSTRUCTION:** delta from the RECORDED greeks (**0.5075**, ATM CE
intraday-T, not a hardcoded 0.5); lot from the scrip master's `SEM_LOT_UNITS` (**65**, not config's
75) — *even though `chain/config.py` still says 75 on this branch* (the lot-size fix is a separate
gated branch; the cost model reads the authoritative source directly, so it's right regardless).

**REGISTERED RATES (defaults in `signals/costs.py::DEFAULTS`; 2026-07 ASSUMPTIONS):** `stt_rate_sell`
0.1% sell premium (Finance Act 2024); `exchange_txn_rate` 0.03503% both legs; `sebi_turnover_rate`
0.0001%; `stamp_duty_rate_buy` 0.003% buy; `gst_rate` 18% on (brokerage+txn+SEBI); `spread_option_pts`
**1.0 MEASURED** — the dominant term, a PARAMETER (varies ToD/moneyness/expiry, `spread_override`);
`slippage_option_pts` 0.0 (separate from spread; stops eat more); `fallback_delta` 0.5 (greeks-absent
only, flagged). **⚠️ `brokerage_per_order_inr` ₹20 flat is an ASSUMPTION — the ONE rate not yet
sourced; VERIFY against the actual Dhan account statement/contract note before trusting net R.**

*Code-lane: `signals/costs.py` + schema + engine wiring (capture ATM delta/premium/lot at fire, apply
at close, best-effort — gross survives if an input is missing). No config VALUES changed (rates are new
DEFAULTS in code). Nothing fires at threshold 999 → ammunition waiting on a calibrated threshold; feeds
the walk-forward harness's net-of-cost R (separate branch, sequenced after this).*

### 📌 FOUNDER DECISION (2026-07-17) — R8 sizing design (risk-constant sizing)
**Customer-facing lot selection (min 2 / 4 / 6 / 8 lots) is a PRODUCT setting → DEFERRED to the
customer/product phase (R9), NOT part of R8.** The customer lot-selection UI + limits belong to R9.

**But R8 MUST model sizing INTERNALLY — fixed-lot = uncontrolled risk.** A 7pt stop and a 40pt stop
at the same lot count are ~**5.7×** different risk. The 17 Jul research is explicit: **hold RISK
constant by varying SIZE against stop distance** (not the other way round).

**R8 spec — size = risk_budget / stop_distance (fractional-Kelly, lineage I4), capped by the
customer max-lot when that phase arrives:**
```
lots = min( floor( risk_budget / (stop_pts × delta × lot_size) ),  customer_max_lots )
```
(denominator = ₹ risk per lot: stop distance in future pts × delta = option-pts of risk, × lot_size
= ₹/lot. `delta` and `lot_size` come from the SAME authoritative sources as the cost model — recorded
greeks + scrip master, never hardcoded.)

**⚠️ OPEN FOUNDER DECISION — the 2-lot-minimum reality:** the 1R partial is IMPOSSIBLE at 1 lot (you
can't sell half a lot). So a trade whose calculated size is 1 lot must EITHER (a) skip the partial,
or (b) be rejected outright. **Founder to decide which** — logged, not chosen.

*Decision record only — no R8 code yet. R8 (sizing) is sequenced after the cost model (it consumes
cost_r + delta + lot_size). Customer lot-selection UI/limits = R9/product phase, explicitly not R8.*

### 🚨 Option-exec vs future-exec — the notional-STT flip (2026-07-17, MEASURED)
**FIRST-CLASS FINDING (founder, verbatim): "We assumed futures would be cheaper (no theta, tighter
spread). The data says the OPPOSITE: futures charge on NOTIONAL (₹15–17L/lot), options on PREMIUM
(₹9k/lot). STT alone: ₹314 future vs ₹9 option. The 07-15 trade's +0.849R GROSS becomes +0.31/+0.49R
net in options but −0.22/−0.86R in futures — a win turns into a loss. The plan's locked ATM-option
execution spec is VINDICATED by measurement, not assumption."** This killed BOTH our intuitions
(futures-cheaper AND our own hand-figures).

**CALIBRATION TARGET (not a default change):** measured NIFTY ATM CE spread **0.35pt** — the cost
model's 1.0 default is ~3× conservative; BANKNIFTY **1.70pt**. **KEEP 1.0 as the conservative default**
(conservative-by-default stays); log 0.35/1.70 as the 15-day-set calibration target for `spread_option_pts`.

**₹5L ICP FLOOR IS NOW ARITHMETIC, NOT OPINION:** ₹1L structurally untradeable (1.67/1.53 lots → below
the 2-lot even-partial minimum → REJECT). Options viable ≥₹2L, futures ≥₹5L. The plan's ₹5L
ideal-customer-profile floor follows from the sizing arithmetic, not preference.

Head-to-head at ONE capital (₹5L, to avoid confounding capital+instrument), real inputs from 07-15.
**COUNTERINTUITIVE HEADLINE: option execution is ~3–5× CHEAPER than future execution, at ALL R-units
tested — the opposite of the "futures are cheaper (no theta)" intuition.** Cause: futures charges are
levied on the full NOTIONAL (~₹15–17L/lot), options on the tiny PREMIUM (~₹9k/lot).
- **Future round-trip cost ≈ ₹471/lot NIFTY (STT ₹314 alone), ₹517 BANKNIFTY (STT ₹348)** — STT
  (0.02% sell, on notional) dominates → **7.24 future-pts (NIFTY) / 17.2 (BANKNIFTY) of cost BEFORE
  spread**, fixed regardless of R.
- **Option round-trip cost ≈ ₹64/lot (charges) + spread**, /delta → **2.62 future-pts (NIFTY) / 7.96
  (BANKNIFTY)** — ~3× cheaper in absolute future-points even after the delta division.
- **Net R (the one real trade, NIFTY 7.22pt R): OPTION +0.31R (default spread) to +0.49R (measured
  spread) — FUTURE −0.22R to −0.86R (a WIN turns into a LOSS).** Futures only stop bleeding at large R
  (≥20pt NIFTY / ≥40pt BANKNIFTY) and even there options stay cheaper. **Options win on cost, decisively.**
- Robust to the spread uncertainty below: even at a true-touch 0.5pt future spread, future cost (7.74pt)
  ≫ option cost (2.62pt).

**MEASURED SPREADS (real, 07-15):** NIFTY ATM CE **0.35pt** (p75 0.45) — TIGHTER than the cost model's
conservative 1.0 default; BANKNIFTY ATM CE **1.70pt**. **⚠️ FUTURE spread anomaly:** NIFTY_FUT top-of-
book **5.1pt median**, BANKNIFTY **13pt** — CONFIRMED by BOTH R0 ticks AND R1 depth (two feeds agree),
but 10–20× wider than NIFTY-future's known ~0.05–0.25pt touch. Almost certainly the Dhan feed's
disseminated top-of-book is snapshotted/throttled, NOT the true executable NSE touch. So the future
spread is UNCERTAIN (0.5pt true .. 5pt as-fed); reported as a range. **The option conclusion does not
depend on it.**

**🚫 MARGIN — a hard blocker for futures sizing, NO DATA anywhere.** The scrip master has NO margin/
SPAN/exposure field (only lot/strike/tick). So "how many future lots at ₹5L" is unanswerable from our
data. Sources, in order of authority: **(a) Dhan order-margin API** (we hold Dhan creds; a live call —
most authoritative for what WE'd be charged); (b) NSE daily SPAN files (not ingested; downloadable);
(c) broker-published per-contract margin CSVs; (d) rule-of-thumb SPAN+exposure ≈ 12–15% of notional
(~₹1.9L/lot NIFTY, ~₹2.1L/lot BANKNIFTY) — an ESTIMATE only, used in the table below with that caveat.

**CAPITAL TABLE (1% risk, stop NIFTY 20pt / BANKNIFTY 40pt; option risk-limited, future min(risk,
margin-est); <2 lots → REJECT):**
| capital | NIFTY option | NIFTY future | BANKNIFTY option | BANKNIFTY future |
|---|---|---|---|---|
| ₹1L | 1 → **REJECT** | 0 → **REJECT** | 1 → **REJECT** | 0 → **REJECT** |
| ₹2L | 3 | 1 → **REJECT** (margin) | 3 | 1 → **REJECT** (margin) |
| ₹5L | 7 | 2 (margin-capped) | 8 | 2 (margin-capped) |
| ₹10L | 15 | 5 (margin-capped) | 16 | 4 (margin-capped) |

**FOUNDER'S ₹1L-OPTIONS IDEA — logged as a CANDIDATE, but ARITHMETIC SAYS STRUCTURALLY UNTRADEABLE.**
At ₹1L / 1% risk (₹1,000 budget): BANKNIFTY 40pt stop needs ₹1,000 / (40 × 0.5 × 30) = **1.67 lots →
floor 1 → below the 2-lot minimum → REJECT** (the 1R partial is impossible at 1 lot — the Gear-2
free-trade is structural, per today's R8 decision). NIFTY 20pt is the same (1.53 → 1 → REJECT). **₹1L
is structurally untradeable at 1% with even-lot partials, for BOTH instruments, BOTH executions.**
Options become viable at **₹2L** (3 lots); futures not until **₹5L** (2 lots, margin-capped). Capital
is the separate question — answer it AFTER the option-vs-future call, exactly as the founder framed.

*Read-only measurement; no config, no code, spec unchanged. Future rates (STT 0.02% sell, txn 0.002%,
stamp 0.002%) + margin 12% are 2026 ASSUMPTIONS — verify futures STT + get real margin before trusting
the future column.*

### 🏁 R8 Paper Executor — BUILT (2026-07-17), the LAST big module
**R8 is the last big MODULE. Everything after this is CALIBRATION, not construction** — the full
chain R0→R8 now exists (recorder → depth → replay → tape → levels → chain → signals → cost → paper
executor). What remains is the 15-day set, the paper run, and sweeps — tuning, not building.

**THE EQUITY BLOCKER R8 EXPOSED (the finding it delivered before running a single trade):** two months
in, the engine had **NO capital concept at all**. R without capital is DIMENSIONLESS — you cannot size
`risk_budget = risk_pct × equity` with no equity. Sizing was literally impossible until R8 introduced
`starting_capital_inr` + a running-equity ledger. That gap had been invisible because the sim worked in
pure R fractions (`SimPosition.remaining = 1.0`), never rupees.

**THE FOUNDER'S EVEN-LOT CATCH (why `even_lots_only` exists):** raw sizing gives 7.57 lots at ₹5L →
naive floor = 7, but **7 is ODD → the 1R 50% partial (sell half) = 3.5 lots, which cannot exist.** No
error would fire — just a half-book that silently can't happen, breaking Gear-2's free-trade. So lots
round DOWN to the nearest EVEN number (7.57 → **6**). This is the structural reason even_lots_only is a
default, not a preference.

**EVERY R8 PARAMETER IS HYPOTHESIS-NOT-CALIBRATED (the 15-day set + paper decide all of them):**
`starting_capital_inr` ₹5L · `risk_pct` 1% · D1 50%-after-2-consecutive-wins · D2 hard global-one-
position · `daily_loss_limit_r` −3R · `consecutive_loss_halt` 3 · `customer_max_lots` 8 · `min_lots` 2.
None is measured; all are the founder's 17-Jul decisions pending validation.

**"FRACTIONAL-KELLY" IS FIXED-FRACTIONAL 1% (honest labelling):** true Kelly needs a measured win-rate +
payoff we do NOT have (zero fired trades at threshold 999). So R8 v1 sizes at a flat 1% risk. **Trigger
to revisit Kelly-proper: a win-rate + payoff estimate from the 30-day PAPER run.**

**What's built:** `signals/sizing.py` (even-lot, reject-<2), `signals/risk.py` (D1/D2 + daily-loss +
consecutive-loss halt + streaks), `signals/ledger.py` (per-trade + running equity + TCA/I3 cost
attribution — what G2 reads), `signals/order_router.py` (INERT stub: OFF, read-only, NOT wired, no
broker adapter imported). Engine wiring is additive + guarded by `r8.enabled` (default false) → the
existing path is byte-identical when off. **TRIPLE FENCE:** r8.enabled=false · fire_threshold 999
(nothing fires) · order router off/readonly/unwired. No live container, no live-money file touched.
Tests: 16 (sizing, risk, ledger, router fence, + two full-session-loop tests). Suite 505 passed, 1 skip.

### Walk-forward validation harness — built BEFORE the data (2026-07-17)
`research/walkforward.py` — the missing OOS-validation tooling for G2's "PF ≥ 1.5 after costs on
out-of-sample data" gate. Built now, on purpose, so it EXISTS before the 15 days land (~31 Jul):
otherwise every sweep on that data would be in-sample fitting, and we'd be building the tool
instead of using it. **A loaded gun with no ammunition** — and that's the right order. Four
capabilities, all pure/deterministic/tested (17 tests): (1) walk-forward splitter (anchored +
rolling, López de Prado purge+embargo); (2) Sweep 2.0 in code (pre-registered range, full curve,
plateau + ±20% perturbation); (3) permutation null (shuffle the outcome `r`, preserving the return
distribution, destroying param↔return structure → the false-positive floor); (4) Deflated Sharpe.

**🎯 CANONICAL EXAMPLE — why Deflated Sharpe is MANDATORY on every sweep (the 1000-monkeys problem
killed in real time):** a nonsense sweep produced a raw **Sharpe 20.66 → Deflated Sharpe 0.000**,
with **permutation p = 1.000**. The deflation + null both nuked a spectacular-looking in-sample
number to nothing, on the very first run. This is exactly "try 100 things and pick the best":
without DSR + permutation, that 20.66 would look like a discovery. **DSR is reported automatically
on every sweep — never optional.** Contrast the demo's genuine synthetic edge: even crushing the
permutation null (p=0.005), it still FAILED the 0.95 DSR bar on N=4 — the honest signal that N=4 is
a smoke test, not a result.

**THE HARNESS'S INPUT PROBLEM (why it's a gun with no ammunition):** `fire_threshold=999` → zero
trades fire → every `realized_r` sweep is currently VACUOUS (nothing to validate). Ammunition comes
from (a) the COST MODEL + (b) a CALIBRATED threshold, both PENDING. **The harness waits for them,
not the other way round** — it's ready the moment real net-of-cost trades exist.

**P1 2026-07-20 — PBO (CSCV) added:** `research/pbo.py` + `--pbo` CLI flag (DEFAULT OFF, new outputs only) — Bailey/López-de-Prado combinatorially-symmetric CV: S=10 chronological day-blocks, all C(10,5)=252 IS/OOS splits, λ=logit(OOS rank of the IS-best), ties half-counted (identical configs → PBO 0.5), boundary-purge default ON (no-op on intraday trades, machinery tested); REFUSES below 10 usable days / 4 configs — refuses on the current recorded days by design, real use = the completed 15-day set. Synthetic-only validation: superior system → PBO 0.00 · antisymmetric overfit → PBO > 0.6 · identical → 0.5 · iid noise → ~0.5.

**P2 2026-07-20 — purge+embargo AUDIT (no gap, teeth added):** measured horizons — feature lookback max 20 bars / honest max = SESSION-LONG (CVD/VWAP/profile/OFI all session-anchored), holding = min(60-min sleeper, session force-close), label = same-session exit; engines built FRESH per day (signals/pipeline.py:59-77) with day-granular splits ⇒ required cross-boundary embargo = 0 — **current embargo 0 is JUSTIFIED, not an oversight; NO behavior change.** Invariant documented in embargo_test docstring (revisit if: multi-day holds, cross-day rolling features, sub-day splits, or non-fresh engines). Teeth: tests/test_purge_embargo.py t1-t4 incl. a PLANTED +10R leak that inflates unguarded metrics and is provably dropped by purge/embargo (suite 577).

**P3 2026-07-21 — plateau-robustness (per-config) added:** `plateau_robustness(curve)` in research/walkforward.py — for each swept config i over its median OOS EXPECTANCY: PE=median(E_{i-1},E_i,E_{i+1}), PD=MAD(...), PR=PE−0.5·PD. ELIGIBLE only if INTERIOR and E_i + both neighbours > 0 — an isolated peak (a neighbour ≤ 0) is REJECTED regardless of height; EDGE candidates flagged 'limited-neighbor evidence', never eligible-full; best_plateau prefers interior. ADDITIVE — plateau_report (argmax summary) and R2 hash faf6d8b8 untouched; 5 tests (broad plateau→interior eligible, isolated spike→rejected, edge→flagged, all-negative→none, hand-computed PE/PD/PR golden). Suite 581. Rationale: pick a config sitting on a broad all-positive shelf over a taller lone needle.

**P4 2026-07-21 — STRESS GATES added (research/stress_gates.py, CLI --stress-gates DEFAULT OFF):** (a) remove_best_days(n=5) — fat-tail concentration test on the stitched daily net-R series; refuses < 3n days; (b) slippage_stress — net@1.0x vs net@1.5x via the EXISTING cost knob slippage_multiplier (signals/costs.py:55; friction-only, zero duplicate cost math; uncosted trades counted, never estimated); (c) paired_block_bootstrap — 5-day contiguous blocks, 10k reps, STORED SEED, paired daily A−B delta + 95% CI, verdict 'no clear superiority' when CI includes 0; refuses < 2 blocks. 7 tests (fat-tail edge dies after best-5 / spread survives; guardrails; marginal system dies @1.5x, robust survives; A>B CI excludes 0, tie includes 0; seed-determinism; flags-off byte-identical). Suite 588; R2 hash faf6d8b8 untouched.

**P5 2026-07-21 — PRICE EFFICIENCY feature (research/price_efficiency.py, DEFAULT OFF):** UpsideEff = up-ticks/max(aggr-buy-qty,eps), DownsideEff mirror, per-bar + rolling-10, strictly causal, from R3 Lee-Ready buy/sell volumes (tape/bars.py:37-38). DISTINCT from Kaufman ER (price-only, rejected 07-19): volume in the denominator = 'how much price a unit of aggression bought' (low = absorption). PRECHECK on 5 clean sessions ×2 futs (611 bars) + the 53-universe: de-clustered ρ(PE,ER)=+0.169 (tripwire 0.7 NOT hit → NOT an ER-twin); per-bar PE⊥delta/volimb/velocity (|ρ|<0.06 median); prior-only candidate signal ρ(PE,R)=+0.37 full / +0.17 de-clustered — IN-SAMPLE PRIOR, no gate claims. Written to NEW files only (analysis/<day>/price_efficiency_*.json via opt-in CLI); pipeline byte-identical; 4 tests (golden, causality, eps-guard, off-by-default). Carried as 15-day feature candidate + P7/LAR absorption input.

**P6 2026-07-21 — DEPTH PROXIES (research/depth_proxies.py, DEFAULT OFF, APPROXIMATIONS):** replenishment + cancellation-pressure from 5-level depth diffs, diffed BY PRICE never by level index (price-shift test proves zero fake events when the book merely ticks). (a) refill events + refill_ratio=restored/removed (within k=5 snapshots, best within 2 ticks); (b) cancel_proxy=max(removed−traded,0) with interleaved tick-feed trades matched at the exact price; vanishing-wall = ≥P90 level absent in-range with <20% traded. Gap-guarded (5s; the 07-15 445s lull discards diffs + pending state). KNOWN LIMITS embedded in every output (5 levels, cadence blind spots, no order IDs — proxy not truth). NEW files only (analysis/<day>/depth_proxies_*.json via opt-in CLI); pipeline byte-identical; distinct from book_ofi/queue_imbalance (those summarize the standing book; these decompose CHANGES into executed vs pulled). 7 tests (golden cancel 200 + refill 250/300; price-shift zero; full-execution zero-cancel; causality; gap-guard; off-by-default). Events/day (descriptive ONLY, no outcome claims): refills 1–4k, cancels 33–63k, walls 2.4–9.3k per instrument-day across 07-14..17+20 — plausible + stable magnitudes; BANKNIFTY consistently wall-heavier. Suite 599; R2 hash faf6d8b8 untouched.

**P7 2026-07-21 — LAR STUDY MODE (research/lar_study.py + lar_summary.py, COUNTING ONLY, DEFAULT OFF):** per-level (PDH/PDL/ORH/ORL — OR = R4's Initial Balance, no second definition) strictly-causal state machine FAR→APPROACHING→TOUCHED→SWEPT→ABSORPTION_CANDIDATE→FLOW_FLIPPED→RECLAIMED→ARMED→TRIGGERED|FAILED|EXPIRED. All thresholds in one STUDY_CONFIG (reasoned from existing conventions: ATR14, 2-tick, 20-bar baselines, percentile cuts) logged into every output; every transition persisted with ts/reason/feature-snapshot/data-quality; absorption inputs REUSE P5 efficiency + P6 refills (depth-less days flagged no_depth); TRIGGERED = virtual marker only (stop=sweep extreme, forward gross R at 5/10/20 bars; net only with chain inputs — never estimated). REAL-DAY FUNNEL (7 days ×2 futs, descriptive ONLY): 52 level-machines → 11 SWEPT → 3 ABSORPTION (27.3%) → 2 RECLAIMED (66.7%) → 1 TRIGGERED (07-16 BANKNIFTY ORH short, r_10b −0.37 — a loser; N=1 says NOTHING). Ranking check refuses honestly: 'INSUFFICIENT DATA for ranking claims (n=1<10)'. NEW files only (analysis/<day>/lar_study_*.json + lar_summary.json + lar_dashboard.html — NOTE: repo had NO existing HTML dashboard generator, page is new+standalone). 7 tests (exact clean-path sequence w/ hand-checked timestamps; efficient-break FAILED pre-absorption; touch-no-sweep no false SWEPT; causality; stage timers incl. non-terminal approach reset; forward-R marks; off-by-default). Suite 606; R2 hash faf6d8b8 untouched.

**P8 2026-07-21 — BAR-QUALITY DIAGNOSTICS (research/bar_quality.py, DEFAULT OFF, descriptive-only):** folds ADDITIVELY into the pre-registered bar-representation study (b2fc49a — its criteria text UNTOUCHED). Per day/instrument: flat-bar rate, duration Q10/Q50/Q90 + Q90/Q10 split by session regime (OPEN = IB 60min levels/config.py:30, CLOSE = gates.session_cutoff 14:45 — REUSED anchors, no new regime), range/volume/trades-per-bar median+IQR. REAL-DAY TABLE (7 days): tick-100 flat-bar rate 0.0% everywhere; NIFTY durQ50 160–260s (Q90/10 2.0–3.9), BANKNIFTY durQ50 199–431s (Q90/10 3.2–5.9 — burstier), MIDCP durQ50 1.1–3.2 ks (Q90/10 up to 11.6 — tick-100 clearly too coarse there); trades/bar exactly 100 (definition check ✓). Numbers FEED the pre-registered sweep, judge nothing. NEW files only; 4 tests (exact flat+quantile golden, regime buckets, empty/short guard, off-by-default). Suite 610; R2 hash faf6d8b8 untouched.

**BSE STOCK-F&O RECORDING — Phase B build 2026-07-21 (deploy-gated; recorders untouched until rebuild):** config.yaml gains additive `stock_fno:` block — BSE Ltd FUTSTK (monthly, rollover day-after-expiry via generic resolve_future(instrument_name=FUTSTK), lot 200 from scrip master) + OPTSTK monthly chain ATM±10 (±10 by strike INDEX on the listed grid → mixed 50/100 step respected, ~22 instruments, ~15-25 MB/day est). ATM anchors to the BSE equity feed (already recorded), falls back to the future; re-centers EVERY session (resolve_instruments() per-day, main.py:725 — Phase-0 audit: no start-only drift). gap_check:false on the stock future + verify_session._is_lenient now honors an EXPLICIT gap_check flag (index futures carry true, legacy manifests keep kind-based — behavior unchanged for all existing instruments). 4 tests (FUTSTK rollover 28-Jul→25-Aug; OPTSTK chain + ATM window on mixed grid + OPTIDX isolation; gap-exemption matrix incl. legacy; pipeline glob/sid convention). Suite 614; R2 hash faf6d8b8 untouched. DEPLOY = image rebuild + recreate (config+code baked) — Saturday/founder-gated.

**M1 2026-07-21 — S3 RESTORE TOOL (scripts/restore_day.py, explicit-CLI-only):** restores ONE archived day (ticks + top-level depth/*.parquet — the consolidated files the replayer reads, replayer/source.py:82; parts subtrees EXCLUDED) into <clone>/restore/data/<day>, NEVER the live data dir. ADD-ONLY (existing files skipped, never overwritten), TODAY always refused, disk-guard (free < size+10GB → refuse), verification = S3 ContentLength + backup.json size + md5-vs-ETag (single-part), any mismatch → delete + loud stop. --dry-run + --cleanup. REPLAYABILITY TABLE (audit): 07-13+07-14 were ticks-only locally (5-day depth retention, recorder/depth_retention.py); S3 holds full depth for both. PROOF on 07-14: 521/521 files restored+verified (337MB; 34,338 parts objects excluded) → replayed WITH depth first time since aging (fired=4, qualified=7, gross −1.787R — DESCRIPTIVE ONLY) → frozen baseline slice re-verified 17/+2.017 → cleanup returned disk to baseline (27G). 7 mocked-S3 tests (add-only, checksum refusal, disk-guard, today-refusal, parts exclusion, verify matrix, cleanup). Suite 626; R2 hash faf6d8b8 untouched.

**THREE DESIGN DEFAULTS + reasoning (for when the ammunition lands):**
  - **Anchored (expanding) train, default.** With N small, a rolling window starves training;
    expanding uses all history to date and mirrors how we'd actually retrain. Switch to rolling
    only once N is large enough that a fixed window still has power.
  - **Purge = trade hold-time, + a 1-day embargo.** Over-purging costs a little data; a leak costs
    the whole validity. So we err toward over-purge: drop any train trade whose exit overlaps the
    test window, then embargo a day.
  - **Plateau ratio is UNRELIABLE at N=4** (neighbours are noisy) — it needs the 15-day set before
    its verdict means anything. Reported now, trusted later.

**⚠️ `purge_bars` is pinned to the 60-min SLEEPER because true hold-time is UNKNOWN.** The sim
persists no exit timestamp, so `trades_from_signals` uses entry-ts and purge can't see straddlers
from persisted data. Interim: assume max hold = the exit engine's 60-min sleeper timeout. **This
MUST be re-derived from real fired trades' actual hold-time distribution once the sim fires** — a
hardcoded hold-time is the same anti-pattern as the lot-size mirror (a constant with a real source).

*Research/validation package only — no config touched, no component wired, menu stays CLOSED. The
strategy plugs into the `evaluator` seam; `trades_from_signals` consumes `realized_r` today and
net-of-cost R unchanged when the cost model lands.*

### N=17 GROSS look — three observations (NOT conclusions) (2026-07-17)
A THROWAWAY in-memory run (config untouched on disk — OFI on + fire_threshold 40 overridden in
memory, no artifacts, GROSS only, chain stubbed) over 5 days. **Clean days 15/16/17: 17 trades,
53% WR, total GROSS +2.02R** (mean +0.119, median +0.497). Degraded 13/14 reported separately
(−0.83R). **These are NOT conclusions — in-sample, arbitrary threshold, GROSS, N tiny.** They are
the questions the 15-day set must answer, pre-registered so we can't move the goalposts later.

**1. SCORE ≠ OUTCOME (the scorer's own pre-registered test).** Three of the four highest scorers
(51.2, 50.6, 49.9) were **−1R**; only the 4th (50.5) won. At N=17 this proves nothing — but it is
**the single most important thing the 15-day set must answer: does the composite score rank outcome
AT ALL?** Pre-registered, same template as OFI's leak-proof test: rank trades by score, measure
whether higher-score buckets have higher net-of-cost R out-of-sample. If score doesn't rank outcome,
the whole confluence scorer is unproven regardless of how clean the code is.

**2. EDGE LIVES IN A HANDFUL OF TRADES.** The clean +2.02R is concentrated in the two trail-runners
(**+2.68 on 07-15, +2.28 on 07-17**); strip those two and the clean days go **negative**. The rest is
a pile of **+0.5R scratches** (1R partial → breakeven stop) and clean **−1R** losers. (The founder's
cited third runner +1.47 is 07-13 — a DEGRADED day — so on clean-only the concentration is even
tighter.) Pre-registered question: is the trail-runner tail REAL and repeatable, or is +2.02R just 2
lucky trades? The permutation-null + Deflated-Sharpe in the walk-forward harness exist precisely to
answer this.

**3. THE PARTIAL MAY BE EATING THE EDGE (a 15-day EXIT experiment).** Our earlier partial-booking
finding: booking the 1R partial COSTS ~46% of absolute profit but LIFTS win rate 52.6%→63.4%. This
N=17 shape is **consistent** with it: we book half at 1R, the runner then stops at breakeven → a pile
of +0.5R scratches, while the actual gross comes from the few that ran uninterrupted. **Pre-registered
experiment for the 15-day set: partial-at-1R vs no-partial, AFTER costs, walk-forward** (does killing
the partial let the runners run enough to beat the WR hit, net of the 55%-of-1R cost?). **Menu stays
CLOSED — this is an EXIT parameter, not a signal change.**

### 🛡️ Hardcode-audit guardrails (2026-07-17) — two notes that PREVENT future bugs
From Task #8 (the anti-pattern sweep). Both are places where a well-meaning "fix" would
INTRODUCE a bug — logged so nobody does it.

**1. TICK_SIZE TRAP — and it CORRECTS our own meta-lesson.** `tick_size = 0.05` is hardcoded in
`tape_config.yaml:184` and `signals/config.py:73`. The value is CORRECT (NSE index-future tick). The
scrip master DOES have `SEM_TICK_SIZE` — but it reports **10.0 (NIFTY) / 20.0 (BANKNIFTY)**, which do
NOT parse to 0.05 (and differ between two instruments with the same real 0.05 tick → the field is not
the price tick, or is in an unknown unit). **Mechanically applying our own "read the source, don't
mirror" rule here would have created a ~200× stop-slippage bug (0.05 → 10.0).** The hardcode is right;
the "source" is the trap.
> **CORRECTED RULE (supersedes the raw meta-lesson):** read the authoritative source only after
> VERIFYING the source is actually authoritative *for that field* AND correctly typed. A field's
> PRESENCE doesn't make it right. Verify the parse, verify the value, THEN wire. **A rule applied
> without verification is just a different hardcode.** (Lot-size passed this — GCD + SEM_LOT_UNITS
> agreed at 65/30. Tick-size fails it — SEM_TICK_SIZE ≠ 0.05. Same rule, opposite action, because we
> VERIFIED.)

**2. MARKET-CLOSE → DELTA coupling.** `chain/engine.py:26` `_EXCHANGE_CLOSE = time(15, 30)` is a
hardcoded NSE close. The value is correct and NSE-stable, so it stays a constant — BUT it silently
reaches the greeks: it sets the intraday time-to-expiry (`_time_to_expiry_years`), which drives
**IV/greeks → DELTA → the cost model AND R8 sizing**. A change to this one time silently re-prices
delta everywhere downstream. **Do not touch 15:30 in isolation.** Also note 09:15/15:30 is mirrored in
~7 files (verify_session, depth_verify, gex_predictive, walkforward, chain/engine, signals/events) — if
NSE ever changes trading hours, all of them move together, and chain/engine is the one with teeth.

### ✅ Task #9 CLOSED — cost + margin resolved (2026-07-17)
**MARGIN IS NOT A BLOCKER.** We execute weekly ATM OPTIONS as BUYERS (premium-only debit) — the
plan's locked spec, confirmed by last night's cost analysis AND the founder's real futures contract
note (charges on notional → futures rejected). An option buyer posts no margin. **R8's sizer is
margin- and premium-agnostic** (`signals/sizing.py:64-65`: `risk_per_lot = stop_pts × delta × lot_size;
raw = risk_budget / risk_per_lot`) — it sizes on RISK, never on capital outlay. Margin matters ONLY
for futures execution, which we do not use. The Dhan `margincalculator` design (POST /v2/margincalculator,
reuse the DB token, ~2 read-only calls/day) is RECORDED for the day we ever need it — **it is NOT open
work.**

**COST RATES stay AS-IS (founder's standing decision).** The founder handles all charges himself and
applies real costs to our GROSS numbers. Our model's rates are a documented approximation, NOT the
gate. The 2026-07-17 futures contract-note check (ANGELONE+CDSL FUTSTK) verified: stamp (0.002% buy)
and GST (18% on brokerage+txn+SEBI) MATCH; brokerage is ₹15/leg not ₹20 AND Gear-2 is 3 legs not 2;
NSE txn (~2.2×) + SEBI (~2×) overstated; STT showed ₹0 on the note (a note-scope artifact — the
Finance-Act 0.02% sell ≈ ₹604 on ₹30L is real, so futures-expensive STRENGTHENS). The OPTION rate half
(STT/txn/GST on premium) stays UNVERIFIED until the paper run's first option round trip — recorded, not
open. **#9 done; only #10 (holidays refresh) remains.**

### ✅ Task #10 CLOSED — the G0 holiday hole (2026-07-17)
**THE HOLE (real, traced):** `holidays.yaml` is read ONLY by the two recorders' session clocks
(`scheduler.py:45`), NOT by the verifier / G0 / pipeline. So a weekday holiday NOT in the list
(a missing entry, or an NSE mid-year UNSCHEDULED holiday) → recorder connects 09:07 → ~0 ticks →
verify writes PARTIAL (0% coverage) → `_g0_counter` reset the streak **on a day the market was
simply closed.** The file's old "under-listing is harmless" comment was WRONG about G0 — it only
weighed data loss.

**THE FIX (consumer, not the verifier — which is 4 recalibrations deep and stays untouched):**
`alerts/pulse.py::_g0_counter` now SKIPS listed holidays AND no-session days (`coverage < 5%`); only
a REAL dirty session (real coverage, non-PASS) resets. **KEY INSIGHT: the list protects against
WASTED RUNS; the coverage<5% skip protects G0 — and the second is what actually matters.** An
unlisted or unscheduled NSE holiday can no longer silently kill a clean-session streak, because the
skip is DATA-DRIVEN (zero coverage = no session), not list-driven. More robust than the list itself.

**2026 VERIFICATION (verify-first standard applied to a list, not assumed):** all 6 remaining-2026
holidays cross-checked vs ClearTax — **Sep-14, Oct-02, Oct-20, Nov-10, Nov-24, Dec-25** — all correct.
**Aug-15 (Independence Day) is a SATURDAY** (auto-skipped, correctly absent); the Nov-8 Diwali-Laxmi
**Muhurat is a Sunday, correctly excluded**. No over-listing, no missing weekday holiday.

**YEARLY REFRESH — the honest answer (same trap as the tick-size guardrail above):** NSE's holiday
circular is a **webpage/PDF, not a typed feed**. Wiring it as an "authoritative source" would be
brittle — exactly the `SEM_TICK_SIZE` trap (a source's presence ≠ it being cleanly usable). So a
**hand-maintained list + a Sunday-ritual yearly refresh (like `events.yaml`)** is the honest answer,
and the no-session skip **removes the criticality of UNDER-listing** (a stale/missing entry now just
wastes one recorder run that G0 skips). **The one remaining job of the list: DON'T over-list a real
trading day** (that still loses a session forever) — which the yearly refresh + a visible "no-data
weekday" anomaly guard. Re-verify against the NSE 2027 circular next year.

### 🎯 The harness's first act on real data was to DESTROY our only positive result (2026-07-17)
Fed the 27 throwaway trades (OFI-on/threshold-40, in-memory, config untouched) — 17 clean, +2.02R
gross — to the walk-forward harness. **Its first act on real data was to destroy our only positive
result. Three independent nulls agreed: 2 lucky trail-runners on ONE day (07-15), indistinguishable
from noise at N=17.**
- **Deflated/Probabilistic Sharpe = 0.65** (per-trade SR 0.096, T=17, skew +0.61) — fails the 0.95 bar.
- **Sign-flip null p = 0.34** — 34% of random sign-flips beat +2.02R.
- **Walk-forward OOS PF = 0.672** — the +2.02 doesn't survive even a trivial 3/2 split (it all lives
  in 07-15; the test window 16/17 is net-negative gross).
**That is the tool WORKING, and it is worth more than the number it killed.** N far too small, in-sample,
arbitrary threshold, gross — exactly what the harness is for. The machinery runs end-to-end on real
trades before the 15-day set arrives.

**TWO REAL GAPS the run exposed (both fixed, `research/walkforward.py`):**
1. **The missing FIXED-STRATEGY null.** `permutation_null` shuffles return-to-trade ASSIGNMENT, which
   PRESERVES THE SUM — so it answers *"did my SWEEP pick luck?"* (selection), NOT *"is this RESULT
   luck?"* for a fixed strategy (whose net is permutation-invariant). Added **`sign_flip_null`** (no-
   directional-edge) + **`bootstrap_null`** (sampling uncertainty), each docstring'd with WHICH
   question it answers. **LESSON: this gap survived EVERY synthetic test because they always had a
   sweep — synthetic tests only probe the shapes you imagined.**
2. **The DEGRADED-DAY filter.** With chronological data the degraded days lead, so the splitter would
   silently TRAIN on 07-13 (disk crash) + 07-14 (43% coverage). `walk_forward_sweep(..., root=...)`
   now runs **`pass_days`** first — refusing any day whose `report.json` status != PASS, by default,
   with `require_pass=False` as the explicit override. Tested both paths.

**⚠️ DSR 0.65 is the OPTIMISTIC end.** With `n_trials=1` (no sweep) the trial-deflation is nil. When a
REAL sweep runs, `n_trials>1` inflates `SR0` (expected-max) and DSR drops FURTHER — **our first real
sweep will face a HARDER bar than this 0.65.** Suite 552 passed.

### 🎯 SHARPEST STATEMENT of SCORE ≠ OUTCOME — zero winner-separation at N=17 (2026-07-17)
Examined the 17 clean trades for what separated the two trail-runners from the rest. **N=17: NOTHING
separated the winners. The score-40.0 trade (the threshold FLOOR) delivered the 2nd-biggest win
(+2.28R), while trades scoring 42.6 / 45 / 50.6 all lost −1R. Neither R-unit, hold time, hour,
instrument, side, nor stop-source distinguished them. The only shared property is an OUTCOME (price
trended far after entry) — invisible at entry.**

**Implication, stated plainly: at this N the composite score does NOT rank outcome.** The gross result
lives in the EXIT engine catching whatever happens to trend; the entry score cannot pick those trades.
**Four independent angles now agree — DSR 0.65, sign-flip p=0.34, OOS PF 0.672, and now zero
winner-separation.**

**NOT a conclusion at N=17.** But it makes **SCORE≠OUTCOME the single question the 15-day set must
answer FIRST**, before any threshold, weight, or sweep work. If the score cannot rank outcome
out-of-sample on 15 days, no amount of calibration saves it — and that finding would be worth more than
any number we could tune. (Per-day: 07-15 +4.34R carries everything; 07-16 −1.06R + 07-17 −1.26R are
net-negative. Strip 07-15 → −2.32R. In-sample, arbitrary threshold 40, GROSS, N=17 — not edge.)

### big_print rolling-percentile machinery — built INERT (2026-07-17)
big_print carries **weight 20 of the ~65-point reachable ceiling** but contributes ZERO on every
trade (`notional_threshold=0`). The prints ARE there — the 07-15/16 calibration measured NIFTY p99
≈ ₹8.45cr with a 5× lift (base 1.8% → 9.2% for a ≥20pt move in 60s). The machine just couldn't see
them. Built the machinery to see them; **left it INERT**.

**WHY A PERCENTILE, NOT THE MEASURED ₹8.5cr (the design decision):** a fixed ₹ cut is a HARDCODE WITH
NO SOURCE — the lot-size anti-pattern. It's 2-day data, and **BANKNIFTY's p99 print-count swung 89 → 15
across those two days (6×)** — a fixed number would be fitted to noise. A percentile is **per-instrument
AND per-regime by construction**: a print is "big" if its notional exceeds the Nth percentile of THAT
instrument's OWN rolling trade window. Same pattern we've already proven — OFI's floor+scale, ATR's
per-instrument stops, min_stop being ATR-derived. Derive the cut from the instrument's live
distribution; never mirror a number.

**GRADED, not binary (OFI's lesson applied BEFORE the bug could repeat):** the event carries
`strength ∈ [0,1]` = the print's percentile-rank in the tail mapped `[percentile,100] → [0,1]` (p99.9
→ ~1, a print at the p99 cut → ~0); the `big_print` component returns `clamp01(strength)`, not a flag.
Fixed mode emits 1.0 (binary, backward-compatible).

**STRICT NO-LOOK-AHEAD:** the window is appended AFTER the classification, so the percentile at trade t
uses only trades before t. Leak-proof test pins it: a colossal print appended at the end cannot change
any earlier verdict. **WARM-UP = "0 until warm"** — below `min_samples` the percentile isn't estimable,
so the detector contributes NOTHING (not day-1 leaky self-data, not fail-loud). **LOOKBACK = last N
TRADES, not days** — trade frequency varies 100× across instruments, a trade-count window self-adapts
and tracks the recent regime; cross-day history is deliberately not carried (stale-regime + restart-safe).

**⚠️ PERF, flagged BEFORE activation not after:** percentile mode recomputes the cut O(N log N) per
trade. Fine for the tradeables; across the full 400-instrument set it's heavy → at activation, scope
percentile mode to the tradeables or add a recompute stride. **Default-off (`mode=fixed`) has ZERO
overhead** — the path never runs.

**STANDING STATE:** the machinery lands INERT (`bigprint.mode=fixed`, `notional_threshold=0`). **The
activation — `mode=percentile` + which percentile — is a 15-DAY-SET DECISION, not a config edit**,
because big_print is 20 of the ~65-point ceiling and turning it on **changes every score** (and would
poison the SCORE≠OUTCOME baseline). Knobs: `bigprint.mode`, `.percentile` (99), `.lookback` (2000),
`.min_samples` (500). Suite 558 passed.

### 🧭🧭🧭 THE REFRAME (2026-07-17) — the sharpest reframe in the project; must not fade
"THE REFRAME (17 Jul): §1 and §2 point opposite ways. The ONLY predictor with a real rank signal is
stop-width (R-unit% ρ=+0.777) — and even that is mechanically 'tight stops get noised out', i.e. trade
STRUCTURE, not tape reading. Every flow signal we can measure ranks at ≈zero: composite score
ρ=−0.140, |OFI| magnitude ρ=+0.120, saturated activation undefined-by-construction.

So the 15-day set's FIRST question is not 'which signal' — it is: DOES ANY SIGNAL RANK AT ALL, or is
R-multiple structure (stop discipline + two fat tails) doing all the work?

This reframes the OFI-percentile experiment from 'fix the signal' to 'confirm the signal is even worth
ranking'. And it reframes the whole 15-day set: before tuning any weight or threshold, establish
whether the scorer has ANY rank information out-of-sample. If it doesn't, no calibration saves it —
and that finding would be worth more than any number we could tune.

N=17, in-sample, not a conclusion. But it is the shape to test first."

Anchors: the three correlations ([[THREE CORRELATIONS]]), the all-17-same-trade structural finding,
the N=17 winner-separation, and the OFI saturation/percentile [[OPEN DESIGN QUESTION]]. First test of
the 15-day set = an out-of-sample rank-information check on the scorer, BEFORE any weight/threshold
calibration.

### 🧬 DNA of the DEAD COMPONENTS + the path (2026-07-17) — why the non-working parts don't work
Cracked the root cause of every component that contributes ~nothing, classified as **(A) off-by-switch**,
**(B) half-built (wiring missing)**, or **(C) design flaw**. Proved each with an in-memory run.

- **big_print (weight 20) → (A) off-by-switch, NOT broken.** Root: `bigprint.mode="fixed"` +
  `notional_threshold=0`. The percentile-path is fully built AND wired end-to-end (detector →
  tape.event_rows → `_recent_print` → ctx → component). PROOF: flip mode=percentile in-memory →
  NIFTY 302 / BANKNIFTY 190 prints (~0.99% = p99, as designed); **44% of fires** coincide with a
  big print (graded strength 0.33–1.00). It comes alive on the flip.
- **queue_imbalance (weight 0) → (B) half-built.** Root: `depth_imbalance.queue_imbalance_rows()`
  EXISTS and computes fine off live depth (|mean| 0.23–0.34, max 1.0) — but the tape engine never
  called it, so `ctx.queue_imbalance` was always None. **FIXED this session** (commit on
  `feat/orderflow-queue-wire`): tape now emits per-bar `queue_imbalance`, signal ctx reads it,
  **INERT (weight 0) → zero trade change**; 17-trade baseline byte-identical, suite 561 passed.
- **OFI saturation → (C) design/calibration.** floor+linear scale saturates inside the firing region.
  Path: percentile-rank OFI (see [[OPEN DESIGN QUESTION]]). 15-day experiment.
- **collinearity (OFI+CVD+regime=40) → (C) deepest flaw.** three drift-reads = one idea 3×. Path:
  require an INDEPENDENT confirmer to fire, don't stack drift.
- **location optional → (C).** additive scoring, vwap/level not required → fires into extension
  (#15/#16 lost). Path: make location a gate/multiplier.

**🛑 KEY EVIDENCE — turning big_print ON makes it WORSE, not better (in-memory, nothing committed):**
big_print fixed(off) = 17 trades **+2.018R** → percentile(on) = 18 trades **−2.861R** (**Δ −4.879R**).
Not because big_print is wrong, but because (a) the extra bars it surfaces are mostly losers (3 of 4
new trades lost), and (b) via the outcome-blind `max_trades_per_day`/`one_open_position` gates, those
EARLY junk fires **crowd out the baseline's big winners** — #17 (+2.282) and #2 (+1.065) both vanish.
This is the REFRAME proven a THIRD way: **adding a signal to an un-ranked scorer with outcome-blind
gates doesn't create edge — here it destroyed it.** Decision: big_print STAYS inert (fixed/0), like
queue; percentile is an experiment tool gated behind the 15-day rank-test. Its real path is
required-confirmer + loss-aware gate (design), not a switch flip.

**Suppression audit (why only 17 trades, not the "many more" on the chart):** across the 3 days the
signal was QUALIFIED (score≥40) **53 times; 17 fired, 36 blocked** — `max_trades_per_day` 25 (the
3/instrument cap; on 07-16 it blocked a **55.0** — the highest score of all 3 days), `one_open_position`
6, `after_session_cutoff` 3, `cooldown` 2. But taking the 36 would likely LOSE (score doesn't rank, and
07-16 — the most-signalled day, 25 qualified — was the LOSING day): the cap accidentally limited damage.

**THE PATH (sequenced, gated):** ① queue wired ✅ (INERT) · ② big_print — stays inert, do NOT flip
(evidence above) · ③ OFI percentile-rank experiment (15-day) · ④ decorrelate + location gate (design).
Nothing activates (weight>0) until the out-of-sample rank-test earns it. Menu stays CLOSED.

### 🔬 Bar-representation + noise-efficiency study (15-day set) — PRE-REGISTERED 2026-07-17
Pre-registered BEFORE the 15-day data arrives (ranges DECLARED, not fitted). Candidate study for
AFTER 31 Jul, run through the walk-forward harness — **NOT to be eyeballed on the current 5 days.**

**1. QUESTION — does the 100-tick bar carry too much noise?** Compare bar representations for
signal-vs-noise:
- **Fixed tick-count sweep (PRE-REGISTERED range, recorded now): 100 / 200 / 300 / 500 / 1000.**
- **Event bars:** volume bars + tick-imbalance bars (the "volume clock"). Race them against fixed-tick.

**2. METRIC — Kaufman Efficiency Ratio (ER = net move / total path):**
- **DIAGNOSTIC:** objectively measures noise per bar-size (replaces eyeballing with a number). Report
  the ER distribution per representation.
- **Candidate FILTER/FEATURE:** ER as a chop-gate ("trade only when the tape is efficient, skip
  low-ER wander") — directly targets the outcome-blind-gate problem. ER window length + threshold are
  themselves parameters → **gated, not free.**

**3. DISCIPLINE (the whole point):**
- Bar-size and ER-threshold changes **MOVE the baseline** (like big_print). So this runs in
  **replay/research ONLY**; live engine + frozen 17-trade reference untouched. Winners become GATED
  config changes AFTER the rank-test.
- Every sweep through the harness: walk-forward OOS split + permutation null + Deflated Sharpe +
  **PLATEAU detection.** A lone spike (300 great, 200 & 500 bad) = luck → REJECT. A stable region
  (200–500 all decent) = candidate-real. **Plateau is the deciding test.**
- **N-trials counting:** 5 tick-sizes + 2 event-bar types + ER thresholds → the multiple-comparisons
  burden MUST be paid (deflate accordingly). More values tried = higher false-positive floor.

**4. SEQUENCE:** a research item feeding ③ (OFI percentile-rank) and ④ (decorrelate + location gate)
— all post-15-day, harness-gated. **Does NOT run before the data arrives.** Menu stays CLOSED.

### 🧪 THE SCORE IS BUILT ON THE WRONG FEATURES — PRE-REGISTERED hypothesis 2026-07-18
Feature-separation deep-dive over the **53 qualified candidates** (07-15/16/17, NIFTY+BANKNIFTY), each
priced by independent exit sim (N=53, 22 win / 31 loss). Spearman(feature, R) + shuffle-R permutation:

- **What SEPARATES winners (permutation-significant):** **bar delta** ρ=+0.425 **(p=0.002)**, **aggressor
  volume imbalance (buy/sell)** ρ=+0.494 **(p=0.001)**, **stop-width (R-unit%)** ρ=+0.473 (p=0.001).
  Best usable combo `delta-strong & price>VWAP`: N=22, +0.602R/trade, p=0.002.
- **What does NOT:** **OFI — the HEAVIEST weight (25) — is ANTI-predictive, ρ=−0.29** (more aligned OFI
  → *worse* outcome). **CVD** borderline (ρ=+0.267, p=0.056). **The composite SCORE is FLAT: ρ=+0.066,
  p=0.65** — pure noise. The scorer's own core `OFI & CVD` combo: N=10, perm-p=0.241 (indistinguishable
  from luck).
- **The finding:** score≠outcome is not just "3 days too few" — **the score is flat because it weights
  the wrong things.** OFI (its biggest input) hurts; delta / volume-imbalance (which work) carry ZERO
  weight. This is a second, feature-level confirmation of [[THE REFRAME]].

**PRE-REGISTERED 15-day OOS test (do NOT change anything live first):** re-weight the scorer TOWARD
**delta + aggressor volume-imbalance**, **drop or invert OFI**, add a **min-stop-width filter** — then
**confirm it ranks out-of-sample** on the 15-day set (walk-forward OOS + permutation null + Deflated
Sharpe) BEFORE any live change. Menu stays CLOSED until it passes.

**N-CAVEAT (mandatory — this is a LEAD, not an edge):** N=53 but **autocorrelated** (07-16 morning
alone ≈ 10 near-identical NIFTY longs) → effective N ≪ 53, so the permutation p's are **optimistic**
(samples not exchangeable). **In-sample, 3 days, fat-tail-driven avg-R, multiple-comparison burden**
(13 features + 8 combos + an all-pairs auto-scan → discount the auto-best `volimb&level` N=10 p=0.02).
The three single features (delta/volimb/stop-width, p≤0.002 on full N) are the trustworthy part;
everything combo-level needs the 15-day OOS confirmation. **Not edge — the sharpest lead yet.**
(Chain features pcr/net_gex/atm_iv NOT tested — the option-chain replay risked an OOM host-hang on the
3.8 GB box; capture them in a lighter per-instrument pass on the 15-day set.)

### 🛡️ STRESS TEST BROKE MOST OF IT — the ONE surviving hypothesis (2026-07-18)
**SUPERSEDES the entry above.** A 7-angle attack (holdout, de-cluster, per-instrument/day, drop-fat-tail,
permutation-on-effective-N, costs, devil's-advocate) demoted most of the "wrong features" finding.

"7-angle stress test (07-15/16/17, effective N~14-18 after de-clustering, confidence 35/100) BROKE most
of the earlier finding: volume-imbalance, the OFI-anti-signal, and the fat-tail avg-R edge are 3-day
artifacts (BANKNIFTY inverts, effect carried by one 07-16 NIFTY morning move, dies after costs). ONLY
'bar delta + price on correct side of VWAP' survived holdout + de-clustering + permutation (delta
p~0.03-0.05).

15-DAY OOS TEST (pre-registered): test ONLY delta+VWAP-side as a gate/weight, per-instrument (NIFTY and
BANKNIFTY separately, since 3-day showed inversion), through the walk-forward harness (OOS + permutation
+ DSR + plateau + costs). Confirm it ranks out-of-sample AND survives costs before any live change.
Everything else = rejected as 3-day artifact."

**Reconciliation with the entry above (for the record):** the deep-dive's headline separators do NOT
survive equally. Per-angle: (3) instrument split — delta/volimb ρ≈0.54/0.52 on NIFTY but ≈0.08/0.04 on
BANKNIFTY (edge is NIFTY-only; OFI-anti is BANKNIFTY-only → the two halves lived on different
instruments); (2) de-cluster 53→29 (≈45% were near-duplicates) — delta/volimb survive but OFI-anti
weakens; (5) permutation on de-clustered N — delta p=0.035, volimb p=0.016, stop-width p=0.004 survive,
**OFI-anti DIES p=0.42**, score noise p=0.60; (6) after 0.55R cost the best combo nets **+0.05R**
(rank survives, profit dies); (1) holdout survives 2/3 days, weakens on 07-17. Net confidence the whole
thing replicates OOS = **~35/100**; the durable sub-claim is only "the composite score does not rank
(ρ0.07, p0.65)" + "delta+VWAP-side ranks better than it, on NIFTY, in-sample." Carry delta+VWAP forward;
reject the rest. Links [[THE REFRAME]]. Menu stays CLOSED.

### ❌ EFFICIENCY RATIO (lb 10) REJECTED — it looks the wrong way (2026-07-19)
"Kaufman ER (lb 10) tested on BOTH the 17-cap and the 48 caps-off sets. Verdict: NOT a fake-vs-strong
filter — it's inverted. On caps-off: high-ER 'clean' entries were WORST (-3.91R), low-ER 'chop' was the
only positive bucket (+3.49R) but that is entirely 2 fat tails (14:12 BANKNIFTY +7.17R at ER 0.07, 10:47
NIFTY +2.44R at ER 0.10). De-clustered ER rho -0.22, permutation p=0.32 = luck. Gating high-ER worsens
caps-off to -5.07R. ROOT INSIGHT: pre-entry ER looks BACKWARD (past 10 bars) but P&L comes from the move
AFTER entry — high pre-entry ER means you're LATE/exhausted; the monsters were entered DURING chop before
the move. A pre-entry cleanliness filter looks the wrong way. Drop ER (lb 10) as a gate; 15-day sweep may
try other lookbacks but the prior and the sign are both against it. Survivor: delta + VWAP-side +
adequate stop-width."

(Consistency note: this REVISES the pre-registered bar-representation/ER study's optimism about ER as a
chop-gate — ER stays in the 15-day lookback sweep, but the 3-day prior is negative and the effect sign is
against the hypothesis. Gaussian channel [also 2026-07-19] separately found redundant with VWAP-side /
regime. The only thing that keeps surviving is [[delta + VWAP-side]] + stop-width. Menu stays CLOSED.)

### 🔒 OOS EVALUATION WINDOW — FROZEN 2026-07-22 (before the window completes)
This block is a PRE-REGISTRATION. It is frozen; nothing below is to be edited after the window
completes except an NSE-holiday miscount correction (documented inline).

- **Window** = 15 consecutive NSE equity trading sessions, STARTING **2026-07-23**, excluding
  NSE-declared holidays and weekends. (Ends **~2026-08-12**, exact end pinned against the official
  NSE 2026 holiday calendar.)
- **Rationale:** the delta+VWAP-side rule was frozen ~2026-07-18, AND a non-binding 5-day dry-run on
  2026-07-15..21 was already run/examined on 2026-07-22. Therefore days **2026-07-13/15/16/17**
  (pre-rule-freeze) and **2026-07-20/21/22** (already seen via dry-run) are EXCLUDED from the OOS
  window — they are not blind. The window contains only sessions whose delta+VWAP evaluator output
  had never been examined at freeze time.
- **Feeds the pre-registered 15-day test verbatim:** delta+VWAP-side only, per-instrument (NIFTY and
  BANKNIFTY SEPARATELY), full harness — OOS + permutation + DSR + plateau + costs; G2 gate PF>=1.5
  after costs. No re-fitting, no day added/dropped after freeze except to correct an NSE-holiday
  miscount (documented).
- **Frozen as a RULE, not a hand-typed date list** — [[window_builder]] (research/window_builder.py)
  generates the list from this rule when the sessions complete.
- **Computed enumeration at freeze time (from the RULE + repo holidays.yaml; no NSE holiday falls in
  this span — the Jun-26→Sep-14 gap):** 2026-07-23, 07-24, 07-27, 07-28, 07-29, 07-30, 07-31, 08-03,
  08-04, 08-05, 08-06, 08-07, 08-10, 08-11, 08-12. End = **2026-08-12 (Wed)**. This enumeration is the
  rule's output at freeze, recorded for the audit trail; the rule — not this list — is authoritative
  if a holiday-calendar correction is ever needed.

### 🧪 IN-SAMPLE LEDGER — veto hypotheses (research-lane, NOT registered)
2026-07-22: 2 further veto hypotheses explored IN-SAMPLE on 07-15..21 (VWAP K=1 SD-band veto;
3x-volume absorption veto), frozen params, one run. Absorption near-inert (2/367 fires). Band veto
removes 40-58% of fires and improves NET on both instruments while GROSS stays ~flat — removed
fires were ~gross-neutral in aggregate, so the net gain ~= cost savings from trading less, not
evidence of trade selection; also trims fat-tail winners; all configs remain net-negative.
In-sample only, not a registered result; carries to OOS only if pre-registered (Round 2).

2026-07-23 addendum: random-removal null (1,000 draws, seed 20260723, matching per-day removal
counts) — band veto net at the 9.6th percentile of the null on NIFTY (worse than ~90% of random
removals; removed fires gross-neutral, all gain = cost savings) and 59.5th on BANKNIFTY (inside the
null body). No top-tail selection on either instrument. Band veto = pure cost mechanics, mildly
anti-selective on NIFTY; dropped as a Round-2 selection candidate, retained as a documented negative.

2026-07-23: bar-size exploration menu expanded to {100..1000 step 100} for the burned-days
in-sample sweep — declared before any per-size result exists. R2-13 pre-registered core
remains {100,200,300,500,1000}; additions {400,600,700,800,900} are exploration-only. 18
curves (9 sizes x 2 instruments) acknowledged into the multiple-comparisons burden — DSR
N-trials discount widens accordingly. No post-result menu additions.

2026-07-24: bar-size sweep results (in-sample 07-16..21, menu {100..1000/100} per the
2026-07-23 amendment). Cost/trade falls monotonically with size (NIFTY 0.394→0.170R,
BANKNIFTY 0.225→0.092R), fires shrink 177→18 — most net movement along the size axis is
cost mechanics, per the veto-null precedent. Sparse positives on tiny N: NIFTY s900/s1000
net +0.31/+2.34 (13-18 trades); BANKNIFTY de-dup positives s200-400 (+2.95/+0.65/+0.37).
Instruments point in opposite directions. Structural: at s1000 median bar 39-52min vs the
60-min wall-clock sleeper — exit machinery near-degenerate at large sizes. No adoption;
cells of interest carry only to R2-13's fresh-data exam under the 18-curve discount.

2026-07-24: shadow-trio ranking probe (in-sample, burned depth-days 07-16..21,
fires-only, 6 comparisons declared upfront, 1000-perm null seed 20260724). No component
ranked outcomes positively. Tail excursions are INVERSE only: pain_map NIFTY rho -0.212
(0.1st pctile; sign flips to +0.048 / 73.8th on BANKNIFTY) and book_ofi BANKNIFTY -0.138
(2.9th; NIFTY -0.103 / 10.4th). queue_imbalance inside the null body on both (82.0/25.1).
Activations sparse (15-28% of fires). Consistent with FEED_PHYSICS: tick-rule OFI is
PHYSICS-BOUNDED (~8-10% mis-sign floor); pain_map is PHYSICS-CLEAN, so its NIFTY
excursion is not feed-noise-explainable. In-sample R2-priority info only; any
contra-indicator use = NEW hypothesis requiring fresh pre-registration.
2026-07-24 correction: qi/pain_map shadow store recording began post-rebuild (07-24
backfilled offline; 24-Jul pipeline ran pre-rebuild image 40584).
2026-07-24 identity clarification: the probe's pain_map values were 0/0.1 only — the
max-pain-side nudge; the buildup-FUEL term has never populated (chain first-grid pins
ltp=None at first snapshot, engine.py:209-211, so _buildup_matrix always returns {} —
EMPTY-GRID plumbing gap, not intraday rarity). The NIFTY inverse excursion is therefore a
MAX-PAIN-SIDE finding, not trapped-pressure. Fuel fix = shadow-side one-liner, ledger item.

### 🚨🚨🚨 THE SHARPEST FINDING — all 17 trades are the SAME trade (2026-07-17)
Read all 17 clean trades' full component breakdowns (glass box, in-memory OFI-on/threshold-40).

**STRUCTURAL FINDING (verbatim):** "All 17 trades are the SAME trade: book_ofi 25 + cvd_confirm 10
+ regime 5 = exactly 40, the threshold. Those three are collinear — one directional read counted
three times. This isn't confluence, it's one idea wearing three hats. big_print (weight 20, the
institutional footprint a tape reader would demand) contributes 0.000 on all 17. queue (0) is dead.
So 45 of the 65-point ceiling is either redundant or off. A 15-year tape reader would pass on all 17
— none is a story, they're all the same reflex. THIS is why the winners were unseparable: the score
isn't reading the tape, it's reading its own redundancy."

Per-day: **07-15 +4.336R, 07-16 −1.064R, 07-17 −1.255R** — one positive day out of three, and it
carries everything.

**🚨 NEW BUG surfaced — OFI SATURATES IN THE FIRING REGION (book_ofi = 1.000 → 25 on ALL 17).**
Investigated (words + numbers, no fix): it is NOT last night's sign-saturation, and NOT universal —
the graded floor+scale WORKS on the bar population (only **23% (NIFTY) / 30% (BANKNIFTY) of ALL bars
saturate**; median activation **0.45 / 0.53**). The all-17 saturation is a **SELECTION EFFECT**:
threshold 40 = OFI(25)+CVD(10)+regime(5), so firing REQUIRES `book_ofi=25` = activation 1.0 = |OFI| ≥
the saturation point → only saturated-OFI bars can ever reach 40.
- Saturation point = floor+scale = **17,000 (NIFTY) / 8,000 (BANKNIFTY)**, which sits at ~**p85** of
  per-bar |OFI| (med 8.8k/4.7k, p90 32k/13k, max 154k/54k). Firing lives ABOVE p85.
- The 17 firing bars are **1.1×–9.1×** the saturation point → all clamp to 1.0. So OFI **grades the
  bars that never fire and is BINARY on the ones that do** — zero discrimination among trades.
- Answer to "scale too small / floor doing nothing": **NEITHER exactly.** Scale is fine for the
  population (median 0.45); floor (2k/1k) trims only the bottom ~10%. The flaw is the scale saturates
  INSIDE the firing region. Grading the firers would need a ~10× wider scale (~150k) — which would
  under-grade the bulk. **Not fixable by scale alone**; the deeper cause is the threshold forcing OFI
  to max + the OFI/CVD/regime redundancy. NO FIX tonight.

**IMPLICATION (founder, verbatim):** "OFI is not broken — it grades the bar population (median 0.45,
only ~25% saturate). But the threshold MECHANICALLY selects saturated bars: reaching 40 requires
book_ofi=25 = activation 1.0 = |OFI| above the saturation point. So OFI grades the bars that never
fire and is BINARY on the ones that do — zero discrimination among trades. The 17 firers span 1.1x to
9.1x the saturation point and all score identically. This is NOT fixable by widening the scale (it
would under-grade the bulk). The cause is upstream: (a) the threshold forces OFI to max, and (b)
OFI/CVD/regime are collinear, so 40 of the 65-point ceiling is one idea. Together they mean the score
CANNOT rank the trades it fires — which is exactly what the N=17 winner-separation found. Two
independent routes, one conclusion."

**OPEN DESIGN QUESTION for the 15-day set (do NOT answer now):** does OFI need PERCENTILE-RANKING
(like big_print got tonight) rather than a floor+linear scale? A percentile rank would grade the
FIRING REGION by construction — it's relative to the instrument's OWN distribution, not an absolute
scale, so the tail can't all clamp to 1.0. This is a 15-day-set EXPERIMENT, not a tonight fix. (Note
the symmetry: big_print already got percentile-ranking tonight for exactly this reason; OFI's
floor+scale is the older pattern and may want the same treatment. Menu stays CLOSED.)

In-sample, arbitrary threshold 40, GROSS, N=17 — not a conclusion, but the sharpest statement of the
problem yet.

### 📏 THREE CORRELATIONS across the 17 trades (2026-07-17) — words + numbers, N=17, NOT conclusions
Measured on the 17 verified trades (in-sample, threshold 40, GROSS). Significance bar for N=17:
Spearman ρ ≈ **0.49** (two-tailed p≈0.05). Only ONE number below clears it.

**1. R-UNIT vs OUTCOME — the one number that clears significance.**
| predictor | Pearson r | r² | Spearman ρ |
|---|---|---|---|
| R-unit (raw points) | +0.274 | 0.075 | +0.579 |
| **R-unit (% of entry)** | +0.428 | 0.184 | **+0.777** |
Use the **% version, not raw points** — NIFTY ~24k vs BANKNIFTY ~57k, so raw points conflate
instrument scale (91.7 BANKNIFTY pts = 0.159% ≈ 19.2 NIFTY pts = 0.080%). win R-unit% mean **0.080%**
[0.041–0.159] vs loss **0.046%** [0.030–0.103]. The **4 smallest R% all lost** (#15, #16, #14, #8);
3 of the 4 largest won. **Spearman ρ=+0.777 clears the 0.49 bar — the only number in this whole
exercise that does.**
- **SHARPENING (verbatim):** "small R loses is substantially TIGHT STOP = NOISE DEATH — gating on
  min_viable_R gates stop-width, not edge. It's the same lever as the min_stop floor seen from the
  other end." (The 4 smallest-R trades had stops at the `min_stop_pct` floor 0.030–0.037%: the natural
  stop was inside the noise and got whipsawed out before target.)
- **CAVEAT:** post-hoc threshold selection (40 chosen after the fact), so even a significant ρ is a
  **hypothesis for the 15-day set**, not evidence.

**2. |OFI| MAGNITUDE vs OUTCOME — the bigger finding: raw OFI doesn't rank either.**
| predictor | Pearson r | Spearman ρ |
|---|---|---|
| \|OFI\| ×sat multiple | +0.406 | **+0.120 ≈ null** |
The Pearson **+0.406 is ONE leverage point** — #1 at 9.1×/+2.68R, a lone outlier 2× beyond any other
|OFI|; drop it and the linear correlation collapses. Rank correlation (outlier-robust) **ρ=0.120 ≈
zero**. Top-4 |OFI|: #1(9.1×)+2.68 ✓, #6(4.6×)+0.50 ✓, **#8(4.4×)−1.01 ✗, #7(3.0×)−1.01 ✗** — two of
the four strongest imbalances LOST. Confirms the founder's read: **raw |OFI| magnitude does not rank
winners.**
- **YELLOW FLAG (verbatim):** "percentile-ranking a signal whose raw rank is uncorrelated with outcome
  won't manufacture an edge — this LOWERS the prior on OFI-percentile being the fix. Still run the
  experiment, but as a yellow flag, not a green light." (This is *bigger* than the saturation bug: we
  knew the saturated activation can't discriminate; this says the **raw pre-saturation magnitude**
  can't either. Percentile-ranking preserves rank order by construction — but if the rank itself is
  uncorrelated with outcome, preserving it buys nothing. Links the [[OPEN DESIGN QUESTION]] above.)

**3. SCORE vs OUTCOME — third independent score≠outcome confirmation.**
score vs gross R → Pearson **−0.123**, Spearman **−0.140**. Faintly **NEGATIVE** — higher composite
score → marginally *worse* outcome (dragged by #7, the 50.6 top-scorer that lost −1.01). Third route
to the same conclusion (after N=17 winner-separation and the all-17-same-trade structural finding).

All three: N=17, in-sample, arbitrary threshold, GROSS. Hypotheses for the 15-day set, not conclusions.

### 🚦 COOLDOWN GATE — not broken, LOOSE + OUTCOME-BLIND (2026-07-17)
The 07-16 morning cluster (three NIFTY longs in 14 min, combined **−1.524R**) is NOT a gate failure —
the gate passed all three legitimately. Config (`tape_config.yaml`, matches code default), enforced
**per-instrument** (`self._gate: dict[sid→GateState]`, `signals/gates.py`):
`cooldown_s: 300` · `max_trades_per_day: 3` · `one_open_position: true` · `first_minutes_no_entry: 5`.
Exact gaps: **#6 09:18:53→exit 09:23:48 (+0.497); #7 09:26:44 (471s after #6 signal, >300s ✓) →exit
09:29:58 (−1.010); #8 09:33:02 (378s after #7, >300s ✓) →exit 09:36:17 (−1.011).** Each fired >300s
after the prior signal AND after the prior position had closed → all three clear the gate as
configured. `max_trades_per_day:3` is why NIFTY stopped at three that morning.
Two specific loose shapes:
- **300s is short** — allows **3 same-direction entries in a 14-min window**; in chop that's three
  bites at one losing idea.
- **The cooldown is OUTCOME-BLIND** — no longer cooldown after a loss, no same-direction re-entry
  lock. **#6 stopped → #7 re-entered the identical long 3 min later → stopped → #8 re-entered it
  again.** The gate counts time + open-position, never outcome or repetition.
- **15-day-set CANDIDATE: loss-aware cooldown / same-direction re-entry lock** — a **GATE change, not
  a signal change**. Menu stays CLOSED (do not implement now).

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

### Depth (R1) gap-verdict recalibration (2026-07-16) — FOURTH verdict correction
The above three fixed **R0** (ticks). Depth's `depth_verify` had the same untuned "any
GAP → PARTIAL" rule, so every clean depth day read PARTIAL. Recalibrated with the SAME
four moves, each **derived from depth's own measured data**, not copied from R0:
- **gap_threshold 10s** — measured cadence on the ~200ms (5Hz) snapshot feed is 3–7s;
  `>10s` only increments an observability count, it does not drive the verdict.
- **Liquid-scoping → `{NIFTY_FUT, BANKNIFTY_FUT}`** — the only OFI-tradeable instruments.
  The 2 thin index futures (FINNIFTY/MIDCPNIFTY) + 14 constituent equities go quiet for
  minutes legitimately (ANGELONE/CDSL sit silent for 5–10 min mid-session on 07-14) — their
  gaps/empties/one-sided are LOGGED on the instrument entry but never drive PASS/PARTIAL.
  Structural corruption (unreadable / missing columns) is still FAIL for ANY instrument.
- **Outage rule** — a single LIQUID in-hours gap `> 60s` = a real hole → PARTIAL. Replaces
  "any gap". Also PARTIAL on any reconnect/disconnect, liquid coverage `< 95%`, disk event,
  or no clean session-end.
- **Two-sided market-hours clip `[09:15, 15:30]`** — and here depth DIVERGES from R0 on
  purpose: **depth's post-close gaps RESOLVE** (the feed winds down and the watchdog logs a
  15:30→~15:33 gap that then closes), whereas R0's session-end gaps run **open-ended**. So
  depth clips BOTH ends (pre-open AND post-close credited 0), R0 clips only the open end.
  This is read straight off depth's events: on 07-14 the largest liquid gaps are a 246.6s
  NIFTY gap 09:07:56→09:12:03 (pre-open) and a 196.6s BANKNIFTY gap 15:29:59→15:33:16
  (post-close) — both no-trade artifacts. `liquid_max_gap_raw_s` keeps the pre-clip value.

**6-day re-audit (before persisted / after recalibrated):** 07-09 & 07-10 N/A (depth
recorder deployed 07-11); **07-13 PARTIAL→PARTIAL** (DISK_FULL 14:33 + no clean
session-end + liquid cov 83.8% — all real; in-hours liquid gaps max 12.6s, correctly <60);
**07-14 PARTIAL→PASS** (see asymmetry below); **07-15 PARTIAL→PASS** (liquid 99.4%, clean);
**07-16 PARTIAL→PASS** (liquid 99.3%, clean). The known-bad disk day still PARTIALs for its
real reasons. Regression tests lock both directions incl. a **simulated 300s in-hours
NIFTY_FUT outage → PARTIAL** (proof a real depth outage still flags).

**🔑 07-14 R0/depth ASYMMETRY IS CORRECT — do not "fix" it.** On 07-14 R0 verifies
**PARTIAL** (coverage 43.4%) while depth verifies **PASS** (100.1%, single clean session).
This is not a contradiction: at **12:46 on 07-14 we deployed the IDX_I spot fix and
restarted ONLY `orderflow_recorder`** — the deploy report at the time confirmed *"depth
container id af2225505493 unchanged, still Up — untouched."* R0 was fractured mid-session
(hence 43.4%); depth ran one uninterrupted 09:05→15:45 session (one SESSION start, one
SESSION end, zero reconnect/disconnect/disk). The "multi-session" label that day was **R0's,
not depth's.** Evidence and deployment history agree — anyone who later sees "same day, two
verdicts" and tries to reconcile them is wrong to.

**🔑 G0 reads R0 ONLY — depth verdicts do NOT touch G0.** `pulse._g0_counter` streaks on
`data/{d}/report.json` (R0's day-root, `status=="PASS"`); depth's `data/{d}/depth/report.json`
is loaded separately into `depth_rep` for DISPLAY only and never feeds the counter (verified
in `alerts/pulse.py`). So this recalibration flipping 07-14/15/16 depth to PASS has **zero
effect on G0**. **G0 stays 2/5 (07-15, 07-16)** — driven entirely by R0's report.json. Never
conflate the two verdicts.

> ⚠️ **GOVERNANCE — verify logic has now been corrected FOUR times** (R0: gap threshold
> 3→10, volume magnitude verdict, pre-open market-open clock; R1: depth liquid-scoped
> outage rule + two-sided clip) — all were pre-first-clean-day blind guesses that only
> surfaced against real recorded days.
> **NO further verify verdict changes (R0 OR R1) without a full re-audit of ALL recorded
> days (07-13 onward), showing each day's status + driver, and confirming the known-bad
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

### 🚨 S3 BACKUP INCIDENT (2026-07-16) — G0 Day-1 was silently short in S3 for 2 days
**Trust failure, not just a bug.** The Daily Pulse's first act (dry-run against real data)
surfaced that `data/2026-07-15/backup.json` had `success:false` — and it had sat SILENTLY
since 07-15. We believed G0 Day-1 was sealed in S3; it was not. Root cause: `s3_backup.
backup_day` enumerated `day_dir.rglob("*")` INCLUDING a transient depth `.consolidate.tmp`
file; consolidation removed it mid-backup, `f.stat()` threw `FileNotFoundError`, and the
outer `except` ABORTED the whole loop — **440 files uploaded, then aborted; the tail (~15
files) never attempted.** `success` never reached true. TWO independent defects: (a) transient
`*.tmp` files should never be in the backup set; (b) one bad file must never abort the whole
backup. FIXED both (commit pending): (a) exclude `*.tmp`; (b) per-file try/except → log +
`fail_count++` + CONTINUE; `success = fail_count == 0` only when a REAL file failed after
retry. Tests: tmp excluded; one bad file → other 3 uploaded, success=false, all attempted.
**RECOVERY:** re-ran `make backup-day DAY=2026-07-15` (tmp long gone; `_upload_one` HEAD-verifies
so it's idempotent) → complete.

**`parts/` EXCLUSION from backup — APPROVED (founder, 2026-07-16), do not re-litigate.**
The backup uploads FINALS only; `parts/` + `depth/parts/` are excluded (like `analysis/`).
Reasoning: finals are row-complete + VERIFIED (verify_session schema-checks + row-counts them)
and atomically written (fsync); parts are transient rotation/journal scratch that
consolidation folds INTO the finals. On 07-15 there were ~198K parts (~9GB) vs 460 finals
(~489MB) — uploading them = hours + S3 cost for ZERO durability gain, and it's what aborted
the backup. Same call the founder made on 07-14.
**DURABILITY READ (finals-only in S3 — acceptable? my read: YES, and it's SAFER):** a final
that passes verify is proven valid at write; S3 gives 11-nines durability + upload checksums,
so the S3 final IS the durable source of truth. Parts are useful ONLY to re-consolidate a
final that was bad AT CONSOLIDATION time — which verify catches (bad final → PARTIAL/FAIL →
re-consolidate from parts BEFORE they're deleted). Once a final is verified PASS + in S3,
parts add no durability — they're a local copy of data already safe in S3. The residual risk
(post-upload S3 bit-rot) is negligible vs the risk the parts ACTUALLY caused: ~80GB of dead
parts filling a 96GB disk and crashing recording (13-Jul). So finals-only trades a negligible
risk for eliminating a proven-catastrophic one. Condition: keep parts until (final verified
PASS AND backed up), then delete (see the parts-accumulation note below).

**Investigation — was there data loss / silent deletion? NO.** `recorder/retention.py`
`_delete_reason` KEEPS a day unless `report.json` exists AND (`s3 disabled` OR `backup.json
success`). A `success:false` day returns "awaiting successful S3 backup" → **never deleted**
(same guard in `depth_retention.py`). Plus the newest `retention_days`(10) are always kept and
07-15 is 1 day old. So the LOCAL copy was always safe — retention is the net that held. **The
hole was SURFACING, not deletion:** the only signal was a `log.error` at backup time (`main.py`),
which nobody reads. **Fix going forward: the Daily Pulse shows S3 ✅/❌ same-day** (this is
exactly how we caught 07-15). Enhancement candidate: have the retention sweep count + surface
"N days stuck awaiting S3 backup" so a PERSISTENT backup failure (which also blocks local
rotation → disk creep) is visible, not just same-day.

### 🚨 PARTS ACCUMULATION — the 13-Jul disk-crisis root cause (2026-07-16 investigation, HIGH)
**Consolidation folds parts→finals but NEVER deletes the parts.** Measured disk (per day):
07-13 **7.6GB** parts / 455MB finals; 07-14 **7.0GB** / 320MB; 07-15 **9.3GB** / 559MB; 07-16
**9.2GB** / 543MB — **parts are 93–95% of every day.** `depth/parts/` is the bigger chunk
(4–5GB/day: journal-mode ~8,800 tiny parts/instrument × 18); top `parts/` is R0 rotation
(2–4GB/day). 07-09/07-10 have ~5–12MB parts (pre-depth / salvaged), i.e. the bleed started
07-13 when depth came online.
**Mechanism:** `_stream_consolidate` (writer.py) merges parts→final and returns — no `unlink`.
`InstrumentWriter.finalize` (writer.py:350-355) and depth `close()` both consolidate, neither
cleans up. `salvage.py:14` EXPLICITLY leaves parts as a crash-recovery source; normal EOD
consolidation leaves them too but with NO intent/comment and NO cleanup window → effectively
an OVERSIGHT (the salvage recovery-pattern applied without bounding parts' lifetime).
**Retention reach:** `retention.py` `rmtree(day_dir)` DELETES the whole day incl. parts at
day-10 — but ONLY if safe (report exists AND backup success). So within 10 days parts survive
(no cleanup); at day-10 they go with the day IF backup ok. **COMPOUNDING FAILURE:** a
`success:false` day is KEPT INDEFINITELY (retention refuses to delete) → its parts NEVER go →
unbounded growth. And backups WERE failing silently (the S3 incident above) → the two bugs
stack into the disk crisis. 10 days × ~8GB = ~80GB dead parts on a 96GB disk.
**Right fix (proposed, NOT built — investigate/gate first):** parts are LOCAL-ONLY recovery
scratch; finals go durably to S3. So DELETE a day's parts as soon as (final verified PASS AND
S3 backup success) — the exact moment parts stop being useful (final proven good AND durable).
That bounds parts to ~same-evening (≈0.5GB/day steady state, from ~9GB) while preserving the
recovery window exactly as long as it's actually needed. Parts retention ≠ finals retention:
finals keep 10 days local + S3-forever; parts keep only until verified+backed-up. Filed HIGH.

### Auto-evening pipeline — runs in its OWN capped container, NOT the recorder's cgroup (2026-07-16)
After EOD, the full analysis chain (levels.daily → tape → levels → chain → signals → alerts,
~55min, **measured peak ~1.25GB RSS**) runs so the day's X-ray is on disk by ~16:40 instead of
the founder waiting ~55min. ARCHITECTURE (founder-gated): a **SEPARATE one-shot container**
(`docker-compose` `evening_pipeline` service, `profile: manual`, own `mem_limit 2000m`), triggered
by a **HOST cron ~15:50 IST**, NOT by the recorder. WHY not in the recorder / not raising its cap:
host RAM is only **3814MB** with the live-money stack co-resident (backend/celery/postgres/redis
~550MB); the recorder's **1.5G cap IS its recording-hours leak-fuse**. Raising it to 2.5G would
(a) leave ~314MB for OS+live-money after recorder(2.5G)+depth(1G), and (b) let a recording leak
reach 2.5G before the cgroup fires → HOST OOM could kill **postgres/backend (live money)**. The
separate 2G container keeps the recorder at 1.5G (fuse intact) and gives the burst its own cgroup;
if the pipeline runs away, ITS cgroup OOM-kills it, never the recorder or live-money. NOT
recorder-triggered because that would need `docker.sock` mounted in a live-money-adjacent
container (privilege escalation) — a host cron is unprivileged. Guards: hard total budget
(5400s) + per-step timeout (2400s, SIGKILL); best-effort (a step failure is recorded, chain
continues). **Daily Pulse** (`alerts/pulse.py`, `alerts.pulse_enabled`, SEPARATE from signal
`alerts.enabled` — sends session health even when signals are off): recording verdict+coverage,
spot/VIX, depth, S3, disk, **G0 day N/5**, candidates/top/fired, pipeline status. `fire_threshold`
untouched. G0 counter reads persisted `report.json` (accurate once every day is written by the
fixed verifier).

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

2026-07-24 — ROUND-2 PORTFOLIO FRAMING (declared BEFORE the Market-DNA study
ran): Round-2's goal = seat a PORTFOLIO of 3-4 small, independent, validated
edges across distinct families (bias/trend, breakout-follow OR fade,
mean-revert, option-vehicle) rather than one mega-composite. Sizing stays
conservative — contest-style aggression never on live money. The Market-DNA
study (pre-declared metrics M1-M5, burned days only) informs Round-2
PRIORITIZATION only; nothing is adopted from it. Five design drafts sealed
pre-study at commit 39539e7.


2026-07-25: D5 exploration backtest (sealed spec 39539e7; rulings-of-record: G4=DQ+bucket
only with spread/OR-width UNSEALED-OMITTED, level-anchored R-unit UNSEALED-BY-ANCHOR,
07-13 burn-in; branch feat/orderflow-d5-explore @ 088165f; in-sample pre-window days
07-13..22, descriptive, NO adoption). 88 OR-break episodes, 4 gate-passing trades
(1W/3L, gross -1.5R; net costed 1/4 — chain cost cache is NIFTY-only, BANKNIFTY never
estimated). BASE RATE: ~73% of breaks were stop-first at the -1R/+1.5R bracket — a
THIRD independent corroboration of the mean-reverting character alongside Market-DNA
M1 (VR<1, ac1<0) and M4 (VWAP reversion 12/12) — descriptive, in-sample. Anomaly A:
the level-anchored R-unit produced a 0.70-pt R with a 6.42R round-trip cost — R-unit
definitions MUST be sealed WITH a stability floor (min_stop_atr analogue). G3 LAR-veto
fired once and was wrong that once (N=1 — no conclusion).
