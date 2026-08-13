"""Module R5 — Option-Chain Analytics.

Reconstructs each index's option chain from replayed option ticks (R2 stream +
manifest.json strikes/expiries) and derives: per-strike OI/ΔOI/volume, OFFLINE
IV + Greeks (Black-Scholes from the contemporaneous index spot in the merged
stream), PCR, max-pain, ATM-IV, basis, a GEX proxy (net gamma + flip level), and
a price×OI buildup matrix. Pure analysis — never the live feed, zero runtime risk.

Doctrine: knobs in tape_config.yaml (`chain:`), UNCALIBRATED defaults. Descriptive
computations ship functional; SIGNAL-firing flags (GEX regime, buildup
significance) ship INERT at 0.
"""
