"""Alert message formatting (Module R7) — the Glass-Box message.

Builds the AlertPayload from an R6 signals.parquet row (component raw/weighted from
the `breakdown` JSON; exit trail_k/time_stop from the exits config — NOT invented)
and renders an HTML Telegram message that stays under Telegram's 4096-char limit via
deterministic truncation (drop the lowest-weighted components first). All field
values are HTML-escaped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))
TRUNCATION_MARK = "\n…truncated"


def esc(v) -> str:
    """HTML-escape a value (& first, then < >)."""
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def ts_to_ist(ts_ns: int) -> str:
    return datetime.fromtimestamp(int(ts_ns) / 1e9, tz=IST).strftime("%Y-%m-%d %H:%M:%S IST")


@dataclass
class AlertPayload:
    signal_id: str
    ts_ist: str
    instrument: str
    side: str
    score: float
    fire_threshold: float
    components: dict                       # name -> (raw, weighted)
    gates_passed: bool
    gates_failed: list                     # first-reject reason only (R6 records one)
    regime: str
    exit_plan: dict                        # thesis_stop, one_r_target, trail_k, time_stop_min
    image_path: Optional[str] = None       # future chart-snapshot stub; unused today


def payload_from_row(row: dict, *, trail_k: float, time_stop_min: float) -> AlertPayload:
    breakdown = json.loads(row.get("breakdown") or "{}")
    components = {name: (v.get("activation", 0.0), v.get("contribution", 0.0))
                 for name, v in breakdown.items() if v.get("enabled")}
    reason = row.get("gate_reason") or ""
    return AlertPayload(
        signal_id=f"{row['instrument']}:{row['side']}:{row['ts_ns']}",
        ts_ist=ts_to_ist(row["ts_ns"]), instrument=row["instrument"], side=row["side"],
        score=float(row["score"]), fire_threshold=float(row["threshold"]),
        components=components,
        gates_passed=(reason == ""), gates_failed=([reason] if reason else []),
        regime=f"{row.get('regime_direction')}/{row.get('regime_vol_band')}",
        exit_plan={"thesis_stop": row.get("stop"), "one_r_target": row.get("target"),
                   "trail_k": trail_k, "time_stop_min": time_stop_min},
    )


def _component_lines(components: dict) -> list[tuple[float, str]]:
    """(weighted, line) sorted by weighted DESC — line ready for the <pre> table."""
    rows = []
    for name, (raw, weighted) in components.items():
        rows.append((float(weighted),
                     f"{esc(name):<20} raw={raw:>6.3f}  wt={weighted:>7.3f}"))
    rows.sort(key=lambda r: r[0], reverse=True)
    return rows


def format_signal(p: AlertPayload, max_chars: int = 4096) -> str:
    arrow = "🟢 LONG" if p.side == "long" else "🔴 SHORT"
    header = (f"<b>{arrow} · {esc(p.instrument)}</b>\n"
              f"score <b>{p.score:.1f}</b> / thr {p.fire_threshold:.0f}   "
              f"{esc(p.ts_ist)}")
    gates = ("gates: ✅ passed" if p.gates_passed
             else "gates: ⛔ " + esc(", ".join(p.gates_failed)))
    regime = f"regime: {esc(p.regime)}"
    ep = p.exit_plan
    exit_block = (f"<b>exit</b>: stop {_fmt(ep['thesis_stop'])} · 1R {_fmt(ep['one_r_target'])}"
                  f" · trail k={_fmt(ep['trail_k'])} · time {_fmt(ep['time_stop_min'])}m")
    footer = f"<code>{esc(p.signal_id)}</code>"

    lines = _component_lines(p.components)
    fixed = [header, gates, regime, exit_block, footer]

    def assemble(comp_lines, truncated: bool) -> str:
        pre = "<pre>" + "\n".join(l for _, l in comp_lines) + "</pre>"
        body = "\n".join([header, pre, gates, regime, exit_block, footer])
        return body + (TRUNCATION_MARK if truncated else "")

    msg = assemble(lines, False)
    if len(msg) <= max_chars:
        return msg
    # deterministic truncation: drop the lowest-weighted components until it fits
    kept = list(lines)
    while kept:
        kept = kept[:-1]                      # drop the lowest (list is desc-sorted)
        msg = assemble(kept, True)
        if len(msg) <= max_chars:
            return msg
    # even with no components it doesn't fit -> hard clip the fixed portion
    return ("\n".join(fixed))[: max_chars - len(TRUNCATION_MARK)] + TRUNCATION_MARK


def _fmt(x) -> str:
    return f"{x:.2f}" if isinstance(x, (int, float)) else "—"


def format_daily_summary(summary: dict, top_n: int = 5) -> str:
    c = summary.get("counts", {})
    lines = [f"<b>📊 Orderflow signals — {esc(summary.get('date', '?'))}</b>",
             f"candidates: {c.get('candidates', 0)}   fired: {c.get('fired', 0)}   "
             f"net R: {summary.get('net_simulated_r', 0)}"]
    gr = summary.get("gate_rejects", {})
    if gr:
        top = sorted(gr.items(), key=lambda x: -x[1])
        lines.append("gate blocks: " + esc(", ".join(f"{k}={v}" for k, v in top)))
    cands = summary.get("top_candidates") or summary.get("fires") or []
    if cands:
        lines.append(f"<b>top {top_n} by score</b>:")
        pre = []
        for cnd in cands[:top_n]:
            pre.append(f"{esc(cnd.get('instrument', '?')):<16} "
                       f"{esc(cnd.get('side', '?')):<5} score={cnd.get('score', 0):.1f}")
        lines.append("<pre>" + "\n".join(pre) + "</pre>")
    return "\n".join(lines)
