"""Pine Script v4.8.1 → TRADETRI native webhook payload mapper.

The production Pine strategy emits a richer payload shape than the native
TRADETRI webhook expects:

    {
      "action": "ENTRY" | "PARTIAL" | "EXIT",
      "type":   "LONG_ENTRY" | "SHORT_ENTRY" |
                "LONG_PARTIAL" | "SHORT_PARTIAL" |
                "LONG_EXIT" | "SHORT_EXIT" |
                "LONG_SL" | "SHORT_SL",
      "qty": 4,
      "indicators": { ... 17 keys ... },
      ...
    }

This module normalises that into the native TRADETRI payload shape so
downstream code (ai validator, executor, position manager) keeps a
single contract. The webhook endpoint detects the Pine format by the
presence of ``type`` with a ``LONG_``/``SHORT_`` prefix.

Phase-1 scope: Future + Options. Cash + multi-broker is Phase-2.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.services.ai_validator import compute_score

if TYPE_CHECKING:
    from app.db.models.strategy import Strategy

#: Pine ``type`` prefixes that identify a Pine payload.
_PINE_TYPE_PREFIXES: tuple[str, ...] = ("LONG_", "SHORT_")

#: Mapping (pine_action, pine_type) -> (tradetri_action, side, side_tag).
#: side_tag is recorded on the mapped payload so downstream can
#: differentiate LONG from SHORT exits/partials without re-parsing type.
_PINE_TO_NATIVE: dict[tuple[str, str], tuple[str, str]] = {
    ("ENTRY", "LONG_ENTRY"): ("BUY", "long"),
    ("ENTRY", "SHORT_ENTRY"): ("SELL", "short"),
    ("PARTIAL", "LONG_PARTIAL"): ("PARTIAL_LONG", "long"),
    ("PARTIAL", "SHORT_PARTIAL"): ("PARTIAL_SHORT", "short"),
    ("EXIT", "LONG_EXIT"): ("EXIT", "long"),
    ("EXIT", "SHORT_EXIT"): ("EXIT", "short"),
    ("EXIT", "LONG_SL"): ("SL_HIT", "long"),
    ("EXIT", "SHORT_SL"): ("SL_HIT", "short"),
}


def is_pine_payload(payload: dict[str, Any]) -> bool:
    """True iff ``payload`` looks like a Pine Script v4.8.1 alert body."""
    pine_type = payload.get("type")
    if not isinstance(pine_type, str):
        return False
    return pine_type.upper().startswith(_PINE_TYPE_PREFIXES)


def map_to_tradetri_payload(
    raw_payload: dict[str, Any],
    strategy: Strategy | None = None,
) -> dict[str, Any]:
    """Translate a Pine payload into the native TRADETRI shape.

    Caller is responsible for HMAC verification and persistence — this
    function only does the field translation. Unknown action/type pairs
    raise :class:`PineMappingError` so the webhook can return a 400.
    """
    if not is_pine_payload(raw_payload):
        raise PineMappingError(
            "payload missing 'type' with LONG_/SHORT_ prefix; cannot map"
        )

    pine_action = str(raw_payload.get("action", "")).strip().upper()
    pine_type = str(raw_payload.get("type", "")).strip().upper()

    mapping = _PINE_TO_NATIVE.get((pine_action, pine_type))
    if mapping is None:
        raise PineMappingError(
            f"unsupported Pine action/type combo: {pine_action}/{pine_type}"
        )
    native_action, side_tag = mapping

    indicators = raw_payload.get("indicators")
    if not isinstance(indicators, dict):
        indicators = {}

    # Score uses the same weighted system the AI validator already runs;
    # keeping the source of truth in one place. SHORT trades use SHORT_W.
    score_side = "SHORT" if side_tag == "short" else "LONG"
    score = compute_score(indicators, score_side)

    quantity = _coerce_int(raw_payload.get("qty"))
    symbol = _resolve_symbol(raw_payload, strategy)
    price = _resolve_price(raw_payload, indicators)
    timestamp = _resolve_timestamp(raw_payload)

    return {
        "symbol": symbol,
        "action": native_action,
        "side": side_tag,
        "quantity": quantity,
        "score": score,
        "price": price,
        "order_type": str(raw_payload.get("order_type") or "market"),
        "timestamp": timestamp,
        "indicators": indicators,
        "use_dhan": bool(raw_payload.get("useDhan", False)),
        "pine_type": pine_type,
        "pine_action_raw": pine_action,
        "_source": "pine_v4.8.1",
    }


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


class PineMappingError(ValueError):
    """Raised when a Pine payload cannot be mapped to the native shape."""


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_symbol(
    raw_payload: dict[str, Any], strategy: Strategy | None
) -> str:
    """Pine often omits the symbol; fall back to strategy.allowed_symbols[0]."""
    symbol = raw_payload.get("symbol")
    if isinstance(symbol, str) and symbol.strip():
        return symbol.strip()
    if strategy is not None:
        allowed = getattr(strategy, "allowed_symbols", None) or []
        if allowed:
            first = allowed[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
    return ""


def _resolve_price(
    raw_payload: dict[str, Any], indicators: dict[str, Any]
) -> float | None:
    """Use payload.price if present; else LongMA, else SlowMA."""
    price = _coerce_float(raw_payload.get("price"))
    if price is not None:
        return price
    for key in ("LongMA", "SlowMA"):
        candidate = _coerce_float(indicators.get(key))
        if candidate is not None:
            return candidate
    return None


def _resolve_timestamp(raw_payload: dict[str, Any]) -> str:
    """Use payload.timestamp string if present; else server now() in ISO-8601 UTC."""
    ts = raw_payload.get("timestamp")
    if isinstance(ts, str) and ts.strip():
        return ts.strip()
    return datetime.now(UTC).isoformat()


__all__ = [
    "PineMappingError",
    "is_pine_payload",
    "map_to_tradetri_payload",
]
