#!/usr/bin/env python3
"""ADVERSARIAL AUDIT — read-only. No configs re-run, no parameters touched."""
import sys
from pathlib import Path
import numpy as np, pandas as pd

TRACK = Path("/Users/jayeshparekh/projects/trading-bridge/canslim_swing")
sys.path.insert(0, str(TRACK / "scripts"))
import module2_backtest as M2

SLIP, START = M2.SLIP, M2.START_EQUITY
P = pd.read_parquet(TRACK / "data" / "panel_v2" / "module1_panel.parquet")
P["date"] = pd.to_datetime(P["date"])
OPEN = P.pivot(index="date", columns="symbol", values="open").sort_index()
CLOSE = P.pivot(index="date", columns="symbol", values="close").sort_index()
CMARK = CLOSE.ffill()
T = pd.read_parquet(TRACK / "data" / "m2" / "module2_trades_A.parquet")
EQ = pd.read_parquet(TRACK / "data" / "m2" / "module2_equity_A.parquet")["equity"]
dates = EQ.index

print("#" * 78); print("SECTION A — LOOK-AHEAD"); print("#" * 78)
# A6: does per-symbol indicator computation leak across the pivot?
sub = P[P.symbol == "RELIANCE"].sort_values("date")
c = sub["close"].to_numpy()
manual_hh = pd.Series(c).shift(1).rolling(252).max().to_numpy()
print(f"A1/A6 hh252_excl recomputed for RELIANCE == stored: "
      f"{np.allclose(manual_hh, sub['hh252_excl'].to_numpy(), equal_nan=True)}")
i = 400
print(f"   spot: date {sub['date'].iloc[i].date()} close {c[i]:.2f} "
      f"hh252_excl {sub['hh252_excl'].iloc[i]:.2f} "
      f"max(close[{i-252}:{i}]) {c[i-252:i].max():.2f}  "
      f"includes-today? {c[i] > c[i-252:i].max() and sub['BRK'].iloc[i]}")
manual_ll = pd.Series(sub["low"].to_numpy()).rolling(252).min().to_numpy()
print(f"A2 ll252 recomputed == stored (INCLUSIVE of today): "
      f"{np.allclose(manual_ll, sub['ll252'].to_numpy(), equal_nan=True)}")
manual_f5 = (pd.Series((sub['low'] < sub['ema220']).to_numpy()).rolling(90).sum() > 0).to_numpy()
print(f"A2 f5 recomputed (90-session window INCLUDING today) == stored: "
      f"{np.array_equal(manual_f5, sub['F5'].to_numpy())}")
manual_r = pd.Series(c) / pd.Series(c).shift(126) - 1
print(f"A2 ret126 recomputed == stored: {np.allclose(manual_r, sub['ret126'], equal_nan=True)}")

# A3/A4/A5: entry/exit price sourcing, reconstructed from the ledger
o_impl = T["entry_px"] / (1 + SLIP)
chk = [OPEN.at[r.entry_date, r.symbol] for r in T.itertuples()]
print(f"A3 entry fill == OPEN of entry_date * (1+slip) for all {len(T)} trades: "
      f"{np.allclose(o_impl.to_numpy(), np.array(chk))}")
cl = T[~T["open_at_end"]]
x_impl = cl["exit_px"] / (1 - SLIP)
chk2 = [OPEN.at[r.exit_date, r.symbol] for r in cl.itertuples()]
print(f"A4 exit fill == OPEN of exit_date * (1-slip) for all {len(cl)} closed: "
      f"{np.allclose(x_impl.to_numpy(), np.array(chk2))}")
# entry date must be strictly after a signal date
sig = P[P.signal][["date", "symbol"]]
sigset = set(zip(sig["date"], sig["symbol"]))
prev = {d: dates[k-1] for k, d in enumerate(dates) if k > 0}
ok = all((prev[r.entry_date], r.symbol) in sigset for r in T.itertuples())
print(f"A3 every entry_date is the session immediately AFTER a signal day: {ok}")
same = any((r.entry_date, r.symbol) in sigset and (prev[r.entry_date], r.symbol) not in sigset
           for r in T.itertuples())
print(f"A3 any entry priced on its own signal day (same-day fill)? {same}")

print()
print("#" * 78); print("SECTION B — DRAWDOWN"); print("#" * 78)
peak = EQ.cummax(); dd = EQ / peak - 1
trough = dd.idxmin(); pk = EQ.loc[:trough].idxmax()
print(f"B7 equity series = cash + MTM of OPEN positions (module2_backtest.py:139)")
print(f"B8 peak {pk.date()} Rs {EQ.loc[pk]:,.0f}   trough {trough.date()} Rs {EQ.loc[trough]:,.0f}"
      f"   dd {100*dd.min():.2f}%")
real_pk = T.loc[(~T.open_at_end) & (T.exit_date <= pk), "pnl"].sum()
real_tr = T.loc[(~T.open_at_end) & (T.exit_date <= trough), "pnl"].sum()
d_real = real_tr - real_pk
d_tot = EQ.loc[trough] - EQ.loc[pk]
print(f"B8 peak-to-trough change Rs {d_tot:,.0f}")
print(f"      realised P&L booked in that stretch : Rs {d_real:,.0f}  ({100*d_real/d_tot:.1f}%)")
print(f"      unrealised MTM on open positions    : Rs {d_tot-d_real:,.0f}  ({100*(d_tot-d_real)/d_tot:.1f}%)")
nclosed = int(((~T.open_at_end) & (T.exit_date > pk) & (T.exit_date <= trough)).sum())
print(f"      trades closed between peak and trough: {nclosed}")
nif = pd.read_parquet(TRACK / "data" / "panel_v2" / "nifty_daily.parquet")
nif.index = pd.DatetimeIndex(pd.to_datetime(nif.index)).normalize()
nif = nif.loc[(nif.index >= dates[0]) & (nif.index <= dates[-1]), "close"]
ndd = nif / nif.cummax() - 1
UNI = [l.strip() for l in (TRACK/"config"/"universe_frozen.txt").read_text().splitlines() if l.strip()]
first = CLOSE[UNI].apply(lambda s: s.first_valid_index())
shares = pd.Series({s: (START/len(UNI)) / CLOSE[s].loc[first[s]] for s in UNI})
val = CMARK[UNI].mul(shares, axis=1).where(~CMARK[UNI].isna(), START/len(UNI))
ew = val.sum(axis=1); ewdd = ew / ew.cummax() - 1
print(f"B9 on the trough date {trough.date()}:")
print(f"      config A drawdown : {100*dd.loc[trough]:.2f}%")
print(f"      NIFTY drawdown    : {100*ndd.loc[trough]:.2f}%")
print(f"      EW universe dd    : {100*ewdd.loc[trough]:.2f}%")
print(f"      NIFTY worst of run: {100*ndd.min():.2f}% on {ndd.idxmin().date()}")

print()
print("#" * 78); print("SECTION C — ACCOUNTING"); print("#" * 78)
# C11 independent reconstruction of cash + MV
held_end = T[T.open_at_end]
recon = np.empty(len(dates)); maxdiff = 0.0
ent = T.groupby("entry_date")["cost_in"].sum()
exi = T[~T.open_at_end].groupby("exit_date")["proceeds"].sum()
cash = START - ent.reindex(dates, fill_value=0).cumsum() + exi.reindex(dates, fill_value=0).cumsum()
for k, d in enumerate(dates):
    hold = T[(T.entry_date <= d) & ((T.exit_date > d) | (T.open_at_end & (T.exit_date >= d)))]
    mv = float((hold["shares"].to_numpy() *
                np.array([CMARK.at[d, s] for s in hold["symbol"]])).sum()) if len(hold) else 0.0
    recon[k] = cash.iloc[k] + mv
R = pd.Series(recon, index=dates)
diff = (R - EQ).abs()
print(f"C11 independent cash+MV vs stored equity: max abs discrepancy Rs {diff.max():.6f}"
      f"  (on {diff.idxmax().date()})")
# C12
mtm_open = float((held_end["shares"] * [CMARK.at[dates[-1], s] for s in held_end["symbol"]]).sum())
lhs = T.loc[~T.open_at_end, "pnl"].sum() + (mtm_open - held_end["cost_in"].sum())
print(f"C12 sum(closed pnl) + open MTM-vs-cost = Rs {lhs:,.2f}")
print(f"    final equity - start                = Rs {EQ.iloc[-1]-START:,.2f}")
print(f"    residual                            = Rs {lhs-(EQ.iloc[-1]-START):,.2f}")
print("    (open positions are marked at CLOSE with no exit costs deducted in equity;")
print("     the ledger's open_at_end rows DO deduct a hypothetical sell cost)")
oa = held_end
print(f"    hypothetical sell costs booked on the {len(oa)} open rows: "
      f"Rs {(oa['shares']*oa['exit_px']*0 + (oa['shares']*oa['exit_px'] - oa['proceeds'])).sum():,.2f}")
# C13 recompute costs independently
bc = T["notional"].apply(M2.buy_costs)
print(f"C13 buy costs recomputed == cost_in - notional: "
      f"{np.allclose(bc, T['cost_in']-T['notional'])}")
sc = (T["shares"]*T["exit_px"]).apply(M2.sell_costs)
print(f"    sell costs recomputed == shares*exit_px - proceeds: "
      f"{np.allclose(sc, T['shares']*T['exit_px'] - T['proceeds'])}")
print(f"    trades with zero buy cost: {int((T['cost_in']-T['notional']<=0).sum())}   "
      f"zero sell cost: {int(((T['shares']*T['exit_px']-T['proceeds'])<=0).sum())}")
# C14 slippage direction
print(f"C14 buy: entry_px > raw open on all trades: "
      f"{bool((T['entry_px'] > o_impl).all())}   "
      f"sell: exit_px < raw open on all closed: {bool((cl['exit_px'] < x_impl).all())}")
# C15 rounding / cap
eqprev = EQ.shift(1)
cap = []
for r in T.itertuples():
    e = eqprev.get(r.entry_date, np.nan)
    cap.append(100*r.notional/e if e==e else np.nan)
T2 = T.assign(pct_of_equity=cap)
print(f"C15 position notional as % of PREVIOUS-close equity: max {T2.pct_of_equity.max():.4f}%  "
      f"count > 10.0%: {int((T2.pct_of_equity > 10.0).sum())}")
print(f"    negative cash on any session: {int((cash < -1e-6).sum())}   min cash Rs {cash.min():,.2f}")

print()
print("#" * 78); print("SECTION E/F — UNIVERSE + DATA"); print("#" * 78)
print(f"E19 universe file lines: {len(UNI)}; symbols in panel: {P.symbol.nunique()}; "
      f"fixed list, no time dimension in config/universe_frozen.txt")
fe = P[P.eligible].groupby("symbol")["date"].min()
print(f"E19 first-eligible = 300th session of that symbol's own history "
      f"(session_no >= 300); range {fe.min().date()} .. {fe.max().date()}")
late = first[first > dates[0]]
print(f"E20 symbols not present on 2015-01-01: {len(late)} of 188 (listing-based LOWER BOUND "
      f"on the F&O-membership question)")
tl = T[T.symbol.isin(late.index)]
print(f"E20 config A trades in those names: {len(tl)} of {len(T)} ({100*len(tl)/len(T):.1f}%), "
      f"P&L Rs {tl.pnl.sum():,.0f} of Rs {T.pnl.sum():,.0f} ({100*tl.pnl.sum()/T.pnl.sum():.1f}%)")

rng = np.random.default_rng(7)
s10 = T.sample(10, random_state=7)
print("\nF21 sample of 10 entry fills vs panel:")
for r in s10.itertuples():
    op = OPEN.at[r.entry_date, r.symbol]
    print(f"   {r.symbol:<12} {r.entry_date.date()}  panel open {op:>9.2f}  "
          f"fill {r.entry_px:>9.2f}  ratio {r.entry_px/op:.6f}  session exists: {op==op}")
s10b = cl.sample(10, random_state=11)
print("F21 sample of 10 exit fills vs panel:")
for r in s10b.itertuples():
    op = OPEN.at[r.exit_date, r.symbol]
    print(f"   {r.symbol:<12} {r.exit_date.date()}  panel open {op:>9.2f}  "
          f"fill {r.exit_px:>9.2f}  ratio {r.exit_px/op:.6f}  session exists: {op==op}")
bad = [(r.symbol, r.entry_date.date(), 'entry') for r in T.itertuples()
       if not np.isfinite(OPEN.at[r.entry_date, r.symbol])]
bad += [(r.symbol, r.exit_date.date(), 'exit') for r in cl.itertuples()
        if not np.isfinite(OPEN.at[r.exit_date, r.symbol])]
print(f"\nF22 trades transacting on a MISSING session for that symbol: {len(bad)}  {bad[:10]}")
