"""LevelRegistry (Module R4) — one queryable map per instrument/day.

Holds every reference level {type, price, metadata} plus non-price context (gap,
etc.). ``distance_to_nearest`` is the primary call R6 will make to score where the
current price sits relative to the map. Serializable to a parquet row set.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Level:
    level_type: str
    price: float
    metadata: dict = field(default_factory=dict)


class LevelRegistry:
    def __init__(self, security_id: int, symbol: str, date: str):
        self.security_id = security_id
        self.symbol = symbol
        self.date = date
        self._levels: list[Level] = []
        self.context: dict = {}

    def add(self, level_type: str, price: float, metadata: dict | None = None) -> None:
        if price is None:
            return
        self._levels.append(Level(level_type, float(price), metadata or {}))

    def add_many(self, type_price: dict, metadata: dict | None = None) -> None:
        for t, p in type_price.items():
            self.add(t, p, metadata)

    def set_context(self, key: str, value) -> None:
        self.context[key] = value

    def levels(self, types: list[str] | None = None) -> list[Level]:
        if types is None:
            return list(self._levels)
        want = set(types)
        return [l for l in self._levels if l.level_type in want]

    def distance_to_nearest(self, price: float, types: list[str] | None = None) -> dict | None:
        """Nearest level to ``price``. ``signed_distance`` = level.price - price
        (positive => the level sits ABOVE current price). None if no levels."""
        cands = self.levels(types)
        if not cands:
            return None
        nearest = min(cands, key=lambda l: abs(l.price - price))
        return {
            "level_type": nearest.level_type,
            "level_price": nearest.price,
            "signed_distance": nearest.price - price,
            "abs_distance": abs(nearest.price - price),
        }

    def to_rows(self) -> list[dict]:
        return [{
            "security_id": self.security_id, "symbol": self.symbol, "date": self.date,
            "level_type": l.level_type, "price": l.price,
            "metadata": json.dumps(l.metadata, default=str) if l.metadata else "",
        } for l in sorted(self._levels, key=lambda x: x.price)]
