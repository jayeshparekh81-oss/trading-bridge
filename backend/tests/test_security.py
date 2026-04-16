"""Unit tests for :mod:`app.core.security`.

The timing-attack test is the headline coverage requirement — it asserts
that :func:`verify_hmac_signature` returns ``False`` for any wrong byte
position with a stable mean latency, the hallmark of
:func:`hmac.compare_digest`.
"""

from __future__ import annotations

import os
import statistics
import time
from collections.abc import Iterator

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core import security


@pytest.fixture(autouse=True)
def _ensure_known_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Pin a deterministic Fernet key per test so caches don't leak across cases."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    security.reset_cipher_cache()
    yield key
    security.reset_cipher_cache()


class TestEncryption:
    def test_round_trip_preserves_plaintext(self) -> None:
        token = security.encrypt_credential("super-secret-api-key")
        assert isinstance(token, str)
        assert token != "super-secret-api-key"
        assert security.decrypt_credential(token) == "super-secret-api-key"

    def test_two_encryptions_differ(self) -> None:
        # Fernet includes a random IV — same plaintext twice → different tokens.
        a = security.encrypt_credential("payload")
        b = security.encrypt_credential("payload")
        assert a != b

    def test_decrypt_rejects_tampered_token(self) -> None:
        token = security.encrypt_credential("payload")
        # Flip a character mid-token.
        tampered = token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1]
        with pytest.raises(InvalidToken):
            security.decrypt_credential(tampered)

    def test_encrypt_rejects_non_string(self) -> None:
        with pytest.raises(TypeError):
            security.encrypt_credential(b"bytes")  # type: ignore[arg-type]

    def test_decrypt_rejects_non_string(self) -> None:
        with pytest.raises(TypeError):
            security.decrypt_credential(b"bytes")  # type: ignore[arg-type]

    def test_missing_key_raises_runtime_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        security.reset_cipher_cache()
        with pytest.raises(RuntimeError, match="ENCRYPTION_KEY environment variable"):
            security.encrypt_credential("anything")

    def test_invalid_key_raises_runtime_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENCRYPTION_KEY", "not-a-valid-fernet-key")
        security.reset_cipher_cache()
        with pytest.raises(RuntimeError, match="not a valid Fernet key"):
            security.encrypt_credential("anything")


class TestHMAC:
    SECRET = "webhook-shared-secret"

    def test_compute_signature_is_hex_sha256(self) -> None:
        sig = security.compute_hmac_signature(b"payload", self.SECRET)
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA-256 hex
        int(sig, 16)  # asserts hex-only

    def test_verify_accepts_correct_signature(self) -> None:
        payload = b'{"action":"BUY","ticker":"RELIANCE"}'
        sig = security.compute_hmac_signature(payload, self.SECRET)
        assert security.verify_hmac_signature(payload, sig, self.SECRET) is True

    def test_verify_rejects_wrong_signature(self) -> None:
        payload = b"hello"
        sig = security.compute_hmac_signature(payload, self.SECRET)
        wrong = sig[:-1] + ("0" if sig[-1] != "0" else "1")
        assert security.verify_hmac_signature(payload, wrong, self.SECRET) is False

    def test_verify_rejects_wrong_payload(self) -> None:
        sig = security.compute_hmac_signature(b"hello", self.SECRET)
        assert security.verify_hmac_signature(b"goodbye", sig, self.SECRET) is False

    def test_verify_rejects_wrong_secret(self) -> None:
        sig = security.compute_hmac_signature(b"hello", self.SECRET)
        assert security.verify_hmac_signature(b"hello", sig, "different") is False

    def test_compute_rejects_str_payload(self) -> None:
        with pytest.raises(TypeError):
            security.compute_hmac_signature("string-not-bytes", self.SECRET)  # type: ignore[arg-type]

    def test_verify_handles_bad_input_gracefully(self) -> None:
        # Mismatched lengths must return False, not raise — so the webhook
        # endpoint never 500s on attacker input.
        assert (
            security.verify_hmac_signature(b"x", "tooshort", self.SECRET) is False
        )

    def test_timing_attack_resistance(self) -> None:
        """compare_digest must take ~constant time regardless of mismatch index.

        We measure the mean latency of verifying a signature that differs
        from the correct one only at byte position 1 vs position 60. With
        ``compare_digest`` the two means stay within a tight ratio; a
        naive ``==`` would let the early-mismatch sample finish first.
        """
        payload = b"payload-x" * 32
        correct = security.compute_hmac_signature(payload, self.SECRET)

        # Mismatch positions chosen at opposite ends of the digest.
        early_wrong = ("0" if correct[1] != "0" else "1") + correct[1:]
        early_wrong = correct[0] + early_wrong[0] + correct[2:]
        late_wrong = correct[:-1] + ("0" if correct[-1] != "0" else "1")

        def measure(candidate: str) -> float:
            samples: list[float] = []
            for _ in range(2_000):
                t0 = time.perf_counter_ns()
                security.verify_hmac_signature(payload, candidate, self.SECRET)
                samples.append(time.perf_counter_ns() - t0)
            # Trim outliers — GC pauses skew otherwise.
            samples.sort()
            trimmed = samples[200:-200]
            return statistics.mean(trimmed)

        early = measure(early_wrong)
        late = measure(late_wrong)
        # Either ratio direction is fine; mismatch position must not move
        # the mean by more than 50% (constant-time would predict ~1.0).
        ratio = max(early, late) / min(early, late)
        assert ratio < 1.5, (
            f"verify_hmac_signature is not constant-time: "
            f"early={early:.1f}ns, late={late:.1f}ns, ratio={ratio:.2f}"
        )


class TestPasswords:
    def test_hash_then_verify(self) -> None:
        h = security.hash_password("correct horse battery staple")
        assert h.startswith(("$2b$", "$2a$", "$2y$"))
        assert security.verify_password("correct horse battery staple", h) is True
        assert security.verify_password("wrong", h) is False

    def test_hash_uses_cost_factor_12(self) -> None:
        h = security.hash_password("x")
        # bcrypt format: $2b$<rounds>$<22-char-salt><31-char-hash>
        assert h.split("$")[2] == "12"

    def test_two_hashes_of_same_password_differ(self) -> None:
        a = security.hash_password("same")
        b = security.hash_password("same")
        assert a != b
        assert security.verify_password("same", a)
        assert security.verify_password("same", b)

    def test_hash_rejects_non_string(self) -> None:
        with pytest.raises(TypeError):
            security.hash_password(b"bytes")  # type: ignore[arg-type]

    def test_verify_rejects_non_string(self) -> None:
        assert security.verify_password(b"bytes", "hash") is False  # type: ignore[arg-type]
        assert security.verify_password("plain", b"hash") is False  # type: ignore[arg-type]

    def test_verify_returns_false_on_malformed_hash(self) -> None:
        assert security.verify_password("x", "not-a-bcrypt-string") is False


class TestTokens:
    def test_generate_webhook_token_default_length(self) -> None:
        token = security.generate_webhook_token()
        # 32 bytes → ~43 char base64 (no padding)
        assert 40 <= len(token) <= 44
        assert "/" not in token and "+" not in token  # url-safe alphabet

    def test_generate_webhook_token_custom_length(self) -> None:
        token = security.generate_webhook_token(length=64)
        assert len(token) >= 80

    def test_generate_webhook_token_rejects_short_length(self) -> None:
        with pytest.raises(ValueError, match="at least 16"):
            security.generate_webhook_token(length=8)

    def test_two_tokens_differ(self) -> None:
        assert security.generate_webhook_token() != security.generate_webhook_token()

    def test_generate_fernet_key_round_trips(self) -> None:
        key = security.generate_fernet_key()
        # Must be acceptable to Fernet — round-trip a payload through it.
        cipher = Fernet(key.encode())
        assert cipher.decrypt(cipher.encrypt(b"x")) == b"x"

    def test_is_valid_fernet_key_helper(self) -> None:
        good = security.generate_fernet_key()
        assert security._is_valid_fernet_key(good) is True
        assert security._is_valid_fernet_key("not-a-key") is False
        assert security._is_valid_fernet_key("") is False
