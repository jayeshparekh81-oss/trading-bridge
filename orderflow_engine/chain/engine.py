"""ChainEngine (Module R5) — replayer Consumer building per-index chain analytics.

From the merged replay stream it tracks each index's last spot + future and every
strike's OI/volume/price, and at a cadence (60s grid + on-demand at R3
big-print/velocity-spike timestamps, or per-tick when interval=0) snapshots each
chain — computing OFFLINE IV/Greeks from the contemporaneous spot (with a
staleness flag). finalize() derives PCR / max-pain / ATM-IV / net-GEX / flip /
basis / buildup per index. Deterministic.
"""

from __future__ import annotations

import logging
from datetime import date

from chain import analytics, gex
from chain.bsm import greeks, implied_vol
from chain.buildup import classify_buildup
from chain.config import ChainConfig
from chain.state import ChainState

log = logging.getLogger("chain.engine")


def _time_to_expiry_years(expiry: str, session_date: date, day_count: int) -> float:
    try:
        exp = date.fromisoformat(expiry)
    except (ValueError, TypeError):
        return 0.0
    days = (exp - session_date).days
    if days < 0:
        return 0.0
    if days == 0:
        return 0.5 / day_count      # expiry day: half-day floor so BSM doesn't degenerate
    return days / day_count


class ChainEngine:
    def __init__(self, config: ChainConfig, meta_by_id: dict[int, dict],
                 session_date: date, event_triggers: dict[str, list[int]] | None = None):
        self.cfg = config
        self.meta = meta_by_id
        self.session_date = session_date
        self.windows = config.delta_oi_windows_s
        self.triggers = {k: sorted(v) for k, v in (event_triggers or {}).items()}
        self._tptr: dict[str, int] = {k: 0 for k in self.triggers}
        self.chains: dict[str, ChainState] = {}
        self.spot: dict[str, tuple[float, int]] = {}
        self.fut: dict[str, tuple[float, int]] = {}
        self._proxy_warned: set[str] = set()
        self.rows: list[dict] = []
        self._first: dict[tuple, tuple] = {}   # (index,expiry,right,strike)->(oi,ltp) first grid
        self._last: dict[tuple, tuple] = {}
        self._next_grid: int | None = None
        self._last_ts: int | None = None
        self.counts = {"ticks": 0, "trades": 0, "depth": 0, "events": 0, "snapshots": 0}

    def _chain(self, index: str) -> ChainState:
        c = self.chains.get(index)
        if c is None:
            c = ChainState(index, self.windows)
            self.chains[index] = c
        return c

    # -- consumer contract ---------------------------------------------------
    def on_packet(self, parsed: dict, ts: int) -> None:
        if not parsed.get("is_tick"):
            return
        self.counts["ticks"] += 1
        sid = parsed.get("security_id")
        meta = self.meta.get(sid)
        if meta is None:
            return
        self._last_ts = ts
        index = meta["index"]
        ltp = parsed.get("ltp")
        if meta["kind"] == "spot":
            if ltp is not None:
                self.spot[index] = (float(ltp), ts)
        elif meta["kind"] == "future":
            if ltp is not None:
                self.fut[index] = (float(ltp), ts)
        elif meta["kind"] == "option":
            self._chain(index).update(meta["expiry"], meta["right"], meta["strike"],
                                      ts, parsed.get("oi"), parsed.get("volume"), ltp)

        interval = self.cfg.snapshot_interval_ns
        if interval <= 0:
            self._snapshot(index, ts, "tick")
        else:
            if self._next_grid is None:
                self._next_grid = ts + interval
            elif ts >= self._next_grid:
                for idx in list(self.chains):
                    self._snapshot(idx, ts, "grid")
                while self._next_grid <= ts:
                    self._next_grid += interval
        self._fire_events(index, ts)

    def _fire_events(self, index: str, ts: int) -> None:
        trig = self.triggers.get(index)
        if not trig:
            return
        i = self._tptr[index]
        fired = False
        while i < len(trig) and ts >= trig[i]:
            fired = True
            i += 1
        self._tptr[index] = i
        if fired:
            self._snapshot(index, ts, "event")

    def on_depth(self, parsed: dict, ts: int) -> None:
        self.counts["depth"] += 1

    def on_event(self, kind, detail, value_num) -> None:
        self.counts["events"] += 1

    def _effective_spot(self, index: str) -> tuple:
        """(price, source_ts, source) for IV/greeks. GLASS BOX: when the real
        spot never ticked (2026-07-13 finding: IDX_I delivered zero packets) and
        chain.spot_proxy == 'future_fallback', the index FUTURE's price is used
        as a spot-proxy — WARNED once per index and marked in the summary as
        spot_source='future_proxy', never silently. 'strict' restores the old
        behavior (no spot -> no IV). Proxy IV carries a basis offset — see
        TAPE_NOTES. The IDX_I subscription root-fix is a separate R0 task."""
        sp = self.spot.get(index)
        if sp is not None:
            return sp[0], sp[1], "spot"
        if self.cfg.spot_proxy == "future_fallback":
            ft = self.fut.get(index)
            if ft is not None:
                if index not in self._proxy_warned:
                    log.warning("chain: %s spot missing — using FUTURE price as "
                                "spot-proxy for IV/greeks (basis-offset bias; "
                                "see TAPE_NOTES)", index)
                    self._proxy_warned.add(index)
                return ft[0], ft[1], "future_proxy"
        return None, 0, "none"

    # -- snapshot ------------------------------------------------------------
    def _snapshot(self, index: str, ts: int, trigger: str) -> None:
        chain = self.chains.get(index)
        if chain is None:
            return
        spot_val, src_ts, _src = self._effective_spot(index)
        spot_stale = spot_val is None or (ts - src_ts) > self.cfg.spot_staleness_ns
        r = self.cfg.risk_free_rate
        self.counts["snapshots"] += 1
        for row in chain.snapshot(ts):
            expiry, right, strike = row["expiry"], row["right"], row["strike"]
            T = _time_to_expiry_years(expiry, self.session_date, self.cfg.day_count)
            iv = g = None
            if spot_val and row["ltp"]:
                iv = implied_vol(row["ltp"], spot_val, strike, T, r, right)
                if iv is not None:
                    g = greeks(spot_val, strike, T, r, iv, right)
            dws = [row.get(f"doi_{w}s") for w in self.windows] + [None, None, None]
            out = {
                "snapshot_ts_ns": ts, "index": index, "trigger": trigger,
                "expiry": expiry, "right": right, "strike": strike,
                "oi": row["oi"], "doi_w1": dws[0], "doi_w2": dws[1], "doi_w3": dws[2],
                "volume": row["volume"], "ltp": row["ltp"],
                "spot": spot_val, "spot_stale": spot_stale, "iv": iv,
                "delta": g["delta"] if g else None, "gamma": g["gamma"] if g else None,
                "vega": g["vega"] if g else None, "theta": g["theta"] if g else None,
            }
            self.rows.append(out)
            key = (index, expiry, right, strike)
            if key not in self._first:
                self._first[key] = (row["oi"], row["ltp"])
            self._last[key] = (row["oi"], row["ltp"])

    def _final_rows(self, index: str) -> list[dict]:
        idx_rows = [r for r in self.rows if r["index"] == index]
        if not idx_rows:
            return []
        last_ts = max(r["snapshot_ts_ns"] for r in idx_rows)
        # Several snapshots can share the last ts (per-tick + forced final); they
        # are identical state, so dedupe to one row per strike to keep sums
        # (net GEX, PCR) from multi-counting.
        dedup: dict[tuple, dict] = {}
        for r in idx_rows:
            if r["snapshot_ts_ns"] == last_ts:
                dedup[(r["expiry"], r["right"], r["strike"])] = r
        return list(dedup.values())

    def finalize(self) -> dict:
        # force a final snapshot so summaries reflect end-of-session state
        if self._last_ts is not None:
            for idx in list(self.chains):
                self._snapshot(idx, self._last_ts, "final")
        per = {}
        for index in sorted(self.chains):
            fr = self._final_rows(index)
            real_spot = self.spot.get(index, (None, None))[0]
            spot, _, spot_source = self._effective_spot(index)   # proxy-aware
            fut = self.fut.get(index, (None, None))[0]
            cs = self.cfg.contract_size(index)
            strikes_with_iv = sum(1 for r in fr if r["iv"] is not None)
            atm_iv = analytics.atm_iv(fr, spot)
            expiries = sorted({r["expiry"] for r in fr})
            days = None
            if expiries:
                days = max(0, (date.fromisoformat(expiries[0]) - self.session_date).days)
            net = gex.net_gex(fr, cs)
            per[index] = {
                "strikes": len({(r["right"], r["strike"]) for r in fr}),
                "strikes_with_iv": strikes_with_iv,
                "spot": spot, "spot_missing": real_spot is None,
                "spot_source": spot_source,     # GLASS BOX: 'spot'|'future_proxy'|'none'
                "pcr_oi": analytics.pcr_oi(fr), "pcr_volume": analytics.pcr_volume(fr),
                "max_pain": analytics.max_pain(fr),
                "atm_strike": analytics.atm_strike(fr, spot) if spot else None,
                "atm_iv": atm_iv,
                "net_gex": net, "gamma_flip": gex.gamma_flip(fr, cs),
                "gex_regime": gex.regime_flag(net, self.cfg.gex_regime_threshold),
                # basis is ONLY honest against a REAL spot — under the proxy it
                # would be trivially ~0 (future vs itself), so it stays None.
                "basis": analytics.basis(fut, real_spot),
                "annualized_basis": analytics.annualized_basis(
                    fut, real_spot, days, self.cfg.day_count) if days else None,
                "buildup_matrix": self._buildup_matrix(index),
                "top_doi_strikes": self._top_doi(fr),
            }
        self._per = per
        return {
            "instruments": len(self.meta), "indices": len(self.chains),
            "counts": dict(self.counts), "windows_s": self.windows,
            "per_index": per, "uncalibrated_knobs": self.cfg.uncalibrated(),
        }

    def _buildup_matrix(self, index: str) -> dict:
        counts: dict[str, int] = {}
        for key, (oi0, p0) in self._first.items():
            if key[0] != index:
                continue
            oi1, p1 = self._last.get(key, (oi0, p0))
            if p0 is None or p1 is None:
                continue
            b = classify_buildup(p0, p1, oi0, oi1,
                                 self.cfg.buildup_price_threshold_pct,
                                 self.cfg.buildup_oi_threshold_pct)
            counts[b.label] = counts.get(b.label, 0) + 1
        return counts

    def _top_doi(self, fr: list[dict], n: int = 5) -> list[dict]:
        ranked = sorted((r for r in fr if r.get("doi_w2") is not None),
                        key=lambda r: abs(r["doi_w2"]), reverse=True)
        return [{"right": r["right"], "strike": r["strike"], "doi_5m": r["doi_w2"],
                 "oi": r["oi"]} for r in ranked[:n]]
