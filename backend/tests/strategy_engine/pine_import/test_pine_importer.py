"""Pine importer — converts Pine v5/v6 source to a Tradetri StrategyJSON.

The 10-test matrix covers each of the spec's required scenarios:

    1.  ta.ema converts correctly
    2.  ta.rsi converts correctly
    3.  ta.crossover produces a CROSSOVER condition
    4.  request.security returns an unsupported warning (blocked)
    5.  Array usage returns an unsupported warning (blocked)
    6.  Protected / invite-only source is blocked
    7.  Unknown license becomes needs_review
    8.  Partial conversion returns partial=True with a non-empty
        unsupported list
    9.  Resulting StrategyJSON validates against the Phase 1 schema
    10. AST-inspect this importer module — no eval / exec / compile /
        __import__ / subprocess code path exists
"""

from __future__ import annotations

import ast
import pathlib

from app.strategy_engine.pine_import import (
    convert_pine_to_strategy,
    validate_source,
)
from app.strategy_engine.pine_import.validator import LicenseStatus
from app.strategy_engine.schema.strategy import StrategyJSON

# ─── 1-2. Indicator conversion ─────────────────────────────────────────


def test_ema_converts_to_ema_indicator_with_correct_period_and_source() -> None:
    source = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("EMA test", overlay=true)
ema_fast = ta.ema(close, 9)
ema_slow = ta.ema(close, 21)
buy_signal = ta.crossover(ema_fast, ema_slow)
if buy_signal
    strategy.entry("Long", strategy.long)
"""
    result = convert_pine_to_strategy(source)

    assert result["success"] is True
    indicators = result["strategy"]["indicators"]
    by_id = {ind["id"]: ind for ind in indicators}
    assert "ema_fast" in by_id
    assert by_id["ema_fast"]["type"] == "ema"
    assert by_id["ema_fast"]["params"]["period"] == 9
    assert by_id["ema_fast"]["params"]["source"] == "close"
    assert by_id["ema_slow"]["params"]["period"] == 21


def test_rsi_converts_to_rsi_indicator_with_period_and_source() -> None:
    source = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("RSI test")
rsi_value = ta.rsi(close, 14)
"""
    result = convert_pine_to_strategy(source)

    # No entry signal in this source — converter inserts a placeholder
    # price > 0 condition so the schema still passes.
    assert result["success"] is True
    indicators = result["strategy"]["indicators"]
    assert len(indicators) == 1
    assert indicators[0]["type"] == "rsi"
    assert indicators[0]["params"]["period"] == 14


# ─── 3. crossover → CROSSOVER condition ───────────────────────────────


def test_crossover_emits_crossover_condition_pointing_at_indicator_ids() -> None:
    source = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("Cross test")
ema_fast = ta.ema(close, 9)
ema_slow = ta.ema(close, 21)
buy_signal = ta.crossover(ema_fast, ema_slow)
if buy_signal
    strategy.entry("Long", strategy.long)
"""
    result = convert_pine_to_strategy(source)

    assert result["success"] is True
    conditions = result["strategy"]["entry"]["conditions"]
    assert len(conditions) == 1
    cond = conditions[0]
    assert cond["type"] == "indicator"
    assert cond["op"] == "crossover"
    assert cond["left"] == "ema_fast"
    assert cond["right"] == "ema_slow"
    assert result["strategy"]["entry"]["side"] == "BUY"


# ─── 4-5. Prohibited constructs blocked ───────────────────────────────


def test_request_security_blocks_import_with_explanatory_message() -> None:
    source = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("Multi-symbol")
htf_close = request.security(syminfo.tickerid, "60", close)
ema_value = ta.ema(htf_close, 14)
"""
    result = convert_pine_to_strategy(source)

    assert result["success"] is False
    assert any("request.security" in u for u in result["unsupported"])
    assert "request.security" in result["message"]


def test_array_usage_blocks_import() -> None:
    source = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("Array script")
levels = array.new_float(0)
ema_value = ta.ema(close, 14)
"""
    result = convert_pine_to_strategy(source)

    assert result["success"] is False
    assert any("array" in u.lower() for u in result["unsupported"])


# ─── 6. Protected source blocked ──────────────────────────────────────


def test_protected_invite_only_source_is_blocked_at_validation_step() -> None:
    source = """\
//@version=5
// © Author — protected, invite-only access. Contact for licensing.
strategy("Secret edge")
ema_value = ta.ema(close, 14)
"""
    result = convert_pine_to_strategy(source)

    assert result["success"] is False
    assert result["license_status"] == LicenseStatus.BLOCKED.value
    assert "protected" in result["message"].lower() or "invite" in result["message"].lower()


# ─── 7. Unknown license → needs_review ────────────────────────────────


def test_source_without_license_marker_is_classified_needs_review() -> None:
    source = """\
//@version=5
strategy("No license")
ema_value = ta.ema(close, 14)
"""
    report = validate_source(source)
    assert report.license_status is LicenseStatus.NEEDS_REVIEW

    result = convert_pine_to_strategy(source)
    # needs_review still imports — the UI surfaces the flag.
    assert result["success"] is True
    assert result["license_status"] == LicenseStatus.NEEDS_REVIEW.value


# ─── 8. Partial conversion shape ──────────────────────────────────────


def test_partial_conversion_emits_partial_true_with_unsupported_list() -> None:
    """An unsupported ``ta.<func>`` plus a supported one yields a partial."""
    source = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("Partial")
ema_value = ta.ema(close, 14)
sma_obscure = ta.alma(close, 9, 0.85, 6)
"""
    result = convert_pine_to_strategy(source)

    assert result["success"] is False
    assert result["partial"] is True
    assert result["converted"] is not None
    assert any("ta.alma" in u for u in result["unsupported"])
    # The successfully-converted indicator survives in the partial draft.
    converted_ids = {ind["id"] for ind in result["converted"]["indicators"]}
    assert "ema_value" in converted_ids


# ─── 9. Output validates against StrategyJSON ─────────────────────────


def test_successful_import_round_trips_through_strategy_json_schema() -> None:
    """The strategy dict re-validates with no errors via Phase 1's schema."""
    source = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("Schema round trip")
ema_fast = ta.ema(close, 9)
ema_slow = ta.ema(close, 21)
buy_signal = ta.crossover(ema_fast, ema_slow)
if buy_signal
    strategy.entry("Long", strategy.long)
"""
    result = convert_pine_to_strategy(source)
    assert result["success"] is True

    revalidated = StrategyJSON.model_validate(result["strategy"])
    # Indicator and entry shapes survive the round-trip.
    assert {ind.id for ind in revalidated.indicators} == {"ema_fast", "ema_slow"}
    assert revalidated.entry.conditions[0].type == "indicator"


# ─── 10. No dynamic-code execution path ───────────────────────────────


_DANGEROUS_NAMES: frozenset[str] = frozenset(
    {"eval", "exec", "compile", "__import__"}
)
_DANGEROUS_MODULES: frozenset[str] = frozenset(
    {"subprocess", "ctypes", "marshal"}
)


def test_no_dynamic_code_execution_in_pine_import_package() -> None:
    """AST-walk every .py under app/strategy_engine/pine_import/.

    Asserts none of them call ``eval``/``exec``/``compile``/
    ``__import__`` or import ``subprocess``/``ctypes``/``marshal``.
    This makes the spec's "Do NOT execute Pine code under any
    circumstance" rule load-bearing — a future contributor that
    introduces a dynamic-execution path will break this test.
    """
    pkg_root = (
        pathlib.Path(__file__).resolve().parents[3]
        / "app"
        / "strategy_engine"
        / "pine_import"
    )
    assert pkg_root.is_dir(), f"pine_import package not found at {pkg_root}"

    offenders: list[str] = []
    for py_file in pkg_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in _DANGEROUS_NAMES:
                    offenders.append(f"{py_file.name}:{node.lineno} calls {func.id}()")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in _DANGEROUS_MODULES:
                        offenders.append(
                            f"{py_file.name}:{node.lineno} imports {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in _DANGEROUS_MODULES:
                    offenders.append(
                        f"{py_file.name}:{node.lineno} imports from {node.module}"
                    )

    assert not offenders, (
        "Pine importer must remain execution-free, but found:\n  - "
        + "\n  - ".join(offenders)
    )
