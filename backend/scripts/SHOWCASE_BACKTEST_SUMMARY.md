# TRADETRI — Backtest Showcase Summary (HONEST, size-independent)

_Generated 2026-06-21 from the isolated backtest store (`backend/backtest_signal_history.sqlite3`, table `backtest_trades`). Strategy version **v4.8.1**, source `tv_trade_list`._

> **These are IN-SAMPLE backtests, not a guarantee of future results.** All figures are size-independent per-trade metrics. TradingView's compounded cumulative (a %-of-equity-compounding + oversized-position artifact) is **deliberately excluded everywhere** — it is fantasy and never surfaced.

## Consolidated metrics

| Metric | BSE | CDSL | ANGELONE |
|---|---|---|---|
| Instrument | NSE:BSE fut | NSE:CDSL fut | NSE:ANGELONE fut |
| Deployment context | live-real* | live-real* | **PAPER** |
| Date range (in-sample) | 2019-12→2026-06 | 2019-12→2026-06 | 2020-10→2026-06 |
| Closed trades | 1,149 | 1,031 | 942 |
| Open/unrealized (excluded) | 0 | 1 | 0 |
| Wins / Losses / Flat | 890/254/5 | 730/299/2 | 689/249/4 |
| Win rate | 77.46% | 70.81% | 73.14% |
| Avg per-trade (gross) | +1.622% | +1.133% | +1.415% |
| Median per-trade (gross) | +1.470% | +1.030% | +1.520% |
| Best / worst trade | +16.61% / -8.03% | +14.79% / -5.76% | +22.59% / -10.91% |
| Profit factor (Σwin% / |Σloss%|) | 5.80 | 3.91 | 3.82 |
| Longest losing streak | 6 trades | 13 trades | 7 trades |
| Max drawdown (non-compounded†) | 5.24% | 5.21% | 9.89% |
| Avg est. cost / round-trip | +0.030% | +0.030% | +0.030% |
| Avg per-trade (NET of est. cost) | +1.592% | +1.103% | +1.386% |

\* **live-real**: BSE/CDSL are deployed live-real-money strategies; their *live track record* is a SEPARATE artifact (read-only from the live system) and is NOT shown here. This table is their **backtest** only. ANGELONE has **no** live deployment — paper/backtest only.

† **Max drawdown basis (stated):** NON-compounded, **constant notional** per trade — per-trade % returns are *added* (not compounded) onto an equity normalized to 1.0. This is NOT %-of-equity compounding. It deliberately avoids the oversized-position artifact.

‡ **Cost basis:** the existing Indian F&O cost model (`pnl_reconciler/costs.py`, **NFO** segment) at a fixed notional ₹1,500,000/round-trip, 2 orders. Costs are **ESTIMATED** (published-rate model, not broker contract-note) — STT-dominated, ~0.03%/round-trip.

## Mandatory caveats (read before trusting any number)

- **In-sample.** These are each strategy's own historical signals — no out-of-sample / walk-forward validation. Curve-fit / over-optimization risk applies.
- **Charges only — NOT slippage.** The cost model covers exchange/tax/brokerage charges. Real **slippage/market-impact** on a ₹15L single-stock-futures order is typically *larger* than the charges and would reduce the net edge. TradingView fills at the exact signal price.
- **No walk-forward / no regime split.** Performance is not segmented by market regime; a single blended edge can hide regime-dependent behaviour.
- **TV 'Net PnL %' treated as gross** of real charges (assumes the Pine backtest ran commission/slippage ≈ 0, standard for signal research).
- **ANGELONE is PAPER.** No live real-money track record exists for it. It must be labelled **PAPER / backtest-only** anywhere it is shown — never implied as live or verified.
- **Backtest ≠ live.** A backtest is a hypothesis about edge, not a track record. BSE/CDSL live results are a separate, read-only artifact and are not represented in this table.
- **Compounded totals are forbidden.** The TradingView compounded cumulative (BSE 109,001%, CDSL 3,470%, ANGELONE 16,242%) is an un-executable artifact and is never computed or shown.

