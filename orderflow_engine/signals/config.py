"""Signal-engine config — reads the `signal:` block of tape_config.yaml.

Every weight/threshold is a knob (floats to 0.001); each component individually
toggleable; defaults UNCALIBRATED. The fire threshold ships at 999 (INERT).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent.parent  # orderflow_engine/

COMPONENT_NAMES = [
    "book_ofi", "big_print", "queue_imbalance", "vwap_value_location",
    "cvd_confirm", "level_zone", "tape_velocity", "regime", "pain_map",
]

DEFAULTS = {
    "enabled": True,
    "fire_threshold": 999.0,          # INERT
    "eval_trigger": "bar_close",      # bar_close | event | tick
    "tradeable": ["NIFTY_FUT", "BANKNIFTY_FUT"],
    "components": {
        "book_ofi": {"enabled": True, "weight": 25.0},
        "big_print": {"enabled": True, "weight": 20.0},
        # 2026-07-15: weight 15 -> 0. Changes NOTHING functionally — queue_imbalance is
        # an unbuilt None stub, already contributing 0. This makes the config HONEST
        # about the real ceiling (was reserving 15 phantom points on faith). Stays 0
        # until a 15-clean-day predictive test earns it back (TAPE_NOTES). Pure function
        # + tests kept for that revival test.
        "queue_imbalance": {"enabled": True, "weight": 0.0},
        "vwap_value_location": {"enabled": True, "weight": 15.0},
        "cvd_confirm": {"enabled": True, "weight": 10.0},
        "level_zone": {"enabled": True, "weight": 5.0},
        "tape_velocity": {"enabled": True, "weight": 5.0},
        "regime": {"enabled": True, "weight": 5.0},
        "pain_map": {"enabled": True, "weight": 0.0},   # INERT
    },
    "short": {"fire_threshold": 999.0, "weight_overrides": {}},
    "component_params": {
        "big_print_window_s": 30.0, "cvd_slope_min": 0.0, "level_zone_ticks": 5.0,
        "vwap_band_k": 1.0, "ofi_min": 0.0, "queue_imbalance_min": 0.0,
    },
    "regime": {
        "vix_low": 12.0, "vix_high": 18.0, "trend_ma_bars": 20, "trend_slope_min": 0.0,
        "participant_oi_bias": "neutral", "use_gex": True, "gex_flag": False,
    },
    "asymmetric_gate": {
        "enabled": True, "strong_bull_short_penalty": 10.0,
        "strong_bear_long_penalty": 10.0, "disable_countertrend": False,
    },
    "gates": {
        "first_minutes_no_entry": 5, "session_cutoff": "14:45", "max_trades_per_day": 3,
        "one_open_position": True, "cooldown_s": 300,
        "liquidity": {"enabled": True, "max_spread_ticks": 0, "min_size": 0},
        "expiry_theta_guard": {"enabled": True, "after": "14:00"},
    },
    "exits": {
        "partial_fraction": 0.5, "chandelier_k_long": 3.0, "chandelier_k_short": 3.0,
        "thesis_stop_buffer_ticks": 2.0, "sleeper_minutes": 60,
        "momentum_death": {"conditions_required": 2, "cvd_flip": True, "velocity_die": True,
                           "big_print_opposite": True, "ofi_flip": True, "level_reject": True},
    },
}


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


@dataclass
class Component:
    enabled: bool
    weight: float


class SignalConfig:
    def __init__(self, cfg: dict | None = None):
        blk = (cfg or {}).get("signal", {}) if isinstance(cfg, dict) else {}
        self.d = _merge(DEFAULTS, blk)

    @property
    def enabled(self) -> bool:
        return bool(self.d["enabled"])

    @property
    def eval_trigger(self) -> str:
        return str(self.d["eval_trigger"])

    @property
    def tradeable(self) -> list[str]:
        return list(self.d["tradeable"])

    def fire_threshold(self, side: str) -> float:
        if side == "short":
            return float(self.d["short"]["fire_threshold"])
        return float(self.d["fire_threshold"])

    def component(self, name: str, side: str = "long") -> Component:
        c = self.d["components"].get(name, {"enabled": False, "weight": 0.0})
        weight = float(c.get("weight", 0.0))
        if side == "short":
            weight = float(self.d["short"]["weight_overrides"].get(name, weight))
        return Component(bool(c.get("enabled", False)), weight)

    def param(self, name: str, default=None):
        return self.d["component_params"].get(name, default)

    # -- sub-blocks (returned as dicts for the respective modules) ----------
    @property
    def regime(self) -> dict:
        return self.d["regime"]

    @property
    def asymmetric_gate(self) -> dict:
        return self.d["asymmetric_gate"]

    @property
    def gates(self) -> dict:
        return self.d["gates"]

    @property
    def exits(self) -> dict:
        return self.d["exits"]

    def uncalibrated(self) -> list[str]:
        out = []
        if self.fire_threshold("long") >= 999 or self.fire_threshold("short") >= 999:
            out.append("signal.fire_threshold (INERT at 999)")
        if self.component("pain_map").weight == 0:
            out.append("signal.components.pain_map (weight 0, INERT)")
        out.append("signal.regime.vix_low/high (UNCALIBRATED)")
        out.append("signal.component_params.* (UNCALIBRATED)")
        return out


def load_signal_config(path: str | Path | None = None) -> SignalConfig:
    p = Path(path) if path else HERE / "tape_config.yaml"
    if not p.exists():
        return SignalConfig({})
    return SignalConfig(yaml.safe_load(p.read_text()) or {})
