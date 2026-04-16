"""Broker exception hierarchy.

Every broker integration MUST raise from this hierarchy — never bare
``Exception``. Upstream services (kill switch, retry middleware, circuit
breaker) react to specific subclasses, so swallowing a typed error inside
a generic ``Exception`` would silently break those guarantees.

Design notes:
    * Exceptions are picklable — Celery tasks may need to ship them across
      process boundaries, so ``__reduce__`` is implemented explicitly
      instead of relying on the ``args`` heuristic that breaks once we
      add keyword-only fields.
    * ``__str__`` is human-readable (broker prefix + message + cause), so
      log lines and Sentry events stay scannable without unpacking.
    * Every exception carries an optional ``metadata`` dict for structured
      context (request id, symbol, etc.) that the logger can spread into
      a JSON payload.
"""

from __future__ import annotations

from typing import Any


class BrokerError(Exception):
    """Root of the broker exception hierarchy.

    Subclasses should not override ``__init__`` unless they add their own
    typed fields (e.g. ``BrokerOrderRejectedError.reason``); rely on the
    ``metadata`` bag for everything else.
    """

    def __init__(
        self,
        message: str,
        broker_name: str,
        original_error: BaseException | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.broker_name = broker_name
        self.original_error = original_error
        self.metadata: dict[str, Any] = dict(metadata) if metadata else {}

    def __str__(self) -> str:
        base = f"[{self.broker_name}] {self.message}"
        if self.original_error is not None:
            base = f"{base} (caused by {type(self.original_error).__name__}: {self.original_error})"
        return base

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(message={self.message!r}, "
            f"broker_name={self.broker_name!r}, "
            f"original_error={self.original_error!r}, "
            f"metadata={self.metadata!r})"
        )

    def __reduce__(self) -> tuple[Any, ...]:
        # Explicit pickling — keeps subclasses with extra kwargs round-tripping.
        state = self._pickle_state()
        return (_rebuild_broker_error, (type(self), state))

    def _pickle_state(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "broker_name": self.broker_name,
            "original_error": self.original_error,
            "metadata": self.metadata,
        }


def _rebuild_broker_error(cls: type[BrokerError], state: dict[str, Any]) -> BrokerError:
    """Module-level rebuilder so pickle can find it by qualified name."""
    return cls(**state)


# ═══════════════════════════════════════════════════════════════════════
# Authentication / session
# ═══════════════════════════════════════════════════════════════════════


class BrokerAuthError(BrokerError):
    """Login or credential failure (bad API key, bad PIN, account locked).

    Non-recoverable from the system's perspective — surfacing this should
    pause the user's strategy and notify them, not retry.
    """


class BrokerSessionExpiredError(BrokerError):
    """Access token expired mid-flight — auto-retry trigger.

    Raised when the broker rejects a call with the equivalent of HTTP 401
    AFTER a previously valid login. The order/data layer should catch
    this once, call ``login()`` to refresh, and replay the original call.
    """


# ═══════════════════════════════════════════════════════════════════════
# Order management
# ═══════════════════════════════════════════════════════════════════════


class BrokerOrderError(BrokerError):
    """Generic order-flow failure (place / modify / cancel)."""


class BrokerOrderRejectedError(BrokerOrderError):
    """Broker rejected the order (margin, price band, freeze qty, etc.).

    Carries the broker's textual ``reason`` so audit logs and user-facing
    notifications can show exactly why the order died.
    """

    def __init__(
        self,
        message: str,
        broker_name: str,
        reason: str,
        original_error: BaseException | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, broker_name, original_error, metadata)
        self.reason = reason

    def __str__(self) -> str:
        return f"{super().__str__()} — reason: {self.reason}"

    def _pickle_state(self) -> dict[str, Any]:
        state = super()._pickle_state()
        state["reason"] = self.reason
        return state


# ═══════════════════════════════════════════════════════════════════════
# Connectivity
# ═══════════════════════════════════════════════════════════════════════


class BrokerConnectionError(BrokerError):
    """Network failure / broker API unreachable — circuit breaker trigger.

    The circuit breaker counts these and opens once the threshold is hit,
    so do not raise this for HTTP 4xx — only for genuine transport-level
    failures (DNS, TCP, TLS, 5xx without body, timeouts).
    """


class BrokerRateLimitError(BrokerError):
    """Broker rate-limit hit. ``retry_after`` is seconds the caller should sleep."""

    def __init__(
        self,
        message: str,
        broker_name: str,
        retry_after: float | None = None,
        original_error: BaseException | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, broker_name, original_error, metadata)
        self.retry_after = retry_after

    def __str__(self) -> str:
        if self.retry_after is not None:
            return f"{super().__str__()} — retry after {self.retry_after}s"
        return super().__str__()

    def _pickle_state(self) -> dict[str, Any]:
        state = super()._pickle_state()
        state["retry_after"] = self.retry_after
        return state


# ═══════════════════════════════════════════════════════════════════════
# Validation / business rule
# ═══════════════════════════════════════════════════════════════════════


class BrokerInvalidSymbolError(BrokerError):
    """Symbol not found in the broker's master list."""


class BrokerInsufficientFundsError(BrokerError):
    """Insufficient margin / cash to place the order.

    Distinct from generic rejection — the kill switch reads this directly
    to decide whether to pause the strategy versus simply log-and-continue.
    """


__all__ = [
    "BrokerAuthError",
    "BrokerConnectionError",
    "BrokerError",
    "BrokerInsufficientFundsError",
    "BrokerInvalidSymbolError",
    "BrokerOrderError",
    "BrokerOrderRejectedError",
    "BrokerRateLimitError",
    "BrokerSessionExpiredError",
]
