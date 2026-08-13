"""Fixtures for chain tests."""

from __future__ import annotations


def opt_tick(ts, sid, oi=None, volume=None, ltp=None):
    return {"is_tick": True, "security_id": sid, "ts_recv_ns": ts,
            "oi": oi, "volume": volume, "ltp": ltp}


def spot_tick(ts, sid, ltp):
    return {"is_tick": True, "security_id": sid, "ts_recv_ns": ts, "ltp": ltp,
            "oi": None, "volume": None}
