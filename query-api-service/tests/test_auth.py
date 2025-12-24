from __future__ import annotations

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import TokenProvider
from app.config import Settings


class DummySecret:
    def __init__(self, value: str) -> None:
        self.value = value


class DummyClient:
    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret(self, name: str) -> DummySecret:  # pragma: no cover - trivial wrapper
        return DummySecret(self._value)


def test_auth_uses_fallback_token() -> None:
    settings = Settings(api_auth_fallback="fallback-token", key_vault_name=None)
    provider = TokenProvider(settings)

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="fallback-token")
    provider.validate(credentials)


def test_auth_fetches_from_key_vault(monkeypatch) -> None:
    settings = Settings(api_auth_fallback=None, key_vault_name="kv", cache_ttl_seconds=1)
    provider = TokenProvider(settings)

    monkeypatch.setattr(TokenProvider, "_vault_client", lambda self: DummyClient("vault-token"))

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="vault-token")
    provider.validate(credentials)

    # Cached token should be reused until TTL elapses.
    credentials_reuse = HTTPAuthorizationCredentials(scheme="Bearer", credentials="vault-token")
    provider.validate(credentials_reuse)

    # Invalid token should raise an error.
    bad_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="other")
    try:
        provider.validate(bad_credentials)
    except HTTPException as exc:
        assert exc.status_code == 401
    else:  # pragma: no cover - defensive
        assert False, "Expected an authentication error"
