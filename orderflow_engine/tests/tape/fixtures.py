"""Synthetic builders for tape-engine tests (pure dicts; no recorder runtime)."""

from __future__ import annotations

from recorder.depth_schema import SIDE_ASK, SIDE_BID


def tick(ts_ns: int, volume: int, ltp: float, *, ltq: int = 0,
         bid: float | None = None, ask: float | None = None, sid: int = 1) -> dict:
    """A parsed tick row as the replayer would deliver it to on_packet."""
    return {"is_tick": True, "security_id": sid, "ts_recv_ns": ts_ns, "ltp": ltp,
            "ltq": ltq, "volume": volume, "bid_price_1": bid, "ask_price_1": ask}


def depth_row(sid: int, side: int, qtys: list[int], prices: list[float] | None = None) -> dict:
    """A parsed 20-depth side-tagged row (qtys[i] -> qty_{i+1})."""
    row = {"is_depth": True, "security_id": sid, "side": side}
    for i, q in enumerate(qtys, start=1):
        row[f"qty_{i}"] = q
        row[f"price_{i}"] = (prices[i - 1] if prices else 100.0 - i)
        row[f"orders_{i}"] = 1
    return row
