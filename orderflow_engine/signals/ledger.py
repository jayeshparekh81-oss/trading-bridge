"""R8 trade ledger + running account equity + TCA (I3). This is what G2 reads.

Per closed trade it records lots, ₹ risked, gross R, cost_r, net R, the ₹ P&L, the running
equity, and a per-trade TCA breakdown (cost attribution — where the money went). Both gross
and net are kept, never one replacing the other.

₹ consistency: risk_inr = lots × stop_pts × delta × lot_size (the ₹ actually risked, = 1R in
rupees). gross_inr = gross_r × risk_inr; cost_inr = cost_r × risk_inr; net_inr = gross − cost.
(cost_r × risk_inr reduces exactly to lots × option-point-cost × lot_size — the true ₹ cost.)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LedgerEntry:
    ts_ns: int
    instrument: str
    side: str
    lots: int
    stop_pts: float
    delta: float
    lot_size: int
    risk_inr: float              # ₹ risked = 1R in rupees
    gross_r: float
    cost_r: float
    net_r: float
    gross_inr: float
    cost_inr: float
    net_inr: float
    equity_before_inr: float
    equity_after_inr: float
    tca: dict = field(default_factory=dict)   # ₹ cost attribution (scaled to `lots`)


class Ledger:
    def __init__(self, starting_equity_inr: float):
        self.starting_equity_inr = float(starting_equity_inr)
        self.equity_inr = float(starting_equity_inr)
        self.entries: list[LedgerEntry] = []

    def record(self, *, ts_ns: int, instrument: str, side: str, lots: int, stop_pts: float,
               delta: float, lot_size: int, gross_r: float, cost_r: float,
               tca_per_lot: dict | None = None) -> LedgerEntry:
        risk_inr = lots * stop_pts * delta * lot_size
        net_r = gross_r - cost_r
        gross_inr = gross_r * risk_inr
        cost_inr = cost_r * risk_inr
        net_inr = gross_inr - cost_inr
        before = self.equity_inr
        self.equity_inr = before + net_inr
        tca = {k: round(v * lots, 2) for k, v in (tca_per_lot or {}).items()}
        e = LedgerEntry(ts_ns=ts_ns, instrument=instrument, side=side, lots=lots,
                        stop_pts=stop_pts, delta=delta, lot_size=lot_size, risk_inr=risk_inr,
                        gross_r=gross_r, cost_r=cost_r, net_r=net_r, gross_inr=gross_inr,
                        cost_inr=cost_inr, net_inr=net_inr, equity_before_inr=before,
                        equity_after_inr=self.equity_inr, tca=tca)
        self.entries.append(e)
        return e

    def summary(self) -> dict:
        """The G2-facing roll-up: net-of-cost PF (the actual gate), gross vs net, equity."""
        gains = sum(e.net_inr for e in self.entries if e.net_inr > 0)
        losses = -sum(e.net_inr for e in self.entries if e.net_inr < 0)
        pf = (gains / losses) if losses > 0 else (float("inf") if gains > 0 else 0.0)
        return {
            "trades": len(self.entries),
            "starting_equity_inr": self.starting_equity_inr,
            "equity_inr": round(self.equity_inr, 2),
            "net_inr": round(self.equity_inr - self.starting_equity_inr, 2),
            "profit_factor_net": pf,                       # G2's "PF >= 1.5 AFTER costs"
            "gross_r": round(sum(e.gross_r for e in self.entries), 4),
            "net_r": round(sum(e.net_r for e in self.entries), 4),
            "cost_r": round(sum(e.cost_r for e in self.entries), 4),
            "cost_inr": round(sum(e.cost_inr for e in self.entries), 2),
        }
