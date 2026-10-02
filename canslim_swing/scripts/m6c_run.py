#!/usr/bin/env python3
"""M6c Round-2 runner — SEPARATE script (Stage A.1). Champion + grid + nulls.

REGISTERED FRAME (amended): sealed window 01-Apr-2019 -> 31-Jul-2021, universe 169
(M6b's 173 minus 4 insurers). Everything before 01-Apr-2019 is WARMUP ONLY.

HARD ASSERTION: no trade row and no equity row may predate 2019-04-01.
"""
from __future__ import annotations

import itertools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m5_engine as E  # noqa: E402
import m5_sweep as S  # noqa: E402

TRACK = Path(__file__).resolve().parents[1]
ROOT = TRACK / "data" / "round2" / "root"
OUT = TRACK / "data" / "round2"
WIN_START = pd.Timestamp("2019-04-01")
WIN_END = pd.Timestamp("2021-07-31")

CHAMPION = E.Config(exit="E4", stop="8", c_growth=1.30, base_floor=0.0,
                    rs_min=90.0, mfilter="ema10m", volume="none")


def load():
    mkt = E.load_market(ROOT)                    # no max_date: warmup is legitimate
    # SEALED BOUNDARY on the EPS frame. Passing no max_date is right for pre-window
    # WARMUP but it also disables the post-window guard, and the merged parquet
    # carries announcements out to 2026 (62% of rows postdate 2021-07-31). That
    # leaks through eps_base_table's cons/stand SERIES PICK, which counts quarters
    # over the whole table with no as-of cutoff — a future filing can decide which
    # series a 2019 day uses. Caught by adversarial review; measured impact was
    # PF 1.68 -> 1.16, i.e. it would have manufactured a PASS.
    eps = mkt["eps"]
    mkt["eps"] = eps[eps["announce_ts"] <= WIN_END + pd.Timedelta(days=1)]
    assert mkt["eps"]["announce_ts"].max() <= WIN_END + pd.Timedelta(days=1), \
        "SEALED LEAK: post-window EPS announcement visible"
    eps_tab = E.eps_base_table(mkt)
    cf = E.build_candidate_frame(mkt, eps_tab)
    all_days = sorted(cf["date"].unique())
    calendar = [d for d in all_days if WIN_START <= d <= WIN_END]
    assert calendar and calendar[0] >= WIN_START, "calendar leaks pre-window days"
    return mkt, cf, calendar


def assert_in_window(trades: pd.DataFrame, equity: pd.DataFrame, tag: str):
    if trades is not None and not trades.empty:
        assert trades["entry_date"].min() >= WIN_START, f"{tag}: entry predates window"
        assert trades["exit_date"].min() >= WIN_START, f"{tag}: exit predates window"
        assert trades["exit_date"].max() <= WIN_END + pd.Timedelta(days=5), f"{tag}: exit past window"
    if equity is not None and not equity.empty:
        assert equity.index.min() >= WIN_START, f"{tag}: equity row predates window"


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "champion"
    mkt, cf, calendar = load()
    print(f"[load] universe {len(mkt['universe'])} | window {calendar[0].date()} -> "
          f"{calendar[-1].date()} ({len(calendar)} sessions)")

    if mode == "champion":
        r = E.simulate(CHAMPION, cf, mkt["px"], calendar)
        pos = E.positionize(r["trades"])
        assert_in_window(pos, r["equity"], "champion")
        pos.to_parquet(OUT / "r2_champion_trades.parquet")
        r["equity"].to_parquet(OUT / "r2_champion_equity.parquet")
        m = E.metrics(r["trades"], r["equity"])
        print("champion:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()})

    elif mode == "grid":
        combos = list(itertools.product(S.EXITS, S.STOPS, S.GROWTH,
                                        ["none", "p25", "p50"], S.RS, S.MFILTER, S.VOLUME))
        assert len(combos) == 2268, len(combos)
        # IN-WINDOW ONLY: deriving the base-EPS floor from the full 2016-2021 scan
        # would let warmup and post-window rows set a threshold used inside the
        # window — a subtle leak in the grid's floor dimension. (The champion uses
        # floor='none', so this affects the thermometer, not the sealed shot.)
        in_win = cf[(cf["date"] >= WIN_START) & (cf["date"] <= WIN_END)]
        floors = S.base_floor_levels(in_win)
        print(f"[floors] p25={floors['p25']:.3f} p50={floors['p50']:.3f} "
              f"(from {floors['_n']:,} IN-WINDOW rows)")
        rows = []
        t0 = time.time()
        for i, (ex, st, gr, fl, rs, mf, vo) in enumerate(combos, 1):
            cfg = E.Config(exit=ex, stop=st, c_growth=gr, base_floor=floors[fl],
                           rs_min=rs, mfilter=mf, volume=vo)
            res = E.simulate(cfg, cf, mkt["px"], calendar)
            mm = E.metrics(res["trades"], res["equity"])
            rows.append({"exit": ex, "stop": st, "c_growth": gr, "floor": fl, "rs": rs,
                         "mfilter": mf, "volume": vo, **mm})
            if i % 300 == 0:
                el = time.time() - t0
                print(f"  {i}/2268 ({el:.0f}s, eta {el/i*(2268-i)/60:.1f}m)", flush=True)
                pd.DataFrame(rows).to_parquet(OUT / "r2_grid.parquet")
        pd.DataFrame(rows).to_parquet(OUT / "r2_grid.parquet")
        print(f"[grid] done {time.time()-t0:.0f}s")

    elif mode == "sens":
        rows = []
        for slip in (0.0005, 0.0010, 0.0020):
            cfg = E.Config(exit="E4", stop="8", c_growth=1.30, base_floor=0.0,
                           rs_min=90.0, mfilter="ema10m", volume="none", slippage=slip)
            res = E.simulate(cfg, cf, mkt["px"], calendar)
            mm = E.metrics(res["trades"], res["equity"])
            rows.append({"slippage_%": 100 * slip, **mm})
        pd.DataFrame(rows).to_parquet(OUT / "r2_sensitivity.parquet")
        print(pd.DataFrame(rows).to_string(index=False))

    elif mode == "exclude":            # Stage F recompute, symbol passed as argv[2]
        drop = sys.argv[2]
        res = E.simulate(CHAMPION, cf[cf["symbol"] != drop], mkt["px"], calendar)
        mm = E.metrics(res["trades"], res["equity"])
        pd.DataFrame([{"excluded": drop, **mm}]).to_parquet(OUT / "r2_excl.parquet")
        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in mm.items()})


if __name__ == "__main__":
    main()
