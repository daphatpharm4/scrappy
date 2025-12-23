from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class BaseRecord(BaseModel):
    country: str = Field(..., description="ISO 3166-1 alpha-3 country code")
    provider: str | None = Field(None, description="Data provider name")
    captured_at: datetime


class PriceRecord(BaseRecord):
    item: str
    price: float
    currency: str


class RealEstateRecord(BaseRecord):
    city: str
    bedrooms: int
    bathrooms: int
    rent: float
    currency: str


class ProviderRecord(BaseModel):
    country: str
    provider: str
    category: str
    website: str | None = None


class RawIngestMetadata(BaseModel):
    source_type: str
    ingested_at: datetime
    correlation_id: str
    domain: str


class RawIngestEnvelope(BaseModel):
    metadata: RawIngestMetadata
    records: List[dict]


class CleanedRecord(BaseModel):
    domain: str
    country: str
    payload: dict
    source_raw_key: str
    cleaned_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str


class Pagination(BaseModel):
    page: int = 1
    page_size: int = 50

    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class AnalyticsResponse(BaseModel):
    metric: str
    params: dict
    value: float | int


class AIAnswer(BaseModel):
    intent: str
    params: dict
    answer: str
    data: list[dict]
