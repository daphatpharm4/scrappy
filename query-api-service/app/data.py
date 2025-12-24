from __future__ import annotations

from pathlib import Path
from typing import List

import polars as pl
import requests

from .cache import CacheManager
from .config import Settings
from .models import AnalyticsQuery, BaseDataQuery, PriceQuery, RealEstateQuery


class DataAccessError(Exception):
    pass


class DataRepository:
    def __init__(self, settings: Settings, cache: CacheManager) -> None:
        self.settings = settings
        self.cache = cache

    @property
    def base_path(self) -> Path:
        if self.settings.data_base_path:
            return Path(self.settings.data_base_path)
        return Path(".")

    def _dataset_root(self, dataset: str) -> Path:
        return self.base_path / self.settings.blob_prefix_clean / dataset

    def _cache_key_for_path(self, path: str) -> str:
        return f"parquet_{path}"

    def _resolve_source(self, path: str) -> Path:
        candidate = Path(path)
        if candidate.is_absolute() or candidate.exists():
            return candidate
        return (self.base_path / path).resolve()

    def _download_to_cache(self, path: str) -> Path:
        cache_key = self._cache_key_for_path(path)
        if self.cache.is_fresh(cache_key):
            return self.cache.path_for_key(cache_key)

        resolved = self._resolve_source(path)
        if resolved.exists():
            data = resolved.read_bytes()
        else:
            # Fallback to HTTP/HTTPS download when file is remote.
            try:
                response = requests.get(path, timeout=30)
                response.raise_for_status()
            except requests.RequestException as exc:  # pragma: no cover - network failure
                raise DataAccessError(f"Failed to download parquet at {path}") from exc
            data = response.content

        return self.cache.write_bytes(cache_key, data)

    def _list_parquet_files(self, dataset: str) -> List[str]:
        cache_key = f"list_{dataset}"

        def loader() -> List[str]:
            root = self._dataset_root(dataset)
            if not root.exists():
                raise DataAccessError(f"Dataset path not found: {root}")
            return [str(p) for p in root.rglob("*.parquet")]

        return self.cache.get_or_set_json(cache_key, loader)

    def _read_lazyframe(self, dataset: str) -> pl.LazyFrame:
        paths = [self._download_to_cache(path) for path in self._list_parquet_files(dataset)]
        if not paths:
            raise DataAccessError(f"No parquet files available for dataset '{dataset}'")
        return pl.scan_parquet([str(p) for p in paths])

    def _apply_common_filters(self, lf: pl.LazyFrame, query: BaseDataQuery) -> pl.LazyFrame:
        schema = lf.collect_schema()

        def has_column(name: str) -> bool:
            return name in schema

        if query.provider and has_column("provider"):
            lf = lf.filter(pl.col("provider") == query.provider)
        if query.country and has_column("country"):
            lf = lf.filter(pl.col("country") == query.country)
        if query.region and has_column("region"):
            lf = lf.filter(pl.col("region") == query.region)
        if has_column("date"):
            lf = lf.with_columns(pl.col("date").cast(pl.Date, strict=False))
            if query.start_date:
                lf = lf.filter(pl.col("date") >= pl.lit(query.start_date))
            if query.end_date:
                lf = lf.filter(pl.col("date") <= pl.lit(query.end_date))
        if query.limit:
            lf = lf.limit(query.limit)
        return lf

    def fetch_dataset(self, dataset: str, query: BaseDataQuery) -> list[dict]:
        lf = self._apply_common_filters(self._read_lazyframe(dataset), query)
        return lf.collect().to_dicts()

    def fetch_prices(self, query: PriceQuery) -> list[dict]:
        lf = self._apply_common_filters(self._read_lazyframe("prices"), query)
        schema = lf.collect_schema()
        if "price" in schema:
            if query.min_price is not None:
                lf = lf.filter(pl.col("price") >= pl.lit(query.min_price))
            if query.max_price is not None:
                lf = lf.filter(pl.col("price") <= pl.lit(query.max_price))
        return lf.collect().to_dicts()

    def fetch_realestate(self, query: RealEstateQuery) -> list[dict]:
        lf = self._apply_common_filters(self._read_lazyframe("realestate"), query)
        schema = lf.collect_schema()
        if "bedrooms" in schema:
            if query.min_bedrooms is not None:
                lf = lf.filter(pl.col("bedrooms") >= pl.lit(query.min_bedrooms))
            if query.max_bedrooms is not None:
                lf = lf.filter(pl.col("bedrooms") <= pl.lit(query.max_bedrooms))
        return lf.collect().to_dicts()

    def fetch_provider_summary(self, dataset: str, query: AnalyticsQuery) -> list[dict]:
        lf = self._apply_common_filters(self._read_lazyframe(dataset), query)
        schema = lf.collect_schema()
        metric_column = query.metric or ("price" if "price" in schema else "value")
        if metric_column not in schema:
            raise DataAccessError(f"Metric column '{metric_column}' not found")
        grouped = (
            lf.group_by("provider")
            .agg(
                pl.col(metric_column).mean().alias("avg"),
                pl.col(metric_column).sum().alias("total"),
                pl.len().alias("count"),
            )
            .sort("provider")
        )
        return grouped.collect().to_dicts()

    def list_providers(self) -> list[str]:
        lf = self._read_lazyframe("providers")
        schema = lf.collect_schema()
        if "provider" not in schema:
            raise DataAccessError("'provider' column missing from providers dataset")
        providers = lf.select("provider").unique().sort("provider")
        return [row[0] for row in providers.collect().to_rows()]
