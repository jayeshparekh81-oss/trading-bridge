"""Performance analytics + equity plot for the backtest harness."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless — save PNGs, no display
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from config import Config  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "data"


def _max_drawdown(equity: pd.Series) -> tuple[float, float]:
    running_max = equity.cummax()
    dd = equity - running_max
    dd_pct = (dd / running_max).replace([np.inf, -np.inf], np.nan)
    return float(dd.min()), float(dd_pct.min() * 100.0)


def _streaks(net: pd.Series) -> tuple[int, int]:
    win = loss = cur_w = cur_l = 0
    for v in net:
        if v > 0:
            cur_w += 1; cur_l = 0
        elif v < 0:
            cur_l += 1; cur_w = 0
        else:
            cur_w = cur_l = 0
        win = max(win, cur_w); loss = max(loss, cur_l)
    return win, loss


def _sharpe_sortino(equity: pd.Series, config: Config) -> tuple[float, float]:
    # Per-BAR (5-min) returns on the equity curve, including flat (zero-return)
    # bars. Annualization factor = sqrt(bars_per_day * trading_days_per_year)
    #   = sqrt(75 * 252) = sqrt(18900) ≈ 137.48 for 5-min bars.
    ann = np.sqrt(config.bars_per_day * config.trading_days_per_year)
    ret = equity.pct_change().dropna()
    if ret.std(ddof=1) == 0 or len(ret) < 2:
        sharpe = 0.0
    else:
        sharpe = ret.mean() / ret.std(ddof=1) * ann
    downside = ret[ret < 0]
    if len(downside) < 2 or downside.std(ddof=1) == 0:
        sortino = 0.0
    else:
        sortino = ret.mean() / downside.std(ddof=1) * ann
    return float(sharpe), float(sortino)


def summarize(symbol: str, variant: str, trades: pd.DataFrame, equity: pd.Series,
              config: Config, out_dir: Path | None = None) -> dict:
    out_dir = out_dir or OUT_DIR
    tag = f"{symbol} · {variant}"
    print(f"\n{'═' * 66}\n  {tag}\n{'═' * 66}")

    if trades.empty:
        print("  NO TRADES generated.")
        _plot(symbol, variant, equity, config, out_dir)
        return {"symbol": symbol, "variant": variant, "trades": 0}

    net = trades["net_pnl"]
    wins = net[net > 0]
    losses = net[net < 0]
    gross_win = float(wins.sum())
    gross_loss = float(losses.sum())  # negative
    profit_factor = (gross_win / abs(gross_loss)) if gross_loss != 0 else float("inf")
    net_profit = float(net.sum())
    max_dd_inr, max_dd_pct = _max_drawdown(equity)
    sharpe, sortino = _sharpe_sortino(equity, config)
    win_streak, loss_streak = _streaks(net)

    def inr(x: float) -> str:
        return f"₹{x:,.0f}"

    rows = [
        ("net profit", inr(net_profit)),
        ("return on capital", f"{net_profit / config.capital * 100:.2f}%"),
        ("total trades", f"{len(trades)}"),
        ("win rate", f"{len(wins) / len(trades) * 100:.1f}%"),
        ("profit factor", f"{profit_factor:.2f}"),
        ("expectancy / trade", inr(float(net.mean()))),
        ("avg win", inr(float(wins.mean())) if len(wins) else "—"),
        ("avg loss", inr(float(losses.mean())) if len(losses) else "—"),
        ("max drawdown", f"{inr(max_dd_inr)}  ({max_dd_pct:.2f}%)"),
        ("Sharpe (5-min, annualized)", f"{sharpe:.2f}"),
        ("Sortino (5-min, annualized)", f"{sortino:.2f}"),
        ("longest win streak", f"{win_streak}"),
        ("longest loss streak", f"{loss_streak}"),
        ("total costs paid", inr(float(trades['cost'].sum()))),
    ]
    w = max(len(k) for k, _ in rows)
    for k, v in rows:
        print(f"  {k:<{w}} : {v}")

    # Monthly net PnL (by exit month).
    monthly = (
        trades.assign(month=pd.to_datetime(trades["exit_time"]).dt.strftime("%Y-%m"))
        .groupby("month")["net_pnl"].sum()
    )
    print("  monthly net PnL:")
    for m, v in monthly.items():
        print(f"    {m} : {inr(float(v))}")

    _plot(symbol, variant, equity, config, out_dir)
    return {
        "symbol": symbol, "variant": variant, "trades": len(trades),
        "net_profit": net_profit, "profit_factor": profit_factor,
        "win_rate": len(wins) / len(trades), "sharpe": sharpe, "sortino": sortino,
        "max_dd_pct": max_dd_pct,
    }


def _plot(symbol: str, variant: str, equity: pd.Series, config: Config, out_dir: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})
    ax1.plot(equity.index, equity.values, lw=1.0, color="#1f77b4")
    ax1.axhline(config.capital, color="grey", ls="--", lw=0.8)
    ax1.set_title(f"{symbol} · {variant} — equity (5-min, intraday, {len(equity):,} bars)")
    ax1.set_ylabel("equity (INR)")
    ax1.grid(alpha=0.3)

    dd = equity - equity.cummax()
    ax2.fill_between(equity.index, dd.values, 0, color="#d62728", alpha=0.4)
    ax2.set_ylabel("drawdown")
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    path = out_dir / f"equity_{symbol}_{variant}.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"  saved plot: {path}")
