"""Minimal FastAPI app placeholder for the Query API service."""

from __future__ import annotations

import os
from fastapi import FastAPI

SERVICE_NAME = "query-api-service"
API_PREFIX = "/api"

app = FastAPI(title="Query API (Placeholder)", version="0.1.0")


def service_metadata() -> dict:
    return {
        "service": SERVICE_NAME,
        "environment": os.environ.get("ENVIRONMENT", "dev"),
        "storage_account": os.environ.get("AZURE_STORAGE_ACCOUNT", ""),
        "blob_container": os.environ.get("BLOB_CONTAINER", ""),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", **service_metadata()}


@app.get(f"{API_PREFIX}/health")
def api_health() -> dict:
    return {"status": "ok", **service_metadata()}


@app.get(f"{API_PREFIX}/info")
def info() -> dict:
    return {"message": "Query API placeholder running", **service_metadata()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
