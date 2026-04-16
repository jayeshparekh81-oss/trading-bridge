"""Unit tests for :mod:`app.core.exceptions`.

Covers:
    * Each subclass carries its typed fields and is catchable as
      :class:`BrokerError`.
    * ``__str__`` produces the broker-prefixed, cause-aware message.
    * Pickle round-trips preserve every field, including subclass-specific
      ones (``reason``, ``retry_after``).
    * ``metadata`` defaults to an empty dict and is mutation-safe (we
      copy on input so callers can mutate their dict afterwards).
"""

from __future__ import annotations

import pickle

import pytest

from app.core.exceptions import (
    BrokerAuthError,
    BrokerConnectionError,
    BrokerError,
    BrokerInsufficientFundsError,
    BrokerInvalidSymbolError,
    BrokerOrderError,
    BrokerOrderRejectedError,
    BrokerRateLimitError,
    BrokerSessionExpiredError,
)


class TestBrokerError:
    def test_basic_attributes(self) -> None:
        err = BrokerError("login failed", "fyers")
        assert err.message == "login failed"
        assert err.broker_name == "fyers"
        assert err.original_error is None
        assert err.metadata == {}

    def test_metadata_is_copied(self) -> None:
        meta = {"symbol": "RELIANCE"}
        err = BrokerError("x", "fyers", metadata=meta)
        meta["symbol"] = "MUTATED"
        assert err.metadata == {"symbol": "RELIANCE"}

    def test_str_includes_broker_and_message(self) -> None:
        err = BrokerError("login failed", "fyers")
        assert str(err) == "[fyers] login failed"

    def test_str_includes_cause(self) -> None:
        cause = ValueError("bad token")
        err = BrokerError("login failed", "fyers", original_error=cause)
        assert "caused by ValueError: bad token" in str(err)

    def test_repr_round_trips(self) -> None:
        err = BrokerError("x", "fyers", metadata={"k": 1})
        rendered = repr(err)
        assert "BrokerError" in rendered
        assert "metadata={'k': 1}" in rendered

    def test_pickle_round_trip(self) -> None:
        err = BrokerError(
            "boom", "fyers", original_error=RuntimeError("inner"), metadata={"k": "v"}
        )
        restored = pickle.loads(pickle.dumps(err))
        assert isinstance(restored, BrokerError)
        assert restored.message == "boom"
        assert restored.broker_name == "fyers"
        assert restored.metadata == {"k": "v"}
        assert isinstance(restored.original_error, RuntimeError)
        assert str(restored.original_error) == "inner"


class TestSubclasses:
    @pytest.mark.parametrize(
        "cls",
        [
            BrokerAuthError,
            BrokerSessionExpiredError,
            BrokerOrderError,
            BrokerConnectionError,
            BrokerInvalidSymbolError,
            BrokerInsufficientFundsError,
        ],
    )
    def test_simple_subclass_inherits_broker_error(
        self, cls: type[BrokerError]
    ) -> None:
        err = cls("msg", "fyers", metadata={"k": 1})
        assert isinstance(err, BrokerError)
        assert err.message == "msg"
        restored = pickle.loads(pickle.dumps(err))
        assert isinstance(restored, cls)
        assert restored.metadata == {"k": 1}

    def test_rejected_carries_reason(self) -> None:
        err = BrokerOrderRejectedError(
            "rejected", "fyers", reason="insufficient margin"
        )
        assert err.reason == "insufficient margin"
        assert "insufficient margin" in str(err)
        assert isinstance(err, BrokerOrderError)

    def test_rejected_pickle_preserves_reason(self) -> None:
        err = BrokerOrderRejectedError(
            "rejected", "fyers", reason="margin", metadata={"sym": "X"}
        )
        restored = pickle.loads(pickle.dumps(err))
        assert restored.reason == "margin"
        assert restored.metadata == {"sym": "X"}

    def test_rate_limit_carries_retry_after(self) -> None:
        err = BrokerRateLimitError("slow down", "fyers", retry_after=2.5)
        assert err.retry_after == 2.5
        assert "retry after 2.5s" in str(err)

    def test_rate_limit_without_retry_after(self) -> None:
        err = BrokerRateLimitError("slow down", "fyers")
        assert err.retry_after is None
        assert "retry after" not in str(err)

    def test_rate_limit_pickle_preserves_retry_after(self) -> None:
        err = BrokerRateLimitError("slow", "fyers", retry_after=1.0)
        restored = pickle.loads(pickle.dumps(err))
        assert restored.retry_after == 1.0

    def test_session_expired_distinct_from_auth(self) -> None:
        # Both must catch as BrokerError but be independently catchable.
        with pytest.raises(BrokerSessionExpiredError):
            raise BrokerSessionExpiredError("expired", "fyers")
        with pytest.raises(BrokerAuthError):
            raise BrokerAuthError("bad creds", "fyers")
        assert not issubclass(BrokerSessionExpiredError, BrokerAuthError)

    def test_catch_all_via_broker_error(self) -> None:
        for cls in (
            BrokerAuthError,
            BrokerSessionExpiredError,
            BrokerOrderError,
            BrokerOrderRejectedError,
            BrokerConnectionError,
            BrokerRateLimitError,
            BrokerInvalidSymbolError,
            BrokerInsufficientFundsError,
        ):
            with pytest.raises(BrokerError):
                if cls is BrokerOrderRejectedError:
                    raise cls("x", "fyers", reason="r")
                raise cls("x", "fyers")
