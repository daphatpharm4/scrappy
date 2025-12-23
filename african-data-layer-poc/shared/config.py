import os
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class MinioSettings(BaseModel):
    endpoint_url: HttpUrl = Field(..., alias="MINIO_ENDPOINT")
    access_key: str = Field(..., alias="MINIO_ACCESS_KEY")
    secret_key: str = Field(..., alias="MINIO_SECRET_KEY")
    bucket: str = Field("datalake", alias="MINIO_BUCKET")
    region: str = Field("us-east-1", alias="MINIO_REGION")
    secure: bool = Field(True, alias="MINIO_SECURE")


class ServiceSettings(BaseModel):
    service_name: str = Field(..., alias="SERVICE_NAME")
    version: str = Field("0.1.0", alias="SERVICE_VERSION")
    environment: str = Field("local", alias="SERVICE_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    shutdown_grace_seconds: int = Field(15, alias="SHUTDOWN_GRACE_SECONDS")
    request_timeout_seconds: int = Field(30, alias="REQUEST_TIMEOUT_SECONDS")
    shared_token: Optional[str] = Field(None, alias="SHARED_BEARER_TOKEN")


class QueryAPISettings(ServiceSettings):
    port: int = Field(8000, alias="QUERY_API_PORT")
    cache_ttl_seconds: int = Field(60, alias="QUERY_CACHE_TTL_SECONDS")


class AIQASettings(ServiceSettings):
    port: int = Field(8001, alias="AI_QA_PORT")
    query_api_url: HttpUrl = Field(..., alias="QUERY_API_URL")


@lru_cache(maxsize=1)
def get_minio_settings() -> MinioSettings:
    return MinioSettings()


@lru_cache(maxsize=1)
def get_service_settings() -> ServiceSettings:
    return ServiceSettings()


@lru_cache(maxsize=1)
def get_query_api_settings() -> QueryAPISettings:
    return QueryAPISettings()


@lru_cache(maxsize=1)
def get_ai_qa_settings() -> AIQASettings:
    return AIQASettings()


def get_env(key: str, default: str | None = None) -> str:
    value = os.getenv(key, default)
    if value is None:
        raise RuntimeError(f"Environment variable {key} is required")
    return value
