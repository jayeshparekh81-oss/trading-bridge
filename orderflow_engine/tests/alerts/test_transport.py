"""Transport: retry/backoff, never-raises, token-never-logged (Module R7)."""

from __future__ import annotations

import logging

from alerts.config import AlertsConfig
from alerts.transport import DryRunTransport, TelegramTransport

TOKEN = "123456:SECRET-TOKEN-VALUE"
CFG = AlertsConfig({"alerts": {"send_retries": 2, "retry_backoff_sec": 0.01}})


def _transport(post, **kw):
    return TelegramTransport(CFG, token=TOKEN, chat_id="42", http_post=post,
                             sleep=lambda *_: None, **kw)


def test_success_sends_once():
    calls = []
    t = _transport(lambda url, payload, timeout: calls.append(url) or True)
    assert t.send("hi") is True
    assert len(calls) == 1


def test_failure_retries_then_returns_false():
    calls = {"n": 0}

    def boom(url, payload, timeout):
        calls["n"] += 1
        raise ConnectionError("network down")

    t = _transport(boom)
    assert t.send("hi") is False          # never raises
    assert calls["n"] == 3                # 1 initial + 2 retries


def test_not_ok_response_is_a_failure():
    t = _transport(lambda url, payload, timeout: False)
    assert t.send("hi") is False


def test_missing_credentials_returns_false_without_posting():
    calls = []
    t = TelegramTransport(CFG, token=None, chat_id=None,
                          http_post=lambda *a: calls.append(1) or True, sleep=lambda *_: None)
    assert t.credentials_present() is False
    assert t.send("hi") is False
    assert calls == []


def test_token_never_appears_in_logs(caplog):
    def boom(url, payload, timeout):
        raise ConnectionError(f"failed connecting to {url}")   # url embeds the token

    t = _transport(boom)
    with caplog.at_level(logging.WARNING, logger="alerts.transport"):
        t.send("hi")
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert TOKEN not in joined                                 # token never logged
    assert "SECRET" not in joined


def test_dryrun_writes_file(tmp_path):
    f = tmp_path / "alerts_dryrun.txt"
    t = DryRunTransport(out_file=f)
    assert t.send("hello <b>world</b>") is True
    assert t.sent == ["hello <b>world</b>"]
    assert "hello" in f.read_text()
