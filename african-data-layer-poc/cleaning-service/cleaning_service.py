import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import io

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import typer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from shared.logging_utils import set_correlation_id, setup_logging  # noqa: E402
from shared.models import (  # noqa: E402
    CleanedRecord,
    HealthResponse,
    PriceRecord,
    ProviderRecord,
    RealEstateRecord,
)
from shared.minio_client import get_minio_client  # noqa: E402
from shared.retry import RetryConfig, retry  # noqa: E402
from shared.config import get_service_settings  # noqa: E402

logger = logging.getLogger(__name__)
app = FastAPI(title="Cleaning Service")
cli = typer.Typer(help="Clean raw objects into curated outputs")
setup_logging()

MANIFEST_KEY = "curated/manifests/processed_raw_files.json"


@retry(RetryConfig(attempts=3, backoff_seconds=2))
def fetch_raw_keys() -> List[str]:
    client = get_minio_client()
    keys = [k for k in client.list_unprocessed("raw/", MANIFEST_KEY) if k.endswith(".json")]
    return keys


def load_raw(key: str) -> dict:
    client = get_minio_client()
    return client.download_json(key)


def normalize_record(domain: str, record: dict, raw_key: str) -> dict | None:
    try:
        if domain == "prices":
            parsed = PriceRecord(**{**record, "country": record.get("country", "").upper()})
            return {
                "domain": domain,
                "country": parsed.country,
                "item": parsed.item,
                "price": parsed.price,
                "currency": parsed.currency,
                "provider": parsed.provider,
                "captured_at": parsed.captured_at,
                "source_raw_key": raw_key,
            }
        if domain == "realestate":
            parsed = RealEstateRecord(
                country=record.get("country", "").upper(),
                city=record["city"],
                bedrooms=int(record["bedrooms"]),
                bathrooms=int(record["bathrooms"]),
                rent=float(record["rent"]),
                currency=record["currency"],
                provider=record.get("provider"),
                captured_at=datetime.fromisoformat(record["captured_at"].replace("Z", "+00:00")),
            )
            return {
                "domain": domain,
                "country": parsed.country,
                "city": parsed.city,
                "bedrooms": parsed.bedrooms,
                "bathrooms": parsed.bathrooms,
                "rent": parsed.rent,
                "currency": parsed.currency,
                "provider": parsed.provider,
                "captured_at": parsed.captured_at,
                "source_raw_key": raw_key,
            }
        if domain == "providers":
            parsed = ProviderRecord(**record)
            return {
                "domain": domain,
                "country": parsed.country,
                "provider": parsed.provider,
                "category": parsed.category,
                "website": parsed.website,
                "source_raw_key": raw_key,
            }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to normalize record", extra={"extra_data": {"domain": domain, "error": str(exc)}})
        return None
    return None


def write_outputs(domain: str, country: str, cleaned: List[dict]) -> Dict[str, str]:
    client = get_minio_client()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base_key = f"clean/{domain}/{country}/{date_str}"
    json_key = f"{base_key}.json"
    parquet_key = f"{base_key}.parquet"
    client.upload_json(json_key, cleaned)
    df = pd.DataFrame(cleaned)
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True)
    table = pa.Table.from_pandas(df)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="zstd")
    client.upload_bytes(parquet_key, buf.getvalue())
    return {"json": json_key, "parquet": parquet_key}


def process_raw_key(raw_key: str) -> Dict[str, str]:
    envelope = load_raw(raw_key)
    metadata = envelope.get("metadata", {})
    domain = metadata.get("domain")
    records = envelope.get("records", [])
    cleaned: List[dict] = []
    for record in records:
        normalized = normalize_record(domain, record, raw_key)
        if normalized:
            cleaned.append(normalized)
    if not cleaned:
        logger.warning("No valid records", extra={"extra_data": {"raw_key": raw_key}})
        return {}
    country = cleaned[0]["country"].lower()
    outputs = write_outputs(domain, country, cleaned)
    client = get_minio_client()
    client.write_manifest_entry(MANIFEST_KEY, raw_key)
    logger.info("Processed raw file", extra={"extra_data": {"raw_key": raw_key, "outputs": outputs}})
    return outputs


def run_cleaning() -> Dict[str, Dict[str, str]]:
    set_correlation_id()
    processed: Dict[str, Dict[str, str]] = {}
    for raw_key in fetch_raw_keys():
        outputs = process_raw_key(raw_key)
        processed[raw_key] = outputs
    return processed


@app.post("/clean")
async def clean_endpoint() -> JSONResponse:
    set_correlation_id()
    processed = run_cleaning()
    return JSONResponse({"status": "ok", "processed": processed})


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_service_settings()
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.version,
        environment=settings.environment,
    )


@cli.command()
def run() -> None:
    setup_logging()
    run_cleaning()


if __name__ == "__main__":
    setup_logging()
    cli()
