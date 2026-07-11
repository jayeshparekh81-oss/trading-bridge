"""Depth imbalance + book OFI (Module R3) — INTERFACES + pure functions.

R1's 20-level depth arrives Monday; these are the pure, unit-testable primitives
the calibrated signals will use. Depth rows are SIDE-TAGGED (one row = one side's
20 levels), so the engine assembles the latest bid-row + ask-row per instrument
and calls these.

queue_imbalance is a normalized ratio in [-1, 1] (positive = bid-heavy). book_ofi
is the standard L1 order-flow-imbalance increment (Cont/Kukanov/Stoikov) between
two consecutive book snapshots. Both are STRUCTURALLY correct but their thresholds
/ weights are UNCALIBRATED — see TAPE_NOTES.md and depth.ofi_enabled (off default).
"""

from __future__ import annotations

from typing import Optional, Sequence


def _side_qtys(row: dict, levels: int) -> list[int]:
    return [int(row.get(f"qty_{i}") or 0) for i in range(1, levels + 1)]


def _side_prices(row: dict, levels: int) -> list[float]:
    return [float(row.get(f"price_{i}") or 0.0) for i in range(1, levels + 1)]


def queue_imbalance(bid_qtys: Sequence[int], ask_qtys: Sequence[int],
                    levels: int = 5) -> Optional[float]:
    """(bid - ask) / (bid + ask) over the top ``levels``; None if the book is empty."""
    b = sum(int(q) for q in list(bid_qtys)[:levels])
    a = sum(int(q) for q in list(ask_qtys)[:levels])
    total = b + a
    if total == 0:
        return None
    return (b - a) / total


def queue_imbalance_rows(bid_row: dict, ask_row: dict, levels: int = 5) -> Optional[float]:
    """Convenience: compute imbalance from two side-tagged depth rows."""
    if bid_row is None or ask_row is None:
        return None
    return queue_imbalance(_side_qtys(bid_row, levels), _side_qtys(ask_row, levels), levels)


def book_ofi(prev_bid: dict, prev_ask: dict, curr_bid: dict, curr_ask: dict) -> Optional[float]:
    """L1 order-flow imbalance between two book snapshots (Cont et al.).

    e = ΔBidQty(if bid px unchanged/up) − ΔAskQty(if ask px unchanged/down), with
    full add/cancel on a price move. TODO-CALIBRATION: sign conventions verified,
    but scaling/aggregation weights across levels are UNCALIBRATED (real depth
    Monday). Returns None if any snapshot is missing.
    """
    if not all((prev_bid, prev_ask, curr_bid, curr_ask)):
        return None
    pbp, pbq = float(prev_bid.get("price_1") or 0), int(prev_bid.get("qty_1") or 0)
    cbp, cbq = float(curr_bid.get("price_1") or 0), int(curr_bid.get("qty_1") or 0)
    pap, paq = float(prev_ask.get("price_1") or 0), int(prev_ask.get("qty_1") or 0)
    cap, caq = float(curr_ask.get("price_1") or 0), int(curr_ask.get("qty_1") or 0)
    # bid contribution
    if cbp > pbp:
        d_bid = cbq
    elif cbp < pbp:
        d_bid = -pbq
    else:
        d_bid = cbq - pbq
    # ask contribution
    if cap < pap:
        d_ask = caq
    elif cap > pap:
        d_ask = -paq
    else:
        d_ask = caq - paq
    return float(d_bid - d_ask)
