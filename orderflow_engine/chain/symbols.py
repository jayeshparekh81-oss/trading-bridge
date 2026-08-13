"""Parse recorded instrument symbols into option-chain coordinates (Module R5).

Recorder symbols: options ``{INDEX}_{CE|PE}_{STRIKE}`` (e.g. NIFTY_CE_23700),
spot ``{INDEX}_SPOT``, future ``{INDEX}_FUT``. Index names are single tokens
(NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY, SENSEX).
"""

from __future__ import annotations

from dataclasses import dataclass

CALL = "CE"
PUT = "PE"


@dataclass
class Parsed:
    kind: str            # "option" | "spot" | "future" | "other"
    index: str | None = None
    right: str | None = None      # CE | PE
    strike: int | None = None


def parse_symbol(symbol: str) -> Parsed:
    s = symbol or ""
    parts = s.split("_")
    if len(parts) >= 3 and parts[-2] in (CALL, PUT):
        try:
            return Parsed("option", index="_".join(parts[:-2]),
                          right=parts[-2], strike=int(parts[-1]))
        except ValueError:
            return Parsed("other")
    if s.endswith("_SPOT"):
        return Parsed("spot", index=s[:-len("_SPOT")])
    if s.endswith("_FUT"):
        return Parsed("future", index=s[:-len("_FUT")])
    return Parsed("other")
