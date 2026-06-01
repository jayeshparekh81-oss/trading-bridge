"""Sprint 3 — auto-discovery of indicators in calculations/.

Returns a list of (module_name, primary_function_name, signature_kind).

signature_kind classifies the input shape needed:
    C       — closes only
    HL      — highs, lows (no closes)
    HLC     — highs, lows, closes
    HLCV    — highs, lows, closes, volumes
    CV      — closes, volumes
    OHLC    — open, high, low, close
    OHLCV   — full OHLCV
    SCALAR  — takes a value (chain/composed indicators)
    UNKNOWN — couldn't parse; flag NEEDS_MANUAL_REVIEW
"""

from __future__ import annotations

import inspect
import importlib
from pathlib import Path


CALC_DIR = Path("/Users/jayeshparekh/trading-bridge-chart/backend/app/strategy_engine/indicators/calculations")

SKIP_MODULES = {
    "macd", "sma", "ema", "rsi", "bollinger_bands", "atr", "vwap",
    "stochastic", "adx", "donchian_channel", "ichimoku", "mfi", "roc", "cci",
}


def discover_modules() -> list[Path]:
    """List all non-underscore .py modules in calculations/."""
    return sorted(
        p for p in CALC_DIR.glob("*.py")
        if not p.stem.startswith("_") and p.stem != "__init__"
    )


def detect_signature_kind(params: list[str]) -> str:
    """Classify the input shape from parameter names."""
    p = set(params)
    has = lambda *names: any(n in p for n in names)
    has_high = has("highs", "high")
    has_low = has("lows", "low")
    has_close = has("closes", "close", "values", "source")
    has_open = has("opens", "open")
    has_volume = has("volumes", "volume")

    if has_open and has_high and has_low and has_close and has_volume:
        return "OHLCV"
    if has_open and has_high and has_low and has_close:
        return "OHLC"
    if has_high and has_low and has_close and has_volume:
        return "HLCV"
    if has_high and has_low and has_close:
        return "HLC"
    if has_high and has_low:
        return "HL"
    if has_close and has_volume:
        return "CV"
    if has_close:
        return "C"
    # No OHLCV-shaped params — likely a composed/chained indicator
    return "SCALAR" if params else "UNKNOWN"


def discover_indicators() -> list[dict]:
    """For each module, find the primary function + its signature kind.

    Returns rows with: module, function, signature_kind, params, defaults_dict.
    Skips modules in SKIP_MODULES.
    """
    rows = []
    for path in discover_modules():
        module_name = path.stem
        if module_name in SKIP_MODULES:
            continue
        # Import via the strategy_engine package path
        try:
            mod = importlib.import_module(
                f"app.strategy_engine.indicators.calculations.{module_name}"
            )
        except Exception as e:
            rows.append({
                "module": module_name,
                "function": "?",
                "signature_kind": "IMPORT_FAIL",
                "params": [],
                "defaults": {},
                "error": f"{type(e).__name__}: {str(e)[:100]}",
            })
            continue

        # Primary function = module-named function, else first public function
        fn = getattr(mod, module_name, None)
        if fn is None or not callable(fn):
            # Try __all__
            all_names = getattr(mod, "__all__", [])
            candidates = [
                n for n in all_names
                if callable(getattr(mod, n, None)) and not n.startswith("_")
            ]
            fn = getattr(mod, candidates[0], None) if candidates else None

        if fn is None:
            rows.append({
                "module": module_name,
                "function": "?",
                "signature_kind": "NO_PUBLIC_FN",
                "params": [],
                "defaults": {},
                "error": "no callable matches module name or __all__[0]",
            })
            continue

        try:
            sig = inspect.signature(fn)
            params = list(sig.parameters.keys())
            defaults = {
                name: p.default
                for name, p in sig.parameters.items()
                if p.default is not inspect.Parameter.empty
            }
            kind = detect_signature_kind(params)
            rows.append({
                "module": module_name,
                "function": fn.__name__,
                "signature_kind": kind,
                "params": params,
                "defaults": defaults,
                "error": "",
            })
        except Exception as e:
            rows.append({
                "module": module_name,
                "function": getattr(fn, "__name__", "?"),
                "signature_kind": "SIG_FAIL",
                "params": [],
                "defaults": {},
                "error": f"{type(e).__name__}: {str(e)[:100]}",
            })
    return rows
