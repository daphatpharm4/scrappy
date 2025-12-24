from __future__ import annotations

import time
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, get_settings


class TokenProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cached_token: Optional[str] = settings.api_auth_fallback
        self._fetched_at: Optional[float] = None

    def _vault_client(self) -> SecretClient:
        if not self.settings.key_vault_name:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Key Vault not configured")
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        vault_url = f"https://{self.settings.key_vault_name}.vault.azure.net"
        return SecretClient(vault_url=vault_url, credential=credential)

    def _should_refresh(self) -> bool:
        if self._cached_token is None:
            return True
        if not self.settings.key_vault_name:
            return False
        if self._fetched_at is None:
            return True
        return (time.time() - self._fetched_at) > self.settings.cache_ttl_seconds

    def _fetch_secret_from_vault(self) -> str:
        client = self._vault_client()
        secret = client.get_secret(self.settings.api_auth_secret_name)
        self._fetched_at = time.time()
        return secret.value

    def expected_token(self) -> str:
        if self._should_refresh():
            self._cached_token = self._fetch_secret_from_vault()
        if not self._cached_token:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth token unavailable")
        return self._cached_token

    def validate(self, credentials: Optional[HTTPAuthorizationCredentials]) -> None:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
        expected = self.expected_token()
        if credentials.credentials != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")


def get_token_provider(settings: Settings = Depends(get_settings)) -> TokenProvider:
    return TokenProvider(settings)


bearer_scheme = HTTPBearer(auto_error=False)


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    token_provider: TokenProvider = Depends(get_token_provider),
) -> None:
    token_provider.validate(credentials)
