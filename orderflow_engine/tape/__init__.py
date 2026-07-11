"""Module R3 — Tape Engine (analysis layer).

Turns a REPLAYED recorded day into analysis primitives: event-time bars, tick
classification, CVD, big prints, tape velocity, and (interfaces for) depth
imbalance/OFI. It consumes the R2 replayer's consumer contract
(``on_packet`` / ``on_depth`` / ``on_event``) and NEVER the live feed, so it
carries zero runtime risk to the R0/R1 recorders.

DOCTRINE: every threshold/weight is a config-driven CALIBRATION KNOB in
``tape_config.yaml``, defaulted UNCALIBRATED. Structural knobs (bar size, velocity
baseline) ship functional; threshold detectors (big prints, volume bars) ship
INERT (0) so nothing fires on an uncalibrated value. Real values come from
replaying actual recorded days.
"""
