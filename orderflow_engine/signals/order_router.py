"""R8 Order Router — INTERFACE STUB ONLY (2026-07-17).

HARD FENCE. The paper phase touches NO broker path whatsoever. This class exists so the
paper↔live seam is explicit and cannot be crossed by accident — it is NOT wired into the
engine, defaults OFF and read-only, and every mutating call RAISES until an operator both
enables it AND flips it off read-only (which is a deliberate future step, not tonight).

Live-money broker adapters (dhan.py/fyers.py) are NOT imported here and must NOT be — see
the project PRODUCTION SAFETY rules. Wiring a real broker path is a separate, gated task.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrderRouterConfig:
    enabled: bool = False
    mode: str = "readonly"          # 'readonly' | 'live' — 'live' alone still requires enabled

    @classmethod
    def from_dict(cls, d: dict | None) -> "OrderRouterConfig":
        d = d or {}
        return cls(enabled=bool(d.get("enabled", False)), mode=str(d.get("mode", "readonly")))


class OrderRouter:
    """A deliberately-inert placeholder. `place`/`modify`/`cancel` refuse unless live-armed,
    and even then this stub has no broker binding — it never reaches a broker."""

    def __init__(self, cfg: OrderRouterConfig | None = None):
        self.cfg = cfg or OrderRouterConfig()

    def is_live(self) -> bool:
        return bool(self.cfg.enabled) and self.cfg.mode == "live"

    def _refuse(self, action: str):
        raise RuntimeError(
            f"R8 OrderRouter.{action}: paper-phase stub — no broker path is wired, and it is "
            f"{'OFF' if not self.cfg.enabled else self.cfg.mode}. Refusing.")

    def place(self, *_a, **_k):
        self._refuse("place")

    def modify(self, *_a, **_k):
        self._refuse("modify")

    def cancel(self, *_a, **_k):
        self._refuse("cancel")
