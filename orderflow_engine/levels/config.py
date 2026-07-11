"""Levels calibration config — reads the `levels:` block of tape_config.yaml.

Shares the tape config FILE (one calibration surface for R3+R4) but its own block.
Reuses tape.config.classify_instrument for per-class knobs. Same doctrine:
structural knobs functional, signal-firing flags (HVN/LVN) INERT at 0.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from tape.config import CLS_INDEX_FUT, CLS_OPTION, CLS_STOCK, classify_instrument

HERE = Path(__file__).resolve().parent.parent  # orderflow_engine/

DEFAULTS = {
    "vwap": {
        "bands": [1.0, 2.0],            # SD band multipliers (structural, functional)
        "snapshot_every_trades": 100,   # cadence of VWAP snapshots to the output
    },
    "volume_profile": {
        "bin_size": {CLS_INDEX_FUT: 5.0, CLS_STOCK: 0.5, CLS_OPTION: 1.0},  # functional
        "value_area_pct": 0.70,
        "hvn_threshold": 0,             # INERT (0) — signal flag off until calibrated
        "lvn_threshold": 0,             # INERT (0)
    },
    "pivots": {"set": "classic"},
    "prior_levels": {
        # descriptive-context knob: ships FUNCTIONAL (not a trade-firing signal)
        "gap_threshold_pct": {CLS_INDEX_FUT: 0.3, CLS_STOCK: 0.5},
    },
    "historical": {"cache_dir": "cache/historical", "daily_lookback_days": 60},
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class LevelsConfig:
    def __init__(self, cfg: dict | None = None):
        blk = (cfg or {}).get("levels", {}) if isinstance(cfg, dict) else {}
        self.d = _merge(DEFAULTS, blk)

    @property
    def vwap_bands(self) -> list[float]:
        return [float(x) for x in self.d["vwap"]["bands"]]

    @property
    def snapshot_every_trades(self) -> int:
        return max(1, int(self.d["vwap"]["snapshot_every_trades"]))

    def bin_size(self, symbol: str) -> float:
        return float(self.d["volume_profile"]["bin_size"].get(classify_instrument(symbol), 1.0))

    @property
    def value_area_pct(self) -> float:
        return float(self.d["volume_profile"]["value_area_pct"])

    @property
    def hvn_threshold(self) -> float:
        return float(self.d["volume_profile"]["hvn_threshold"])

    @property
    def lvn_threshold(self) -> float:
        return float(self.d["volume_profile"]["lvn_threshold"])

    @property
    def pivots_set(self) -> str:
        return str(self.d["pivots"]["set"])

    def gap_threshold_pct(self, symbol: str) -> float:
        return float(self.d["prior_levels"]["gap_threshold_pct"].get(
            classify_instrument(symbol), 0.3))

    @property
    def historical_cache_dir(self) -> str:
        return str(self.d["historical"]["cache_dir"])

    @property
    def daily_lookback_days(self) -> int:
        return int(self.d["historical"]["daily_lookback_days"])

    def uncalibrated(self) -> list[str]:
        out = []
        if self.hvn_threshold == 0:
            out.append("levels.volume_profile.hvn_threshold (INERT)")
        if self.lvn_threshold == 0:
            out.append("levels.volume_profile.lvn_threshold (INERT)")
        out.append("levels.volume_profile.bin_size.* (functional, confirm vs tick size)")
        out.append("levels.prior_levels.gap_threshold_pct.* (functional, confirm vs gap distribution)")
        return out


def load_levels_config(path: str | Path | None = None) -> LevelsConfig:
    p = Path(path) if path else HERE / "tape_config.yaml"
    if not p.exists():
        return LevelsConfig({})
    return LevelsConfig(yaml.safe_load(p.read_text()) or {})
