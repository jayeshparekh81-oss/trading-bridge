"""CP6 — the one real run, exactly per PREREG. Run twice (--rerun) to prove determinism."""
import json, sys, numpy as np
from pathlib import Path
DE = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(DE / "scripts")); import scorer as S
tag = sys.argv[1] if len(sys.argv) > 1 else "run1"; dfs = {i: S.load(i) for i in ("NIFTY_FUT", "BANKNIFTY_FUT")}; rows = []
for h, feats in list(S.POWERED.items()) + [("close", S.ALL_FEATURES)]:
    for feat in feats:
        a, b = S.score(dfs["NIFTY_FUT"], "NIFTY_FUT", feat, h), S.score(dfs["BANKNIFTY_FUT"], "BANKNIFTY_FUT", feat, h)
        v = "UNPOWERED — not scored" if h == "close" else S.cell_verdict(a, b)
        rows.append({"horizon": h, "feature": feat, "NIFTY_FUT": a, "BANKNIFTY_FUT": b, "same_sign": bool(a.get("sign") == b.get("sign")), "verdict": v, "cost": "PRE-COST / PENDING"})
(DE / f"cp6_result_{tag}.json").write_text(json.dumps(rows, indent=1))
print(f"  {tag}: {len(rows)} cells")
print("  horizon feature           | NIFTY n_eff  diff_pts   diff_bps   p      | BANKNIFTY n_eff  diff_pts  diff_bps   p      | same sign | verdict")
for r in rows:
    a, b = r["NIFTY_FUT"], r["BANKNIFTY_FUT"]
    print(f"  {r['horizon']:>5}   {r['feature']:<17} | {a['n_eff']:>5}  {a['diff_pts']:+8.3f}  {a['diff_bps']:+7.3f}  {a['p_two_sided']:.3f} | {b['n_eff']:>5}  {b['diff_pts']:+8.3f}  {b['diff_bps']:+7.3f}  {b['p_two_sided']:.3f} | {'yes' if r['same_sign'] else 'NO '} | {r['verdict']}")
