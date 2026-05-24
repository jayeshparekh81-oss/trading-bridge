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

Phase-1 scope: Futures + Options (single-leg directional, NRML
carry-forward). Options strike/expiry resolved at mapping from
strategy_json + Pine spot price.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Final
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from app.schemas.broker import (
    Exchange,
    OrderRequest,
    OrderSide,
    OrderType,
    ProductType,
)
from app.schemas.pine_webhook import (
    _NRML_ALIASES,
    OptionsConfig,
)
from app.services.ai_validator import compute_score

if TYPE_CHECKING:
    from app.brokers.dhan import ScripMeta
    from app.db.models.strategy import Strategy

#: Pine ``type`` prefixes that identify a Pine payload.
_PINE_TYPE_PREFIXES: tuple[str, ...] = ("LONG_", "SHORT_")

#: Mapping (pine_action, pine_type) -> (tradetri_action, side_tag).
#: side_tag is recorded on the mapped payload so downstream can
#: differentiate LONG from SHORT exits/partials without re-parsing type.
#:
#: Sun 2026-05-03 refactor: native action names switched from the legacy
#: ``BUY/SELL/PARTIAL_LONG/PARTIAL_SHORT`` set to the canonical Pine
#: vocabulary ``ENTRY/PARTIAL/EXIT/SL_HIT``. Side is now carried purely
#: in the ``side`` field. Legacy callers using BUY/SELL still work — the
#: webhook handler aliases them to ENTRY with an INFO log.
_PINE_TO_NATIVE: dict[tuple[str, str], tuple[str, str]] = {
    ("ENTRY", "LONG_ENTRY"): ("ENTRY", "long"),
    ("ENTRY", "SHORT_ENTRY"): ("ENTRY", "short"),
    ("PARTIAL", "LONG_PARTIAL"): ("PARTIAL", "long"),
    ("PARTIAL", "SHORT_PARTIAL"): ("PARTIAL", "short"),
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
    # closePct (Pine spelling) — passed through for PARTIAL actions. Also
    # accept ``close_pct`` (snake-case) so a hand-crafted alert can use
    # either spelling. Validated downstream by the webhook handler.
    close_pct = _coerce_float(
        raw_payload.get("closePct", raw_payload.get("close_pct"))
    )

    # Pine sends ``qty`` in LOTS — server_final30mar.py convention. The
    # executor needs total contracts to send to Dhan, so we tag the
    # mapped payload with ``quantity_unit="lots"`` and let the executor
    # multiply by the resolved lot_size.
    #
    # Best-effort lot_size_hint from the in-process Dhan scrip-master
    # cache: paper-mode tests that don't have a Dhan broker call in
    # their flow won't load the cache, so the lookup may MISS and we
    # leave the hint absent. Live mode picks up the real lot_size via
    # ``broker.get_lot_size`` regardless. The caller can always override
    # by injecting ``lot_size_hint`` in the raw payload.
    lot_size_hint = _try_lookup_lot_size(symbol)
    if lot_size_hint is None:
        lot_size_hint = _coerce_int(raw_payload.get("lot_size_hint"))

    # PARTIAL/EXIT/SL_HIT don't use quantity (PARTIAL uses closePct, EXIT
    # closes remaining). Pine sends qty=0 in these cases as a legacy
    # placeholder; the Pydantic schema rejects 0 as invalid for the
    # quantity field. Drop it so the schema only validates quantity for
    # the action that actually carries it.
    quantity_for_payload: int | None = quantity if native_action == "ENTRY" else None

    return {
        "symbol": symbol,
        "action": native_action,
        "side": side_tag,
        "quantity": quantity_for_payload,
        "quantity_unit": "lots",
        "lot_size_hint": lot_size_hint,
        "closePct": close_pct,
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


def _try_lookup_lot_size(symbol: str) -> int | None:
    """Best-effort lot_size lookup against the module-level Dhan cache.

    Returns None when the cache is empty (process hasn't yet had any
    code path load the scrip master) or when the symbol isn't in the
    cache. The executor's :func:`_resolve_lot_size` handles the live
    case via ``broker.get_lot_size``; this hint is purely so paper-mode
    Pine tests don't have to manually inject ``lot_size_hint``.

    Lazy-imports to avoid coupling the mapper to the Dhan module at
    import time (the test fixture monkeypatches it freely).
    """
    try:
        from app.brokers.dhan import _SCRIP_MASTER

        sec_id = _SCRIP_MASTER.lookup(symbol.upper(), "NSE_FNO")
        if sec_id is None:
            return None
        return _SCRIP_MASTER.lot_size(sec_id)
    except Exception:  # noqa: BLE001 — best-effort, never fail mapping
        return None


def _resolve_timestamp(raw_payload: dict[str, Any]) -> str:
    """Use payload.timestamp string if present; else server now() in ISO-8601 UTC."""
    ts = raw_payload.get("timestamp")
    if isinstance(ts, str) and ts.strip():
        return ts.strip()
    return datetime.now(UTC).isoformat()


# ═══════════════════════════════════════════════════════════════════════
# Options support (Phase 2B) — single-leg directional, NRML carry-forward
# ═══════════════════════════════════════════════════════════════════════
#
# CRITICAL SEMANTIC — Options are NRML carry-forward ONLY.
# MIS/INTRADAY are forbidden: the broker auto-squares-off MIS positions at
# ~15:15-15:30 IST, which would silently liquidate a multi-day options
# position. The OptionsConfig schema rejects them at parse time and
# ``_enforce_nrml`` re-checks at the order boundary as a hard guard.
#
# This path BUILDS an OrderRequest but is NOT yet wired into the (frozen)
# strategy_executor — that is Phase 3. The executor still hard-codes
# Exchange.NFO; see PINE_MAPPER_OPTIONS_NOTES.md.


class PineMapperError(PineMappingError):
    """Options mapping / config-validation failure.

    Subclass of :class:`PineMappingError` so the webhook layer's existing
    ``except PineMappingError`` handler still catches it — no behavioural
    regression for the futures path.
    """


_IST: Final = ZoneInfo("Asia/Kolkata")

#: Default strike step for BSE LTD weekly options.
#: ⚠️ ASSUMPTION — verify against the live contract spec before Phase 3.
#: Overridable per-strategy via ``OptionsConfig.strike_step``.
_DEFAULT_STRIKE_STEP: Final = Decimal("100")

#: BSE LTD weekly options expire Thursday. ``date.weekday()``: Mon=0…Thu=3.
#: ⚠️ ASSUMPTION — flagged for verification (see notes).
_WEEKLY_EXPIRY_WEEKDAY: Final = 3

#: F&O segment → orderable Exchange. Options inherit their underlying's
#: F&O segment; BSE LTD lives in NSE_FNO → NFO.
_SEGMENT_TO_EXCHANGE: Final[dict[str, Exchange]] = {
    "NSE_FNO": Exchange.NFO,
    "BSE_FNO": Exchange.BFO,
}


# ─── Strike resolver ───────────────────────────────────────────────────


def resolve_atm_strike(
    spot_price: Decimal, strike_step: Decimal = _DEFAULT_STRIKE_STEP
) -> Decimal:
    """Round ``spot_price`` to the nearest ``strike_step`` multiple (ATM).

    Half-up rounding: a spot exactly between two strikes rounds to the
    higher one (e.g. 24450 @ step 100 → 24500).
    """
    if strike_step <= 0:
        raise PineMapperError(f"strike_step must be > 0, got {strike_step!r}")
    steps = (spot_price / strike_step).to_integral_value(rounding=ROUND_HALF_UP)
    return steps * strike_step


def resolve_strike(
    spot_price: Decimal,
    option_type: str,
    *,
    method: str = "ATM",
    offset: int = 0,
    strike_step: Decimal = _DEFAULT_STRIKE_STEP,
) -> Decimal:
    """Resolve the target strike from spot + selection method.

    ``OTM_OFFSET`` moves away from the money (CE → higher strikes, PE →
    lower); ``ITM_OFFSET`` moves toward the money. ATM ignores ``offset``.
    """
    atm = resolve_atm_strike(spot_price, strike_step)
    method_upper = method.strip().upper()
    if method_upper == "ATM" or offset == 0:
        return atm

    ce = option_type.strip().upper() == "CE"
    if method_upper == "OTM_OFFSET":
        direction = 1 if ce else -1
    elif method_upper == "ITM_OFFSET":
        direction = -1 if ce else 1
    else:
        raise PineMapperError(f"unknown strike method {method!r}")
    return atm + (Decimal(direction * offset) * strike_step)


# ─── Expiry resolver ─────────────────────────────────────────────────────


def _next_weekday_on_or_after(ref: date, weekday: int) -> date:
    """First date >= ``ref`` whose weekday is ``weekday`` (Mon=0…Sun=6)."""
    return ref + timedelta(days=(weekday - ref.weekday()) % 7)


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """Last ``weekday`` of the given month (e.g. last Thursday)."""
    first_of_next = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last_day = first_of_next - timedelta(days=1)
    return last_day - timedelta(days=(last_day.weekday() - weekday) % 7)


def resolve_options_expiry(
    reference_date: date,
    expiry_type: str,
    *,
    weekday: int = _WEEKLY_EXPIRY_WEEKDAY,
    holidays: set[date] | None = None,
) -> date:
    """Resolve an options expiry date from a config keyword.

    * ``current_week`` — the upcoming ``weekday`` on or after
      ``reference_date`` (BSE LTD weekly → next Thursday).
    * ``next_week`` — one week after ``current_week``.
    * ``current_month`` — the last ``weekday`` of ``reference_date``'s
      month; if that has already passed, rolls to next month.

    Holiday handling: if ``holidays`` is supplied and the computed expiry
    falls on one, it shifts to the previous day (mirrors NSE's "previous
    working day" rule). No holiday calendar ships today — by default
    expiry is computed purely from the calendar; see notes for the caveat.
    """
    et = expiry_type.strip().lower()
    if et in ("current_week", "weekly"):
        target = _next_weekday_on_or_after(reference_date, weekday)
    elif et == "next_week":
        target = _next_weekday_on_or_after(reference_date, weekday) + timedelta(days=7)
    elif et in ("current_month", "monthly"):
        target = _last_weekday_of_month(
            reference_date.year, reference_date.month, weekday
        )
        if target < reference_date:
            ny, nm = (
                (reference_date.year + 1, 1)
                if reference_date.month == 12
                else (reference_date.year, reference_date.month + 1)
            )
            target = _last_weekday_of_month(ny, nm, weekday)
    else:
        raise PineMapperError(f"unknown expiry type {expiry_type!r}")

    return _shift_off_holiday(target, holidays)


def _shift_off_holiday(d: date, holidays: set[date] | None) -> date:
    """Walk back to the previous non-holiday day (NSE expiry-shift rule)."""
    if not holidays:
        return d
    guard = 0
    while d in holidays and guard < 14:
        d -= timedelta(days=1)
        guard += 1
    return d


# ─── Direction / option-type resolution ──────────────────────────────────


def resolve_option_type(direction: str, config: OptionsConfig) -> str:
    """Resolve CE/PE from signal direction + config.

    ``auto`` → LONG buys a CE, SHORT buys a PE (single-leg directional);
    ``CE_only``/``PE_only`` pin the leg regardless of direction.
    """
    mode = config.option_type
    if mode == "CE_only":
        return "CE"
    if mode == "PE_only":
        return "PE"
    side = _direction_to_side(direction)
    if side == "long":
        return "CE"
    if side == "short":
        return "PE"
    raise PineMapperError(
        f"cannot resolve option_type for direction {direction!r} in auto mode"
    )


def _direction_to_side(direction: str) -> str:
    """Normalise a direction/type token to 'long' | 'short' | 'exit'.

    Non-entry tokens (``LONG_EXIT``, ``SHORT_SL``, ``*_PARTIAL``, bare
    ``EXIT``) classify as ``exit`` even though they carry a LONG/SHORT
    prefix — only ``*_ENTRY`` (and a bare LONG/SHORT) is an order-entry
    direction.
    """
    d = direction.strip().upper()
    if any(marker in d for marker in ("EXIT", "PARTIAL", "SL")):
        return "exit"
    if "LONG" in d:
        return "long"
    if "SHORT" in d:
        return "short"
    raise PineMapperError(f"unrecognised signal direction {direction!r}")


def _signal_direction(raw_payload: dict[str, Any]) -> str:
    """Prefer the explicit ``signal_direction`` field; else use ``type``."""
    sd = raw_payload.get("signal_direction")
    if isinstance(sd, str) and sd.strip():
        return sd.strip().upper()
    return str(raw_payload.get("type", "")).strip().upper()


# ─── Config parsing + strategy detection ─────────────────────────────────


def is_options_strategy(strategy: Strategy | None) -> bool:
    """True iff ``strategy`` is configured for options.

    Detection order: an explicit ``instrument_type`` attribute (forward
    compat for a future migration), then ``strategy_json.instrument_type``
    == 'options', then the presence of a ``strategy_json.options`` block.
    """
    if strategy is None:
        return False
    direct = getattr(strategy, "instrument_type", None)
    if isinstance(direct, str) and direct.strip().lower() == "options":
        return True
    sj = getattr(strategy, "strategy_json", None)
    if isinstance(sj, dict):
        if str(sj.get("instrument_type", "")).strip().lower() == "options":
            return True
        if isinstance(sj.get("options"), dict):
            return True
    return False


def parse_options_config(strategy: Strategy) -> OptionsConfig:
    """Parse + validate the options config off ``strategy.strategy_json``.

    Accepts the config under ``strategy_json["options"]`` or at the top
    level of ``strategy_json``. NRML/carry-forward violations surface as
    :class:`PineMapperError`.
    """
    sj = getattr(strategy, "strategy_json", None)
    if not isinstance(sj, dict):
        raise PineMapperError(
            "strategy_json missing or not an object; no options config"
        )
    raw = sj.get("options")
    if raw is None:
        # Allow the config at the top level of strategy_json, but only when
        # it actually carries an options marker key — otherwise a futures
        # strategy_json would silently parse as a default-NRML options
        # config (every field is optional).
        marker_keys = {
            "option_type",
            "strike_selection",
            "expiry",
            "product_type",
            "carry_forward",
        }
        if marker_keys & sj.keys():
            raw = sj
        else:
            raise PineMapperError("strategy_json has no 'options' config block")
    if not isinstance(raw, dict):
        raise PineMapperError("strategy_json['options'] is not an object")
    try:
        return OptionsConfig.model_validate(raw)
    except ValidationError as exc:
        raise PineMapperError(f"invalid options config: {exc}") from exc


def _enforce_nrml(config: OptionsConfig) -> None:
    """Hard guard re-checked at the order boundary (belt-and-suspenders).

    OptionsConfig already validates this, but a config object could be
    mutated after parsing; never let a non-NRML order reach construction.
    """
    if config.product_type.strip().upper() not in _NRML_ALIASES:
        raise PineMapperError(
            "HARD GUARD: options product_type must be NRML carry-forward, "
            f"got {config.product_type!r}"
        )
    if config.carry_forward is not True:
        raise PineMapperError("HARD GUARD: options require carry_forward=true")


# ─── Spot / underlying / scrip resolution ────────────────────────────────


def _resolve_spot(
    raw_payload: dict[str, Any], spot_price: Decimal | None
) -> Decimal:
    """Spot for strike resolution: explicit arg → payload.spot_price →
    payload.price (graceful fallback). Raises if nothing usable."""
    for candidate in (
        spot_price,
        raw_payload.get("spot_price"),
        raw_payload.get("price"),
    ):
        if candidate is None or candidate == "":
            continue
        try:
            value = Decimal(str(candidate))
        except (InvalidOperation, ValueError):
            continue
        if value > 0:
            return value
    raise PineMapperError(
        "no usable spot_price/price on alert; cannot resolve strike"
    )


def _underlying_root(raw_payload: dict[str, Any], strategy: Strategy) -> str:
    """Best-effort underlying root from the alert symbol or strategy.

    ``NSE:BSE`` → ``BSE``; ``BSE-MAY2026-FUT`` → ``BSE``; ``BSE1!`` →
    ``BSE``. Used as a secondary filter when matching the option row.
    """
    candidate = raw_payload.get("symbol")
    if not (isinstance(candidate, str) and candidate.strip()):
        allowed = getattr(strategy, "allowed_symbols", None) or []
        candidate = allowed[0] if allowed else ""
    token = str(candidate).strip().upper()
    if ":" in token:
        token = token.split(":")[-1]
    token = token.split("-")[0]
    return token.rstrip("1!").strip()


def _find_option_scrip(
    scrip_master: Any,
    *,
    option_type: str,
    strike: Decimal,
    expiry: date,
    underlying: str,
) -> ScripMeta | None:
    """Scan the (Phase 2A) scrip-master metadata for a matching option.

    Read-only consumption of ``_ScripMaster._meta`` — we cannot add a
    search method to the frozen ``dhan.py`` adapter, so we iterate the
    parsed ``ScripMeta`` values here. Match on the option triplet, with
    the underlying root as a substring guard.
    """
    meta_map = getattr(scrip_master, "_meta", None)
    if not isinstance(meta_map, dict):
        return None
    want_root = underlying.upper()
    candidates: list[ScripMeta] = list(meta_map.values())
    for m in candidates:
        if m.option_type != option_type:
            continue
        if m.strike_price != strike:
            continue
        if m.expiry_date != expiry:
            continue
        if want_root and want_root not in m.symbol.upper():
            continue
        return m
    return None


# ─── Top-level: build the options OrderRequest ───────────────────────────


def map_pine_to_option_order(
    raw_payload: dict[str, Any],
    strategy: Strategy,
    *,
    spot_price: Decimal | None = None,
    reference_date: date | None = None,
    scrip_master: Any | None = None,
) -> OrderRequest:
    """Map a Pine entry signal → an options :class:`OrderRequest`.

    Single-leg directional: a bullish signal **buys a CE**, a bearish
    signal **buys a PE** (``option_type="auto"``). ``product_type`` is
    **always** ``MARGIN`` (NRML carry-forward) — enforced by a hard guard.

    Resolution: option_type from direction+config → strike from spot+config
    → expiry from config → ScripMeta lookup (Phase 2A) → qty =
    ``entry_lots * lot_size``.

    Raises :class:`PineMapperError` on any unresolved step (non-options
    strategy, EXIT signal, missing spot, MIS config, unknown contract).
    """
    if not is_options_strategy(strategy):
        raise PineMapperError("strategy is not configured for options")

    config = parse_options_config(strategy)
    _enforce_nrml(config)

    direction = _signal_direction(raw_payload)
    side = _direction_to_side(direction)
    if side == "exit":
        raise PineMapperError(
            "EXIT signals are handled by the exit path, not the entry "
            "order builder (Phase 3)"
        )

    option_type = resolve_option_type(direction, config)
    spot = _resolve_spot(raw_payload, spot_price)
    strike_step = config.strike_step or _DEFAULT_STRIKE_STEP
    strike = resolve_strike(
        spot,
        option_type,
        method=config.strike_selection.method,
        offset=config.strike_selection.offset,
        strike_step=strike_step,
    )

    ref = reference_date or datetime.now(_IST).date()
    expiry = resolve_options_expiry(ref, config.expiry)

    root = _underlying_root(raw_payload, strategy)
    if scrip_master is None:
        from app.brokers.dhan import _SCRIP_MASTER

        scrip_master = _SCRIP_MASTER

    scrip = _find_option_scrip(
        scrip_master,
        option_type=option_type,
        strike=strike,
        expiry=expiry,
        underlying=root,
    )
    if scrip is None:
        raise PineMapperError(
            f"no scrip-master contract for {root} {option_type} "
            f"strike={strike} expiry={expiry.isoformat()}"
        )

    lot_size = scrip.lot_size
    if lot_size is None and hasattr(scrip_master, "lot_size"):
        lot_size = scrip_master.lot_size(scrip.security_id)
    if not lot_size or lot_size <= 0:
        raise PineMapperError(
            f"missing/invalid lot_size for {scrip.symbol} "
            f"(security_id={scrip.security_id})"
        )

    entry_lots = _coerce_int(getattr(strategy, "entry_lots", None))
    if not entry_lots or entry_lots <= 0:
        raise PineMapperError("strategy.entry_lots must be a positive integer")

    quantity = entry_lots * lot_size
    exchange = _SEGMENT_TO_EXCHANGE.get(scrip.segment, Exchange.NFO)
    tag = (getattr(strategy, "name", None) or "")[:32] or None

    return OrderRequest(
        symbol=scrip.symbol,
        exchange=exchange,
        side=OrderSide.BUY,  # buying the option leg (long premium)
        quantity=quantity,
        order_type=OrderType.MARKET,
        product_type=ProductType.MARGIN,  # NRML carry-forward — ALWAYS
        price=None,
        tag=tag,
    )


async def resolve_normalized_symbol(payload: dict[str, Any]) -> str:
    """D1 symbol-normalizer hook (additive, 2026-05-24).

    If the Pine payload carries the short-form fields (``instrument_type`` +
    ``expiry_preference``), treat ``symbol`` as a stable underlying and
    resolve it to the current/next-month Dhan contract symbol via
    :mod:`app.services.symbol_normalizer`. Otherwise return ``symbol``
    unchanged (legacy full-contract passthrough) — no existing mapping
    behaviour changes.

    Raises :class:`PineMapperError` (a :class:`PineMappingError`) on an
    unresolvable underlying or an unsupported instrument type, so the
    webhook's existing ``except PineMappingError`` returns a clean 400.
    """
    symbol = str(payload.get("symbol") or "").strip()
    instrument_type = payload.get("instrument_type")
    expiry_preference = payload.get("expiry_preference")
    exchange = payload.get("exchange") or "NFO"

    # Legacy / full-contract passthrough — nothing to resolve.
    if not instrument_type or not expiry_preference:
        return symbol

    from app.core.exceptions import BrokerInvalidSymbolError
    from app.services import symbol_normalizer

    try:
        resolved = await symbol_normalizer.resolve_symbol(
            underlying=symbol,
            instrument_type=str(instrument_type),
            expiry_preference=str(expiry_preference),  # type: ignore[arg-type]
            exchange=str(exchange),
        )
    except NotImplementedError as exc:
        raise PineMapperError(str(exc)) from exc
    except BrokerInvalidSymbolError as exc:
        raise PineMapperError(
            f"symbol normalization failed for {symbol!r}: {exc}"
        ) from exc
    return str(resolved["dhan_symbol"])


__all__ = [
    "OptionsConfig",
    "PineMapperError",
    "PineMappingError",
    "is_options_strategy",
    "is_pine_payload",
    "map_pine_to_option_order",
    "map_to_tradetri_payload",
    "parse_options_config",
    "resolve_atm_strike",
    "resolve_normalized_symbol",
    "resolve_option_type",
    "resolve_options_expiry",
    "resolve_strike",
]
