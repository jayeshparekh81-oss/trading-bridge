"""Pine Importer — Batch 1 expanded mappings.

Phase 7 shipped 9 ``ta.<func>`` mappings (ema, sma, rsi, macd, bb,
atr, vwap, highest, lowest). This batch adds 22 more — six ACTIVE
mappings that produce real indicator dicts, sixteen COMING_SOON
mappings that match a recognised registry id but surface a note
(same pattern as Phase 7's ``highest``/``lowest``) because the
calculation function isn't shipped yet.

Each test parses one Pine snippet through
:func:`convert_pine_to_strategy` and asserts the contract:

    * ACTIVE — indicator appears in ``result["strategy"]["indicators"]``
      with the right ``type`` + ``params``.
    * COMING_SOON — indicator does NOT appear in the strategy, but
      ``result["notes"]`` contains a line naming the registry id so
      the user knows which feature they're waiting on.

The tests use the smallest valid Pine snippet that exercises the
function — header + one ``strategy.entry`` so the converter accepts
the program. Where a function takes positional args (period,
source), we pin both to a non-default value so a regression in the
arg-order handling shows up here.
"""

from __future__ import annotations

from app.strategy_engine.pine_import import convert_pine_to_strategy

# ─── Helpers ───────────────────────────────────────────────────────────


_PINE_HEADER = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("Batch1 test")
"""

_TRIGGER_TAIL = """
trigger = ta.crossover(close, open)
if trigger
    strategy.entry("Long", strategy.long)
"""


def _wrap(indicator_line: str) -> str:
    """Glue header + the indicator line + a no-op entry trigger."""
    return f"{_PINE_HEADER}{indicator_line}\n{_TRIGGER_TAIL}"


def _by_id(result: dict[str, object]) -> dict[str, dict[str, object]]:
    indicators = result["strategy"]["indicators"]  # type: ignore[index]
    return {ind["id"]: ind for ind in indicators}  # type: ignore[index, attr-defined]


def _notes(result: dict[str, object]) -> list[str]:
    notes = result.get("notes")
    return list(notes) if isinstance(notes, list) else []


# ─── ACTIVE mappings — indicator appears in the output ────────────────


def test_wma_active_mapping_emits_wma_with_period_and_source() -> None:
    src = _wrap("wma_main = ta.wma(close, 30)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "wma_main" in inds
    assert inds["wma_main"]["type"] == "wma"
    assert inds["wma_main"]["params"] == {"period": 30, "source": "close"}


def test_adx_active_mapping_emits_adx_with_period() -> None:
    src = _wrap("adx_val = ta.adx(20)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "adx_val" in inds
    assert inds["adx_val"]["type"] == "adx"
    assert inds["adx_val"]["params"] == {"period": 20}


def test_cmf_active_mapping_emits_cmf_with_period() -> None:
    src = _wrap("cmf_val = ta.cmf(25)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "cmf_val" in inds
    assert inds["cmf_val"]["type"] == "cmf"
    assert inds["cmf_val"]["params"] == {"period": 25}


def test_trix_active_mapping_emits_trix_with_period_and_source() -> None:
    src = _wrap("trix_val = ta.trix(close, 18)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "trix_val" in inds
    assert inds["trix_val"]["type"] == "trix"
    assert inds["trix_val"]["params"] == {"period": 18, "source": "close"}


def test_aroon_active_mapping_emits_aroon_with_period() -> None:
    src = _wrap("aroon_val = ta.aroon(30)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "aroon_val" in inds
    assert inds["aroon_val"]["type"] == "aroon"
    assert inds["aroon_val"]["params"] == {"period": 30}


def test_obv_active_mapping_emits_obv_with_no_params() -> None:
    # The Phase-7 parser recognises ``ta.<fn>(args)`` syntax; modern
    # Pine v5 surfaces ``ta.obv`` as a parameter-less built-in
    # (no parens), but the parser's call-assign regex requires the
    # parens. Users who want OBV via the importer write ``ta.obv()``
    # — same shape as ``ta.vwap(...)`` already does. Tested with
    # parens so the contract matches the parser surface.
    src = _wrap("obv_val = ta.obv()")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "obv_val" in inds
    assert inds["obv_val"]["type"] == "obv"
    assert inds["obv_val"]["params"] == {}


# ─── ACTIVE — defaults applied when args omitted ─────────────────────


def test_wma_default_period_when_args_omitted() -> None:
    src = _wrap("wma_def = ta.wma(close)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    # Default period for WMA is 20 (mirrors the registry InputSpec).
    assert inds["wma_def"]["params"]["period"] == 20


def test_adx_default_period_when_args_omitted() -> None:
    src = _wrap("adx_def = ta.adx()")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    # Default period for ADX is 14.
    assert inds["adx_def"]["params"]["period"] == 14


# ─── COMING_SOON mappings — note emitted, indicator dropped ───────────


# Only entries whose registry calc still isn't shipped. The 13
# Pack 2 promotions (commit 511f591 + dispatch follow-up) live in
# ``test_pack2_active_mappings.py`` instead.
_COMING_SOON_PINE_TO_REGISTRY = {
    "stoch_rsi": "stoch_rsi",
    "mom": "momentum",
    "heikinashi": "heikin_ashi",
}


def test_stoch_rsi_coming_soon_mapping_notes_stoch_rsi() -> None:
    src = _wrap("srsi_val = ta.stoch_rsi(close, 14)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "srsi_val" not in inds
    assert any("stoch_rsi" in n for n in _notes(result))


def test_mom_coming_soon_mapping_notes_momentum() -> None:
    src = _wrap("mom_val = ta.mom(close, 10)")
    result = convert_pine_to_strategy(src)
    assert "mom_val" not in _by_id(result)
    assert any("momentum" in n for n in _notes(result))


def test_heikinashi_coming_soon_mapping_notes_heikin_ashi() -> None:
    src = _wrap("ha_val = ta.heikinashi(close)")
    result = convert_pine_to_strategy(src)
    assert "ha_val" not in _by_id(result)
    assert any("heikin_ashi" in n for n in _notes(result))


# ─── Edge cases ───────────────────────────────────────────────────────


def test_phase7_originals_still_emit_unchanged() -> None:
    """Regression — original Phase 7 mappings keep working after the
    Batch 1 extension. Pins ``ema`` (most-used) and ``vwap`` (no-param
    edge case) so a stray refactor of the mapper trips here."""
    src = _wrap("ema_val = ta.ema(close, 21)\nvwap_val = ta.vwap(close)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert inds["ema_val"]["type"] == "ema"
    assert inds["ema_val"]["params"] == {"period": 21, "source": "close"}
    assert inds["vwap_val"]["type"] == "vwap"
    assert inds["vwap_val"]["params"] == {}


def test_unrecognised_pine_function_is_skipped_silently() -> None:
    """Functions outside ``SUPPORTED_TA_INDICATORS`` (e.g. ``ta.tsi``,
    ``ta.cog``) are dropped at the parser layer — the converter
    doesn't surface a Batch-1-style ``coming_soon`` note that could
    confuse the user about whether the indicator is supported."""
    src = _wrap("tsi_val = ta.tsi(close, 25, 13)")
    result = convert_pine_to_strategy(src)
    # The converter may classify this as a failed import (no recognised
    # indicators in the source) — that's fine; the contract this test
    # pins is just "no Batch-1-style coming_soon note for ``ta.tsi``".
    notes = _notes(result)
    assert not any("ta.tsi" in n and "coming_soon" in n for n in notes)
    # And if the strategy did emit, the indicator is absent from it.
    if "strategy" in result:
        assert "tsi_val" not in _by_id(result)


def test_coming_soon_note_includes_registry_id_for_every_pine_name() -> None:
    """One sweep over every Batch-1 coming-soon mapping — each emits a
    note that names the canonical registry id so users know exactly
    which feature is pending."""
    for pine_name, registry_id in _COMING_SOON_PINE_TO_REGISTRY.items():
        # Each call uses a single argument so the parser can read it
        # uniformly — variations are exercised in the per-mapping
        # tests above.
        src = _wrap(f"x_{pine_name} = ta.{pine_name}(close, 14)")
        result = convert_pine_to_strategy(src)
        notes = _notes(result)
        assert any(registry_id in n for n in notes), (
            f"Pine ``ta.{pine_name}`` did not produce a note naming "
            f"the registry id ``{registry_id}``"
        )


def test_active_mappings_keep_strategy_validatable() -> None:
    """A snippet that uses every Batch-1 ACTIVE mapping plus one
    cross trigger produces a StrategyJSON the schema accepts. Pins
    that the new branches don't slip a malformed shape that would
    crash the converter's downstream Pydantic validation."""
    from app.strategy_engine.schema.strategy import StrategyJSON

    src = _wrap(
        "wma_a = ta.wma(close, 20)\n"
        "adx_a = ta.adx(14)\n"
        "cmf_a = ta.cmf(20)\n"
        "trix_a = ta.trix(close, 15)\n"
        "aroon_a = ta.aroon(25)\n"
        "obv_a = ta.obv"
    )
    result = convert_pine_to_strategy(src)
    assert result["success"] is True or result.get("partial") is True
    # The strategy dict the converter produced must round-trip the
    # validator without raising.
    StrategyJSON.model_validate(result["strategy"])
