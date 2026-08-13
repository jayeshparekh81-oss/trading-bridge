"""ATM±20 config + capacity math (item 6).

Documents and guards the strike-window change: ±20 => 82 options/chain, 5 chains
=> 410 options, well within 3 connections x 5000.
"""

from __future__ import annotations

from pathlib import Path

import yaml

CFG = Path(__file__).resolve().parent.parent / "config.yaml"


def _config():
    return yaml.safe_load(CFG.read_text())


def test_atm_window_is_20():
    assert _config()["options"]["atm_window"] == 20


def test_capacity_math_within_limits():
    cfg = _config()
    window = cfg["options"]["atm_window"]
    per_chain = (2 * window + 1) * 2                     # CE+PE across ATM±window
    assert per_chain == 82
    n_option_chains = sum(1 for idx in cfg["indices"]
                          if idx.get("options", {}).get("enabled"))
    assert n_option_chains == 5
    max_opts = n_option_chains * per_chain
    assert max_opts == 410
    # core = 5 spots + 5 futures + 1 VIX + equities (14 configured)
    core = (len(cfg["indices"]) * 2 + len(cfg.get("standalone", []))
            + len(cfg.get("equities", [])))
    total = core + max_opts
    conns = cfg["connections"]["max"]
    cap = conns * 5000
    assert core == 25
    assert total == 435
    assert total < cap                                  # 435 << 15000
