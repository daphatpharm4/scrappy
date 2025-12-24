from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    environment: str = Field(default="dev")
    api_prefix: str = Field(default="/api")
    azure_client_id: Optional[str] = Field(default=None, env="AZURE_CLIENT_ID")
    azure_tenant_id: Optional[str] = Field(default=None, env="AZURE_TENANT_ID")
    key_vault_name: Optional[str] = Field(default=None, env="KEY_VAULT_NAME")
    api_auth_secret_name: str = Field(default="API_AUTH_TOKEN", env="API_AUTH_SECRET_NAME")
    api_auth_fallback: Optional[str] = Field(default=None, env="API_AUTH_TOKEN")
    storage_account: str = Field(default="", env="AZURE_STORAGE_ACCOUNT")
    blob_container: str = Field(default="", env="BLOB_CONTAINER")
    blob_prefix_clean: str = Field(default="clean", env="BLOB_PREFIX_CLEAN")
    blob_prefix_curated: str = Field(default="curated", env="BLOB_PREFIX_CURATED")
    cache_dir: str = Field(default="/tmp/cache")
    cache_ttl_seconds: int = Field(default=300)
    data_base_path: Optional[str] = Field(default=None, env="DATA_BASE_PATH")

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
