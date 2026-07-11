"""Live fire-wiring SEAM (Module R7) — DEFERRED until R6 is calibrated.

``on_signal_fired`` is the single documented entry point the running signal engine
will call in real time once R6 is calibrated and alerts.enabled is turned on. It
does: enabled-check -> dedup -> format -> transport.send -> record. It is NOT wired
to the running engine today (R6 is inert). See TAPE_NOTES: "R7 live wiring deferred
until R6 calibrated."
"""

from __future__ import annotations

import logging

from alerts.format import AlertPayload, format_signal

log = logging.getLogger("alerts.hook")


def on_signal_fired(payload: AlertPayload, *, transport, deduper, cfg) -> bool:
    """Format + dedup + send one fired signal. Returns True iff actually sent.

    NOTE: deferred seam — nothing calls this from the running engine yet.
    """
    if not cfg.enabled:
        return False
    try:
        ts_ns = int(payload.signal_id.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return False
    now_ts = ts_ns / 1e9
    ok, reason = deduper.should_send(payload.instrument, payload.side, ts_ns, now_ts)
    if not ok:
        log.info("alert suppressed (%s) for %s", reason, payload.signal_id)
        return False
    msg = format_signal(payload, max_chars=cfg.truncate_max_chars)
    if transport.send(msg):
        deduper.record(payload.instrument, payload.side, ts_ns, now_ts)
        return True
    return False
