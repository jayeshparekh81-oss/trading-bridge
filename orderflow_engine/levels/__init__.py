"""Module R4 — Levels & Context Engine.

The daily "map" layer: reference levels and value areas that R6 will score
location against. Two data paths:
  (a) INTRADAY — consumes the R2 replayer's Consumer contract (same as R3) to
      build session VWAP + developing volume profile from recorded ticks.
  (b) DAILY/HISTORICAL — consumes OHLCV bars (parquet) for pivots / PDH-PDL /
      prior-day / prior-week levels; fetched via a minimal VENDORED Dhan v2
      historical client (levels/historical.py) — the backend/pine_replica client
      is NOT imported (isolation) or modified.

Same doctrine as R3: thresholds are config knobs in tape_config.yaml (`levels:`),
defaulted UNCALIBRATED. Structural computations ship functional; SIGNAL-firing
flags (HVN/LVN) ship INERT. Zero runtime risk to the R0/R1 recorders.
"""
