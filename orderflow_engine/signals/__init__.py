"""Module R6 — Confluence Signal Engine (the brain).

Consumes R3 (tape + footprint), R4 (levels + IB), R5 (chain / IV / GEX) live over a
SINGLE R2 replay pass (composite consumer) and produces SCORED, EXPLAINED, GATED
signals — long and short as first-class mirrors. Every candidate (fired or
rejected) is logged with a full breakdown (glass box). Fired signals get a
Brahmastra-2.0 exit plan that is SIMULATED on the replay so calibration can measure
expectancy end to end. Pure analysis: no live feed, no broker, zero runtime risk.

Doctrine: every weight/threshold is a `signal:` knob in tape_config.yaml, each
component individually toggleable, defaults UNCALIBRATED. The fire threshold ships
at 999 (INERT) — the engine evaluates and explains but fires NOTHING until
calibration lowers it.
"""
