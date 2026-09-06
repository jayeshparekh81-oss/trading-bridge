"""CP5 — the dummy exam: RANDX (random events), INJ+ / INJ- (known injected effect), each with seeds 1 and 2."""
import json, sys, zlib, numpy as np, pandas as pd
from pathlib import Path
DE = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(DE / "scripts")); import scorer as S
PW = S.PW; out = {"RANDX": [], "INJ+": [], "INJ-": [], "INJ+R": [], "INJ-R": []}
dfs = {i: S.load(i) for i in ("NIFTY_FUT", "BANKNIFTY_FUT")}
for seed in (1, 2):
    for h, feats in S.POWERED.items():
        for feat in feats:
            res = {}
            for inst, df in dfs.items():
                real = S.events_for(df, inst, feat); slot = df.slot.to_numpy(); rng = np.random.default_rng([seed, zlib.crc32(f'{feat}|{h}'.encode())])   # deterministic (Python hash() is per-process)
                rand = np.zeros(len(df), bool)                                            # RANDX: same count per slot, uniformly random bars
                for s in np.unique(slot[real]):
                    pool = np.flatnonzero(slot == s); rand[rng.choice(pool, size=int(np.sum(real & (slot == s))), replace=False)] = True
                res[inst] = {"RANDX": S.score(df, inst, feat, h, ev=rand, seed=seed)}
                mde = PW["instruments"][inst]["features"][feat]["by_horizon"][h]["mde_pts"]; delta = 3.0 * mde
                for tag, sgn, evx in (("INJ+", 1, None), ("INJ-", -1, None), ("INJ+R", 1, rand), ("INJ-R", -1, rand)):
                    r = S.score(df, inst, feat, h, ev=evx, inject=sgn * delta, seed=seed); r["injected_pts"] = sgn * delta
                    r["se_pts"] = PW["instruments"][inst]["dispersion"][h]["sigma_pts"] * np.sqrt(2.0 / r["n_eff"]); r["recovered_minus_injected_pts"] = r["diff_pts"] - sgn * delta
                    r["within_2se"] = bool(abs(r["recovered_minus_injected_pts"]) <= 2 * r["se_pts"]); r["sign_ok"] = bool(np.sign(r["diff_pts"]) == sgn); res[inst][tag] = r
            for tag in out:
                a, b = res["NIFTY_FUT"][tag], res["BANKNIFTY_FUT"][tag]
                out[tag].append({"seed": seed, "horizon": h, "feature": feat, "NIFTY_FUT": a, "BANKNIFTY_FUT": b, "verdict": S.cell_verdict(a, b)})
(DE / "cp5_calibration.json").write_text(json.dumps(out, indent=1))
for tag, rows in out.items():
    print(f"\n  {tag}: {len(rows)} cells (16 x 2 seeds)")
    if tag == "RANDX":
        ps = [r[i]["p_two_sided"] for r in rows for i in ("NIFTY_FUT", "BANKNIFTY_FUT")]
        print(f"    cells passing the pass bar: {sum(r['verdict'].startswith('PRE-COST PASS') for r in rows)} | p<0.05 on an instrument: {sum(p < 0.05 for p in ps)}/{len(ps)} (expected ~{0.05*len(ps):.1f}) | min p {min(ps):.3f} | median p {np.median(ps):.3f}")
    else:
        ok2 = sum(r[i]["within_2se"] for r in rows for i in ("NIFTY_FUT", "BANKNIFTY_FUT")); sg = sum(r[i]["sign_ok"] for r in rows for i in ("NIFTY_FUT", "BANKNIFTY_FUT"))
        print(f"    recovered within 2 SE of injected: {ok2}/{2*len(rows)} | correct sign: {sg}/{2*len(rows)} | cells passing: {sum(r['verdict'].startswith('PRE-COST PASS') for r in rows)}/{len(rows)}")
        if tag in ("INJ+", "INJ-"):
            other = out["INJ-" if tag == "INJ+" else "INJ+"]
            resid_same = sum(abs(r[i]["recovered_minus_injected_pts"] - o[i]["recovered_minus_injected_pts"]) < 1e-9 for r, o in zip(rows, other) for i in ("NIFTY_FUT", "BANKNIFTY_FUT"))
            print(f"    residual (recovered - injected) identical between INJ+ and INJ- : {resid_same}/{2*len(rows)}  -> the residual is the REAL event effect, not instrument error")
        for r in rows[:4] + rows[16:20]:
            for i in ("NIFTY_FUT", "BANKNIFTY_FUT"): x = r[i]; print(f"      seed{r['seed']} {r['horizon']:>4} {r['feature']:<17} {i:<13} injected={x['injected_pts']:+.3f} recovered={x['diff_pts']:+.3f} (±SE {x['se_pts']:.3f}) p={x['p_two_sided']:.3f}")
