"""Tests for the A5 Dhan credential factory in
``app.tasks.historical_backfill_tasks``.

Queue FFF Phase 2 — local-only verification. All tests are mock-based
(no DB, no Dhan network calls), so they run unmodified in CI without
a Postgres service.

Coverage:
    * 8 cases for :func:`_resolve_dhan_creds` — the full decision tree.
    * 6 supporting cases for the env-reading helpers.
    * 1 integration case wiring the resolver into the factory closure.

Mocking strategy:
    * ``_resolve_dhan_creds`` decision-tree tests mock the inner
      ``_lookup_user_dhan_creds`` to focus on the conditional logic.
    * ``_lookup_user_dhan_creds`` tests mock the SQLAlchemy session +
      ``decrypt_credential`` to focus on DB-query / decrypt handling.
    * Factory tests mock ``get_sessionmaker`` + ``_resolve_dhan_creds``
      + ``DhanHistoricalClient`` constructor.

Sensitive values never appear in logs or assertions — all "secrets"
in these tests are plainly-named fixture strings like
``"plain_client_id"`` / ``"plain_access_token"``.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════
# Constants + helpers
# ═══════════════════════════════════════════════════════════════════════

_TEST_USER_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")
_SERVICE_ACCOUNT_UUID = uuid.UUID("87654321-4321-8765-4321-876543218765")


def _make_job(*, requested_by_user_id: uuid.UUID | None) -> MagicMock:
    """Stand-in for a HistoricalBackfillJob row — only the fields the
    resolver reads."""
    job = MagicMock()
    job.requested_by_user_id = requested_by_user_id
    return job


def _make_cred(
    *,
    client_id_enc: str = "ciphertext_client",
    access_token_enc: str | None = "ciphertext_token",
) -> MagicMock:
    """Stand-in for a BrokerCredential row — only the fields the lookup
    reads."""
    cred = MagicMock()
    cred.client_id_enc = client_id_enc
    cred.access_token_enc = access_token_enc
    return cred


def _make_session_returning(cred_or_none) -> MagicMock:
    """Build an async-mock session whose execute().scalar_one_or_none()
    returns the supplied value."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=cred_or_none)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


def _clear_backfill_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "BACKFILL_DHAN_USER_ID",
        "BACKFILL_DHAN_CLIENT_ID",
        "BACKFILL_DHAN_ACCESS_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)


# ═══════════════════════════════════════════════════════════════════════
# _service_account_user_id (env-reading helper, beta path)
# ═══════════════════════════════════════════════════════════════════════


def test_service_account_user_id__unset_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BACKFILL_DHAN_USER_ID", raising=False)
    from app.tasks.historical_backfill_tasks import _service_account_user_id

    assert _service_account_user_id() is None


def test_service_account_user_id__valid_uuid_parsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BACKFILL_DHAN_USER_ID", str(_TEST_USER_UUID))
    from app.tasks.historical_backfill_tasks import _service_account_user_id

    result = _service_account_user_id()
    assert isinstance(result, uuid.UUID)
    assert result == _TEST_USER_UUID


def test_service_account_user_id__invalid_format_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid UUID format → None (caller falls through to alpha / error).
    Should NOT raise."""
    monkeypatch.setenv("BACKFILL_DHAN_USER_ID", "definitely-not-a-uuid")
    from app.tasks.historical_backfill_tasks import _service_account_user_id

    assert _service_account_user_id() is None


# ═══════════════════════════════════════════════════════════════════════
# _env_direct_creds (env-reading helper, alpha path)
# ═══════════════════════════════════════════════════════════════════════


def test_env_direct_creds__both_set_returns_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BACKFILL_DHAN_CLIENT_ID", "plain_client_id")
    monkeypatch.setenv("BACKFILL_DHAN_ACCESS_TOKEN", "plain_access_token")
    from app.tasks.historical_backfill_tasks import _env_direct_creds

    assert _env_direct_creds() == ("plain_client_id", "plain_access_token")


def test_env_direct_creds__only_client_id_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Partial config rejected — defense against half-rotated env."""
    monkeypatch.setenv("BACKFILL_DHAN_CLIENT_ID", "plain_client_id")
    monkeypatch.delenv("BACKFILL_DHAN_ACCESS_TOKEN", raising=False)
    from app.tasks.historical_backfill_tasks import _env_direct_creds

    assert _env_direct_creds() is None


def test_env_direct_creds__both_unset_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BACKFILL_DHAN_CLIENT_ID", raising=False)
    monkeypatch.delenv("BACKFILL_DHAN_ACCESS_TOKEN", raising=False)
    from app.tasks.historical_backfill_tasks import _env_direct_creds

    assert _env_direct_creds() is None


# ═══════════════════════════════════════════════════════════════════════
# _lookup_user_dhan_creds — DB + decrypt path (low-level)
# ═══════════════════════════════════════════════════════════════════════


async def test_lookup_user_dhan_creds__happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.tasks.historical_backfill_tasks import _lookup_user_dhan_creds

    cred = _make_cred(client_id_enc="ciphertext_client", access_token_enc="ciphertext_token")
    session = _make_session_returning(cred)

    with patch(
        "app.core.security.decrypt_credential",
        side_effect=lambda s: s.replace("ciphertext", "plain"),
    ):
        client_id, access_token, returned_user_id = await _lookup_user_dhan_creds(
            session, _TEST_USER_UUID, source="per_user"
        )

    assert client_id == "plain_client"
    assert access_token == "plain_token"
    assert returned_user_id == _TEST_USER_UUID
    session.execute.assert_awaited_once()


async def test_lookup_user_dhan_creds__no_cred_raises_brokerautherror() -> None:
    """Case 2 (resolver): per-user lookup finds no cred → BrokerAuthError."""
    from app.brokers.dhan_historical import BrokerAuthError
    from app.tasks.historical_backfill_tasks import _lookup_user_dhan_creds

    session = _make_session_returning(None)
    with pytest.raises(BrokerAuthError, match="No active Dhan BrokerCredential"):
        await _lookup_user_dhan_creds(session, _TEST_USER_UUID, source="per_user")


async def test_lookup_user_dhan_creds__no_access_token_raises() -> None:
    """Case 3 (resolver): cred present but access_token_enc=None →
    BrokerAuthError."""
    from app.brokers.dhan_historical import BrokerAuthError
    from app.tasks.historical_backfill_tasks import _lookup_user_dhan_creds

    cred = _make_cred(access_token_enc=None)
    session = _make_session_returning(cred)
    with pytest.raises(BrokerAuthError, match="access_token not stored"):
        await _lookup_user_dhan_creds(session, _TEST_USER_UUID, source="per_user")


async def test_lookup_user_dhan_creds__decrypt_failure_wrapped() -> None:
    """Case 4 (resolver, Q3): decrypt_credential raises → wrapped in
    BrokerAuthError. Underlying exception chained via __cause__."""
    from app.brokers.dhan_historical import BrokerAuthError
    from app.tasks.historical_backfill_tasks import _lookup_user_dhan_creds

    cred = _make_cred()
    session = _make_session_returning(cred)

    class _SimulatedDecryptError(RuntimeError):
        pass

    with (
        patch(
            "app.core.security.decrypt_credential",
            side_effect=_SimulatedDecryptError("token mac mismatch"),
        ),
        pytest.raises(BrokerAuthError, match="decryption failed") as excinfo,
    ):
        await _lookup_user_dhan_creds(session, _TEST_USER_UUID, source="per_user")
    # Original exception chained for debugging without leaking secrets.
    assert isinstance(excinfo.value.__cause__, _SimulatedDecryptError)


# ═══════════════════════════════════════════════════════════════════════
# _resolve_dhan_creds — the 8 main decision-tree cases
# ═══════════════════════════════════════════════════════════════════════


async def test_resolve__case1_per_user_path_used_when_id_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case 1: job.requested_by_user_id set → per-user path."""
    _clear_backfill_env(monkeypatch)
    from app.tasks.historical_backfill_tasks import _resolve_dhan_creds

    job = _make_job(requested_by_user_id=_TEST_USER_UUID)
    session = MagicMock()

    with patch(
        "app.tasks.historical_backfill_tasks._lookup_user_dhan_creds",
        new=AsyncMock(return_value=("client_id_per_user", "token_per_user", _TEST_USER_UUID)),
    ) as mock_lookup:
        client_id, access_token, user_id = await _resolve_dhan_creds(session, job)

    assert client_id == "client_id_per_user"
    assert access_token == "token_per_user"
    assert user_id == _TEST_USER_UUID
    mock_lookup.assert_awaited_once_with(session, _TEST_USER_UUID, source="per_user")


async def test_resolve__case2_per_user_no_cred_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case 2: per-user path returns no cred → BrokerAuthError propagates."""
    _clear_backfill_env(monkeypatch)
    from app.brokers.dhan_historical import BrokerAuthError
    from app.tasks.historical_backfill_tasks import _resolve_dhan_creds

    job = _make_job(requested_by_user_id=_TEST_USER_UUID)
    session = MagicMock()

    with (
        patch(
            "app.tasks.historical_backfill_tasks._lookup_user_dhan_creds",
            new=AsyncMock(
                side_effect=BrokerAuthError(
                    f"No active Dhan BrokerCredential for user {_TEST_USER_UUID} (source=per_user)."
                )
            ),
        ),
        pytest.raises(BrokerAuthError, match="No active Dhan"),
    ):
        await _resolve_dhan_creds(session, job)


async def test_resolve__case3_per_user_no_access_token_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case 3: per-user cred has no access_token → BrokerAuthError."""
    _clear_backfill_env(monkeypatch)
    from app.brokers.dhan_historical import BrokerAuthError
    from app.tasks.historical_backfill_tasks import _resolve_dhan_creds

    job = _make_job(requested_by_user_id=_TEST_USER_UUID)
    session = MagicMock()

    with (
        patch(
            "app.tasks.historical_backfill_tasks._lookup_user_dhan_creds",
            new=AsyncMock(side_effect=BrokerAuthError("Dhan access_token not stored ...")),
        ),
        pytest.raises(BrokerAuthError, match="access_token not stored"),
    ):
        await _resolve_dhan_creds(session, job)


async def test_resolve__case4_decrypt_failure_wrapped_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case 4 (Q3): per-user decrypt failure wrapped as BrokerAuthError."""
    _clear_backfill_env(monkeypatch)
    from app.brokers.dhan_historical import BrokerAuthError
    from app.tasks.historical_backfill_tasks import _resolve_dhan_creds

    job = _make_job(requested_by_user_id=_TEST_USER_UUID)
    session = MagicMock()

    with (
        patch(
            "app.tasks.historical_backfill_tasks._lookup_user_dhan_creds",
            new=AsyncMock(
                side_effect=BrokerAuthError(
                    "Dhan credential decryption failed for user ... (source=per_user): InvalidToken"
                )
            ),
        ),
        pytest.raises(BrokerAuthError, match="decryption failed"),
    ):
        await _resolve_dhan_creds(session, job)


async def test_resolve__case5_service_account_db_path_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case 5: job.requested_by_user_id=None + BACKFILL_DHAN_USER_ID set
    → service-account beta (DB) path."""
    _clear_backfill_env(monkeypatch)
    monkeypatch.setenv("BACKFILL_DHAN_USER_ID", str(_SERVICE_ACCOUNT_UUID))
    from app.tasks.historical_backfill_tasks import _resolve_dhan_creds

    job = _make_job(requested_by_user_id=None)
    session = MagicMock()

    with patch(
        "app.tasks.historical_backfill_tasks._lookup_user_dhan_creds",
        new=AsyncMock(return_value=("client_id_svc", "token_svc", _SERVICE_ACCOUNT_UUID)),
    ) as mock_lookup:
        client_id, access_token, user_id = await _resolve_dhan_creds(session, job)

    assert client_id == "client_id_svc"
    assert access_token == "token_svc"
    assert user_id == _SERVICE_ACCOUNT_UUID
    # Confirm beta path was taken — lookup called with the service-account UUID
    # from env, NOT job.requested_by_user_id (which is None).
    mock_lookup.assert_awaited_once_with(
        session, _SERVICE_ACCOUNT_UUID, source="service_account_db"
    )


async def test_resolve__case6_service_account_env_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case 6: no user_id, no beta env, but alpha env vars BOTH set
    → returns env values + the _BACKFILL_SERVICE_ACCOUNT_USER_ID sentinel."""
    _clear_backfill_env(monkeypatch)
    monkeypatch.setenv("BACKFILL_DHAN_CLIENT_ID", "env_client_id")
    monkeypatch.setenv("BACKFILL_DHAN_ACCESS_TOKEN", "env_access_token")
    from app.tasks.historical_backfill_tasks import (
        _BACKFILL_SERVICE_ACCOUNT_USER_ID,
        _resolve_dhan_creds,
    )

    job = _make_job(requested_by_user_id=None)
    session = MagicMock()

    client_id, access_token, user_id = await _resolve_dhan_creds(session, job)

    assert client_id == "env_client_id"
    assert access_token == "env_access_token"
    assert user_id == _BACKFILL_SERVICE_ACCOUNT_USER_ID
    # No DB lookup happened
    session.execute.assert_not_called()


async def test_resolve__case7_beta_wins_when_both_beta_and_alpha_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case 7: no user_id, BOTH beta (BACKFILL_DHAN_USER_ID) and alpha
    (env-direct) set → beta path wins (DB lookup happens, env-direct ignored)."""
    _clear_backfill_env(monkeypatch)
    monkeypatch.setenv("BACKFILL_DHAN_USER_ID", str(_SERVICE_ACCOUNT_UUID))
    monkeypatch.setenv("BACKFILL_DHAN_CLIENT_ID", "env_client_id")
    monkeypatch.setenv("BACKFILL_DHAN_ACCESS_TOKEN", "env_access_token")
    from app.tasks.historical_backfill_tasks import _resolve_dhan_creds

    job = _make_job(requested_by_user_id=None)
    session = MagicMock()

    with patch(
        "app.tasks.historical_backfill_tasks._lookup_user_dhan_creds",
        new=AsyncMock(return_value=("client_id_beta", "token_beta", _SERVICE_ACCOUNT_UUID)),
    ) as mock_lookup:
        client_id, access_token, user_id = await _resolve_dhan_creds(session, job)

    # beta values used, not alpha
    assert client_id == "client_id_beta"
    assert access_token == "token_beta"
    assert user_id == _SERVICE_ACCOUNT_UUID
    mock_lookup.assert_awaited_once_with(
        session, _SERVICE_ACCOUNT_UUID, source="service_account_db"
    )


async def test_resolve__case8_nothing_configured_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case 8: no user_id, no beta env, no alpha env → BrokerAuthError."""
    _clear_backfill_env(monkeypatch)
    from app.brokers.dhan_historical import BrokerAuthError
    from app.tasks.historical_backfill_tasks import _resolve_dhan_creds

    job = _make_job(requested_by_user_id=None)
    session = MagicMock()

    with pytest.raises(BrokerAuthError, match="No Dhan credentials configured"):
        await _resolve_dhan_creds(session, job)
    session.execute.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# _dhan_client_factory_for_job — integration with the closure
# ═══════════════════════════════════════════════════════════════════════


async def test_factory__wires_resolver_into_dhan_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Factory builds a DhanHistoricalClient with the resolved
    client_id/access_token/user_id."""
    _clear_backfill_env(monkeypatch)
    from app.tasks.historical_backfill_tasks import _dhan_client_factory_for_job

    job = _make_job(requested_by_user_id=_TEST_USER_UUID)

    # Mock the resolver to return known values
    mock_resolver = AsyncMock(return_value=("resolved_client", "resolved_token", _TEST_USER_UUID))

    # Mock the session maker (yields an async-context-manager mock)
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_maker = MagicMock(return_value=mock_session)

    # Mock the DhanHistoricalClient class so we don't make a network call
    mock_client_instance = MagicMock()

    with (
        patch(
            "app.tasks.historical_backfill_tasks._resolve_dhan_creds",
            new=mock_resolver,
        ),
        patch("app.db.session.get_sessionmaker", return_value=mock_maker),
        patch(
            "app.brokers.dhan_historical.DhanHistoricalClient",
            return_value=mock_client_instance,
        ) as mock_client_ctor,
    ):
        factory = _dhan_client_factory_for_job(job)
        client = await factory()

    assert client is mock_client_instance
    mock_resolver.assert_awaited_once()
    mock_client_ctor.assert_called_once_with(
        client_id="resolved_client",
        access_token="resolved_token",
        user_id=_TEST_USER_UUID,
    )


# ═══════════════════════════════════════════════════════════════════════
# Sentinel UUID identity
# ═══════════════════════════════════════════════════════════════════════


def test_backfill_service_account_user_id_is_two_not_zero_or_one() -> None:
    """Sister to _SMOKE_TEST_USER_ID (...0001); …0000 is a test fixture
    elsewhere. Backfill service-account = …0002."""
    from app.tasks.historical_backfill_tasks import (
        _BACKFILL_SERVICE_ACCOUNT_USER_ID,
    )

    assert uuid.UUID("00000000-0000-0000-0000-000000000002") == _BACKFILL_SERVICE_ACCOUNT_USER_ID
