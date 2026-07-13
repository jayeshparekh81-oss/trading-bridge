"""CLI: format/dedup/dispatch alerts from R6's signals output (Module R7).

    python -m alerts.run --date D [--dry-run|--send] [--min-score X] [--daily-summary] [--top N]

Default is --dry-run (prints + writes analysis/{date}/alerts_dryrun.txt, sends
nothing). --send requires env credentials AND alerts.enabled=true, else it exits
cleanly. --min-score is a TEST-ONLY view filter to exercise formatting on real
candidates — it does NOT change any config value (fire_threshold stays 999).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pyarrow.parquet as pq

from signals.config import load_signal_config
from tape.writer import analysis_dir

from alerts.config import load_alerts_config
from alerts.dedup import Deduper
from alerts.format import format_daily_summary, format_signal, payload_from_row
from alerts.transport import DryRunTransport, TelegramTransport

HERE = Path(__file__).resolve().parent.parent
log = logging.getLogger("alerts.run")


def _rows(path: Path) -> list[dict]:
    t = pq.read_table(str(path))
    cols = {c: t.column(c).to_pylist() for c in t.column_names}
    return [{c: cols[c][i] for c in t.column_names} for i in range(t.num_rows)]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="alerts.run")
    ap.add_argument("--date", required=True)
    ap.add_argument("--data-dir", default=str(HERE / "data"))
    ap.add_argument("--config", default=None)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--send", action="store_true")
    ap.add_argument("--min-score", type=float, default=None,
                    help="TEST-ONLY view filter: also format non-fired candidates >= X")
    ap.add_argument("--daily-summary", action="store_true")
    ap.add_argument("--top", type=int, default=None)
    args = ap.parse_args(argv[1:])

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cfg = load_alerts_config(args.config)
    out_dir = analysis_dir(Path(args.data_dir), args.date)
    sig_path = out_dir / "signals.parquet"
    if not sig_path.exists():
        print(f"no signals.parquet at {sig_path} — run signals.run first", file=sys.stderr)
        return 2

    # transport selection: default dry-run; --send is strictly gated
    dry_file = out_dir / "alerts_dryrun.txt"
    if args.send:
        if not cfg.enabled:
            print("alerts.enabled=false — refusing to send (set it true to arm). Nothing sent.")
            return 0
        transport = TelegramTransport(cfg)
        if not transport.credentials_present():
            print("ORDERFLOW_TELEGRAM_BOT_TOKEN / ORDERFLOW_TELEGRAM_CHAT_ID not set — cannot send. Nothing sent.")
            return 0
    else:
        if dry_file.exists():
            dry_file.unlink()                      # fresh dry-run output for this invocation
        transport = DryRunTransport(out_file=dry_file)

    if args.daily_summary:
        return _daily(args, cfg, out_dir, sig_path, transport)

    exits = load_signal_config(args.config).exits
    deduper = Deduper(cfg, state_path=out_dir / "alerts_state.json")
    rows = sorted(_rows(sig_path), key=lambda r: r["ts_ns"])
    considered = [r for r in rows if r["fired"]
                  or (args.min_score is not None and r["score"] >= args.min_score)]
    sent = 0
    suppressed: dict[str, int] = {}
    for r in considered:
        side = r["side"]
        trail_k = float(exits.get(f"chandelier_k_{side}", 3.0))
        p = payload_from_row(r, trail_k=trail_k,
                             time_stop_min=float(exits.get("sleeper_minutes", 60)))
        ts_ns = int(r["ts_ns"])
        ok, reason = deduper.should_send(r["instrument"], side, ts_ns, ts_ns / 1e9)
        if not ok:
            suppressed[reason] = suppressed.get(reason, 0) + 1
            continue
        if transport.send(format_signal(p, max_chars=cfg.truncate_max_chars)):
            deduper.record(r["instrument"], side, ts_ns, ts_ns / 1e9)
            sent += 1

    print("=" * 60)
    print(f"ALERTS — {args.date}  ({'SEND' if args.send else 'DRY-RUN'})")
    print(f"candidates considered: {len(considered)}   sent: {sent}")
    if suppressed:
        print("suppressed: " + ", ".join(f"{k}={v}" for k, v in sorted(suppressed.items())))
    if not args.send:
        print(f"dry-run written -> {dry_file}")
    print(f"alerts.enabled={cfg.enabled}  (config fire_threshold untouched)")
    print("=" * 60)
    return 0


def _daily(args, cfg, out_dir: Path, sig_path: Path, transport) -> int:
    sp = out_dir / "signals_summary.json"
    summary = json.loads(sp.read_text()) if sp.exists() else {"date": args.date}
    # top candidates by score across ALL rows (for the evening ritual view)
    top_n = args.top or cfg.daily_summary_top_n
    rows = sorted(_rows(sig_path), key=lambda r: -r["score"])
    summary["top_candidates"] = [{"instrument": r["instrument"], "side": r["side"],
                                  "score": r["score"]} for r in rows[:top_n]]
    transport.send(format_daily_summary(summary, top_n))
    if not args.send:
        print(f"dry-run written -> {out_dir / 'alerts_dryrun.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
