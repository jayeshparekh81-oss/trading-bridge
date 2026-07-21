"""LAR cross-day summary + dashboard (P7 STEP 2/3).

Aggregates analysis/<day>/lar_study_<sym>.json into ONE summary JSON (funnel counts per
state per level type, sweep→absorption→reclaim frequencies, TRIGGERED forward-R table,
sequence-depth vs forward-R Spearman when N permits) and a NEW standalone HTML page.

DEVIATION NOTE (audited 2026-07-21): the repo contains NO existing HTML dashboard
generator — the "review dashboard" is the founder's external tool fed by exported JSONs.
This generator is therefore a NEW additive file writing a NEW self-contained HTML; it
modifies nothing existing. DEFAULT OFF (runs only when invoked).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from research.lar_study import ORDER

MIN_N_FOR_RANKING = 10


def _spearman(x, y):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[o[j + 1]] == v[o[i]]:
                j += 1
            a = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[o[k]] = a
            i = j + 1
        return r
    rx, ry = rank(x), rank(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    c = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return c / (sx * sy) if sx and sy else 0.0


def summarize(analysis_root: str | Path) -> dict:
    root = Path(analysis_root)
    files = sorted(root.glob("*/lar_study_*.json"))
    funnel: dict[str, dict[str, int]] = {}
    reached: dict[str, dict[str, int]] = {}
    triggered: list[dict] = []
    days = set()
    for f in files:
        d = json.loads(f.read_text())
        days.add(d["day"])
        for name, lv in d["levels"].items():
            kind = name
            funnel.setdefault(kind, {}).setdefault(lv["final_state"], 0)
            funnel[kind][lv["final_state"]] += 1
            seen = {t["new"] for t in lv["transitions"]}
            for st in ORDER:
                if st in seen:
                    reached.setdefault(kind, {}).setdefault(st, 0)
                    reached[kind][st] += 1
            if "virtual_outcome" in lv:
                triggered.append({"day": d["day"], "symbol": d["symbol"], "level": name,
                                  "depth_of_seq": len(lv["transitions"]),
                                  **lv["virtual_outcome"]})
    swept = sum(v.get("SWEPT", 0) for v in reached.values())
    absorbed = sum(v.get("ABSORPTION_CANDIDATE", 0) for v in reached.values())
    reclaimed = sum(v.get("RECLAIMED", 0) for v in reached.values())
    lar = {"swept": swept, "absorption_candidates": absorbed, "reclaimed": reclaimed,
           "sweep_to_absorption_pct": round(100 * absorbed / swept, 1) if swept else None,
           "absorption_to_reclaim_pct": round(100 * reclaimed / absorbed, 1) if absorbed else None}
    ranking: dict = {"note": None}
    pairs = [(t["depth_of_seq"], t.get("r_10b")) for t in triggered
             if t.get("r_10b") is not None]
    if len(pairs) >= MIN_N_FOR_RANKING:
        ranking = {"n": len(pairs),
                   "spearman_seqdepth_vs_r10": round(_spearman([a for a, _ in pairs],
                                                              [b for _, b in pairs]), 3)}
    else:
        ranking = {"n": len(pairs),
                   "note": f"INSUFFICIENT DATA for ranking claims (n={len(pairs)} < {MIN_N_FOR_RANKING})"}
    return {"days": sorted(days), "n_files": len(files), "funnel_final_states": funnel,
            "states_reached": reached, "lar_frequencies": lar,
            "triggered": triggered, "ranking": ranking}


def render_html(summary: dict) -> str:
    rows = []
    for kind in sorted(summary["funnel_final_states"]):
        fin = summary["funnel_final_states"][kind]
        rows.append(f"<tr><td>{kind}</td>" + "".join(
            f"<td>{summary['states_reached'].get(kind, {}).get(s, 0)}</td>"
            for s in ORDER[3:9]) + f"<td>{json.dumps(fin)}</td></tr>")
    trig = "".join(
        f"<tr><td>{t['day']}</td><td>{t['symbol']}</td><td>{t['level']}</td>"
        f"<td>{t['side']}</td><td>{t['trigger_price']}</td><td>{t['stop']}</td>"
        f"<td>{t.get('r_5b')}</td><td>{t.get('r_10b')}</td><td>{t.get('r_20b')}</td></tr>"
        for t in summary["triggered"]) or "<tr><td colspan=9>none</td></tr>"
    lar = summary["lar_frequencies"]
    rk = summary["ranking"]
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>LAR Study — Glass Box</title>
<style>body{{font-family:monospace;margin:2em}}table{{border-collapse:collapse}}
td,th{{border:1px solid #999;padding:4px 8px}}h2{{margin-top:1.5em}}</style></head><body>
<h1>LAR Study — Glass Box (COUNTING ONLY — no trading, descriptive)</h1>
<p>days: {', '.join(summary['days'])} · files: {summary['n_files']}</p>
<h2>Funnel (levels reaching each state)</h2>
<table><tr><th>level</th><th>SWEPT</th><th>ABSORB</th><th>FLIPPED</th><th>RECLAIMED</th>
<th>ARMED</th><th>TRIGGERED</th><th>final states</th></tr>{''.join(rows)}</table>
<h2>The LAR question</h2>
<p>swept: {lar['swept']} · sweep→absorption: {lar['sweep_to_absorption_pct']}% ·
absorption→reclaim: {lar['absorption_to_reclaim_pct']}%</p>
<h2>TRIGGERED (virtual markers, gross R at horizons — descriptive only)</h2>
<table><tr><th>day</th><th>sym</th><th>level</th><th>side</th><th>trigger</th><th>stop</th>
<th>r_5b</th><th>r_10b</th><th>r_20b</th></tr>{trig}</table>
<h2>Ranking check</h2><p>{json.dumps(rk)}</p>
<p><i>All thresholds pre-registered in STUDY_CONFIG (embedded in every day JSON).
N is tiny — no outcome claims; the 15-day criteria remain the judge.</i></p>
</body></html>"""


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="research.lar_summary")
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv[1:])
    root = Path(args.root) / "analysis"
    s = summarize(root)
    (root / "lar_summary.json").write_text(json.dumps(s, indent=1))
    (root / "lar_dashboard.html").write_text(render_html(s))
    print(f"summary: {root/'lar_summary.json'}")
    print(f"dashboard: {root/'lar_dashboard.html'}")
    print(json.dumps({k: s[k] for k in ("lar_frequencies", "ranking")}, indent=1))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
