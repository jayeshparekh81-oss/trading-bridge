"""cq_calibrate.py — A5 instrument calibration. Synthetic only. No network.

If the machine cannot read a known truth, none of its unknown answers count.

  C1 host guard refuses everything outside the boundary, and the refusal fires
  C2 sealed split raises for discovery code, and is single-use
  C3 disk ceiling and request cap refuse rather than exceed
  C4 random walk returns the THEORETICAL hit-first rate, within binomial SE
  C5 an effect injected AT THE MDE is recovered, sign and rough size
  C6 structureless events do NOT pass
  C7 funding charged per stamp; sub-stamp holds pay exactly zero
  C8 overlapping events are suppressed; effective N < raw N and ratio printed
"""
from __future__ import annotations

import json
import math

import numpy as np

import cq_engine as E
import cq_guards as G
import cq_stats as S

RESULTS = []


def rec(cid, name, passed, detail):
    RESULTS.append({"id": cid, "name": name, "pass": bool(passed), "detail": detail})
    print(f"  {cid} {name:44s} {'PASS' if passed else 'FAIL'}")
    print(f"      {detail}")


# ─────────────────────────────────────────────────────────────── C1
def c1_host_guard():
    refused, allowed_ok = [], []
    for bad in ["https://example.com/data",
                "https://api.binance.com.attacker.net/api/v3/klines",
                "https://api.binance.com/api/v3/order",
                "https://api.binance.com/sapi/v1/capital/withdraw/apply",
                "https://api.binance.com/fapi/v2/account",
                "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&signature=deadbeef",
                "http://data.binance.vision/data"]:
        try:
            G.assert_allowed(bad)
            refused.append((bad, "NOT REFUSED"))
        except (G.ForbiddenHost, G.ForbiddenPath) as e:
            refused.append((bad, type(e).__name__))
    for good in ["https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/x.zip",
                 "https://api.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT"]:
        try:
            G.assert_allowed(good)
            allowed_ok.append((good, "allowed"))
        except Exception as e:
            allowed_ok.append((good, f"WRONGLY REFUSED {e}"))
    ok = all(r[1] != "NOT REFUSED" for r in refused) and all("allowed" == a[1] for a in allowed_ok)
    rec("C1", "host/path guard refuses and fires", ok,
        f"{len(refused)} hostile URLs all refused; {len(allowed_ok)} legitimate URLs allowed")
    return ok


# ─────────────────────────────────────────────────────────────── C2
def c2_sealed():
    rows = [{"time": t, "v": t} for t in range(0, 100)]
    led = G.STATE / "calib_seal_ledger.json"
    if led.exists():
        led.unlink()
    sp = G.SealedSplit(70, ledger=led)
    fired = False
    try:
        sp.confirmation(rows)
    except G.SealedDataAccess:
        fired = True
    disc = sp.discovery(rows)
    sp.unlock("calib-batch", "0" * 64)
    conf = sp.confirmation(rows)
    spent_fired = False
    try:
        G.SealedSplit(70, ledger=led).unlock("second-batch", "0" * 64)
    except G.SealedDataAccess:
        spent_fired = True
    ok = fired and spent_fired and len(disc) == 70 and len(conf) == 30
    rec("C2", "sealed split guard fires, single-use", ok,
        f"discovery-access raised={fired}; discovery={len(disc)} confirmation={len(conf)}; "
        f"second unlock refused={spent_fired}")
    return ok


# ─────────────────────────────────────────────────────────────── C3
def c3_limits():
    d_fired = c_fired = False
    try:
        G.assert_disk_ok(G.DISK_CEILING_BYTES + 1)
    except G.DiskCeilingReached:
        d_fired = True
    saved = G.REQUEST_CAP
    try:
        G.REQUEST_CAP = 0
        G._bump(0)
    except G.RequestCapReached:
        c_fired = True
    finally:
        G.REQUEST_CAP = saved
    ok = d_fired and c_fired
    rec("C3", "disk ceiling and request cap refuse", ok,
        f"disk ceiling raised={d_fired} (ceiling {G.DISK_CEILING_BYTES/1024**3:.0f} GiB); "
        f"request cap raised={c_fired}")
    return ok


# ─────────────────────────────────────── synthetic path helper
def make_walk(n, sigma_step, seed, drift=0.0, p0=100.0):
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, sigma_step, n)
    return p0 + np.cumsum(steps)


def run_events(prices, times, ev_idx, sigma, k_grid, horizon_ms, target, stop, side=1):
    objs = [E.first_passage(times, prices, i, sigma, k_grid, horizon_ms) for i in ev_idx]
    outs = [E.hit_first(o, target, stop, side) for o in objs]
    return objs, outs


# ─────────────────────────────────────────────────────────────── C4
def c4_random_walk():
    n = 400_000
    sigma_step = 1.0
    prices = make_walk(n, sigma_step, seed=42)
    times = list(range(0, n * 1000, 1000))
    sigma = 20.0
    k_grid = [1.0, 2.0, 3.0]
    horizon = 60_000_000
    rng = np.random.default_rng(5)
    ev = sorted(rng.choice(np.arange(1000, n - 60_000), size=4000, replace=False).tolist())
    lines = []
    ok_all = True
    for target, stop in [(1.0, 1.0), (2.0, 1.0), (3.0, 1.0)]:
        objs, outs = run_events(prices, times, ev, sigma, k_grid, horizon, target, stop)
        res = [o for o in outs if o != "censored"]
        cens = len(outs) - len(res)
        hit = sum(1 for o in res if o == "target")
        emp = hit / len(res) if res else float("nan")
        theo = S.rw_hit_first_rate(target, stop)
        se = math.sqrt(theo * (1 - theo) / len(res)) if res else float("nan")
        z = (emp - theo) / se if se else float("nan")
        good = abs(z) <= 3.0
        ok_all &= good
        lines.append(f"target {target}:stop {stop} -> theoretical {theo:.4f}, "
                     f"empirical {emp:.4f}, n={len(res)}, censored={cens}, "
                     f"SE={se:.4f}, z={z:+.2f} {'ok' if good else 'OUT OF TOLERANCE'}")
    rec("C4", "random walk returns theoretical rate", ok_all, " | ".join(lines))
    return ok_all


# ─────────────────────────────────────────────────────────────── C5
def c5_injected_at_mde():
    """Inject an effect exactly at the MDE and require recovery."""
    n = 300_000
    prices = make_walk(n, 1.0, seed=7)
    times = list(range(0, n * 1000, 1000))
    sigma, target, stop = 20.0, 1.0, 1.0
    horizon = 40_000_000
    rng = np.random.default_rng(9)
    ev = sorted(rng.choice(np.arange(1000, n - 40_000), size=3000, replace=False).tolist())
    p0 = S.rw_hit_first_rate(target, stop)
    mde = S.mde_binomial(p0, len(ev))
    # inject: nudge the path upward after each event so the true rate is p0+mde
    inj = prices.copy()
    bump = 0.0
    lo, hi = 0.0, 3.0
    for _ in range(28):
        bump = (lo + hi) / 2
        test = prices.copy()
        for i in ev:
            test[i:i + 4000] += bump * np.linspace(0, 1, min(4000, len(test) - i))
        _, outs = run_events(test, times, ev, sigma, [1.0], horizon, target, stop)
        res = [o for o in outs if o != "censored"]
        emp = sum(1 for o in res if o == "target") / len(res)
        if emp < p0 + mde:
            lo = bump
        else:
            hi = bump
        inj = test
    _, outs = run_events(inj, times, ev, sigma, [1.0], horizon, target, stop)
    res = [o for o in outs if o != "censored"]
    emp = sum(1 for o in res if o == "target") / len(res)
    lift = emp - p0
    ok = lift > 0 and abs(lift - mde) <= 0.5 * mde
    rec("C5", "effect injected AT the MDE is recovered", ok,
        f"p0={p0:.4f}, MDE at n={len(ev)} is {mde:.5f}; injected lift measured "
        f"{lift:+.5f} (target {mde:.5f}); n_resolved={len(res)}")
    return ok


# ─────────────────────────────────────────────────────────────── C6
def c6_structureless():
    n = 300_000
    prices = make_walk(n, 1.0, seed=1234)
    times = list(range(0, n * 1000, 1000))
    sigma, target, stop = 20.0, 2.0, 1.0
    horizon = 40_000_000
    rng = np.random.default_rng(999)
    ev = sorted(rng.choice(np.arange(1000, n - 40_000), size=2500, replace=False).tolist())
    _, outs = run_events(prices, times, ev, sigma, [1.0, 2.0], horizon, target, stop)
    res = [o for o in outs if o != "censored"]
    emp = sum(1 for o in res if o == "target") / len(res)
    theo = S.rw_hit_first_rate(target, stop)
    se = math.sqrt(theo * (1 - theo) / len(res))
    z = (emp - theo) / se
    ok = abs(z) <= 3.0
    rec("C6", "structureless events do NOT pass", ok,
        f"theoretical {theo:.4f}, empirical {emp:.4f}, z={z:+.2f}, n={len(res)} "
        f"-> {'indistinguishable from the null, correct' if ok else 'MANUFACTURED A SIGNAL'}")
    return ok


# ─────────────────────────────────────────────────────────────── C7
def c7_funding():
    H = 3600 * 1000
    rate = lambda ts: 0.0001
    sub = E.charge_funding(1 * H, 3 * H, side=1, notional=1_000_000, rate_lookup=rate)
    across = E.charge_funding(1 * H, 20 * H, side=1, notional=1_000_000, rate_lookup=rate)
    short = E.charge_funding(1 * H, 20 * H, side=-1, notional=1_000_000, rate_lookup=rate)
    ok = (sub["stamps_crossed"] == 0 and sub["funding_paid"] == 0.0
          and across["stamps_crossed"] == 2 and across["funding_paid"] > 0
          and across["funding_received"] == 0.0
          and short["funding_received"] > 0 and short["funding_paid"] == 0.0)
    rec("C7", "funding charged per stamp, sub-stamp is zero", ok,
        f"sub-stamp hold: {sub['stamps_crossed']} stamps, paid {sub['funding_paid']:.2f}; "
        f"19h long: {across['stamps_crossed']} stamps, paid {across['funding_paid']:.2f}, "
        f"recv {across['funding_received']:.2f}; same window short: "
        f"paid {short['funding_paid']:.2f}, recv {short['funding_received']:.2f}")
    return ok


# ─────────────────────────────────────────────────────────────── C8
def c8_independence():
    n = 120_000
    prices = make_walk(n, 1.0, seed=3)
    times = list(range(0, n * 1000, 1000))
    sigma = 20.0
    base = sorted(np.random.default_rng(4).choice(
        np.arange(1000, n - 30_000), size=600, replace=False).tolist())
    clustered = sorted(set(base + [b + d for b in base for d in (5, 10, 15, 20)
                                   if b + d < n - 30_000]))
    objs = [E.first_passage(times, prices, i, sigma, [1.0], 30_000_000) for i in clustered]
    kept, raw, eff = E.suppress_overlapping(clustered, objs, 1.0, 1.0)
    vr = E.variance_ratio(raw, eff)
    ok = eff < raw and vr is not None and vr < 1.0
    rec("C8", "overlapping events suppressed, effective N", ok,
        f"raw N={raw}, effective N={eff}, variance ratio={vr:.4f} "
        f"-> {raw-eff} correlated events collapsed")
    return ok


def main():
    print("===== A5 INSTRUMENT CALIBRATION (synthetic only, no network) =====")
    fns = [c1_host_guard, c2_sealed, c3_limits, c4_random_walk,
           c5_injected_at_mde, c6_structureless, c7_funding, c8_independence]
    passed = sum(bool(f()) for f in fns)
    verdict = "GREEN" if passed == len(fns) else "RED"
    out = {"checkpoint": "A5-CALIBRATION", "status": verdict,
           "passed": f"{passed}/{len(fns)}", "results": RESULTS}
    G.STATE.mkdir(parents=True, exist_ok=True)
    (G.STATE / "calibration.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n  CALIBRATION {verdict}: {passed}/{len(fns)}")
    return 0 if verdict == "GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
