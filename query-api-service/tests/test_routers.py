from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
from fastapi.testclient import TestClient

from app.cache import CacheManager
from app.config import Settings
from app.data import DataRepository
from app.dependencies import get_data_repository
from main import create_app


def build_app(tmp_path: Path) -> TestClient:
    data_root = tmp_path / "clean"
    (data_root / "prices").mkdir(parents=True)
    (data_root / "realestate").mkdir(parents=True)
    (data_root / "providers").mkdir(parents=True)

    pl.DataFrame(
        {
            "provider": ["ONE", "ONE"],
            "country": ["KEN", "KEN"],
            "date": [date(2024, 1, 1), date(2024, 1, 2)],
            "price": [5.0, 6.0],
        }
    ).write_parquet(data_root / "prices" / "data.parquet")

    pl.DataFrame(
        {
            "provider": ["HOME"],
            "country": ["KEN"],
            "date": [date(2024, 1, 5)],
            "bedrooms": [3],
        }
    ).write_parquet(data_root / "realestate" / "homes.parquet")

    pl.DataFrame({"provider": ["ONE", "HOME"]}).write_parquet(data_root / "providers" / "providers.parquet")

    settings = Settings(
        api_auth_fallback="secret",
        key_vault_name=None,
        cache_dir=str(tmp_path / "cache"),
        data_base_path=str(tmp_path),
        blob_prefix_clean="clean",
    )

    cache = CacheManager(settings.cache_dir, settings.cache_ttl_seconds)
    repository = DataRepository(settings=settings, cache=cache)
    app = create_app(settings=settings)
    app.dependency_overrides[get_data_repository] = lambda: repository

    return TestClient(app)


def test_health_endpoints(tmp_path: Path) -> None:
    client = build_app(tmp_path)
    assert client.get("/health").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_authenticated_routes(tmp_path: Path) -> None:
    client = build_app(tmp_path)
    headers = {"Authorization": "Bearer secret"}

    resp = client.get("/api/data/prices", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp_no_auth = client.get("/api/data/prices")
    assert resp_no_auth.status_code == 401

    resp_realestate = client.get("/api/data/realestate", headers=headers)
    assert resp_realestate.status_code == 200

    resp_providers = client.get("/api/data/providers", headers=headers)
    assert resp_providers.status_code == 200
    assert resp_providers.json() == ["HOME", "ONE"]

    resp_summary = client.get("/api/analytics/provider-summary", headers=headers)
    assert resp_summary.status_code == 200
