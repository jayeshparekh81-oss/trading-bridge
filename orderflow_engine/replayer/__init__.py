"""Module R2 — event-driven replayer.

Read-only replay of a recorded day (``data/{date}/``) as a single time-ordered
event stream, delivered through the SAME consumer interface the live feed uses
(``on_packet(parsed, ts_recv_ns)`` / ``on_event(kind, detail, value_num)``), so
downstream modules (R3+) run identically on live or replayed data.

This package NEVER imports the running recorder's runtime (main/feed/writer/
watchdog), never writes, and never touches the recorder container. It reads only
recorded parquet plus the ``recorder.schema`` / ``recorder.parser`` constants.
"""
