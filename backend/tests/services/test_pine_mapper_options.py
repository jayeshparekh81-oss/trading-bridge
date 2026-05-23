"""Pine mapper — options support (Phase 2B) unit tests.

Covers the new options path added in feat/pine-mapper-options:

  * Strike resolution — ATM (various spots) + OTM/ITM offset.
  * Expiry resolution — current_week / next_week / current_month, the
    on-Thursday edge, and holiday shift.
  * option_type resolution — auto (LONG→CE, SHORT→PE), CE_only, PE_only.
  * OptionsConfig NRML mandate — NRML accepted, MIS/INTRADAY/CNC and
    carry_forward=false rejected with PineMapperError.
  * Strategy detection (strategy_json + instrument_type attr).
  * End-to-end OrderRequest build via a mock ScripMaster (Phase 2A
    ScripMeta), asserting product_type is ALWAYS MARGIN (NRML), qty =
    entry_lots * lot_size, side BUY, exchange NFO, and the spot fallback.

Pure code: no DB, no broker, no HTTP.

    pytest backend/tests/services/test_pine_mapper_options.py -v
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.brokers.dhan import ScripMeta
from app.schemas.broker import Exchange, OrderSide, OrderType, ProductType
from app.services.pine_mapper import (
    PineMapperError,
    PineMappingError,
    is_options_strategy,
    map_pine_to_option_order,
    parse_options_config,
    resolve_atm_strike,
    resolve_option_type,
    resolve_options_expiry,
    resolve_strike,
)

# ───────────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ───────────────────────────────────────────────────────────────────────

_NRML_OPTIONS: dict[str, Any] = {
    "option_type": "auto",
    "strike_selection": {"method": "ATM", "offset": 0},
    "expiry": "current_week",
    "premium_budget_per_lot": 18000,
    "product_type": "NRML",
    "carry_forward": True,
    "expiry_day_force_close": True,
    "no_intraday_squareoff": True,
}


class _FakeScripMaster:
    """Stand-in for the Phase 2A ``_ScripMaster`` — exposes the ``_meta``
    map the mapper scans plus ``lot_size``."""

    def __init__(self, *metas: ScripMeta) -> None:
        self._meta = {m.security_id: m for m in metas}

    def lot_size(self, security_id: str) -> int | None:
        m = self._meta.get(security_id)
        return m.lot_size if m else None


def _option_scrip(
    *,
    security_id: str = "44321",
    option_type: str = "CE",
    strike: Decimal = Decimal("2400"),
    expiry: date,
    lot_size: int = 375,
    root: str = "BSE",
) -> ScripMeta:
    return ScripMeta(
        security_id=security_id,
        symbol=f"{root}-{expiry:%d%b%Y}-{int(strike)}-{option_type}".upper(),
        segment="NSE_FNO",
        instrument="OPTSTK",
        lot_size=lot_size,
        option_type=option_type,
        strike_price=strike,
        expiry_date=expiry,
    )


def _options_strategy(
    *,
    options: dict[str, Any] | None = _NRML_OPTIONS,
    entry_lots: int = 4,
    allowed: list[str] | None = None,
    instrument_type: str | None = None,
    name: str = "bse-opt",
) -> Any:
    sj: dict[str, Any] = {}
    if instrument_type is not None:
        sj["instrument_type"] = instrument_type
    if options is not None:
        sj["options"] = options
    return SimpleNamespace(
        strategy_json=sj or None,
        allowed_symbols=allowed or ["NSE:BSE"],
        entry_lots=entry_lots,
        name=name,
        instrument_type=instrument_type,
    )


# ═══════════════════════════════════════════════════════════════════════
# Strike resolution
# ═══════════════════════════════════════════════════════════════════════


class TestStrikeResolution:
    @pytest.mark.parametrize(
        ("spot", "step", "expected"),
        [
            (Decimal("2437"), Decimal("100"), Decimal("2400")),
            (Decimal("2450"), Decimal("100"), Decimal("2500")),  # half-up
            (Decimal("2400"), Decimal("100"), Decimal("2400")),  # exact
            (Decimal("24999"), Decimal("100"), Decimal("25000")),
            (Decimal("2437"), Decimal("50"), Decimal("2450")),
        ],
    )
    def test_resolve_atm_strike(
        self, spot: Decimal, step: Decimal, expected: Decimal
    ) -> None:
        assert resolve_atm_strike(spot, step) == expected

    def test_resolve_atm_strike_default_step_is_100(self) -> None:
        assert resolve_atm_strike(Decimal("2437")) == Decimal("2400")

    def test_resolve_atm_strike_rejects_zero_step(self) -> None:
        with pytest.raises(PineMapperError):
            resolve_atm_strike(Decimal("2437"), Decimal("0"))

    def test_otm_offset_ce_moves_up(self) -> None:
        assert resolve_strike(
            Decimal("2437"), "CE", method="OTM_OFFSET", offset=1
        ) == Decimal("2500")

    def test_otm_offset_pe_moves_down(self) -> None:
        assert resolve_strike(
            Decimal("2437"), "PE", method="OTM_OFFSET", offset=1
        ) == Decimal("2300")

    def test_itm_offset_ce_moves_down(self) -> None:
        assert resolve_strike(
            Decimal("2437"), "CE", method="ITM_OFFSET", offset=2
        ) == Decimal("2200")

    def test_atm_ignores_offset(self) -> None:
        assert resolve_strike(
            Decimal("2437"), "CE", method="ATM", offset=5
        ) == Decimal("2400")

    def test_unknown_strike_method_raises(self) -> None:
        with pytest.raises(PineMapperError):
            resolve_strike(Decimal("2437"), "CE", method="DELTA", offset=1)


# ═══════════════════════════════════════════════════════════════════════
# Expiry resolution
# ═══════════════════════════════════════════════════════════════════════


class TestExpiryResolution:
    # 2026-05-04 is a Monday; the Thursday of that week is 2026-05-07.
    _MONDAY = date(2026, 5, 4)
    _THURSDAY = date(2026, 5, 7)

    def test_current_week_is_upcoming_thursday(self) -> None:
        assert resolve_options_expiry(self._MONDAY, "current_week") == self._THURSDAY

    def test_current_week_on_thursday_returns_same_day(self) -> None:
        assert (
            resolve_options_expiry(self._THURSDAY, "current_week") == self._THURSDAY
        )

    def test_next_week_is_thursday_plus_seven(self) -> None:
        assert resolve_options_expiry(self._MONDAY, "next_week") == date(2026, 5, 14)

    def test_current_month_is_last_thursday(self) -> None:
        # Last Thursday of May 2026 is the 28th.
        assert resolve_options_expiry(
            date(2026, 5, 1), "current_month"
        ) == date(2026, 5, 28)

    def test_current_month_rolls_when_passed(self) -> None:
        # After May's last Thursday → June's last Thursday (2026-06-25).
        assert resolve_options_expiry(
            date(2026, 5, 29), "current_month"
        ) == date(2026, 6, 25)

    def test_holiday_shifts_to_previous_day(self) -> None:
        # Thursday 2026-05-07 is a holiday → expiry shifts to Wed 05-06.
        assert resolve_options_expiry(
            self._MONDAY, "current_week", holidays={self._THURSDAY}
        ) == date(2026, 5, 6)

    def test_unknown_expiry_type_raises(self) -> None:
        with pytest.raises(PineMapperError):
            resolve_options_expiry(self._MONDAY, "fortnightly")


# ═══════════════════════════════════════════════════════════════════════
# option_type / direction
# ═══════════════════════════════════════════════════════════════════════


class TestOptionTypeResolution:
    def test_auto_long_is_ce(self) -> None:
        cfg = parse_options_config(_options_strategy())
        assert resolve_option_type("LONG_ENTRY", cfg) == "CE"

    def test_auto_short_is_pe(self) -> None:
        cfg = parse_options_config(_options_strategy())
        assert resolve_option_type("SHORT_ENTRY", cfg) == "PE"

    def test_ce_only_forces_ce_even_for_short(self) -> None:
        opts = {**_NRML_OPTIONS, "option_type": "CE_only"}
        cfg = parse_options_config(_options_strategy(options=opts))
        assert resolve_option_type("SHORT_ENTRY", cfg) == "CE"

    def test_pe_only_forces_pe_even_for_long(self) -> None:
        opts = {**_NRML_OPTIONS, "option_type": "PE_only"}
        cfg = parse_options_config(_options_strategy(options=opts))
        assert resolve_option_type("LONG_ENTRY", cfg) == "PE"


# ═══════════════════════════════════════════════════════════════════════
# Config validation — NRML mandate
# ═══════════════════════════════════════════════════════════════════════


class TestOptionsConfigValidation:
    def test_nrml_config_parses(self) -> None:
        cfg = parse_options_config(_options_strategy())
        assert cfg.product_type == "NRML"
        assert cfg.carry_forward is True
        assert cfg.expiry == "current_week"

    def test_margin_alias_normalises_to_nrml(self) -> None:
        opts = {**_NRML_OPTIONS, "product_type": "MARGIN"}
        cfg = parse_options_config(_options_strategy(options=opts))
        assert cfg.product_type == "NRML"

    def test_mis_config_rejected(self) -> None:
        opts = {**_NRML_OPTIONS, "product_type": "MIS"}
        with pytest.raises(PineMapperError):
            parse_options_config(_options_strategy(options=opts))

    def test_intraday_config_rejected(self) -> None:
        opts = {**_NRML_OPTIONS, "product_type": "INTRADAY"}
        with pytest.raises(PineMapperError):
            parse_options_config(_options_strategy(options=opts))

    def test_delivery_config_rejected(self) -> None:
        opts = {**_NRML_OPTIONS, "product_type": "CNC"}
        with pytest.raises(PineMapperError):
            parse_options_config(_options_strategy(options=opts))

    def test_carry_forward_false_rejected(self) -> None:
        opts = {**_NRML_OPTIONS, "carry_forward": False}
        with pytest.raises(PineMapperError):
            parse_options_config(_options_strategy(options=opts))

    def test_no_options_block_raises(self) -> None:
        strat = SimpleNamespace(strategy_json={"instrument_type": "futures"})
        with pytest.raises(PineMapperError):
            parse_options_config(strat)


# ═══════════════════════════════════════════════════════════════════════
# Strategy detection
# ═══════════════════════════════════════════════════════════════════════


class TestStrategyDetection:
    def test_detected_via_options_block(self) -> None:
        assert is_options_strategy(_options_strategy()) is True

    def test_detected_via_instrument_type_attr(self) -> None:
        strat = SimpleNamespace(
            instrument_type="options", strategy_json=None, allowed_symbols=[]
        )
        assert is_options_strategy(strat) is True

    def test_detected_via_strategy_json_instrument_type(self) -> None:
        strat = SimpleNamespace(strategy_json={"instrument_type": "options"})
        assert is_options_strategy(strat) is True

    def test_futures_strategy_not_detected(self) -> None:
        strat = SimpleNamespace(
            strategy_json=None, allowed_symbols=["NSE:BSE"], instrument_type=None
        )
        assert is_options_strategy(strat) is False

    def test_none_strategy_not_detected(self) -> None:
        assert is_options_strategy(None) is False


# ═══════════════════════════════════════════════════════════════════════
# End-to-end OrderRequest build
# ═══════════════════════════════════════════════════════════════════════


class TestBuildOptionOrder:
    def _ref_and_master(
        self, option_type: str = "CE", strike: Decimal = Decimal("2400")
    ) -> tuple[date, _FakeScripMaster]:
        ref = date(2026, 5, 4)
        expiry = resolve_options_expiry(ref, "current_week")
        scrip = _option_scrip(option_type=option_type, strike=strike, expiry=expiry)
        return ref, _FakeScripMaster(scrip)

    def test_long_entry_builds_ce_nrml_order(self) -> None:
        ref, master = self._ref_and_master("CE")
        order = map_pine_to_option_order(
            {"action": "ENTRY", "type": "LONG_ENTRY", "spot_price": "2437"},
            _options_strategy(entry_lots=4),
            reference_date=ref,
            scrip_master=master,
        )
        assert isinstance(order.symbol, str) and order.symbol.endswith("-CE")
        assert order.side is OrderSide.BUY
        assert order.order_type is OrderType.MARKET
        # qty = entry_lots(4) * lot_size(375)
        assert order.quantity == 1500
        assert order.exchange is Exchange.NFO
        # HARD GUARD — NRML carry-forward ALWAYS.
        assert order.product_type is ProductType.MARGIN

    def test_short_entry_builds_pe_order(self) -> None:
        ref, master = self._ref_and_master("PE")
        order = map_pine_to_option_order(
            {"action": "ENTRY", "type": "SHORT_ENTRY", "spot_price": "2437"},
            _options_strategy(),
            reference_date=ref,
            scrip_master=master,
        )
        assert order.symbol.endswith("-PE")
        assert order.side is OrderSide.BUY  # buying a put (long premium)
        assert order.product_type is ProductType.MARGIN

    def test_product_type_is_always_margin_nrml(self) -> None:
        ref, master = self._ref_and_master("CE")
        order = map_pine_to_option_order(
            {"type": "LONG_ENTRY", "spot_price": "2437"},
            _options_strategy(),
            reference_date=ref,
            scrip_master=master,
        )
        assert order.product_type == ProductType.MARGIN

    def test_spot_price_falls_back_to_payload_price(self) -> None:
        # No spot_price → uses price (2437) as the spot proxy → ATM 2400.
        ref, master = self._ref_and_master("CE", Decimal("2400"))
        order = map_pine_to_option_order(
            {"type": "LONG_ENTRY", "price": "2437"},
            _options_strategy(),
            reference_date=ref,
            scrip_master=master,
        )
        assert order.symbol.endswith("-2400-CE")

    def test_spot_price_kwarg_overrides(self) -> None:
        ref, master = self._ref_and_master("CE", Decimal("2500"))
        order = map_pine_to_option_order(
            {"type": "LONG_ENTRY"},
            _options_strategy(),
            spot_price=Decimal("2480"),  # half-up → 2500
            reference_date=ref,
            scrip_master=master,
        )
        assert order.symbol.endswith("-2500-CE")

    def test_otm_offset_picks_otm_contract(self) -> None:
        ref = date(2026, 5, 4)
        expiry = resolve_options_expiry(ref, "current_week")
        # spot 2437 → ATM 2400, OTM offset 1 CE → 2500.
        master = _FakeScripMaster(
            _option_scrip(option_type="CE", strike=Decimal("2500"), expiry=expiry)
        )
        opts = {**_NRML_OPTIONS, "strike_selection": {"method": "OTM_OFFSET", "offset": 1}}
        order = map_pine_to_option_order(
            {"type": "LONG_ENTRY", "spot_price": "2437"},
            _options_strategy(options=opts),
            reference_date=ref,
            scrip_master=master,
        )
        assert order.symbol.endswith("-2500-CE")

    def test_missing_spot_and_price_raises(self) -> None:
        ref, master = self._ref_and_master("CE")
        with pytest.raises(PineMapperError):
            map_pine_to_option_order(
                {"type": "LONG_ENTRY"},
                _options_strategy(),
                reference_date=ref,
                scrip_master=master,
            )

    def test_unknown_contract_raises(self) -> None:
        order_payload = {"type": "LONG_ENTRY", "spot_price": "2437"}
        with pytest.raises(PineMapperError):
            map_pine_to_option_order(
                order_payload,
                _options_strategy(),
                reference_date=date(2026, 5, 4),
                scrip_master=_FakeScripMaster(),  # empty master
            )

    def test_exit_signal_rejected_by_entry_builder(self) -> None:
        ref, master = self._ref_and_master("CE")
        with pytest.raises(PineMapperError):
            map_pine_to_option_order(
                {"type": "LONG_EXIT", "spot_price": "2437"},
                _options_strategy(),
                reference_date=ref,
                scrip_master=master,
            )

    def test_non_options_strategy_rejected(self) -> None:
        ref, master = self._ref_and_master("CE")
        futures_strat = SimpleNamespace(
            strategy_json=None, allowed_symbols=["NSE:BSE"], instrument_type=None
        )
        with pytest.raises(PineMapperError):
            map_pine_to_option_order(
                {"type": "LONG_ENTRY", "spot_price": "2437"},
                futures_strat,
                reference_date=ref,
                scrip_master=master,
            )

    def test_mis_config_blocks_order_construction(self) -> None:
        ref, master = self._ref_and_master("CE")
        opts = {**_NRML_OPTIONS, "product_type": "MIS"}
        with pytest.raises(PineMapperError):
            map_pine_to_option_order(
                {"type": "LONG_ENTRY", "spot_price": "2437"},
                _options_strategy(options=opts),
                reference_date=ref,
                scrip_master=master,
            )

    def test_signal_direction_field_overrides_type(self) -> None:
        ref, master = self._ref_and_master("PE")
        # type says LONG but explicit signal_direction says SHORT → PE.
        order = map_pine_to_option_order(
            {
                "type": "LONG_ENTRY",
                "signal_direction": "SHORT_ENTRY",
                "spot_price": "2437",
            },
            _options_strategy(),
            reference_date=ref,
            scrip_master=master,
        )
        assert order.symbol.endswith("-PE")

    def test_pine_mapper_error_is_pine_mapping_error_subclass(self) -> None:
        # Webhook layer catches PineMappingError; PineMapperError must be
        # caught by that same handler → no behavioural regression.
        assert issubclass(PineMapperError, PineMappingError)
