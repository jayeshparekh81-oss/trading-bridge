"""Verify the strategy_engine.backtest.indicator_runner pipeline now passes
timestamps to vwap() and produces session-anchored output.

This is an integration check against the full
``precompute_indicators(candles, strategy)`` path that the simulator hot
loop uses. The 3-session synthetic exercises the new session-reset code
path that the old indicator_runner couldn't reach.

Run:
    cd backend && python3 -m tests.queue_ww_sprint_8.framework_extensions.vwap_backtest_verification
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON

_IST = ZoneInfo("Asia/Kolkata")


def _build_candles(sessions: int = 3, bars_per_session: int = 75) -> list[Candle]:
    rng = random.Random(42)
    out: list[Candle] = []
    price = 21500.0
    for s in range(sessions):
        session_start = datetime(2026, 6, 1 + s, 9, 15, tzinfo=_IST)
        for i in range(bars_per_session):
            ts = session_start + timedelta(minutes=5 * i)
            close = price + rng.gauss(0, 8)
            high = max(price, close) + abs(rng.gauss(0, 4))
            low = min(price, close) - abs(rng.gauss(0, 4))
            open_ = price
            volume = float(rng.randint(1000, 50000))
            out.append(
                Candle(
                    timestamp=ts,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
            price = close
    return out


def _minimal_vwap_strategy() -> StrategyJSON:
    return StrategyJSON.model_validate(
        {
            "id": "queue-ww-vwap-verification",
            "name": "Queue WW VWAP verification",
            "mode": "expert",
            "indicators": [{"id": "vwap_default", "type": "vwap", "params": {}}],
            "entry": {
                "side": "BUY",
                "operator": "AND",
                "conditions": [{"type": "price", "op": ">", "value": 0.0}],
            },
            "exit": {"targetPercent": 2, "stopLossPercent": 1},
            "risk": {},
            "execution": {
                "mode": "backtest",
                "orderType": "MARKET",
                "productType": "INTRADAY",
            },
        }
    )


def main() -> int:
    print("=== VWAP backtest-pipeline verification ===\n")
    candles = _build_candles(sessions=3, bars_per_session=75)
    strategy = _minimal_vwap_strategy()
    series, _warnings = precompute_indicators(candles, strategy)

    vwap_out = series["vwap_default"]
    n = len(candles)

    print(f"input candles      : {n} (3 sessions × 75 bars)")
    print(f"vwap output length : {len(vwap_out)}")
    print(f"non-None count     : {sum(1 for x in vwap_out if x is not None)}")
    assert len(vwap_out) == n, "output length must equal input"
    assert all(x is not None for x in vwap_out), "all bars should have defined vwap"

    session2_first_bar = vwap_out[75]
    session2_typical = (candles[75].high + candles[75].low + candles[75].close) / 3
    session_anchored = abs(session2_first_bar - session2_typical) < 1e-9
    print(f"session 2 first bar: {session2_first_bar:.4f}")
    print(f"session 2 typical  : {session2_typical:.4f}")
    print(f"session reset proof: {'YES' if session_anchored else 'NO'}")

    session1_finite = sum(1 for x in vwap_out[:75] if x is not None)
    session2_finite = sum(1 for x in vwap_out[75:150] if x is not None)
    session3_finite = sum(1 for x in vwap_out[150:] if x is not None)
    print(f"\nper-session finite: s1={session1_finite}, s2={session2_finite}, s3={session3_finite}")
    print(f"trade-fireable count (close > vwap): {sum(1 for i in range(n) if candles[i].close > vwap_out[i])}")

    ok = session_anchored and all(x is not None for x in vwap_out)
    print(f"\nVERDICT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
