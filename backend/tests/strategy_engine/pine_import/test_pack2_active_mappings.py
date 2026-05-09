"""Pack 2 — Pine importer ACTIVE mappings.

Pack 2 (commit 511f591) shipped 13 calculation functions that
matched Pine call names which used to live in the importer's
``_COMING_SOON_PINE_TO_REGISTRY`` dict (plus 2 brand-new active
mappings: ``ta.rma -> smma`` and ``ta.cmo -> chande_momentum``).

The follow-up commit moved all 15 to active branches in the
mapper. These tests pin the new contract:

    * indicator dict appears in the result with the right ``type``
      and ``params``;
    * no 'currently coming_soon' note is emitted for these names.

The 3 names that genuinely remain coming-soon
(``stoch_rsi`` / ``mom`` / ``heikinashi``) keep their notes-only
behavior — covered by ``test_mappings_batch1.py``.
"""

from __future__ import annotations

from app.strategy_engine.pine_import import convert_pine_to_strategy
from app.strategy_engine.schema.strategy import StrategyJSON

# ─── Helpers (mirror ``test_mappings_batch1.py``) ─────────────────────


_PINE_HEADER = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("Pack 2 active test")
"""

_TRIGGER_TAIL = """
trigger = ta.crossover(close, open)
if trigger
    strategy.entry("Long", strategy.long)
"""


def _wrap(indicator_line: str) -> str:
    return f"{_PINE_HEADER}{indicator_line}\n{_TRIGGER_TAIL}"


def _by_id(result: dict[str, object]) -> dict[str, dict[str, object]]:
    indicators = result["strategy"]["indicators"]  # type: ignore[index]
    return {ind["id"]: ind for ind in indicators}  # type: ignore[index, attr-defined]


def _notes(result: dict[str, object]) -> list[str]:
    notes = result.get("notes")
    return list(notes) if isinstance(notes, list) else []


def _assert_no_coming_soon_note_for(result: dict[str, object], pine_name: str) -> None:
    """Pine name's note must not say 'currently coming_soon' anymore."""
    for n in _notes(result):
        if pine_name in n and "coming_soon" in n:
            raise AssertionError(
                f"stale coming_soon note still emitted for ``ta.{pine_name}``: {n!r}"
            )


# ─── Trend (7 of the 13 promoted) ─────────────────────────────────────


def test_vwma_active_mapping_emits_indicator_with_period_and_source() -> None:
    src = _wrap("vwma_val = ta.vwma(close, 20)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "vwma_val" in inds
    assert inds["vwma_val"]["type"] == "vwma"
    assert inds["vwma_val"]["params"] == {"period": 20, "source": "close"}
    _assert_no_coming_soon_note_for(result, "vwma")


def test_rma_active_mapping_emits_smma() -> None:
    """Pine ``ta.rma`` maps to the registry's ``smma`` (Wilder RMA)."""
    src = _wrap("rma_val = ta.rma(close, 14)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "rma_val" in inds
    assert inds["rma_val"]["type"] == "smma"
    assert inds["rma_val"]["params"] == {"period": 14, "source": "close"}


def test_dema_active_mapping_emits_dema() -> None:
    src = _wrap("dema_val = ta.dema(close, 20)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "dema_val" in inds
    assert inds["dema_val"]["type"] == "dema"
    assert inds["dema_val"]["params"] == {"period": 20, "source": "close"}
    _assert_no_coming_soon_note_for(result, "dema")


def test_tema_active_mapping_emits_tema() -> None:
    src = _wrap("tema_val = ta.tema(close, 20)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "tema_val" in inds
    assert inds["tema_val"]["type"] == "tema"
    _assert_no_coming_soon_note_for(result, "tema")


def test_hma_active_mapping_emits_hull_ma() -> None:
    src = _wrap("hma_val = ta.hma(close, 20)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "hma_val" in inds
    assert inds["hma_val"]["type"] == "hull_ma"
    assert inds["hma_val"]["params"] == {"period": 20, "source": "close"}
    _assert_no_coming_soon_note_for(result, "hma")


def test_supertrend_active_mapping_emits_supertrend() -> None:
    """Pine arg order is ``(factor, atrPeriod)`` — opposite of the
    registry's ``(period, multiplier)``. Mapper must swap correctly."""
    src = _wrap("st_val = ta.supertrend(3.0, 10)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "st_val" in inds
    assert inds["st_val"]["type"] == "supertrend"
    assert inds["st_val"]["params"] == {"period": 10, "multiplier": 3.0}
    _assert_no_coming_soon_note_for(result, "supertrend")


def test_psar_active_mapping_emits_parabolic_sar() -> None:
    """Pine ``ta.psar(start, increment, max)`` -> registry
    ``(step, max_step)``. We map ``increment -> step`` and
    ``max -> max_step``."""
    src = _wrap("psar_val = ta.psar(0.02, 0.02, 0.2)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "psar_val" in inds
    assert inds["psar_val"]["type"] == "parabolic_sar"
    assert inds["psar_val"]["params"] == {"step": 0.02, "max_step": 0.2}
    _assert_no_coming_soon_note_for(result, "psar")


# ─── Momentum (5 of the 13 promoted) ──────────────────────────────────


def test_cci_active_mapping_emits_cci() -> None:
    src = _wrap("cci_val = ta.cci(close, 20)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "cci_val" in inds
    assert inds["cci_val"]["type"] == "cci"
    assert inds["cci_val"]["params"] == {"period": 20}
    _assert_no_coming_soon_note_for(result, "cci")


def test_williams_r_active_mapping_emits_williams_r() -> None:
    src = _wrap("wr_val = ta.williams_r(close, high, low, 14)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "wr_val" in inds
    assert inds["wr_val"]["type"] == "williams_r"
    assert inds["wr_val"]["params"] == {"period": 14}
    _assert_no_coming_soon_note_for(result, "williams_r")


def test_cmo_active_mapping_emits_chande_momentum() -> None:
    """Brand-new active mapping (``cmo`` was never in the importer)."""
    src = _wrap("cmo_val = ta.cmo(close, 9)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "cmo_val" in inds
    assert inds["cmo_val"]["type"] == "chande_momentum"
    assert inds["cmo_val"]["params"] == {"period": 9, "source": "close"}


def test_stoch_active_mapping_emits_stochastic_with_default_d_period() -> None:
    """Pine ``ta.stoch`` only surfaces the %K period; the registry's
    Stochastic also takes ``d_period`` (default 3)."""
    src = _wrap("stoch_val = ta.stoch(close, high, low, 14)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "stoch_val" in inds
    assert inds["stoch_val"]["type"] == "stochastic"
    assert inds["stoch_val"]["params"] == {"k_period": 14, "d_period": 3}
    _assert_no_coming_soon_note_for(result, "stoch")


def test_roc_active_mapping_emits_roc() -> None:
    src = _wrap("roc_val = ta.roc(close, 12)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "roc_val" in inds
    assert inds["roc_val"]["type"] == "roc"
    assert inds["roc_val"]["params"] == {"period": 12, "source": "close"}
    _assert_no_coming_soon_note_for(result, "roc")


# ─── Volume / Channels (3 of the 13 promoted) ─────────────────────────


def test_mfi_active_mapping_emits_mfi() -> None:
    src = _wrap("mfi_val = ta.mfi(close, 14)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "mfi_val" in inds
    assert inds["mfi_val"]["type"] == "mfi"
    assert inds["mfi_val"]["params"] == {"period": 14}
    _assert_no_coming_soon_note_for(result, "mfi")


def test_donchian_active_mapping_emits_donchian_channel() -> None:
    src = _wrap("dc_val = ta.donchian(20)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "dc_val" in inds
    assert inds["dc_val"]["type"] == "donchian_channel"
    assert inds["dc_val"]["params"] == {"period": 20}
    _assert_no_coming_soon_note_for(result, "donchian")


def test_keltner_active_mapping_emits_keltner_channel() -> None:
    src = _wrap("kc_val = ta.keltner(close, 20, 2.0)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "kc_val" in inds
    assert inds["kc_val"]["type"] == "keltner_channel"
    assert inds["kc_val"]["params"] == {"period": 20, "multiplier": 2.0}
    _assert_no_coming_soon_note_for(result, "keltner")


# ─── Coexistence + StrategyJSON validation ────────────────────────────


def test_active_pack2_mappings_keep_strategy_validatable() -> None:
    """A snippet mixing a half-dozen Pack 2 active mappings with a
    Phase-7 EMA round-trips through ``StrategyJSON.model_validate``
    cleanly. Pins that no Pack 2 branch leaks a malformed shape."""
    src = _wrap(
        "ema_a = ta.ema(close, 21)\n"
        "vwma_a = ta.vwma(close, 20)\n"
        "st_a = ta.supertrend(3.0, 10)\n"
        "cci_a = ta.cci(close, 14)\n"
        "dc_a = ta.donchian(20)\n"
        "mfi_a = ta.mfi(close, 14)\n"
        "stoch_a = ta.stoch(close, high, low, 14)"
    )
    result = convert_pine_to_strategy(src)
    assert result["success"] is True or result.get("partial") is True
    StrategyJSON.model_validate(result["strategy"])


def test_remaining_coming_soon_mappings_still_emit_notes() -> None:
    """Sanity — the 3 names that DIDN'T get promoted in Pack 2 still
    surface a coming_soon note (so users know what's pending)."""
    for pine_name, registry_id in (
        ("stoch_rsi", "stoch_rsi"),
        ("mom", "momentum"),
        ("heikinashi", "heikin_ashi"),
    ):
        src = _wrap(f"x_{pine_name} = ta.{pine_name}(close, 14)")
        result = convert_pine_to_strategy(src)
        notes = _notes(result)
        assert any(registry_id in n and "coming_soon" in n for n in notes), (
            f"``ta.{pine_name}`` lost its coming_soon note in the cleanup"
        )
