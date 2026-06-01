"""Sprint 4a — corrected reference handler for the 9 Sprint 3 D-tier indicators.

Two corrections vs Sprint 3's `references.py`:

1. **Per-indicator parameter overrides** — Sprint 3 passed a single
   `default_period=14` positional, which broke any indicator whose talib
   signature uses different / multiple period args (ADOSC, ULTOSC, VAR).

2. **Tuple column selection** — Sprint 3 took `out[0]` for any tuple
   return, which paired TRADETRI's `aroon_up` against talib's
   `aroon_down` (talib.AROON returns `(down, up)` not `(up, down)`).

Per spec: framework fixes only, NO indicator math touched.
"""

from __future__ import annotations

import numpy as np


#: Per-indicator kwargs to pass into the talib reference call. These
#: match TRADETRI's default parameters as read from the impl source
#: (e.g. trix.py default period=15, chande_momentum.py default period=9).
TALIB_PARAM_OVERRIDES: dict[str, dict[str, int]] = {
    # Aroon family
    "aroon":              {"timeperiod": 25},  # TRADETRI default 25
    "aroon_up":           {"timeperiod": 14},
    "aroon_down":         {"timeperiod": 14},
    "aroon_oscillator":   {"timeperiod": 14},
    # Multi-period indicators that need explicit args
    "chaikin_oscillator": {"fastperiod": 3, "slowperiod": 10},
    "chande_momentum":    {"timeperiod": 9},
    "trix":               {"timeperiod": 15},
    "ultimate_oscillator": {
        "timeperiod1": 7, "timeperiod2": 14, "timeperiod3": 28,
    },
    "variance":           {"timeperiod": 20, "nbdev": 1},
}


#: Which column of a tuple return to select for TRADETRI-vs-talib comparison.
#: talib.AROON return order is (aroondown, aroonup). TRADETRI's `aroon`
#: returns (up, down, oscillator), so its [0] is up → compare against
#: talib.AROON[1] (up).
TALIB_TUPLE_COLUMN: dict[str, int] = {
    "aroon":      1,  # TRADETRI[0]=up → talib.AROON[1]=up
    "aroon_up":   1,  # TRADETRI returns scalar → talib.AROON[1]=up
    "aroon_down": 0,  # TRADETRI returns scalar → talib.AROON[0]=down
}


#: Forward-mapping for which TRADETRI output column to take BEFORE comparison.
#: When TRADETRI returns a tuple, this picks which element matches the
#: expected "primary" output for comparison purposes.
TRADETRI_TUPLE_COLUMN: dict[str, int] = {
    "aroon":      0,  # take aroon_up from TRADETRI's (up, down, osc)
    # aroon_up, aroon_down, aroon_oscillator return scalar lists — no tuple
    # access needed.
}


TALIB_MAP_4A = {
    "aroon":              "AROON",
    "aroon_up":           "AROON",
    "aroon_down":         "AROON",
    "aroon_oscillator":   "AROONOSC",
    "chaikin_oscillator": "ADOSC",
    "chande_momentum":    "CMO",
    "trix":               "TRIX",
    "ultimate_oscillator": "ULTOSC",
    "variance":           "VAR",
}


def call_talib_with_overrides(
    module_name: str,
    arrays: dict[str, np.ndarray],
):
    """Invoke the talib reference with the right kwargs + column for ``module_name``.

    Returns ``(np.ndarray | None, talib_name)``. Only handles the 9 Sprint 3
    D-tier indicators by design — caller resolves anything else through the
    Sprint 3 reference cascade.
    """
    import talib

    talib_name = TALIB_MAP_4A.get(module_name)
    if talib_name is None:
        return None, ""
    fn = getattr(talib, talib_name, None)
    if fn is None:
        return None, ""

    kwargs = TALIB_PARAM_OVERRIDES.get(module_name, {})

    high = arrays["high"]
    low = arrays["low"]
    close = arrays["close"]
    volume = arrays["volume"]

    # Each of the 9 is matched explicitly so the positional argument order
    # is unambiguous (no auto-routing surprises).
    try:
        if module_name in ("aroon", "aroon_up", "aroon_down", "aroon_oscillator"):
            out = fn(high, low, **kwargs)
        elif module_name == "chaikin_oscillator":
            out = fn(high, low, close, volume, **kwargs)
        elif module_name == "chande_momentum":
            out = fn(close, **kwargs)
        elif module_name == "trix":
            out = fn(close, **kwargs)
        elif module_name == "ultimate_oscillator":
            out = fn(high, low, close, **kwargs)
        elif module_name == "variance":
            out = fn(close, **kwargs)
        else:
            return None, ""
    except Exception as e:
        return None, f"talib.{talib_name}(...) error: {type(e).__name__}: {e}"

    # Select column if talib returns a tuple
    if isinstance(out, tuple):
        col = TALIB_TUPLE_COLUMN.get(module_name, 0)
        out = out[col]

    return out, f"talib.{talib_name}" + (
        f"[col={TALIB_TUPLE_COLUMN[module_name]}]" if module_name in TALIB_TUPLE_COLUMN else ""
    )


def select_tradetri_output(module_name: str, raw_output):
    """Pick which element of TRADETRI's return to compare against talib.

    For `aroon` (returns 3-tuple up/down/osc), the comparison target is
    aroon_up (column 0). All other Sprint 4a indicators return a scalar
    list, so this passes through.
    """
    if isinstance(raw_output, tuple):
        col = TRADETRI_TUPLE_COLUMN.get(module_name, 0)
        return raw_output[col]
    return raw_output


__all__ = [
    "TALIB_MAP_4A",
    "TALIB_PARAM_OVERRIDES",
    "TALIB_TUPLE_COLUMN",
    "TRADETRI_TUPLE_COLUMN",
    "call_talib_with_overrides",
    "select_tradetri_output",
]
