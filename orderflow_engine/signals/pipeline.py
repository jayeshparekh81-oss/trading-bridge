"""Composite pipeline (Module R6) — one replay pass feeding R3+R4+R5+R6.

MultiConsumer fans the consumer contract out to [tape, levels, chain, signal] in
order, so the SignalEngine sees each packet only after R3/R4/R5 have updated.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from chain.config import load_chain_config
from chain.engine import ChainEngine
from chain.lotsize import load_lot_by_index
from chain.symbols import parse_symbol
from levels.config import load_levels_config
from levels.engine import LevelsEngine
from tape.config import load_tape_config
from tape.engine import TapeEngine

from signals.config import SignalConfig
from signals.engine import SignalEngine
from signals.events import load_events


class MultiConsumer:
    def __init__(self, consumers: list):
        self.consumers = consumers

    def on_packet(self, parsed, ts):
        for c in self.consumers:
            c.on_packet(parsed, ts)

    def on_depth(self, parsed, ts):
        for c in self.consumers:
            c.on_depth(parsed, ts)

    def on_event(self, kind, detail, value_num):
        for c in self.consumers:
            c.on_event(kind, detail, value_num)


def build_meta(day_dir: Path) -> dict[int, dict]:
    """sid -> {symbol, kind, index, right, strike, expiry} for every instrument."""
    mf = day_dir / "manifest.json"
    meta: dict[int, dict] = {}
    if not mf.exists():
        return meta
    for e in json.loads(mf.read_text()).get("instruments", []):
        p = parse_symbol(e["symbol"])
        meta[int(e["security_id"])] = {
            "symbol": e["symbol"], "kind": p.kind, "index": p.index,
            "right": p.right, "strike": p.strike, "expiry": e.get("expiry", ""),
        }
    return meta


def build_pipeline(day_dir: Path, signal_cfg: SignalConfig | None = None, *,
                   config_path=None, sides=("long", "short")):
    day_dir = Path(day_dir)
    session_date = date.fromisoformat(day_dir.name)
    meta = build_meta(day_dir)
    sym_by_id = {sid: m["symbol"] for sid, m in meta.items()}
    chain_meta = {sid: m for sid, m in meta.items()
                  if m["kind"] in ("spot", "future", "option")}

    tape = TapeEngine(load_tape_config(config_path), sym_by_id)
    levels = LevelsEngine(load_levels_config(config_path), sym_by_id, date=day_dir.name)
    # Authoritative lot per index from the dated scrip master (same source as chain.run).
    indices = sorted({m["index"] for m in chain_meta.values() if m.get("index")})
    lot_by_index = load_lot_by_index(Path(__file__).resolve().parent.parent / "cache",
                                     session_date, indices)
    chain = ChainEngine(load_chain_config(config_path), chain_meta, session_date,
                        lot_by_index=lot_by_index)
    scfg = signal_cfg or SignalConfig({})
    sig = SignalEngine(scfg, tape, levels, chain, meta, session_date,
                       events=load_events(), sides=sides)
    multi = MultiConsumer([tape, levels, chain, sig])
    return multi, {"tape": tape, "levels": levels, "chain": chain, "signal": sig, "meta": meta}
