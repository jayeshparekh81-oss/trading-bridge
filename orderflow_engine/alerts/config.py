"""Alerts config — reads the `alerts:` block of tape_config.yaml.

Same loader pattern as tape/levels/chain/signals configs. Ships INERT:
``enabled`` is false by default, so --send is a no-op until the founder turns it on.
"""

from __future__ import annotations

from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent.parent  # orderflow_engine/

DEFAULTS = {
    "enabled": False,             # INERT master toggle (SIGNAL alerts)
    # Daily Pulse = the ops/status message (recording verdict, coverage, disk, G0,
    # pipeline status). SEPARATE channel from signal alerts: it sends even when
    # `enabled` is false, because it carries NO trade signal — only session health.
    "pulse_enabled": True,
    "transport": "telegram",      # telegram (send-only) | dryrun
    "send_timeout_sec": 5.0,
    "send_retries": 2,            # + backoff; final failure -> WARN, return False
    "retry_backoff_sec": 1.0,
    "cooldown_sec": 300,          # suppress repeat (instrument, side) within this
    "min_gap_sec": 10,            # min gap between ANY two sends
    "max_alerts_per_day": 20,     # spam guard
    "persist_state": True,        # alerts_state.json -> same-evening rerun won't re-send
    "daily_summary_top_n": 5,
    "truncate_max_chars": 4096,   # Telegram hard limit
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class AlertsConfig:
    def __init__(self, cfg: dict | None = None):
        blk = (cfg or {}).get("alerts", {}) if isinstance(cfg, dict) else {}
        self.d = _merge(DEFAULTS, blk)

    @property
    def enabled(self) -> bool:
        return bool(self.d["enabled"])

    @property
    def pulse_enabled(self) -> bool:
        return bool(self.d["pulse_enabled"])

    @property
    def transport(self) -> str:
        return str(self.d["transport"])

    @property
    def send_timeout_sec(self) -> float:
        return float(self.d["send_timeout_sec"])

    @property
    def send_retries(self) -> int:
        return int(self.d["send_retries"])

    @property
    def retry_backoff_sec(self) -> float:
        return float(self.d["retry_backoff_sec"])

    @property
    def cooldown_sec(self) -> float:
        return float(self.d["cooldown_sec"])

    @property
    def min_gap_sec(self) -> float:
        return float(self.d["min_gap_sec"])

    @property
    def max_alerts_per_day(self) -> int:
        return int(self.d["max_alerts_per_day"])

    @property
    def persist_state(self) -> bool:
        return bool(self.d["persist_state"])

    @property
    def daily_summary_top_n(self) -> int:
        return int(self.d["daily_summary_top_n"])

    @property
    def truncate_max_chars(self) -> int:
        return int(self.d["truncate_max_chars"])


def load_alerts_config(path: str | Path | None = None) -> AlertsConfig:
    p = Path(path) if path else HERE / "tape_config.yaml"
    if not p.exists():
        return AlertsConfig({})
    return AlertsConfig(yaml.safe_load(p.read_text()) or {})
