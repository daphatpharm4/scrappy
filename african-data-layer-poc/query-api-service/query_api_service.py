import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from shared.config import get_query_api_settings  # noqa: E402
from shared.logging_utils import set_correlation_id, setup_logging  # noqa: E402
from shared.minio_client import get_minio_client  # noqa: E402
from shared.models import AnalyticsResponse, HealthResponse, Pagination  # noqa: E402

logger = logging.getLogger(__name__)
app = FastAPI(title="Query API Service")
cache: Dict[str, tuple[float, List[dict]]] = {}
setup_logging()


class DataFilters(BaseModel):
    country: Optional[str] = None
    provider: Optional[str] = None
    city: Optional[str] = None
    item: Optional[str] = None


class BearerAuth:
    def __init__(self, token: str):
        self.token = token

    def __call__(self, authorization: str = Header(default="")) -> None:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        provided = authorization.split("Bearer ", 1)[1]
        if provided != self.token:
            raise HTTPException(status_code=403, detail="Invalid token")


auth_dep = BearerAuth(get_query_api_settings().shared_token or "change-me")


def cache_key(domain: str, filters: DataFilters, pagination: Pagination) -> str:
    return f"{domain}:{filters.model_dump()}:{pagination.page}:{pagination.page_size}"


def fetch_latest_parquet(domain: str, country: Optional[str]) -> str:
    client = get_minio_client()
    prefix = f"clean/{domain}/"
    if country:
        prefix += f"{country.lower()}/"
    keys = [k for k in client.list_prefix(prefix) if k.endswith(".parquet")]
    if not keys:
        raise HTTPException(status_code=404, detail="No data available")
    keys.sort()
    return keys[-1]


def load_records(domain: str, country: Optional[str]) -> List[dict]:
    key = fetch_latest_parquet(domain, country)
    client = get_minio_client()
    data = client.download_bytes(key)
    with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
        tmp.write(data)
        tmp.flush()
        rel = duckdb.query(f"SELECT * FROM parquet_scan('{tmp.name}')").to_df()
    return rel.to_dict(orient="records")


def apply_filters(records: List[dict], filters: DataFilters) -> List[dict]:
    filtered = records
    if filters.country:
        filtered = [r for r in filtered if r.get("country", "").lower() == filters.country.lower()]
    if filters.provider:
        filtered = [r for r in filtered if r.get("provider", "").lower() == filters.provider.lower()]
    if filters.city:
        filtered = [r for r in filtered if r.get("city", "").lower() == filters.city.lower()]
    if filters.item:
        filtered = [r for r in filtered if r.get("item", "").lower() == filters.item.lower()]
    return filtered


def paginate(records: List[dict], pagination: Pagination) -> List[dict]:
    start = pagination.offset()
    end = start + pagination.page_size
    return records[start:end]


def get_cached(domain: str, filters: DataFilters, pagination: Pagination, ttl: int) -> Optional[List[dict]]:
    key = cache_key(domain, filters, pagination)
    if key in cache:
        ts, val = cache[key]
        if time.time() - ts < ttl:
            return val
        cache.pop(key, None)
    return None


def set_cached(domain: str, filters: DataFilters, pagination: Pagination, records: List[dict]) -> None:
    ttl = get_query_api_settings().cache_ttl_seconds
    cache[cache_key(domain, filters, pagination)] = (time.time(), records)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_query_api_settings()
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.version,
        environment=settings.environment,
    )


@app.get("/data/{domain}")
async def data_endpoint(
    domain: str,
    country: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    item: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: None = Depends(auth_dep),
):
    settings = get_query_api_settings()
    set_correlation_id()
    filters = DataFilters(country=country, provider=provider, city=city, item=item)
    pagination = Pagination(page=page, page_size=page_size)
    cached = get_cached(domain, filters, pagination, settings.cache_ttl_seconds)
    if cached is not None:
        return {"data": cached, "cached": True}
    records = load_records(domain, country)
    filtered = apply_filters(records, filters)
    paged = paginate(filtered, pagination)
    set_cached(domain, filters, pagination, paged)
    return {"data": paged, "cached": False}


@app.get("/analytics/average_price", response_model=AnalyticsResponse)
async def average_price(
    country: Optional[str] = Query(None),
    item: Optional[str] = Query(None),
    _: None = Depends(auth_dep),
):
    set_correlation_id()
    filters = DataFilters(country=country, item=item)
    records = load_records("prices", country)
    filtered = apply_filters(records, filters)
    values = [r["price"] for r in filtered if "price" in r]
    avg = sum(values) / len(values) if values else 0
    return AnalyticsResponse(metric="average_price", params=filters.model_dump(), value=avg)


@app.get("/analytics/provider_counts", response_model=AnalyticsResponse)
async def provider_counts(country: Optional[str] = Query(None), _: None = Depends(auth_dep)):
    set_correlation_id()
    filters = DataFilters(country=country)
    records = load_records("providers", country)
    filtered = apply_filters(records, filters)
    counts: Dict[str, int] = {}
    for r in filtered:
        provider = r.get("provider")
        counts[provider] = counts.get(provider, 0) + 1
    return AnalyticsResponse(metric="provider_counts", params=filters.model_dump(), value=len(counts))


@app.exception_handler(HTTPException)
async def http_exc_handler(request, exc: HTTPException):  # type: ignore[override]
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


if __name__ == "__main__":
    setup_logging()
    import uvicorn

    settings = get_query_api_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
