from __future__ import annotations

import pandas as pd


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to snake_case for downstream compatibility."""

    renamed = {col: col.strip().lower().replace(" ", "_") for col in df.columns}
    return df.rename(columns=renamed)


def ensure_partition_columns(df: pd.DataFrame, country_code: str, ingest_date: str) -> pd.DataFrame:
    enriched = df.copy()
    enriched["country"] = country_code.upper()
    enriched["ingest_date"] = ingest_date
    return enriched
