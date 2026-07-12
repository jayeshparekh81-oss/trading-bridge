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

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Final
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from app.core.logging import get_logger
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
from app.strategy_engine.trading_calendar import trading_days_between

if TYPE_CHECKING:
    from app.brokers.dhan import ScripMeta
    from app.db.models.strategy import Strategy

_logger = get_logger("services.pine_mapper")

#: Pine ``type`` prefixes that identify a Pine payload.
_PINE_TYPE_PREFIXES: tuple[str, ...] = ("LONG_", "SHORT_")

#: Inbound key the TV alert template will carry. MUST be confirmed
#: against the founder's actual Pine alert JSON before merge — rename
#: here if the template differs.
_INBOUND_SCORE_KEY: Final = "score"

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

    # Score: honour the alert's own score when present + valid — Pine is
    # the calibrated source of truth for its chart. The server-side
    # compute_score replica (₹740-era AVG_VALUES anchors) is a FALLBACK
    # only, for templates that don't send a score. NOTE: the check is
    # ``is not None``, not truthiness — an inbound 0.0 is a valid score
    # and must pass through (the gate then rejects it, correctly).
    score_side = "SHORT" if side_tag == "short" else "LONG"
    inbound_score = _extract_inbound_score(raw_payload)
    if inbound_score is not None:
        score = inbound_score
        score_source = "pine"
        _logger.info(
            "pine_mapper.score_passthrough",
            symbol=raw_payload.get("symbol"),
            score=score,
        )
    else:
        score = compute_score(indicators, score_side)
        score_source = "computed"

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
        "score_source": score_source,
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


def _extract_inbound_score(raw_payload: dict[str, Any]) -> float | None:
    """Alert-supplied score (``_INBOUND_SCORE_KEY``), or None to fall back.

    Mirrors ``ai_validator._extract_payload_score`` VERBATIM: None or
    bool → None (bool is an int subclass — reject explicitly); float()
    failure → None; accept only ``0.0 <= v <= 100.0``, else None.
    """
    raw = raw_payload.get(_INBOUND_SCORE_KEY)
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if 0.0 <= value <= 100.0:
        return value
    return None


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

#: Near-expiry roll floor, in TRADING days (weekends skipped; counted
#: start-exclusive / expiry-inclusive via ``trading_days_between``).
#: Contracts whose expiry is <= this many trading days away are skipped
#: and the pick rolls to the next listed contract — the decided
#: 2-3-trading-day theta-avoidance rule. Default 2; widening to 3 is a
#: single-constant change.
OPTIONS_ROLL_MIN_TRADING_DAYS: Final = 2

#: F&O segment → orderable Exchange. Options inherit their underlying's
#: F&O segment; BSE LTD lives in NSE_FNO → NFO.
_SEGMENT_TO_EXCHANGE: Final[dict[str, Exchange]] = {
    "NSE_FNO": Exchange.NFO,
    "BSE_FNO": Exchange.BFO,
}

#: Segment the option picker enumerates — mirrors futures_resolver's
#: NSE_FNO pin in ``_list_fut_contracts``. Dual-listed underlyings
#: (ANGELONE: 280 NSE + 130 BSE option rows in the live master) would
#: otherwise make the pick between identical NSE/BSE contracts arbitrary
#: and could route to BFO via ``_SEGMENT_TO_EXCHANGE``. BFO/dual-listing
#: support = future config decision, out of scope here.
_OPTIONS_SEGMENT: Final = "NSE_FNO"


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


def _pick_option_contract(
    scrip_master: Any,
    *,
    option_type: str,
    strike: Decimal,
    underlying: str,
    reference_date: date,
    expiry_type: str,
) -> ScripMeta:
    """Enumerate real listed contracts and pick by ACTUAL expiry.

    Replaces the old guess-then-exact-match design (compute a calendar
    date from a hardcoded weekday, then demand ``expiry_date ==``).
    Selection now runs over the REAL listed expiries — ``SEM_EXPIRY_DATE``
    from the scrip master, which is already Tuesday-correct and
    holiday-shifted by the exchange — so no weekday assumption survives.

    Read-only consumption of ``_ScripMaster._meta`` — we cannot add a
    search method to the frozen ``dhan.py`` adapter, so we iterate the
    parsed ``ScripMeta`` values here.

    * Candidates: ``_OPTIONS_SEGMENT`` (NSE_FNO) rows matching
      (underlying root, ``option_type``, ``strike``) that carry a
      parsed ``expiry_date``, sorted ascending by expiry.
    * Near-expiry roll: candidates with
      ``trading_days_between(reference_date, expiry) <=
      OPTIONS_ROLL_MIN_TRADING_DAYS`` are dropped (theta avoidance).
    * ``current_week`` / ``weekly`` / ``current_month`` / ``monthly`` →
      first eligible; ``next_week`` → second eligible. For monthly-only
      stock options ``current_week`` and ``current_month`` coincide
      (both = the nearest eligible listed contract). Weekly-vs-monthly
      disambiguation for INDEX options is a documented TODO, out of
      scope here — verified against the live master: index weeklies and
      monthlies share the same ``MonYYYY`` symbol token, so the
      disambiguation input is the CSV's ``SEM_EXPIRY_FLAG`` (W/M),
      which is NOT currently parsed into :class:`ScripMeta` (a gated
      ``dhan.py`` change when that TODO is picked up).

    Raises :class:`PineMapperError` on an unknown ``expiry_type`` or
    when no eligible contract exists at the requested position.
    """
    et = expiry_type.strip().lower()
    if et in ("current_week", "weekly", "current_month", "monthly"):
        pick_index = 0
    elif et == "next_week":
        pick_index = 1
    else:
        raise PineMapperError(f"unknown expiry type {expiry_type!r}")

    meta_map = getattr(scrip_master, "_meta", None)
    candidates: list[ScripMeta] = []
    if isinstance(meta_map, dict):
        # Root match mirrors _list_fut_contracts' prefix match in
        # futures_resolver — both scan the same SEM_TRADING_SYMBOL
        # source, dash-structured ``ROOT-…-CE``. Prefix (not substring)
        # so root BSE cannot match an SBSEX contract.
        want_prefix = f"{underlying.upper()}-"
        for m in meta_map.values():
            if m.segment != _OPTIONS_SEGMENT:
                continue
            if m.option_type != option_type:
                continue
            if m.strike_price != strike:
                continue
            if m.expiry_date is None:
                continue
            if underlying and not m.symbol.upper().startswith(want_prefix):
                continue
            candidates.append(m)

    eligible = sorted(
        (
            m
            for m in candidates
            if trading_days_between(reference_date, m.expiry_date)
            > OPTIONS_ROLL_MIN_TRADING_DAYS
        ),
        key=lambda m: m.expiry_date,
    )
    if pick_index >= len(eligible):
        raise PineMapperError(
            f"no eligible {expiry_type!r} option contract for "
            f"{underlying} {option_type} strike={strike} as of "
            f"{reference_date.isoformat()} "
            f"(roll floor: {OPTIONS_ROLL_MIN_TRADING_DAYS} trading days)"
        )
    return eligible[pick_index]


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
    → contract picked from the REAL listed expiries (enumerate-and-pick
    with a near-expiry trading-day roll; see
    :func:`_pick_option_contract`) → qty = ``entry_lots * lot_size``.

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

    root = _underlying_root(raw_payload, strategy)
    if scrip_master is None:
        from app.brokers.dhan import _SCRIP_MASTER

        scrip_master = _SCRIP_MASTER

    scrip = _pick_option_contract(
        scrip_master,
        option_type=option_type,
        strike=strike,
        underlying=root,
        reference_date=ref,
        expiry_type=config.expiry,
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
    "resolve_option_type",
    "resolve_strike",
]
