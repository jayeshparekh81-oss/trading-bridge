"""A4 baseline 2 (vol-matched control) + the ONE sealed-set unlock."""
import json, math
import numpy as np, pandas as pd
from statistics import NormalDist
import cq_engine as E, cq_stats as S, cq_guards as G

ALPHA=0.05/6; ZC=NormalDist().inv_cdf(1-ALPHA/2)
HORIZON_BARS=240; K_GRID=[1.0,1.5,2.0,3.0]; CELLS=[(1.0,1.0),(2.0,1.0)]
b=pd.read_parquet("raw/bars_1m.parquet").reset_index(drop=True)
ts=b["ts_ms"].to_numpy(np.int64); close=b["close"].to_numpy(float)
high=b["high"].to_numpy(float); low=b["low"].to_numpy(float)
delta=b["delta"].to_numpy(float); vol=b["volume"].to_numpy(float); cvd=b["cvd"].to_numpy(float)
ret=np.diff(np.log(close),prepend=np.nan)
sig_ret=pd.Series(ret).rolling(60).std().to_numpy(); sigma=sig_ret*close
hour=((ts//3600000)%24).astype(int)
volb=S.vol_bucket(np.nan_to_num(sig_ret,nan=np.nanmedian(sig_ret)),5)
rmin=pd.Series(close).rolling(60).min().shift(1).to_numpy()
rmax=pd.Series(close).rolling(60).max().shift(1).to_numpy()
vmin=pd.Series(cvd).rolling(60).min().shift(1).to_numpy()
vmax=pd.Series(cvd).rolling(60).max().shift(1).to_numpy()
absd=np.abs(delta); q90d=pd.Series(absd).rolling(1440).quantile(.90).shift(1).to_numpy()
absr=np.abs(ret); q33r=pd.Series(absr).rolling(1440).quantile(1/3).shift(1).to_numpy()
imb=np.divide(delta,vol,out=np.zeros_like(delta),where=vol>0)
q90i=pd.Series(imb).rolling(1440).quantile(.90).shift(1).to_numpy()
q10i=pd.Series(imb).rolling(1440).quantile(.10).shift(1).to_numpy()
valid=np.isfinite(sigma)&(sigma>0); idx=np.arange(len(close))
HYP={"H1_CVD_divergence":(valid&(close<rmin)&(cvd>vmin), valid&(close>rmax)&(cvd<vmax)),
     "H2_absorption":(valid&(absd>=q90d)&(absr<=q33r)&(delta<0), valid&(absd>=q90d)&(absr<=q33r)&(delta>0)),
     "H3_aggressive_flow_imbalance":(valid&(imb>=q90i), valid&(imb<=q10i))}
split_i=int(len(close)*0.70); split_ts=int(ts[split_i])

def rate_for(ev, tgt, stp, side):
    ev=[int(i) for i in ev if i+HORIZON_BARS+1<len(close)]
    if not ev: return None
    objs=[E.first_passage_bars(ts,high,low,close,i,sigma[i],K_GRID,HORIZON_BARS) for i in ev]
    kept,raw,eff=E.suppress_overlapping(ev,objs,tgt,stp,side)
    outs=[E.hit_first_bars(objs[i],tgt,stp,side) for i in kept]
    res=[o for o in outs if o in ("target","stop")]
    if not res: return None
    return {"raw_n":raw,"effective_n":eff,"resolved":len(res),
            "rate":sum(1 for o in res if o=="target")/len(res),
            "censored":sum(1 for o in outs if o=="censored"),
            "ambiguous":sum(1 for o in outs if o=="ambiguous")}

print("===== A4 BASELINE 2 - VOLATILITY-MATCHED CONTROL, on DISCOVERY =====")
ctrl_rows=[]
for name,(lm,sm) in HYP.items():
    for side,mask in ((1,lm),(-1,sm)):
        ev=[int(i) for i in idx[mask] if i<split_i]
        cidx,unm=S.matched_controls(ev,hour,volb,n_per_event=1,seed=101,min_spacing_idx=HORIZON_BARS)
        for tgt,stp in CELLS:
            e=rate_for(ev,tgt,stp,side); c=rate_for(cidx,tgt,stp,side)
            if not e or not c: continue
            se=math.sqrt(e["rate"]*(1-e["rate"])/e["effective_n"]+c["rate"]*(1-c["rate"])/c["effective_n"])
            z=(e["rate"]-c["rate"])/se
            row={"hypothesis":name,"side":"long" if side==1 else "short","cell":f"{tgt}:{stp}",
                 "event_rate":e["rate"],"event_effN":e["effective_n"],
                 "control_rate":c["rate"],"control_effN":c["effective_n"],
                 "unmatched_events":len(unm),"edge_vs_control":e["rate"]-c["rate"],
                 "z":z,"significant":bool(abs(z)>ZC)}
            ctrl_rows.append(row)
            print(f"  {name:30s} {row['side']:5s} {tgt}:{stp} event={e['rate']:.4f} "
                  f"control={c['rate']:.4f} edge={row['edge_vs_control']:+.4f} z={z:+.2f} "
                  f"{'SIG' if row['significant'] else '-'} unmatched={len(unm)}")

print("\n===== A3 SEALED SET - UNLOCKING ONCE =====")
seal=G.SealedSplit(split_ts, ledger=G.STATE/"phase2_seal.json")
print(f"  seal spent before unlock? {seal.spent()}")
seal.unlock("phase2-batch-6cells","4398d74521a633df02dada34115134a21d48716253de3ae0f235754bb4030885")
print("  UNLOCKED. This seal is now SPENT and may never confirm another candidate.")
conf_rows=[]
for name,(lm,sm) in HYP.items():
    for side,mask in ((1,lm),(-1,sm)):
        evc=[int(i) for i in idx[mask] if i>=split_i]
        for tgt,stp in CELLS:
            c=rate_for(evc,tgt,stp,side)
            if not c: continue
            conf_rows.append({"hypothesis":name,"side":"long" if side==1 else "short",
                              "cell":f"{tgt}:{stp}",**c})
            print(f"  {name:30s} {'long' if side==1 else 'short':5s} {tgt}:{stp} "
                  f"effN={c['effective_n']:5d} rate={c['rate']:.4f}")
json.dump({"alpha":ALPHA,"z_critical":ZC,"control_discovery":ctrl_rows,
           "confirmation":conf_rows,"seal_split_ts":split_ts},
          open("receipts/cp_phase2_confirm.json","w"),indent=2)
print("\n  written -> receipts/cp_phase2_confirm.json")
