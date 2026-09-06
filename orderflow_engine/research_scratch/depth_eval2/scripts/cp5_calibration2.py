"""CP5 (run 2) — RANDX, INJ+R, INJ-R on RANDOM events (clean design), seeds 11 and 22 (non-overlapping by seed sequence)."""
import json, sys, zlib, numpy as np
from pathlib import Path
D2 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D2 / "scripts")); import scorer2 as S
dfs = {i: S.load(i) for i in ("NIFTY_FUT", "BANKNIFTY_FUT")}; cells = S.powered_cells(); out = {"RANDX": [], "INJ+R": [], "INJ-R": []}
for seed in (11, 22):
    for h, feats in cells.items():
        for feat in feats:
            res = {}
            for inst, df in dfs.items():
                real, _ = S.events_for(df, inst, feat); slot = df.slot.to_numpy(); rng = np.random.default_rng([seed, zlib.crc32(f"{feat}|{h}".encode())]); rand = np.zeros(len(df), bool)
                for s in np.unique(slot[real]): pool = np.flatnonzero(slot == s); rand[rng.choice(pool, size=int(np.sum(real & (slot == s))), replace=False)] = True
                res[inst] = {"RANDX": S.score(df, inst, feat, h, ev=rand, seed=seed)}
                mde = S.PW["instruments"][inst]["features"][feat]["by_horizon"][h]["mde_pts"]; delta = 3.0 * mde; sig = S.PW["instruments"][inst]["dispersion"][h]["sigma_pts"]
                for tag, sgn in (("INJ+R", 1), ("INJ-R", -1)):
                    r = S.score(df, inst, feat, h, ev=rand, inject=sgn * delta, seed=seed); r["injected_pts"] = sgn * delta; r["se_pts"] = sig * np.sqrt(2.0 / max(r["n_eff"], 1))
                    r["recovered_minus_injected_pts"] = r["diff_pts"] - sgn * delta; r["within_2se"] = bool(abs(r["recovered_minus_injected_pts"]) <= 2 * r["se_pts"]); r["sign_ok"] = bool(np.sign(r["diff_pts"]) == sgn); res[inst][tag] = r
            for tag in out: out[tag].append({"seed": seed, "horizon": h, "feature": feat, "NIFTY_FUT": res["NIFTY_FUT"][tag], "BANKNIFTY_FUT": res["BANKNIFTY_FUT"][tag], "verdict": S.cell_verdict(res["NIFTY_FUT"][tag], res["BANKNIFTY_FUT"][tag])})
(D2 / "cp5_calibration2.json").write_text(json.dumps(out, indent=1)); I = ("NIFTY_FUT", "BANKNIFTY_FUT")
for tag, rows in out.items():
    n = 2 * len(rows)
    if tag == "RANDX":
        ps = [r[i]["p_two_sided"] for r in rows for i in I]; print(f"  RANDX: {len(rows)} cells x 2 seeds | passing the pass bar: {sum(r['verdict'].startswith('PRE-COST PASS') for r in rows)} | p<0.05: {sum(p<0.05 for p in ps)}/{n} (expected ~{0.05*n:.1f}) | min p {min(ps):.4f} median {np.median(ps):.3f}")
    else:
        print(f"  {tag}: within 2 SE {sum(r[i]['within_2se'] for r in rows for i in I)}/{n} | correct sign {sum(r[i]['sign_ok'] for r in rows for i in I)}/{n} | cells passing {sum(r['verdict'].startswith('PRE-COST PASS') for r in rows)}/{len(rows)}")
        for r in rows[:3]:
            for i in I: x = r[i]; print(f"      seed{r['seed']} {r['horizon']:>4} {r['feature']:<22} {i:<13} injected={x['injected_pts']:+.3f} recovered={x['diff_pts']:+.3f} (SE {x['se_pts']:.3f}) p={x['p_two_sided']:.4f}")
