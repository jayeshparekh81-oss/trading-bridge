"""Signal score-distribution baseline (research, read-only).

Founder's need (2026-07-15): capture TODAY's full pre-OFI signal baseline so
tomorrow's depth.ofi_enabled flip + re-run isolates OFI's contribution cleanly —
and surface any OTHER component that is silently DEAD (always-zero activation with
a nonzero weight, like book_ofi/queue_imbalance were) vs INERT-by-design (weight 0).

Reads analysis/<date>/signals.parquet (one row per evaluated candidate, each with a
per-component ``breakdown`` JSON of activation/contribution/enabled/weight). Pure
descriptive stats — no model, no config, no look-ahead.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pyarrow.parquet as pq

BUCKETS = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 30), (30, 1e9)]
EPS = 1e-9


def load(path: Path) -> list[dict]:
    """Rows with the breakdown JSON parsed into ``comp`` (name -> component dict)."""
    rows = pq.read_table(str(path)).to_pylist()
    for r in rows:
        r["comp"] = json.loads(r.get("breakdown") or "{}")
    return rows


def _pctile(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    i = min(len(s) - 1, int(math.ceil(q / 100.0 * len(s))) - 1)
    return s[max(0, i)]


def score_histogram(rows: list[dict]) -> dict:
    scores = [r["score"] for r in rows]
    hist = {f"{lo}-{'+' if hi > 1e8 else int(hi)}": sum(1 for s in scores if lo <= s < hi)
            for lo, hi in BUCKETS}
    return {"hist": hist, "median": _pctile(scores, 50), "p90": _pctile(scores, 90),
            "max": max(scores) if scores else 0.0, "n": len(scores)}


def component_stats(rows: list[dict]) -> dict:
    names = sorted({k for r in rows for k in r["comp"]})
    out = {}
    for name in names:
        acts, contribs, weight, enabled = [], [], 0.0, False
        for r in rows:
            c = r["comp"].get(name)
            if not c:
                continue
            weight = c.get("weight", 0.0)
            enabled = c.get("enabled", False)
            acts.append(float(c.get("activation") or 0.0))
            contribs.append(float(c.get("contribution") or 0.0))
        nz = [a for a in acts if abs(a) > EPS]
        nz_contrib = [c for c in contribs if abs(c) > EPS]
        # The parquet can't tell WHY a weighted component is always zero (unbuilt
        # stub vs gated-off vs uncalibrated threshold) — it flags it for a code-level
        # root-cause check. weight 0 = inert by design.
        if weight == 0:
            status = "INERT (weight 0, by design)"
        elif not nz:
            status = "ALWAYS-ZERO (weight>0 — investigate cause)"
        else:
            status = "LIVE"
        out[name] = {
            "weight": weight, "enabled": enabled, "status": status,
            "nonzero_count": len(nz), "fire_rate": round(len(nz) / len(rows), 3) if rows else 0,
            "act_min": round(min(nz), 4) if nz else 0.0,
            "act_median": round(_pctile(nz, 50), 4) if nz else 0.0,
            "act_max": round(max(nz), 4) if nz else 0.0,
            "contrib_median": round(_pctile(nz_contrib, 50), 3) if nz_contrib else 0.0,
            "contrib_max": round(max(nz_contrib), 3) if nz_contrib else 0.0,
        }
    return out


def cofire_matrix(rows: list[dict]) -> dict:
    """Jaccard overlap of nonzero-activation sets for each LIVE component pair."""
    live = [n for n, s in component_stats(rows).items() if s["status"] == "LIVE"]
    fire = {n: {i for i, r in enumerate(rows)
                if abs(float(r["comp"].get(n, {}).get("activation") or 0.0)) > EPS}
            for n in live}
    out = {}
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            inter = len(fire[a] & fire[b])
            union = len(fire[a] | fire[b])
            out[f"{a} & {b}"] = {"both": inter, "either": union,
                                 "jaccard": round(inter / union, 3) if union else 0.0}
    return out


def max_achievable(rows: list[dict]) -> dict:
    """Theoretical max score if every component fired at activation 1.0, and the
    real ceiling with the DEAD (always-zero) components removed."""
    cs = component_stats(rows)
    total = sum(s["weight"] for s in cs.values())
    dead = {n: s["weight"] for n, s in cs.items() if s["status"].startswith("ALWAYS-ZERO")}
    inert = {n: s["weight"] for n, s in cs.items() if s["status"].startswith("INERT")}
    ceiling = total - sum(dead.values())
    return {"total_weight": total, "dead": dead, "inert_weight": sum(inert.values()),
            "ceiling_with_dead_removed": ceiling,
            "observed_max": max((r["score"] for r in rows), default=0.0)}


def _rows_report(rows: list[dict]) -> None:
    from collections import Counter
    import datetime
    IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

    print(f"SCORE-DISTRIBUTION BASELINE — {len(rows)} candidates (pre-OFI)\n")
    h = score_histogram(rows)
    print("1. SCORE HISTOGRAM")
    for k, v in h["hist"].items():
        print(f"   {k:>6s}: {v:4d}  {'#' * (v // 3)}")
    print(f"   median={h['median']:.1f}  p90={h['p90']:.1f}  max={h['max']:.1f}\n")

    print("2. COMPONENT FIRING RATES")
    cs = component_stats(rows)
    print(f"   {'component':22s} {'w':>4s} {'fire%':>6s} {'act(min/med/max)':>22s} "
          f"{'contrib med/max':>16s}  status")
    for n, s in sorted(cs.items(), key=lambda kv: -kv[1]["weight"]):
        am = f"{s['act_min']}/{s['act_median']}/{s['act_max']}"
        cm = f"{s['contrib_median']}/{s['contrib_max']}"
        print(f"   {n:22s} {s['weight']:4.0f} {100*s['fire_rate']:5.1f}% {am:>22s} {cm:>16s}  {s['status']}")

    print("\n3. COMPONENT CO-FIRING (LIVE pairs, Jaccard)")
    for k, v in sorted(cofire_matrix(rows).items(), key=lambda kv: -kv[1]["jaccard"]):
        print(f"   {k:44s} both={v['both']:3d}/{v['either']:<3d}  jaccard={v['jaccard']}")

    print("\n4. GATE BREAKDOWN")
    for reason, cnt in Counter(r["gate_reason"] or "(passed gates)" for r in rows).most_common():
        scored = sum(1 for r in rows if (r["gate_reason"] or "(passed gates)") == reason and r["score"] > 0)
        print(f"   {reason:32s} {cnt:4d}  (of which scored>0: {scored})")
    print(f"   fired (threshold met): {sum(1 for r in rows if r['fired'])}  "
          f"[threshold={rows[0]['threshold']:.0f} INERT]")

    print("\n5. LONG vs SHORT")
    for side in ("long", "short"):
        ss = [r["score"] for r in rows if r["side"] == side]
        if ss:
            print(f"   {side:6s} n={len(ss):4d}  median={_pctile(ss,50):.1f}  p90={_pctile(ss,90):.1f}  max={max(ss):.1f}")

    print("\n6. TIME-OF-DAY (IST hour)")
    byhr = Counter(datetime.datetime.fromtimestamp(r["ts_ns"] / 1e9, IST).hour for r in rows)
    for hr in sorted(byhr):
        print(f"   {hr:02d}:00  {byhr[hr]:4d}  {'#' * (byhr[hr] // 3)}")

    print("\n7. INSTRUMENT")
    for inst, cnt in Counter(r["instrument"] for r in rows).most_common():
        ms = [r["score"] for r in rows if r["instrument"] == inst]
        print(f"   {inst:16s} n={cnt:4d}  median={_pctile(ms,50):.1f}  max={max(ms):.1f}")

    print("\nMAX ACHIEVABLE")
    m = max_achievable(rows)
    print(f"   total weight (all fire @1.0): {m['total_weight']:.0f}")
    print(f"   DEAD (always-zero, weight>0): {m['dead']}  |  INERT weight: {m['inert_weight']:.0f}")
    print(f"   CEILING with dead removed:    {m['ceiling_with_dead_removed']:.0f}")
    print(f"   OBSERVED max score:           {m['observed_max']:.1f}  "
          f"({100*m['observed_max']/m['ceiling_with_dead_removed']:.0f}% of ceiling)")


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-07-15")
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv[1:])
    path = Path(args.root) / "analysis" / args.date / "signals.parquet"
    if not path.exists():
        print(f"no signals.parquet at {path}")
        return 1
    _rows_report(load(path))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
