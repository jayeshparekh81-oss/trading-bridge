"""HMAC signer for TradingView webhook bodies.

Run with::

    python scripts/sign_webhook.py --secret $HMAC_SECRET --body payload.json
    echo '{"action":"BUY",...}' | python scripts/sign_webhook.py --secret $HMAC_SECRET

Outputs the lowercase hex digest produced by
:func:`app.core.security.compute_hmac_signature` plus a ready-to-paste
curl command. Stays a thin wrapper — the signing primitive lives in
``app.core.security`` and is shared with the live verify path so signer
and verifier can never drift.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the backend package importable when invoked as ``python scripts/...``.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _read_body(path: str | None) -> bytes:
    """Body source: ``--body <path>`` (preferred) else stdin."""
    if path:
        return Path(path).read_bytes()
    if sys.stdin.isatty():
        sys.exit(
            "  [error] No --body path given and stdin is a TTY. "
            "Pipe the JSON in, or pass --body /path/to/payload.json."
        )
    return sys.stdin.buffer.read()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--secret",
        required=True,
        help="The HMAC secret printed by seed_strategy_webhook.py.",
    )
    parser.add_argument(
        "--body",
        default=None,
        help="Path to the JSON payload. Reads from stdin when omitted.",
    )
    parser.add_argument(
        "--token",
        default=None,
        help=(
            "Optional webhook token. When provided, prints a complete "
            "curl command pointed at /api/webhook/strategy/<token>."
        ),
    )
    parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Backend base URL for the printed curl example.",
    )
    args = parser.parse_args()

    # Defer import so --help works even when the venv is missing extras.
    from app.core.security import compute_hmac_signature

    body = _read_body(args.body)
    signature = compute_hmac_signature(body, args.secret)

    print(f"X-Signature: {signature}")
    if args.token:
        url = f"{args.host.rstrip('/')}/api/webhook/strategy/{args.token}"
        body_arg = (
            f"@{args.body}"
            if args.body is not None
            else "$(cat <payload-file>)"
        )
        print()
        print("# ready-to-run curl:")
        print(
            f"curl -sS -X POST {url} \\\n"
            f"  -H 'Content-Type: application/json' \\\n"
            f"  -H 'X-Signature: {signature}' \\\n"
            f"  --data-binary {body_arg}"
        )


if __name__ == "__main__":
    main()
