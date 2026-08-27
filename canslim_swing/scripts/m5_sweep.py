#!/usr/bin/env python3
"""M5 STAGE B — pre-registered build-half sweep (7x3x2x3x3x3x2 = 2,268 configs).

BUILD ONLY. The market is loaded from canslim_swing/data/build/ with the
boundary assertion armed; this script never opens data/sealed/.

Results cache to data/m5/sweep_results.parquet and the run is resumable
(already-computed config keys are skipped).
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

TRACK = Path(__file__).resolve().parents[1]
BUILD_ROOT = TRACK / "data" / "build"
OUT = TRACK / "data" / "m5"
RESULTS = OUT / "sweep_results.parquet"

EXITS = ["E1", "E2", "E3", "E4", "E5", "E6", "E7"]
STOPS = ["5", "8", "atr"]
GROWTH = [1.25, 1.30]
RS = [70.0, 80.0, 90.0]
MFILTER = ["dma_entry", "dma_force", "ema10m"]
VOLUME = ["none", "violation"]


def base_floor_levels(cf: pd.DataFrame) -> dict:
    """p25/p50 of the BUILD-half distribution of candidate base-quarter EPS.
    Derived from data (echoed in the report), never hardcoded."""
    cand = cf[cf["t1_7"] & cf["base_pass"] & (cf["eps_base"] > 0)
              & (cf["eps_latest"] >= 1.25 * cf["eps_base"])
              & (cf["rs_pct"] >= 80) & cf["dma_on"]]
    return {"none": 0.0,
            "p25": float(cand["eps_base"].quantile(0.25)),
            "p50": float(cand["eps_base"].quantile(0.50)),
            "_n": len(cand)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    mkt = E.load_market(BUILD_ROOT, max_date=E.BOUNDARY)
    eps_tab = E.eps_base_table(mkt)
    cf = E.build_candidate_frame(mkt, eps_tab)
    calendar = sorted(cf["date"].unique())
    floors = base_floor_levels(cf)
    print(f"[load] {time.time() - t0:.1f}s | universe {len(mkt['universe'])} | "
          f"days {len(calendar)} ({calendar[0].date()} -> {calendar[-1].date()})")
    print(f"[floors] from {floors['_n']:,} build candidate rows: "
          f"p25={floors['p25']:.3f}  p50={floors['p50']:.3f}")

    done = {}
    if RESULTS.exists():
        prev = pd.read_parquet(RESULTS)
        done = {r.key: r for r in prev.itertuples()}
        print(f"[resume] {len(done):,} configs already cached")

    combos = list(itertools.product(EXITS, STOPS, GROWTH,
                                    ["none", "p25", "p50"], RS, MFILTER, VOLUME))
    assert len(combos) == 2268, len(combos)
    rows = list(pd.read_parquet(RESULTS).to_dict("records")) if RESULTS.exists() else []

    t0 = time.time()
    n_new = 0
    for i, (ex, st, gr, fl, rs, mf, vo) in enumerate(combos, 1):
        cfg = E.Config(exit=ex, stop=st, c_growth=gr, base_floor=floors[fl],
                       rs_min=rs, mfilter=mf, volume=vo)
        if cfg.key() in done:
            continue
        r = E.simulate(cfg, cf, mkt["px"], calendar)
        m = E.metrics(r["trades"], r["equity"])
        rows.append({"key": cfg.key(), "exit": ex, "stop": st, "c_growth": gr,
                     "floor": fl, "rs": rs, "mfilter": mf, "volume": vo, **m})
        n_new += 1
        if n_new % 200 == 0:
            el = time.time() - t0
            print(f"  {i}/{len(combos)}  ({n_new} new, {el:.0f}s, "
                  f"eta {el / n_new * (len(combos) - i) / 60:.1f} min)", flush=True)
            pd.DataFrame(rows).to_parquet(RESULTS)

    df = pd.DataFrame(rows)
    df.to_parquet(RESULTS)
    meta = {"floors": floors, "n_configs": len(df),
            "calendar_first": str(calendar[0].date()), "calendar_last": str(calendar[-1].date()),
            "universe": len(mkt["universe"]), "elapsed_s": round(time.time() - t0, 1)}
    pd.Series(meta).to_json(OUT / "sweep_meta.json")
    print(f"\n[done] {len(df):,} configs in {time.time() - t0:.0f}s -> {RESULTS}")


if __name__ == "__main__":
    main()
