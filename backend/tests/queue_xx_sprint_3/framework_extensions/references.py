"""Sprint 3 — reference cascade: TA-Lib → pandas-ta-classic → NEEDS_HANDROLL.

Returns (reference_array, reference_name) or (None, 'NEEDS_HANDROLL').
"""

from __future__ import annotations

import numpy as np


VOLUME_AWARE_PATTERNS = (
    "mfi", "obv", "vwap", "cmf", "ad_line", "money_flow",
    "chaikin", "volume", "vwac", "accumulation_distribution",
    "buying_pressure", "elder",
)


def is_volume_aware(module_name: str) -> bool:
    return any(p in module_name.lower() for p in VOLUME_AWARE_PATTERNS)


# Map module_name → talib function name (case-insensitive)
TALIB_MAP = {
    "wma": "WMA",
    "trima": "TRIMA",
    "kama": "KAMA",
    "tema": "T3",  # close-ish; actual is T3 = triple EMA; tema=TEMA
    "dema": "DEMA",
    "tema_3": "TEMA",
    "willr": "WILLR",
    "williams_pct_r": "WILLR",
    "ad_line": "AD",
    "adosc": "ADOSC",
    "chaikin_oscillator": "ADOSC",
    "obv": "OBV",
    "natr": "NATR",
    "true_range": "TRANGE",
    "ultimate_oscillator": "ULTOSC",
    "trix": "TRIX",
    "ppo": "PPO",
    "apo": "APO",
    "linear_reg": "LINEARREG",
    "linear_reg_slope": "LINEARREG_SLOPE",
    "linear_reg_intercept": "LINEARREG_INTERCEPT",
    "linear_reg_angle": "LINEARREG_ANGLE",
    "stddev": "STDDEV",
    "variance": "VAR",
    "midpoint": "MIDPOINT",
    "midprice": "MIDPRICE",
    "sar": "SAR",
    "parabolic_sar": "SAR",
    "bop": "BOP",
    "mom": "MOM",
    "momentum": "MOM",
    "minus_di": "MINUS_DI",
    "plus_di": "PLUS_DI",
    "minus_dm": "MINUS_DM",
    "plus_dm": "PLUS_DM",
    "dx": "DX",
    "adxr": "ADXR",
    "aroon_down": "AROON",  # returns down,up pair
    "aroon_up": "AROON",
    "aroon": "AROON",
    "aroon_oscillator": "AROONOSC",
    "ht_trendline": "HT_TRENDLINE",
    "midpoint_price": "MIDPRICE",
    "cci_classic": "CCI",
    "cmo": "CMO",
    "chande_momentum": "CMO",
    "ht_dcperiod": "HT_DCPERIOD",
}


def try_talib_reference(
    module_name: str,
    sig_kind: str,
    arrays: dict[str, np.ndarray],
    default_period: int = 14,
):
    """Try to compute a TA-Lib reference for this indicator.

    Returns (np.ndarray | None, name_str). None if TA-Lib has no match.
    """
    import talib
    talib_fn_name = TALIB_MAP.get(module_name, module_name.upper())
    fn = getattr(talib, talib_fn_name, None)
    if fn is None:
        return None, ""

    high = arrays["high"]
    low = arrays["low"]
    close = arrays["close"]
    volume = arrays["volume"]
    try:
        if sig_kind == "C":
            out = fn(close, default_period)
        elif sig_kind == "HL":
            out = fn(high, low, default_period)
        elif sig_kind == "HLC":
            out = fn(high, low, close, default_period)
        elif sig_kind == "HLCV":
            out = fn(high, low, close, volume, default_period)
        elif sig_kind == "CV":
            out = fn(close, volume)
        elif sig_kind in ("OHLC", "OHLCV"):
            try:
                out = fn(arrays["open"], high, low, close)
            except TypeError:
                return None, ""
        else:
            return None, ""
        if isinstance(out, tuple):
            out = out[0]  # primary output
        return out, f"talib.{talib_fn_name}"
    except Exception:
        return None, ""
