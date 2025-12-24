from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class BaseDataQuery(BaseModel):
    provider: Optional[str] = Field(default=None, min_length=1)
    country: Optional[str] = Field(default=None, min_length=2, max_length=3)
    region: Optional[str] = Field(default=None, min_length=2)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    limit: int = Field(default=1000, ge=1, le=10000)

    @field_validator("provider", "country", "region", mode="before")
    @classmethod
    def normalize_strings(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned.upper() if cleaned else None

    @model_validator(mode="after")
    def validate_date_range(self) -> "BaseDataQuery":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class PriceQuery(BaseDataQuery):
    min_price: Optional[float] = Field(default=None, ge=0)
    max_price: Optional[float] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_price_range(self) -> "PriceQuery":
        if self.min_price is not None and self.max_price is not None and self.max_price < self.min_price:
            raise ValueError("max_price must be greater than or equal to min_price")
        return self


class RealEstateQuery(BaseDataQuery):
    min_bedrooms: Optional[int] = Field(default=None, ge=0)
    max_bedrooms: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_bedrooms(self) -> "RealEstateQuery":
        if (
            self.min_bedrooms is not None
            and self.max_bedrooms is not None
            and self.max_bedrooms < self.min_bedrooms
        ):
            raise ValueError("max_bedrooms must be greater than or equal to min_bedrooms")
        return self


class AnalyticsQuery(BaseDataQuery):
    metric: Optional[str] = Field(default=None, description="Numeric column to aggregate")
