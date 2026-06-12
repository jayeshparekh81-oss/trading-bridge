# Queue EEE — State File

**Mission:** Smoke-test 137 SKIPPED indicators from Sprint 6b. Execution-quality testing only — no reference verification.

**Total indicators:** 137
**Modules present in calculations/:** 133 of 137
**Auto-FAIL (missing module):** 4

## Next Batch Pointer

**NEXT_BATCH: 5**

Sessions claim batches sequentially. Update this pointer at end of every session.

## Batch plan

6 batches × ~25 indicators (last is 12). Each batch is one commit.

| Batch | Size | First | Last | Status |
|---:|---:|---|---|---|
| 1 | 25 | `breakout_probability_score` | `trend_momentum_combo` | DONE (21P/0W/0F/3 moved/1 removed) |
| 2 | 25 | `weekly_trend_strength` | `pivot_swing` | DONE (25P/0W/0F) |
| 3 | 25 | `price_acceleration` | `linear_regression_upper` | DONE (24P/1W/0F) |
| 4 | 25 | `logarithmic_regression` | `relative_vigor_index` | DONE (21P/4W/0F) |
| 5 | 25 | `reversal_likelihood_score` | `ulcer_index` | PENDING |
| 6 | 12 | `underwater_curve` | `zscore` | PENDING |

## Indicator status table

Updated by smoke_runner after each batch run.

| # | Batch | Name | Module | Skip category note | Status |
|---:|---:|---|:-:|---|---|
| 1 | 1 | `breakout_probability_score` | ✓ | TRADETRI composite score; multi-component aggregation | SMOKE_PASS |
| 2 | 1 | `consolidation_breakout_score` | ✓ | TRADETRI composite | SMOKE_PASS |
| 3 | 1 | `consolidation_score` | ✓ | TRADETRI composite | SMOKE_PASS |
| 4 | 1 | `divergence_strength_score` | ✓ | Sums 3 divergence indicators; weighted | SMOKE_PASS |
| 5 | 1 | `exhaustion_score` | ✓ | TRADETRI composite | SMOKE_PASS |
| 6 | 1 | `mean_reversion_score` | ✓ | TRADETRI composite | SMOKE_PASS |
| 7 | 1 | `momentum_quality_score` | ✓ | TRADETRI composite | SMOKE_PASS |
| 8 | 1 | `range_expansion_score` | ✓ | TRADETRI composite | SMOKE_PASS |
| 9 | 1 | `trend_quality_score` | ✓ | TRADETRI composite | SMOKE_PASS |
| 10 | 1 | `trust_score` | ✗ | TRADETRI composite | MOVED_OUT_OF_SCOPE |
| 11 | 1 | `truth_score` | ✗ | TRADETRI composite | MOVED_OUT_OF_SCOPE |
| 12 | 1 | `regime_score` | ✗ | TRADETRI composite | REMOVED_FROM_CODEBASE |
| 13 | 1 | `rule_adherence_score` | ✗ | TRADETRI composite | MOVED_OUT_OF_SCOPE |
| 14 | 1 | `cycle_period_oscillator` | ✓ | Hilbert transform-based; complex | SMOKE_PASS |
| 15 | 1 | `klinger_volume_oscillator` | ✓ | Multi-step volume oscillator; >5 min | SMOKE_PASS |
| 16 | 1 | `volume_zone_oscillator` | ✓ | Custom volume regime oscillator | SMOKE_PASS |
| 17 | 1 | `burke_ratio` | ✓ | Risk-adjusted ratio; needs cumulative drawdown | SMOKE_PASS |
| 18 | 1 | `calmar_ratio` | ✓ | Risk-adjusted; needs MDD | SMOKE_PASS |
| 19 | 1 | `martin_ratio` | ✓ | Risk-adjusted; needs ulcer index | SMOKE_PASS |
| 20 | 1 | `omega_ratio` | ✓ | Risk-adjusted; needs partial expectations | SMOKE_PASS |
| 21 | 1 | `money_flow_ratio` | ✓ | MFI internal; combined with mfi | SMOKE_PASS |
| 22 | 1 | `variance_ratio` | ✓ | Statistical test; needs specific window | SMOKE_PASS |
| 23 | 1 | `volatility_ratio` | ✓ | Multi-window volatility; needs spec | SMOKE_PASS |
| 24 | 1 | `supertrend_v2` | ✓ | Possible v2 variant; needs spec | SMOKE_PASS |
| 25 | 1 | `trend_momentum_combo` | ✓ | Composite | SMOKE_PASS |
| 26 | 2 | `weekly_trend_strength` | ✓ | Multi-timeframe; complex grouping | SMOKE_PASS |
| 27 | 2 | `mtf_ema_alignment` | ✓ | Multi-timeframe EMA; complex | SMOKE_PASS |
| 28 | 2 | `correlation_with_volume` | ✓ | Correlation against volume; needs pairwise window | SMOKE_PASS |
| 29 | 2 | `volume_at_price_high` | ✓ | Volume profile; histogram | SMOKE_PASS |
| 30 | 2 | `volume_momentum_ratio` | ✓ | Composite | SMOKE_PASS |
| 31 | 2 | `volume_weighted_avg_close` | ✓ | VWAC variant; similar to VWAP issues | SMOKE_PASS |
| 32 | 2 | `atm_strike_distance` | ✓ | Options-specific; needs strike data | SMOKE_PASS |
| 33 | 2 | `fno_lot_size_atr` | ✓ | F&O lot size lookup; needs broker meta | SMOKE_PASS |
| 34 | 2 | `iv_proxy_atr` | ✓ | Implied volatility proxy; needs options | SMOKE_PASS |
| 35 | 2 | `gamma_proxy_acceleration` | ✓ | Options Greeks; needs Black-Scholes | SMOKE_PASS |
| 36 | 2 | `delta_proxy_directional` | ✓ | Options Greeks | SMOKE_PASS |
| 37 | 2 | `regression_channel` | ✓ | Linear regression + std bands; multi-line | SMOKE_PASS |
| 38 | 2 | `atr_trailing_stop` | ✓ | Multi-state trailing; needs flip logic | SMOKE_PASS |
| 39 | 2 | `chande_kroll_stop` | ✓ | Multi-step trailing stop | SMOKE_PASS |
| 40 | 2 | `autocorrelation` | ✓ | Lag-1 autocorrelation rolling; needs spec | SMOKE_PASS |
| 41 | 2 | `mass_index` | ✓ | EMA-of-EMA-of-range-ratios; possible | SMOKE_PASS |
| 42 | 2 | `max_drawdown_pct` | ✓ | Cumulative; needs equity curve, not OHLC | SMOKE_PASS |
| 43 | 2 | `negative_volume_index_signal` | ✓ | Composite of NVI + threshold | SMOKE_PASS |
| 44 | 2 | `positive_volume_index_signal` | ✓ | Composite of PVI + threshold | SMOKE_PASS |
| 45 | 2 | `capitulation_signal` | ✓ | Multi-condition composite | SMOKE_PASS |
| 46 | 2 | `dominant_cycle_period` | ✓ | Hilbert transform-based | SMOKE_PASS |
| 47 | 2 | `macd_divergence` | ✓ | Already in Queue UU coverage; uses divergence helper | SMOKE_PASS |
| 48 | 2 | `obv_divergence` | ✓ | Uses divergence helper; needs separate test vectors | SMOKE_PASS |
| 49 | 2 | `rsi_divergence` | ✓ | Uses divergence helper; needs separate test vectors | SMOKE_PASS |
| 50 | 2 | `pivot_swing` | ✓ | Multi-step pivot detection; >5 min | SMOKE_PASS |
| 51 | 3 | `price_acceleration` | ✓ | Second-difference; possible but skipped for time | SMOKE_PASS |
| 52 | 3 | `arnaud_legoux_ma` | ✓ | Same as alma in 6a — ERR last sprint | SMOKE_PASS |
| 53 | 3 | `ehlers_fisher` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 54 | 3 | `envelope_lower` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 55 | 3 | `envelope_upper` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 56 | 3 | `evening_star` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 57 | 3 | `exponential_regression` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 58 | 3 | `fear_greed_index` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 59 | 3 | `fibonacci_retracement` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_WARN |
| 60 | 3 | `fisher_transform` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 61 | 3 | `force_index` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 62 | 3 | `fractal_chaos_bands` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 63 | 3 | `half_life_mean_reversion` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 64 | 3 | `high_low_spread` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 65 | 3 | `higher_high_lower_low` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 66 | 3 | `historical_volatility` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 67 | 3 | `hurst_exponent` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 68 | 3 | `inside_bar_breakout` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 69 | 3 | `iv_percentile` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 70 | 3 | `iv_rank` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 71 | 3 | `kurtosis` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 72 | 3 | `linear_regression` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 73 | 3 | `linear_regression_lower` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 74 | 3 | `linear_regression_slope` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 75 | 3 | `linear_regression_upper` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 76 | 4 | `logarithmic_regression` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 77 | 4 | `mcginley_dynamic` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 78 | 4 | `median_value` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 79 | 4 | `mesa_sine_lead` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 80 | 4 | `mesa_sine_wave` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 81 | 4 | `morning_star` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 82 | 4 | `nifty_50_relative_position` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_WARN |
| 83 | 4 | `nifty_correlation` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_WARN |
| 84 | 4 | `nr7` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 85 | 4 | `nse_bse_arbitrage_proxy` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_WARN |
| 86 | 4 | `on_balance_volume_ema` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 87 | 4 | `outside_bar` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 88 | 4 | `parabolic_sar` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 89 | 4 | `parkinson_volatility` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 90 | 4 | `percentile_nearest` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 91 | 4 | `percentile_rank` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 92 | 4 | `piercing_pattern` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 93 | 4 | `polynomial_regression_2` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 94 | 4 | `polynomial_regression_3` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 95 | 4 | `price_momentum_index` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 96 | 4 | `price_velocity` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 97 | 4 | `r_squared` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 98 | 4 | `recovery_factor` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 99 | 4 | `relative_strength_vs_benchmark` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_WARN |
| 100 | 4 | `relative_vigor_index` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | SMOKE_PASS |
| 101 | 5 | `reversal_likelihood_score` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 102 | 5 | `roc_smoothed` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 103 | 5 | `round_number_attraction` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 104 | 5 | `sharpe_ratio` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 105 | 5 | `skewness` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 106 | 5 | `smma` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 107 | 5 | `sortino_ratio` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 108 | 5 | `spectral_dominant_period` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 109 | 5 | `starc_lower` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 110 | 5 | `starc_upper` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 111 | 5 | `std_dev` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 112 | 5 | `swing_failure` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 113 | 5 | `theta_proxy_decay` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 114 | 5 | `three_black_crows` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 115 | 5 | `three_white_soldiers` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 116 | 5 | `tick_index` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 117 | 5 | `trade_efficiency` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 118 | 5 | `trend_consistency_score` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 119 | 5 | `trend_continuation_score` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 120 | 5 | `true_range` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 121 | 5 | `true_strength_index` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 122 | 5 | `ttm_squeeze` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 123 | 5 | `ttm_squeeze_pro` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 124 | 5 | `twiggs_money_flow` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 125 | 5 | `ulcer_index` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 126 | 6 | `underwater_curve` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 127 | 6 | `vega_proxy_iv_sensitivity` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 128 | 6 | `vidya` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 129 | 6 | `vix_correlation` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 130 | 6 | `volatility_regime` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 131 | 6 | `vortex_negative` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 132 | 6 | `vortex_positive` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 133 | 6 | `vwma` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 134 | 6 | `wide_range_bar` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 135 | 6 | `zigzag` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 136 | 6 | `zlema` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |
| 137 | 6 | `zscore` | ✓ | TRADETRI-custom or complex; not in Sprint 6b's batch hand-ro | PENDING |

## Session log

| Session | UTC start | Batches run | Pass | Warn | Fail | Notes |
|---:|---|---|---:|---:|---:|---|
| 1 | 2026-06-12 | 1, 2, 3 | 64 | 3 | 8 | Host python3.14, no Docker. 4 missing-module FAILs + 4 empty-output FAILs (calmar/omega/iv_percentile/iv_rank); 3 all-NaN-tail WARNs. |

## Smoke battery spec

Each indicator is run against 6 synthetic regimes:

- **R1 uptrend** — positive drift, low noise, 200 bars
- **R2 downtrend** — negative drift, low noise, 200 bars
- **R3 flat** — zero drift, very low noise, 200 bars
- **R4 gappy_multi_day** — 200 bars with synthetic ±2% gaps every 50 bars
- **R5 minimal_bars** — only 10 bars (below typical 14/20/30 period)
- **R6 zero_volume** — normal price series, volume=0 throughout

Per indicator, S1–S5 checks:

- **S1** — executes without exception across R1–R4 (R5/R6 measured separately as S5)
- **S2** — output length matches input length (or scalar 1-element)
- **S3** — post-warmup (last 30%) contains ≥1 finite value, no +inf/-inf anywhere
- **S4** — deterministic: two identical runs return identical output (NaN-safe equality)
- **S5** — R5 + R6 do not crash (NaN output acceptable)

Classification:

- **SMOKE_PASS** — all S1–S5 hold
- **SMOKE_WARN** — S1–S2–S4 hold, but S3 anomalies (all-NaN tail) and/or S5 anomalies (crashed on R5 or R6)
- **SMOKE_FAIL** — S1 fails on R1–R4, or S2 fails, or output contains inf, or S4 fails (non-deterministic)

## Hard-stops (per spec)

1. Never modify production indicator code; classify SMOKE_FAIL and move on
2. Never run docker compose or touch the main repo working tree
3. If framework can't load >30% of a batch, end session with report
4. Hard cap: 3 batches per session (~75 indicators)