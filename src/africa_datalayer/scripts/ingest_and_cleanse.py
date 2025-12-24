"""Ingest and cleanse pipeline entrypoint."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import time
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import typer
import yaml
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from httpx import Client, HTTPError

app = typer.Typer(help="Africa Data Layer pipeline runner")


def _configure_logging(log_level: str) -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    return logging.getLogger(__name__)


logger = _configure_logging("INFO")


@dataclass
class RetryConfig:
    attempts: int = 3
    backoff_seconds: int = 2
    max_backoff_seconds: int = 30


@dataclass
class FetchConfig:
    url: str
    method: str = "GET"
    format: str = "csv"
    compression: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    retry: RetryConfig = field(default_factory=RetryConfig)


@dataclass
class SchemaField:
    name: str
    dtype: str
    required: bool = False


@dataclass
class DatasetConfig:
    name: str
    domain: str
    country: str
    source_id: str
    run_mode: str = "batch"
    fetch: FetchConfig = field(default_factory=FetchConfig)
    schema: List[SchemaField] = field(default_factory=list)


def _parse_retry(raw: Dict[str, Any]) -> RetryConfig:
    return RetryConfig(
        attempts=int(raw.get("attempts", 3)),
        backoff_seconds=int(raw.get("backoff_seconds", 2)),
        max_backoff_seconds=int(raw.get("max_backoff_seconds", 30)),
    )


def _parse_fetch(raw: Dict[str, Any]) -> FetchConfig:
    retry_cfg = _parse_retry(raw.get("retry", {}))
    return FetchConfig(
        url=str(raw["url"]),
        method=str(raw.get("method", "GET")).upper(),
        format=str(raw.get("format", "csv")).lower(),
        compression=raw.get("compression"),
        headers=raw.get("headers", {}) or {},
        params=raw.get("params", {}) or {},
        retry=retry_cfg,
    )


def _parse_schema(raw_schema: Dict[str, Any] | List[Dict[str, Any]]) -> List[SchemaField]:
    fields = raw_schema.get("fields", raw_schema) if isinstance(raw_schema, dict) else raw_schema
    parsed: List[SchemaField] = []
    for field_def in fields or []:
        if not isinstance(field_def, dict) or "name" not in field_def or "dtype" not in field_def:
            continue
        parsed.append(
            SchemaField(
                name=str(field_def["name"]),
                dtype=str(field_def["dtype"]),
                required=bool(field_def.get("required", False)),
            )
        )
    return parsed


def _load_datasets(config_path: Path) -> List[DatasetConfig]:
    if not config_path.exists():
        logger.warning("Config file not found at %s; nothing to ingest", config_path)
        return []

    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    datasets_raw = raw.get("datasets", [])
    datasets: List[DatasetConfig] = []
    for entry in datasets_raw:
        if not isinstance(entry, dict):
            continue
        try:
            fetch_cfg = _parse_fetch(entry["fetch"])
            schema = _parse_schema(entry.get("schema", []))
            datasets.append(
                DatasetConfig(
                    name=str(entry["name"]),
                    domain=str(entry["domain"]),
                    country=str(entry["country"]),
                    source_id=str(entry["source_id"]),
                    run_mode=str(entry.get("run_mode", "batch")).lower(),
                    fetch=fetch_cfg,
                    schema=schema,
                )
            )
        except KeyError as exc:
            logger.error("Dataset entry missing required key %s: %s", exc, entry)
            continue

    return datasets


def _create_blob_service(storage_account: str, credential: DefaultAzureCredential) -> BlobServiceClient:
    account_url = f"https://{storage_account}.blob.core.windows.net"
    return BlobServiceClient(account_url=account_url, credential=credential)


def _upload_blob(
    blob_service: BlobServiceClient,
    container: str,
    blob_name: str,
    data: bytes,
    content_type: str,
) -> None:
    client = blob_service.get_blob_client(container=container, blob=blob_name)
    client.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type),
    )
    logger.info("Uploaded blob %s", blob_name)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fetch_bytes(fetch_cfg: FetchConfig) -> Tuple[bytes, Dict[str, Any]]:
    attempt = 0
    last_error: Optional[Exception] = None
    while attempt < fetch_cfg.retry.attempts:
        try:
            with Client(timeout=60.0, follow_redirects=True) as client:
                response = client.request(
                    fetch_cfg.method,
                    fetch_cfg.url,
                    headers=fetch_cfg.headers,
                    params=fetch_cfg.params,
                )
                response.raise_for_status()
                return response.content, dict(response.headers)
        except HTTPError as exc:
            last_error = exc
            delay = min(
                fetch_cfg.retry.backoff_seconds * (2**attempt),
                fetch_cfg.retry.max_backoff_seconds,
            )
            logger.warning(
                "Fetch failed (attempt %s/%s): %s; retrying in %ss",
                attempt + 1,
                fetch_cfg.retry.attempts,
                exc,
                delay,
            )
            time.sleep(delay)
            attempt += 1

    raise RuntimeError(f"Failed to fetch {fetch_cfg.url} after retries") from last_error


def _deterministic_record_id(row: pd.Series, dataset: DatasetConfig) -> str:
    payload = {
        "dataset": dataset.source_id,
        "values": row.to_dict(),
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _apply_schema(df: pd.DataFrame, dataset: DatasetConfig) -> pd.DataFrame:
    for field in dataset.schema:
        if field.name not in df.columns:
            df[field.name] = pd.NA
        if field.dtype:
            try:
                if field.dtype.startswith("datetime"):
                    df[field.name] = pd.to_datetime(df[field.name], errors="coerce")
                else:
                    df[field.name] = df[field.name].astype(field.dtype, errors="ignore")
            except TypeError:
                logger.warning("Could not cast %s to %s", field.name, field.dtype)
    return df


def _quality_report(df: pd.DataFrame, dataset: DatasetConfig) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "row_count": len(df.index),
        "columns": list(df.columns),
        "dataset": dataset.source_id,
    }
    missing_required: Dict[str, int] = {}
    for field in dataset.schema:
        if field.required:
            missing_required[field.name] = int(df[field.name].isna().sum())
    report["missing_required"] = missing_required
    return report


def _build_paths(prefix: str, dataset: DatasetConfig, ingest_date: str) -> str:
    return f"{prefix}/{dataset.country}/{dataset.domain}/{dataset.source_id}/{ingest_date}"


def _dataframe_from_bytes(fetch_cfg: FetchConfig, payload: bytes) -> pd.DataFrame:
    if fetch_cfg.format == "csv":
        return pd.read_csv(io.BytesIO(payload))
    if fetch_cfg.format == "json":
        parsed = json.loads(payload.decode("utf-8"))
        if isinstance(parsed, list):
            return pd.DataFrame(parsed)
        if isinstance(parsed, dict):
            return pd.DataFrame([parsed])
    return pd.DataFrame()


def _write_parquet(df: pd.DataFrame) -> bytes:
    table = pa.Table.from_pandas(df, preserve_index=False)
    buffer = io.BytesIO()
    pq.write_table(table, buffer, compression="zstd")
    return buffer.getvalue()


def _run_pipeline_for_dataset(
    dataset: DatasetConfig,
    blob_service: BlobServiceClient,
    container: str,
    raw_prefix: str,
    clean_prefix: str,
    curated_prefix: str,
    run_mode: str,
) -> None:
    ingest_date = datetime.now(timezone.utc).date().isoformat()
    raw_bytes, response_headers = _fetch_bytes(dataset.fetch)
    raw_path = _build_paths(raw_prefix, dataset, ingest_date)
    raw_ext = "json" if dataset.fetch.format == "json" else dataset.fetch.format
    raw_blob_name = f"{raw_path}/source.{raw_ext}"
    _upload_blob(
        blob_service,
        container,
        raw_blob_name,
        raw_bytes,
        content_type="application/octet-stream",
    )

    raw_manifest = {
        "dataset": dataset.name,
        "source_id": dataset.source_id,
        "country": dataset.country,
        "domain": dataset.domain,
        "ingest_date": ingest_date,
        "run_mode": run_mode,
        "content_length": len(raw_bytes),
        "checksum": _sha256_bytes(raw_bytes),
        "response_headers": response_headers,
        "raw_blob": raw_blob_name,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    _upload_blob(
        blob_service,
        container,
        f"{raw_path}/manifest.json",
        json.dumps(raw_manifest, indent=2).encode("utf-8"),
        content_type="application/json",
    )

    df = _dataframe_from_bytes(dataset.fetch, raw_bytes)
    df = _apply_schema(df, dataset)
    df["country"] = dataset.country
    df["domain"] = dataset.domain
    df["source_id"] = dataset.source_id
    df["ingest_date"] = ingest_date
    df["record_id"] = df.apply(lambda row: _deterministic_record_id(row, dataset), axis=1)

    parquet_bytes = _write_parquet(df)
    clean_path = _build_paths(clean_prefix, dataset, ingest_date)
    _upload_blob(
        blob_service,
        container,
        f"{clean_path}/data.parquet",
        parquet_bytes,
        content_type="application/octet-stream",
    )

    clean_manifest = {
        "dataset": dataset.name,
        "source_id": dataset.source_id,
        "country": dataset.country,
        "domain": dataset.domain,
        "ingest_date": ingest_date,
        "row_count": int(len(df.index)),
        "columns": list(df.columns),
        "partitions": {"country": dataset.country, "domain": dataset.domain, "ingest_date": ingest_date},
        "checksum": _sha256_bytes(parquet_bytes),
        "clean_blob": f"{clean_path}/data.parquet",
    }
    _upload_blob(
        blob_service,
        container,
        f"{clean_path}/manifest.json",
        json.dumps(clean_manifest, indent=2).encode("utf-8"),
        content_type="application/json",
    )

    quality = _quality_report(df, dataset)
    curated_path = _build_paths(curated_prefix, dataset, ingest_date)
    curated_manifest = {
        "dataset": dataset.name,
        "source_id": dataset.source_id,
        "run_mode": run_mode,
        "quality": quality,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _upload_blob(
        blob_service,
        container,
        f"{curated_path}/quality.json",
        json.dumps(quality, indent=2).encode("utf-8"),
        content_type="application/json",
    )
    _upload_blob(
        blob_service,
        container,
        f"{curated_path}/manifest.json",
        json.dumps(curated_manifest, indent=2).encode("utf-8"),
        content_type="application/json",
    )
    logger.info("Completed dataset %s", dataset.source_id)


@app.command("ingest-and-cleanse")
def ingest_and_cleanse(
    config: Path = typer.Option(
        Path("configs/datasets.yaml"),
        "--config",
        "-c",
        help="Path to datasets config file.",
    ),
    run_mode: str = typer.Option("batch", envvar="RUN_MODE", help="Run mode (batch, backfill, dev)."),
    log_level: str = typer.Option("INFO", envvar="LOG_LEVEL", help="Logging level."),
) -> None:
    global logger
    logger = _configure_logging(log_level)
    run_mode = run_mode.lower()
    datasets = _load_datasets(config)

    if not datasets:
        logger.info("No datasets defined; exiting early")
        return

    storage_account = os.getenv("AZURE_STORAGE_ACCOUNT")
    container = os.getenv("BLOB_CONTAINER", "datalake")
    raw_prefix = os.getenv("BLOB_PREFIX_RAW", "raw")
    clean_prefix = os.getenv("BLOB_PREFIX_CLEAN", "clean")
    curated_prefix = os.getenv("BLOB_PREFIX_CURATED", "curated")

    if not storage_account:
        raise typer.BadParameter("AZURE_STORAGE_ACCOUNT must be set")

    credential = DefaultAzureCredential(
        managed_identity_client_id=os.getenv("AZURE_CLIENT_ID"),
        exclude_interactive_browser_credential=True,
    )
    blob_service = _create_blob_service(storage_account, credential)

    for dataset in datasets:
        allowed_modes = ("batch", "backfill", "dev", "any")
        if dataset.run_mode not in allowed_modes:
            logger.warning("Skipping dataset %s due to unsupported run_mode %s", dataset.name, dataset.run_mode)
            continue
        if dataset.run_mode not in ("any", run_mode):
            logger.info(
                "Skipping dataset %s due to run_mode mismatch (dataset=%s, runner=%s)",
                dataset.name,
                dataset.run_mode,
                run_mode,
            )
            continue
        _run_pipeline_for_dataset(
            dataset=dataset,
            blob_service=blob_service,
            container=container,
            raw_prefix=raw_prefix,
            clean_prefix=clean_prefix,
            curated_prefix=curated_prefix,
            run_mode=run_mode,
        )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
