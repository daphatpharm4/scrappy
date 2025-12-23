from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, Optional


@dataclass(slots=True)
class DatasetConfig:
    """Configuration describing a source dataset and how it should be stored.

    Attributes:
        country_code: ISO-3166 alpha-3 code (e.g., "KEN", "CMR").
        dataset: A short identifier for the dataset (e.g., "economic_indicators").
        ingest_date: The logical ingest date for partitioning and traceability.
        source_url: HTTP/HTTPS endpoint for the raw data export.
        source_format: Expected format of the source; currently "csv" or "json".
    """

    country_code: str
    dataset: str
    ingest_date: date
    source_url: str
    source_format: Literal["csv", "json"] = "csv"


@dataclass(slots=True)
class StorageLayout:
    """Logical layout for object prefixes in the data lake."""

    raw_prefix: str = "raw"
    cleansed_prefix: str = "cleansed"

    def raw_path(self, cfg: DatasetConfig) -> str:
        return f"{self.raw_prefix}/{cfg.country_code.lower()}/{cfg.dataset}/{cfg.ingest_date.isoformat()}/"

    def cleansed_path(self, cfg: DatasetConfig) -> str:
        return (
            f"{self.cleansed_prefix}/{cfg.country_code.lower()}/"
            f"{cfg.dataset}/ingest_date={cfg.ingest_date.isoformat()}/"
        )


@dataclass(slots=True)
class ObjectStoreConfig:
    """Settings to build an object store client."""

    bucket: str
    endpoint_url: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    region_name: Optional[str] = None
    local_path: Optional[Path] = None
