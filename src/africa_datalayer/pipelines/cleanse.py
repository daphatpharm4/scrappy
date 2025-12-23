from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Callable, List

import pandas as pd
import pandera as pa
import pyarrow as pa_arrow
import pyarrow.parquet as pq
from pandera.typing import DataFrame, Series

from ..config import DatasetConfig, StorageLayout
from ..storage import ObjectStore, write_json
from ..utils.frame import ensure_partition_columns, normalize_columns


class EconomicIndicatorSchema(pa.SchemaModel):
    country: Series[str] = pa.Field(isin=["KEN", "CMR", "NGA", "ZAF", "EGY"])
    indicator: Series[str]
    value: Series[float] = pa.Field(coerce=True)
    year: Series[int] = pa.Field(ge=1900)
    ingest_date: Series[str]


@dataclass(slots=True)
class CleansingResult:
    cleansed_key: str
    row_count: int
    columns: List[str]


Loader = Callable[[], bytes]


def cleanse_parquet_bytes(parquet_payload: bytes, schema: pa.SchemaModel = EconomicIndicatorSchema) -> pd.DataFrame:
    df = pd.read_parquet(io.BytesIO(parquet_payload))
    normalized = normalize_columns(df)
    if "country" not in normalized.columns or "ingest_date" not in normalized.columns:
        raise ValueError("Input parquet is missing required partition columns: country and ingest_date")
    enriched = ensure_partition_columns(
        normalized,
        country_code=str(normalized["country"].iloc[0]),
        ingest_date=str(normalized["ingest_date"].iloc[0]),
    )
    validated: DataFrame[EconomicIndicatorSchema] = schema.validate(enriched)
    return validated


def write_cleansed(
    cfg: DatasetConfig,
    layout: StorageLayout,
    store: ObjectStore,
    loader: Loader,
    schema: pa.SchemaModel = EconomicIndicatorSchema,
) -> CleansingResult:
    parquet_payload = loader()
    df = cleanse_parquet_bytes(parquet_payload, schema=schema)

    cleansed_key = f"{layout.cleansed_path(cfg)}data.parquet"
    manifest_key = f"{layout.cleansed_path(cfg)}manifest.json"

    table = pa_arrow.Table.from_pandas(df)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="zstd")
    store.put_object(cleansed_key, buf.getvalue(), content_type="application/octet-stream")

    write_json(
        store,
        manifest_key,
        {
            "row_count": len(df),
            "columns": list(df.columns),
            "partition": {
                "country": cfg.country_code,
                "ingest_date": cfg.ingest_date.isoformat(),
            },
        },
    )

    return CleansingResult(cleansed_key=cleansed_key, row_count=len(df), columns=list(df.columns))


def load_raw_object(store: ObjectStore, key: str) -> bytes:
    return store.get_object(key)


def cleanse_from_raw(cfg: DatasetConfig, layout: StorageLayout, store: ObjectStore) -> CleansingResult:
    raw_key = f"{layout.raw_path(cfg)}data.parquet"
    return write_cleansed(cfg, layout, store, lambda: store.get_object(raw_key))
