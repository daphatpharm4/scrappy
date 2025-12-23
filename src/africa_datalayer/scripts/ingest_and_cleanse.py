from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any, Dict

import yaml

from ..config import DatasetConfig, ObjectStoreConfig, StorageLayout
from ..pipelines.cleanse import cleanse_from_raw
from ..pipelines.ingest import http_fetcher, ingest_dataset
from ..storage import build_object_store


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def parse_dataset(config: Dict[str, Any]) -> DatasetConfig:
    ingest_date = date.fromisoformat(config["ingest_date"])
    return DatasetConfig(
        country_code=config["country_code"],
        dataset=config["dataset"],
        ingest_date=ingest_date,
        source_url=config["source_url"],
        source_format=config.get("source_format", "csv"),
    )


def parse_store(config: Dict[str, Any]) -> ObjectStoreConfig:
    local_root = config.get("local_path")
    return ObjectStoreConfig(
        bucket=config["bucket"],
        endpoint_url=config.get("endpoint_url"),
        access_key=config.get("access_key"),
        secret_key=config.get("secret_key"),
        region_name=config.get("region_name"),
        local_path=Path(local_root) if local_root else None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ingestion and cleansing for a dataset")
    parser.add_argument("--config", type=Path, required=True, help="Path to a YAML config file")
    args = parser.parse_args()

    raw_config = load_config(args.config)
    dataset_cfg = parse_dataset(raw_config["dataset"])
    store_cfg = parse_store(raw_config["object_store"])
    layout = StorageLayout()

    store = build_object_store(store_cfg)

    ingest_result = ingest_dataset(
        cfg=dataset_cfg,
        layout=layout,
        store=store,
        fetcher=http_fetcher(dataset_cfg.source_url),
    )

    cleanse_result = cleanse_from_raw(dataset_cfg, layout, store)

    print("Ingestion complete:", ingest_result)
    print("Cleansing complete:", cleanse_result)


if __name__ == "__main__":  # pragma: no cover
    main()
