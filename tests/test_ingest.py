from __future__ import annotations

from datetime import date

import pandas as pd

from africa_datalayer.config import DatasetConfig, StorageLayout
from africa_datalayer.pipelines.ingest import ingest_dataset
from africa_datalayer.storage import LocalObjectStore


def test_ingest_dataset_writes_raw_and_manifest(tmp_path):
    csv_data = """indicator,value,year\nGDP,1000,2023\n""".encode("utf-8")
    cfg = DatasetConfig(
        country_code="KEN",
        dataset="economic_indicators",
        ingest_date=date(2024, 9, 30),
        source_url="https://example.com/data.csv",
    )
    layout = StorageLayout()
    store = LocalObjectStore(bucket="africa-datalayer", base_path=tmp_path)

    result = ingest_dataset(
        cfg=cfg,
        layout=layout,
        store=store,
        fetcher=lambda: csv_data,
    )

    raw_path = tmp_path / "africa-datalayer" / result.raw_key
    manifest_path = tmp_path / "africa-datalayer" / result.manifest_key

    assert raw_path.exists()
    assert manifest_path.exists()

    df = pd.read_parquet(raw_path)
    assert list(df.columns) == ["indicator", "value", "year", "country", "ingest_date"]
    assert result.row_count == 1
    assert result.columns == ["indicator", "value", "year", "country", "ingest_date"]
