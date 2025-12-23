from __future__ import annotations

import io
import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Callable, Dict, Iterable, List

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

from ..config import DatasetConfig, StorageLayout
from ..storage import ObjectStore, write_json
from ..utils.checksum import sha256_bytes, sha256_many
from ..utils.frame import ensure_partition_columns, normalize_columns


@dataclass(slots=True)
class IngestionResult:
    raw_key: str
    manifest_key: str
    row_count: int
    columns: List[str]


@dataclass(slots=True)
class BatchMetadata:
    dataset: DatasetConfig
    storage_layout: StorageLayout
    source_checksum: str
    parquet_checksum: str
    row_count: int
    columns: List[str]

    def as_dict(self) -> Dict[str, str | int | List[str]]:
        payload = asdict(self)
        payload["dataset"] = {
            "country_code": self.dataset.country_code,
            "dataset": self.dataset.dataset,
            "ingest_date": self.dataset.ingest_date.isoformat(),
            "source_url": self.dataset.source_url,
            "source_format": self.dataset.source_format,
        }
        payload["storage_layout"] = {
            "raw_prefix": self.storage_layout.raw_prefix,
            "cleansed_prefix": self.storage_layout.cleansed_prefix,
        }
        return payload


Fetcher = Callable[[], bytes]


def http_fetcher(url: str) -> Fetcher:
    def _fetch() -> bytes:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content

    return _fetch


def dataframe_from_bytes(payload: bytes, fmt: str) -> pd.DataFrame:
    if fmt == "csv":
        return pd.read_csv(io.BytesIO(payload))
    if fmt == "json":
        return pd.read_json(io.BytesIO(payload))
    raise ValueError(f"Unsupported source format: {fmt}")


def dataframe_to_parquet_bytes(df: pd.DataFrame) -> bytes:
    table = pa.Table.from_pandas(df)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="zstd")
    return buf.getvalue()


def build_raw_key(layout: StorageLayout, cfg: DatasetConfig) -> str:
    return f"{layout.raw_path(cfg)}data.parquet"


def build_manifest_key(layout: StorageLayout, cfg: DatasetConfig) -> str:
    return f"{layout.raw_path(cfg)}manifest.json"


def create_manifest(
    cfg: DatasetConfig,
    layout: StorageLayout,
    source_payload: bytes,
    parquet_payload: bytes,
    df: pd.DataFrame,
) -> BatchMetadata:
    return BatchMetadata(
        dataset=cfg,
        storage_layout=layout,
        source_checksum=sha256_bytes(source_payload),
        parquet_checksum=sha256_bytes(parquet_payload),
        row_count=len(df),
        columns=list(df.columns),
    )


def ingest_dataset(
    cfg: DatasetConfig,
    layout: StorageLayout,
    store: ObjectStore,
    fetcher: Fetcher,
) -> IngestionResult:
    source_payload = fetcher()
    df = dataframe_from_bytes(source_payload, fmt=cfg.source_format)
    df = normalize_columns(df)
    df = ensure_partition_columns(df, country_code=cfg.country_code, ingest_date=cfg.ingest_date.isoformat())
    parquet_payload = dataframe_to_parquet_bytes(df)

    raw_key = build_raw_key(layout, cfg)
    manifest_key = build_manifest_key(layout, cfg)

    store.put_object(raw_key, parquet_payload, content_type="application/octet-stream")

    manifest = create_manifest(cfg, layout, source_payload, parquet_payload, df)
    write_json(store, manifest_key, manifest.as_dict())

    return IngestionResult(
        raw_key=raw_key,
        manifest_key=manifest_key,
        row_count=manifest.row_count,
        columns=manifest.columns,
    )


def checksum_files(store: ObjectStore, keys: Iterable[str]) -> str:
    payloads = (store.get_object(key) for key in keys)
    return sha256_many(payloads)
