"""Chain-analytics config — reads the `chain:` block of tape_config.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent.parent  # orderflow_engine/

DEFAULTS = {
    "risk_free_rate": 0.065,          # BSM rate (functional, UNCALIBRATED)
    "day_count": 365,
    "spot_staleness_s": 5.0,          # spot older than this -> stale flag
    "snapshot_interval_s": 60.0,      # chain + IV/greeks cadence (0 = per tick)
    "delta_oi_windows_s": [60, 300, 900],
    "contract_size": {"NIFTY": 75, "BANKNIFTY": 35, "FINNIFTY": 65,
                      "MIDCPNIFTY": 140, "SENSEX": 20},
    "gex": {"regime_flag_threshold": 0},          # INERT
    "buildup": {"window_s": 300, "price_threshold_pct": 0, "oi_threshold_pct": 0},  # INERT gates
    "iv_percentile": {"history_dir": "analysis/iv_history", "min_days": 20},
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class ChainConfig:
    def __init__(self, cfg: dict | None = None):
        blk = (cfg or {}).get("chain", {}) if isinstance(cfg, dict) else {}
        self.d = _merge(DEFAULTS, blk)

    @property
    def risk_free_rate(self) -> float:
        return float(self.d["risk_free_rate"])

    @property
    def day_count(self) -> int:
        return int(self.d["day_count"])

    @property
    def spot_staleness_ns(self) -> int:
        return int(float(self.d["spot_staleness_s"]) * 1e9)

    @property
    def snapshot_interval_ns(self) -> int:
        return int(float(self.d["snapshot_interval_s"]) * 1e9)

    @property
    def delta_oi_windows_s(self) -> list[int]:
        return [int(x) for x in self.d["delta_oi_windows_s"]]

    def contract_size(self, index: str) -> int:
        return int(self.d["contract_size"].get(index, 1))

    @property
    def gex_regime_threshold(self) -> float:
        return float(self.d["gex"]["regime_flag_threshold"])

    @property
    def buildup_window_s(self) -> float:
        return float(self.d["buildup"]["window_s"])

    @property
    def buildup_price_threshold_pct(self) -> float:
        return float(self.d["buildup"]["price_threshold_pct"])

    @property
    def buildup_oi_threshold_pct(self) -> float:
        return float(self.d["buildup"]["oi_threshold_pct"])

    @property
    def iv_history_dir(self) -> str:
        return str(self.d["iv_percentile"]["history_dir"])

    @property
    def iv_min_days(self) -> int:
        return int(self.d["iv_percentile"]["min_days"])

    def uncalibrated(self) -> list[str]:
        out = ["chain.risk_free_rate (functional, confirm)"]
        if self.gex_regime_threshold == 0:
            out.append("chain.gex.regime_flag_threshold (INERT)")
        if self.buildup_price_threshold_pct == 0 or self.buildup_oi_threshold_pct == 0:
            out.append("chain.buildup significance thresholds (INERT)")
        out.append(f"chain.iv_percentile (UNCALIBRATED until {self.iv_min_days} days)")
        return out


def load_chain_config(path: str | Path | None = None) -> ChainConfig:
    p = Path(path) if path else HERE / "tape_config.yaml"
    if not p.exists():
        return ChainConfig({})
    return ChainConfig(yaml.safe_load(p.read_text()) or {})
