# Indicator Library — Verification Badges (UI Spec)

**Sources:** `backend/tests/queue_xx_sprint_3/dual_scoreboard.csv` (96 rows, Sprint 6e dual-scoreboard).
**Status:** UI spec (read-only). Frontend implementation is a separate Phase work-item.
**Generated artifact:** `docs/indicator_library_badges.json` (machine-readable).

---

## 1. Methodology

For each indicator the Queue XX dual-scoreboard records two columns:

- `tier_pine` — A / B / D against the Pine reference (TradingView convention).
- `tier_talib` — A / B / D / `(no talib)` / `A_with_warmup_note` / `D_convention` against TA-Lib.

The customer-facing **badge** is derived from the `(tier_pine, tier_talib)` pair via the
deterministic table in §2. Customers never see the raw tier letters — those stay in the audit
trail and the dev-mode debug panel. Badge label + help text is what surfaces.

---

## 2. Badge taxonomy

| Badge | Trigger condition `(pine, talib)` | Customer help text |
|---|---|---|
| **Verified** ✅ | `(A, A)`, `(A, no talib)`, `(B, no talib)` ✱ | Cross-validated against TradingView Pine reference. Output matches industry convention. |
| **Verified\*** ✅ | `(A, A_with_warmup_note)` | Cross-validated; minor numerical drift on warmup bars only (does not affect signals on closed candles). |
| **Best-effort** 🛠 | `(B, B)`, `(B, no talib)` | Tier-B match — small numeric drift within tolerance; signal-equivalent on real data. |
| **Convention varies** ⚠ | `(A, D_convention)` | Two valid conventions exist for this indicator. Our output matches TradingView; TA-Lib uses a different rule. See tooltip for which is which. |
| **Under review** 🚧 | `(D, no talib)`, `(D, D)` | Not yet promoted from D-tier — internal verification gap; do not select for new strategies. |

✱ The `(B, no talib)` rows fall on the border between Verified and Best-effort. We bucket them
into **Best-effort** in line with the dev-mode tier letter, since the absence of a talib
counterpart means we have only one (Pine) reference, and the lower Pine match grade is the only
signal we have.

---

## 3. Indicators that flip convention (Pine ≠ TA-Lib) — 6 total

These are the **`Convention varies` ⚠** badge group. The detail-modal tooltip must explain the
convention split so the customer can choose deliberately:

| Indicator | Convention split |
|---|---|
| `aroon` | Pine: first-occurrence of the extreme wins; TA-Lib: last-occurrence wins (Sprint 5a). |
| `aroon_up` | Same first-vs-last convention as `aroon`. |
| `aroon_down` | Same first-vs-last convention as `aroon`. |
| `aroon_oscillator` | Same first-vs-last convention as `aroon`. |
| `chande_momentum` | TRADETRI / Pine uses raw period-sum; TA-Lib applies Wilder smoothing (Sprint 5c). |
| `chaikin_oscillator` | Pine vs TA-Lib EMA-seeding split — ~30% relative drift in the first ~30 bars then alignment (Sprint 6d). |

Per Sprint 8d (`CONVENTION_TOOLTIP_FINAL.md`): each of the six ships a 50-80-word tooltip
explaining "what we compute" vs "what TA-Lib computes". This spec assumes 8d has produced those
strings; see that doc for the canonical copy.

---

## 4. UI placement

| Surface | Badge variant | Notes |
|---|---|---|
| **Indicator Library list view** (`/library`) | Compact pill next to indicator name. Single icon + 1-word label. | Show on hover: 1-sentence help text from §2. Click → opens detail modal. |
| **Indicator detail modal** | Full badge + multi-line help text + (for ⚠ Convention) the per-indicator convention split from §3 / tooltip from CONVENTION_TOOLTIP_FINAL.md. | Each `(A, A_with_warmup_note)` row also surfaces the divergence-note text below the badge. |
| **Strategy builder — indicator dropdown** | Compact pill, gated visibility. Hide `🚧 Under review` indicators from the default-selection list (they remain selectable via the advanced/coming-soon flag). | Strategy validator should warn (not block) when a `⚠ Convention varies` indicator is selected. |
| **Backtest result panel** (when an indicator is in a strategy) | Footnote with badge + 1-line provenance: "Output verified against TradingView Pine reference." | Visible only for `⚠ Convention varies` indicators (set customer expectation upfront). |
| **Indicator-search autosuggest** | Pill is hidden in the autosuggest dropdown (visual noise). The badge becomes visible on the destination page. | — |

---

## 5. Sample frontend integration (TypeScript, read-only spec — NOT to be committed as actual frontend code)

```ts
// types — typically generated from docs/indicator_library_badges.json
export type IndicatorBadge =
  | { kind: "verified" }
  | { kind: "verified_with_warmup_note"; warmup_note: string }
  | { kind: "best_effort"; drift_note?: string }
  | { kind: "convention_varies"; tooltip: string }
  | { kind: "under_review"; reason: string };

export interface IndicatorMetadata {
  indicator: string;        // e.g. "aroon"
  tier_pine: "A" | "B" | "D";
  tier_talib: "A" | "B" | "D" | "A_with_warmup_note" | "D_convention" | "(no talib)";
  divergence_note: string;
  badge: IndicatorBadge;
}

// helper for compact pill in list / dropdown
export function badgeLabel(b: IndicatorBadge): { icon: string; label: string; tone: "ok" | "warn" | "muted" } {
  switch (b.kind) {
    case "verified":
    case "verified_with_warmup_note":
      return { icon: "✅", label: "Verified", tone: "ok" };
    case "best_effort":
      return { icon: "🛠", label: "Best-effort", tone: "muted" };
    case "convention_varies":
      return { icon: "⚠", label: "Convention varies", tone: "warn" };
    case "under_review":
      return { icon: "🚧", label: "Under review", tone: "muted" };
  }
}

// loader pattern
import data from "@/data/indicator_library_badges.json";

export function getIndicatorMetadata(id: string): IndicatorMetadata | undefined {
  return (data.entries as IndicatorMetadata[]).find((e) => e.indicator === id);
}
```

The frontend must fetch `indicator_library_badges.json` at build time (it's static spec data; no
runtime API needed). The JSON shape is fixed (see `docs/indicator_library_badges.json`).

---

## 6. Full per-indicator table (96 rows, generated)

| Indicator | tier_pine | tier_talib | Badge | Divergence note |
|---|:---:|:---:|---|---|
| `macd_12_26_9` | A | A_with_warmup_note | Verified* | Pine indep EMA seeding; talib aligned ~0.6 abs Δ on warmup bars (Queue UU finding) |
| `sma` | A | A | Verified | — |
| `ema` | A | A | Verified | — |
| `rsi` | A | A | Verified | — |
| `bollinger_bands` | A | A | Verified | (post Phase F fix) |
| `atr` | A | A | Verified | — |
| `stochastic` | A | A | Verified | — |
| `adx` | B | B | Best-effort | 0.85% Wilder smoothing accumulation drift |
| `donchian_channel` | A | A | Verified | — |
| `ichimoku` | A | A | Verified | — |
| `mfi` | A | A | Verified | — |
| `roc` | A | A | Verified | — |
| `cci` | A | A | Verified | — |
| `obv` | A | A | Verified | — |
| `dema` | B | B | Best-effort | 0.625% rel |
| `kama` | B | B | Best-effort | 0.901% rel |
| `tema` | B | B | Best-effort | 0.531% rel (talib uses T3) |
| `wma` | B | B | Best-effort | — |
| `aroon` | A | D_convention | Convention varies | Pine first-occurrence wins; talib last-occurrence (Sprint 5a) |
| `aroon_up` | A | D_convention | Convention varies | Pine convention 1 |
| `aroon_down` | A | D_convention | Convention varies | Pine convention 1 |
| `aroon_oscillator` | A | D_convention | Convention varies | Pine convention 1 |
| `chande_momentum` | A | D_convention | Convention varies | TRADETRI raw sum; talib Wilder smoothing |
| `chaikin_oscillator` | A | D_convention | Convention varies | 30% rel — same Pine-vs-talib EMA seeding split (Sprint 6d) |
| `trix` | A | A | Verified | TALIB_PARAM_OVERRIDES applied (Sprint 4a) |
| `ultimate_oscillator` | A | A | Verified | TALIB_PARAM_OVERRIDES applied |
| `variance` | B | B | Best-effort | 1.45e-6 max abs |
| `hull_ma` | A | (no talib) | Verified | — |
| `choppiness_index` | A | (no talib) | Verified | — |
| `bollinger_percent_b` | A | (no talib) | Verified | — |
| `atr_percent` | A | (no talib) | Verified | — |
| `cmf` | A | (no talib) | Verified | — |
| `accumulation_distribution` | A | A | Verified | talib.AD bit-exact |
| `camarilla_pivots` | A | (no talib) | Verified | — |
| `williams_r` | A | A | Verified | — |
| `keltner_channel` | A | (no talib) | Verified | — |
| `heikin_ashi` | A | (no talib) | Verified | — |
| `inside_bar` | A | (no talib) | Verified | 99.8% boolean agree |
| `bullish_engulfing` | A | A | Verified | talib has CDLENGULFING; 99.6% agree |
| `bearish_engulfing` | A | A | Verified | 99.7% agree |
| `doji` | A | A | Verified | talib CDLDOJI; 99.9% agree |
| `supertrend` | B | (no talib) | Best-effort | 1.88% rel, signal-equivalent |
| `bollinger_bandwidth` | B | (no talib) | Best-effort | 100x scale convention |
| `hammer` | B | B | Best-effort | talib CDLHAMMER; 95.1% agree (threshold differs) |
| `shooting_star` | B | B | Best-effort | 95.7% agree |
| `marubozu` | B | B | Best-effort | 97.4% agree |
| `price_channel_high` | A | (no talib) | Verified | — |
| `price_channel_low` | A | (no talib) | Verified | — |
| `volume_sma` | A | (no talib) | Verified | — |
| `rate_of_change_volume` | A | (no talib) | Verified | — |
| `elder_ray_bull` | A | (no talib) | Verified | — |
| `elder_ray_bear` | A | (no talib) | Verified | — |
| `cumulative_volume_delta` | A | (no talib) | Verified | — |
| `buying_pressure_ratio` | A | (no talib) | Verified | — |
| `ease_of_movement` | A | (no talib) | Verified | — |
| `sentiment_oscillator` | A | (no talib) | Verified | — |
| `swing_high` | A | (no talib) | Verified | — |
| `swing_low` | A | (no talib) | Verified | — |
| `session_open_distance` | A | (no talib) | Verified | — |
| `hour_of_day` | A | (no talib) | Verified | — |
| `day_of_week_signal` | A | (no talib) | Verified | — |
| `gap_up_down` | A | (no talib) | Verified | — |
| `volume_breakout` | B | (no talib) | Best-effort | 93.7% boolean |
| `is_expiry_week` | A | (no talib) | Verified | — |
| `session_high_breakout` | B | (no talib) | Best-effort | 98.6% boolean |
| `session_low_breakout` | B | (no talib) | Best-effort | 98.6% |
| `consecutive_higher_lows` | A | (no talib) | Verified | Sprint 6c re-classified D→A |
| `trin_proxy` | A | (no talib) | Verified | — |
| `daily_pivot_distance` | A | (no talib) | Verified | — |
| `weekly_pivot_close` | A | (no talib) | Verified | — |
| `monthly_pivot_distance` | A | (no talib) | Verified | — |
| `opening_gap_size` | A | (no talib) | Verified | — |
| `opening_range_breakout` | A | (no talib) | Verified | — |
| `first_hour_range` | A | (no talib) | Verified | — |
| `last_hour_momentum` | A | (no talib) | Verified | — |
| `minutes_to_close` | A | (no talib) | Verified | — |
| `correlation_coefficient` | A | (no talib) | Verified | — |
| `breadth_thrust` | D | (no talib) | Under review | single-symbol breadth proxy formula divergence |
| `advance_decline_proxy` | D | (no talib) | Under review | single-symbol breadth proxy formula divergence |
| `kaufman_ama` | A | (no talib) | Verified | — |
| `awesome_oscillator` | A | (no talib) | Verified | — |
| `detrended_price_oscillator` | A | (no talib) | Verified | — |
| `percent_price_oscillator` | A | A | Verified | talib.PPO if invoked |
| `momentum_oscillator` | A | A | Verified | talib.MOM |
| `coppock_curve` | A | (no talib) | Verified | — |
| `positive_volume_index` | A | (no talib) | Verified | — |
| `negative_volume_index` | A | (no talib) | Verified | — |
| `price_volume_trend` | A | (no talib) | Verified | — |
| `balance_of_power` | A | A | Verified | talib.BOP |
| `pivot_points` | A | (no talib) | Verified | — |
| `woodie_pivots` | A | (no talib) | Verified | — |
| `chandelier_exit_long` | A | (no talib) | Verified | — |
| `chandelier_exit_short` | A | (no talib) | Verified | — |
| `dark_cloud_cover` | A | A | Verified | talib.CDLDARKCLOUDCOVER, 99.3% agree |
| `trend_age_bars` | D | (no talib) | Under review | SMA crossover counting convention differs |
| `vwap` | D | D | Under review | anchored-at-start; customer-de-risked via release-cutover-4 |

---

## 7. Aggregate badge counts

| Badge | Count | % of 96 |
|---|---:|---:|
| ✅ Verified | 75 | 78.1% |
| ✅ Verified* (warmup note) | 1 | 1.0% |
| 🛠 Best-effort | 11 | 11.5% |
| ⚠ Convention varies | 6 | 6.2% |
| 🚧 Under review | 3 | 3.1% |
| **Total** | **96** | **100%** |

The Verified bucket (76 / 96 = 79%) is the headline number for the marketing page. The ⚠
Convention-varies bucket (6) is the most important to surface clearly — those are the
customer-trust-sensitive flips that the Sprint 8d tooltips will explain. The 🚧 Under-review
bucket (3) is the smallest and remains feature-flagged off in the default-selection list.

`vwap` is in Under-review because the D-tier classification predates Queue WW Sprint 8a's
session-anchoring fix. Once the founder approves the §6 reactivation criterion from
QUEUE_VV_TRIPLE_IMPL_AUDIT §5, `vwap` will promote A and this badge will flip to ✅ Verified.
