from __future__ import annotations

from datetime import date

import pandas as pd

from africa_datalayer.config import DatasetConfig, StorageLayout
from africa_datalayer.pipelines.cleanse import cleanse_from_raw
from africa_datalayer.storage import LocalObjectStore


def test_cleanse_writes_validated_parquet(tmp_path):
    store = LocalObjectStore(bucket="africa-datalayer", base_path=tmp_path)
    cfg = DatasetConfig(
        country_code="KEN",
        dataset="economic_indicators",
        ingest_date=date(2024, 9, 30),
        source_url="https://example.com/data.csv",
    )
    layout = StorageLayout()

    df = pd.DataFrame(
        {
            "indicator": ["GDP"],
            "value": [1000.0],
            "year": [2023],
            "country": ["KEN"],
            "ingest_date": [cfg.ingest_date.isoformat()],
        }
    )
    raw_key = f"{layout.raw_path(cfg)}data.parquet"
    store.put_object(raw_key, df.to_parquet())

    result = cleanse_from_raw(cfg, layout, store)

    cleansed_path = tmp_path / "africa-datalayer" / result.cleansed_key
    manifest_path = tmp_path / "africa-datalayer" / layout.cleansed_path(cfg) / "manifest.json"

    assert cleansed_path.exists()
    assert manifest_path.exists()

    cleansed = pd.read_parquet(cleansed_path)
    assert len(cleansed) == 1
    assert set(cleansed.columns) == {"indicator", "value", "year", "country", "ingest_date"}
