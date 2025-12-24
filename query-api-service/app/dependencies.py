from __future__ import annotations

from fastapi import Depends

from .auth import get_token_provider, require_auth
from .cache import CacheManager
from .config import Settings, get_settings
from .data import DataRepository


def get_cache_manager(settings: Settings = Depends(get_settings)) -> CacheManager:
    return CacheManager(settings.cache_dir, settings.cache_ttl_seconds)


def get_data_repository(
    settings: Settings = Depends(get_settings), cache: CacheManager = Depends(get_cache_manager)
) -> DataRepository:
    return DataRepository(settings=settings, cache=cache)


__all__ = [
    "get_cache_manager",
    "get_data_repository",
    "get_settings",
    "get_token_provider",
    "require_auth",
    "Settings",
]
