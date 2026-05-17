# Template Activation Audit

**Date:** 2026-05-18  
**Active equity templates audited:** 45  
**Runtime-safe:** 29  
**Unsafe (recommend deactivation):** 16

## Per-template status

| Slug | Status | Indicators (per-status) |
|---|---|---|
| `ema-crossover-9-21` | RUNTIME_SAFE | `ema_9`=RUNTIME_SAFE, `ema_21`=RUNTIME_SAFE |
| `ema-crossover-20-50` | RUNTIME_SAFE | `ema_20`=RUNTIME_SAFE, `ema_50`=RUNTIME_SAFE |
| `macd-trend-signal` | RUNTIME_SAFE | `macd_12_26_9`=RUNTIME_SAFE |
| `supertrend-rider` | RUNTIME_SAFE | `supertrend_10_3`=RUNTIME_SAFE |
| `rsi-oversold-bounce` | RUNTIME_SAFE | `rsi_14`=RUNTIME_SAFE |
| `bb-mean-reversion` | RUNTIME_SAFE | `bb_20_2`=RUNTIME_SAFE |
| `bb-squeeze-breakout` | RUNTIME_SAFE | `bb_20_2`=RUNTIME_SAFE, `atr_14`=RUNTIME_SAFE |
| `orb-15min` | RUNTIME_SAFE | `orb_15`=RUNTIME_SAFE |
| `pdh-pdl-breakout` | NOT_REGISTERED | `pdh`=NOT_REGISTERED, `pdl`=NOT_REGISTERED |
| `vwap-bounce` | RUNTIME_SAFE | `vwap`=RUNTIME_SAFE |
| `macd-histogram-momentum` | RUNTIME_SAFE | `macd_12_26_9`=RUNTIME_SAFE |
| `banknifty-weekly-equity` | NOT_REGISTERED | `banknifty_pdh`=NOT_REGISTERED, `india_vix`=NOT_REGISTERED |
| `premarket-gap` | NOT_REGISTERED | `pre_market_gap_pct`=NOT_REGISTERED |
| `rsi-macd-confluence` | RUNTIME_SAFE | `rsi_14`=RUNTIME_SAFE, `macd_12_26_9`=RUNTIME_SAFE |
| `bb-rsi-oversold` | RUNTIME_SAFE | `bb_20_2`=RUNTIME_SAFE, `rsi_14`=RUNTIME_SAFE |
| `heikin-ashi-trend` | NOT_ACTIVE (coming_soon) | `heikin_ashi`=NOT_ACTIVE (coming_soon), `ema_20`=RUNTIME_SAFE |
| `donchian-channel-breakout` | RUNTIME_SAFE | `donchian_channel_20`=RUNTIME_SAFE, `donchian_channel_10`=RUNTIME_SAFE, `adx_14`=RUNTIME_SAFE |
| `keltner-channel-bounce` | NOT_REGISTERED | `keltner_channel_20_2_atr14`=NOT_REGISTERED, `ema_50`=RUNTIME_SAFE |
| `parabolic-sar-reversal` | NOT_REGISTERED | `parabolic_sar_0.02_0.2`=NOT_REGISTERED, `ema_50`=RUNTIME_SAFE |
| `ichimoku-cloud-crossover` | RUNTIME_SAFE | `ichimoku_9_26_52`=RUNTIME_SAFE |
| `adx-strong-trend-filter` | RUNTIME_SAFE | `adx_14`=RUNTIME_SAFE, `ema_9`=RUNTIME_SAFE, `ema_21`=RUNTIME_SAFE |
| `triple-ema-crossover` | RUNTIME_SAFE | `ema_8`=RUNTIME_SAFE, `ema_21`=RUNTIME_SAFE, `ema_55`=RUNTIME_SAFE |
| `williams-pct-r-reversal` | RUNTIME_SAFE | `williams_r_14`=RUNTIME_SAFE, `ema_50`=RUNTIME_SAFE |
| `cci-momentum` | RUNTIME_SAFE | `cci_20`=RUNTIME_SAFE, `ema_50`=RUNTIME_SAFE |
| `stochastic-oscillator` | NOT_REGISTERED | `stochastic_slow_14_3_3`=NOT_REGISTERED, `ema_50`=RUNTIME_SAFE |
| `aroon-crossover` | RUNTIME_SAFE | `aroon_up_14`=RUNTIME_SAFE, `aroon_down_14`=RUNTIME_SAFE |
| `psar-ema-combo` | NOT_REGISTERED | `parabolic_sar_0.02_0.2`=NOT_REGISTERED, `ema_50`=RUNTIME_SAFE |
| `pivot-point-bounce` | NOT_REGISTERED | `pivot_points_standard`=NOT_REGISTERED, `rsi_14`=RUNTIME_SAFE |
| `camarilla-pivots-intraday` | RUNTIME_SAFE | `camarilla_pivots`=RUNTIME_SAFE, `vwap`=RUNTIME_SAFE |
| `fibonacci-retracement-entry` | NOT_REGISTERED | `fib_retracement_swing`=NOT_REGISTERED, `ema_50`=RUNTIME_SAFE, `rsi_14`=RUNTIME_SAFE |
| `range-trading-sr` | NOT_REGISTERED | `auto_support_resistance_20`=NOT_REGISTERED, `adx_14`=RUNTIME_SAFE, `rsi_14`=RUNTIME_SAFE |
| `inside-bar-breakout` | RUNTIME_SAFE | `ema_20`=RUNTIME_SAFE |
| `engulfing-candle-reversal` | RUNTIME_SAFE | `ema_50`=RUNTIME_SAFE, `rsi_14`=RUNTIME_SAFE |
| `hammer-hanging-man-pattern` | NOT_REGISTERED | `auto_support_resistance_20`=NOT_REGISTERED, `rsi_14`=RUNTIME_SAFE |
| `doji-reversal` | RUNTIME_SAFE | `ema_50`=RUNTIME_SAFE, `rsi_14`=RUNTIME_SAFE |
| `chandelier-exit-trail` | NOT_REGISTERED | `chandelier_22_3.0`=NOT_REGISTERED, `ema_50`=RUNTIME_SAFE |
| `volume-spike-price-confirm` | NOT_REGISTERED | `volume`=NOT_REGISTERED, `volume_sma_20`=RUNTIME_SAFE, `ema_20`=RUNTIME_SAFE |
| `obv-divergence` | RUNTIME_SAFE | `obv`=RUNTIME_SAFE, `ema_50`=RUNTIME_SAFE |
| `cmf-confirmation` | RUNTIME_SAFE | `cmf_20`=RUNTIME_SAFE, `ema_20`=RUNTIME_SAFE, `ema_50`=RUNTIME_SAFE |
| `mfi-overbought-oversold` | RUNTIME_SAFE | `mfi_14`=RUNTIME_SAFE, `ema_50`=RUNTIME_SAFE |
| `rsi-divergence` | RUNTIME_SAFE | `rsi_14`=RUNTIME_SAFE |
| `macd-divergence` | RUNTIME_SAFE | `macd_12_26_9`=RUNTIME_SAFE |
| `bollinger-pct-b-extreme` | NOT_REGISTERED | `bollinger_bands_20_2`=RUNTIME_SAFE, `bollinger_pct_b_20_2`=NOT_REGISTERED, `rsi_14`=RUNTIME_SAFE |
| `squeeze-momentum` | NOT_REGISTERED | `bollinger_bands_20_2`=RUNTIME_SAFE, `keltner_channel_20_1.5_atr14`=NOT_REGISTERED, `momentum_12`=NOT_ACTIVE (coming_soon) |
| `hull-ma-trend` | RUNTIME_SAFE | `hull_ma_21`=RUNTIME_SAFE |

## Unsafe templates (recommend `is_active=False`)

- `pdh-pdl-breakout`
- `banknifty-weekly-equity`
- `premarket-gap`
- `heikin-ashi-trend`
- `keltner-channel-bounce`
- `parabolic-sar-reversal`
- `stochastic-oscillator`
- `psar-ema-combo`
- `pivot-point-bounce`
- `fibonacci-retracement-entry`
- `range-trading-sr`
- `hammer-hanging-man-pattern`
- `chandelier-exit-trail`
- `volume-spike-price-confirm`
- `bollinger-pct-b-extreme`
- `squeeze-momentum`