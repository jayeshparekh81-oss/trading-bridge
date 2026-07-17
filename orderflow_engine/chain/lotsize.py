"""Authoritative contract (lot) size, resolved from the scrip master's SEM_LOT_UNITS.

ROOT FIX (2026-07-17) for the lot-size mismatch. The hardcoded ``chain.config``
``contract_size`` dict was wrong for 4 of 5 index futures — NIFTY 75 vs 65, BANKNIFTY
35 vs 30, FINNIFTY 65 vs 60, MIDCPNIFTY 140 vs 120 (only SENSEX 20 correct) — so every
``net_gex`` MAGNITUDE was inflated ~8-17%. SEM_LOT_UNITS is the exchange's own lot for
the actual recorded contract, so reading it (a) kills the whole class of error and
(b) survives contract rolls automatically. Only the GEX magnitude was ever affected:
net_gex SIGN, gamma_flip LEVEL, max_pain, PCR, IV and greeks are all scale-invariant
or lot-free (proven in tests/chain/test_gex.py).

The config dict remains ONLY as a loud last-resort fallback (see ChainEngine.contract_size).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from recorder.scrip_master import load_rows, resolve_future

# SENSEX is a BSE product; every other index future is on NSE.
_EXCH_BY_INDEX = {"SENSEX": "BSE"}


def resolve_lot_by_index(rows: list[dict], ref_date: date,
                         indices: list[str]) -> dict[str, int]:
    """{index -> lot} from the scrip master's front non-expired future per index.

    Indices whose future cannot be resolved are OMITTED (the caller then falls back
    to the config default, loudly). Reuses the tested ``resolve_future`` resolver.
    """
    out: dict[str, int] = {}
    for idx in indices:
        try:
            inst = resolve_future(rows, ref_date, underlying=idx,
                                  exch=_EXCH_BY_INDEX.get(idx, "NSE"),
                                  symbol=f"{idx}_FUT")
        except LookupError:
            continue
        if inst.lot_size:
            out[idx] = int(inst.lot_size)
    return out


def load_lot_by_index(cache_dir: str | Path, ref_date: date,
                      indices: list[str]) -> dict[str, int]:
    """Load the dated scrip master from ``cache_dir`` and resolve lots.

    Returns {} if the scrip master for ``ref_date`` is absent — the caller treats an
    empty map as "fall back to config, loudly", never as "lot 0".
    """
    csv = Path(cache_dir) / f"api-scrip-master-{ref_date.isoformat()}.csv"
    if not csv.exists():
        return {}
    return resolve_lot_by_index(load_rows(csv), ref_date, indices)
