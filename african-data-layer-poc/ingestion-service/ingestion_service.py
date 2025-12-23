import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import typer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from ingestion_service.mock_loaders import load_api_payload, scrape_static_html  # noqa: E402
from shared.config import get_service_settings  # noqa: E402
from shared.logging_utils import get_correlation_id, set_correlation_id, setup_logging  # noqa: E402
from shared.minio_client import get_minio_client  # noqa: E402
from shared.models import HealthResponse, RawIngestEnvelope, RawIngestMetadata  # noqa: E402
from shared.retry import RetryConfig, retry  # noqa: E402

logger = logging.getLogger(__name__)
app = FastAPI(title="Ingestion Service")
cli = typer.Typer(help="Ingest sample inputs into MinIO")
setup_logging()

DOMAINS = ["prices", "realestate", "providers"]


class IngestRequest(BaseModel):
    domain: str | None = None
    country: str | None = None


@retry(RetryConfig(attempts=3, backoff_seconds=1.5))
def load_json_samples(domain: str, country: str) -> List[dict]:
    return load_api_payload(domain, country)


def load_html_samples(domain: str) -> List[dict]:
    return scrape_static_html(domain)


def build_envelope(domain: str, records: List[dict], correlation_id: str) -> RawIngestEnvelope:
    metadata = RawIngestMetadata(
        source_type="sample",
        ingested_at=datetime.now(timezone.utc),
        correlation_id=correlation_id,
        domain=domain,
    )
    return RawIngestEnvelope(metadata=metadata, records=records)


def write_raw(domain: str, country: str, envelope: RawIngestEnvelope) -> str:
    minio = get_minio_client()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"raw/{domain}/{country}/{timestamp}.json"
    minio.upload_json(
        key,
        envelope.model_dump(),
        metadata={"country": country, "domain": domain},
    )
    return key


def ingest_domain_country(domain: str, country: str, correlation_id: str) -> str:
    api_records = load_json_samples(domain, country)
    html_records = [r for r in load_html_samples(domain) if r.get("country") == country.upper()]
    combined = api_records + html_records
    envelope = build_envelope(domain, combined, correlation_id)
    return write_raw(domain, country.lower(), envelope)


def ingest_all(domain: str | None = None, country: str | None = None) -> Dict[str, List[str]]:
    correlation_id = set_correlation_id(get_correlation_id())
    results: Dict[str, List[str]] = {}
    for dom in DOMAINS if domain is None else [domain]:
        for ctry in ["kenya", "cameroon"] if country is None else [country]:
            key = ingest_domain_country(dom, ctry, correlation_id)
            logger.info("Ingested sample", extra={"extra_data": {"domain": dom, "country": ctry, "key": key}})
            results.setdefault(dom, []).append(key)
    return results


@app.post("/ingest")
async def ingest_endpoint(req: IngestRequest) -> JSONResponse:
    set_correlation_id()
    results = ingest_all(req.domain, req.country)
    return JSONResponse({"status": "ok", "written": results})


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
def run(domain: str = typer.Option(None), country: str = typer.Option(None)) -> None:
    setup_logging()
    set_correlation_id()
    ingest_all(domain, country)


if __name__ == "__main__":
    setup_logging()
    cli()
