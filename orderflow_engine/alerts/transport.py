"""Alert transports (Module R7) — send-only, stdlib urllib (no framework, no new dep).

TelegramTransport POSTs to api.telegram.org/bot<token>/sendMessage. Credentials come
ONLY from the environment under NAMESPACED names — ORDERFLOW_TELEGRAM_BOT_TOKEN /
ORDERFLOW_TELEGRAM_CHAT_ID — with NO fallback to the live system's bare
TELEGRAM_BOT_TOKEN. FOUNDER DECISION 12 Jul: R7 shares the live bot (single inbox),
but only via a DELIBERATE feed — the founder places the token under the ORDERFLOW_*
names in orderflow_engine/.env; a shell that sourced backend/.env can never leak the
live token into R7. Credentials are NEVER printed or logged — log messages carry
only the exception TYPE and attempt number, never the URL (which embeds the token)
or the exception string. A send failure logs WARN and returns False; never raises.

DryRunTransport prints the exact message and appends it to a dry-run file — used by
``--dry-run`` and the whole test suite, so no test ever touches the network.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("alerts.transport")

TELEGRAM_API = "https://api.telegram.org"


def _default_post(url: str, payload: dict, timeout: float) -> bool:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return bool(body.get("ok"))


class TelegramTransport:
    def __init__(self, cfg, *, token: Optional[str] = None, chat_id: Optional[str] = None,
                 http_post: Callable = _default_post, sleep: Callable = time.sleep):
        self.cfg = cfg
        # NAMESPACED env names ONLY — deliberately no fallback to bare TELEGRAM_*
        # (those belong to the live trading_bridge bot; see module docstring).
        self.token = token if token is not None \
            else os.environ.get("ORDERFLOW_TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id if chat_id is not None \
            else os.environ.get("ORDERFLOW_TELEGRAM_CHAT_ID")
        self._post = http_post
        self._sleep = sleep

    def credentials_present(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.credentials_present():
            log.warning("telegram credentials missing "
                        "(ORDERFLOW_TELEGRAM_BOT_TOKEN/CHAT_ID); not sending")
            return False
        url = f"{TELEGRAM_API}/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode,
                   "disable_web_page_preview": True}
        attempts = self.cfg.send_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                if self._post(url, payload, self.cfg.send_timeout_sec):
                    return True
                raise IOError("telegram responded not-ok")
            except Exception as exc:  # noqa: BLE001 - alerts must never raise
                # log the TYPE only — never the exception string or url (token!)
                if attempt < attempts:
                    delay = self.cfg.retry_backoff_sec * (2 ** (attempt - 1))
                    log.warning("telegram send attempt %d/%d failed (%s); retry in %.1fs",
                                attempt, attempts, type(exc).__name__, delay)
                    self._sleep(delay)
                else:
                    log.warning("telegram send FAILED after %d attempts (%s)",
                                attempts, type(exc).__name__)
        return False


class DryRunTransport:
    """Prints the message and appends it to a dry-run file. Never sends."""

    def __init__(self, out_file: Optional[Path] = None):
        self.out_file = Path(out_file) if out_file else None
        self.sent: list[str] = []

    def credentials_present(self) -> bool:
        return True

    def send(self, text: str, parse_mode: str = "HTML") -> bool:
        self.sent.append(text)
        print(text)
        if self.out_file is not None:
            self.out_file.parent.mkdir(parents=True, exist_ok=True)
            with self.out_file.open("a", encoding="utf-8") as fh:
                fh.write(text + "\n" + "=" * 48 + "\n")
        return True
