"""Tape calibration config — loads tape_config.yaml, all knobs UNCALIBRATED.

Kept in a SEPARATE file from the recorders' config.yaml so the heavy, iterative
recalibration of these knobs never touches (or risks) the live R0/R1 container
config. Every knob has a safe default; ``uncalibrated()`` lists the ones still at
their placeholder so the CLI/notes can surface them.
"""

from __future__ import annotations

from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent.parent  # orderflow_engine/

# Instrument classes (select which per-class knob applies).
CLS_INDEX_FUT = "index_fut"
CLS_STOCK = "stock"
CLS_OPTION = "option"

# Defaults. Structural knobs are functional; threshold detectors are INERT (0 =
# "off until calibrated"). Keys mirrored in tape_config.yaml.
DEFAULTS = {
    "bars": {
        "tick_bar_size": 100,          # functional structural default
        "volume_bar_enabled": True,
        "volume_bar_threshold": {CLS_INDEX_FUT: 0, CLS_STOCK: 0, CLS_OPTION: 0},  # 0 = inert
    },
    "classify": {
        "method": "lee_ready",         # lee_ready | tick_rule
        "trade_size": "volume_delta",  # volume_delta (default) | ltq
    },
    "cvd": {"slope_window_bars": 20},
    "bigprint": {
        "notional_threshold": {CLS_INDEX_FUT: 0, CLS_STOCK: 0, CLS_OPTION: 0},   # 0 = inert
        "cluster_k": 3,
        "cluster_window_s": 10,
    },
    "velocity": {"baseline_bars": 20, "spike_ratio": 0.5},
    "depth": {"imbalance_levels": 5, "ofi_enabled": False},
}

# Knobs whose default is a placeholder that MUST be set from replay evidence
# before the corresponding output is meaningful. (dotted path -> reason)
UNCALIBRATED_KNOBS = {
    "bars.tick_bar_size": "structural default; confirm vs bar-duration distribution",
    "bars.volume_bar_threshold.*": "INERT (0) until per-class traded-volume distribution seen",
    "cvd.slope_window_bars": "structural default; confirm vs signal horizon",
    "bigprint.notional_threshold.*": "INERT (0) until per-class trade-notional distribution seen",
    "bigprint.cluster_k": "confirm vs observed print clustering",
    "bigprint.cluster_window_s": "confirm vs observed print clustering",
    "velocity.baseline_bars": "structural default; confirm vs session bar counts",
    "velocity.spike_ratio": "structural default; confirm vs velocity distribution",
    "depth.ofi_enabled": "OFI weights UNCALIBRATED; enable after R1 depth replay",
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def classify_instrument(symbol: str) -> str:
    """Map an instrument symbol to a class for per-class knob selection."""
    s = (symbol or "").upper()
    if "_CE_" in s or "_PE_" in s:
        return CLS_OPTION
    if s.endswith("_FUT") or "_FUT_" in s:
        return CLS_INDEX_FUT
    return CLS_STOCK


class TapeConfig:
    def __init__(self, cfg: dict | None = None):
        self.d = _merge(DEFAULTS, (cfg or {}).get("tape", cfg or {}))

    # -- bars ---------------------------------------------------------------
    @property
    def tick_bar_size(self) -> int:
        return int(self.d["bars"]["tick_bar_size"])

    @property
    def volume_bar_enabled(self) -> bool:
        return bool(self.d["bars"]["volume_bar_enabled"])

    def volume_bar_threshold(self, symbol: str) -> int:
        return int(self.d["bars"]["volume_bar_threshold"].get(
            classify_instrument(symbol), 0))

    # -- classify -----------------------------------------------------------
    @property
    def classify_method(self) -> str:
        return str(self.d["classify"]["method"])

    @property
    def trade_size_mode(self) -> str:
        return str(self.d["classify"]["trade_size"])

    # -- cvd ----------------------------------------------------------------
    @property
    def cvd_slope_window(self) -> int:
        return int(self.d["cvd"]["slope_window_bars"])

    # -- bigprint -----------------------------------------------------------
    def bigprint_notional(self, symbol: str) -> float:
        return float(self.d["bigprint"]["notional_threshold"].get(
            classify_instrument(symbol), 0))

    @property
    def cluster_k(self) -> int:
        return int(self.d["bigprint"]["cluster_k"])

    @property
    def cluster_window_s(self) -> float:
        return float(self.d["bigprint"]["cluster_window_s"])

    # -- velocity -----------------------------------------------------------
    @property
    def velocity_baseline_bars(self) -> int:
        return int(self.d["velocity"]["baseline_bars"])

    @property
    def velocity_spike_ratio(self) -> float:
        return float(self.d["velocity"]["spike_ratio"])

    # -- depth --------------------------------------------------------------
    @property
    def depth_imbalance_levels(self) -> int:
        return int(self.d["depth"]["imbalance_levels"])

    @property
    def depth_ofi_enabled(self) -> bool:
        return bool(self.d["depth"]["ofi_enabled"])

    def uncalibrated(self) -> list[str]:
        """Knobs still at an inert/placeholder value (for the run summary)."""
        out = []
        for cls in (CLS_INDEX_FUT, CLS_STOCK, CLS_OPTION):
            if self.d["bigprint"]["notional_threshold"].get(cls, 0) == 0:
                out.append(f"bigprint.notional_threshold.{cls} (INERT)")
            if self.d["bars"]["volume_bar_threshold"].get(cls, 0) == 0:
                out.append(f"bars.volume_bar_threshold.{cls} (INERT)")
        if not self.depth_ofi_enabled:
            out.append("depth.ofi_enabled (off)")
        return out


def load_tape_config(path: str | Path | None = None) -> TapeConfig:
    p = Path(path) if path else HERE / "tape_config.yaml"
    if not p.exists():
        return TapeConfig({})
    return TapeConfig(yaml.safe_load(p.read_text()) or {})
