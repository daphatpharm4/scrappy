from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from app.cache import CacheManager
from app.config import Settings
from app.data import DataAccessError, DataRepository
from app.models import AnalyticsQuery, PriceQuery, RealEstateQuery


@pytest.fixture()
def sample_settings(tmp_path: Path) -> Settings:
    cache_dir = tmp_path / "cache"
    return Settings(
        cache_dir=str(cache_dir),
        cache_ttl_seconds=1,
        data_base_path=str(tmp_path),
        blob_prefix_clean="clean",
    )


@pytest.fixture()
def price_data(tmp_path: Path) -> None:
    path = tmp_path / "clean" / "prices"
    path.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(
        {
            "provider": ["ONE", "TWO", "ONE"],
            "country": ["KEN", "KEN", "CMR"],
            "date": [date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1)],
            "price": [10.0, 20.0, 30.0],
        }
    )
    df.write_parquet(path / "data.parquet")


@pytest.fixture()
def realestate_data(tmp_path: Path) -> None:
    path = tmp_path / "clean" / "realestate"
    path.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(
        {
            "provider": ["HOMES", "HOMES"],
            "country": ["KEN", "CMR"],
            "date": [date(2024, 1, 15), date(2024, 1, 20)],
            "bedrooms": [2, 4],
        }
    )
    df.write_parquet(path / "listings.parquet")


@pytest.fixture()
def provider_data(tmp_path: Path) -> None:
    path = tmp_path / "clean" / "providers"
    path.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame({"provider": ["ONE", "TWO", "HOMES"]})
    df.write_parquet(path / "providers.parquet")


@pytest.fixture()
def repository(sample_settings: Settings, price_data: None, realestate_data: None, provider_data: None) -> DataRepository:
    cache = CacheManager(sample_settings.cache_dir, sample_settings.cache_ttl_seconds)
    return DataRepository(sample_settings, cache)


def test_cache_refreshes_on_ttl(sample_settings: Settings) -> None:
    cache = CacheManager(sample_settings.cache_dir, sample_settings.cache_ttl_seconds)
    cache.write_bytes("demo", b"content")
    assert cache.is_fresh("demo")

    stale_time = time.time() - (sample_settings.cache_ttl_seconds + 5)
    os.utime(cache.path_for_key("demo"), (stale_time, stale_time))
    assert not cache.is_fresh("demo")


def test_price_filters(repository: DataRepository) -> None:
    query = PriceQuery(provider="one", start_date=date(2024, 1, 15), max_price=15.0)
    rows = repository.fetch_prices(query)
    assert len(rows) == 0

    query = PriceQuery(provider="one", end_date=date(2024, 2, 1), max_price=15.0)
    rows = repository.fetch_prices(query)
    assert len(rows) == 1
    assert rows[0]["price"] == 10.0


def test_realestate_filters(repository: DataRepository) -> None:
    query = RealEstateQuery(min_bedrooms=3)
    rows = repository.fetch_realestate(query)
    assert len(rows) == 1
    assert rows[0]["bedrooms"] == 4


def test_provider_summary(repository: DataRepository) -> None:
    query = AnalyticsQuery()
    summary = repository.fetch_provider_summary("prices", query)
    assert {row["provider"] for row in summary} == {"ONE", "TWO"}


def test_list_providers(repository: DataRepository) -> None:
    providers = repository.list_providers()
    assert providers == ["HOMES", "ONE", "TWO"]


def test_missing_dataset_raises(sample_settings: Settings) -> None:
    cache = CacheManager(sample_settings.cache_dir, sample_settings.cache_ttl_seconds)
    repo = DataRepository(sample_settings, cache)
    with pytest.raises(DataAccessError):
        repo.fetch_dataset("missing", PriceQuery())
