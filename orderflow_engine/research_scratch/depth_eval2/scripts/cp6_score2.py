"""CP6 (run 2) — the one real run per PREREG2; run twice for determinism; run-1 comparison table."""
import json, sys, numpy as np
from pathlib import Path
D2 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D2 / "scripts")); import scorer2 as S
tag = sys.argv[1] if len(sys.argv) > 1 else "run1"; dfs = {i: S.load(i) for i in ("NIFTY_FUT", "BANKNIFTY_FUT")}; cells = S.powered_cells(); rows = []
for h, feats in list(cells.items()) + [("close", S.C.SIGNED + S.C.COUNTS)]:
    for feat in feats:
        a, b = S.score(dfs["NIFTY_FUT"], "NIFTY_FUT", feat, h), S.score(dfs["BANKNIFTY_FUT"], "BANKNIFTY_FUT", feat, h)
        v = "UNPOWERED — not scored" if h == "close" else S.cell_verdict(a, b)
        rows.append({"horizon": h, "feature": feat, "NIFTY_FUT": a, "BANKNIFTY_FUT": b, "same_sign": bool(a.get("sign") == b.get("sign") and a.get("sign", 0) != 0), "verdict": v, "cost": "PRE-COST / PENDING"})
(D2 / f"cp6_result2_{tag}.json").write_text(json.dumps(rows, indent=1)); print(f"  {tag}: {len(rows)} cells; alpha (second look, {S.N_HYP_BOTH_RUNS} hypotheses across both runs) = {S.ALPHA:.5f}")
print("  horizon feature                | NIFTY n_eff  diff_pts  diff_bps  p       | BANKNIFTY n_eff  diff_pts  diff_bps  p       | same sign | verdict")
for r in rows:
    a, b = r["NIFTY_FUT"], r["BANKNIFTY_FUT"]
    print(f"  {r['horizon']:>5}   {r['feature']:<22} | {a['n_eff']:>5}  {a['diff_pts']:+8.3f}  {a['diff_bps']:+7.3f}  {a['p_two_sided']:.4f} | {b['n_eff']:>5}  {b['diff_pts']:+8.3f}  {b['diff_bps']:+7.3f}  {b['p_two_sided']:.4f} | {'yes' if r['same_sign'] else 'NO '} | {r['verdict']}")
