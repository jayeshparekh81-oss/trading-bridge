"""Determinism: same replay -> byte-identical signal stream (Module R6)."""

from __future__ import annotations

import hashlib
import json

from tests.signals.test_end_to_end import _run


def _hash(sig) -> str:
    return hashlib.sha256(json.dumps(sig.rows, sort_keys=True, default=str).encode()).hexdigest()


def test_signal_stream_is_deterministic(tmp_path):
    s1 = _run(tmp_path / "a")
    s2 = _run(tmp_path / "b")
    assert _hash(s1) == _hash(s2)
    assert len(s1.rows) == len(s2.rows) and len(s1.rows) > 0
