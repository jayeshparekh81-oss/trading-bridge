# Backtest engine — using `app.services.indicators` indicators

This guide is for callers building inside the Phase F backtest engine
(or any future hot-path consumer) that needs the 5 MVP indicators
without the HTTP-shaped `(list[Candle], Pydantic params) → dict[str, ndarray]`
boilerplate the orchestrator at
:mod:`app.services.indicator_service` is wired for.

## Quick start

```python
import numpy as np
from app.services.indicators.backtest_adapter import (
    sma, ema, rsi, macd, bollinger,
)

close = np.array([22000.0, 22010.5, 22008.2, ...], dtype=np.float64)

# Single-output indicators return one ndarray same length as close.
sma_values = sma(close, period=20)         # ndarray[float64], NaN warmup
ema_values = ema(close, period=20)
rsi_values = rsi(close, period=14)

# Multi-output indicators return NamedTuples — destructure positionally.
m_line, m_signal, m_hist = macd(close, fast=12, slow=26, signal=9)
upper, middle, lower = bollinger(close, period=20, stddev=2.0)
```

## Why a separate adapter instead of using the class API directly

The class-based API at :mod:`app.services.indicators.{sma,ema,rsi,macd,bb}`
is designed for the HTTP route (orchestrator → Pydantic params →
`list[Candle]` with `Decimal` prices → JSON response with NaN→`None`
conversion). Building that input chain per indicator call on the
backtest hot path is friction:

```python
# Without adapter (class API directly):
candles = [Candle(symbol="X", timeframe=Timeframe.FIVE_MIN,
                  timestamp=ts, open=Decimal(...), ...) for ts, c in ...]
out = SmaIndicator().compute(candles, SmaParams(length=20))["value"]

# With adapter:
out = sma(close, period=20)
```

The adapter does the Candle synthesis internally — one-shot cost
amortised across the backtest run.

## Inputs and validation

Every adapter function validates `close` at entry:

| Input | Outcome |
|---|---|
| Not 1-D | `ValueError: close must be 1-D, got shape (...)` |
| Contains `inf` | `ValueError: close contains inf — NaN is allowed but inf is not` |
| Length < indicator minimum | `ValueError: close has N bars but indicator needs at least M bars` |
| `np.nan` in input | Allowed — TA-Lib propagates NaN to output positions |
| Non-float dtype | Coerced to `np.float64` via `np.asarray` |
| Non-contiguous | Coerced via `np.ascontiguousarray` |

Minimum lengths per indicator:

| Function | Min bars (period args) |
|---|---|
| `sma(close, period)` | `period` |
| `ema(close, period)` | `period` |
| `rsi(close, period)` | `period + 1` (need one delta) |
| `macd(close, fast, slow, signal)` | `slow + signal - 1` |
| `bollinger(close, period, stddev)` | `period` |

## NaN policy

- **Warmup positions** at the start of each output array are `np.nan`.
- The first valid index for each indicator:
  - SMA: `period - 1`
  - EMA: `period - 1`
  - RSI: `period`
  - MACD `macd_line`: `slow + signal - 2` (TA-Lib aligns the macd line
    mask to the signal line first-valid index)
  - MACD `signal_line`: `slow + signal - 2`
  - MACD `histogram`: `slow + signal - 2`
  - Bollinger: `period - 1`
- **NaN in input propagates to output** at the same positions and beyond
  (TA-Lib's rolling-sum design poisons subsequent values once a NaN
  enters the accumulator; see `_deviation_analysis_part2_output.csv`
  for empirical 50-bar SMA propagation on a single NaN injection).
- The backtest engine is responsible for **skipping signal evaluation
  on NaN bars**. Pattern:

```python
for i in range(close.size):
    if np.isnan(rsi_values[i]):
        continue
    if rsi_values[i] < 30:
        emit_buy_signal(i)
```

## Pine convention notes

All adapter outputs are sourced from the existing TA-Lib-backed
classes. After the Phase F sprint (commits `63932b0` + `333b675`),
Pine-convention conformance is:

| Indicator | Pine match | Notes |
|---|---|---|
| SMA | ✓ exact | Trivial rolling mean; no smoothing convention to diverge on. |
| EMA | ✓ float64 ε | TA-Lib + Pine both seed with `SMA(close[0..N-1])` at index `N-1`. |
| RSI | ✓ float64 ε | TA-Lib + Pine both use Wilder smoothing. |
| MACD | ⚠ aligned-seeding | TA-Lib seeds fast EMA at index `slow-1` with `SMA(close[slow-fast..slow-1])`, NOT Pine docs' independent SMA seeding. Industry standard (pandas-ta-classic `ta.macd` default agrees). Empirical TradingView UI check pending — see `PHASE_F_OVERRIDE_LOG.md`. |
| Bollinger | ✓ float64 ε | Biased (population) stddev, matches Pine `ta.bb` default after the Phase F BB fix. |

## Performance characteristics

- Each adapter call: 1 µs to 30 ms depending on `len(close)` (dominated
  by the per-bar Candle synthesis at ~3 µs/bar). For 10K-bar backtest
  precomputation: ~30 ms one-shot.
- TA-Lib's C kernel itself runs in microseconds. The bottleneck is the
  Decimal/Pydantic Candle construction, not the math.
- **Pattern: precompute once per backtest run, then iterate**. Avoid
  calling an adapter function inside the per-bar loop — that re-pays
  the synthesis cost on every iteration.

```python
# Good — one-shot precompute, fast iteration
rsi_values = rsi(close, period=14)
for i in range(close.size):
    if not np.isnan(rsi_values[i]) and rsi_values[i] < 30:
        ...

# Bad — synthesises Candle list 10K times
for i in range(close.size):
    r = rsi(close[:i+1], period=14)  # quadratic!
    ...
```

## Result types

```python
from app.services.indicators._types import MACDResult, BollingerResult

m = macd(close)
m.macd       # ndarray
m.signal     # ndarray
m.histogram  # ndarray
# Also destructurable: macd_line, signal_line, hist = m

b = bollinger(close)
b.upper, b.middle, b.lower  # also destructurable
```

Both `MACDResult` and `BollingerResult` are `typing.NamedTuple`. All
fields are `np.ndarray` aligned positionally to the input `close`.

## Cross-validation

The new test file
`backend/tests/services/indicators/test_indicators_phase_f_reference.py`
validates each indicator's output against pandas-ta-classic-derived
Pine reference fixtures with tolerance `atol=0.01, rtol=1e-7`. The
fixtures live at:

```
backend/tests/services/indicators/fixtures/
├── nifty_100_bars_5m.csv             # deterministic OHLCV input
├── rsi_14_pine_expected.csv
├── sma_20_pine_expected.csv
├── ema_20_pine_expected.csv
├── macd_12_26_9_pine_expected.csv    # (xfail pending TV verification)
└── bollinger_20_2_pine_expected.csv
```

Regenerate with:

```bash
python3 backend/tests/services/indicators/fixtures/_generate_phase_f_fixtures.py
```

(Requires `pandas-ta-classic` in dev env; cross-verifies against
hand-rolled Pine references too.)

## Source pointer

- Adapter:  `backtest_adapter.py` (this directory)
- Types:    `_types.py` (this directory)
- Tests:    `backend/tests/services/indicators/test_indicators_phase_f_reference.py`
- Audit trail: `PHASE_F_COMPONENT_1_AUDIT.md` + Part 1 + Part 2
  deviation analysis docs at repo root.
