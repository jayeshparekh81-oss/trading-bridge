"""Backtest harness (Module 0).

run_backtest(df, signal_fn, cost_model, slippage_model, config, symbol)
    -> (trades_df, equity_series)

signal_fn(df) returns the DESIRED position in {-1, 0, +1} formed at each bar's
CLOSE, using data up to and including that bar.

╔══════════════════════════════════════════════════════════════════════════╗
║ NO LOOK-AHEAD CONTRACT                                                     ║
║ The position decided from data up to bar t (signal_fn value at index t) is ║
║ executed at bar t+1's OPEN — never at bar t. In the loop below, at bar i   ║
║ we act only on desired[i-1]. signal_fn never sees future bars, and the     ║
║ fill uses the *next* bar's open, so no information from bar i's close (or   ║
║ later) can influence the trade entered at bar i.                           ║
╚══════════════════════════════════════════════════════════════════════════╝

Session-aware + intraday only: no overnight carry (each new day starts flat),
and every position is squared off at config.square_off_time. Session state
(e.g. VWAP) is the signal_fn's concern — the baseline resets it daily.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import Config
from costs import CostModel, SlippageModel


def run_backtest(
    df: pd.DataFrame,
    signal_fn,
    cost_model: CostModel,
    slippage_model: SlippageModel,
    config: Config,
    symbol: str,
) -> tuple[pd.DataFrame, pd.Series]:
    desired = np.asarray(signal_fn(df), dtype=int)  # decision at each bar's close
    o = df["open"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    idx = df.index
    dates = idx.date
    times = idx.time
    n = len(df)

    qty = config.instruments[symbol].lot_size * config.lots
    square_off = config.square_off_time

    pos = 0
    entry_fill = 0.0
    entry_dir = 0
    entry_time = None
    entry_i = 0
    realized = 0.0
    equity = np.empty(n)
    trades: list[dict] = []

    def _close(exit_price_open: float, exit_time, exit_i: int) -> None:
        nonlocal pos, realized
        exit_fill = slippage_model.adjust(exit_price_open, side=-pos)  # closing fill
        if entry_dir == 1:
            buy_val, sell_val = entry_fill * qty, exit_fill * qty
        else:
            sell_val, buy_val = entry_fill * qty, exit_fill * qty
        gross = (exit_fill - entry_fill) * pos * qty
        cost = cost_model.round_trip(buy_val, sell_val)
        net = gross - cost
        realized += net
        trades.append(
            {
                "entry_time": entry_time,
                "exit_time": exit_time,
                "direction": "long" if entry_dir == 1 else "short",
                "entry_price": round(entry_fill, 2),
                "exit_price": round(exit_fill, 2),
                "qty": qty,
                "bars_held": exit_i - entry_i,
                "gross_pnl": gross,
                "cost": cost,
                "net_pnl": net,
            }
        )
        pos = 0

    for i in range(n):
        # ── NO LOOK-AHEAD: execute the PREVIOUS bar's decision at THIS bar's open.
        if i == 0 or dates[i] != dates[i - 1]:
            target = 0                    # new session → start flat (no overnight carry)
        else:
            target = desired[i - 1]
        if times[i] >= square_off:
            target = 0                    # square-off / stay flat into the close

        op = o[i]
        if target != pos:
            if pos != 0:
                _close(op, idx[i], i)
            if target != 0:
                entry_fill = slippage_model.adjust(op, side=target)
                pos = target
                entry_dir = target
                entry_time = idx[i]
                entry_i = i

        # bar-level equity, marked to this bar's close
        unreal = (c[i] - entry_fill) * pos * qty if pos != 0 else 0.0
        equity[i] = config.capital + realized + unreal

    # Safety: close anything still open at the final bar (square-off should
    # prevent this, but never leave a dangling position).
    if pos != 0:
        _close(c[n - 1], idx[n - 1], n - 1)
        equity[n - 1] = config.capital + realized

    trades_df = pd.DataFrame(trades)
    equity_series = pd.Series(equity, index=idx, name="equity")
    return trades_df, equity_series
