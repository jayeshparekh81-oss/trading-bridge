"""Module R7 — Telegram Alert skeleton (send-only).

Consumes R6's glass-box output (analysis/{date}/signals.parquet + signals_summary
.json) and formats/dedups/sends alerts. SKELETON ONLY: transport + formatting +
dedup + a CLI dry-run. LIVE fire-wiring (real-time consumption from the running
engine) is a documented STUB deferred until R6 is calibrated — see alerts/hook.py
and TAPE_NOTES.

Doctrine: every parameter is a knob in the `alerts:` block of tape_config.yaml, and
the whole module ships INERT — alerts.enabled=false by default, so nothing is ever
sent until the founder turns it on. A failed alert is an OUTPUT, never a dependency:
it logs a warning and returns False, never raising into the caller.
"""
